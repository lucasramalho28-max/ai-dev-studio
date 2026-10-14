# Revisão de coerência — 14/10/2026

Escopo: Studio, serviços de geração, base `starters/stock_portal` e único projeto persistido, `workspace/b51ebbd762d8447892f5e5dc02363324` (Atlas Estoque). Banco consultado somente para leitura. Não foram alterados códigos, contas ou propostas existentes. Instaladores de terceiros, ambiente virtual e binários não fazem parte da revisão de código. Esta revisão não garante ausência de todas as vulnerabilidades.

## Achados por prioridade

### 1. Alta — acesso de rede contradiz a documentação

`app.py:395–396` inicia em `0.0.0.0`, e `services/execution_service.py:38–42` faz o mesmo com projetos. `secure_local` aceita IP privado como Host e não exige autenticação para leitura nem login para abrir uma sessão. Se o firewall permitir, outro computador da rede pode ler projetos e abrir a interface para obter seu próprio token e operar o Studio. O token CSRF não autentica o usuário. Um teste local com Host `192.168.1.50:5050`, sem sessão, retornou 200 em `/api/state`; não foi feita tentativa de acesso remoto. Correção indicada: bind em `127.0.0.1` no Studio e no executor; acesso remoto deve ser uma opção separada com autenticação. README promete uso somente local.

### 2. Alta — dashboard logístico pode substituir autenticação existente

`services/dashboard_service.py:299` propõe substituir `app.py`, `templates/index.html` e `requirements.txt` sem verificar o tipo do projeto. No Atlas, aprovar esse `app.py` remove cadastro/login/logout e passa a expor `/api/dashboard-data` sem autenticação. Templates e testes anteriores permanecem, criando um projeto incoerente. Há aprovação manual, mas não um aviso específico sobre perda de autenticação. Correção indicada: gerar em projeto separado ou integrar as rotas preservando autenticação e dependências existentes.

### 3. Média — cabeçalhos com espaços perdem valores

`services/logistics_service.py:213–219` remove espaços do nome das colunas, mas consulta o dicionário CSV usando o nome já modificado. Reprodução: ` pedido ,filial,no_prazo` e `P1,CD A,Sim` resultam em `pedido=None`. Isso impede reconhecer a chave e pode excluir registros válidos. JSON com chaves contendo espaços sofre problema semelhante; nomes truncados a 120 caracteres também deixam de corresponder às chaves. Correção indicada: normalizar nomes e chaves em conjunto, verificando colisões após normalização.

### 4. Média — erro original da base pronta é ocultado

`core/orchestrator.py:75–76` acessa `reply` e `aid` antes de essas variáveis serem definidas no fluxo da base pronta. Uma falha de validação foi simulada em ambiente temporário: o resultado foi `cannot access local variable 'reply' where it is not associated with a value`, ocultando a causa original e impedindo a atualização normal da tarefa para erro. Correção indicada: usar apenas variáveis disponíveis nesse fluxo e preservar a exceção original.

### 5. Média — senha personalizada vira informação pública

`services/starter_service.py` copia a senha reconhecida no pedido para `DEMO_PASSWORD` e README. `starters/stock_portal/app.py:97,108` entrega essa senha ao template de login público. Portanto, uma senha pessoal fornecida nesse formato vira senha pública de demonstração, além de permanecer em mensagens, propostas e código. No Atlas atual, a senha é explicitamente de demonstração e está documentada; não foi identificada senha secreta necessária e omitida. Correção indicada: manter credenciais demo claramente separadas de contas privadas; contas privadas devem escolher senha no cadastro e guardar somente hash.

### 6. Média — etapas de agentes indicam trabalho que não ocorreu

**Atualização de 14/10/2026: corrigido no código.** O gerador agora apresenta uma única tarefa de geração local, informa validação da base e preparação de propostas e não identifica especialistas como executados. Testes propostos continuam distintos de testes executados. O texto abaixo preserva o achado original.

