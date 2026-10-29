"""Padrões decisórios: o que a vara já decidiu em casos parecidos.

A fonte é a decisão registrada em cada processo do acervo (no MVP, a base
fictícia; na fase 2, a coluna PROVIDÊNCIA da planilha e os movimentos do PJe).
O Sentinela só mostra o histórico da própria vara; quem decide é o juiz.
"""
from collections import Counter, defaultdict
from datetime import datetime
from statistics import median


def resumir(relacionados: list[dict]) -> dict | None:
    """Padrão entre os casos relacionados a um processo que já têm decisão."""
    decididos = [r for r in relacionados if r.get("decisao")]
    if not decididos:
        return None
    contagem = Counter(r["decisao"]["tipo"] for r in decididos)
    predominante, vezes = contagem.most_common(1)[0]
    return {
        "decididos": len(decididos),
        "predominante": predominante,
        "vezes": vezes,
        "distribuicao": [{"tipo": t, "n": n} for t, n in contagem.most_common()],
    }


def _dias_ate_decisao(p: dict) -> int:
    return (datetime.fromisoformat(p["decisao"]["data"]) - datetime.fromisoformat(p["data_entrada"])).days


def por_assunto(acervo: list[dict], exemplos: int = 3) -> list[dict]:
    """Quadro do acervo: para cada assunto, como a vara costuma decidir e em quanto tempo."""
    grupos: dict[str, list[dict]] = defaultdict(list)
    for p in acervo:
        grupos[p.get("assunto") or "Sem assunto"].append(p)

    quadro = []
    for assunto, processos in grupos.items():
        decididos = [p for p in processos if p.get("decisao")]
        contagem = Counter(p["decisao"]["tipo"] for p in decididos)
        recentes = sorted(decididos, key=lambda p: p["decisao"]["data"], reverse=True)[:exemplos]
        quadro.append({
            "assunto": assunto,
            "total": len(processos),
            "decididos": len(decididos),
            "dias_ate_decisao": round(median(map(_dias_ate_decisao, decididos))) if decididos else None,
            "distribuicao": [{"tipo": t, "n": n} for t, n in contagem.most_common()],
            "recentes": [{"numero": p["numero"], "classe": p.get("classe"), "servidor": p.get("servidor"),
                          **p["decisao"]} for p in recentes],
        })
    return sorted(quadro, key=lambda g: g["total"], reverse=True)
