"""Persistência (SQLite no MVP; PostgreSQL + pgvector na fase 2, mesma interface).

O FastAPI atende requisições em várias threads; todo acesso à conexão passa por
um lock para evitar uso concorrente da mesma conexão SQLite.
"""
import json
import sqlite3
import threading
from datetime import datetime
from functools import wraps
from pathlib import Path

from .config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS processos (
    numero TEXT PRIMARY KEY,
    dados TEXT NOT NULL,          -- JSON com capa, partes, síntese, alertas, vínculos
    servidor TEXT,
    status TEXT NOT NULL,         -- 'acervo' (distribuído) ou 'proposta' (aguardando aprovação)
    data_entrada TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quando TEXT NOT NULL,
    acao TEXT NOT NULL,
    detalhe TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS estado (chave TEXT PRIMARY KEY, valor TEXT);
"""


def _sincronizado(metodo):
    @wraps(metodo)
    def envoltorio(self, *args, **kwargs):
        with self._lock:
            return metodo(self, *args, **kwargs)
    return envoltorio


def _linha(processo: dict, status: str) -> tuple:
    dados = {k: v for k, v in processo.items() if k != "status"}  # status vive na coluna, não no JSON
    return (processo["numero"], json.dumps(dados, ensure_ascii=False), processo.get("servidor"),
            status, processo["data_entrada"])


class Repositorio:
    def __init__(self, caminho: Path = DB_PATH):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)

    # processos
    @_sincronizado
    def salvar(self, processo: dict, status: str):
        self.salvar_varios([processo], status)

    @_sincronizado
    def salvar_varios(self, processos: list[dict], status: str):
        """Grava todos ou nenhum (uma transação)."""
        with self.con:
            self.con.executemany(
                "INSERT OR REPLACE INTO processos (numero, dados, servidor, status, data_entrada) VALUES (?,?,?,?,?)",
                [_linha(p, status) for p in processos],
            )

    @_sincronizado
    def obter(self, numero: str) -> dict | None:
        row = self.con.execute("SELECT dados, status FROM processos WHERE numero=?", (numero,)).fetchone()
        return {**json.loads(row["dados"]), "status": row["status"]} if row else None

    @_sincronizado
    def listar(self, status: str | None = None) -> list[dict]:
        sql, args = "SELECT dados, status FROM processos", ()
        if status:
            sql, args = sql + " WHERE status=?", (status,)
        rows = self.con.execute(sql + " ORDER BY data_entrada", args).fetchall()
        return [{**json.loads(r["dados"]), "status": r["status"]} for r in rows]

    @_sincronizado
    def servidor_de(self, numero: str) -> str | None:
        row = self.con.execute("SELECT servidor FROM processos WHERE numero=?", (numero,)).fetchone()
        return row["servidor"] if row else None

    @_sincronizado
    def carga_por_servidor(self) -> dict[str, int]:
        rows = self.con.execute(
            "SELECT servidor, COUNT(*) n FROM processos WHERE status='acervo' GROUP BY servidor").fetchall()
        return {r["servidor"]: r["n"] for r in rows}

    @_sincronizado
    def remover_propostas(self):
        with self.con:
            self.con.execute("DELETE FROM processos WHERE status='proposta'")

    # estado e auditoria
    @_sincronizado
    def get_estado(self, chave: str) -> str | None:
        row = self.con.execute("SELECT valor FROM estado WHERE chave=?", (chave,)).fetchone()
        return row["valor"] if row else None

    @_sincronizado
    def set_estado(self, chave: str, valor: str | None):
        with self.con:
            if valor is None:
                self.con.execute("DELETE FROM estado WHERE chave=?", (chave,))
            else:
                self.con.execute("INSERT OR REPLACE INTO estado VALUES (?,?)", (chave, valor))

    @_sincronizado
    def auditar(self, acao: str, detalhe: str):
        with self.con:
            self.con.execute("INSERT INTO auditoria (quando, acao, detalhe) VALUES (?,?,?)",
                             (datetime.now().isoformat(timespec="seconds"), acao, detalhe))

    @_sincronizado
    def auditoria(self, limite: int = 50) -> list[dict]:
        rows = self.con.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r) for r in rows]

    @_sincronizado
    def limpar(self):
        with self.con:
            self.con.execute("DELETE FROM processos")
            self.con.execute("DELETE FROM auditoria")
            self.con.execute("DELETE FROM estado")
