import json
import uuid
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from core.store import now
from models.logistics import LogisticsDashboard
from services.logistics_service import ROLE_ALIASES, missing


APP_PY = '''from pathlib import Path
import json

from flask import Flask, jsonify, render_template

app = Flask(__name__)
DATA_FILE = Path(__file__).parent / "data" / "logistics_sla.json"


def dashboard_data():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/dashboard-data")
def data():
    return jsonify(dashboard_data())


@app.get("/api/health")
def health():
    data = dashboard_data()
    return jsonify(status="ok", records=len(data.get("records", [])))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
'''


INDEX_HTML = '''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Painel de SLA Logístico</title>
  <link rel="stylesheet" href="/static/dashboard.css">
</head>
<body>
<header>
  <div><span class="eyebrow">INTELIGÊNCIA LOGÍSTICA</span><h1>Painel de SLA de expedição</h1></div>
  <button id="export">Exportar visão em CSV</button>
</header>
<main>
  <aside class="filters" aria-label="Filtros">
    <h2>Filtros</h2>
    <label>Filial<select id="branch"><option value="">Todas</option></select></label>
    <label>Regional<select id="regional"><option value="">Todas</option></select></label>
    <label>Semana<select id="week"><option value="">Todas</option></select></label>
    <button id="clear">Limpar filtros</button>
    <div class="source"><strong>Fonte</strong><span id="source"></span><small>Os números abaixo são calculados somente a partir da base aprovada.</small></div>
  </aside>
  <section class="content">
    <div class="kpis">
      <article><span>Pedidos elegíveis</span><strong id="total">—</strong></article>
      <article><span>No prazo</span><strong id="ontime">—</strong></article>
      <article class="alert"><span>Com atraso</span><strong id="late">—</strong></article>
      <article class="primary"><span>SLA de expedição</span><strong id="sla">—</strong></article>
    </div>
    <div class="grid">
      <article class="panel"><h2>SLA por filial</h2><div id="branch-chart" class="bars"></div></article>
      <article class="panel"><h2>Motivos dos atrasos</h2><div id="reason-chart" class="bars red"></div></article>
      <article class="panel wide"><h2>Evolução semanal</h2><div id="week-chart" class="line-chart"></div></article>
      <article class="panel wide"><h2>Detalhamento por filial</h2><div class="table-wrap"><table><thead><tr><th>Filial</th><th>Regional</th><th>Pedidos</th><th>No prazo</th><th>Atrasados</th><th>SLA</th></tr></thead><tbody id="detail"></tbody></table></div></article>
      <article class="panel wide"><h2>Leitura executiva</h2><ul id="insights"></ul><p id="warning" class="warning"></p></article>
    </div>
  </section>
</main>
<script src="/static/dashboard.js"></script>
</body>
</html>
'''


