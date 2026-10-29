"""Fluxo da triagem diária: extrair → deduplicar → analisar → propor → aprovar."""
import json
import re
from datetime import datetime
from pathlib import Path

from . import cnj, planilha, urgencia, vinculos
from .config import ACERVO_INICIAL_PATH, MARCO_INICIAL, MODO_DISTRIBUICAO, PLANILHA_PATH, SERVIDORES
from .conectores import ConectorPJe
from .distribuidor import distribuir
from .repositorio import Repositorio

SECAO_FATOS = re.compile(r"DOS FATOS\s*(.+?)(?:II\s*[–-]\s*DO DIREITO|$)", re.S)


def extrair_sintese(paginas: list[str]) -> str:
    texto = "\n".join(paginas)
    m = SECAO_FATOS.search(texto)
    return " ".join((m.group(1) if m else texto[:1500]).split())


class Sentinela:
    def __init__(self, repo: Repositorio, conector: ConectorPJe, planilha_path: Path = PLANILHA_PATH):
        self.repo = repo
        self.pje = conector
        self.planilha_path = planilha_path

    @property
    def marco(self) -> datetime | None:
        valor = self.repo.get_estado("marco")
        return datetime.fromisoformat(valor) if valor else None

    def executar_triagem(self, modo: str = MODO_DISTRIBUICAO) -> dict:
        self.repo.remover_propostas()
        marco_anterior = self.marco
        recebidos = self.pje.buscar_novos(marco_anterior)
        vistos: set[str] = set()
        novos, duplicados, invalidos = [], [], []

        for bruto in recebidos:
            p = {k: v for k, v in bruto.items() if k not in ("servidor", "status")}
            try:
                p["numero"] = cnj.normalizar(p["numero"])
            except ValueError:
                invalidos.append({"numero": p["numero"], "motivo": "Número fora do padrão CNJ"})
                continue
            if not cnj.valido(p["numero"]):
                invalidos.append({"numero": p["numero"], "motivo": "Dígito verificador inválido"})
                continue
            dono_atual = self.repo.servidor_de(p["numero"])
            if dono_atual or p["numero"] in vistos:
                duplicados.append({
                    "numero": p["numero"], "classe": p["classe"], "data_entrada": p["data_entrada"],
                    "motivo": f"Já distribuído para {dono_atual}" if dono_atual else "Repetido na mesma extração",
                })
                continue
            vistos.add(p["numero"])

            paginas = self.pje.paginas_documento(p)
            p["sintese"] = extrair_sintese(paginas) if paginas else p.get("sintese", "")
            p["locais"] = vinculos.locais_citados(" ".join(paginas)) or p.get("locais", [])
            p["alertas"] = [a.to_dict() for a in urgencia.detectar(paginas, p.get("metadados", {}))]
            novos.append(p)

        carga = self.repo.carga_por_servidor()
        for atr, p in zip(distribuir(novos, SERVIDORES, carga, self.repo.servidor_de, modo), novos):
            p["servidor"], p["motivo_distribuicao"] = atr.servidor, atr.motivo

        # Vínculos depois da distribuição, para indicar com quem está cada processo relacionado.
        for p, achados in zip(novos, vinculos.encontrar_lote(novos, self.repo.listar("acervo"))):
            p.update(achados)
        self.repo.salvar_varios(novos, "proposta")

        # O marco avança com tudo o que foi LIDO (inclusive duplicados e inválidos), para que
        # nada reapareça na próxima busca. Só vale depois da aprovação humana; se não houver
        # nada a aprovar, avança na hora.
        marco_lido = max((p["data_entrada"] for p in recebidos), default=None)
        if novos:
            self.repo.set_estado("marco_pendente", marco_lido)
        else:
            self.repo.set_estado("marco_pendente", None)
            if marco_lido:
                self.repo.set_estado("marco", marco_lido)

        resumo = {
            "executada_em": datetime.now().isoformat(timespec="seconds"),
            "modo": modo,
            "marco_anterior": marco_anterior.isoformat(timespec="minutes") if marco_anterior else None,
            "lidos": len(recebidos),
            "novos": len(novos),
            "duplicados": duplicados,
            "invalidos": invalidos,
        }
        self.repo.set_estado("ultima_triagem", json.dumps(resumo, ensure_ascii=False))
        self.repo.auditar("triagem", f"{len(recebidos)} lidos no PJe: {len(novos)} novos, "
                                     f"{len(duplicados)} duplicados, {len(invalidos)} inválidos; modo {modo}")
        return resumo

    def reatribuir(self, numero: str, servidor: str):
        p = self.repo.obter(numero)
        if not p or p["status"] != "proposta":
            raise ValueError("Só é possível alterar a etiqueta de processos ainda não aprovados.")
        if servidor not in {s.nome for s in SERVIDORES}:
            raise ValueError("Servidor desconhecido.")
        anterior = p["servidor"]
        if anterior == servidor:
            return
        p["servidor"], p["motivo_distribuicao"] = servidor, f"Ajuste manual (antes: {anterior})"
        self.repo.salvar(p, "proposta")
        self.repo.auditar("reatribuicao", f"{numero}: {anterior} → {servidor}")

    def aprovar(self) -> dict:
        propostas = self.repo.listar("proposta")
        if not propostas:
            return {"aprovados": 0, "urgentes": 0, "novo_marco": self.repo.get_estado("marco")}
        # Planilha primeiro: se o arquivo estiver aberto no Excel, nada é gravado no banco
        # e a aprovação pode ser repetida.
        acervo_final = self.repo.listar("acervo") + propostas
        planilha.acrescentar(propostas, self.planilha_path, acervo_final)
        self.repo.salvar_varios(propostas, "acervo")
        marco = self.repo.get_estado("marco_pendente") or max(p["data_entrada"] for p in propostas)
        self.repo.set_estado("marco", marco)
        self.repo.set_estado("marco_pendente", None)
        urgentes = sum(1 for p in propostas if p.get("alertas"))
        self.repo.auditar("aprovacao", f"{len(propostas)} processos distribuídos ({urgentes} com alerta); planilha atualizada")
        return {"aprovados": len(propostas), "urgentes": urgentes, "novo_marco": marco}

    def reiniciar_demo(self):
        self.repo.limpar()
        acervo = json.loads(ACERVO_INICIAL_PATH.read_text(encoding="utf-8"))
        for p in acervo:
            p.setdefault("alertas", [])
            p.setdefault("vinculos", [])
            p.setdefault("semelhantes", [])
        self.repo.salvar_varios(acervo, "acervo")
        self.repo.set_estado("marco", MARCO_INICIAL)
        planilha.gerar(self.repo.listar("acervo"), self.planilha_path)
        self.repo.auditar("reinicio", "Base de demonstração restaurada")
