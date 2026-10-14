# Validação do Analista de Inteligência Logística

Data: 12 de outubro de 2026.

## Resultado

- 39 testes aprovados, sem falhas e sem testes ignorados: `python -m unittest discover -s tests -v`.
- JavaScript validado com `node --check static/app.js`.
- Interface real aberta pelo Playwright/Edge, incluindo a nova seção **Logística**, sem erros JavaScript.
- CSV, XLSX e JSON lidos localmente; TXT usa o mesmo parser seguro de texto delimitado ou linhas simples.
- Isolamento por projeto confirmado para bases, análises, indicadores, memória e dashboards.
- Confirmação obrigatória verificada para base sintética, regras, memória, indicadores e geração das propostas.
- Base original preservada por SHA-256; nenhuma geração altera o arquivo enviado.
- Conflitos de edição continuam protegidos por hash na aplicação de cada proposta.

## Cenário prático de SLA

A suíte criou uma base explicitamente sintética com 800 pedidos, quatro CDs, quatro regionais e oito semanas. O resultado calculado foi:

- 594 pedidos no prazo;
- 206 pedidos atrasados;
- SLA de expedição de 74,25%;
- fórmula: pedidos únicos no prazo / pedidos únicos elegíveis × 100.

O agente gerou sete propostas: backend Flask, página HTML, CSS, JavaScript, JSON rastreável, teste do dashboard e `requirements.txt`. Depois da aplicação controlada, os testes do projeto gerado passaram e o Playwright abriu o dashboard real, confirmou HTTP 200, o total de 800 pedidos e ausência de erros JavaScript.

## Compatibilidade do ambiente

O Controle de Aplicativos do Windows bloqueou extensões nativas de NumPy/Pandas e a extensão C opcional do SQLAlchemy. O runtime foi adaptado sem reduzir os formatos aceitos:

- CSV, JSON e TXT usam a biblioteca padrão do Python;
- XLSX usa `openpyxl` em modo somente leitura;
- SQLAlchemy usa seu modo Python puro sobre o mesmo SQLite;
- o limite permanece em 25 MB e 100 mil linhas.

O dashboard gerado não usa CDN. Gráficos, filtros e exportação CSV funcionam com HTML, CSS, JavaScript e SVG locais.

## Modelos locais

- `qwen3.5:4b` foi baixado pelo Ollama e validado com uma resposta real `OK`.
- O teste usou `think: false`, contexto de 4.096 tokens e confirmou `done: true`.
- O endpoint `/api/ps` informou 3.130.009.844 bytes do modelo na VRAM, igual ao tamanho carregado: execução integral na GPU.
- `qwen2.5-coder:3b` permanece instalado para implementação e como fallback; o perfil `qwen2.5-coder:3b-cpu` continua disponível.
- O orquestrador escolhe o Qwen3.5 para o analista logístico quando instalado e o Qwen2.5 Coder para os agentes de código. A seleção por agente continua configurável na interface.