DASHBOARD_CSS = '''
:root{--blue:#0647a8;--blue2:#0b63ce;--red:#e32732;--ink:#14213d;--muted:#68768c;--line:#dce4ef;--bg:#f4f7fb;--white:#fff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px Inter,Segoe UI,Arial,sans-serif}header{min-height:112px;padding:24px clamp(20px,4vw,64px);display:flex;align-items:center;justify-content:space-between;gap:24px;background:linear-gradient(120deg,#043984,#0b63ce);color:white;border-bottom:5px solid var(--red)}h1{margin:7px 0 0;font-size:clamp(24px,4vw,39px)}h2{font-size:16px;margin:0 0 20px}.eyebrow{font-size:11px;font-weight:800;letter-spacing:2px}button,select{font:inherit;border-radius:6px}button{border:1px solid #ffffff55;background:white;color:var(--blue);font-weight:700;padding:10px 14px;cursor:pointer}main{display:grid;grid-template-columns:230px 1fr;max-width:1600px;margin:auto}.filters{padding:28px 20px;min-height:calc(100vh - 117px);background:white;border-right:1px solid var(--line)}.filters label{display:block;color:var(--muted);font-size:12px;font-weight:700;margin:16px 0}.filters select{display:block;width:100%;margin-top:7px;padding:10px;border:1px solid var(--line);background:white}.filters>button{width:100%;border-color:var(--blue);margin-top:5px}.source{display:flex;flex-direction:column;gap:8px;margin-top:34px;padding-top:20px;border-top:1px solid var(--line);overflow-wrap:anywhere}.source strong{color:var(--blue)}.source span,.source small{color:var(--muted);font-size:11px;line-height:1.5}.content{padding:28px}.kpis{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:16px}.kpis article,.panel{background:white;border:1px solid var(--line);border-radius:10px;box-shadow:0 3px 16px #0b39700a}.kpis article{padding:20px;border-top:4px solid #9db9dc}.kpis article.primary{border-color:var(--blue2)}.kpis article.alert{border-color:var(--red)}.kpis span{display:block;color:var(--muted);font-size:12px}.kpis strong{display:block;font-size:30px;margin-top:8px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}.panel{padding:22px;min-height:280px}.panel.wide{grid-column:1/-1}.bars{display:flex;flex-direction:column;gap:13px}.bar-row{display:grid;grid-template-columns:minmax(80px,150px) 1fr 55px;align-items:center;gap:9px;font-size:12px}.bar-track{height:12px;background:#e8eef7;border-radius:99px;overflow:hidden}.bar-fill{height:100%;min-width:2px;background:linear-gradient(90deg,var(--blue),#35a4ff);border-radius:99px}.red .bar-fill{background:linear-gradient(90deg,#b81724,var(--red))}.line-chart svg{width:100%;height:230px;overflow:visible}.line-chart text{font-size:10px;fill:var(--muted)}.line-chart line{stroke:#dbe4ef}.line-chart polyline{fill:none;stroke:var(--blue2);stroke-width:3}.line-chart circle{fill:var(--red);stroke:white;stroke-width:2}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:12px;border-bottom:1px solid var(--line);white-space:nowrap}th{font-size:11px;color:var(--muted);text-transform:uppercase}td:last-child{font-weight:800;color:var(--blue)}#insights{line-height:1.7}.warning{border-left:4px solid var(--red);padding:10px 12px;background:#fff4f4;color:#8f1821}.empty{color:var(--muted);padding:20px 0}@media(max-width:900px){main{display:block}.filters{min-height:0;border-right:0;border-bottom:1px solid var(--line)}.filters label{display:inline-block;width:30%;margin-right:2%}.kpis{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}.panel.wide{grid-column:auto}}@media(max-width:560px){header{align-items:flex-start;flex-direction:column}.content{padding:16px}.kpis{grid-template-columns:1fr}.filters label{display:block;width:100%}.bar-row{grid-template-columns:85px 1fr 45px}}
'''.strip()


