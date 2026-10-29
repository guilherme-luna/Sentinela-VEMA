@echo off
rem Sobe o Sentinela VEMA em http://localhost:8000 (instala o que faltar a cada execucao)
setlocal
set "RAIZ=%~dp0"
pushd "%RAIZ%" || goto pasta
echo Pasta do projeto: %RAIZ%

if not exist "%RAIZ%requirements.txt" goto pasta
if not exist "%RAIZ%app\main.py" goto pasta

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo.
  echo [ERRO] Python 3.10 ou superior nao encontrado.
  echo        Instale em https://www.python.org/downloads/ marcando "Add Python to PATH"
  echo        e execute este arquivo novamente.
  echo.
  pause
  exit /b 1
)

set "PY=%RAIZ%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Criando ambiente Python...
  python -m venv "%RAIZ%.venv" || goto falha
)

echo Conferindo dependencias...
"%PY%" -m pip install -q --disable-pip-version-check -r "%RAIZ%requirements.txt" || goto falha

if not exist "%RAIZ%dados\fila_pje.json" (
  echo Gerando base de demonstracao ficticia...
  "%PY%" "%RAIZ%scripts\gerar_dados.py" || goto falha
)

echo.
echo Sentinela VEMA em http://localhost:8000  (feche esta janela para encerrar)
rem o navegador abre sozinho quando o servidor terminar de carregar
start "" /b "%PY%" "%RAIZ%scripts\abrir_navegador.py"
"%PY%" -m uvicorn app.main:app --port 8000
exit /b 0

:pasta
echo.
echo [ERRO] Este arquivo precisa ficar dentro da pasta do projeto,
echo        junto com as pastas app, web, scripts e o requirements.txt.
echo        Pasta onde ele esta: %RAIZ%
echo        Baixe o projeto inteiro (git clone ou Code - Download ZIP) e rode o iniciar.bat de la.
pause
exit /b 1

:falha
echo.
echo [ERRO] A preparacao falhou. Verifique a conexao com a internet e execute novamente.
echo        Se persistir, apague a pasta .venv e tente de novo.
pause
exit /b 1