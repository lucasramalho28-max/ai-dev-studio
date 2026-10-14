import os
import shutil
import subprocess
import time
from pathlib import Path

OFFICIAL_DOWNLOAD = 'https://ollama.com/download/windows'
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


class OllamaInstaller:
    def __init__(self, ollama):
        self.ollama = ollama
        self.owned = None

    def executable(self):
        found = shutil.which('ollama')
        if found:
            return found
        p = Path(os.environ.get('LOCALAPPDATA', ''))/'Programs'/'Ollama'/'ollama.exe'
        return str(p) if p.is_file() else None

    def status(self):
        path = self.executable()
        try:
            version = self.ollama.request('/api/version')
            running = True
        except RuntimeError:
            version, running = {}, False
        return {'installed':bool(path), 'executable':path, 'running':running,
                'version':version.get('version'), 'winget':bool(shutil.which('winget')),
                'windows':os.name=='nt', 'owned':bool(self.owned and self.owned.poll() is None),
                'download_url':OFFICIAL_DOWNLOAD}

    def install(self, emit, cancel):
        if os.name != 'nt':
            raise ValueError('Instalador disponível somente no Windows')
        winget = shutil.which('winget')
        if not winget:
            raise ValueError('winget indisponível. Baixe o instalador em '+OFFICIAL_DOWNLOAD)
        emit('log', {'text':'Instalando via winget oficial. O Windows pode solicitar permissão/UAC. Não feche essa janela.'})
        command = [winget, 'install', '--id','Ollama.Ollama','--exact','--source','winget',
                   '--accept-source-agreements','--accept-package-agreements','--disable-interactivity']
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              encoding='utf-8', errors='replace', creationflags=HIDDEN) as proc:
            for line in proc.stdout:
                emit('log', {'text':line.rstrip()})
            code = proc.wait()
        status = self.status()
        emit('installation', {'exit_code':code, **status})
        if code != 0 or not status['installed']:
            raise RuntimeError(f'Instalação não verificada (winget: {code}). Consulte o log e o link oficial.')
        if not status['running']:
            emit('log', {'text':'Ollama instalado; serviço ainda não responde. Use Iniciar serviço.'})
        return status

    def start(self, restart=False):
        if restart:
            if not self.owned or self.owned.poll() is not None:
                raise ValueError('Só é possível reiniciar o processo iniciado pelo Studio. Para instância externa, use o ícone do Ollama no Windows.')
            self.owned.terminate()
            self.owned.wait(timeout=15)
        elif self.status()['running']:
            return self.status()
        path = self.executable()
        if not path:
            raise ValueError('Ollama não instalado')
        env = dict(os.environ, OLLAMA_NUM_PARALLEL='1', OLLAMA_MAX_LOADED_MODELS='1', OLLAMA_HOST='127.0.0.1:11434')
        self.owned = subprocess.Popen([path,'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      env=env, creationflags=HIDDEN)
        for _ in range(20):
            time.sleep(.5)
            status = self.status()
            if status['running']:
                return status
            if self.owned.poll() is not None:
                break
        raise RuntimeError('Serviço não respondeu após a tentativa de início')
