"""Configuração da vara: servidores, pesos e caminhos.

Tudo que é regra de negócio ajustável pela gestão fica aqui, não espalhado pelo código.
"""
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DADOS_DIR = BASE_DIR / "dados"
PDF_DIR = DADOS_DIR / "pdfs"
DB_PATH = DADOS_DIR / "sentinela.db"
PLANILHA_PATH = DADOS_DIR / "01 - Controle de Acervo.xlsx"
FILA_PJE_PATH = DADOS_DIR / "fila_pje.json"
ACERVO_INICIAL_PATH = DADOS_DIR / "acervo_inicial.json"


@dataclass(frozen=True)
class Servidor:
    nome: str
    peso: float  # 1.0 = 5 dias na unidade; 0.6 = 3 dias
    grupo_paridade: str  # "par" ou "impar", usado no modo par/ímpar


# Nomes fictícios para a demonstração; a vara substitui pelos reais.
SERVIDORES: list[Servidor] = [
    Servidor("Ana", 1.0, "par"),
    Servidor("Bruno", 1.0, "impar"),
    Servidor("Carla", 1.0, "par"),
    Servidor("Diego", 0.6, "impar"),
    Servidor("Elisa", 0.6, "impar"),
]

# Ponto de partida da extração incremental na base de demonstração
# (última triagem aprovada antes da fila do dia gerada pelo script).
MARCO_INICIAL = "2026-10-27T18:00"

# Modo de distribuição padrão: "equilibrado" (rodízio ponderado) ou "paridade".
MODO_DISTRIBUICAO = "equilibrado"

# Similaridade textual mínima para sugerir vínculo por assunto.
LIMIAR_SIMILARIDADE = 0.30
