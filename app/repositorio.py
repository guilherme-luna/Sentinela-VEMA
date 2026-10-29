"""Persistência (SQLite no MVP; PostgreSQL + pgvector na fase 2, mesma interface)."""
import json
import sqlite3
from datetime import datetime
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


class Repositorio:
    def __init__(self, caminho: Path = DB_PATH):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(caminho, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA)

    # processos
    def salvar(self, processo: dict, status: str):
        self.con.execute(
            "INSERT OR REPLACE INTO processos (numero, dados, servidor, status, data_entrada) VALUES (?,?,?,?,?)",
            (processo["numero"], json.dumps(processo, ensure_ascii=False), processo.get("servidor"),
             status, processo["data_entrada"]),
        )
        self.con.commit()

    def obter(self, numero: str) -> dict | None:
        row = self.con.execute("SELECT dados, status FROM processos WHERE numero=?", (numero,)).fetchone()
        return {**json.loads(row["dados"]), "status": row["status"]} if row else None

    def listar(self, status: str | None = None) -> list[dict]:
        sql, args = "SELECT dados, status FROM processos", ()
        if status:
            sql, args = sql + " WHERE status=?", (status,)
        rows = self.con.execute(sql + " ORDER BY data_entrada", args).fetchall()
        return [{**json.loads(r["dados"]), "status": r["status"]} for r in rows]

    def existe(self, numero: str) -> bool:
        return self.con.execute("SELECT 1 FROM processos WHERE numero=?", (numero,)).fetchone() is not None

    def carga_por_servidor(self) -> dict[str, int]:
        rows = self.con.execute(
            "SELECT servidor, COUNT(*) n FROM processos WHERE status='acervo' GROUP BY servidor").fetchall()
        return {r["servidor"]: r["n"] for r in rows}

    def remover_propostas(self):
        self.con.execute("DELETE FROM processos WHERE status='proposta'")
        self.con.commit()

    # estado e auditoria
    def get_estado(self, chave: str) -> str | None:
        row = self.con.execute("SELECT valor FROM estado WHERE chave=?", (chave,)).fetchone()
        return row["valor"] if row else None

    def set_estado(self, chave: str, valor: str):
        self.con.execute("INSERT OR REPLACE INTO estado VALUES (?,?)", (chave, valor))
        self.con.commit()

    def auditar(self, acao: str, detalhe: str):
        self.con.execute("INSERT INTO auditoria (quando, acao, detalhe) VALUES (?,?,?)",
                         (datetime.now().isoformat(timespec="seconds"), acao, detalhe))
        self.con.commit()

    def auditoria(self, limite: int = 50) -> list[dict]:
        rows = self.con.execute("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r) for r in rows]

    def limpar(self):
        self.con.executescript("DELETE FROM processos; DELETE FROM auditoria; DELETE FROM estado;")
        self.con.commit()
