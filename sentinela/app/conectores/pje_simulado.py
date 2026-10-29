"""PJe simulado: lê a fila de redistribuição de um JSON e as peças em PDF.

Mesma interface que o conector real via MNI (Modelo Nacional de Interoperabilidade
do CNJ), que na fase 2 consultará o PJe do TJCE sem alterar o sistema.
"""
import json
from datetime import datetime

import pymupdf

from ..config import FILA_PJE_PATH, PDF_DIR


class PJeSimulado:
    def __init__(self, caminho_fila=FILA_PJE_PATH, pasta_pdf=PDF_DIR):
        self.caminho_fila = caminho_fila
        self.pasta_pdf = pasta_pdf

    def buscar_novos(self, desde: datetime | None) -> list[dict]:
        fila = json.loads(self.caminho_fila.read_text(encoding="utf-8"))
        novos = [p for p in fila if desde is None or datetime.fromisoformat(p["data_entrada"]) > desde]
        return sorted(novos, key=lambda p: p["data_entrada"])

    def paginas_documento(self, processo: dict) -> list[str]:
        caminho = self.pasta_pdf / processo["pdf"]
        if not caminho.exists():
            return []
        with pymupdf.open(caminho) as doc:
            return [pagina.get_text() for pagina in doc]
