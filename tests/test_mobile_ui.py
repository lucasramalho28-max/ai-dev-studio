"""Mobile navigation, editing and responsive layout using a real browser."""
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from werkzeug.serving import make_server
from app import create_app
from tests.test_browser_real import sync_playwright


@unittest.skipIf(sync_playwright is None, 'Playwright não instalado')
class MobileUITest(unittest.TestCase):
    def test_mobile_panels_preserve_editor_and_fit_viewport(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp)/'data', Path(tmp)/'workspace', testing=True)
            studio = app.extensions['studio']
            server = make_server('127.0.0.1', 0, app, threaded=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with sync_playwright() as pw:
                    try:
                        browser = pw.chromium.launch(headless=True)
                    except Exception:
                        browser = pw.chromium.launch(headless=True, channel='msedge')
                    try:
                        page = browser.new_page(viewport={'width':390, 'height':844}, is_mobile=True, has_touch=True)
                        # Exercise the local editor without relying on external assets.
                        page.route('https://**/*', lambda route: route.abort())
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('dialog', lambda dialog: dialog.accept('Mobile QA' if dialog.type == 'prompt' else None))
                        page.goto(f'http://127.0.0.1:{server.server_port}', wait_until='domcontentloaded')
                        page.locator('#new-project').click()
                        page.locator('#studio-dialog-input').fill('Mobile QA')
                        page.locator('#studio-dialog button[type=submit]').click()
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        pid = studio['store'].rows('SELECT id FROM projects')[0]['id']
                        text = studio['files'].read(pid, 'app.py')['content'] + '\n# mobile edit\n'
                        page.locator('#fallback-editor').fill(text)
                        switch = page.locator('.mobile-switch')
                        switch.locator('[data-mobile-pane=chat]').click()
                        page.locator('#prompt').fill('Mensagem preservada')
                        switch.locator('[data-mobile-pane=files]').click()
                        self.assertTrue(page.locator('#project').is_visible())
                        page.locator('#files button[title^="app.py "]').click()
                        self.assertEqual(page.locator('#fallback-editor').input_value(), text)
                        page.locator('#save-file').click()
                        page.wait_for_function("document.querySelector('#toast').textContent==='Arquivo salvo.'")
                        self.assertEqual(studio['files'].read(pid, 'app.py')['content'], text)
                        for width, height in ((320,568), (390,844), (844,390)):
                            page.set_viewport_size({'width':width, 'height':height})
                            for pane in ('files','chat','logs','workspace'):
                                switch.locator(f'[data-mobile-pane={pane}]').click()
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                            for view in ('agents','logistics','models','settings','editor'):
                                page.locator(f'.nav[data-view={view}]').click()
                                self.assertTrue(page.locator('#view-'+view).is_visible())
                                self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), width)
                        switch.locator('[data-mobile-pane=chat]').click()
                        self.assertEqual(page.locator('#prompt').input_value(), 'Mensagem preservada')
                        page.set_viewport_size({'width':390,'height':844})
                        artifacts = Path(__file__).resolve().parents[1]/'data'/'qa'
                        artifacts.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(artifacts/'studio-mobile-chat.png'))
                        page.locator('.nav[data-view=editor]').click()
                        page.screenshot(path=str(artifacts/'studio-mobile-editor.png'))
                        page.set_viewport_size({'width':1600,'height':1000})
                        self.assertFalse(switch.is_visible())
                        self.assertTrue(page.locator('.explorer').is_visible())
                        self.assertTrue(page.locator('.chat-panel').is_visible())
                        page.locator('#chat-mode').select_option('query')
                        page.locator('#prompt').fill('Qual login e senha?')
                        page.locator('#prompt').press('Enter')
                        page.get_by_text('Não consigo confirmar um login e uma senha ativos', exact=False).wait_for()
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        with patch.object(studio['ollama'], 'tags', return_value=[]), patch.object(studio['ollama'], 'chat', return_value=iter([{'done':True, 'done_reason':'length'}])):
                            page.locator('#chat-mode').select_option('change')
                            page.locator('#prompt').fill('Corrija o menu')
                            page.locator('#prompt').press('Enter')
                            page.locator('.message').filter(has_text='Falha no pedido:').wait_for()
                            page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        self.assertIn('Não foi possível', page.locator('#chat-status').inner_text())
                        page.reload(wait_until='domcontentloaded')
                        page.locator('.message').filter(has_text='Falha no pedido:').wait_for()
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()
            finally:
                server.shutdown()
                thread.join(timeout=5)
                for worker in list(studio['jobs'].threads.values()):
                    worker.join(timeout=5)
