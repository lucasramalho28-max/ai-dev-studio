'use strict';

class AgentOrganogram {
    constructor(root, agents) {
        this.root=root;this.agents=agents;this.project='';this.jobs=[];
        this.selectedJob='';this.selectedTask='';this.selectedAgent='';this.pinnedJob=false;this.follow=true;
        // Static markup; all project/event text below is inserted through textContent.
        root.innerHTML='<div class="org-heading"><div><div class="eyebrow">ORQUESTRAÇÃO AO VIVO</div><h2>Organograma dos agentes</h2></div><span class="org-badge" id="org-status" role="status">Pronto</span></div><p class="muted">Selecione um agente para acompanhar sua tarefa. As setas mostram a passagem entre etapas da execução.</p><div class="org-controls"><label for="org-execution">Execução<select id="org-execution"></select></label><button id="org-follow" type="button">Acompanhar agente ativo</button></div><div class="org-now" role="status"></div><details class="org-team-section" open><summary>Estrutura da equipe</summary><div class="org-team"></div></details><div class="org-workspace"><aside class="org-detail" aria-label="Detalhes da etapa"></aside><section><h3>Fluxo do trabalho</h3><ol class="org-flow" aria-label="Etapas e passagens entre agentes"></ol></section></div>';
        this.select=root.querySelector('#org-execution');
        this.select.onchange=()=>{this.selectedJob=this.select.value;this.selectedTask='';this.pinnedJob=true;this.follow=true;this.render()};
        root.querySelector('#org-follow').onclick=()=>{this.follow=true;this.render()};
        this.render();
    }
    element(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node}
    name(id){return id==='generator'?'Gerador local de dashboards':this.agents().find(a=>a.id===id)?.name||id}
    status(value){return {idle:'Disponível',queued:'Na fila',running:'Em trabalho',completed:'Concluído',cancelled:'Interrompido',interrupted:'Interrompido',error:'Falhou',skipped:'Não executado'}[value]||value}
    update(project,jobs){
        if(this.project!==project){this.project=project;this.selectedJob='';this.selectedTask='';this.pinnedJob=false;this.follow=true}
        this.jobs=jobs.filter(j=>j.project===project&&['chat','logistics_dashboard'].includes(j.kind));
        this.render();
    }
    render(){
        const sorted=[...this.jobs].sort((a,b)=>String(b.created||b.id).localeCompare(String(a.created||a.id)));
        let job=sorted.find(j=>j.id===this.selectedJob);
        if(!job||!this.pinnedJob){job=sorted.find(j=>j.status==='running')||sorted.find(j=>j.status==='queued')||sorted[0];this.selectedJob=job?.id||''}
        const optionKey=sorted.map(j=>j.id+j.status).join('|');
        if(optionKey!==this.optionKey){
            this.optionKey=optionKey;this.select.replaceChildren();
            if(!sorted.length)this.select.append(new Option('Nenhuma execução neste projeto',''));
            sorted.forEach(j=>{const date=new Date(j.created);const label=Number.isNaN(date.getTime())?j.id.slice(0,8):date.toLocaleString('pt-BR');this.select.append(new Option(`${label} · ${this.status(j.status)}`,j.id))});
        }
        this.select.value=this.selectedJob;this.select.disabled=!sorted.length;
        const badge=this.root.querySelector('#org-status');badge.textContent=job?this.status(job.status):'Pronto';badge.dataset.status=job?.status||'idle';
        const tasks=job?.tasks||[],active=tasks.find(t=>t.status==='running');
        this.root.querySelector('.org-now').textContent=active?(active.activity||`${this.name(active.agent)}: ${active.detail||'Executando a etapa.'}`):job?job.detail:'Envie um pedido para acompanhar o fluxo. Marque a equipe completa no chat para envolver as especialidades.';
        if(this.follow){this.selectedAgent='';this.selectedTask=active?.id||tasks.find(t=>t.status==='queued')?.id||tasks.at(-1)?.id||''}
        const selected=tasks.find(t=>t.id===this.selectedTask);
        this.renderTeam(tasks);
        const flow=this.root.querySelector('.org-flow');flow.replaceChildren();
        if(!tasks.length)flow.append(this.element('li','org-empty',job?'Aguardando o servidor informar o plano de execução.':'Nenhum fluxo iniciado. A equipe acima está disponível.'));
        tasks.forEach((task,index)=>{
            const item=this.element('li','org-step');
            if(index){
                const previous=tasks[index-1];
                const handoff=(job.handoffs||[]).find(h=>h.from_task===previous.id&&h.to_task===task.id);
                const edge=this.element('div','org-transfer');edge.dataset.state=handoff?(task.status==='running'?'active':'confirmed'):'planned';
                edge.append(this.element('span','org-arrow','↓'),this.element('span','',`${this.name(previous.agent)} → ${this.name(task.agent)} · ${handoff?'Passagem confirmada':'Passagem não registrada'}`));
                if(!handoff&&task.status==='queued')edge.lastChild.textContent=`Próxima etapa · ${this.name(task.agent)}`;
                item.append(edge);
            }
            const card=this.element('button','org-node');card.type='button';card.dataset.task=task.id;card.dataset.status=task.status;card.setAttribute('aria-pressed',String(selected?.id===task.id));
            const title=this.element('div','org-node-heading');title.append(this.element('span','org-step-number',String(index+1).padStart(2,'0')),this.element('strong','',this.name(task.agent)),this.element('span','org-badge',this.status(task.status)));card.append(title);
            card.append(this.element('p','org-action',task.activity||task.detail||'Aguardando sua vez.'));
            if(task.model)card.append(this.element('small','org-model',task.model));
            card.onclick=()=>{this.follow=false;this.selectedAgent='';this.selectedTask=task.id;this.render()};
            item.append(card);flow.append(item);
        });
        this.renderDetail(selected,job);
    }
    renderTeam(tasks){
        const team=this.root.querySelector('.org-team');team.replaceChildren();
        const coordinator=this.agents().find(a=>a.id==='coordinator');
        const leaders=this.element('div','org-leader'),members=this.element('div','org-members');
        for(const agent of this.agents()){
            const matches=tasks.filter(t=>t.agent===agent.id);
            const task=matches.find(t=>t.status==='running')||matches.find(t=>t.status==='error')||matches.find(t=>t.status==='queued')||matches.at(-1);
            const card=this.element('button','org-agent');card.type='button';card.dataset.agent=agent.id;card.dataset.status=task?.status||'idle';
            card.append(this.element('strong','',agent.name),this.element('small','',agent.specialty),this.element('span','org-agent-state',this.status(task?.status||'idle')));
            card.onclick=()=>{this.follow=false;this.selectedTask=task?.id||'';this.selectedAgent=task?'':agent.id;this.render()};
            (agent.id===coordinator?.id?leaders:members).append(card);
        }
        team.append(leaders,members);
    }
    showAgent(agent){const detail=this.root.querySelector('.org-detail');detail.replaceChildren(this.element('div','eyebrow','AGENTE'),this.element('h3','',agent.name),this.element('p','muted',agent.specialty),this.element('p','', 'Sem tarefa atribuída nesta execução.'))}
    renderDetail(task,job){
        const detail=this.root.querySelector('.org-detail');detail.replaceChildren();
        if(!task){const agent=this.agents().find(a=>a.id===this.selectedAgent);if(agent){this.showAgent(agent);return}detail.append(this.element('h3','','Detalhes da etapa'),this.element('p','muted','Clique em um agente ou em uma etapa do fluxo.'));return}
        detail.append(this.element('div','eyebrow','ETAPA SELECIONADA'),this.element('h3','',this.name(task.agent)),this.element('p','org-detail-status',this.status(task.status)),this.element('p','',task.activity||task.detail||'Aguardando início.'));
        if(task.model)detail.append(this.element('p','muted',`Modelo: ${task.model}`));
        const incoming=(job.handoffs||[]).find(h=>h.to_task===task.id);
        if(incoming){detail.append(this.element('h4','','Recebido de '+this.name(incoming.from_agent)),this.element('p','muted',incoming.detail));if(incoming.files_available?.length)detail.append(this.element('p','muted','Arquivos disponíveis: '+incoming.files_available.join(', ')))}
        if(task.files?.length)detail.append(this.element('p','muted','Arquivos propostos disponíveis: '+task.files.join(', ')));
        if(task.error)detail.append(this.element('p','org-error',task.error));
        if(task.logs?.length){detail.append(this.element('h4','','Atividade recente'));const list=this.element('ul','org-task-logs');task.logs.forEach(log=>list.append(this.element('li','',log)));detail.append(list)}
    }
}
