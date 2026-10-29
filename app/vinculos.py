"""Vinculação de casos: mesma parte, mesmo local e assunto semelhante.

Cada vínculo informa o critério que o gerou, para que o servidor entenda por que
os processos foram relacionados. A busca semântica com embeddings (fase 2)
substitui o TF-IDF sem mudar a interface deste módulo.
"""
import re
import unicodedata

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import LIMIAR_SIMILARIDADE

# Partes institucionais aparecem em quase todo processo e não indicam conexão.
PARTES_INSTITUCIONAIS = {
    "ministerio publico do estado do ceara",
    "estado do ceara",
    "municipio de fortaleza",
    "defensoria publica do estado do ceara",
    "justica publica",
}

# Locais ambientais do Ceará reconhecidos no texto (amostra para a demonstração).
LOCAIS = [
    "Lagoa da Parangaba", "Lagoa de Messejana", "Rio Cocó", "Rio Ceará", "Rio Maranguapinho",
    "Riacho Pajeú", "Praia do Cumbuco", "Praia de Iracema", "Praia do Futuro", "Serra de Maranguape",
    "Serra de Baturité", "Açude Castanhão", "Açude Orós", "Dunas do Cocó", "Parque do Cocó",
    "Lagoa do Banana", "Jericoacoara", "Canoa Quebrada",
]

STOPWORDS = (
    "a o e de da do das dos em no na nos nas para por com que se ao aos um uma os as "
    "sua seu suas seus pelo pela pelos pelas mais como foi ser ter sob art lei fls autos "
    "processo ministerio publico estado ceara requer requerido requerida autor reu acao"
).split()


def _norm(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


def _doc(documento: str | None) -> str:
    return re.sub(r"\D", "", documento or "")


def locais_citados(texto: str) -> list[str]:
    t = _norm(texto)
    return [l for l in LOCAIS if _norm(l) in t]


def _chaves_partes(processo: dict) -> dict[str, str]:
    """Mapa chave->rótulo. Chave por documento (CPF/CNPJ) ou, sem documento, por nome."""
    chaves = {}
    for parte in processo.get("partes", []):
        nome = parte["nome"]
        if _norm(nome) in PARTES_INSTITUCIONAIS:
            continue
        doc = _doc(parte.get("documento"))
        if doc:
            chaves[f"doc:{doc}"] = f"{nome} ({parte['documento']})"
        else:
            chaves[f"nome:{_norm(nome)}"] = nome
    return chaves


def _vetorizador() -> TfidfVectorizer:
    return TfidfVectorizer(stop_words=STOPWORDS, ngram_range=(1, 2), sublinear_tf=True, preprocessor=_norm)


def encontrar(processo: dict, acervo: list[dict], max_resultados: int = 6) -> dict:
    """Devolve {"vinculos": [...], "semelhantes": [...]} para um processo.

    Vínculo (forte): mesma parte, ou mesmo local com assunto semelhante — indica
    conexão real entre os casos. Semelhante: só o assunto parece, útil para
    reaproveitar entendimento e minutas.
    """
    return encontrar_lote([processo], acervo, max_resultados)[0]


def encontrar_lote(processos: list[dict], base: list[dict], max_resultados: int = 6) -> list[dict]:
    """Vínculos de vários processos contra a mesma base, ajustando o TF-IDF uma única vez."""
    base = list({p["numero"]: p for p in base + processos}.values())
    indice = {p["numero"]: i for i, p in enumerate(base)}
    corpus = [p.get("sintese", "") for p in base]
    matriz = _vetorizador().fit_transform(corpus) if any(corpus) else None
    resultado = []
    for processo in processos:
        sims = {}
        if matriz is not None:
            linha = cosine_similarity(matriz[indice[processo["numero"]]], matriz).ravel()
            sims = {p["numero"]: float(linha[i]) for i, p in enumerate(base)}
        resultado.append(_avaliar(processo, base, sims, max_resultados))
    return resultado


def _avaliar(processo: dict, base: list[dict], sims: dict[str, float], max_resultados: int) -> dict:
    outros = [p for p in base if p["numero"] != processo["numero"]]
    achados: dict[str, dict] = {}

    def add(numero: str, criterio: str, detalhe: str, peso: float):
        v = achados.setdefault(numero, {"numero": numero, "criterios": [], "score": 0.0})
        v["criterios"].append({"tipo": criterio, "detalhe": detalhe})
        v["score"] += peso

    minhas_partes = _chaves_partes(processo)
    meus_locais = set(processo.get("locais") or locais_citados(processo.get("sintese", "")))

    for p in outros:
        for chave in set(minhas_partes) & set(_chaves_partes(p)):
            add(p["numero"], "mesma_parte", f"Mesma parte: {minhas_partes[chave]}", 1.0)
        for local in sorted(meus_locais & set(p.get("locais") or [])):
            add(p["numero"], "mesmo_local", f"Mesmo local: {local}", 0.8)
        s = sims.get(p["numero"], 0.0)
        if s >= LIMIAR_SIMILARIDADE:
            add(p["numero"], "assunto_semelhante", f"Assunto semelhante ({s:.0%} de similaridade)", s)

    por_numero = {p["numero"]: p for p in outros}
    vinculos, semelhantes = [], []
    for v in sorted(achados.values(), key=lambda v: v["score"], reverse=True):
        p = por_numero[v["numero"]]
        v.update(classe=p.get("classe"), servidor=p.get("servidor"), assunto=p.get("assunto"),
                 decisao=p.get("decisao"), score=round(v["score"], 2))
        tipos = {c["tipo"] for c in v["criterios"]}
        if "mesma_parte" in tipos or {"mesmo_local", "assunto_semelhante"} <= tipos:
            vinculos.append(v)
        elif "assunto_semelhante" in tipos:
            semelhantes.append(v)
    return {"vinculos": vinculos[:max_resultados], "semelhantes": semelhantes[:5]}
