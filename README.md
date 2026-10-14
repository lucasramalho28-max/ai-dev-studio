# AI DEV STUDIO — MVP local para Windows

Plataforma Flask com editor de código, oito agentes sequenciais, memória SQLite por projeto e gerenciamento real do Ollama. O aplicativo escuta somente em `127.0.0.1` e não depende de serviços de hospedagem.

## Iniciar

1. Abra esta pasta e execute `instalar.bat`. O assistente verifica Python 3.11+, solicita autorização e prepara `.venv`, dependências e Chromium do Playwright. Não instala Python nem Ollama silenciosamente.
2. Execute `iniciar.bat`.
3. Abra **http://127.0.0.1:5050**. Mantenha a janela do servidor aberta; Ctrl+C encerra o Studio.
4. Entre em **IA / Gerenciador de inteligência artificial**. Clique em **Instalar Ollama** e confirme, se necessário. Caso winget não esteja disponível, use o link oficial da tela e execute o instalador manualmente. Eventuais solicitações do Windows devem ser respondidas pelo usuário.
5. Use **Iniciar serviço** se o Ollama não responder. O Studio só reinicia processos do Ollama que ele próprio iniciou; uma instância aberta pelo Windows deve ser encerrada pelo ícone da bandeja.
6. Baixe `qwen2.5-coder:3b` para código e, para o agente logístico, `qwen3.5:4b`. O analista usa o Qwen3.5 quando disponível e recorre ao modelo de código instalado quando necessário.
7. Crie um projeto, converse com um agente ou marque **Acionar equipe completa**. Revise as propostas em **Alterações** e aprove os arquivos desejados.
8. Para análise operacional, abra **Logística**, carregue CSV, XLSX, JSON ou TXT, revise o diagnóstico e o mapeamento, confirme a fórmula e gere o dashboard. Os arquivos aparecem como propostas para aprovação.
9. Edite e salve os arquivos. Clique em **Executar**, confirme a execução e abra **Preview**. Use **Parar** ao terminar.
10. Em **Ajustes**, prepare o ambiente virtual do projeto e execute seus testes. Na prévia, **Inspecionar / screenshot** executa o Playwright real.

O ambiente Python do próprio Studio foi preparado nesta entrega. Se iniciar.bat já funcionar, não é necessário reinstalar. O Playwright pode usar o Edge existente quando o Chromium gerenciado não estiver instalado.

## Interface móvel

Em telas de até 850 px, o Studio apresenta os painéis **Arquivos**, **Área de trabalho**, **Assistente** e **Logs** separadamente. A barra inferior dá acesso a Editor, Agentes, Logística, IA e Ajustes. Mensagens e edições permanecem ao alternar painéis; use **Salvar** para gravar os arquivos. A adaptação é automática ao abrir a mesma página em uma tela menor.

## Aprovação automática

O botão do chat muda de **Enviar** para **Interromper** enquanto o pedido está em execução. Após solicitar o cancelamento, mostra **Interrompendo…** até o encerramento e então volta a **Enviar**. Enter envia quando o chat está livre; Shift+Enter insere uma linha.

No assistente, marque **Autoaprovar arquivos dos novos pedidos** antes de enviar. A opção começa desativada e salva as propostas validadas desses pedidos enquanto a guia estiver aberta. Propostas antigas continuam disponíveis em **Alterações** para revisão manual. Edições não salvas ou conflitos de versão pausam a aplicação; o chat informa o resultado. Desmarcar cancela as autoaprovações pendentes desse projeto. Autorizações de pedidos em andamento são recuperadas ao recarregar a mesma guia.

A opção aprova arquivos. Execução de código, testes, instalações e downloads continuam usando suas confirmações próprias.

## Organograma dos agentes

Na barra **Código · Preview · Alterações · Organograma**, abra **Organograma** para ver a estrutura da equipe e a sequência do trabalho. Clique em um agente ou etapa para consultar tarefa, modelo, atividade recente e origem do encaminhamento. **Acompanhar agente ativo** volta a seguir automaticamente a etapa em execução. As conexões indicam a próxima etapa ou uma passagem confirmada pelo servidor.

O seletor permite consultar as dez execuções recentes do projeto, incluindo fluxos concluídos após recarregar a página. Etapas repetidas do Coordenador e da Logística aparecem separadamente. Consultas com um agente e geração local de dashboards exibem o fluxo correspondente.

## Implementado

O assistente exibe **atividade em tempo real** dentro do chat: agente ativo, modelo, etapa atual, fila de etapas, conclusões e falhas. O painel usa eventos persistidos do servidor e recupera execuções ainda ativas ao recarregar. A equipe trabalha em sequência; consultas e bases prontas podem usar apenas um agente. A geração logística determinística aparece como gerador local, sem indicar inferência ou testes executados.

