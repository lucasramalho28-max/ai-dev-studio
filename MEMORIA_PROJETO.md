# Memória do projeto — AI DEV STUDIO

Última atualização: **14/10/2026**, fuso America/Cuiaba.

## Finalidade e uso desta memória

Este arquivo mantém a continuidade entre sessões que tenham acesso a este repositório. `AGENTS.md` orienta sua leitura e atualização. Não é memória global da conta nem garantia de contexto em conversas sem acesso aos arquivos.

O usuário pediu revisão da coerência dos projetos feitos pela IA, código desnecessário e senhas não informadas. Depois pediu uma memória para acompanhar o que foi feito, o que foi concluído e o contexto do projeto. Até este momento, foi feita auditoria; as correções identificadas não foram implementadas.

## Contexto e arquitetura

- Workspace: `C:/Users/luas/Desktop/ia Lucas/ai_dev_studio`, Windows/PowerShell.
- Produto: Studio Flask para criar e editar projetos, conversar com agentes locais via Ollama, revisar propostas de arquivos e executar aplicações/testes/inspeção de navegador.
- Persistência: `data/studio.sqlite3`; projetos gerados em `workspace/<id>`; estado logístico adicional em `data/logistics` e tabelas SQLAlchemy no mesmo banco.
- Entrada: `app.py`; configuração: `config.py`; instalação/início: `instalar.bat` e `iniciar.bat`. Porta padrão 5050.
- Componentes: `agents/registry.py` (prompts), `core/orchestrator.py` (fluxos), `core/jobs.py` (fila), `core/context_manager.py` (evidências/contexto), `core/response_policy.py` (consultas/credenciais), `core/proposal_validation.py` (validação estática).
- Serviços: arquivos, Ollama/instalador, execução Python, Playwright, logística e geração determinística de dashboards. Interface em `templates/` e `static/`.
- Navegação atual: **Editor, Agentes, IA e Ajustes** no desktop e no celular. Aba dedicada de Logística removida por decisão do usuário; agente especialista e APIs existentes continuam disponíveis. Selecionar projeto não carrega dados logísticos automaticamente.
- Dependências declaradas: Flask, Playwright, openpyxl e SQLAlchemy. Inferência atual usa Ollama; não há integração implementada com APIs externas que exija chave.
- Modelo padrão configurado: `qwen2.5-coder:3b`; logística prefere `qwen3.5:4b` quando disponível. Disponibilidade atual não foi revalidada nesta auditoria.
- Propostas usam aprovação manual ou a opção explícita de autoaprovação de novos pedidos no assistente (desativada por padrão). Validação estática e controle de hash não equivalem a execução nem garantem segurança. Aprovação é por arquivo, sem transação completa do conjunto.
- `data/`, `workspace/`, `.venv/`, bancos e chaves estão ignorados pelo Git. Fazer backup do repositório sem essas pastas não preserva os projetos/dados locais.
- GitHub atual: **repositório público** `https://github.com/lucasramalho28-max/ai-dev-studio`, remoto `origin`, branch `main`. Perfil publicado separadamente em `https://github.com/lucasramalho28-max/lucasramalho28-max`.

## Projeto gerado encontrado

Na leitura do banco em 14/10/2026, existia **um projeto persistido**:

- Nome: Atlas Estoque - Login e Logistica Ficticia.
- ID: `b51ebbd762d8447892f5e5dc02363324`.
- Pasta: `workspace/b51ebbd762d8447892f5e5dc02363324`.
- Origem reconhecida: base local `starters/stock_portal`, com propostas aplicadas. Não confundir esse fluxo determinístico com geração livre do modelo.
- Recursos: cadastro/login/logout, sessão, hash de senha, CSRF, estoque sintético, filtros, indicadores, paginação e CSV.
- Dados confirmados: 72 produtos, 216 posições de estoque, 626 movimentos, três centros; referência sintética de 13/10/2026.
- Banco: `instance/atlas.sqlite3`; chave persistente: `instance/session.key`. Não copiar seus valores para esta memória.
- Acesso demo documentado no README e na tela de login do projeto. A correspondência da senha documentada com o hash da conta demo foi verificada. Existiam duas contas; a senha da outra conta não foi recuperada nem presumida.
- Snapshot do Studio: 19 propostas (17 aplicadas, 2 rejeitadas), 24 jobs. Essas contagens são históricas e podem mudar.

