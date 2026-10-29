"""Gera a base FICTÍCIA da demonstração (nenhum dado real de processo).

Saídas em dados/:
  acervo_inicial.json  — processos já distribuídos (o que está hoje na planilha)
  fila_pje.json        — tarefa "Analisar distribuição" do PJe simulado
  pdfs/*.pdf           — petições/peças de cada processo

Casos plantados para o roteiro da demo: tutelas de urgência, réu preso, idoso,
etiqueta de réu preso errada, duplicados, apensos, mesma parte com conduta
repetida e vários processos sobre a Lagoa da Parangaba.
Semente fixa: a base gerada é sempre a mesma.
"""
import json
import random
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import cnj  # noqa: E402
from app.config import ACERVO_INICIAL_PATH, DADOS_DIR, FILA_PJE_PATH, PDF_DIR, SERVIDORES  # noqa: E402

rnd = random.Random(2026)
HOJE = datetime(2026, 10, 28)
MARCO = datetime(2026, 10, 27, 18, 0)  # última triagem aprovada

MP = {"nome": "Ministério Público do Estado do Ceará", "documento": None, "polo": "ativo"}
ESTADO = {"nome": "Estado do Ceará", "documento": None, "polo": "passivo"}
DEFENSORIA = {"nome": "Defensoria Pública do Estado do Ceará", "documento": None, "polo": "ativo"}

NOMES = ["José", "Francisco", "Antônio", "Raimundo", "Francisca", "Maria José", "Antônia", "Paulo",
         "Luiz Carlos", "Expedito", "Cícero", "Joana", "Rita", "Edmilson", "Valdir", "Socorro", "Fátima"]
SOBRENOMES = ["Silva", "Sousa", "Oliveira", "Lima", "Pereira", "Costa", "Rodrigues", "Almeida",
              "Nascimento", "Bezerra", "Holanda", "Cavalcante", "Barbosa", "Gomes", "Pinheiro", "Mota"]
EMPRESAS = ["Cerâmica Vale do Jaguaribe Ltda", "Construtora Atlântico Norte Ltda", "Posto Avenida Sul Ltda",
            "Curtume Boa Esperança Ltda", "Mineração Serra Verde S/A", "Eventos Litoral Leste Ltda",
            "Frigorífico Sertão Central Ltda", "Loteamento Brisa do Mar SPE Ltda"]
BAIRROS = ["Parangaba", "Messejana", "Barra do Ceará", "Bom Jardim", "Mondubim", "Aldeota", "Jangurussu",
           "Pirambu", "Conjunto Ceará", "Sabiaguaba"]
ORIGENS = ["0001", "0001", "0001", "0001", "0296", "0512", "0302", "0091"]  # Fortaleza e interior


def cpf() -> str:
    d = [rnd.randint(0, 9) for _ in range(11)]
    return f"{d[0]}{d[1]}{d[2]}.{d[3]}{d[4]}{d[5]}.{d[6]}{d[7]}{d[8]}-{d[9]}{d[10]}"


def cnpj() -> str:
    d = "".join(str(rnd.randint(0, 9)) for _ in range(8))
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/0001-{rnd.randint(10, 99)}"


def pessoa(polo="passivo") -> dict:
    return {"nome": f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)} {rnd.choice(SOBRENOMES)}", "documento": cpf(), "polo": polo}


def empresa(polo="passivo", nome=None) -> dict:
    return {"nome": nome or rnd.choice(EMPRESAS), "documento": cnpj(), "polo": polo}


# Partes recorrentes (conduta repetida)
MARIA = {"nome": "Maria do Socorro Albuquerque", "documento": "412.873.553-08", "polo": "passivo"}
LAVANDERIA = {"nome": "Lavanderia Industrial Parangaba Ltda", "documento": "07.384.912/0001-55", "polo": "passivo"}
EVENTOS = {"nome": "Eventos Litoral Leste Ltda", "documento": "15.226.490/0001-31", "polo": "passivo"}

