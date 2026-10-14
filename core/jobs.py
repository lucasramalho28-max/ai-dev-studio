import json
import threading
import uuid
from core.store import now


class Jobs:
    def __init__(self, store):
        self.store = store
        self.cancels = {}
        self.threads = {}
        self.gpu = threading.Lock()
        self.install_lock = threading.Lock()

    def start(self, kind, project, payload, fn, serial=False):
        jid = uuid.uuid4().hex
        cancel = threading.Event()
        self.cancels[jid] = cancel
        self.store.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',
                           (jid,kind,project,'queued',json.dumps(payload),'',now()))

        def emit(kind, data):
            self.store.event(jid, kind, data)

        def run():
            lock = self.gpu if serial else threading.Lock()
            try:
                with lock:
                    if cancel.is_set():
                        raise InterruptedError('Cancelado antes de iniciar')
                    self.store.execute("UPDATE jobs SET status='running' WHERE id=?", (jid,))
                    emit('status', {'status':'running'})
                    result = fn(jid, emit, cancel)
                    status = 'cancelled' if cancel.is_set() else 'completed'
                    self.store.execute('UPDATE jobs SET status=?,result=? WHERE id=?',
                                       (status,json.dumps(result, ensure_ascii=False),jid))
                    emit('done', {'status':status,'result':result})
            except Exception as exc:
                status = 'cancelled' if cancel.is_set() else 'error'
                self.store.execute('UPDATE jobs SET status=?,result=? WHERE id=?', (status,str(exc),jid))
                emit('error', {'message':str(exc), 'status':status})
            finally:
                self.cancels.pop(jid, None)
                self.threads.pop(jid, None)
        thread = threading.Thread(target=run, daemon=True, name='job-'+jid[:8])
        self.threads[jid] = thread
        thread.start()
        return jid

    def cancel(self, jid):
        job = self.store.one('SELECT * FROM jobs WHERE id=?', (jid,))
        if not job:
            raise ValueError('Execução inexistente')
        if job['kind'] not in ('chat','pull','model_test'):
            raise ValueError('Esta operação não admite interrupção segura pelo Studio')
        if jid in self.cancels:
            self.cancels[jid].set()
            self.store.event(jid,'log',{'text':'Interrupção solicitada; aguardando o próximo bloco de rede (até 120 s).'})