- Flask modular; SQLite com projetos, conversas, tarefas, eventos, configurações, propostas e resumo de contexto.
- Detecção independente do executável e do serviço Ollama; instalação winget do pacote `Ollama.Ollama`, log real, verificação posterior e fallback para o site oficial.
- APIs Ollama `/api/tags`, `/api/pull`, `/api/chat`, `/api/delete` e `/api/version`. Download e chat com streaming NDJSON retransmitido por SSE. Progresso por camada, bytes e velocidade observada quando disponíveis; exclusão verificada; teste do modelo.
- Modelos sugeridos Qwen2.5 Coder 1.5B/3B e Qwen3.5 4B; nome livre validado; seleção global e por agente. Confirmação antes de cada download.
- Oito identidades com prompts próprios, incluindo o **Analista de Inteligência Logística**. Histórico separado por projeto/agente, geração de propostas de arquivos completos, tarefas ordenadas persistidas e uma fila de inferência global.
- Equipe completa: coordenador → logística → banco → backend → frontend → testes → navegador → revisor → logística → coordenador. As etapas usam o contexto e as propostas anteriores; não aplicam arquivos sem revisão.
- Módulo logístico local com upload seguro de CSV, XLSX, JSON e TXT, limite de 25 MB/100 mil linhas, perfil de tipos, ausências, duplicidades, mapeamento editável, catálogo de indicadores e memória aprovada por projeto.
- Geração determinística e rastreável de dashboard Flask de SLA com filtros por filial/regional/semana, KPIs, gráficos locais em SVG/CSS, detalhamento, exportação CSV e testes. A base original permanece imutável e os arquivos gerados são propostas com hash de versão.
- Persistência logística em modelos SQLAlchemy sobre SQLite. O runtime força o modo Python puro do SQLAlchemy para compatibilidade com a política de controle de aplicativos deste Windows.
- Editor Monaco 0.52.2, abas, arquivos em subpastas, criação/leitura/escrita/renomeação/exclusão, realce e diff das propostas. Editor de texto local quando o CDN não responde.
- Hash de versão para bloquear sobrescritas concorrentes. Propostas não são aplicadas sobre buffers não salvos pela interface. Alterações no disco exigem recarregamento antes de sobrescrever.
- Execução Flask em porta disponível, URL, logs, readiness HTTP, parada da árvore de processos no Windows, reinício e ambiente virtual por projeto com instalação controlada de Flask.
- Execução real de unittest e Playwright mediante confirmação. O navegador aceita `click` e `fill` por seletor, captura DOM, erros JavaScript, respostas HTTP e screenshot. A navegação de rede fica restrita à origem local do processo gerenciado.
- Criação de agentes personalizados com aprovação e ferramenta limitada a propor arquivos.
- Recuperação identifica jobs interrompidos após reinício. O painel de tarefas oferece reexecutar a última conversa interrompida; reexecutar começa o fluxo novamente usando a memória existente.
- Interface escura em português, painéis redimensionáveis, logs, cartões de agentes e preview com abertura externa.

## Consultas e redução de respostas inventadas

- O chat oferece **Automático**, **Só perguntar** e **Pedir alteração**. No automático, pedidos explícitos de implementação geram propostas; mensagens ambíguas são consultas. Perguntas não acionam a equipe completa nem criam propostas, mesmo com a equipe marcada. Use o seletor para corrigir a classificação.
- Consultas de login e senha usam análise estática local, sem chamar o modelo. O Studio identifica o fluxo Flask/SQLite de cadastro e a verificação por hash quando reconhecidos, citando arquivo e linha. Não consulta contas no banco em execução, não recupera senhas e não apresenta exemplos de testes como credenciais ativas. Outros padrões de autenticação podem exigir inspeção manual.
- A recuperação pesquisa nomes e conteúdo, incluindo trechos além do início dos arquivos. Cada trecho tem arquivo, linha e indicação de arquivo aplicado, exemplo/teste ou proposta não aplicada. A análise se limita a 250 arquivos de texto, 256 KB por arquivo e 4 MB por consulta.
- Consultas ao modelo usam saída JSON estruturada, com explicação e referências restritas às linhas fornecidas. As respostas são verificadas antes de aparecer: blocos de proposta são removidos e referências ausentes ou fora dos trechos enviados geram uma resposta de insuficiência de evidência. Conferir referências não comprova automaticamente a interpretação do modelo.
- O orçamento conjunto inclui instruções, pedido, evidências, histórico e resposta. A estimativa usa bytes UTF-8 e margem de segurança, não o tokenizer exato do modelo. O contexto permanece em 4.096 tokens; consultas têm até 768 tokens de saída e alterações até 2.048. Pedidos grandes devem ser divididos; respostas que informam truncamento não criam propostas.
- A memória `memory_v2` guarda somente pedidos e caminhos propostos, sem copiar conclusões da IA. Resumos antigos permanecem no banco para preservação dos dados, mas não são reutilizados como contexto. O histórico de conversa é tratado como informação não verificada.

