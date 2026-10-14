"""Automatic saving stays opt-in and protects unsaved editor content."""
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
class AutoApprovalUITest(unittest.TestCase):
    def test_opt_in_new_requests_and_dirty_buffer_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'data',Path(tmp)/'workspace',testing=True)
            studio=app.extensions['studio']
            server=make_server('127.0.0.1',0,app,threaded=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            outputs=iter([
                {'summary':'','files':[{'path':'old.txt','content':'manual review'}],'edits':[]},
                {'summary':'','files':[{'path':'automatic.txt','content':'saved automatically'}],'edits':[]},
                {'summary':'','files':[{'path':'app.py','content':'# proposed replacement\n'}],'edits':[]},
                {'summary':'','files':[{'path':'app.py','content':'# another replacement\n'}],'edits':[]},
            ])
            calls=[]
            def model(*args,**kwargs):
                calls.append(1)
                if len(calls)==4:
                    project=studio['store'].rows('SELECT id FROM projects')[0]['id']
                    current=studio['files'].read(project,'app.py')
                    studio['files'].write(project,'app.py',current['content']+'\n# outside change\n',current['hash'])
                yield {'message':{'content':json.dumps(next(outputs))},'done':True}
            try:
                with patch.object(studio['ollama'],'tags',return_value=[]),patch.object(studio['ollama'],'chat',side_effect=model),sync_playwright() as pw:
                    try:browser=pw.chromium.launch(headless=True)
                    except Exception:browser=pw.chromium.launch(headless=True,channel='msedge')
                    try:
                        page=browser.new_page(viewport={'width':1600,'height':1000})
                        page.route('https://**/*',lambda route:route.abort())
                        page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='domcontentloaded')
                        page.locator('#new-project').click()
                        page.locator('#studio-dialog-input').fill('QA autoaprovação')
                        page.locator('#studio-dialog button[type=submit]').click()
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        pid=studio['store'].rows('SELECT id FROM projects')[0]['id']
                        original=studio['files'].read(pid,'app.py')['content']
                        self.assertFalse(page.locator('#auto-approve').is_checked())
                        page.locator('#chat-mode').select_option('change')
                        page.locator('#prompt').fill('Crie old.txt')
                        page.locator('#prompt').press('Enter')
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send' && document.querySelector('#proposal-count').textContent==='1'")
                        page.locator('#auto-approve').check()
                        self.assertFalse(studio['files'].path(pid,'old.txt').exists())
                        page.locator('#prompt').fill('Crie automatic.txt')
                        page.locator('#prompt').press('Enter')
                        page.locator('.message').filter(has_text='salvo(s) automaticamente').wait_for()
                        self.assertEqual(studio['files'].read(pid,'automatic.txt')['content'],'saved automatically')
                        self.assertEqual(studio['store'].one("SELECT status FROM proposals WHERE path='old.txt'")['status'],'pending')
                        event=studio['store'].one("SELECT data FROM events WHERE type='file' ORDER BY id DESC")
                        self.assertTrue(json.loads(event['data'])['automatic'])
                        page.locator('#fallback-editor').fill(original+'\n# unsaved user edit\n')
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        page.locator('#prompt').fill('Altere app.py')
                        page.locator('#prompt').press('Enter')
                        page.locator('.message').filter(has_text='Autoaprovação pausada').wait_for()
                        self.assertEqual(studio['files'].read(pid,'app.py')['content'],original)
                        self.assertIn('unsaved user edit',page.locator('#fallback-editor').input_value())
                        self.assertEqual(studio['store'].one("SELECT status FROM proposals WHERE path='app.py'")['status'],'pending')
                        page.locator('#fallback-editor').fill(original)
                        page.wait_for_function("document.querySelector('#send').dataset.mode==='send'")
                        page.locator('#prompt').fill('Altere app.py novamente')
                        page.locator('#prompt').press('Enter')
                        page.locator('.message').filter(has_text='O arquivo mudou desde a proposta').wait_for()
                        self.assertIn('outside change',studio['files'].read(pid,'app.py')['content'])
                        page.locator('#auto-approve').uncheck()
                        self.assertFalse(page.locator('#auto-approve').is_checked())
                    finally:browser.close()
            finally:
                for worker in list(studio['jobs'].threads.values()):worker.join(timeout=5)
                server.shutdown();server.server_close();thread.join(timeout=5)
