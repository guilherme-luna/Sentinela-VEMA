"""Número único de processo no padrão CNJ (Resolução CNJ 65/2008).

Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
"""
import re

PADRAO = re.compile(r"^(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})$")


def digito_verificador(sequencial: str, ano: str, justica: str, tribunal: str, origem: str) -> str:
    base = int(f"{sequencial}{ano}{justica}{tribunal}{origem}00")
    return f"{98 - (base % 97):02d}"


def montar(sequencial: int, ano: int, origem: str = "0001", justica: str = "8", tribunal: str = "06") -> str:
    seq = f"{sequencial:07d}"
    dv = digito_verificador(seq, str(ano), justica, tribunal, origem)
    return f"{seq}-{dv}.{ano}.{justica}.{tribunal}.{origem}"


def normalizar(numero: str) -> str:
    """Aceita o número com ou sem máscara e devolve no formato CNJ."""
    digitos = re.sub(r"\D", "", numero or "")
    if len(digitos) != 20:
        raise ValueError(f"Número de processo inválido: {numero!r}")
    return f"{digitos[:7]}-{digitos[7:9]}.{digitos[9:13]}.{digitos[13]}.{digitos[14:16]}.{digitos[16:]}"


def valido(numero: str) -> bool:
    try:
        m = PADRAO.match(normalizar(numero))
    except ValueError:
        return False
    seq, dv, ano, j, tr, orig = m.groups()
    return digito_verificador(seq, ano, j, tr, orig) == dv


def paridade(numero: str) -> str:
    """Paridade usada pela vara: o dígito verificador (ex.: 3115920-52... é par)."""
    dv = int(normalizar(numero)[8:10])
    return "par" if dv % 2 == 0 else "impar"