## Geração e teste de projetos

- Pedidos de cadastro/login com dashboard de estoque fictício, em projeto ainda vazio, podem usar a base local `starters/stock_portal`. O chat identifica explicitamente a origem **sem inferência** e cria propostas para aprovação. A base não substitui projetos personalizados e não é usada em consultas. Pedir "sem base pronta" mantém a geração livre.
- A base contém cadastro, sessão, hashes de senha, proteção de formulários, logout, 72 produtos, 216 posições de estoque, três centros, 626 movimentos fictícios, gráficos, filtros, paginação, CSV e testes. Os saldos reconciliam com as movimentações. A conta demo é indicada no login e no README; usuário/senha solicitados no pedido são respeitados quando reconhecidos.
- Geração livre usa JSON estruturado com `summary`, `files` e `edits`. Edições pequenas usam trechos `old`/`new`: o original precisa existir exatamente uma vez. O resultado completo continua sendo uma proposta com controle de versão; nada é aplicado automaticamente. Blocos Markdown legados permanecem compatíveis com o parser.
- Antes de propor ou aplicar, o Studio verifica sintaxe Python/Jinja, dependências disponíveis, templates referenciados e alguns padrões inválidos de autenticação (comparação direta, hashes rápidos e chave de sessão fixa). Isso é análise estática, não execução nem uma auditoria completa de segurança. Respostas sem arquivos/edições deixam de ser apresentadas como alterações concluídas.
- O chat apresenta um resumo construído a partir dos arquivos efetivamente propostos. A saída original do modelo fica em eventos `model_output` para diagnóstico; afirmações livres do modelo não substituem resultados de ferramentas.
- A inspeção real de navegador aceita `click`, `fill`, `select` e `expect_text`, além de viewport de computador/celular. Registra status da navegação final, erros HTTP/JavaScript e largura da página para detectar transbordamento horizontal.

Os pedidos enviados como usuário e os resultados reais deste experimento ficam em `data/qa/atlas-user-flow.json`; as falhas iniciais são preservadas para comparação com os testes após as correções.

## Limites desta versão

- O coordenador usa uma sequência fixa de especialidades. Ainda não há seleção dinâmica de agentes, dependências em grafo, ciclos automáticos de correção nem retomada exata de cada etapa.
- Na conversa, os agentes Testes e Navegador fazem análise e propõem arquivos. Os botões **Executar testes** e **Inspecionar / screenshot** executam as ferramentas reais após aprovação. Não há execução automática de código gerado durante a conversa. Os status de conversa desses agentes são REVISANDO, não um resultado fictício de teste.
- As propostas são aprovadas arquivo a arquivo. Não há aplicação atômica de vários arquivos nem rollback completo. Faça backup de projetos importantes.
- A memória guarda pedidos e caminhos de propostas, e a recuperação usa busca lexical por nomes e conteúdo; não há banco vetorial ou recuperação semântica. Regras de evidência reduzem erros, mas não garantem que toda resposta do modelo esteja correta.
- Sem integração de nuvem nesta entrega. Nenhuma chave é solicitada ou armazenada. A arquitetura admite outro adaptador de inferência, mas o backend atual utiliza somente Ollama.
- Monaco e fontes usam CDN; offline há fallback de texto. Para Monaco totalmente offline, será necessário empacotar os assets `vs/` localmente.
- O terminal é um visualizador de logs com ações controladas; não é um shell interativo. Dependências extras do projeto precisam ser revisadas e instaladas manualmente no ambiente correspondente.
- Criar pastas funciona ao criar arquivos com subdiretórios. Não há renomeação/exclusão de diretórios inteiros ou importação de projetos externos nesta versão.
- Processos de instalação e criação de ambiente não são interrompidos em um ponto arbitrário. Cancelar chat/download solicita interrupção no próximo bloco de rede (timeout máximo de leitura de 120 segundos); o Ollama pode manter dados parciais reutilizáveis.
- O daemon Ollama iniciado pelo Studio permanece disponível ao fechar o Studio. Projetos Flask gerenciados são encerrados na saída normal; em encerramento forçado do Windows, processos podem exigir parada manual.

