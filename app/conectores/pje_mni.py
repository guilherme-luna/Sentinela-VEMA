"""Conector real do PJe via MNI (fase 2, após acesso concedido pelo TJCE).

O MNI é o serviço SOAP padrão de interoperabilidade do CNJ exposto pelo PJe, com
operações como `consultarProcesso` (capa, partes, movimentos e documentos).
A implementação de produção ficará em Java (JAX-WS), stack mantida pela TI do
tribunal, e entregará os mesmos dicionários que o PJeSimulado.
"""
from datetime import datetime


class PJeMNI:
    def __init__(self, wsdl_url: str, usuario: str, senha: str):
        self.wsdl_url, self.usuario, self.senha = wsdl_url, usuario, senha

    def buscar_novos(self, desde: datetime | None) -> list[dict]:
        raise NotImplementedError("Disponível após liberação de acesso ao MNI do TJCE.")

    def paginas_documento(self, processo: dict) -> list[str]:
        raise NotImplementedError("Disponível após liberação de acesso ao MNI do TJCE.")