# Modelos de fatos. {reu}, {local}, {bairro} são preenchidos na geração.
MODELOS = {
    "poluicao_lagoa": ("Poluição", ["Lagoa da Parangaba", "Lagoa de Messejana", "Rio Maranguapinho", "Rio Cocó"],
        "Apurou-se que {reu} vem lançando efluentes sem tratamento na {local}, no bairro {bairro}, causando "
        "mortandade de peixes, odor intenso e alteração da coloração da água, conforme relatório de vistoria da "
        "SEMACE e laudo de análise físico-química que acompanham a inicial. Moradores do entorno relatam que o "
        "despejo ocorre principalmente no período noturno."),
    "maus_tratos": ("Crimes contra a Fauna", [None],
        "Consta que {reu} mantinha cães e gatos em situação de maus-tratos em imóvel no bairro {bairro}, sem "
        "água, alimentação adequada ou abrigo, alguns acorrentados e com ferimentos, conforme auto de constatação "
        "da Polícia Militar Ambiental e laudo médico-veterinário. A conduta amolda-se ao art. 32 da Lei 9.605/98."),
    "app_construcao": ("Dano Ambiental", ["Rio Cocó", "Rio Ceará", "Riacho Pajeú", "Dunas do Cocó", "Lagoa da Parangaba"],
        "Verificou-se construção irregular em Área de Preservação Permanente às margens do {local}, promovida por "
        "{reu}, com aterramento de vegetação ciliar e supressão de mata nativa, sem licença ambiental, conforme "
        "auto de infração e relatório fotográfico da fiscalização municipal."),
    "desmatamento": ("Crimes contra a Flora", ["Serra de Maranguape", "Serra de Baturité", "Açude Castanhão"],
        "Foi constatada a supressão de aproximadamente 12 hectares de vegetação nativa de caatinga na região da "
        "{local}, atribuída a {reu}, sem autorização do órgão ambiental competente, com uso de fogo e "
        "retirada de madeira para produção de carvão, conforme imagens de satélite e auto de infração."),
    "evento_dunas": ("Dano Ambiental", ["Praia do Cumbuco", "Canoa Quebrada", "Jericoacoara"],
        "Noticia-se a realização de evento de grande porte por {reu} na {local}, com instalação de estruturas, "
        "tráfego de veículos sobre as dunas e acesso de público estimado em cinco mil pessoas a área de "
        "proteção ambiental, sem licenciamento e sem estudo de impacto ambiental."),
    "fauna_silvestre": ("Crimes contra a Fauna", [None],
        "Durante fiscalização no bairro {bairro}, foram apreendidas 23 aves silvestres mantidas em cativeiro por "
        "{reu}, entre elas galos-de-campina e papagaios, sem autorização do IBAMA, algumas em gaiolas "
        "superlotadas e com sinais de maus-tratos."),
    "pesca": ("Crimes contra a Fauna", ["Açude Orós", "Açude Castanhão", "Lagoa do Banana"],
        "Foi flagrada a prática de pesca predatória no {local} por {reu}, com uso de rede de malha proibida e "
        "explosivos, em período de defeso, conforme auto de prisão e termo de apreensão de petrechos."),
    "ruido": ("Poluição", [None],
        "Relatam os moradores do bairro {bairro} que o estabelecimento explorado por {reu} emite ruídos acima "
        "dos limites legais diariamente até a madrugada, conforme medições de decibelímetro realizadas pela "
        "AGEFIS que constataram 85 dB no período noturno."),
}

CLASSES_CIVEIS = ["Ação Civil Pública", "Ação Civil Pública", "Ação Civil Pública", "Procedimento Comum Cível",
                  "Cumprimento de Sentença"]
CLASSES_CRIMINAIS = ["Inquérito Policial", "Inquérito Policial", "Ação Penal - Procedimento Ordinário",
                     "Termo Circunstanciado", "Representação Criminal/Notícia de Crime"]

seq_usados: set[int] = set()


def novo_numero(ano: int) -> str:
    while True:
        s = rnd.randint(200000, 3199999)
        if s not in seq_usados:
            seq_usados.add(s)
            return cnj.montar(s, ano, rnd.choice(ORIGENS))


