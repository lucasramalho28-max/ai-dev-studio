import io
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from app import create_app
from core.store import Store
from services.ollama_service import Ollama


class StudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.app=create_app(self.root/'data',self.root/'workspace',testing=True)
        self.client=self.app.test_client()
        self.client.get('/')
        with self.client.session_transaction() as s:
            self.headers={'X-Studio-Token':s['csrf']}
        self.s=self.app.extensions['studio']
        self.pid=self.call('/api/projects','POST',{'name':'Teste'}).json['id']

    def tearDown(self):
        for thread in list(self.s['jobs'].threads.values()):
            thread.join(timeout=5)
        self.s['execution'].stop(self.pid)
        self.tmp.cleanup()

    def call(self,path,method='GET',data=None,**kwargs):
        return self.client.open(path,method=method,json=data,headers=self.headers,**kwargs)

    def wait(self,jid):
        for _ in range(200):
            job=self.s['store'].one('SELECT * FROM jobs WHERE id=?',(jid,))
            if job['status'] not in ('running','queued') and jid not in self.s['jobs'].threads:
                return job
            time.sleep(.02)
        self.fail('Job timed out')

    def test_home_and_state(self):
        self.assertEqual(self.client.get('/').status_code,200)
        data=self.call('/api/state').json
        self.assertEqual(len(data['agents']),8)
        self.assertEqual(data['projects'][0]['name'],'Teste')

    def test_project_scaffold(self):
        files=self.call(f'/api/projects/{self.pid}/files').json
        self.assertEqual(len(files),4)
        self.assertIn('templates/index.html',[f['path'] for f in files])

    def test_file_roundtrip_and_conflict(self):
        url=f'/api/projects/{self.pid}/file'
        response=self.call(url,'PUT',{'path':'nested/code.py','content':'print(1)','hash':None})
        self.assertEqual(response.status_code,200)
        h=response.json['hash']
        self.assertEqual(self.call(url+'?path=nested/code.py').json['content'],'print(1)')
        self.assertEqual(self.call(url,'PUT',{'path':'nested/code.py','content':'print(2)','hash':None}).status_code,409)
        self.assertEqual(self.call(url,'PUT',{'path':'nested/code.py','content':'print(2)','hash':h}).status_code,200)

    def test_paths_blocked(self):
        for path in ['../escape.py','C:/Windows/test','/tmp/test','a/../../x','a\\b', 'file:stream','.env','a/.hidden','CON.txt','a/NUL','a. /test','a./test']:
            with self.subTest(path=path):
                result=self.call(f'/api/projects/{self.pid}/file','PUT',{'path':path,'content':'x','hash':None})
                self.assertEqual(result.status_code,400)
        self.assertFalse((self.root/'escape.py').exists())

    def test_unknown_project(self):
        self.assertEqual(self.call('/api/projects/'+('a'*32)+'/files').status_code,400)

    def test_csrf_and_host(self):
        self.assertEqual(self.client.post('/api/projects',json={'name':'x'}).status_code,403)
        self.assertEqual(self.client.get('/api/state',headers={'Host':'attacker.test'}).status_code,403)
        self.assertEqual(self.client.get('/api/state',headers={'Host':'10.0.0.25:5050'}).status_code,200)
        self.assertEqual(self.client.post('/api/projects',json={'name':'x'},headers={**self.headers,'Origin':'https://evil.test'}).status_code,403)

    def test_delete_confirmation(self):
        p=self.call(f'/api/projects/{self.pid}/file?path=app.py').json
        url=f'/api/projects/{self.pid}/file'
        self.assertEqual(self.call(url,'DELETE',p).status_code,403)
        self.assertEqual(self.call(url,'DELETE',{**p,'confirm':True}).status_code,200)

    def test_rename(self):
        p=self.call(f'/api/projects/{self.pid}/file?path=app.py').json
        r=self.call(f'/api/projects/{self.pid}/rename','POST',{'path':'app.py','new_path':'main.py','hash':p['hash']})
        self.assertEqual(r.status_code,200)
        self.assertTrue(self.s['files'].path(self.pid,'main.py').exists())

    def test_installer_status_mock(self):
        with patch.object(self.s['installer'],'executable',return_value='C:/ollama.exe'),patch.object(self.s['ollama'],'request',return_value={'version':'test'}):
            result=self.call('/api/ollama/status').json
            self.assertTrue(result['installed']);self.assertTrue(result['running'])
            self.assertEqual(result['version'],'test')

    def test_installer_requires_confirmation(self):
        with patch.object(self.s['installer'],'install') as install:
            self.assertEqual(self.call('/api/ollama/install','POST',{}).status_code,403)
            install.assert_not_called()

    def test_installer_job(self):
        with patch.object(self.s['installer'],'install',return_value={'installed':True,'running':True}) as install:
            jid=self.call('/api/ollama/install','POST',{'confirm':True}).json['job']
            job=self.wait(jid)
            self.assertEqual(job['status'],'completed');install.assert_called_once()

    def test_installer_winget_missing(self):
        with patch('services.ollama_installer.os.name','nt'),patch('services.ollama_installer.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'winget indisponível'):
                self.s['installer'].install(lambda *x:None,threading.Event())

    def test_external_service_restart_blocked(self):
        with self.assertRaisesRegex(ValueError,'instância externa'):
            self.s['installer'].start(restart=True)

    def test_winget_command_and_post_install_verification(self):
        proc=MagicMock()
        proc.__enter__.return_value=proc
        proc.stdout=iter(['Installing official package\n'])
        proc.wait.return_value=0
        with patch('services.ollama_installer.os.name','nt'),patch('services.ollama_installer.shutil.which',return_value='winget.exe'),patch('services.ollama_installer.subprocess.Popen',return_value=proc) as popen,patch.object(self.s['installer'],'status',return_value={'installed':False,'running':False}):
            with self.assertRaisesRegex(RuntimeError,'não verificada'):
                self.s['installer'].install(lambda *x:None,threading.Event())
            command=popen.call_args.args[0]
            self.assertIn('Ollama.Ollama',command)
            self.assertIn('--exact',command)
            self.assertEqual(command[command.index('--source')+1],'winget')

    def test_manual_save_during_generation_conflicts(self):
        def response(*args):
            old=self.s['files'].read(self.pid,'app.py')
            self.s['files'].write(self.pid,'app.py','manual save during generation',old['hash'])
            yield {'message':{'content':'```file:app.py\n# generated from old context\n```'},'done':True}
        with patch.object(self.s['ollama'],'chat',side_effect=response):
            jid=self.call(f'/api/projects/{self.pid}/chat','POST',{'prompt':'Edite app.py','agent':'backend'}).json['job']
            self.assertEqual(self.wait(jid)['status'],'completed')
        proposal=self.call(f'/api/projects/{self.pid}/proposals').json[0]
        self.assertEqual(self.call('/api/proposals/'+proposal['id'],'POST',{'confirm':True}).status_code,409)
        self.assertEqual(self.s['files'].read(self.pid,'app.py')['content'],'manual save during generation')

    def test_models_list_and_select(self):
        with patch.object(self.s['ollama'],'tags',return_value=[{'name':'qwen2.5-coder:3b','size':123}]):
            self.assertEqual(self.call('/api/models').json['models'][0]['size'],123)
            self.assertEqual(self.call('/api/models/select','POST',{'model':'qwen2.5-coder:3b'}).status_code,200)
            self.assertEqual(self.call('/api/models/select','POST',{'model':'absent'}).status_code,400)

    def test_download_progress_verified(self):
        chunks=[{'status':'downloading','total':100,'completed':50,'digest':'a'},{'status':'success'}]
        with patch.object(self.s['ollama'],'stream',return_value=iter(chunks)),patch.object(self.s['ollama'],'tags',return_value=[{'name':'qwen2.5-coder:3b'}]):
            jid=self.call('/api/models/pull','POST',{'confirm':True,'model':'qwen2.5-coder:3b'}).json['job']
            job=self.wait(jid)
            self.assertEqual(job['status'],'completed',job['result'])
            events=self.s['store'].rows("SELECT * FROM events WHERE job=? AND type='progress'",(jid,))
            self.assertEqual(len(events),2)
            self.assertEqual(json.loads(events[0]['data'])['completed'],50)

    def test_download_unverified_fails(self):
        with patch.object(self.s['ollama'],'stream',return_value=iter([{'status':'success'}])),patch.object(self.s['ollama'],'tags',return_value=[]):
            jid=self.call('/api/models/pull','POST',{'confirm':True,'model':'missing'}).json['job']
            self.assertEqual(self.wait(jid)['status'],'error')

    def test_model_delete_confirmed_and_verified(self):
        with patch.object(self.s['ollama'],'request',return_value={}) as req,patch.object(self.s['ollama'],'tags',return_value=[]):
            self.assertEqual(self.call('/api/models','DELETE',{'model':'x'}).status_code,403)
            self.assertEqual(self.call('/api/models','DELETE',{'model':'x','confirm':True}).status_code,200)
            req.assert_called_once_with('/api/delete',{'model':'x'},'DELETE')

    def test_model_validation(self):
        for name in ['','a;del C:','a b','$(x)','a\nb']:
            with self.assertRaises(ValueError):Ollama.validate_model(name)

    def test_chat_persistence_and_proposal(self):
        reply='Arquivo proposto:\n```file:hello.py\nprint("oi")\n```'
        with patch.object(self.s['ollama'],'chat',return_value=iter([{'message':{'content':reply},'done':True}])):
            jid=self.call(f'/api/projects/{self.pid}/chat','POST',{'prompt':'Crie hello','agent':'backend'}).json['job']
            self.assertEqual(self.wait(jid)['status'],'completed')
        history=self.call(f'/api/projects/{self.pid}/history?agent=backend').json
        self.assertEqual([m['role'] for m in history],['user','assistant'])
        self.assertFalse(self.s['files'].path(self.pid,'hello.py').exists())
        proposals=self.call(f'/api/projects/{self.pid}/proposals').json
        self.assertEqual(len(proposals),1)
        self.assertEqual(self.call('/api/proposals/'+proposals[0]['id'],'POST',{'confirm':True}).status_code,200)
        self.assertEqual(self.s['files'].read(self.pid,'hello.py')['content'],'print("oi")\n')
        connection=sqlite3.connect(self.root/'data'/'studio.sqlite3')
        self.assertEqual(connection.execute('SELECT count(*) FROM messages').fetchone()[0],2)
        connection.close()

    def test_proposal_conflict(self):
        self.s['store'].execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?)',('test',self.pid,'','app.py','new',self.s['files'].read(self.pid,'app.py')['hash'],'pending'))
        self.s['files'].write(self.pid,'app.py','manual',self.s['files'].read(self.pid,'app.py')['hash'])
        self.assertEqual(self.call('/api/proposals/test','POST',{'confirm':True}).status_code,409)
        self.assertEqual(self.s['files'].read(self.pid,'app.py')['content'],'manual')

    def test_orchestration_sequence(self):
        def response(*args):return iter([{'message':{'content':'Análise concluída'},'done':True}])
        with patch.object(self.s['ollama'],'chat',side_effect=response) as chat:
            jid=self.call(f'/api/projects/{self.pid}/chat','POST',{'prompt':'Planeje','orchestrate':True}).json['job']
            self.assertEqual(self.wait(jid)['status'],'completed')
            self.assertEqual(chat.call_count,10)
            tasks=self.s['store'].rows('SELECT * FROM tasks WHERE job=? ORDER BY position',(jid,))
            self.assertEqual([t['agent'] for t in tasks],['coordinator','logistics','database','backend','frontend','testing','browser','reviewer','logistics','coordinator'])
            self.assertTrue(all(t['status']=='completed' for t in tasks))
            flow=self.call(f'/api/projects/{self.pid}/flow').json['executions']
            self.assertEqual(len(flow),1)
            self.assertEqual(len(flow[0]['tasks']),10)
            handoffs=[e['data'] for e in flow[0]['events'] if e['type']=='handoff']
            self.assertEqual(len(handoffs),9)
            self.assertEqual(handoffs[0]['from_task'],tasks[0]['id'])
            self.assertEqual(handoffs[0]['to_task'],tasks[1]['id'])
            self.assertFalse(any(e['type'] in ('token','model_output') for e in flow[0]['events']))
            other=self.call('/api/projects','POST',{'name':'Outro'}).json['id']
            self.assertEqual(self.call(f'/api/projects/{other}/flow').json['executions'],[])

    def test_serial_gpu_queue(self):
        lock=threading.Lock();busy=0;max_busy=0
        def work(j,e,c):
            nonlocal busy,max_busy
            with lock:busy+=1;max_busy=max(max_busy,busy)
            time.sleep(.05)
            with lock:busy-=1
        ids=[self.s['jobs'].start('test','',{},work,serial=True) for _ in range(3)]
        for jid in ids:self.wait(jid)
        self.assertEqual(max_busy,1)

    def test_cancel_queued_job(self):
        self.s['jobs'].gpu.acquire()
        try:
            jid=self.s['jobs'].start('chat','',{},lambda *x:None,serial=True)
            self.s['jobs'].cancel(jid)
        finally:self.s['jobs'].gpu.release()
        self.assertEqual(self.wait(jid)['status'],'cancelled')

    def test_sse_real_events(self):
        jid=self.s['jobs'].start('test','',{},lambda j,e,c:e('log',{'text':'hello'}))
        self.wait(jid)
        result=self.call('/api/jobs/'+jid+'/events')
        self.assertIn(b'event: log',result.data);self.assertIn(b'hello',result.data)
        self.assertIn(b'event: end',result.data)

    def test_custom_agent_confirmation(self):
        config={'name':'Analista','specialty':'Requisitos','prompt':'Analise requisitos.'}
        self.assertEqual(self.call('/api/agents','POST',config).status_code,403)
        r=self.call('/api/agents','POST',{**config,'confirm':True})
        self.assertEqual(r.status_code,201);self.assertEqual(r.json['tools'],['propose_files'])

    def test_recovery_after_restart(self):
        self.s['store'].execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',('interrupted','chat',self.pid,'running','{}','','now'))
        Store(self.root/'data'/'studio.sqlite3')
        self.assertEqual(self.s['store'].one("SELECT status FROM jobs WHERE id='interrupted'")['status'],'interrupted')

    def test_execution_real_flask(self):
        self.assertEqual(self.call(f'/api/projects/{self.pid}/process','POST',{'action':'start'}).status_code,403)
        response=self.call(f'/api/projects/{self.pid}/process','POST',{'action':'start','confirm':True})
        self.assertEqual(response.status_code,200)
        for _ in range(80):
            status=self.s['execution'].status(self.pid)
            if status['ready']:break
            time.sleep(.1)
        self.assertTrue(status['running']);self.assertTrue(status['ready'])
        import urllib.request
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(status['url'],timeout=3) as res:
            self.assertEqual(res.status,200)
            self.assertIn('Seu projeto',res.read().decode())
        self.s['execution'].stop(self.pid)
        self.assertFalse(self.s['execution'].status(self.pid)['running'])

    def test_project_tests_real(self):
        result=self.s['execution'].tests(self.pid)
        self.assertEqual(result['exit_code'],0,result['output'])
        self.assertIn('Ran 1 test',result['output'])

    def test_browser_requires_running_project(self):
        with self.assertRaisesRegex(ValueError,'Inicie o projeto'):
            self.s['browser'].inspect(self.pid)

    def test_browser_integration_mock(self):
        with patch.object(self.s['browser'],'inspect',return_value={'status':200,'errors':[],'screenshot':'mock'}):
            jid=self.call(f'/api/projects/{self.pid}/browser','POST',{'confirm':True}).json['job']
            self.assertEqual(self.wait(jid)['status'],'completed')

    def test_browser_mobile_viewport_is_forwarded(self):
        with patch.object(self.s['browser'],'inspect',return_value={'status':200,'errors':[]}) as inspect:
            viewport={'width':390,'height':844}
            jid=self.call(f'/api/projects/{self.pid}/browser','POST',{'confirm':True,'viewport':viewport}).json['job']
            self.assertEqual(self.wait(jid)['status'],'completed')
            inspect.assert_called_once_with(self.pid,[],viewport=viewport)

    def test_ollama_ndjson_stream(self):
        service=Ollama()
        response=io.BytesIO(b'{"status":"downloading","completed":2}\n{"status":"success"}\n')
        with patch.object(service,'open',return_value=response):
            self.assertEqual(len(list(service.stream('/api/pull',{},threading.Event()))),2)


if __name__=='__main__':unittest.main()
