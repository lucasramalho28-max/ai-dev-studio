'use strict';

// Only server events change execution state; token content is never treated as status.
class ExecutionActivity {
    constructor(anchor, agents) {
        this.jobs = new Map();
        this.project = '';
        this.agents = agents;
        this.root = document.createElement('section');
        this.root.className = 'execution-feed';
        this.root.setAttribute('aria-label', 'Atividade das execuções');
        this.root.hidden = true;
        anchor.before(this.root);
    }
    selectProject(project) { this.project = project; this.render(); }
    track(id, kind, project) {
        if (!this.jobs.has(id)) this.jobs.set(id, {id, kind, project, status:'queued', tasks:[], logs:[], detail:'Aguardando processamento.'});
        this.render();
    }
    update(id, type, data) {
        const job = this.jobs.get(id);
        if (!job) return;
        if (type === 'status') job.status = data.status;
        if (type === 'plan') job.tasks = data.tasks.map(task => ({...task, status:'queued'}));
        if (type === 'agent') {
            let task = job.tasks.find(task => task.id === data.task_id);
            if (!task) {
                task = {id:data.task_id || data.agent, agent:data.agent};
                job.tasks.push(task);
            }
            const status = data.status === 'CONCLUÍDO' ? 'completed' : data.status === 'ERRO' ? 'error' : data.status === 'INTERROMPIDO' ? 'cancelled' : 'running';
            Object.assign(task, {status, label:data.status, model:data.model || task.model, detail:data.task || task.detail});
            if (status === 'running') job.detail = `${this.agentName(data.agent)}: ${data.status.toLowerCase()}`;
        }
        if (type === 'log') {
            job.logs.push(String(data.text));
            job.logs = job.logs.slice(-8);
            job.detail = String(data.text);
        }
        if (type === 'progress') job.detail = data.status || 'Processando…';
        if (type === 'proposals') job.detail = `${(data.files || []).length} arquivo(s) proposto(s), aguardando aprovação.`;
        if (type === 'test') job.detail = data.exit_code === 0 ? 'Testes concluídos com sucesso.' : 'Testes encerrados com falha.';
        if (type === 'browser') job.detail = 'Inspeção do navegador concluída; confira o relatório.';
        if (type === 'done' || type === 'error') {
            job.status = type === 'error' ? data.status || 'error' : data.status;
            if (type === 'error') job.detail = data.message;
            if (job.status === 'cancelled') job.detail = 'Execução interrompida.';
            for (const task of job.tasks) {
                if (task.status === 'queued') task.status = 'skipped';
                else if (task.status === 'running') task.status = job.status === 'completed' ? 'completed' : job.status;
            }
        }
        if (type === 'connection') job.connection = data.text;
        if (type === 'status' || type === 'agent' || type === 'done') job.connection = '';
        this.render();
    }
    agentName(id) { return id === 'generator' ? 'Gerador local de dashboards' : this.agents().find(agent => agent.id === id)?.name || id; }
    render() {
        const jobs = [...this.jobs.values()].filter(job => job.project === this.project);
        const visible = jobs.filter(job => ['queued','running'].includes(job.status)).concat(jobs.filter(job => !['queued','running'].includes(job.status)).slice(-2));
        this.root.replaceChildren();
        this.root.hidden = !visible.length;
        const statuses = {queued:'Na fila', running:'Em andamento', completed:'Concluída', error:'Falhou', cancelled:'Interrompida', skipped:'Não executada'};
        const kinds = {chat:'Pedido aos agentes', logistics_dashboard:'Dashboard logístico', tests:'Testes', test:'Testes', browser:'Inspeção do navegador', venv:'Ambiente virtual', pull:'Download de modelo', install:'Instalação', service:'Serviço Ollama', model_test:'Teste do modelo'};
        for (const job of visible) {
            const card = document.createElement('details');
            card.className = 'execution-card'; card.dataset.job = job.id; card.dataset.status = job.status;
            card.open = ['queued','running','error'].includes(job.status);
            const summary = document.createElement('summary');
            summary.textContent = `${kinds[job.kind] || job.kind} · ${statuses[job.status] || job.status}`;
            card.append(summary);
            const current = document.createElement('p'); current.className = 'execution-current'; current.setAttribute('role','status'); current.textContent = job.connection || job.detail;
            card.append(current);
            if (job.tasks.length) {
                const list = document.createElement('ol'); list.className = 'execution-tasks';
                for (const task of job.tasks) {
                    const item = document.createElement('li'); item.dataset.status = task.status;
                    const label = document.createElement('strong'); label.textContent = `${this.agentName(task.agent)} · ${statuses[task.status] || task.status}`;
                    item.append(label);
                    if (task.detail || task.model) { const detail = document.createElement('small'); detail.textContent = [task.detail,task.model].filter(Boolean).join(' · '); item.append(detail); }
                    list.append(item);
                }
                card.append(list);
            }
            if (job.logs.length) { const logs = document.createElement('div'); logs.className = 'execution-logs'; job.logs.forEach(text => {const line = document.createElement('p'); line.textContent = text; logs.append(line);}); card.append(logs); }
            this.root.append(card);
        }
    }
}