def montar_processo(modelo: str, *, reu=None, local=None, classe=None, data_entrada: datetime,
                    extras_direito="", extras_pedidos="", polo_ativo=None, idoso_texto="", ano=None) -> dict:
    assunto, locais, texto = MODELOS[modelo]
    local = local or rnd.choice(locais)
    criminal = modelo in ("maus_tratos", "fauna_silvestre", "pesca") or (classe in CLASSES_CRIMINAIS)
    classe = classe or rnd.choice(CLASSES_CRIMINAIS if criminal else CLASSES_CIVEIS)
    reu = reu or (pessoa() if criminal or rnd.random() < 0.4 else empresa())
    sintese = texto.format(reu=reu["nome"], local=local or "", bairro=rnd.choice(BAIRROS))
    sintese += idoso_texto
    partes = [polo_ativo or MP, reu]
    if not criminal and rnd.random() < 0.3:
        partes.append(ESTADO)
    return {
        "numero": novo_numero(ano or rnd.choice([2019, 2021, 2022, 2023, 2024, 2025, 2026])),
        "classe": classe,
        "competencia": "Criminal" if classe in CLASSES_CRIMINAIS or "Penal" in classe or "Prisão" in classe else "Cível",
        "assunto": assunto,
        "data_entrada": data_entrada.isoformat(timespec="minutes"),
        "partes": partes,
        "apenso_de": None,
        "metadados": {"reu_preso": False, "prioridade_idoso": False, "pedido_liminar": False},
        "locais": [local] if local else [],
        "sintese": sintese,
        "_direito": extras_direito,
        "_pedidos": extras_pedidos,
    }


def escrever_pdf(p: dict):
    ativo = ", ".join(x["nome"] for x in p["partes"] if x["polo"] == "ativo")
    passivo = "; ".join(f"{x['nome']}" + (f", inscrito(a) sob nº {x['documento']}" if x["documento"] else "")
                        for x in p["partes"] if x["polo"] == "passivo")
    paginas = [
        f"""<p style="text-align:center"><b>EXCELENTÍSSIMO(A) SENHOR(A) JUIZ(A) DE DIREITO DA VARA ESTADUAL DO MEIO
        AMBIENTE DA COMARCA DE FORTALEZA/CE</b></p><br>
        <p>Processo nº {p['numero']}<br>Classe: {p['classe']}<br>Assunto: {p['assunto']}</p><br>
        <p><b>{ativo}</b>, vem, respeitosamente, perante Vossa Excelência, em face de <b>{passivo}</b>,
        expor e requerer o que segue.</p><br>
        <p><b>I – DOS FATOS</b></p><p style="text-align:justify">{p['sintese']}</p>
        <p style="text-align:justify">Os documentos anexos demonstram a materialidade dos fatos narrados e a
        necessidade de atuação do Poder Judiciário para cessar e reparar o dano ambiental.</p>""",
        f"""<p><b>II – DO DIREITO</b></p><p style="text-align:justify">A Constituição Federal, em seu art. 225,
        assegura a todos o direito ao meio ambiente ecologicamente equilibrado, impondo ao Poder Público e à
        coletividade o dever de defendê-lo e preservá-lo. A Lei 6.938/81 consagra a responsabilidade objetiva do
        poluidor, e a Lei 9.605/98 tipifica as condutas lesivas ao meio ambiente.</p>
        <p style="text-align:justify">{p['_direito']}</p>""",
        f"""<p><b>III – DOS PEDIDOS</b></p><p style="text-align:justify">Diante do exposto, requer:</p>
        <p style="text-align:justify">{p['_pedidos']}</p>
        <p>a) a citação/intimação da parte requerida;</p><p>b) a produção de todas as provas admitidas;</p>
        <p>c) a procedência dos pedidos, com a reparação integral do dano ambiental.</p><br>
        <p>Fortaleza/CE, {datetime.fromisoformat(p['data_entrada']).strftime('%d/%m/%Y')}.</p>""",
    ]
    doc = pymupdf.open()
    for html in paginas:
        pagina = doc.new_page(width=595, height=842)
        pagina.insert_htmlbox(pymupdf.Rect(60, 60, 535, 790), html,
                              css="* {font-family: sans-serif; font-size: 11pt; line-height: 1.4}")
    nome = p["numero"].replace(".", "_").replace("-", "_") + ".pdf"
    doc.save(PDF_DIR / nome)
    p["pdf"] = nome