## Trabalho concluído e evidências

### 14/10/2026 — auditoria

- Inventariados código do Studio, base reutilizável e projeto Atlas; consultados README, configuração e testes.
- Consultado o banco existente em modo somente leitura para identificar projeto, propostas, totais e validar acesso demo, sem exibir hashes ou chaves.
- Executado `./.venv/Scripts/python.exe -m unittest discover -s tests -v` na raiz: **65 testes passaram**, incluindo navegador real e execução de Flask.
- Executada descoberta unittest na pasta do Atlas com o Python da `.venv` do Studio: **6 testes passaram**, incluindo autenticação, CSRF, reconciliação, filtros e exportação.
- Reproduzidos em ambiente temporário: Host privado aceito em leitura sem autenticação; perda de valor CSV com cabeçalho espaçado; exceção secundária que oculta erro da base pronta.
- Criado `REVISAO_PROJETOS.md`, com evidências, impactos, limites e recomendações.
- Não foram corrigidos códigos, alteradas contas nem aplicadas propostas existentes. Testes podem produzir artefatos de QA e inicializar arquivos de runtime; não confundir com correção do produto.

### 14/10/2026 — continuidade

- Criados `AGENTS.md` e este arquivo por pedido do usuário.
- Verificada a existência e o conteúdo dos documentos de memória. Não há necessidade de reexecutar testes da aplicação por essa alteração apenas documental.

### 14/10/2026 — interface móvel do Studio

- Pedido do usuário: criar versão do front para dispositivos móveis. Escopo adotado: interface principal do Studio, preservando o projeto Atlas.
- Adicionados `static/mobile.css`, seletor de painéis no template e função `mobilePane` em `static/app.js`. Até 850 px, Arquivos, Área de trabalho, Assistente e Logs ocupam a tela individualmente; módulos ficam na barra inferior.
- Controles maiores para toque, formulários com fonte de 16 px, layouts de coluna única, suporte a altura dinâmica da tela e área segura inferior. Trocar painéis preserva mensagens e edições não salvas.
- Teste real `tests/test_mobile_ui.py` passou: criação/seleção, edição/salvamento, preservação de conteúdo, navegação em todos os módulos e ausência de transbordamento da página em 320×568, 390×844 e 844×390; verifica também retorno ao layout desktop em 1600×1000. Assets externos bloqueados nesse teste para verificar fallback local.
- Capturas inspecionadas em `data/qa/studio-mobile-editor.png` e `data/qa/studio-mobile-chat.png`.
- Teste desktop existente `tests.test_browser_real` também passou após a alteração: criação, edição, execução, inspeção real e fluxo logístico. `git diff --check` sem erros de whitespace.
- Não houve alteração da rede/autenticação nem correção dos achados da auditoria. Testes usam projetos temporários. Emulação de navegador não substitui teste em aparelho físico.

### 14/10/2026 — envio do prompt pelo teclado

- Enter envia o formulário do chat; Shift+Enter mantém quebra de linha. Composição IME e repetição de tecla não disparam envio.
- Adicionado bloqueio durante a requisição inicial para evitar envios duplicados; botão volta a habilitar em caso de falha, respeitando job ativo.
- Dica de teclado incluída no formulário. Verificação pontual em navegador real confirmou evento de envio, quebra de linha, botão desabilitado e composição IME; envio interceptado no teste, sem chamar modelo. `git diff --check` passou.

### 14/10/2026 — seção ativa do Atlas e retorno do chat

