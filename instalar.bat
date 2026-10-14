@echo off
setlocal
cd /d "%~dp0"
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 goto python_error
echo Este assistente cria .venv e instala Flask, Playwright e Chromium nesta pasta.
choice /m "Autoriza a preparacao das dependencias locais"
if errorlevel 2 exit /b 0
if not exist ".venv\Scripts\python.exe" python -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "from app import create_app; a=create_app(); print(a.extensions['studio']['installer'].status())"
if errorlevel 1 goto fail
echo Banco preparado. A instalacao do Ollama sera oferecida na interface com confirmacao.
choice /m "Iniciar AI DEV STUDIO agora"
if errorlevel 2 exit /b 0
call iniciar.bat
exit /b 0
:python_error
echo Instale Python 3.11 ou superior de https://www.python.org/downloads/windows/ e habilite PATH.
pause
exit /b 1
:fail
echo Falha na preparacao. Consulte as mensagens acima. Nenhum sucesso foi presumido.
pause
exit /b 1
