"""Fluxo da triagem diária: extrair → deduplicar → analisar → propor → aprovar."""
import json
import re
from datetime import datetime

from . import cnj, planilha, urgencia, vinculos
from .config import ACERVO_INICIAL_PATH, MODO_DISTRIBUICAO, PLANILHA_PATH, SERVIDORES
from .conectores import ConectorPJe
from .distribuidor import distribuir
from .repositorio import Repositorio

MARCO_INICIAL = "2026-10-27T18:00"
SECAO_FATOS = re.compile(r"DOS FATOS\s*(.+?)(?:II\s*[–-]\s*DO DIREITO|$)", re.S)


def extrair_sintese(paginas: list[str]) -> str:
    texto = "\n".join(paginas)
    m = SECAO_FATOS.search(texto)
    return " ".join((m.group(1) if m else texto[:1500]).split())


class Sentinela:
    def __init__(self, repo: Repositorio, conector: ConectorPJe):
        self.repo = repo
        self.pje = conector

    @property
    def marco(self) -> datetime | None:
        valor = self.repo.get_estado("marco")
        return datetime.fromisoformat(valor) if valor else None

    def executar_triagem(self, modo: str = MODO_DISTRIBUICAO) -> dict:
        self.repo.remover_propostas()
        recebidos = self.pje.buscar_novos(self.marco)
        acervo = self.repo.listar("acervo")
        vistos: set[str] = set()
        novos, duplicados, invalidos = [], [], []

        for bruto in recebidos:
            p = {k: v for k, v in bruto.items() if k != "servidor"}
            try:
                p["numero"] = cnj.normalizar(p["numero"])
            except ValueError:
                invalidos.append({"numero": p["numero"], "motivo": "Número fora do padrão CNJ"})
                continue
            if not cnj.valido(p["numero"]):
                invalidos.append({"numero": p["numero"], "motivo": "Dígito verificador inválido"})
                continue
            existente = self.repo.obter(p["numero"])
            if existente or p["numero"] in vistos:
                duplicados.append({
                    "numero": p["numero"], "classe": p["classe"], "data_entrada": p["data_entrada"],
                    "motivo": f"Já distribuído para {existente['servidor']}" if existente else "Repetido na mesma extração",
                })
                continue
            vistos.add(p["numero"])

            paginas = self.pje.paginas_documento(p)
            p["sintese"] = extrair_sintese(paginas) if paginas else p.get("sintese", "")
            p["locais"] = vinculos.locais_citados(" ".join(paginas)) or p.get("locais", [])
            p["alertas"] = [a.to_dict() for a in urgencia.detectar(paginas, p.get("metadados", {}))]
            novos.append(p)

        def dono(numero: str) -> str | None:
            principal = self.repo.obter(numero)
            return principal.get("servidor") if principal else None

        carga = self.repo.carga_por_servidor()
        for atr, p in zip(distribuir(novos, SERVIDORES, carga, dono, modo), novos):
            p["servidor"], p["motivo_distribuicao"] = atr.servidor, atr.motivo

        # Vínculos depois da distribuição, para indicar com quem está cada processo relacionado.
        base_vinculos = acervo + novos
        for p in novos:
            p.update(vinculos.encontrar(p, base_vinculos))
            self.repo.salvar(p, "proposta")

        resumo = {
            "executada_em": datetime.now().isoformat(timespec="seconds"),
            "modo": modo,
            "marco_anterior": self.marco.isoformat(timespec="minutes") if self.marco else None,
            "novos": len(novos),
            "duplicados": duplicados,
            "invalidos": invalidos,
        }
        self.repo.set_estado("ultima_triagem", json.dumps(resumo, ensure_ascii=False))
        self.repo.auditar("triagem", f"{len(novos)} novos, {len(duplicados)} duplicados bloqueados, modo {modo}")
        return resumo

    def reatribuir(self, numero: str, servidor: str):
        p = self.repo.obter(numero)
        if not p or p["status"] != "proposta":
            raise ValueError("Só é possível reatribuir processos ainda não aprovados.")
        if servidor not in {s.nome for s in SERVIDORES}:
            raise ValueError("Servidor desconhecido.")
        anterior = p["servidor"]
        p["servidor"], p["motivo_distribuicao"] = servidor, f"Ajuste manual (antes: {anterior})"
        self.repo.salvar(p, "proposta")
        self.repo.auditar("reatribuicao", f"{numero}: {anterior} → {servidor}")

    def aprovar(self) -> dict:
        propostas = self.repo.listar("proposta")
        if not propostas:
            return {"aprovados": 0}
        for p in propostas:
            p.pop("status", None)
            self.repo.salvar(p, "acervo")
        marco = max(p["data_entrada"] for p in propostas)
        self.repo.set_estado("marco", marco)
        planilha.gerar(self.repo.listar("acervo"), PLANILHA_PATH)
        urgentes = sum(1 for p in propostas if p.get("alertas"))
        self.repo.auditar("aprovacao", f"{len(propostas)} processos distribuídos ({urgentes} com alerta); planilha atualizada")
        return {"aprovados": len(propostas), "urgentes": urgentes, "novo_marco": marco}

    def reiniciar_demo(self):
        self.repo.limpar()
        for p in json.loads(ACERVO_INICIAL_PATH.read_text(encoding="utf-8")):
            p.setdefault("alertas", [])
            p.setdefault("vinculos", [])
            p.setdefault("semelhantes", [])
            self.repo.salvar(p, "acervo")
        self.repo.set_estado("marco", MARCO_INICIAL)
        planilha.gerar(self.repo.listar("acervo"), PLANILHA_PATH)
        self.repo.auditar("reinicio", "Base de demonstração restaurada")
