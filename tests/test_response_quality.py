import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from core.context_manager import (context, project_sources, build_messages, estimate_tokens,
                                  message_tokens, input_budget, validate_query_reply)
from core.response_policy import credential_answer, intent
from services.ollama_service import Ollama


REGISTRATION = '''from flask import request
@app.route("/cadastro", methods=["GET", "POST"])
def register():
    username = request.form.get("username")
    password = request.form.get("password")
    db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
               (username, generate_password_hash(password)))

def login():
    return check_password_hash(user["password_hash"], password)
'''


class ResponseQualityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.app = create_app(root / 'data', root / 'workspace', testing=True)
        self.client = self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as session:
            self.headers = {'X-Studio-Token': session['csrf']}
        self.s = self.app.extensions['studio']
        self.pid = self.post('/api/projects', {'name':'Qualidade'}).json['id']

    def tearDown(self):
        for thread in list(self.s['jobs'].threads.values()):
            thread.join(timeout=5)
        self.tmp.cleanup()

    def post(self, url, body):
        return self.client.post(url, json=body, headers=self.headers)

    def write(self, name, content):
        files = self.s['files']
        expected = files.read(self.pid, name)['hash'] if files.path(self.pid, name).exists() else None
        files.write(self.pid, name, content, expected)

    def chat(self, prompt, **options):
        response = self.post(f'/api/projects/{self.pid}/chat', {'prompt':prompt, **options})
        self.assertEqual(response.status_code, 200, response.json)
        jid = response.json['job']
        for _ in range(250):
            job = self.s['store'].one('SELECT * FROM jobs WHERE id=?', (jid,))
            if job['status'] not in ('queued', 'running') and jid not in self.s['jobs'].threads:
                return job
            time.sleep(.02)
        self.fail('Chat timed out')

    def test_credentials_use_real_source_beyond_old_prefix_without_model(self):
        self.write('app.py', '# unrelated\n' * 800 + REGISTRATION)
        self.write('tests/test_auth.py', 'LOGIN = "fake-admin"\nPASSWORD = "fake-password"')
        self.s['store'].set('memory:' + self.pid, 'Login inventado: admin senha 123456')
        with patch.object(self.s['ollama'], 'chat') as model, patch.object(self.s['ollama'], 'tags') as tags:
            job = self.chat('Me explique qual o login e a senha?', orchestrate=True)
        model.assert_not_called()
        tags.assert_not_called()
        self.assertEqual(job['status'], 'completed', job['result'])
        answer = json.loads(job['result'])['message']
        self.assertIn('`/cadastro`', answer)
        self.assertIn('app.py:802', answer)
        self.assertIn('hash', answer)
        for value in ('fake-admin', 'fake-password', '123456'):
            self.assertNotIn(value, answer)
        self.assertIn('não comprovam', answer)
        self.assertEqual(len(self.s['store'].rows('SELECT * FROM tasks WHERE job=?', (job['id'],))), 1)
        self.assertFalse(self.s['store'].rows('SELECT * FROM proposals WHERE project=?', (self.pid,)))
        self.assertEqual(self.s['store'].setting('memory_v2:' + self.pid, []), [])

    def test_unknown_credentials_do_not_claim_absence_of_accounts(self):
        with patch.object(self.s['ollama'], 'chat') as model:
            job = self.chat('qual login e senha?')
        model.assert_not_called()
        answer = json.loads(job['result'])['message']
        self.assertIn('Não consigo confirmar', answer)
        self.assertNotIn('Não há', answer)
        self.assertNotIn('/cadastro', answer)

    def test_test_fixtures_and_pending_proposals_are_not_registration_evidence(self):
        self.write('tests/test_auth.py', REGISTRATION)
        pending = {'auth.py':REGISTRATION}
        sources, _, _ = project_sources(self.s['files'], self.pid, 'senha', pending)
        answer = credential_answer(sources)
        self.assertNotIn('`/cadastro`', answer)
        self.assertIn('não comprovam', answer)
        ctx = context(self.s['store'], self.s['files'], self.pid, 'senha', pending)
        self.assertIn('[proposta não aplicada]', ctx)
        self.assertIn('[exemplo/teste]', ctx)

    def test_content_search_finds_late_evidence_and_ignores_legacy_memory(self):
        for i in range(12):
            self.write(f'login_{i}.txt', 'Sem informação relevante.')
        self.write('implementation.py', '# padding\n' * 800 + 'AUTH_POLICY = "login usa cadastro e hash"\n')
        self.s['store'].set('memory:' + self.pid, 'ALUCINACAO_ANTIGA')
        ctx = context(self.s['store'], self.s['files'], self.pid, 'qual senha?', budget=1000)
        self.assertIn('implementation.py:801', ctx)
        self.assertIn('AUTH_POLICY', ctx)
        self.assertNotIn('ALUCINACAO_ANTIGA', ctx)
        self.assertLessEqual(estimate_tokens(ctx), 1000)

    def test_minified_file_keeps_exact_named_selector_beyond_line_prefix(self):
        target='<div class="topbar-right">Visible target</div>'
        self.write('templates/dashboard.html','<div>'+('unrelated '*500)+target+'</div>')
        ctx=context(self.s['store'],self.s['files'],self.pid,
                    'Corrija topbar-right em templates/dashboard.html',budget=600)
        self.assertIn(target,ctx)
        self.assertIn('templates/dashboard.html:1',ctx)

    def test_query_never_creates_or_streams_file_proposals(self):
        reply = 'O arquivo contém uma rota (app.py:4).\n```file:evil.py\nprint("change")\n```'
        with patch.object(self.s['ollama'], 'tags', return_value=[]), patch.object(
                self.s['ollama'], 'chat', return_value=iter([{'message':{'content':reply}, 'done':True}])) as model:
            job = self.chat('Qual rota existe?', orchestrate=True)
        self.assertEqual(job['status'], 'completed', job['result'])
        self.assertEqual(model.call_count, 1)
        self.assertEqual(model.call_args.kwargs['mode'], 'query')
        self.assertEqual(json.loads(job['result'])['message'], 'O arquivo contém uma rota (app.py:4).')
        self.assertFalse(self.s['store'].rows('SELECT * FROM proposals WHERE project=?', (self.pid,)))
        events = self.s['store'].rows("SELECT data FROM events WHERE job=? AND type='token'", (job['id'],))
        self.assertNotIn('evil.py', str(events))
        messages = model.call_args.args[1]
        self.assertEqual(sum('Qual rota existe?' in m['content'] for m in messages), 1)

    def test_query_rejects_missing_or_fabricated_references(self):
        ctx = '[aplicado] app.py\napp.py:4 | @app.get("/")\n'
        for reply in ('A senha é admin.', 'A rota é / (app.py:999).',
                      'A rota é / (app.py:4), usuário admin (missing.py:1).'):
            with self.subTest(reply=reply):
                checked = validate_query_reply(reply, ctx)
                self.assertIn('Não consegui fundamentar', checked)
                self.assertNotIn('admin', checked)
        self.assertEqual(validate_query_reply('A rota é / (app.py:4).', ctx), 'A rota é / (app.py:4).')
        structured = json.dumps({'answer':'A rota é /.', 'sources':['app.py:4']})
        self.assertEqual(validate_query_reply(structured, ctx), 'A rota é /.\nFontes: app.py:4')
        for sources in ([], ['app.py:999'], [123], 'app.py:4'):
            checked = validate_query_reply(json.dumps({'answer':'Resposta', 'sources':sources}), ctx)
            self.assertIn('Não consegui fundamentar', checked)

    def test_change_without_files_is_reported_as_failure(self):
        with patch.object(self.s['ollama'],'tags',return_value=[]),patch.object(self.s['ollama'],'chat',return_value=iter([
                {'message':{'content':'Tudo pronto, fiz a alteração.'},'done':True}])):
            job=self.chat('Crie um arquivo hello.py')
        self.assertEqual(job['status'],'error')
        self.assertIn('não entregou arquivos',job['result'])

    def test_memory_contains_request_and_proposal_paths_not_ai_claims(self):
        reply = 'A senha ativa é INVENTED_CREDENTIAL.\n```file:new.py\nx = 1\n```'
        with patch.object(self.s['ollama'], 'tags', return_value=[]), patch.object(
                self.s['ollama'], 'chat', return_value=iter([{'message':{'content':reply}, 'done':True}])):
            job = self.chat('Crie new.py')
        self.assertEqual(job['status'], 'completed', job['result'])
        memory = self.s['store'].setting('memory_v2:' + self.pid)
        self.assertEqual(memory, [{'request':'Crie new.py', 'proposed_files':['new.py']}])
        self.assertNotIn('INVENTED_CREDENTIAL', str(memory))

    def test_truncated_generation_never_proposes_partial_files(self):
        chunk = {'message':{'content':'```file:partial.py\nx = 1\n```'}, 'done':True, 'done_reason':'length'}
        with patch.object(self.s['ollama'], 'tags', return_value=[]), patch.object(
                self.s['ollama'], 'chat', return_value=iter([chunk])):
            job = self.chat('Crie partial.py')
        self.assertEqual(job['status'], 'error')
        self.assertIn('limite de geração', job['result'])
        self.assertFalse(self.s['store'].rows('SELECT * FROM proposals WHERE project=?', (self.pid,)))

    def test_intent_distinguishes_questions_from_requests_and_supports_override(self):
        for prompt in ('qual login e senha?', 'Como criar uma conta?', 'Como alterar minha senha?',
                       'Explique o backend', 'Me diga o login, não crie nada', 'Explique sem alterar arquivos'):
            with self.subTest(prompt=prompt):
                self.assertEqual(intent(prompt), 'query')
        for prompt in ('Pode criar uma tela de login?', 'Crie login', 'Planeje', 'Quero alterar o backend',
                       'Faça uma tela', 'Crie o backend sem alterar o frontend'):
            with self.subTest(prompt=prompt):
                self.assertEqual(intent(prompt), 'change')
        self.assertEqual(intent('Crie login', 'query'), 'query')
        self.assertEqual(intent('Revise o backend', 'change'), 'change')
        response = self.post(f'/api/projects/{self.pid}/chat', {'prompt':'teste', 'mode':'invalid'})
        self.assertEqual(response.status_code, 400)

    def test_messages_fit_estimated_budget_and_preserve_current_question(self):
        messages = build_messages('Instruções.', 'PERGUNTA_ATUAL', 'Fonte: ' + 'x' * 50000,
                                  [{'role':'assistant', 'content':'HISTORICO_ANTIGO' * 5000}],
                                  previous='RESPOSTA_ANTERIOR' * 5000, mode='query')
        self.assertLessEqual(message_tokens(messages), input_budget('query'))
        self.assertIn('PERGUNTA_ATUAL', messages[-1]['content'])
        self.assertIn('Fonte:', messages[-1]['content'])
        self.assertNotIn('HISTORICO_ANTIGO', str(messages))
        with self.assertRaisesRegex(ValueError, 'orçamento'):
            build_messages('system', 'x' * 50000, '')

    def test_ollama_factual_options_and_input_guard(self):
        service = Ollama()
        response = io.BytesIO(b'{"done":true}\n')
        with patch.object(service, 'open', return_value=response) as request:
            list(service.chat('qwen2.5-coder:3b', [{'role':'user', 'content':'Qual rota?\napp.py:4 | @app.get("/")'}],
                              threading.Event(), mode='query'))
        options = request.call_args.args[1]['options']
        self.assertEqual(options['temperature'], 0)
        self.assertEqual(options['num_ctx'], 4096)
        self.assertEqual(options['num_predict'], 768)
        schema = request.call_args.args[1]['format']
        self.assertEqual(schema['properties']['sources']['items']['enum'], ['app.py:4'])
        with patch.object(service, 'open') as request:
            with self.assertRaisesRegex(ValueError, 'orçamento'):
                service.chat('qwen2.5-coder:3b', [{'role':'user', 'content':'x' * 50000}], threading.Event())
            request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