def acervo_inicial() -> list[dict]:
    acervo = []
    inicio = datetime(2026, 3, 26, 9)
    total = 118
    for i in range(total):
        data = inicio + timedelta(days=(MARCO - inicio).days * i / total, hours=rnd.randint(0, 8))
        acervo.append(montar_processo(rnd.choice(list(MODELOS)), data_entrada=data))

    # Casos recorrentes plantados no acervo
    for k, d in enumerate([datetime(2026, 4, 14, 10), datetime(2026, 6, 2, 15), datetime(2026, 8, 19, 11)]):
        acervo.append(montar_processo("maus_tratos", reu=MARIA, data_entrada=d,
                                      classe=["Termo Circunstanciado", "Inquérito Policial", "Ação Penal - Procedimento Ordinário"][k]))
    for d in [datetime(2026, 5, 6, 9), datetime(2026, 7, 21, 14)]:
        acervo.append(montar_processo("poluicao_lagoa", reu=LAVANDERIA, local="Lagoa da Parangaba",
                                      classe="Ação Civil Pública", data_entrada=d))
    acervo.append(montar_processo("app_construcao", local="Lagoa da Parangaba", classe="Ação Civil Pública",
                                  data_entrada=datetime(2026, 9, 3, 10)))
    acervo.append(montar_processo("evento_dunas", local="Praia do Cumbuco", reu=EVENTOS,
                                  classe="Ação Civil Pública", data_entrada=datetime(2026, 7, 8, 16)))
    # Ação penal com réu preso: o pedido de relaxamento de hoje será apenso a ela
    acervo.append(montar_processo("pesca", classe="Ação Penal - Procedimento Ordinário",
                                  data_entrada=datetime(2026, 9, 22, 9)))
    acervo.sort(key=lambda p: p["data_entrada"])

    # Distribuição histórica proporcional ao peso (rodízio ponderado)
    carga = {s.nome: 0 for s in SERVIDORES}
    for p in acervo:
        s = min(SERVIDORES, key=lambda s: ((carga[s.nome] + 1) / s.peso, s.nome))
        carga[s.nome] += 1
        p["servidor"] = s.nome
    return acervo


