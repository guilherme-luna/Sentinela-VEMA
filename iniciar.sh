#!/usr/bin/env sh
# Sobe o Sentinela VEMA em http://localhost:8000 (Mac/Linux). Uso: sh iniciar.sh
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ] || ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "[ERRO] Python 3.10 ou superior não encontrado. Instale em https://www.python.org/downloads/"
  exit 1
fi

[ -x .venv/bin/python ] || "$PY" -m venv .venv
echo "Conferindo dependências..."
.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt
[ -f dados/fila_pje.json ] || .venv/bin/python scripts/gerar_dados.py

echo "Sentinela VEMA em http://localhost:8000  (Ctrl+C para encerrar)"
.venv/bin/python scripts/abrir_navegador.py &
exec .venv/bin/python -m uvicorn app.main:app --port 8000
