@echo off
rem Sobe o Sentinela VEMA em http://localhost:8000 (instala tudo na primeira execucao)
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install -q -r requirements.txt
)
if not exist dados\fila_pje.json .venv\Scripts\python scripts\gerar_dados.py
start "" http://localhost:8000
.venv\Scripts\python -m uvicorn app.main:app --port 8000
