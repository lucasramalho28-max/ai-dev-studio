# Atlas Estoque — demonstração fictícia

Sistema Flask/SQLite com cadastro, login, sessão, logout e dashboard logístico. Todos os produtos, saldos, valores e movimentos são sintéticos.

## Acesso

- Usuário de demonstração: **demo**
- Senha de demonstração: **Estoque@123**
- Login: `/login`; nova conta: `/cadastro`; dashboard: `/dashboard`.
- A conta de demonstração é criada na primeira inicialização e as senhas ficam armazenadas como hash. O acesso de demonstração é público e exclusivo deste exemplo fictício.

No Studio, use **Executar** e abra **Preview**. Também é possível executar `python app.py`, que atende em `http://127.0.0.1:5052`. O projeto usa apenas Flask e a biblioteca padrão do Python.

## Dados e indicadores

Base reproduzível com referência em **13/10/2026**: 72 produtos, 6 categorias, 3 centros (Cuiabá, Campo Grande e Rondonópolis), 216 posições de estoque e 626 movimentos.

Os CSVs UTF-8 estão em `data/`: `produtos_ficticios.csv`, `centros_ficticios.csv`, `estoque_ficticio.csv` e `movimentacoes_ficticias.csv`. `metadados.json` informa a origem sintética, a semente e as regras. Custos de origem são inteiros em centavos; exportações apresentam valores em reais.

- Unidades: soma das quantidades das posições selecionadas.
- Valor: soma de quantidade × custo unitário, em centavos.
- Posição crítica: quantidade menor ou igual ao mínimo; ruptura: quantidade zero.
- Entradas e saídas: movimentos dos últimos 7 dias da base, excluindo ajustes. O saldo de cada posição reconcilia com saldo inicial + movimentos assinados, incluindo ajustes.
- Todos os filtros afetam os indicadores, gráficos, tabela e exportação. Uma linha da tabela representa um produto em um centro. A tabela tem paginação de 18 posições.

`seed_demo.py` reproduz os CSVs, sem usar dados externos. O banco é inicializado a partir deles quando vazio e preservado nas próximas inicializações. Regerar CSVs não altera um banco já inicializado. Dados e usuários criados localmente ficam em `instance/atlas.sqlite3`; a chave da sessão é gerada e persistida em `instance/session.key`.

## Testes

Use **Executar testes do projeto** no Studio ou `python -m unittest discover -s tests -v`. A suíte usa bancos temporários e verifica cadastro, hash, duplicidade, login, logout, proteção de rotas, CSRF, filtros, paginação, CSV, indicadores e reconciliação dos saldos.

Este é um exemplo local de demonstração. Não inclui perfis de acesso, recuperação de senha, gestão real de movimentos ou integrações de transportadoras.
