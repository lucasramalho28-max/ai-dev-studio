import json
import re
import uuid
from agents.registry import AGENTS, BASE_PROMPT
from core.context_manager import (context, project_sources, build_messages, input_budget,
                                  estimate_tokens, validate_query_reply)
from core.response_policy import intent, credential_query, credential_answer, defined_demo_access, FACTUAL_RULES, QUERY_RULES, CHANGE_RULES, normalize
from core.proposal_validation import extract_files, resolve_edits, validate_proposals
from services.starter_service import stock_starter


class Orchestrator:
    def __init__(self, store, files, ollama, jobs):
        self.store, self.files, self.ollama, self.jobs = store,files,ollama,jobs

    def agents(self):
        return AGENTS + self.store.setting('custom_agents',[])

    def run(self, project, payload):
        prompt = payload.get('prompt','').strip()
        if not prompt or len(prompt)>20000:
            raise ValueError('Mensagem vazia ou longa demais')
        agent_id = payload.get('agent','coordinator')
        agents = {a['id']:a for a in self.agents()}
        if agent_id not in agents:
            raise ValueError('Agente inválido')
        mode = intent(prompt, payload.get('mode', 'auto'))
        credentials = mode == 'query' and credential_query(prompt)
        sequence = ['coordinator','logistics','database','backend','frontend','testing','browser','reviewer','logistics','coordinator'] if payload.get('orchestrate') and mode == 'change' else [agent_id]
        if sequence == [agent_id]:
            message_id = self.store.message(project,agent_id,'user',prompt)
        else:
            message_id = self.store.message(project,'coordinator','user',prompt)

        def work(jid, emit, cancel):
            staged, bases, previous = {}, {}, ''
            emit('log', {'text': 'Consulta: um agente, sem propostas de arquivos.' if mode == 'query'
                        else 'Pedido de alteração: propostas sujeitas à revisão.'})
            with self.files.lock:
                starter = stock_starter(self.files,project,prompt) if mode == 'change' else None
                if starter:
                    starter_bases = {name:self.files.read(project,name)['hash']
                                     if self.files.path(project,name).exists() else None for name in starter}
            if starter:
                tid = jid+'-0'
                self.store.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)',(tid,jid,agent_id,0,'running',''))
                emit('agent', {'agent':agent_id,'status':'PROGRAMANDO','task':prompt[:160],
                               'model':'Base local de cadastro e estoque (sem inferência)'})
                try:
                    validate_proposals(starter,self.files,project)
                    if cancel.is_set():
                        self.store.execute("UPDATE tasks SET status='cancelled' WHERE id=?",(tid,))
                        return {'proposals':[],'message':'','mode':mode}
                    ids = []
                    for name, content in starter.items():
                        proposal_id = uuid.uuid4().hex
                        self.store.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?)',
                            (proposal_id,project,jid,name,content,starter_bases[name],'pending'))
                        ids.append(proposal_id)
                    demo = defined_demo_access(starter['app.py'])
                    answer = ('Preparei uma base local reutilizável para cadastro, login e dashboard de estoque fictício. '
                              'Esta etapa usa arquivos do Studio, sem geração livre do modelo.\n'
                              'Inclui 72 produtos, 216 posições, três centros e 626 movimentos fictícios, filtros, gráficos, CSV e testes.\n'
                              f"Acesso de demonstração previsto: usuário {demo['username']}, senha {demo['password']}. "
                              'Revise e aplique as propostas, depois execute o projeto e os testes para verificar o acesso. '
                              'A geração das propostas não executou o aplicativo.')
                    self.store.message(project,agent_id,'assistant',answer)
                    self.store.set('memory_v2:'+project,[{'request':prompt[:600],'proposed_files':list(starter)}])
                    self.store.execute("UPDATE tasks SET status='completed',result=? WHERE id=?",(answer,tid))
                    emit('token',{'agent':agent_id,'text':answer})
                    emit('agent',{'agent':agent_id,'status':'CONCLUÍDO','files':list(starter)})
                    emit('proposals',{'ids':ids,'files':list(starter)})
                    return {'proposals':ids,'message':answer,'mode':mode,'source':'local_starter'}
                except Exception as exc:
                    if reply:
                        self.store.event(jid,'model_output',{'agent':aid,'text':reply,'error':str(exc)})
                    self.store.execute("UPDATE tasks SET status='error',result=? WHERE id=?",(str(exc),tid))
                    emit('agent',{'agent':agent_id,'status':'ERRO','error':str(exc)})
                    raise
            if credentials:
                # No model, memory, test fixtures or unapproved proposals can supply a password.
                tid = jid + '-0'
                self.store.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)',
                                   (tid,jid,agent_id,0,'running',''))
                emit('agent', {'agent':agent_id,'status':'ANALISANDO','task':prompt[:160],
                               'model':'Análise local de evidências'})
                try:
                    sources, _, _ = project_sources(self.files, project, prompt)
                    if cancel.is_set():
                        self.store.execute("UPDATE tasks SET status='cancelled' WHERE id=?", (tid,))
                        emit('agent', {'agent':agent_id,'status':'INTERROMPIDO'})
                        return {'proposals':[], 'message':'', 'mode':mode}
                    answer = credential_answer(sources)
                    self.store.message(project,agent_id,'assistant',answer)
                    self.store.execute("UPDATE tasks SET status='completed',result=? WHERE id=?", (answer,tid))
                    emit('token', {'agent':agent_id,'text':answer})
                    emit('agent', {'agent':agent_id,'status':'CONCLUÍDO','files':[]})
                    emit('proposals', {'ids':[], 'files':[]})
                    return {'proposals':[], 'message':answer, 'mode':mode}
                except Exception as exc:
                    self.store.execute("UPDATE tasks SET status='error',result=? WHERE id=?", (str(exc),tid))
                    emit('agent', {'agent':agent_id,'status':'ERRO','error':str(exc)})
                    raise
            try:
                installed_models = {item.get('name') for item in self.ollama.tags()}
            except Exception:
                installed_models = set()
            # A versão-base precede a inferência: salvar durante o streaming
            # também precisa causar conflito, não autorizar a substituição.
            initial = {}
            for entry in self.files.list(project):
                try:
                    initial[entry['path']] = self.files.read(project,entry['path'])['hash']
                except (OSError,UnicodeError,ValueError):
                    initial[entry['path']] = '__unreadable__'
            for i, aid in enumerate(sequence):
                tid = jid+'-'+str(i)
                self.store.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)',(tid,jid,aid,i,'queued',''))
            for i, aid in enumerate(sequence):
                if cancel.is_set():
                    break
                a = agents[aid]
                tid = jid+'-'+str(i)
                self.store.execute("UPDATE tasks SET status='running' WHERE id=?",(tid,))
                configured = self.store.setting('agent_model:'+aid,'')
                default_model = self.store.setting('model','qwen2.5-coder:3b')
                preferred = a.get('preferred_model')
                coding = a.get('coding_model')
                selected = configured or (preferred if preferred in installed_models else None) or (coding if coding in installed_models else None) or default_model
                emit('agent',{'agent':aid,'status':a.get('status','PROGRAMANDO'),'task':prompt[:160],'model':selected})
                system = (a.get('prompt') or BASE_PROMPT.format(**a)) + '\n' + FACTUAL_RULES
                if mode == 'query':
                    system += '\n' + QUERY_RULES
                else:
                    system += '\n' + CHANGE_RULES
                reply = ''
                done = False
                progress_size = 0
                try:
                    available = input_budget(mode) - estimate_tokens(system) - estimate_tokens(prompt) - 160
                    ctx = context(self.store,self.files,project,prompt,staged,budget=max(0, available))
                    history = self.store.rows('SELECT role,content FROM messages WHERE project=? AND agent=? AND id<? ORDER BY id DESC LIMIT 6',(project,aid,message_id))[::-1]
                    messages = build_messages(system,prompt,ctx,history,previous,mode)
                    stream = (self.ollama.chat(selected,messages,cancel,mode='query') if mode == 'query'
                              else self.ollama.chat(selected,messages,cancel))
                    for chunk in stream:
                        token = chunk.get('message',{}).get('content','')
                        reply += token
                        if len(reply) - progress_size >= 2000:
                            progress_size = len(reply)
                            emit('log', {'text':f'{aid}: resposta recebida ({progress_size} caracteres); aguardando validação.'})
                        done = chunk.get('done',False)
                        if done and chunk.get('done_reason') == 'length':
                            raise RuntimeError('Resposta atingiu o limite de geração. Divida o pedido; nenhuma proposta desta execução foi criada.')
                    if cancel.is_set():
                        self.store.execute("UPDATE tasks SET status='cancelled',result=? WHERE id=?",(reply,tid))
                        emit('agent',{'agent':aid,'status':'INTERROMPIDO'})
                        break
                    if not done:
                        raise RuntimeError('Resposta Ollama terminou sem confirmação de conclusão')
                    if mode == 'query':
                        # Validate only references that survived message budgeting.
                        supplied_context = messages[-1]['content'].split('\nCONTEXTO:\n', 1)[-1]
                        reply = validate_query_reply(reply, supplied_context)
                        emit('token', {'agent':aid, 'text':reply})
                    generated = extract_files(reply) if mode == 'change' else {}
                    if mode == 'change':
                        generated.update(resolve_edits(reply,self.files,project,{**staged,**generated}))
                    if generated:
                        validate_proposals({**staged, **generated},self.files,project,references=False)
                        self.store.event(jid,'model_output',{'agent':aid,'text':reply})
                        reply = ('Arquivos propostos: '+', '.join(generated)+'.\n'
                                 'A sintaxe Python e as dependências passaram pela validação estática. '
                                 'Revise as alterações antes de aplicar. Execução e testes ainda não foram realizados.')
                        emit('token', {'agent':aid,'text':reply})
                    elif mode == 'change':
                        if len(sequence)==1 and 'planej' not in normalize(prompt):
                            raise ValueError('O modelo não entregou arquivos nem edições verificáveis. Nenhuma alteração foi criada; divida o pedido ou indique o arquivo.')
                        try:
                            document=json.loads(reply)
                            reply=document.get('summary',reply) if isinstance(document,dict) else reply
                        except ValueError:
                            pass
                        reply = 'Análise do modelo (não validada por execução):\n' + reply
                        emit('token', {'agent':aid,'text':reply})
                    self.store.message(project,aid,'assistant',reply)
                    for name, content in generated.items():
                        if name not in bases:
                            bases[name] = initial.get(name)
                        staged[name] = content
                    previous = reply
                    self.store.execute("UPDATE tasks SET status='completed',result=? WHERE id=?",(reply,tid))
                    emit('agent',{'agent':aid,'status':'CONCLUÍDO','files':list(staged)})
                except Exception as exc:
                    self.store.execute("UPDATE tasks SET status='error',result=? WHERE id=?",(str(exc),tid))
                    self.store.message(project,aid,'assistant','Falha no pedido: '+str(exc))
                    emit('agent',{'agent':aid,'status':'ERRO','error':str(exc)})
                    raise
            proposals = []
            if not cancel.is_set():
                try:
                    validate_proposals(staged,self.files,project)
                except ValueError as exc:
                    self.store.execute("UPDATE tasks SET status='error',result=? WHERE id=?", (str(exc),tid))
                    emit('agent', {'agent':aid,'status':'ERRO','error':str(exc)})
                    raise
                for name, content in staged.items():
                    pid = uuid.uuid4().hex
                    self.store.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?)',
                                       (pid,project,jid,name,content,bases[name],'pending'))
                    proposals.append(pid)
                if mode == 'change':
                    memory = self.store.setting('memory_v2:'+project, [])
                    if not isinstance(memory, list):
                        memory = []
                    memory.append({'request':prompt[:600], 'proposed_files':list(staged)})
                    self.store.set('memory_v2:'+project, memory[-8:])
                emit('proposals',{'ids':proposals,'files':list(staged)})
            return {'proposals':proposals,'message':previous,'mode':mode}
        return self.jobs.start('chat',project,payload,work,serial=True)
