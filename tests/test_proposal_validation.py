import tempfile
import json
import unittest
from pathlib import Path
from core.proposal_validation import extract_files, resolve_edits, validate_proposals
from services.file_service import FileService


class ProposalValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.files = FileService(Path(self.tmp.name))
        self.pid = 'a'*32
        self.files.root(self.pid).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_indented_model_blocks_are_dedented(self):
        files = extract_files('  ```file:app.py\n  x = 1\n  if x:\n      print(x)\n  ```')
        self.assertEqual(files['app.py'], 'x = 1\nif x:\n    print(x)\n')
        validate_proposals(files, self.files, self.pid)

    def test_invalid_python_is_blocked_without_executing_it(self):
        for code in ('assert b"Usuário"', 'def broken(:\n pass'):
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, 'Python inválido'):
                validate_proposals({'app.py':code}, self.files, self.pid)

    def test_missing_dependency_and_removed_flask_api_are_blocked(self):
        with self.assertRaisesRegex(ValueError, 'dependência indisponível'):
            validate_proposals({'app.py':'import nonexistent_studio_test_package'}, self.files, self.pid)
        with self.assertRaisesRegex(ValueError, 'before_first_request'):
            validate_proposals({'app.py':'@app.before_first_request\ndef init():\n pass'}, self.files, self.pid)

    def test_plaintext_auth_and_fixed_session_key_are_blocked(self):
        for code in ('valid = user.password == password', "valid = user['password_hash'] == password",
                     "app.config['SECRET_KEY'] = 'demo-password'", "import hashlib\nh = hashlib.sha256(password.encode()).hexdigest()"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate_proposals({'app.py':code}, self.files, self.pid)
        validate_proposals({'app.py':"from werkzeug.security import check_password_hash\nvalid = check_password_hash(user['password_hash'], password)\nif password != confirmation:\n pass"}, self.files, self.pid)

    def test_templates_must_be_present_and_local_imports_are_allowed(self):
        code = "from models import User\nresult = render_template('login.html')"
        staged = {'app.py':code, 'models.py':'class User: pass'}
        with self.assertRaisesRegex(ValueError, 'template ausente'):
            validate_proposals(staged, self.files, self.pid)
        staged['templates/login.html'] = '<h1>Entrar</h1>'
        validate_proposals(staged, self.files, self.pid)

    def test_exact_edits_preserve_unrelated_content_and_reject_ambiguous_matches(self):
        self.files.write(self.pid,'page.html','<header>Old</header>\n<main>Keep</main>',None)
        reply='```edit:page.html\n{"old":"<header>Old</header>","new":"<header>New</header>"}\n```'
        result=resolve_edits(reply,self.files,self.pid)
        self.assertEqual(result['page.html'],'<header>New</header>\n<main>Keep</main>')
        self.assertIn('Old',self.files.read(self.pid,'page.html')['content'])
        with self.assertRaisesRegex(ValueError,'exatamente uma vez'):
            resolve_edits(reply,self.files,self.pid,{'page.html':'<header>Old</header>'*2})
        with self.assertRaisesRegex(ValueError,'exatamente uma vez'):
            resolve_edits(reply,self.files,self.pid,{'page.html':'Not present'})

    def test_invalid_template_is_blocked(self):
        with self.assertRaisesRegex(ValueError,'Jinja inválido'):
            validate_proposals({'templates/index.html':'{% if user %}'},self.files,self.pid)

    def test_structured_edits_and_invalid_markdown_are_handled(self):
        self.files.write(self.pid,'test.txt','Original content',None)
        reply=json.dumps({'summary':'Edit','files':[],'edits':[{'path':'test.txt','old':'Original','new':'Updated'}]})
        self.assertEqual(extract_files(reply),{})
        self.assertEqual(resolve_edits(reply,self.files,self.pid)['test.txt'],'Updated content')
        with self.assertRaisesRegex(ValueError,'formato de edição'):
            resolve_edits('edit:test.txt\n```json\n{}\n```',self.files,self.pid)


if __name__ == '__main__':
    unittest.main()