- Usuário relatou envio sem resposta ao pedir correção do menu esquerdo. Leitura dos jobs confirmou primeira tentativa com erro de limite de geração; segunda concluída como consulta, sem propostas. A explicação do modelo sobre sessão/login não correspondia à causa encontrada no menu.
- Atlas tinha `selected` fixo em Visão geral. Adicionados atributos de seção, âncora de visão geral e atualização de destaque/`aria-current` por clique, hash, rolagem e redimensionamento, tanto no projeto aplicado quanto na base `starters/stock_portal`.
- Studio agora mostra status do pedido no assistente e falhas como mensagem na conversa. Falhas de inferência/validação do fluxo geral são gravadas no histórico pelo orquestrador. A interface lembra o agente do último envio ao recarregar, preservando acesso ao histórico correto.
- Teste real do Atlas em cópia temporária confirmou navegação, rolagem e link direto. Os 13 testes de qualidade de resposta passaram. Teste móvel ampliado confirmou envio real do formulário por Enter, consulta local respondida e erro de geração simulado visível e preservado após recarregar; passou junto dos 4 testes da base de estoque.
- Backend exige reinício do Studio para carregar a mudança Python. Não houve nova inferência para refazer automaticamente o pedido antigo, nem alteração de contas ou dados de estoque.

### 14/10/2026 — teste visível dentro do VS Code

- Usuário pediu teste em tempo real e depois abertura no VS Code. Controle do Chrome foi interrompido automaticamente por não confirmar a URL; o teste seguinte foi realizado na guia de navegador integrado do VS Code com a habilidade Computer Use.
- Servidor original na porta 5050 estava indisponível. Iniciada instância isolada em `127.0.0.1:5050`, usando `data/qa/live-vscode/data` e `data/qa/live-vscode/workspace`. Não confundir com o banco principal `data/studio.sqlite3`.
- Descoberto em uso real: o navegador integrado não suporta `prompt()`. Substituídos `prompt` e `confirm` do Studio por diálogos HTML acessíveis, incluindo criar/renomear arquivos, criação de projeto, execução e aprovações. Confirmações continuam obrigatórias; Cancelar/Escape não executam a ação.
- Pela interface visível: criado projeto `QA VS Code - teste real`; enviado com Enter o pedido sobre a rota principal de `app.py`; inferência real do Ollama retornou `A rota principal é /`, com referência `app.py:4`. Navegação Agentes → Editor exibiu o destaque correto. Executado projeto e conferido preview com `Seu projeto está no ar.`; parada solicitada após a validação.
- Testes automatizados de navegador desktop e móvel atualizados para os diálogos HTML: **2 testes passaram**, incluindo edição, execução, preview, logística, Enter, mensagem de erro e recuperação do histórico. A resposta Ollama da sessão visível foi real, sem mock.
- Guia do VS Code deixada aberta para acompanhamento. Essa rodada visível validou o Studio de teste; não repetiu login nem navegação do Atlas nessa guia. A validação anterior do Atlas permanece registrada acima.

### 14/10/2026 — preparação para publicação no GitHub

- Usuário pediu envio ao Git e autorizou criar um repositório novo. Nome adotado: `ai-dev-studio`, privado por padrão, na conta conectada `Lucask22000`.
- Git local já existia em `main`, sem remoto; commit inicial `6bead43`. Revisadas alterações da sessão para novo commit, incluindo memória, relatório, interface móvel, chat, diálogos e menu da base de estoque.
- Suíte completa antes do envio: **66 testes passaram**; resultado em `data/qa/git-upload-tests.txt`. Varredura básica de tokens/chaves nos 61 arquivos candidatos não encontrou correspondências; pastas de runtime não estão entre os candidatos.
- `data/`, `workspace/`, `.venv/`, bancos e chaves permanecem excluídos. O Atlas aplicado localmente não será enviado como banco/projeto completo; a base reutilizável e suas correções estão versionadas.
- A criação/publicação remota ainda depende da autenticação do GitHub CLI: o conector disponível identifica a conta, mas não oferece criação de repositório; não foi encontrada credencial Git em cache. Atualizar esta entrada quando o envio for confirmado.

### 14/10/2026 — atividade dos agentes no chat

