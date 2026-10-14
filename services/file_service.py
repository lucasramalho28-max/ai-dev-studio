import hashlib
import os
import re
import tempfile
import threading
from pathlib import Path, PureWindowsPath


class FileService:
    def __init__(self, workspace):
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def root(self, project):
        if not re.fullmatch(r'[a-f0-9]{32}', project):
            raise ValueError('Projeto inválido')
        path = self.workspace / project
        if path.is_symlink() or (path.exists() and path.resolve() != path):
            raise ValueError('Diretório redirecionado')
        return path

    def path(self, project, name):
        if not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name:
            raise ValueError('Caminho inválido')
        relative = Path(name)
        if relative.is_absolute() or PureWindowsPath(name).is_absolute():
            raise ValueError('Caminho absoluto bloqueado')
        for part in relative.parts:
            if part in ('.', '..') or part.startswith('.') or part.endswith((' ', '.')):
                raise ValueError('Caminho protegido')
            if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}:
                raise ValueError('Nome reservado do Windows')
        root = self.root(project)
        target = root / relative
        for ancestor in [target, *target.parents]:
            if ancestor == root.parent:
                break
            if ancestor.is_symlink() or (ancestor.exists() and ancestor.resolve() != ancestor):
                raise ValueError('Links e junctions bloqueados')
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError('Path traversal bloqueado')
        return target

    def list(self, project):
        root = self.root(project)
        result = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('__pycache__','node_modules') and not (Path(directory)/d).is_symlink() and (Path(directory)/d).resolve() == Path(directory)/d]
            for name in files:
                if name.startswith('.'):
                    continue
                rel = (Path(directory)/name).relative_to(root).as_posix()
                try:
                    p = self.path(project, rel)
                    result.append({'path': rel, 'size': p.stat().st_size})
                except ValueError:
                    pass
                if len(result) >= 1000:
                    return result
        return sorted(result, key=lambda f: f['path'])

    def read(self, project, name):
        p = self.path(project, name)
        if p.stat().st_size > 1024*1024:
            raise ValueError('Limite do editor: 1 MB por arquivo')
        content = p.read_text(encoding='utf-8')
        return {'path': name, 'content': content, 'hash': self.digest(content)}

    @staticmethod
    def digest(content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def write(self, project, name, content, expected):
        if not isinstance(content, str) or len(content.encode('utf-8')) > 1024*1024:
            raise ValueError('Conteúdo inválido ou maior que 1 MB')
        with self.lock:
            p = self.path(project, name)
            current = self.read(project, name)['hash'] if p.exists() else None
            if current != expected:
                raise FileExistsError('Arquivo alterado: recarregue ou compare antes de salvar')
            p.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=p.parent, suffix='.tmp')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
                    f.write(content)
                os.replace(tmp, p)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            return self.read(project, name)
