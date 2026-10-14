import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app
from core.response_policy import credential_answer, defined_demo_access
from core.proposal_validation import validate_proposals
from services.starter_service import stock_starter


class StockStarterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.app = create_app(root/'data',root/'workspace',testing=True)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers={'X-Studio-Token':session['csrf']}
        self.s = self.app.extensions['studio']
        self.pid = self.client.post('/api/projects',json={'name':'Demo'},headers=self.headers).json['id']
        self.prompt = 'Crie cadastro, login e dashboard para estoque fictício com usuário demo e senha Estoque@123.'

    def tearDown(self):
        for thread in list(self.s['jobs'].threads.values()):
            thread.join(timeout=5)
        for pid in list(self.s['execution'].processes):
            self.s['execution'].stop(pid)
        self.tmp.cleanup()

    def test_request_creates_reviewable_starter_without_free_generation(self):
        with patch.object(self.s['ollama'],'chat') as model:
            response=self.client.post(f'/api/projects/{self.pid}/chat',json={'prompt':self.prompt},headers=self.headers)
            jid=response.json['job']
            worker=self.s['jobs'].threads.get(jid)
            if worker:worker.join(timeout=10)
        model.assert_not_called()
        job=self.s['store'].one('SELECT * FROM jobs WHERE id=?',(jid,))
        self.assertEqual(job['status'],'completed',job['result'])
        self.assertEqual(json.loads(job['result'])['source'],'local_starter')
        proposals=self.s['store'].rows('SELECT * FROM proposals WHERE project=?',(self.pid,))
        paths={p['path'] for p in proposals}
        self.assertIn('data/estoque_ficticio.csv',paths)
        self.assertIn('templates/dashboard.html',paths)
        self.assertIn('tests/test_app.py',paths)
        self.assertFalse(self.s['files'].path(self.pid,'templates/dashboard.html').exists())
        app_proposal=next(p for p in proposals if p['path']=='app.py')
        applied=self.client.post('/api/proposals/'+app_proposal['id'],json={'confirm':True},headers=self.headers)
        self.assertEqual(applied.status_code,200,applied.json)

    def test_starter_preserves_existing_custom_work_and_respects_query(self):
        file=self.s['files'].read(self.pid,'app.py')
        self.s['files'].write(self.pid,'app.py','# existing custom app',file['hash'])
        self.assertIsNone(stock_starter(self.s['files'],self.pid,self.prompt))
        self.assertIsNone(stock_starter(self.s['files'],self.pid,'Crie apenas uma tela de login'))

    def test_demo_credentials_need_explicit_hashed_insert_evidence(self):
        staged=stock_starter(self.s['files'],self.pid,self.prompt.replace('demo e senha Estoque@123','operador e senha Teste@4567'))
        validate_proposals(staged,self.s['files'],self.pid)
        access=defined_demo_access(staged['app.py'])
        self.assertEqual((access['username'],access['password']),('operador','Teste@4567'))
        answer=credential_answer([{'path':'app.py','content':staged['app.py'],'kind':'aplicado'}])
        self.assertIn('`operador`',answer)
        self.assertIn('`Teste@4567`',answer)
        self.assertIn('não verificou',answer)
        constants="DEMO_USERNAME='fake'\nDEMO_PASSWORD='not-real'"
        self.assertIsNone(defined_demo_access(constants))
        answer=credential_answer([{'path':'tests/test_demo.py','content':staged['app.py'],'kind':'exemplo/teste'}])
        self.assertNotIn('Teste@4567',answer)

    def test_generated_portal_allows_logout_on_mobile_browser(self):
        try:
            import playwright.sync_api
        except ImportError:
            self.skipTest('Playwright não instalado')
        response=self.client.post(f'/api/projects/{self.pid}/chat',json={'prompt':self.prompt},headers=self.headers)
        worker=self.s['jobs'].threads.get(response.json['job'])
        if worker:worker.join(timeout=10)
        proposals=self.s['store'].rows('SELECT * FROM proposals WHERE project=?',(self.pid,))
        for p in proposals:
            applied=self.client.post('/api/proposals/'+p['id'],json={'confirm':True},headers=self.headers)
            self.assertEqual(applied.status_code,200,applied.json)
        self.s['execution'].start(self.pid)
        for _ in range(100):
            if self.s['execution'].status(self.pid).get('ready'):
                break
            time.sleep(.1)
        report=self.s['browser'].inspect(self.pid,[
            {'type':'fill','selector':'#username','value':'demo'},
            {'type':'fill','selector':'#password','value':'Estoque@123'},
            {'type':'click','selector':'button[type="submit"]'},
            {'type':'expect_text','selector':'.topbar','value':'Sair da conta'},
            {'type':'click','selector':'.topbar button[aria-label="Sair da conta"]'},
            {'type':'expect_text','selector':'body','value':'Vamos começar.'}],viewport={'width':390,'height':844})
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['http_errors'],[])
        self.assertLessEqual(report['layout']['documentWidth'],390)
        self.assertIn('Entrar',report['title'])


if __name__=='__main__':unittest.main()
