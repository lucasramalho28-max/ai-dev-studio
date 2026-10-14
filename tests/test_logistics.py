import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from openpyxl import Workbook

from app import create_app


class LogisticsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.app = create_app(self.root / 'data', self.root / 'workspace', testing=True)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers = {'X-Studio-Token': session['csrf']}
        self.studio = self.app.extensions['studio']
        self.pid = self.json('/api/projects', 'POST', {'name': 'Logística'}).json['id']

    def tearDown(self):
        for thread in list(self.studio['jobs'].threads.values()):
            thread.join(timeout=5)
        self.studio['logistics'].engine.dispose()
        self.tmp.cleanup()

    def json(self, path, method='GET', data=None):
        return self.client.open(path, method=method, json=data, headers=self.headers)

    def upload(self, content, name):
        response = self.client.post(
            f'/api/projects/{self.pid}/logistics/uploads',
            data={'file': (io.BytesIO(content), name)},
            headers=self.headers,
            content_type='multipart/form-data',
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.json

    def wait(self, job_id):
        for _ in range(300):
            job = self.studio['store'].one('SELECT * FROM jobs WHERE id=?', (job_id,))
            if job['status'] not in ('queued', 'running') and job_id not in self.studio['jobs'].threads:
                return job
            time.sleep(.02)
        self.fail('Job logístico excedeu o tempo de teste')

    def test_agent_profile_and_models(self):
        agents = self.json('/api/state').json['agents']
        logistics = next(agent for agent in agents if agent['id'] == 'logistics')
        self.assertEqual(logistics['preferred_model'], 'qwen3.5:4b')
        self.assertEqual(logistics['coding_model'], 'qwen2.5-coder:3b')

    def test_csv_analysis_detects_schema_quality_and_mapping(self):
        raw = ('pedido;filial;regional;semana;no_prazo;motivo_atraso\n'
               'P1;CD Norte;Norte;2026-S01;Sim;\n'
               'P2;CD Sul;Sul;2026-S01;Não;Transportadora\n'
               'P2;CD Sul;Sul;2026-S01;Não;Transportadora\n').encode('utf-8')
        upload = self.upload(raw, 'sla.csv')
        response = self.json(f'/api/projects/{self.pid}/logistics/analyze', 'POST', {'upload_id': upload['id']})
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        profile = response.json
        self.assertTrue(profile['sla_ready'])
        self.assertEqual(profile['mapping']['order_id'], 'pedido')
        self.assertEqual(profile['mapping']['branch'], 'filial')
        self.assertEqual(profile['duplicate_rows'], 1)
        self.assertGreater(profile['duplicate_order_records'], 0)
        self.assertTrue(profile['warnings'])

    def test_xlsx_and_json_are_read_locally(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['pedido', 'filial', 'no_prazo'])
        sheet.append(['X1', 'CD 1', 'Sim'])
        data = io.BytesIO()
        book.save(data)
        xlsx = self.upload(data.getvalue(), 'base.xlsx')
        analysis = self.json(f'/api/projects/{self.pid}/logistics/analyze', 'POST', {'upload_id': xlsx['id']}).json
        self.assertEqual(analysis['rows'], 1)
        raw = json.dumps([{'pedido': 'J1', 'filial': 'CD J', 'no_prazo': True}]).encode()
        json_upload = self.upload(raw, 'base.json')
        analysis = self.json(f'/api/projects/{self.pid}/logistics/analyze', 'POST', {'upload_id': json_upload['id']}).json
        self.assertEqual(analysis['mapping']['on_time'], 'no_prazo')

    def test_synthetic_sla_generates_reviewable_real_dashboard(self):
        denied = self.json(f'/api/projects/{self.pid}/logistics/synthetic', 'POST', {})
        self.assertEqual(denied.status_code, 403)
        upload = self.json(f'/api/projects/{self.pid}/logistics/synthetic', 'POST', {'confirm': True}).json
        profile = self.json(f'/api/projects/{self.pid}/logistics/analyze', 'POST', {'upload_id': upload['id']}).json
        original = self.studio['logistics'].upload(self.pid, upload['id'])
        payload = {
            'upload_id': upload['id'], 'objective': 'Acompanhar SLA semanal por CD',
            'mapping': profile['mapping'], 'duplicate_rule': 'reject',
            'rules_confirmed': True, 'confirm': True,
        }
        started = self.json(f'/api/projects/{self.pid}/logistics/dashboard', 'POST', payload)
        self.assertEqual(started.status_code, 200, started.get_data(as_text=True))
        job = self.wait(started.json['job'])
        self.assertEqual(job['status'], 'completed', job['result'])
        result = json.loads(job['result'])
        self.assertEqual(result['kpis']['total'], 800)
        self.assertEqual(len(result['proposal_ids']), 7)
        self.assertEqual(self.studio['logistics'].upload(self.pid, upload['id'])['sha256'], original['sha256'])
        proposals = self.json(f'/api/projects/{self.pid}/proposals').json
        self.assertEqual({item['path'] for item in proposals}, set(result['files']))
        for proposal in proposals:
            applied = self.json('/api/proposals/' + proposal['id'], 'POST', {'confirm': True})
            self.assertEqual(applied.status_code, 200, applied.get_data(as_text=True))
        dashboard = json.loads(self.studio['files'].read(self.pid, 'data/logistics_sla.json')['content'])
        self.assertEqual(dashboard['kpis']['total'], len(dashboard['records']))
        tests = self.studio['execution'].tests(self.pid)
        self.assertEqual(tests['exit_code'], 0, tests['output'])
        self.assertIn('test_health_and_totals', tests['output'])
        self.studio['execution'].start(self.pid)
        for _ in range(80):
            if self.studio['execution'].status(self.pid).get('ready'):
                break
            time.sleep(.1)
        report = self.studio['browser'].inspect(self.pid)
        self.assertEqual(report['status'], 200)
        self.assertEqual(report['errors'], [])
        self.assertIn('Painel de SLA de expedição', report['text'])
        self.assertIn('800', report['text'])
        self.studio['execution'].stop(self.pid)

    def test_rules_memory_and_projects_are_isolated(self):
        other = self.json('/api/projects', 'POST', {'name': 'Outro'}).json['id']
        memory = {'category': 'target', 'key': 'sla_minimo', 'value': '95%', 'confirm': True}
        self.assertEqual(self.json(f'/api/projects/{self.pid}/logistics/memory', 'POST', memory).status_code, 201)
        self.assertEqual(len(self.json(f'/api/projects/{self.pid}/logistics').json['memory']), 1)
        self.assertEqual(len(self.json(f'/api/projects/{other}/logistics').json['memory']), 0)
        upload = self.json(f'/api/projects/{self.pid}/logistics/synthetic', 'POST', {'confirm': True}).json
        self.assertEqual(self.json(f'/api/projects/{other}/logistics/analyze', 'POST', {'upload_id': upload['id']}).status_code, 400)
        profile = self.json(f'/api/projects/{self.pid}/logistics/analyze', 'POST', {'upload_id': upload['id']}).json
        payload = {'upload_id': upload['id'], 'mapping': profile['mapping'], 'duplicate_rule': 'reject', 'confirm': True}
        self.assertEqual(self.json(f'/api/projects/{self.pid}/logistics/dashboard', 'POST', payload).status_code, 200)
        job_id = self.json(f'/api/projects/{self.pid}/logistics/dashboard', 'POST', {**payload, 'rules_confirmed': False}).json['job']
        self.assertEqual(self.wait(job_id)['status'], 'error')


if __name__ == '__main__':
    unittest.main()
