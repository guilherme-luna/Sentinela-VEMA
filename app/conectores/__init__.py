"""Conectores de entrada (PJe) e saída (planilha).

O núcleo depende só destas interfaces: trocar a simulação pelo PJe real (MNI)
ou o .xlsx local pela planilha do Teams (Microsoft Graph) é configuração.
"""
from datetime import datetime
from typing import Protocol


class ConectorPJe(Protocol):
    def buscar_novos(self, desde: datetime | None) -> list[dict]:
        """Processos que entraram na tarefa de redistribuição depois de `desde`."""

    def paginas_documento(self, processo: dict) -> list[str]:
        """Texto, página a página, da petição/peça principal."""
