"""Audited local starters for common requests; always delivered as reviewable proposals."""
import ast
import re
from pathlib import Path
from core.response_policy import normalize

EMPTY_APP = '''from flask import Flask, render_template
app = Flask(__name__)

@app.get('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
'''


def stock_starter(files, project, prompt):
    text = normalize(prompt)
    if not ('estoque' in text and ('dashboard' in text or 'painel' in text)
            and ('login' in text or 'cadastro' in text) and 'fictici' in text):
        return None
    if 'sem modelo pronto' in text or 'sem base pronta' in text:
        return None
    existing = {entry['path'] for entry in files.list(project)}
    if not existing <= {'app.py','templates/index.html','requirements.txt','tests/test_app.py'}:
        return None
    if 'app.py' in existing and files.read(project,'app.py')['content'] != EMPTY_APP:
        return None
    root = Path(__file__).resolve().parents[1]/'starters'/'stock_portal'
    result = {}
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if (not path.is_file() or any(part in ('instance','__pycache__') or part.startswith('.') for part in relative.parts)
                or path.suffix not in ('.py','.html','.css','.js','.md','.txt','.json','.csv')):
            continue
        result[relative.as_posix()] = path.read_text(encoding='utf-8-sig')
    if not result:
        raise RuntimeError('Base local de estoque indisponível')
    match = re.search(r'usu[aá]rio\s+([\w.-]{3,40})\s+(?:e\s+)?senha\s+([^\s,;]+)', prompt, re.I)
    if match:
        username, password = match[1], match[2].rstrip('.!?')
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{3,40}',username) or not 8 <= len(password) <= 128:
            raise ValueError('A conta de demonstração precisa de usuário válido e senha entre 8 e 128 caracteres.')
        result['app.py'] = result['app.py'].replace("DEMO_USERNAME = 'demo'",'DEMO_USERNAME = '+repr(username)).replace("DEMO_PASSWORD = 'Estoque@123'",'DEMO_PASSWORD = '+repr(password))
        result['README.md'] = result['README.md'].replace('**demo**','**'+username+'**').replace('**Estoque@123**','**'+password+'**')
    # Fail if packaging accidentally ships invalid Python sources.
    for name, content in result.items():
        if name.endswith('.py'):
            ast.parse(content, filename=name)
    return result
