"""QA real opcional: requer Playwright e Chromium ou Edge instalado."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
from werkzeug.serving import make_server
from app import create_app
import config

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright=None


@unittest.skipIf(sync_playwright is None,'Playwright não instalado')
class BrowserRealTest(unittest.TestCase):
    def test_ui_create_edit_run_preview_and_browser_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(Path(tmp)/'data',Path(tmp)/'workspace',testing=True)
            server=make_server('127.0.0.1',0,app,threaded=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            studio=app.extensions['studio']
            artifacts=config.DATA/'qa'
            artifacts.mkdir(parents=True,exist_ok=True)
            try:
                with sync_playwright() as pw:
                    try:
                        browser=pw.chromium.launch(headless=True)
                    except Exception:
                        browser=pw.chromium.launch(headless=True,channel='msedge')
                    try:
                        page=browser.new_page(viewport={'width':1600,'height':1000})
                        errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('dialog',lambda d:d.accept('QA Flask' if d.type=='prompt' else None))
                        page.goto(f'http://127.0.0.1:{server.server_port}',wait_until='networkidle')
                        page.locator('#new-project').click()
                        page.wait_for_function("document.querySelector('#file-label').textContent==='app.py'")
                        self.assertEqual(len(studio['store'].rows('SELECT * FROM projects')),1)
                        pid=studio['store'].rows('SELECT * FROM projects')[0]['id']
                        page.locator('#chat-mode').select_option('query')
                        self.assertEqual(page.locator('#chat-mode option:checked').inner_text(),'Só perguntar')
                        self.assertEqual(page.locator('#chat-mode option[value="change"]').inner_text(),'Pedir alteração')
                        page.locator('#orchestrate').check()
                        page.locator('#prompt').fill('Qual login e senha?')
                        page.locator('#send').click()
                        page.get_by_text('Não consigo confirmar um login e uma senha ativos', exact=False).wait_for()
                        page.wait_for_function("!document.querySelector('#send').disabled")
                        chat_job=studio['store'].rows("SELECT * FROM jobs WHERE kind='chat'")[0]
                        self.assertEqual(chat_job['status'],'completed')
                        self.assertEqual(len(studio['store'].rows('SELECT * FROM tasks WHERE job=?',(chat_job['id'],))),1)
                        self.assertEqual(studio['store'].rows('SELECT * FROM proposals'),[])
                        page.locator('#chat-mode').select_option('auto')
                        page.locator('#orchestrate').uncheck()
                        # Aguarda Monaco ou mantém o fallback offline para o mesmo fluxo.
                        page.wait_for_timeout(2500)
                        value=studio['files'].read(pid,'app.py')['content']+'\n# Editado no QA de navegador\n'
                        page.evaluate('(value)=>{if(typeof monaco!=="undefined"&&monaco.editor.getEditors().length)monaco.editor.getEditors()[0].setValue(value);else{const e=document.querySelector("#fallback-editor");e.value=value;e.dispatchEvent(new Event("input"));}}',value)
                        page.locator('#save-file').click()
                        page.wait_for_function("document.querySelector('#toast').textContent==='Arquivo salvo.'")
                        self.assertIn('Editado no QA',studio['files'].read(pid,'app.py')['content'])
                        page.screenshot(path=str(artifacts/'editor.png'),full_page=True)
                        page.locator('#run-project').click()
                        page.wait_for_function("document.querySelector('#process-status').textContent.includes('Em execução')",timeout=20000)
                        self.assertTrue(studio['execution'].status(pid)['ready'])
                        page.frame_locator('#preview').get_by_role('heading',name='Seu projeto está no ar.').wait_for()
                        page.screenshot(path=str(artifacts/'preview.png'),full_page=True)
                        page.locator('#browser-check').click()
                        page.locator('#screenshot').wait_for(state='visible',timeout=30000)
                        jobs=studio['store'].rows("SELECT * FROM jobs WHERE kind='browser'")
                        for job in jobs:
                            worker=studio['jobs'].threads.get(job['id'])
                            if worker:worker.join(timeout=10)
                        self.assertTrue(jobs)
                        self.assertEqual(studio['store'].one('SELECT status FROM jobs WHERE id=?',(jobs[0]['id'],))['status'],'completed')
                        page.locator('#models-shortcut').click()
                        page.locator('#view-models.active').wait_for()
                        page.screenshot(path=str(artifacts/'models.png'),full_page=True)
                        page.locator('[data-view="agents"]').click()
                        self.assertEqual(page.locator('.agent-card').count(),8)
                        page.screenshot(path=str(artifacts/'agents.png'),full_page=True)
                        page.locator('[data-view="logistics"]').click()
                        page.locator('#view-logistics.active').wait_for()
                        self.assertIn('Bases, indicadores',page.locator('#view-logistics').inner_text())
                        page.locator('#logistics-synthetic').click()
                        page.locator('.mapping-select[data-role="order_id"]').wait_for(timeout=15000)
                        self.assertEqual(page.locator('.base-row').count(),1)
                        page.locator('#logistics-rules').check()
                        page.locator('#logistics-create').click()
                        page.wait_for_function("document.querySelector('#proposal-count').textContent==='7'",timeout=20000)
                        self.assertIn('Dashboard proposto',page.locator('#logistics-progress').inner_text())
                        page.screenshot(path=str(artifacts/'logistics.png'),full_page=True)
                        self.assertEqual(errors,[],errors)
                        (artifacts/'browser-report.txt').write_text('PASS: criação, consulta de credenciais sem propostas/equipe, Monaco/fallback, salvar, executar Flask, preview, Playwright real, modelos, oito agentes e módulo logístico.\nErros JavaScript: 0\n',encoding='utf-8')
                    finally:
                        browser.close()
            finally:
                for pid in list(studio['execution'].processes):studio['execution'].stop(pid)
                for worker in list(studio['jobs'].threads.values()):worker.join(timeout=10)
                server.shutdown();server.server_close();thread.join(timeout=5)


if __name__=='__main__':unittest.main()