DASHBOARD_JS = r'''let DATA=null;
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const unique=(rows,key)=>[...new Set(rows.map(r=>r[key]).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'pt-BR'));
function fillSelect(id,values){const s=$(id);values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;s.append(o)})}
function filtered(){return DATA.records.filter(r=>(!$('branch').value||r.branch===$('branch').value)&&(!$('regional').value||r.regional===$('regional').value)&&(!$('week').value||r.week===$('week').value))}
function summarize(rows,key){const map=new Map;rows.forEach(r=>{const name=r[key]||'Não informado',x=map.get(name)||{name,total:0,on_time:0,late:0,regionals:new Set};x.total++;x.on_time+=r.on_time?1:0;x.late+=r.on_time?0:1;if(r.regional)x.regionals.add(r.regional);map.set(name,x)});return [...map.values()].map(x=>({...x,sla:x.total?100*x.on_time/x.total:0,regional:[...x.regionals].join(', ')})).sort((a,b)=>b.total-a.total)}
function bars(id,items,value,label,percent=false){const root=$(id);if(!items.length){root.innerHTML='<p class="empty">Sem registros para os filtros selecionados.</p>';return}const max=Math.max(...items.map(value),1);root.innerHTML=items.slice(0,12).map(x=>`<div class="bar-row"><span title="${esc(label(x))}">${esc(label(x))}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2,100*value(x)/max)}%"></div></div><strong>${percent?value(x).toFixed(1)+'%':value(x)}</strong></div>`).join('')}
function line(items){const root=$('week-chart');if(!items.length){root.innerHTML='<p class="empty">Sem período disponível.</p>';return}const w=900,h=200,p=35,step=items.length>1?(w-2*p)/(items.length-1):0;const points=items.map((x,i)=>[p+i*step,h-p-(x.sla/100)*(h-2*p)]);root.innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Evolução semanal do SLA"><line x1="${p}" y1="${h-p}" x2="${w-p}" y2="${h-p}"/><line x1="${p}" y1="${p}" x2="${p}" y2="${h-p}"/><polyline points="${points.map(p=>p.join(',')).join(' ')}"/>${points.map((pt,i)=>`<circle cx="${pt[0]}" cy="${pt[1]}" r="5"><title>${esc(items[i].name)}: ${items[i].sla.toFixed(1)}%</title></circle><text x="${pt[0]}" y="${h-10}" text-anchor="middle">${esc(items[i].name)}</text>`).join('')}</svg>`}
function render(){const rows=filtered(),total=rows.length,onTime=rows.filter(r=>r.on_time).length,late=total-onTime,sla=total?100*onTime/total:0;$('total').textContent=total.toLocaleString('pt-BR');$('ontime').textContent=onTime.toLocaleString('pt-BR');$('late').textContent=late.toLocaleString('pt-BR');$('sla').textContent=sla.toFixed(1)+'%';const branches=summarize(rows,'branch').sort((a,b)=>a.sla-b.sla);bars('branch-chart',branches,x=>x.sla,x=>x.name,true);const reasons=[...Counter(rows.filter(r=>!r.on_time).map(r=>r.delay_reason||'Não informado'))].map(([name,total])=>({name,total})).sort((a,b)=>b.total-a.total);bars('reason-chart',reasons,x=>x.total,x=>x.name);const weeks=summarize(rows,'week').sort((a,b)=>String(a.name).localeCompare(String(b.name),'pt-BR'));line(weeks);$('detail').innerHTML=branches.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.regional||'—')}</td><td>${x.total}</td><td>${x.on_time}</td><td>${x.late}</td><td>${x.sla.toFixed(1)}%</td></tr>`).join('');const worst=branches[0],top=reasons[0];const facts=[];facts.push(`A visão filtrada contém ${total.toLocaleString('pt-BR')} pedido(s) elegível(is) e SLA de ${sla.toFixed(1)}%.`);if(worst)facts.push(`${worst.name} apresenta o menor SLA no recorte: ${worst.sla.toFixed(1)}% em ${worst.total} pedido(s).`);if(top)facts.push(`${top.name} é o motivo mais frequente entre os atrasos: ${top.total} ocorrência(s).`);$('insights').innerHTML=facts.map(x=>`<li>${esc(x)}</li>`).join('');$('warning').textContent=DATA.disclaimer}
function Counter(values){const m=new Map;values.forEach(v=>m.set(v,(m.get(v)||0)+1));return m}
function exportCsv(){const rows=summarize(filtered(),'branch');const csv=['Filial;Regional;Pedidos;No prazo;Atrasados;SLA',...rows.map(x=>[x.name,x.regional,x.total,x.on_time,x.late,x.sla.toFixed(2)].map(v=>'"'+String(v).replaceAll('"','""')+'"').join(';'))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv'}));a.download='visao_sla.csv';a.click();URL.revokeObjectURL(a.href)}
fetch('/api/dashboard-data').then(r=>{if(!r.ok)throw Error('Falha ao ler os dados');return r.json()}).then(data=>{DATA=data;$('source').textContent=data.source.name;fillSelect('branch',unique(data.records,'branch'));fillSelect('regional',unique(data.records,'regional'));fillSelect('week',unique(data.records,'week'));['branch','regional','week'].forEach(id=>$(id).onchange=render);$('clear').onclick=()=>{['branch','regional','week'].forEach(id=>$(id).value='');render()};$('export').onclick=exportCsv;render()}).catch(e=>document.querySelector('.content').innerHTML='<p class="warning">'+esc(e.message)+'</p>');
'''


TEST_APP = '''import unittest

from app import app, dashboard_data


class DashboardTest(unittest.TestCase):
    def test_health_and_totals(self):
        client = app.test_client()
        self.assertEqual(client.get("/").status_code, 200)
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        data = dashboard_data()
        self.assertEqual(data["kpis"]["total"], len(data["records"]))
        self.assertEqual(data["kpis"]["total"], data["kpis"]["on_time"] + data["kpis"]["late"])
        expected = round(100 * data["kpis"]["on_time"] / data["kpis"]["total"], 2)
        self.assertEqual(data["kpis"]["sla_pct"], expected)


if __name__ == "__main__":
    unittest.main()
'''


