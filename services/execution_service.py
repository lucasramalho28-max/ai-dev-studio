import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from services.ollama_installer import HIDDEN


class Execution:
    def __init__(self, files):
        self.files = files
        self.processes = {}
        self.lock = threading.RLock()

    def python(self, project):
        root = self.files.root(project)
        local = root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        return str(local) if local.exists() else sys.executable

    def status(self, project):
        state = self.processes.get(project)
        if not state:
            return {'running':False,'logs':[]}
        return {'running':state['process'].poll() is None, 'port':state['port'],
                'url':f"http://127.0.0.1:{state['port']}", 'ready':state.get('ready',False),
                'exit_code':state['process'].poll(), 'logs':list(state['logs'])[-400:]}

    def start(self, project):
        with self.lock:
            if self.status(project)['running']:
                return self.status(project)
            root = self.files.root(project)
            self.files.path(project,'app.py').stat()
            with socket.socket() as sock:
                sock.bind(('0.0.0.0',0))
                port = sock.getsockname()[1]
            env = {k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('KEY','TOKEN','SECRET','PASSWORD'))}
            env.update(PYTHONUNBUFFERED='1', FLASK_DEBUG='0')
            proc = subprocess.Popen([self.python(project),'-m','flask','--app','app:app','run','--host','0.0.0.0','--port',str(port),'--no-reload','--no-debugger'],
                                    cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8',errors='replace',creationflags=HIDDEN)
            state = {'process':proc,'port':port,'logs':[],'ready':False}
            self.processes[project] = state

            def read():
                for line in proc.stdout:
                    state['logs'].append(line.rstrip())
                    if len(state['logs']) > 500:
                        del state['logs'][:100]
            threading.Thread(target=read,daemon=True).start()

            def readiness():
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                for _ in range(40):
                    if proc.poll() is not None:
                        return
                    try:
                        with opener.open(f'http://127.0.0.1:{port}',timeout=.5) as response:
                            state['ready'] = response.status < 500
                            return
                    except Exception:
                        time.sleep(.25)
            threading.Thread(target=readiness,daemon=True).start()
            return self.status(project)

    def stop(self, project):
        with self.lock:
            state = self.processes.get(project)
            if state and state['process'].poll() is None:
                proc = state['process']
                if os.name == 'nt':
                    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,creationflags=HIDDEN,timeout=15)
                else:
                    proc.terminate()
                proc.wait(timeout=15)
            return self.status(project)

    def venv(self, project, emit, cancel):
        root = self.files.root(project)
        # Não instala dependências declaradas por código de IA sem revisão humana.
        steps = [[sys.executable,'-m','venv',str(root/'.venv')]]
        for command in steps:
            proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                    encoding='utf-8',errors='replace',creationflags=HIDDEN)
            for line in proc.stdout:
                emit('log',{'text':line.rstrip()})
            if proc.wait() != 0:
                raise RuntimeError('Não foi possível criar o ambiente virtual')
        command = [self.python(project),'-m','pip','install','Flask>=3.1,<4']
        proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                encoding='utf-8',errors='replace',creationflags=HIDDEN)
        for line in proc.stdout:
            emit('log',{'text':line.rstrip()})
        if proc.wait() != 0:
            raise RuntimeError('Falha ao instalar Flask no ambiente do projeto')
        return {'python':self.python(project)}

    def tests(self, project):
        root = self.files.root(project)
        result = subprocess.run([self.python(project),'-m','unittest','discover','-s','tests','-v'],
                                cwd=root,capture_output=True,text=True,encoding='utf-8',errors='replace',
                                timeout=90,creationflags=HIDDEN,
                                env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('KEY','TOKEN','SECRET','PASSWORD'))})
        return {'exit_code':result.returncode,'output':(result.stdout+result.stderr)[-30000:]}
