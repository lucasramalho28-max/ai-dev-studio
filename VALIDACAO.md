# Validação — 12 de outubro de 2026

## Ambiente

Windows; Python 3.14.6 de 64 bits; ambiente virtual local isolado do site-packages global. Dependências Python instaladas somente em `.venv`: Flask 3.1.3, Playwright 1.63.0 e dependências transitivas. Nenhum instalador do Windows foi executado. O navegador de QA foi o Microsoft Edge já existente.

## Resultados reais

- **34 testes aprovados, zero falhas, zero ignorados**, executados por `.venv\Scripts\python.exe tests/run_suite.py`.
- 33 testes de serviços, segurança e integração: detecção, confirmação e comando winget com mocks; listagem/download/exclusão/modelos/chat com mocks; parsing NDJSON; projetos e arquivos reais; bloqueio de caminhos e origens; confirmação de exclusão; persistência SQLite; sequência de oito etapas; fila de inferência sequencial; cancelamento; eventos SSE; recuperação de jobs; conflitos de versões, inclusive edição manual durante a geração.
- Execução **real** de um projeto Flask em porta escolhida, resposta HTTP 200, readiness e parada do processo.
- Execução **real** do unittest incluído no projeto criado.
- Um teste **real** de navegador abriu a interface no Edge, criou projeto, editou e salvou no **Monaco**, iniciou Flask, validou a prévia dentro do iframe, solicitou inspeção pelo serviço **Playwright**, verificou screenshot e abriu as seções de modelos e agentes. **Zero erros JavaScript**.
- Verificação sintática JavaScript pelo Node incluído no pacote Playwright: `--check static/app.js`, código de saída 0.

O relatório completo está em `data/qa/test-results.txt`; o resumo do navegador, em `data/qa/browser-report.txt`. Screenshots reais: `editor.png`, `preview.png`, `models.png` e `agents.png` na mesma pasta.

## Integrações ainda não verificadas de ponta a ponta

O diagnóstico real retornou: **Ollama não instalado, serviço parado, winget disponível**. Não foi solicitada nem concedida nesta execução a confirmação interativa para instalar o Ollama no Windows. Portanto:

- O instalador foi implementado e testado com subprocesso e respostas simuladas; sua instalação real não foi executada.
- O download de pesos, teste de modelo e geração com Ollama foram testados com mocks e parsing de streaming, sem download real.
- Não houve medição de VRAM, velocidade de tokens ou qualidade de código do Qwen neste hardware.
- Chromium gerenciado não foi instalado; o Playwright real funcionou com Edge existente.
- Os assistentes `.bat` foram criados e revisados, mas não executados integralmente, pois incluem confirmações e preparação adicional. Os comandos Python correspondentes foram executados diretamente no ambiente local durante a validação.

## Próximo passo do usuário

Execute `iniciar.bat`, abra `http://127.0.0.1:5050` e use **Gerenciar IA → Instalar Ollama**. Confirme a instalação, inicie/verifique o serviço e confirme o download de `qwen2.5-coder:3b`. Depois selecione o modelo e clique em **Testar**. Esses passos completam a validação dependente da instalação autorizada e da GPU.

Consulte README.md para o escopo e as limitações do MVP: orquestração fixa, aprovação por arquivo, execução de ferramentas por botões, contexto heurístico, integração externa pendente e ausência de sandbox de sistema operacional.


## Atualiza??o: instala??o autorizada em 12 de outubro de 2026

O usu?rio autorizou a instala??o e o download. O winget n?o transferiu o instalador; foi utilizado o mesmo OllamaSetup.exe oficial da vers?o 0.40.3, obtido do reposit?rio ollama/ollama. O SHA256 AB81DB6C6F4F65547242D1B2912E854DA660AB3BC1DBD5AE3483831CF7668C80 correspondeu ao manifesto Microsoft/winget-pkgs e a assinatura digital foi Valid, Ollama Inc. O instalador terminou com c?digo 0 e o servi?o respondeu com vers?o 0.40.3. O Qwen2.5 Coder 3B Q4_K_M foi baixado, com sucesso e verifica??o pelo gerenciador.

A infer?ncia CUDA falhou com PTX unsupported toolchain no driver NVIDIA 560.94 da GTX 1060 6 GB. A infer?ncia CPU respondeu OK. Foi criado o perfil local qwen2.5-coder:3b-cpu, com num_gpu=0 e num_ctx=4096, reutilizando os pesos existentes sem novo download. O perfil foi selecionado como ativo no Studio e o teste real do aplicativo retornou completed, reply OK, verified true. O modelo original permanece instalado. Nenhum driver foi alterado. A configura??o tempor?ria WinINet do winget foi removida; os arquivos tempor?rios do instalador foram limpos. Evid?ncias em data/downloads/installation-result.json e nos logs da mesma pasta.


## Atualiza??o: driver NVIDIA e infer?ncia GPU autorizados

Em 12 de outubro de 2026, o usu?rio autorizou a atualiza??o do driver. Foi baixado o pacote oficial NVIDIA 582.78 WHQL para Windows 11 de 64 bits. A assinatura digital do pacote e do setup.exe foi Valid, NVIDIA Corporation; os arquivos INF inclu?am DEV_1C03, identificador da GTX 1060 instalada. Foi executada somente a instala??o Display.Driver, com supress?o de rein?cio autom?tico. C?digo de sa?da: 0. O nvidia-smi confirmou driver 582.78 carregado, sem rein?cio do Windows.

Ap?s reiniciar o daemon Ollama pelo Studio, o teste real do modelo original qwen2.5-coder:3b respondeu OK, verified true, job completed. O endpoint /api/ps confirmou size_vram=2159374499 e context_length=4096: o modelo foi carregado na GPU. Durante o teste, nvidia-smi mostrou 2374 MiB ocupados e atividade de GPU. O modelo original foi selecionado como ativo; o perfil CPU continua dispon?vel como alternativa. Evid?ncias: data/downloads/nvidia-582.78/gpu-validation.json, installer-result.json, verified-installer.json e install-logs/. A pol?tica de execu??o bloqueou a limpeza autom?tica dos arquivos tempor?rios; instalador, partes e extra??o permanecem no diret?rio de downloads do projeto.