`services/dashboard_service.py:274–295` cria seis tarefas e marca todas como concluídas. Somente a primeira executa `_prepare`; as demais não chamam agentes, revisores ou testes. A geração usa constantes locais, o que é válido, mas o progresso sugere análises especializadas realizadas. Correção indicada: apresentar etapas reais da geração determinística e reservar status de testes/revisão para ferramentas efetivamente executadas.

### 7. Média — exportação CSV logística sem neutralização de fórmulas

`DASHBOARD_JS` em `services/dashboard_service.py`, função `exportCsv`, coloca textos entre aspas, mas não neutraliza valores iniciados por `=`, `+`, `-` ou `@`. Aspas CSV não impedem interpretação de fórmulas por planilhas. Dados importados podem chegar à exportação. O exportador do Atlas já contém proteção básica para textos; o gerador logístico não. Correção indicada: aplicar política consistente de exportação segura e verificar com dados de teste. Não foi executada fórmula em uma planilha real.

### 8. Baixa — sobras e trabalho desnecessário

- `workspace/.../templates/index.html` conserva a página inicial padrão, sem referência no `app.py` atual do Atlas. Pode ser removida após confirmar que será mantido o portal de estoque.
- `SAMPLE` em `app.py` e `EMPTY_APP` em `services/starter_service.py` duplicam o mesmo código. A seleção da base depende de igualdade literal: mudar só um exemplar quebra a detecção. Compartilhar a constante reduz essa fragilidade.
- `dataset()` do Atlas carrega todas as movimentações e filtra em Python a cada pedido, inclusive exportações que só precisam de estoques. Funciona na base pequena, mas gera leitura e processamento evitáveis. Filtrar no SQL e separar cálculos conforme o endpoint.
- O título solicitado ao gerador é gravado no JSON, mas o HTML mantém título e cabeçalho fixos. A tela não reflete esse parâmetro.
- Os testes do portal importam `app`, que cria banco/dados padrão no import. Os bancos dos casos de teste são temporários, mas o import ainda pode inicializar arquivos reais. Separar fábrica e entrada de execução melhora o isolamento.

## Credenciais e configuração confirmadas

- Atlas: usuário `demo`, senha `Estoque@123`, informados no README e no login. A senha documentada corresponde ao hash da conta demo no banco local, verificado sem imprimir o hash.
- Há duas contas no banco. A senha da outra conta não é recuperável pelo hash e não foi presumida. As senhas de testes não comprovam acesso ativo.
- Chave de sessão gerada em `instance/session.key`; não é uma senha que o usuário precise informar. O valor não foi exibido.
- O Studio atual usa Ollama local e não exige chave de API externa. `.env.example` documenta somente `STUDIO_PORT`; `.env` não é carregado automaticamente.
- A varredura do código revisado não identificou chave de API externa ativa. Isso não abrange segredos eventualmente existentes em binários ou arquivos fora do escopo.

## Verificação executada

- Suíte do Studio: **65 testes passaram**, incluindo navegador real, execução de Flask, propostas, autenticação de exemplo e logística.
- Suíte do projeto Atlas atual: **6 testes passaram**.
- Banco Atlas: **72 produtos, 216 posições e 626 movimentos**. Testes confirmam reconciliação de saldos, hashes, CSRF, filtros, exportação e paginação.
- Três verificações adicionais em ambiente temporário reproduziram aceitação de Host privado sem autenticação de leitura, perda de valores em CSV com cabeçalhos espaçados e erro no tratamento de falha da base pronta.
- Testes existentes passando não eliminam os achados acima: os cenários específicos ainda não são cobertos.

Ordem recomendada de correção: restrição de rede; preservação de autenticação ao gerar dashboards; leitura de cabeçalhos; tratamento de erros; separação de credenciais privadas/demo; status verdadeiros; exportação CSV; limpeza de sobras.
