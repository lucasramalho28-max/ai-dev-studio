import json
import re
import urllib.request
import urllib.error
from core.context_manager import NUM_CTX, input_budget, message_tokens, query_schema, change_schema


class Ollama:
    def __init__(self, url='http://127.0.0.1:11434'):
        self.url = url
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @staticmethod
    def validate_model(name):
        if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,150}', name):
            raise ValueError('Nome de modelo inválido')
        return name

    def open(self, endpoint, payload=None, method=None, timeout=15):
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.url+endpoint, data=body, method=method,
                                     headers={'Content-Type':'application/json'})
        try:
            return self.opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            raise RuntimeError('Ollama: '+e.read(4096).decode(errors='replace')) from None
        except (OSError, urllib.error.URLError) as e:
            raise RuntimeError('Ollama indisponível. Inicie o serviço no gerenciador de IA.') from e

    def request(self, endpoint, payload=None, method=None):
        with self.open(endpoint, payload, method) as r:
            return json.load(r)

    def stream(self, endpoint, payload, cancel):
        with self.open(endpoint, payload, timeout=120) as r:
            for line in r:
                if cancel.is_set():
                    return
                if line.strip():
                    item = json.loads(line)
                    if item.get('error'):
                        raise RuntimeError(item['error'])
                    yield item

    def tags(self):
        return self.request('/api/tags').get('models', [])

    def chat(self, model, messages, cancel, mode='change'):
        if message_tokens(messages) > input_budget(mode):
            raise ValueError('Contexto excede o orçamento de inferência. Reduza o pedido.')
        payload = {'model':self.validate_model(model), 'messages':messages,
                   'stream':True, 'think':False, 'keep_alive':'5m',
                   'options':{'num_ctx':NUM_CTX,'num_predict':768 if mode == 'query' else 32 if mode == 'test' else 2048,
                              'temperature':0 if mode == 'query' else 0.1}}
        if mode == 'query':
            payload['format'] = query_schema(messages)
        elif mode == 'change':
            payload['format'] = change_schema(messages)
        return self.stream('/api/chat', payload, cancel)