- Adicionados `static/activity.js` e `static/activity.css`: painel no assistente com etapa atual, agente/modelo, fila, tarefas concluídas, logs recentes, falhas e reconexão. Atualização via SSE real; respostas brutas do modelo não são expostas como progresso.
- Orquestrador emite plano de execução e IDs das tarefas, distinguindo etapas repetidas do mesmo agente; informa preparação do contexto, espera pelo modelo e validação. Eventos de projetos diferentes não entram no painel/chat selecionado.
- Recuperação das execuções ativas ao recarregar usando replay dos eventos. Painel com limite de altura e rolagem própria; botão de envio permanece visível no celular em retrato.
- Geração logística passou a apresentar um gerador local de dashboards, sem as seis atividades fictícias de especialistas. O código apenas propõe arquivos e testes; execução depende das ações já existentes. Isso corrige o achado 6 da auditoria quanto aos status desse fluxo.
- Teste `tests/test_activity_ui.py` verifica transição entre agentes, dez etapas sequenciais, replay após recarregar, fim sem agentes presos como ativos, largura móvel e botão Enviar visível. Inferência simulada nesse teste para controlar precisamente as transições; servidor, navegador e SSE são reais. Captura em `data/qa/chat-live-activity.png`.
- Validação final: **67 testes passaram**, incluindo a nova cobertura de atividade e a suíte completa; resultado em `data/qa/activity-full-suite.txt`. Captura móvel inspecionada visualmente.

### 14/10/2026 — criação do repositório remoto

- Login concluído pelo usuário no GitHub CLI em **lucasramalho28-max**, conta diferente da conexão anterior Lucask22000. Usada a conta efetivamente autenticada para a criação autorizada.
- Criado repositório privado `https://github.com/lucasramalho28-max/ai-dev-studio`; configurado `origin` para esse destino. Commit anterior da sessão: `69286e9`.
- Publicação concluída: `git push -u origin main` enviou o histórico e o commit de implementação `592220c`. Remoto privado: `https://github.com/lucasramalho28-max/ai-dev-studio`. Autenticação Git configurada via GitHub CLI, sem valores de credenciais nos arquivos.
- Instância QA de `data/qa/live-vscode` reiniciada após confirmar identidade do processo e ausência de tarefas ativas, para carregar os novos eventos do orquestrador. Recarregar a guia do VS Code para carregar o front atualizado.

### 14/10/2026 — opção de autoaprovação

- Pedido do usuário: adicionar opção de autoaprovações. Escopo implementado: salvar propostas de arquivos dos novos pedidos enviados com a caixa **Autoaprovar arquivos dos novos pedidos** marcada. Opção desativada por padrão; não altera confirmações de execução, instalações ou downloads.
- Módulo `static/auto-approval.js` mantém autorizações por job/projeto na sessão da guia. Propostas antigas não são autorizadas ao marcar a opção. Desmarcar revoga autorizações pendentes do projeto; não dispara ações que estavam bloqueadas.
- Aplicação exige guia aberta no projeto correspondente. Autorizações de pedidos em andamento sobrevivem ao recarregamento da mesma guia; sem guia aberta as propostas ficam pendentes. A opção é restaurada se houver autorização pendente desse projeto.
- Preflight de todos os arquivos do grupo verifica hashes de disco e buffers abertos; cada salvamento usa a validação estática e o hash já exigidos pelo endpoint. Buffer digitado durante uma requisição é preservado. Conflitos, edições não salvas e falhas pausam a aplicação e aparecem no chat; restantes aguardam revisão manual. Arquivos já salvos antes de uma falha não são revertidos automaticamente.
- Eventos de arquivos registram `automatic:true` quando a aplicação veio desse fluxo. Criação/execução de processos permanece separada.
- Testes de navegador, atividade móvel e serviços: **37 testes direcionados passaram**. Verificação adicional do novo fluxo confirmou aplicação somente após opt-in, preservação de propostas antigas, pausa por buffer não salvo e por alteração de disco durante a inferência. Evidências em `data/qa/auto-approval-tests.txt` e `data/qa/auto-approval-protection-tests.txt`.

### 14/10/2026 — botão único Enviar / Interromper

