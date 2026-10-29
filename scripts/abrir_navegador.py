"""Abre o painel no navegador só quando o servidor já responde (usado pelos scripts iniciar)."""
import sys
import time
import urllib.request
import webbrowser

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

for _ in range(120):  # até 1 minuto
    try:
        urllib.request.urlopen(URL + "/api/estado", timeout=1)
        webbrowser.open(URL)
        break
    except OSError:
        time.sleep(0.5)