class DashboardService:
    def __init__(self, logistics, files, store):
        self.logistics = logistics
        self.files = files
        self.store = store

    @staticmethod
    def _clean_text(value, fallback):
        if missing(value):
            return fallback
        return str(value).strip()[:160]

    @staticmethod
    def _bool_value(value):
        if missing(value):
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        key = str(value).strip().lower()
        if key in {'1', 'true', 'sim', 's', 'yes', 'y', 'ok', 'no prazo', 'dentro do prazo'}:
            return True
        if key in {'0', 'false', 'nao', 'não', 'n', 'no', 'atrasado', 'fora do prazo'}:
            return False
        return None

    @staticmethod
    def _date_value(value):
        if isinstance(value, datetime):
            return value
        if missing(value):
            return None
        text = str(value).strip()
        for pattern in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y', '%d/%m/%Y %H:%M:%S', '%d-%m-%Y'):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                pass
        return None

    def _prepare(self, project, payload):
        upload_id = str(payload.get('upload_id', ''))
        table, meta = self.logistics._read(project, upload_id)
        profile = self.logistics.latest_analysis(project, upload_id)
        mapping = dict(profile.get('mapping', {}))
        overrides = payload.get('mapping') or {}
        if not isinstance(overrides, dict):
            raise ValueError('Mapeamento de colunas inválido')
        for role, column in overrides.items():
            if role not in ROLE_ALIASES or column not in table.columns:
                raise ValueError('Mapeamento contém coluna ou papel inválido')
            mapping[role] = column
        if not mapping.get('order_id') or not mapping.get('branch'):
            raise ValueError('Confirme as colunas de pedido e filial antes de gerar o dashboard')
        if not mapping.get('on_time') and not (mapping.get('due_date') and mapping.get('ship_date')):
            raise ValueError('Confirme a coluna de SLA ou as datas de prazo e expedição')

        rows = list(table.rows)
        signatures = [tuple(json.dumps(row.get(column), ensure_ascii=False, sort_keys=True, default=str) for column in table.columns) for row in rows]
        exact_duplicates = sum(count - 1 for count in Counter(signatures).values() if count > 1)
        duplicate_rule = payload.get('duplicate_rule', 'reject')
        if exact_duplicates:
            if duplicate_rule not in ('drop_exact', 'first', 'last'):
                raise ValueError('A base tem linhas duplicadas. Escolha uma regra de duplicidade antes de continuar')
            chosen = {}
            iterable = zip(signatures, rows)
            for signature, row in iterable:
                if duplicate_rule == 'last' or signature not in chosen:
                    chosen[signature] = row
            rows = list(chosen.values())

        key_column = mapping['order_id']
        key_counts = Counter(str(row.get(key_column)) for row in rows if not missing(row.get(key_column)))
        if any(count > 1 for count in key_counts.values()):
            if duplicate_rule not in ('first', 'last'):
                raise ValueError('Há mais de uma linha por pedido. Confirme se deve prevalecer o primeiro ou o último registro')
            chosen = {}
            for row in rows:
                key = str(row.get(key_column))
                if duplicate_rule == 'last' or key not in chosen:
                    chosen[key] = row
            rows = list(chosen.values())

        records = []
        excluded = 0
        for row in rows:
            if mapping.get('on_time'):
                flag = self._bool_value(row.get(mapping['on_time']))
            else:
                due = self._date_value(row.get(mapping['due_date']))
                shipped = self._date_value(row.get(mapping['ship_date']))
                flag = shipped <= due if due and shipped else None
            if missing(row.get(key_column)) or missing(row.get(mapping['branch'])) or flag is None:
                excluded += 1
                continue
            week = self._clean_text(row.get(mapping.get('week')), 'Sem período') if mapping.get('week') else 'Sem período'
            if week == 'Sem período' and mapping.get('ship_date'):
                shipped = self._date_value(row.get(mapping['ship_date']))
                if shipped:
                    iso = shipped.isocalendar()
                    week = f'{iso.year}-S{iso.week:02d}'
            records.append({
                'order_id': self._clean_text(row.get(key_column), 'Sem chave'),
                'branch': self._clean_text(row.get(mapping['branch']), 'Não informado'),
                'regional': self._clean_text(row.get(mapping.get('regional')), 'Não informado') if mapping.get('regional') else 'Não informado',
                'week': week,
                'on_time': bool(flag),
                'delay_reason': self._clean_text(row.get(mapping.get('delay_reason')), 'Não informado') if mapping.get('delay_reason') and not flag else '',
            })
        if not records:
            raise ValueError('Nenhum pedido elegível restou após validar chave, filial e regra de prazo')
        total = len(records)
        on_time = sum(1 for item in records if item['on_time'])
        data = {
            'schema_version': 1, 'generated_at': now(),
            'title': str(payload.get('title') or 'Painel de SLA de expedição')[:180],
            'objective': str(payload.get('objective') or 'Monitorar o cumprimento do SLA por filial e período')[:1000],
            'source': {'name': meta['name'], 'sha256': meta['sha256'], 'rows_original': len(table),
                       'rows_eligible': total, 'rows_excluded': excluded},
            'formula': 'pedidos únicos no prazo / pedidos únicos elegíveis × 100',
            'mapping': mapping,
            'kpis': {'total': total, 'on_time': on_time, 'late': total - on_time,
                     'sla_pct': round(100 * on_time / total, 2)},
            'records': records,
            'disclaimer': 'Resultados descritivos da base selecionada. Hipóteses e recomendações exigem validação operacional.',
            'quality': {'exact_duplicates_found': exact_duplicates, 'duplicate_rule': duplicate_rule,
                        'excluded_rows': excluded},
        }
        return data, meta

    def _propose(self, project, job, path, content):
        target = self.files.path(project, path)
        base = self.files.read(project, path)['hash'] if target.exists() else None
        proposal_id = uuid.uuid4().hex
        self.store.execute('INSERT INTO proposals VALUES (?,?,?,?,?,?,?)',
                           (proposal_id, project, job, path, content, base, 'pending'))
        return proposal_id

    def generate(self, project, payload, job, emit, cancel):
        if payload.get('rules_confirmed') is not True or payload.get('confirm') is not True:
            raise PermissionError('Confirme a regra de SLA e a geração das propostas')
        stages = [
            ('logistics', 'Validar base, mapeamento e fórmula'),
            ('coordinator', 'Definir escopo do dashboard'),
            ('backend', 'Preparar API e dados agregáveis'),
            ('frontend', 'Construir filtros, KPIs e visualizações'),
            ('testing', 'Criar validações de integridade'),
            ('reviewer', 'Revisar rastreabilidade e segurança'),
        ]
        for position, (agent, detail) in enumerate(stages):
            task_id = uuid.uuid4().hex
            self.store.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?)',
                               (task_id, job, agent, position, 'running', ''))
            emit('agent', {'agent': agent, 'status': 'ANALISANDO' if agent == 'logistics' else 'TRABALHANDO', 'task': detail})
            if cancel.is_set():
                raise InterruptedError('Geração interrompida')
            if position == 0:
                data, meta = self._prepare(project, payload)
            self.store.execute("UPDATE tasks SET status='completed',result=? WHERE id=?",
                               (detail + ' concluído', task_id))
        data_text = json.dumps(data, ensure_ascii=False, indent=2)
        files = {
            'app.py': APP_PY,
            'templates/index.html': INDEX_HTML,
            'static/dashboard.css': DASHBOARD_CSS + '\n',
            'static/dashboard.js': DASHBOARD_JS + '\n',
            'data/logistics_sla.json': data_text + '\n',
            'tests/test_dashboard.py': TEST_APP,
            'requirements.txt': 'Flask>=3.1,<4\n',
        }
        proposals = [self._propose(project, job, path, content) for path, content in files.items()]
        dashboard_id = uuid.uuid4().hex
        result = {
            'dashboard_id': dashboard_id,
            'proposal_ids': proposals,
            'files': list(files),
            'kpis': data['kpis'],
            'quality': data['quality'],
            'source_sha256': meta['sha256'],
            'validation_status': 'aguardando aprovação e teste no navegador',
        }
        with Session(self.logistics.engine) as db:
            db.add(LogisticsDashboard(id=dashboard_id, project=project, upload_id=payload['upload_id'],
                                      title=data['title'], objective=data['objective'], status='proposed',
                                      result_json=json.dumps(result, ensure_ascii=False)))
            db.commit()
        self.logistics._activity(project, 'dashboard', f'Dashboard de SLA proposto com {len(proposals)} arquivos; fonte {meta["name"]}')
        emit('dashboard', result)
        return result