def fila_do_dia(acervo: list[dict]) -> list[dict]:
    t = iter(MARCO + timedelta(minutes=37 * i + rnd.randint(0, 20)) for i in range(1, 200))
    fila: list[dict] = []

    # 1) Tutela de urgência — evento nas dunas no sábado (mesmo réu e local de processo anterior)
    fila.append(montar_processo(
        "evento_dunas", local="Praia do Cumbuco", reu=EVENTOS,
        classe="Ação Civil Pública", polo_ativo=DEFENSORIA, data_entrada=next(t), ano=2026,
        extras_direito="O evento está marcado para o próximo sábado, de modo que a demora na prestação "
                       "jurisdicional tornará o dano irreversível.",
        extras_pedidos="<b>a concessão de TUTELA DE URGÊNCIA, inaudita altera pars</b>, para determinar a "
                       "suspensão imediata do evento e a retirada das estruturas instaladas sobre as dunas, sob "
                       "pena de multa diária de R$ 50.000,00;"))
    # 2) Tutela de urgência — Lagoa da Parangaba, mesma empresa reincidente
    fila.append(montar_processo(
        "poluicao_lagoa", reu=LAVANDERIA, local="Lagoa da Parangaba", classe="Ação Civil Pública",
        data_entrada=next(t), ano=2026,
        extras_pedidos="liminarmente, a interrupção imediata do lançamento de efluentes na Lagoa da Parangaba, "
                       "com lacração das tubulações clandestinas;"))
    # 3) Maria — conduta repetida (4º processo), sem urgência; texto com negação para não gerar falso alerta
    fila.append(montar_processo(
        "maus_tratos", reu=MARIA, classe="Inquérito Policial", data_entrada=next(t), ano=2026,
        extras_direito="Não há, neste momento, pedido de tutela de urgência, tendo os animais sido "
                       "resgatados pela Polícia Militar Ambiental."))
    # 4) Réu preso — auto de prisão em flagrante
    fila.append(montar_processo(
        "fauna_silvestre", classe="Auto de Prisão em Flagrante", data_entrada=next(t), ano=2026,
        extras_direito="O autuado encontra-se recolhido na Delegacia de Capturas, tendo sido lavrado o auto de "
                       "prisão em flagrante, que ora se comunica para análise da legalidade da prisão."))
    # 5) Apenso — relaxamento de prisão na ação penal de pesca (vai para o mesmo servidor)
    principal = next(p for p in acervo if p["classe"] == "Ação Penal - Procedimento Ordinário" and p["assunto"] == "Crimes contra a Fauna"
                     and p["data_entrada"].startswith("2026-09-22"))
    relax = montar_processo("pesca", reu=principal["partes"][1], local=principal["locais"][0],
                            classe="Pedido de Relaxamento de Prisão", data_entrada=next(t), ano=2026,
                            extras_direito="O requerente segue custodiado há mais de 90 dias sem revisão da "
                                           "necessidade da prisão preventiva.")
    relax["competencia"], relax["apenso_de"] = "Criminal", principal["numero"]
    relax["metadados"]["reu_preso"] = True
    fila.append(relax)
    # 6) Idoso pela data de nascimento
    idoso = pessoa()
    fila.append(montar_processo(
        "app_construcao", reu=idoso, classe="Procedimento Comum Cível", data_entrada=next(t), ano=2025,
        idoso_texto=f" O requerido, {idoso['nome']}, nascido em 14/02/1951, reside no imóvel há mais de 30 anos."))
    # 7) Idoso pelo texto (Estatuto)
    fila.append(montar_processo(
        "ruido", classe="Procedimento Comum Cível", polo_ativo=pessoa("ativo"), data_entrada=next(t), ano=2026,
        extras_direito="A autora é pessoa idosa, com problemas cardíacos agravados pela privação de sono, "
                       "fazendo jus à prioridade de tramitação prevista no Estatuto da Pessoa Idosa."))
    # 8) Etiqueta de réu preso ERRADA (erro de migração relatado pela vara)
    errado = montar_processo("desmatamento", classe="Inquérito Policial", data_entrada=next(t), ano=2024)
    errado["metadados"]["reu_preso"] = True
    fila.append(errado)
    # 9) Mais um caso na Lagoa da Parangaba (outro réu)
    fila.append(montar_processo("poluicao_lagoa", local="Lagoa da Parangaba", classe="Inquérito Policial",
                                data_entrada=next(t), ano=2026))

    # Processos comuns
    for _ in range(24):
        fila.append(montar_processo(rnd.choice(list(MODELOS)), data_entrada=next(t), ano=rnd.choice([2022, 2024, 2025, 2026])))

    # Duplicados: processos já distribuídos que voltaram para a fila (redistribuição em andamento)
    for p in rnd.sample(acervo[:100], 4):
        dup = {**p, "data_entrada": next(t).isoformat(timespec="minutes")}
        dup.pop("servidor", None)
        fila.append(dup)

    rnd.shuffle(fila)
    horarios = sorted(p["data_entrada"] for p in fila)
    for p, h in zip(fila, horarios):
        p["data_entrada"] = h

    # Itens antigos ainda visíveis na tarefa (já triados antes do marco): a extração incremental os ignora
    antigos = [{k: v for k, v in p.items() if k != "servidor"} for p in acervo[-10:]]
    return antigos + fila


def main():
    if PDF_DIR.exists():
        shutil.rmtree(PDF_DIR)
    PDF_DIR.mkdir(parents=True)
    acervo = acervo_inicial()
    fila = fila_do_dia(acervo)
    for p in acervo + fila:
        if "pdf" not in p or not (PDF_DIR / p["pdf"]).exists():
            escrever_pdf(p)
    limpar = lambda p: {k: v for k, v in p.items() if not k.startswith("_")}  # noqa: E731
    ACERVO_INICIAL_PATH.write_text(json.dumps([limpar(p) for p in acervo], ensure_ascii=False, indent=1), encoding="utf-8")
    FILA_PJE_PATH.write_text(json.dumps([limpar(p) for p in fila], ensure_ascii=False, indent=1), encoding="utf-8")
    novos = [p for p in fila if p["data_entrada"] > MARCO.isoformat()]
    print(f"Acervo inicial: {len(acervo)} | fila PJe: {len(fila)} ({len(novos)} após a última triagem) | "
          f"PDFs: {len(list(PDF_DIR.glob('*.pdf')))} em {DADOS_DIR}")


if __name__ == "__main__":
    main()
