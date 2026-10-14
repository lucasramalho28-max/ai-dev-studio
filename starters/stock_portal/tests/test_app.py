import csv
import io
import re
import sqlite3
import tempfile
import unittest
from collections import defaultdict
from contextlib import closing
from pathlib import Path
from werkzeug.security import check_password_hash
from app import create_app, ROOT, DEMO_USERNAME, DEMO_PASSWORD


class StockPortalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name)/'test.sqlite3'
        self.app = create_app({'TESTING':True,'SECRET_KEY':'test-only-key','DATABASE':str(self.db_path)})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self, path='/login'):
        html = self.client.get(path).get_data(as_text=True)
        return re.search(r'name="csrf_token" value="([^"]+)"', html)[1]

    def login(self, password=None):
        return self.client.post('/login', data={'csrf_token':self.csrf(),'username':DEMO_USERNAME,'password':password or DEMO_PASSWORD})

    def test_pages_are_protected_and_demo_login_works(self):
        self.assertEqual(self.client.get('/dashboard').status_code,302)
        self.assertEqual(self.client.get('/api/resumo').status_code,401)
        self.assertEqual(self.client.get('/exportar.csv').status_code,302)
        self.assertIn('Usuário ou senha inválidos',self.login('wrong').get_data(as_text=True))
        self.assertEqual(self.login().status_code,302)
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code,200)
        self.assertIn('DADOS FICTÍCIOS',response.get_data(as_text=True))

    def test_signup_duplicate_and_password_hash(self):
        data = {'csrf_token':self.csrf('/cadastro'),'name':'Pessoa fictícia','username':'usuario.teste',
                'password':'Teste@12345','confirm_password':'Teste@12345'}
        self.assertEqual(self.client.post('/cadastro',data=data).status_code,302)
        with closing(sqlite3.connect(self.db_path)) as db:
            saved = db.execute('SELECT password_hash FROM users WHERE username=?',('usuario.teste',)).fetchone()[0]
        self.assertNotEqual(saved,'Teste@12345')
        self.assertTrue(check_password_hash(saved,'Teste@12345'))
        data['csrf_token'] = self.csrf('/cadastro')
        data['username'] = 'USUARIO.TESTE'
        self.assertIn('já está cadastrado',self.client.post('/cadastro',data=data).get_data(as_text=True))

    def test_csrf_validation_and_logout(self):
        self.assertEqual(self.client.post('/login',data={'username':DEMO_USERNAME,'password':DEMO_PASSWORD}).status_code,400)
        self.assertEqual(self.client.post('/cadastro',data={'username':'abc'}).status_code,400)
        self.login()
        self.assertEqual(self.client.post('/logout').status_code,400)
        self.assertEqual(self.client.post('/logout',data={'csrf_token':self.csrf('/dashboard')}).status_code,302)
        self.assertEqual(self.client.get('/api/resumo').status_code,401)

    def test_kpis_match_source_csv_and_filtered_warehouse(self):
        self.login()
        with (ROOT/'data/estoque_ficticio.csv').open(encoding='utf-8-sig') as stream:
            stocks = list(csv.DictReader(stream))
        with (ROOT/'data/produtos_ficticios.csv').open(encoding='utf-8-sig') as stream:
            costs = {r['sku']:int(r['custo_unitario_centavos']) for r in csv.DictReader(stream)}
        for cd in ('', '1'):
            rows = [r for r in stocks if not cd or r['cd_id']==cd]
            kpis = self.client.get('/api/resumo?cd='+cd).json['kpis']
            self.assertEqual(kpis['positions'],len(rows))
            self.assertEqual(kpis['units'],sum(int(r['quantidade']) for r in rows))
            self.assertEqual(kpis['value'],sum(int(r['quantidade'])*costs[r['sku']] for r in rows))
            self.assertEqual(kpis['critical'],sum(int(r['quantidade'])<=int(r['estoque_minimo']) for r in rows))
        self.assertEqual(len(stocks),216)

    def test_ledger_reconciles_every_stock_position(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            rows = db.execute('''SELECT s.id,s.quantity,s.opening_quantity+COALESCE(SUM(m.quantity),0)
                               FROM stocks s LEFT JOIN movements m ON m.stock_id=s.id GROUP BY s.id''').fetchall()
        self.assertEqual(len(rows),216)
        self.assertTrue(all(current==calculated for _,current,calculated in rows))
        self.assertTrue(all(current>=0 for _,current,_ in rows))

    def test_filters_empty_state_csv_and_pagination(self):
        self.login()
        self.assertEqual(self.client.get('/api/resumo?status=ruptura').json['kpis']['units'],0)
        self.assertEqual(self.client.get('/api/resumo?q=NONEXISTENT').json['kpis']['positions'],0)
        self.assertIn('Nenhum produto encontrado',self.client.get('/dashboard?q=NONEXISTENT').get_data(as_text=True))
        export = self.client.get('/exportar.csv?cd=1')
        rows = list(csv.DictReader(io.StringIO(export.get_data(as_text=True).lstrip('\ufeff')),delimiter=';'))
        self.assertEqual(len(rows),72)
        self.assertTrue(all(r['centro']=='CD Cuiabá' and r['dados_ficticios']=='sim' for r in rows))
        self.assertIn('Página 2 de',self.client.get('/dashboard?pagina=2').get_data(as_text=True))
        # Literal percent matches Álcool 70% in three centers, never every product.
        self.assertEqual(self.client.get('/api/resumo?q=%25').json['kpis']['positions'],3)


if __name__=='__main__':
    unittest.main()