## Segurança e hardware

Os caminhos de arquivos são restritos a `workspace/<id do projeto>`; caminhos absolutos, traversal, nomes reservados do Windows, arquivos ocultos, links simbólicos e junctions são bloqueados. Mutações exigem token da sessão, origem compatível e Host local. Não há CORS aberto. O processo web não deve ser exposto na rede.

Respostas da IA não executam shell. Elas geram propostas; executar Flask/testes exige aprovação explícita. **Um ambiente virtual não isola código malicioso:** aplicações Python executadas possuem os privilégios do usuário Windows. Revise código antes de permitir execução. Para projetos não confiáveis, use VM ou conta Windows restrita. O navegador bloqueia requisições fora da origem local e downloads; isso não isola o backend Python da aplicação.

O subprocesso do projeto não herda variáveis cujos nomes contenham KEY, TOKEN, SECRET ou PASSWORD. Isso reduz exposição acidental, mas não substitui isolamento do sistema operacional. Não coloque segredos em arquivos enviados como contexto aos agentes.

Para GTX 1060 de 6 GB / RAM de 16 GB, use Qwen3.5 4B para logística e Qwen2.5 Coder 3B para código, um agente por vez e contexto 4096. A fila limita inferências iniciadas pelo Studio; outros clientes Ollama continuam independentes. Ao iniciar seu próprio daemon, o Studio define `OLLAMA_NUM_PARALLEL=1` e `OLLAMA_MAX_LOADED_MODELS=1`. Nesta máquina, ambos responderam com inferência real na GPU após a instalação do driver NVIDIA 582.78; consulte os arquivos de validação para os valores observados.

## Estrutura

```text
app.py                      fábrica Flask e endpoints JSON/SSE
config.py                   diretórios, porta e modelo padrão
agents/registry.py          identidades e prompts
core/store.py               SQLite e histórico
core/jobs.py                jobs, cancelamento e fila sequencial
core/context_manager.py    contexto seletivo e memória limitada
core/orchestrator.py        execução dos agentes e propostas
services/file_service.py   arquivos e controle de versões
services/ollama_service.py cliente HTTP/NDJSON real
services/ollama_installer.py winget e daemon
services/execution_service.py Flask, venv e unittest
services/browser_service.py Playwright e screenshots
services/logistics_service.py leitura, perfil e memória logística
services/dashboard_service.py cálculo rastreável e propostas de dashboard
models/logistics.py          modelos SQLAlchemy isolados por projeto
routes/logistics_routes.py   API do agente logístico
templates/index.html        interface
static/                     CSS e JavaScript
tests/                      testes unitários, integração e QA de navegador
data/                       banco e evidências de QA (gerados)
workspace/                  projetos (gerados)
instalar.bat / iniciar.bat   assistentes Windows
```

## Testes

Na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

A suíte `test_studio.py` verifica os serviços com mocks para Ollama/winget indisponíveis, além de executar um projeto Flask e seus testes reais. `test_logistics.py` cobre CSV, XLSX, JSON, isolamento por projeto, memória, duplicidades, geração e aplicação das propostas, testes do dashboard e abertura real no Playwright. `test_browser_real.py` valida o fluxo completo do Studio. Screenshots e relatório são gravados em `data/qa/`.

Consulte `VALIDACAO.md` e `VALIDACAO_LOGISTICA.md` para os resultados desta entrega.

## Configuração e recuperação

`STUDIO_PORT` altera a porta padrão antes de iniciar. `.env.example` documenta as variáveis; o aplicativo não carrega `.env` automaticamente. Dados ficam em `data/studio.sqlite3`; faça backup junto da pasta `workspace`. Não rode múltiplas instâncias do Studio no mesmo banco, porque a recuperação identifica jobs ativos como interrompidos ao iniciar.

Se o Ollama não responder, use Verificar e Iniciar serviço. Sem winget, baixe em https://ollama.com/download/windows. Se o Playwright não encontrar navegador, rode novamente instalar.bat e autorize a preparação do Chromium. Se houver erro de importação DLL no Python, recrie o ambiente local ou utilize Python 3.12/3.13 de 64 bits.

Referências oficiais consultadas: [Ollama Windows](https://docs.ollama.com/windows), [API chat](https://docs.ollama.com/api/chat), [API pull](https://docs.ollama.com/api/pull), [pacote winget Microsoft](https://github.com/microsoft/winget-pkgs/tree/master/manifests/o/Ollama/Ollama), [Playwright Python](https://playwright.dev/python/docs/browsers).
