"""Static checks for generated files. Never imports or executes project code."""
import ast
import importlib.util
import json
import re
import sys
import textwrap
from pathlib import PurePosixPath


def extract_files(reply):
    try:
        document = json.loads(reply)
    except ValueError:
        document = None
    if isinstance(document,dict) and 'files' in document:
        result = {}
        for item in document['files']:
            if not isinstance(item,dict) or not isinstance(item.get('path'),str) or not isinstance(item.get('content'),str):
                raise ValueError('Arquivo gerado inválido: informe path e content em texto.')
            if item['path'] in result:
                raise ValueError('O modelo repetiu o mesmo caminho na resposta: '+item['path'])
            result[item['path']] = item['content']
        return result
    return {name.strip():textwrap.dedent(content) for name, content in
            re.findall(r'```file:([^\n\r]+)\r?\n(.*?)```', reply, re.S)}


def resolve_edits(reply, files, project, staged=None):
    result = dict(staged or {})
    changed = {}
    edits=[]
    try:
        document=json.loads(reply)
    except ValueError:
        document=None
    if isinstance(document,dict) and 'edits' in document:
        for edit in document['edits']:
            if not isinstance(edit,dict) or not isinstance(edit.get('path'),str):
                raise ValueError('Edição gerada inválida: caminho ausente.')
            edits.append((edit['path'],json.dumps({'old':edit.get('old'),'new':edit.get('new')})))
    else:
        edits=re.findall(r'```edit:([^\n\r]+)\r?\n(.*?)```',reply,re.S)
        if 'edit:' in reply and not edits:
            raise ValueError('O modelo não usou o formato de edição esperado; nenhuma alteração foi proposta.')
    for name, body in edits:
        name = name.strip()
        files.path(project,name)
        try:
            edit = json.loads(body)
        except ValueError as exc:
            raise ValueError(f'Edição inválida em {name}: use JSON com old e new.') from exc
        if (not isinstance(edit,dict) or set(edit)!={'old','new'}
                or not isinstance(edit['old'],str) or not edit['old'] or not isinstance(edit['new'],str)):
            raise ValueError(f'Edição inválida em {name}: old precisa ser um trecho não vazio e new precisa ser texto.')
        if edit['old']==edit['new']:
            raise ValueError(f'Edição sem efeito em {name}: old e new são idênticos.')
        original = result[name] if name in result else files.read(project,name)['content']
        if original.count(edit['old'])!=1:
            raise ValueError(f'Edição bloqueada em {name}: o trecho original deve ocorrer exatamente uma vez; consulte o arquivo atualizado.')
        result[name] = original.replace(edit['old'],edit['new'],1)
        changed[name] = result[name]
    return changed


def password_operand(node):
    if isinstance(node, ast.Attribute):
        return 'password' in node.attr.lower() or 'senha' in node.attr.lower()
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
        return str(node.slice.value).lower() in ('password','password_hash','senha','senha_hash')
    if isinstance(node, ast.Name):
        return node.id.lower() in ('password','senha','stored_password','hashed_password','password_hash')
    return False


def validate_proposals(staged, files, project, references=True):
    existing = {entry['path'] for entry in files.list(project)}
    paths = existing | set(staged)
    local_modules = {PurePosixPath(path).stem for path in paths if path.endswith('.py') and '/' not in path}
    local_modules |= {path.split('/')[0] for path in paths if path.endswith('/__init__.py')}
    errors = []
    for name, content in staged.items():
        files.path(project, name)
        if name.endswith('.html'):
            from jinja2 import Environment, TemplateSyntaxError
            try:
                Environment().parse(content)
            except TemplateSyntaxError as exc:
                errors.append(f'{name}:{exc.lineno}: template Jinja inválido: {exc.message}')
        if not name.endswith('.py'):
            continue
        try:
            tree = ast.parse(content, filename=name)
        except (SyntaxError, ValueError, RecursionError) as exc:
            errors.append(f'{name}:{getattr(exc,"lineno",1)}: Python inválido: {getattr(exc,"msg",str(exc))}')
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.ImportFrom) and node.level:
                    continue
                imports = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or '']
                for module in imports:
                    top = module.split('.')[0]
                    if not top or top in local_modules or top in sys.stdlib_module_names:
                        continue
                    try:
                        available = importlib.util.find_spec(top) is not None
                    except (ValueError, ImportError):
                        available = False
                    if not available:
                        errors.append(f'{name}:{node.lineno}: dependência indisponível: {top}. Use bibliotecas já instaladas ou proponha uma dependência para revisão.')
            if isinstance(node, ast.Attribute) and node.attr == 'before_first_request':
                errors.append(f'{name}:{node.lineno}: before_first_request foi removido do Flask; inicialize o banco ao criar a aplicação.')
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'hashlib'
                    and node.func.attr in ('sha256','sha1','md5')
                    and any(isinstance(child, ast.Name) and child.id.lower() in ('password','senha')
                            for argument in node.args for child in ast.walk(argument))):
                errors.append(f'{name}:{node.lineno}: hash rápido inadequado para senha; use generate_password_hash/check_password_hash.')
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                if sum(password_operand(item) for item in operands) >= 2:
                    errors.append(f'{name}:{node.lineno}: comparação direta de senha; use check_password_hash para autenticar.')
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                for target in node.targets:
                    key = (target.attr if isinstance(target, ast.Attribute) else
                           target.slice.value if isinstance(target, ast.Subscript) and isinstance(target.slice, ast.Constant) else
                           target.id if isinstance(target, ast.Name) else '')
                    if str(key).upper() in ('SECRET_KEY', 'SECRET'):
                        errors.append(f'{name}:{node.lineno}: chave de sessão fixa; use uma chave aleatória persistente ou configuração externa.')
            if references and isinstance(node, ast.Call) and getattr(node.func, 'id', '') == 'render_template' and node.args:
                template = node.args[0]
                if isinstance(template, ast.Constant) and isinstance(template.value, str):
                    path = 'templates/' + template.value
                    if path not in paths:
                        errors.append(f'{name}:{node.lineno}: template ausente: {path}. Inclua o arquivo na proposta.')
    if errors:
        raise ValueError('Propostas bloqueadas pela validação estática:\n' + '\n'.join(dict.fromkeys(errors)))
    return staged
