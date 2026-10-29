"""Testes das regras críticas: número CNJ, distribuição, urgência e vínculos."""
from datetime import date

import pytest

from app import cnj, urgencia, vinculos
from app.config import Servidor
from app.distribuidor import distribuir

SERVIDORES = [Servidor("A", 1.0, "par"), Servidor("B", 1.0, "impar"), Servidor("C", 0.6, "impar")]


# ---------- número CNJ ----------
def test_numero_real_do_pje_e_valido():
    # Número exibido no PJe da VEMA durante a entrevista
    assert cnj.valido("3115920-52.2025.8.06.0001")


def test_montar_gera_digito_correto_e_normaliza_sem_mascara():
    n = cnj.montar(1234567, 2026)
    assert cnj.valido(n)
    assert cnj.normalizar(n.replace("-", "").replace(".", "")) == n


def test_digito_errado_e_invalido():
    assert not cnj.valido("3115920-53.2025.8.06.0001")
    assert not cnj.valido("123")


def test_paridade_usa_digito_verificador():
    assert cnj.paridade("3115920-52.2025.8.06.0001") == "par"


# ---------- distribuição ----------
def _procs(n):
    return [{"numero": cnj.montar(1000000 + i, 2026)} for i in range(n)]


def test_rodizio_ponderado_respeita_pesos():
    res = distribuir(_procs(130), SERVIDORES, {}, lambda _: None)
    cont = {s.nome: sum(r.servidor == s.nome for r in res) for s in SERVIDORES}
    assert cont["A"] == cont["B"] == 50
    assert cont["C"] == 30  # 0.6 da carga de quem trabalha 5 dias


def test_rodizio_compensa_carga_existente():
    res = distribuir(_procs(3), SERVIDORES, {"A": 10, "B": 10, "C": 0}, lambda _: None)
    assert all(r.servidor == "C" for r in res)


def test_apenso_vai_para_dono_do_principal():
    principal = cnj.montar(42, 2025)
    apenso = {"numero": cnj.montar(43, 2026), "apenso_de": principal}
    res = distribuir([apenso], SERVIDORES, {"B": 99}, lambda n: "B" if n == principal else None)
    assert res[0].servidor == "B"
    assert "Dependente" in res[0].motivo


def test_apenso_de_principal_no_mesmo_lote():
    principal = {"numero": cnj.montar(50, 2026)}
    apenso = {"numero": cnj.montar(51, 2026), "apenso_de": principal["numero"]}
    res = distribuir([principal, apenso], SERVIDORES, {}, lambda _: None)
    assert res[0].servidor == res[1].servidor


def test_modo_paridade():
    res = distribuir(_procs(40), SERVIDORES, {}, lambda _: None, modo="paridade")
    grupo = {s.nome: s.grupo_paridade for s in SERVIDORES}
    for r in res:
        assert grupo[r.servidor] == cnj.paridade(r.numero)


# ---------- urgência ----------
def test_tutela_detectada_com_pagina_e_trecho():
    paginas = ["Dos fatos...", "Requer a concessão de TUTELA DE URGÊNCIA para suspender o evento."]
    alertas = urgencia.detectar(paginas, {})
    assert alertas[0].tipo == urgencia.TUTELA
    assert alertas[0].pagina == 2
    assert "TUTELA DE URGÊNCIA" in alertas[0].trecho


def test_negacao_nao_gera_alerta():
    alertas = urgencia.detectar(["Não há, neste momento, pedido de tutela de urgência."], {})
    assert alertas == []


def test_frase_quebrada_em_linhas_no_pdf():
    alertas = urgencia.detectar(["O requerido, nascido em\n14/02/1951, reside no local."], {}, hoje=date(2026, 10, 28))
    assert [a.tipo for a in alertas] == [urgencia.IDOSO]
    assert "75 anos" in alertas[0].trecho


def test_etiqueta_reu_preso_sem_texto_vira_divergencia():
    alertas = urgencia.detectar(["Supressão de vegetação nativa."], {"reu_preso": True})
    assert alertas[0].fonte == "divergência"


def test_urgencias_ordenadas_por_nivel():
    texto = ["Pessoa idosa. O réu encontra-se preso. Requer liminarmente a suspensão."]
    assert [a.tipo for a in urgencia.detectar(texto, {})] == [urgencia.TUTELA, urgencia.REU_PRESO, urgencia.IDOSO]


# ---------- vínculos ----------
def _p(numero, partes, locais=(), sintese=""):
    return {"numero": numero, "partes": partes, "locais": list(locais), "sintese": sintese}


MP = {"nome": "Ministério Público do Estado do Ceará", "documento": None, "polo": "ativo"}


def test_mesma_parte_por_documento_mesmo_com_nome_diferente():
    a = _p("1", [MP, {"nome": "Maria S. Albuquerque", "documento": "412.873.553-08", "polo": "passivo"}])
    b = _p("2", [MP, {"nome": "MARIA DO SOCORRO ALBUQUERQUE", "documento": "41287355308", "polo": "passivo"}])
    r = vinculos.encontrar(a, [a, b])
    assert [v["numero"] for v in r["vinculos"]] == ["2"]


def test_parte_institucional_nao_gera_vinculo():
    a, b = _p("1", [MP]), _p("2", [MP])
    assert vinculos.encontrar(a, [a, b])["vinculos"] == []


def test_mesmo_local_com_assunto_semelhante_e_vinculo():
    texto = "lançamento de efluentes sem tratamento causando mortandade de peixes na lagoa"
    a = _p("1", [MP], ["Lagoa da Parangaba"], texto)
    b = _p("2", [MP], ["Lagoa da Parangaba"], texto + " no período noturno")
    c = _p("3", [MP], [], "maus-tratos a animais domésticos em residência")
    r = vinculos.encontrar(a, [a, b, c])
    assert [v["numero"] for v in r["vinculos"]] == ["2"]


@pytest.mark.parametrize("texto,esperado", [
    ("Poluição na LAGOA DA PARANGABA e no rio coco", ["Lagoa da Parangaba", "Rio Cocó"]),
    ("Sem local conhecido", []),
])
def test_locais_citados(texto, esperado):
    assert vinculos.locais_citados(texto) == esperado