- Botão principal do chat alterna entre Enviar, Enviando…, Interromper e Interrompendo…. Botão separado de interrupção removido. Durante execução, usa `type=button` para cancelar mesmo com textarea vazio; ao terminar, volta a `type=submit`.
- Clique durante execução chama o endpoint real de cancelamento; pedidos repetidos de cancelamento ficam bloqueados enquanto o agente encerra. Falha de cancelamento permite nova tentativa. Enter continua enviando apenas quando o chat está livre, sem cancelar acidentalmente uma execução.
- Estado recuperado ao recarregar tarefas ativas e ao reexecutar conversa interrompida. Conclusão, erro e cancelamento restauram Enviar.
- **4 testes de navegador passaram**, cobrindo atividade, cancelamento real com modelo controlado, retorno ao envio, recuperação, autoaprovação, mobile e fluxo desktop. Evidências em `data/qa/send-interrupt-tests.txt`; captura móvel inspecionada em `data/qa/chat-live-activity.png`.

### 14/10/2026 — organograma e passagens entre agentes

- Adicionada aba **Organograma** na barra Código / Preview / Alterações do editor, com `static/organogram.js` e `static/organogram.css`. Exibe equipe, agente ativo, etapas da execução, detalhes clicáveis, modelo, logs e setas de encaminhamento. Botão permite retomar acompanhamento do agente ativo após selecionar outra etapa.
- Dados compartilhados com `ExecutionActivity`; eventos de log agora incluem task_id/agent. Orquestrador emite `handoff` após preparar o contexto da próxima etapa, relacionando IDs das etapas e arquivos disponíveis. Setas distinguem próxima etapa, passagem confirmada e passagem ativa. Etapas repetidas continuam separadas.
- Endpoint local `/api/projects/<pid>/flow` recupera dez execuções recentes do projeto, tarefas e até 300 eventos operacionais por execução. Não retorna tokens nem saída bruta do modelo. Organograma recupera também fluxos concluídos ao recarregar, com isolamento por projeto e suporte aos eventos antigos sem plano explícito.
- Visão da equipe usa os agentes cadastrados, incluindo personalizados; geração determinística aparece como gerador local. Estados, erros e interrupções vêm dos dados reais, sem simular atividades nem pensamentos internos.
- **68 testes passaram** na suíte completa. Testes verificam transição Coordenador → Logística, dados de passagem, detalhes da etapa, oito agentes/dez etapas, recuperação de fluxo concluído com nove passagens e isolamento por projeto. Inferência controlada por mock para testar transições; navegador, servidor e SSE reais.
- Evidências: `data/qa/organogram-tests.txt`, `data/qa/organogram-full-suite.txt`, `data/qa/agent-organogram-desktop.png` e `data/qa/agent-organogram-mobile.png`. Capturas inspecionadas visualmente.

### 14/10/2026 — perfil GitHub e projeto público

- Usuário autorizou tornar `ai-dev-studio` público e melhorar o perfil da conta autenticada `lucasramalho28-max`. Visibilidade alterada e confirmada por API sem autenticação; adicionados tópicos Python, Flask, Ollama, agentes, JavaScript, dashboards e logística.
- Revisados 103 blobs únicos do histórico por padrões de tokens/chaves; nenhuma correspondência de alta confiança. `.env.example`, único candidato de caminho sensível, contém apenas a porta pública também nas versões históricas. Essa varredura não equivale a auditoria completa. Runtime, bancos e projetos gerados continuam ignorados.
- Criado repositório público de perfil `lucasramalho28-max/lucasramalho28-max`, com README em português, banner SVG próprio, projeto em destaque, tecnologias e contatos. Usuário confirmou expressamente o WhatsApp como contato público; Instagram, Facebook e WhatsApp aparecem no README e nos links sociais do perfil.
- Usuário concluiu autorização adicional `user` do GitHub CLI. Nome atualizado para Lucas Ramalho, bio sobre IA local/automação/dados e website apontando para o Instagram. Nenhuma credencial foi registrada em arquivos versionados.
- **Recuperação da conta não configurada.** GitHub não oferece cadastro de novo número extra de recuperação por SMS; o contato público não altera autenticação. Consultada a documentação oficial de recuperação/2FA. Não foram alteradas configurações de segurança nem gerados códigos de recuperação.
- Perfil verificado sem login; banner carregado e capturas desktop/mobile inspecionadas, sem transbordamento horizontal a 390 px. Evidências locais em `data/qa/github-profile/`; checkout do perfil em `data/qa/github-profile/repository`, commit `6048e44`. A aplicação não mudou nesta etapa; a suíte de 68 testes permanece como evidência da entrega anterior.

