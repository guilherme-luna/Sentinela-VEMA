"""API e painel do Sentinela VEMA.  Rodar:  python -m uvicorn app.main:app --reload"""
import json
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import padroes
from .config import ACERVO_INICIAL_PATH, PDF_DIR, PLANILHA_PATH, SERVIDORES
from .conectores.pje_simulado import PJeSimulado
from .planilha import PlanilhaEmUso
from .repositorio import Repositorio
from .servico import Sentinela

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

repo = Repositorio()
sentinela = Sentinela(repo, PJeSimulado())


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    if not ACERVO_INICIAL_PATH.exists():
        raise RuntimeError("Base de demonstração ausente. Rode: python scripts/gerar_dados.py")
    if not repo.listar("acervo") or not PLANILHA_PATH.exists():
        sentinela.reiniciar_demo()
    yield


app = FastAPI(title="Sentinela VEMA", version="0.2.0", lifespan=ciclo_de_vida)


class Triagem(BaseModel):
    modo: Literal["equilibrado", "paridade"] = "equilibrado"


class Reatribuicao(BaseModel):
    servidor: str


@app.get("/api/estado")
def estado():
    acervo = repo.listar("acervo")
    propostas = repo.listar("proposta")
    carga = repo.carga_por_servidor()
    proposta_por = Counter(p["servidor"] for p in propostas)
    ultima = repo.get_estado("ultima_triagem")
    return {
        "marco": repo.get_estado("marco"),
        "acervo_total": len(acervo),
        "servidores": [
            {"nome": s.nome, "peso": s.peso, "acervo": carga.get(s.nome, 0), "propostos": proposta_por.get(s.nome, 0)}
            for s in SERVIDORES
        ],
        "propostas": len(propostas),
        "urgentes": sum(1 for p in propostas if p.get("alertas")),
        "com_vinculo": sum(1 for p in propostas if p.get("vinculos")),
        "ultima_triagem": json.loads(ultima) if ultima else None,
    }


@app.post("/api/triagem")
def executar_triagem(req: Triagem):
    return sentinela.executar_triagem(req.modo)


def _resumo(p: dict) -> dict:
    relacionados = p.get("vinculos", []) + p.get("semelhantes", [])
    return {k: p.get(k) for k in ("numero", "classe", "competencia", "assunto", "data_entrada", "servidor",
                                   "motivo_distribuicao", "alertas", "apenso_de", "locais", "decisao")} | {
        "vinculos": len(p.get("vinculos", [])),
        "semelhantes_decididos": sum(1 for r in relacionados if r.get("decisao")),
        "partes": [x["nome"] for x in p.get("partes", []) if x["polo"] == "passivo"],
    }


@app.get("/api/propostas")
def propostas():
    lista = repo.listar("proposta")
    def prioridade(p: dict) -> float:
        # Etiqueta divergente fica abaixo do alerta confirmado do mesmo nível.
        return min((a["nivel"] + (0.5 if a["fonte"] == "divergência" else 0) for a in p.get("alertas", [])), default=9)

    lista.sort(key=lambda p: (prioridade(p), p["data_entrada"]))
    return [_resumo(p) for p in lista]


@app.get("/api/acervo")
def acervo(servidor: str | None = None):
    lista = [p for p in repo.listar("acervo") if not servidor or p.get("servidor") == servidor]
    return [_resumo(p) for p in reversed(lista)]


@app.get("/api/processos/{numero}")
def processo(numero: str):
    p = repo.obter(numero)
    if not p:
        raise HTTPException(404, "Processo não encontrado")
    # Os vínculos guardam um retrato do momento da triagem; mostra com quem cada um está agora
    # e a decisão mais recente registrada em cada um.
    relacionados = p.get("vinculos", []) + p.get("semelhantes", [])
    for v in relacionados:
        atual = repo.obter(v["numero"]) or {}
        v["servidor"] = atual.get("servidor") or v.get("servidor")
        v["decisao"] = atual.get("decisao") or v.get("decisao")
    p["padrao"] = padroes.resumir(relacionados)
    return p


@app.get("/api/padroes")
def padroes_do_acervo():
    return padroes.por_assunto(repo.listar("acervo"))


@app.put("/api/propostas/{numero}")
def reatribuir(numero: str, req: Reatribuicao):
    try:
        sentinela.reatribuir(numero, req.servidor)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@app.post("/api/aprovar")
def aprovar():
    try:
        return sentinela.aprovar()
    except PlanilhaEmUso as e:
        raise HTTPException(409, str(e))


@app.get("/api/planilha")
def baixar_planilha():
    if not PLANILHA_PATH.exists():
        raise HTTPException(404, "Planilha ainda não gerada")
    return FileResponse(PLANILHA_PATH, filename=PLANILHA_PATH.name)


@app.get("/api/pdf/{numero}")
def pdf(numero: str):
    p = repo.obter(numero)
    if not p or not (PDF_DIR / p.get("pdf", "")).is_file():
        raise HTTPException(404, "Documento não encontrado")
    return FileResponse(PDF_DIR / p["pdf"], media_type="application/pdf")


@app.get("/api/auditoria")
def auditoria():
    return repo.auditoria()


@app.post("/api/demo/reiniciar")
def reiniciar():
    sentinela.reiniciar_demo()
    return {"ok": True}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
