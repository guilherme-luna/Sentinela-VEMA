"""Distribuição do acervo entre servidores, seguindo as regras da VEMA.

1. Processo dependente (apenso) vai para quem tem o principal.
2. Demais: rodízio ponderado — recebe quem tem a menor carga relativa ao seu peso
   (servidores de 3 dias têm peso menor). Empate segue a ordem do rodízio.
3. Modo "paridade": processos de dígito verificador par vão para o grupo par, ímpar
   para o grupo ímpar, e dentro do grupo vale o rodízio ponderado.
"""
from dataclasses import dataclass
from typing import Callable

from . import cnj
from .config import Servidor


@dataclass
class Atribuicao:
    numero: str
    servidor: str
    motivo: str


def distribuir(
    processos: list[dict],
    servidores: list[Servidor],
    carga_atual: dict[str, int],
    dono_do_principal: Callable[[str], str | None],
    modo: str = "equilibrado",
) -> list[Atribuicao]:
    carga = {s.nome: carga_atual.get(s.nome, 0) for s in servidores}
    ordem = {s.nome: i for i, s in enumerate(servidores)}
    atribuidos_no_lote: dict[str, str] = {}
    resultado: list[Atribuicao] = []

    for p in processos:
        numero = p["numero"]
        principal = p.get("apenso_de")
        if principal:
            dono = atribuidos_no_lote.get(principal) or dono_do_principal(principal)
            if dono and dono in carga:
                carga[dono] += 1
                atribuidos_no_lote[numero] = dono
                resultado.append(Atribuicao(numero, dono, f"Dependente do processo {principal}, que está com {dono}"))
                continue

        candidatos = servidores
        motivo_grupo = ""
        if modo == "paridade":
            par = cnj.paridade(numero)
            grupo = [s for s in servidores if s.grupo_paridade == par]
            if grupo:
                candidatos = grupo
                motivo_grupo = f"dígito verificador {par}; "

        escolhido = min(candidatos, key=lambda s: ((carga[s.nome] + 1) / s.peso, ordem[s.nome]))
        carga[escolhido.nome] += 1
        atribuidos_no_lote[numero] = escolhido.nome
        resultado.append(Atribuicao(
            numero, escolhido.nome,
            f"{motivo_grupo}rodízio ponderado (carga {carga[escolhido.nome]}, peso {escolhido.peso:g})",
        ))
    return resultado
