import atexit
import ipaddress
import json
import os
import secrets
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit
from flask import Flask, Response, jsonify, render_template, request, send_from_directory, session
import config
from agents.registry import AGENTS
from core.store import Store, now
from core.jobs import Jobs
from core.orchestrator import Orchestrator
from core.proposal_validation import validate_proposals
from services.file_service import FileService
from services.ollama_service import Ollama
from services.ollama_installer import OllamaInstaller
from services.execution_service import Execution
from services.browser_service import Browser
from services.logistics_service import LogisticsService
from services.dashboard_service import DashboardService
from routes.logistics_routes import logistics_blueprint

SAMPLE = '''from flask import Flask, render_template
app = Flask(__name__)

@app.get('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
'''
SAMPLE_HTML = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Meu projeto Flask</title>
<style>body{background:#101522;color:#edf2ff;font:18px system-ui;max-width:800px;margin:12vh auto;padding:24px}span{color:#6de4c5}h1{font-size:48px}a{color:#6de4c5}</style>
<span>CRIADO NO AI DEV STUDIO</span><h1>Seu projeto está no ar.</h1><p>Edite os arquivos ou peça ajuda aos agentes para começar.</p></html>'''


def create_app(data=None, workspace=None, testing=False):
    data = Path(data or config.DATA)
    data.mkdir(parents=True,exist_ok=True)
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32),TESTING=testing,MAX_CONTENT_LENGTH=26*1024*1024,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    store = Store(data/'studio.sqlite3')
    files = FileService(workspace or config.WORKSPACE)
    ollama = Ollama()
    installer = OllamaInstaller(ollama)
    jobs = Jobs(store)
    execution = Execution(files)
    browser = Browser(execution,data)
    orchestrator = Orchestrator(store,files,ollama,jobs)
    logistics = LogisticsService(data,store)
    dashboards = DashboardService(logistics,files,store)
    app.extensions['studio'] = dict(store=store,files=files,ollama=ollama,installer=installer,jobs=jobs,
                                    execution=execution,browser=browser,orchestrator=orchestrator,
                                    logistics=logistics,dashboards=dashboards)

    def project(pid):
        if not store.one('SELECT id FROM projects WHERE id=?',(pid,)):
            raise ValueError('Projeto inexistente')
        return pid

    def body():
        value = request.get_json(silent=True)
        if not isinstance(value,dict):
            raise ValueError('JSON obrigatório')
        return value

    def confirmed(value):
        if value.get('confirm') is not True:
            raise PermissionError('Confirmação explícita obrigatória')

    app.register_blueprint(logistics_blueprint(project,body,confirmed,logistics,dashboards,jobs))

    @app.before_request
    def secure_local():
        hostname = request.host.split(':',1)[0].strip('[]')
        try:
            address = ipaddress.ip_address(hostname)
            local_host = address.is_private or address.is_loopback
        except ValueError:
            local_host = hostname == 'localhost'
        if not local_host:
            return jsonify(error='Host não permitido'),403
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin = request.headers.get('Origin')
            if origin and urlsplit(origin).netloc != request.host:
                return jsonify(error='Origem não permitida'),403
            if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-Studio-Token',''),session['csrf']):
                return jsonify(error='Sessão inválida. Recarregue a página.'),403

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Cache-Control']='no-store'
        return response

    @app.errorhandler(Exception)
    def error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc,HTTPException):
            return jsonify(error=exc.description),exc.code
        code = 409 if isinstance(exc,FileExistsError) else 403 if isinstance(exc,PermissionError) else 400 if isinstance(exc,(ValueError,FileNotFoundError,UnicodeError,KeyError)) else 502
        return jsonify(error=str(exc)),code

    @app.get('/')
    def index():
        session.setdefault('csrf',secrets.token_hex(32))
        return render_template('index.html',csrf=session['csrf'])

    @app.get('/api/state')
    def state():
        return jsonify(projects=store.rows('SELECT * FROM projects ORDER BY created DESC'),
                       agents=orchestrator.agents(), model=store.setting('model',config.DEFAULT_MODEL),
                       agent_models={a['id']:store.setting('agent_model:'+a['id'],'') for a in orchestrator.agents()},
                       jobs=store.rows('SELECT * FROM jobs ORDER BY created DESC LIMIT 30'))

    @app.post('/api/projects')
    def create_project():
        name = body().get('name','').strip()
        if not name or len(name)>80:
            raise ValueError('Nome deve ter entre 1 e 80 caracteres')
        pid = uuid.uuid4().hex
        files.root(pid).mkdir()
        files.write(pid,'app.py',SAMPLE,None)
        files.write(pid,'templates/index.html',SAMPLE_HTML,None)
        files.write(pid,'requirements.txt','Flask>=3.1,<4\n',None)
        files.write(pid,'tests/test_app.py',"import unittest\nfrom app import app\n\nclass AppTest(unittest.TestCase):\n    def test_home(self):\n        self.assertEqual(app.test_client().get('/').status_code, 200)\n",None)
        store.execute('INSERT INTO projects VALUES (?,?,?)',(pid,name,now()))
        store.event('', 'project',{'project':pid,'action':'created'})
        return jsonify(id=pid,name=name),201

    @app.get('/api/projects/<pid>/files')
    def list_files(pid):
        return jsonify(files.list(project(pid)))

    @app.get('/api/projects/<pid>/file')
    def read_file(pid):
        return jsonify(files.read(project(pid),request.args.get('path','')))

    @app.put('/api/projects/<pid>/file')
    def save_file(pid):
        b=body()
        result=files.write(project(pid),b['path'],b['content'],b.get('hash'))
        store.event('','file',{'project':pid,'action':'saved','path':b['path']})
        return jsonify(result)

    @app.delete('/api/projects/<pid>/file')
    def delete_file(pid):
        b=body(); confirmed(b)
        with files.lock:
            existing=files.read(project(pid),b['path'])
            if existing['hash'] != b.get('hash'):
                raise FileExistsError('Arquivo mudou desde a abertura')
            files.path(pid,b['path']).unlink()
        store.event('','file',{'project':pid,'action':'deleted','path':b['path']})
        return jsonify(ok=True)

    @app.post('/api/projects/<pid>/rename')
    def rename_file(pid):
        b=body()
        with files.lock:
            old=files.path(project(pid),b['path']); new=files.path(pid,b['new_path'])
            if new.exists():
                raise FileExistsError('Destino já existe')
            if files.read(pid,b['path'])['hash']!=b.get('hash'):
                raise FileExistsError('Arquivo mudou desde a abertura')
            new.parent.mkdir(parents=True,exist_ok=True); old.rename(new)
        store.event('','file',{'project':pid,'action':'renamed','from':b['path'],'to':b['new_path']})
        return jsonify(ok=True)

    @app.get('/api/ollama/status')
    def ollama_status():
        return jsonify(installer.status())

    @app.post('/api/ollama/install')
    def install_ollama():
        b=body(); confirmed(b)
        def run(jid,emit,cancel):
            if not jobs.install_lock.acquire(blocking=False):
                raise ValueError('Já existe uma instalação em andamento')
            try:
                return installer.install(emit,cancel)
            finally:
                jobs.install_lock.release()
        return jsonify(job=jobs.start('install','',{},run))

    @app.post('/api/ollama/start')
    def start_ollama():
        b=body(); confirmed(b)
        return jsonify(job=jobs.start('service','',b,lambda j,e,c:installer.start(b.get('restart',False))))

    @app.get('/api/models')
    def models():
        return jsonify(models=ollama.tags(),active=store.setting('model',config.DEFAULT_MODEL))

    @app.post('/api/models/pull')
    def pull():
        b=body(); confirmed(b)
        model=ollama.validate_model(b.get('model',config.DEFAULT_MODEL))
        def run(jid,emit,cancel):
            start=time.monotonic(); initial={}; finished=False
            for chunk in ollama.stream('/api/pull',{'model':model,'stream':True},cancel):
                digest=chunk.get('digest',''); completed=chunk.get('completed',0)
                initial.setdefault(digest,(completed,time.monotonic()))
                first,stamp=initial[digest]
                elapsed=time.monotonic()-stamp
                chunk['bytes_per_second']=(completed-first)/elapsed if elapsed>.1 else 0
                emit('progress',chunk)
                finished=chunk.get('status')=='success'
            if not cancel.is_set():
                if not finished or model not in [m.get('name') for m in ollama.tags()]:
                    raise RuntimeError('Download não confirmado na lista de modelos')
            return {'model':model,'verified':finished and not cancel.is_set(),'elapsed':time.monotonic()-start}
        return jsonify(job=jobs.start('pull','',b,run,serial=True))

    @app.delete('/api/models')
    def delete_model():
        b=body(); confirmed(b)
        model=ollama.validate_model(b['model'])
        if not jobs.gpu.acquire(blocking=False):
            raise ValueError('Aguarde as tarefas de IA antes de excluir um modelo')
        try:
            ollama.request('/api/delete',{'model':model},'DELETE')
            if model in [m.get('name') for m in ollama.tags()]:
                raise RuntimeError('Exclusão não verificada')
            return jsonify(ok=True)
        finally:
            jobs.gpu.release()

    @app.post('/api/models/select')
    def select_model():
        b=body(); model=ollama.validate_model(b['model'])
        if model not in [m.get('name') for m in ollama.tags()]:
            raise ValueError('Escolha um modelo instalado')
        agent=b.get('agent')
        if agent and agent not in [a['id'] for a in orchestrator.agents()]:
            raise ValueError('Agente inválido')
        store.set('agent_model:'+agent if agent else 'model',model)
        return jsonify(ok=True)

    @app.post('/api/models/test')
    def test_model():
        b=body(); model=ollama.validate_model(b['model'])
        def run(jid,emit,cancel):
            reply=''; done=False
            for part in ollama.chat(model,[{'role':'user','content':'Responda apenas: OK'}],cancel,mode='test'):
                token=part.get('message',{}).get('content','');reply+=token
                emit('token',{'text':token,'agent':'test'})
                done=part.get('done',False)
            if not cancel.is_set() and not done:
                raise RuntimeError('Teste incompleto')
            return {'reply':reply,'verified':done and not cancel.is_set()}
        return jsonify(job=jobs.start('model_test','',b,run,serial=True))

    @app.post('/api/projects/<pid>/chat')
    def chat(pid):
        return jsonify(job=orchestrator.run(project(pid),body()))

    @app.get('/api/projects/<pid>/history')
    def history(pid):
        return jsonify(store.rows('SELECT * FROM messages WHERE project=? AND agent=? ORDER BY id DESC LIMIT 100',
                                  (project(pid),request.args.get('agent','coordinator')))[::-1])

    @app.get('/api/projects/<pid>/proposals')
    def proposals(pid):
        return jsonify(store.rows("SELECT * FROM proposals WHERE project=? AND status='pending'",(project(pid),)))

    @app.post('/api/proposals/<proposal_id>')
    def apply_proposal(proposal_id):
        b=body(); confirmed(b)
        p=store.one("SELECT * FROM proposals WHERE id=? AND status='pending'",(proposal_id,))
        if not p:
            raise ValueError('Proposta inexistente')
        if b.get('reject'):
            store.execute("UPDATE proposals SET status='rejected' WHERE id=?",(proposal_id,))
        else:
            siblings = store.rows("SELECT path,content FROM proposals WHERE project=? AND job=? AND status='pending'", (p['project'],p['job']))
            validate_proposals({item['path']:item['content'] for item in siblings},files,p['project'])
            files.write(p['project'],p['path'],p['content'],p['base'])
            store.execute("UPDATE proposals SET status='applied' WHERE id=?",(proposal_id,))
            store.event(p['job'],'file',{'project':p['project'],'path':p['path'],'action':'proposal_applied',
                                       'automatic':b.get('automatic') is True})
        return jsonify(ok=True)

    @app.get('/api/jobs/<jid>/events')
    def events(jid):
        if not store.one('SELECT id FROM jobs WHERE id=?',(jid,)):
            raise ValueError('Execução inexistente')
        cursor=int(request.headers.get('Last-Event-ID') or request.args.get('after',0))
        def generate():
            nonlocal cursor
            while True:
                rows=store.rows('SELECT * FROM events WHERE job=? AND id>? ORDER BY id LIMIT 200',(jid,cursor))
                for row in rows:
                    cursor=row['id']
                    yield f"id: {cursor}\nevent: {row['type']}\ndata: {row['data']}\n\n"
                status=store.one('SELECT status FROM jobs WHERE id=?',(jid,))['status']
                if not rows and status not in ('queued','running'):
                    yield 'event: end\ndata: {}\n\n'
                    return
                if not rows:
                    yield ': keepalive\n\n'
                    time.sleep(.5)
        return Response(generate(),mimetype='text/event-stream',headers={'X-Accel-Buffering':'no'})

    @app.get('/api/jobs/<jid>')
    def job_status(jid):
        return jsonify(job=store.one('SELECT * FROM jobs WHERE id=?',(jid,)),tasks=store.rows('SELECT * FROM tasks WHERE job=? ORDER BY position',(jid,)))

    @app.post('/api/jobs/<jid>/cancel')
    def cancel_job(jid):
        jobs.cancel(jid); return jsonify(ok=True)

    @app.post('/api/jobs/<jid>/resume')
    def resume_job(jid):
        job=store.one('SELECT * FROM jobs WHERE id=?',(jid,))
        if not job or job['kind']!='chat' or job['status'] not in ('interrupted','cancelled','error'):
            raise ValueError('Somente conversas interrompidas podem ser reexecutadas')
        return jsonify(job=orchestrator.run(job['project'],json.loads(job['payload'])))

    @app.get('/api/projects/<pid>/process')
    def process_status(pid):
        return jsonify(execution.status(project(pid)))

    @app.post('/api/projects/<pid>/process')
    def process_control(pid):
        b=body(); project(pid)
        action=b.get('action')
        if action=='stop':
            return jsonify(execution.stop(pid))
        confirmed(b)
        store.event('','execution',{'project':pid,'action':action})
        if action=='venv':
            return jsonify(job=jobs.start('venv',pid,b,lambda j,e,c:execution.venv(pid,e,c)))
        if action=='test':
            def run(j,e,c):
                result=execution.tests(pid);e('test',result)
                if result['exit_code']!=0:
                    raise RuntimeError(result['output'])
                return result
            return jsonify(job=jobs.start('tests',pid,b,run))
        if action=='restart':
            execution.stop(pid)
        if action in ('start','restart'):
            return jsonify(execution.start(pid))
        raise ValueError('Ação inválida')

    @app.post('/api/projects/<pid>/browser')
    def browser_test(pid):
        b=body(); confirmed(b); project(pid)
        actions=b.get('actions',[])
        if not isinstance(actions,list):
            raise ValueError('Ações inválidas')
        def run(j,e,c):
            report=browser.inspect(pid,actions,viewport=b.get('viewport'));e('browser',report)
            return report
        return jsonify(job=jobs.start('browser',pid,b,run))

    @app.get('/api/screenshots/<name>')
    def screenshot(name):
        if not name.endswith('.png') or not store.one('SELECT id FROM projects WHERE id=?',(name[:-4],)):
            raise ValueError('Screenshot inválida')
        return send_from_directory(browser.screens,name)

    @app.post('/api/agents')
    def add_agent():
        b=body(); confirmed(b)
        if not all(isinstance(b.get(k),str) and b[k].strip() for k in ('name','specialty','prompt')):
            raise ValueError('Nome, especialidade e prompt são obrigatórios')
        if sum(len(b[k]) for k in ('name','specialty','prompt'))>12000:
            raise ValueError('Configuração longa demais')
        agents=store.setting('custom_agents',[])
        a={k:b[k] for k in ('name','specialty','prompt')}
        a.update(id='custom_'+uuid.uuid4().hex[:10],status='PROGRAMANDO',tools=['propose_files'])
        agents.append(a);store.set('custom_agents',agents)
        return jsonify(a),201

    def cleanup():
        for pid in list(execution.processes):
            try:
                execution.stop(pid)
            except Exception:
                pass
    atexit.register(cleanup)
    return app


if __name__=='__main__':
    print(f'AI DEV STUDIO: http://0.0.0.0:{config.PORT}',flush=True)
    create_app().run(host='0.0.0.0',port=config.PORT,debug=False,threaded=True)
