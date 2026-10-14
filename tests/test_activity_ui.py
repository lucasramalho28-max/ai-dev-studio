"""Exercise live task transitions and replay using the real SSE endpoint."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.serving import make_server
from app import create_app
from tests.test_browser_real import sync_playwright


@unittest.skipIf(sync_playwright is None, 'Playwright não instalado')
class ActivityUITest(unittest.TestCase):
    def test_agents_progress_reconnect_and_finish(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp)/'data', Path(tmp)/'workspace', testing=True)
            studio = app.extensions['studio']
            server = make_server('127.0.0.1',0,app,threaded=True)
            thread = threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            first, second, third = threading.Event(), threading.Event(), threading.Event()
            calls = []

            def model(*args, **kwargs):
                calls.append(1)
                if len(calls) == 1:
                    first.wait(timeout=20)
                elif len(calls) == 2:
                    second.wait(timeout=20)
                elif len(calls) == 11:
                    third.wait(timeout=20)
                yield {'message':{'content':json.dumps({'summary':'Análise da etapa.','files':[],'edits':[]})},'done':True}

            try:
                with patch.object(studio['ollama'],'tags',return_value=[]), patch.object(studio['ollama'],'chat',side_effect=model), sync_playwright() as pw:
                    try: browser = pw.chromium.launch(headless=True)
                    except Exception: browser = pw.chromium.launch(headless=True,channel='msedge')
                    try:
                        page = browser.new_page(viewport={'width':390,'height':844})
                        page.route('https://**/*',lambda route:route.abort())
                        page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
                        page.locator('#new-project').click()
                        page.locator('#studio-dialog-input').fill('QA atividade')
                        page.locator('#studio-dialog button[type=submit]').click()
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        page.locator('.mobile-switch [data-mobile-pane=chat]').click()
                        page.locator('#orchestrate').check()
                        page.locator('#prompt').fill('Planeje uma melhoria no projeto')
                        page.locator('#prompt').press('Enter')
                        page.locator('.execution-tasks li[data-status=running]').filter(has_text='Coordenador').wait_for()
                        self.assertEqual(page.locator('.execution-tasks li').count(),10)
                        self.assertEqual(page.locator('.execution-tasks li[data-status=queued]').count(),9)
                        self.assertIn('Interromper',page.locator('#send').inner_text())
                        self.assertTrue(page.locator('#send').is_enabled())
                        self.assertEqual(page.locator('#send').get_attribute('type'),'button')
                        self.assertIn('aguardando resposta',page.locator('.execution-current').inner_text())
                        page.locator('.mobile-switch [data-mobile-pane=workspace]').click()
                        page.locator('#organogram-mode').click()
                        self.assertTrue(page.locator('#organogram-panel').is_visible())
                        self.assertEqual(page.locator('.org-agent').count(),8)
                        self.assertEqual(page.locator('.org-node').count(),10)
                        self.assertIn('Coordenador',page.locator('.org-node[data-status=running]').inner_text())
                        self.assertEqual(page.locator('.org-transfer[data-state=active]').count(),0)
                        first.set()
                        page.locator('.org-node[data-status=running]').filter(has_text='Logística').wait_for()
                        self.assertEqual(page.locator('.org-transfer[data-state=active]').count(),1)
                        self.assertIn('Coordenador',page.locator('.org-transfer[data-state=active]').inner_text())
                        page.locator('.org-node[data-status=running]').click()
                        self.assertIn('Recebido de Coordenador',page.locator('.org-detail').inner_text())
                        self.assertIn('aguardando resposta',page.locator('.org-detail').inner_text())
                        page.set_viewport_size({'width':1600,'height':1000})
                        page.locator('#organogram-panel').evaluate('(panel)=>panel.scrollTop=0')
                        artifacts=Path(__file__).resolve().parents[1]/'data'/'qa'
                        artifacts.mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(artifacts/'agent-organogram-desktop.png'))
                        page.set_viewport_size({'width':390,'height':844})
                        page.locator('#organogram-panel').evaluate('(panel)=>panel.scrollTop=0')
                        page.screenshot(path=str(artifacts/'agent-organogram-mobile.png'))
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
                        self.assertEqual(page.locator('.execution-tasks li[data-status=completed]').count(),1)
                        page.reload(wait_until='domcontentloaded')
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        page.locator('.mobile-switch [data-mobile-pane=chat]').click()
                        page.locator('.execution-tasks li[data-status=running]').filter(has_text='Logística').wait_for()
                        self.assertEqual(page.locator('.execution-tasks li').count(),10)
                        self.assertIn('Interromper',page.locator('#send').inner_text())
                        artifacts = Path(__file__).resolve().parents[1]/'data'/'qa'
                        artifacts.mkdir(parents=True,exist_ok=True)
                        page.screenshot(path=str(artifacts/'chat-live-activity.png'))
                        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
                        send = page.locator('#send').bounding_box()
                        self.assertLessEqual(send['y'] + send['height'], 844 - 65)
                        second.set()
                        page.locator('.execution-card[data-status=completed]').wait_for()
                        self.assertEqual(page.locator('.execution-tasks li[data-status=running]').count(),0)
                        self.assertEqual(page.locator('.execution-tasks li[data-status=completed]').count(),10)
                        self.assertEqual(len(calls),10)
                        page.reload(wait_until='domcontentloaded')
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        page.locator('#organogram-mode').click()
                        self.assertEqual(page.locator('.org-node[data-status=completed]').count(),10)
                        self.assertEqual(page.locator('.org-transfer[data-state=confirmed]').count(),9)
                        page.locator('.mobile-switch [data-mobile-pane=chat]').click()
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        self.assertEqual(page.locator('#send').get_attribute('type'),'submit')
                        page.locator('#orchestrate').uncheck()
                        page.locator('#prompt').fill('Planeje outra melhoria')
                        page.locator('#prompt').press('Enter')
                        page.locator('.execution-card[data-status=running] li[data-status=running]').wait_for()
                        self.assertEqual(page.locator('#prompt').input_value(),'')
                        page.locator('#send').click()
                        page.wait_for_function("document.querySelector('#chat-status').textContent.includes('Interrupção solicitada')")
                        self.assertEqual(page.locator('#send').inner_text(),'Interrompendo…')
                        self.assertTrue(page.locator('#send').is_disabled())
                        third.set()
                        page.locator('.execution-card[data-status=cancelled]').wait_for()
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        self.assertTrue(page.locator('#send').is_enabled())
                        self.assertEqual(len(studio['store'].rows("SELECT id FROM jobs WHERE kind='chat'")),2)
                    finally: browser.close()
            finally:
                first.set(); second.set(); third.set()
                for worker in list(studio['jobs'].threads.values()): worker.join(timeout=10)
                server.shutdown();server.server_close();thread.join(timeout=5)