### 14/10/2026 — remoção da aba Logística

- Usuário pediu retirar a aba porque o Studio será usado para criar sistemas de diferentes áreas. Removidos botão de navegação, painel, controles, estado/funções JavaScript específicos e os dois arquivos CSS exclusivos da aba. Limpos também os estilos móveis sem uso.
- Removido carregamento automático de `/logistics` na seleção de projetos. Todos os cartões de agentes abrem o editor e atualizam o seletor/modelo do assistente. Recomendação de Qwen3.5 4B na tela IA passa a usar rótulo geral de análise.
- Eventos de dashboards antigos continuam registrando conclusão nos logs e atualizando propostas, sem acessar o painel removido. Serviços, APIs, bancos, arquivos dos projetos e agente especializado foram preservados; a sequência da equipe não foi alterada nesta entrega.
- README atualizado para quatro módulos e serviços logísticos acessíveis por API. **4 testes existentes de navegador passaram**, cobrindo desktop, três dimensões móveis, edição, execução, preview, chat, organograma, interrupção e autoaprovação. Verificado que navegação/criação não faz requisições logísticas e que o especialista abre corretamente o editor, sem erros JavaScript.
- Evidências: `data/qa/remove-logistics-tests.txt`, `data/qa/editor.png` e `data/qa/studio-mobile-editor.png`. Capturas inspecionadas. Instância isolada de QA do VS Code reiniciada após verificar identidade e ausência de jobs ativos; conteúdo atualizado confirmado por HTTP. Recarregar a guia para atualizar a interface.

## Pendências confirmadas — ainda não corrigidas

Detalhes completos e referências estão em `REVISAO_PROJETOS.md`.

| Prioridade | Pendência | Local principal |
|---|---|---|
| Alta | Studio e subprocessos usam `0.0.0.0`, contrariando promessa de acesso local; Host privado é aceito e token CSRF não autentica usuário | `app.py`, `services/execution_service.py` |
| Alta | Gerador de SLA pode substituir `app.py` de projeto existente e remover autenticação/rotas/dependências | `services/dashboard_service.py` |
| Média | Normalização de cabeçalhos CSV/JSON e truncamento de nomes não preservam associação com valores | `services/logistics_service.py` |
| Média | Tratamento de falhas da base pronta usa `reply` e `aid` antes de definição | `core/orchestrator.py` |
| Média | Senha personalizada reconhecida no pedido pode ser publicada como credencial demo no código, README e login | `services/starter_service.py`, base de estoque |
| Média | Exportação logística não neutraliza fórmulas de planilha em textos importados | `DASHBOARD_JS` no gerador |
| Baixa | Template inicial sem uso no Atlas; duplicação `SAMPLE`/`EMPTY_APP`; carregamento desnecessário de movimentos; título de dashboard ignorado na tela; import de testes pode inicializar runtime real | Ver relatório |

Não remover arquivos/dados por suposta inutilidade sem conferir referências e necessidade do usuário. A senha demo pública é intencional no exemplo atual; não classificá-la como segredo omitido. Não há evidência de que todos os projetos futuros estejam corretos só porque as suítes atuais passaram.

## Próxima retomada

1. Ler esta memória e o relatório; conferir `git status` e alterações recentes.
2. Preservar projetos/dados locais. Não recriar o banco para resolver um problema de código.
3. Se houver pedido de correção, começar pela exposição de rede e preservação da autenticação, depois corrigir falhas reproduzidas e adicionar verificações específicas proporcionais às mudanças.
4. Atualizar os estados acima apenas conforme mudanças e validações reais; registrar limitações e novas decisões.

## Referências locais

- `README.md`: instalação, arquitetura e limitações documentadas; há divergência conhecida sobre bind local.
- `REVISAO_PROJETOS.md`: relatório desta auditoria.
- `VALIDACAO.md`, `VALIDACAO_LOGISTICA.md`, `data/qa/`: evidências históricas de entregas anteriores. Não assumir que foram todas reexecutadas nesta sessão.
- README do Atlas e `starters/stock_portal/README.md`: funcionamento da base e acesso demo.
