"""Detector de urgência explicável.

Combina metadados do PJe com regras sobre o texto da petição. Cada alerta traz
o trecho e a página que o justificam, para conferência humana. A camada de
modelo de linguagem (fase 2) apenas confirma/complementa estes alertas.
"""
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import date

TUTELA = "tutela_urgencia"
REU_PRESO = "reu_preso"
IDOSO = "idoso"

NIVEL = {TUTELA: 1, REU_PRESO: 2, IDOSO: 3}  # 1 = mais urgente
ROTULO = {
    TUTELA: "Tutela de urgência / liminar (48h)",
    REU_PRESO: "Réu preso (revisão a cada 90 dias)",
    IDOSO: "Prioridade: pessoa idosa",
}

PADROES = {
    TUTELA: [
        r"tutela (provisoria )?de urgencia",
        r"tutela antecipada",
        r"(pedido|medida|concessao) (de )?liminar",
        r"\bliminarmente\b",
        r"inaudita altera pars",
    ],
    REU_PRESO: [
        r"preso preventivamente",
        r"prisao preventiva (foi )?(decretada|mantida)",
        r"encontra-se (preso|recolhido|custodiado)",
        r"auto de prisao em flagrante",
        r"\bsegue custodiado\b",
    ],
    IDOSO: [
        r"pessoa idosa",
        r"estatuto (da pessoa )?(do )?idos[ao]",
        r"art\. ?1\.048",
    ],
}

NEGACOES = re.compile(r"\b(nao|sem|indefer\w*|inexist\w*|revogad\w*|ausencia de)\b[^.]{0,40}$")
NASCIMENTO = re.compile(r"nascid[oa] em (\d{2})/(\d{2})/(\d{4})")


@dataclass
class Alerta:
    tipo: str
    rotulo: str
    nivel: int
    fonte: str  # "texto", "metadado PJe" ou "divergência"
    trecho: str
    pagina: int | None

    def to_dict(self) -> dict:
        return asdict(self)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def _trecho(original: str, ini: int, fim: int, margem: int = 90) -> str:
    a, b = max(0, ini - margem), min(len(original), fim + margem)
    return ("…" if a else "") + " ".join(original[a:b].split()) + ("…" if b < len(original) else "")


def _buscar(tipo: str, paginas: list[str]) -> Alerta | None:
    for n, original in enumerate(paginas, start=1):
        original = " ".join(original.split())  # o PDF quebra frases em várias linhas
        texto = _sem_acento(original)  # mesmo comprimento do original para os caracteres usados
        for padrao in PADROES[tipo]:
            for m in re.finditer(padrao, texto):
                if NEGACOES.search(texto[max(0, m.start() - 60):m.start()]):
                    continue
                return Alerta(tipo, ROTULO[tipo], NIVEL[tipo], "texto", _trecho(original, m.start(), m.end()), n)
    return None


def _idoso_por_nascimento(paginas: list[str], hoje: date) -> Alerta | None:
    for n, original in enumerate(paginas, start=1):
        original = " ".join(original.split())
        for m in NASCIMENTO.finditer(_sem_acento(original)):
            d, mth, a = map(int, m.groups())
            idade = hoje.year - a - ((hoje.month, hoje.day) < (mth, d))
            if idade >= 60:
                return Alerta(IDOSO, ROTULO[IDOSO], NIVEL[IDOSO], "texto",
                              f"Parte com {idade} anos — " + _trecho(original, m.start(), m.end(), 60), n)
    return None


def detectar(paginas: list[str], metadados: dict, hoje: date | None = None) -> list[Alerta]:
    hoje = hoje or date.today()
    alertas: list[Alerta] = []

    tutela = _buscar(TUTELA, paginas)
    if tutela:
        alertas.append(tutela)
    elif metadados.get("pedido_liminar"):
        alertas.append(Alerta(TUTELA, ROTULO[TUTELA], NIVEL[TUTELA], "metadado PJe", "Pedido de liminar marcado na autuação.", None))

    preso = _buscar(REU_PRESO, paginas)
    if preso:
        alertas.append(preso)
    elif metadados.get("reu_preso"):
        # A etiqueta veio do PJe mas o texto não confirma: sinaliza para conferência
        # (a vara relatou etiquetas de réu preso erradas após a migração).
        alertas.append(Alerta(REU_PRESO, "Etiqueta 'réu preso' sem confirmação no texto — conferir",
                              NIVEL[REU_PRESO], "divergência",
                              "O PJe indica réu preso, mas a petição não menciona prisão.", None))

    idoso = _buscar(IDOSO, paginas) or _idoso_por_nascimento(paginas, hoje)
    if idoso:
        alertas.append(idoso)
    elif metadados.get("prioridade_idoso"):
        alertas.append(Alerta(IDOSO, ROTULO[IDOSO], NIVEL[IDOSO], "metadado PJe", "Prioridade de idoso marcada na autuação.", None))

    return sorted(alertas, key=lambda a: a.nivel)
