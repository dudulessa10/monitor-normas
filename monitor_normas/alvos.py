"""Alvos no SQLite (tabela "alvos" do estado.db).

A definição de cada alvo é o mesmo dicionário que ficava no alvos.yaml (url, anos,
deteccao, extracao...). As configurações globais (regex, palavras-chave, padrões,
frequência e horário) continuam no YAML.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import Config, ErroConfig, carregar_globais, montar_config

SCHEMA = """
CREATE TABLE IF NOT EXISTS alvos (
    id            TEXT PRIMARY KEY,
    ativo         INTEGER NOT NULL DEFAULT 0,
    definicao     TEXT NOT NULL,      -- JSON, mesmo formato de um alvo do alvos.yaml
    criado_em     TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
"""


class AlvoNaoEncontrado(KeyError):
    pass


class AlvoJaExiste(ValueError):
    pass


def _agora() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


class RepositorioAlvos:
    def __init__(self, caminho_db: Path):
        Path(caminho_db).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(caminho_db, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def __enter__(self) -> "RepositorioAlvos":
        return self

    def __exit__(self, *exc) -> None:
        self.con.close()

    @staticmethod
    def _definicao(linha: sqlite3.Row) -> dict:
        # id e ativo vêm das colunas (fonte da verdade), não do JSON.
        return {**json.loads(linha["definicao"]), "id": linha["id"], "ativo": bool(linha["ativo"])}

    def listar(self) -> list[dict]:
        return [self._definicao(r) for r in self.con.execute("SELECT * FROM alvos ORDER BY rowid")]

    def obter(self, alvo_id: str) -> dict:
        linha = self.con.execute("SELECT * FROM alvos WHERE id = ?", (alvo_id,)).fetchone()
        if linha is None:
            raise AlvoNaoEncontrado(alvo_id)
        return self._definicao(linha)

    def existe(self, alvo_id: str) -> bool:
        return self.con.execute("SELECT 1 FROM alvos WHERE id = ?", (alvo_id,)).fetchone() is not None

    def contar(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM alvos").fetchone()[0]

    def criar(self, definicao: dict) -> dict:
        alvo_id = str(definicao.get("id") or "")
        if not alvo_id:
            raise ErroConfig("alvo sem id")
        agora = _agora()
        try:
            with self.con:
                self.con.execute(
                    "INSERT INTO alvos (id, ativo, definicao, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?)",
                    (alvo_id, int(bool(definicao.get("ativo"))), _json(definicao), agora, agora))
        except sqlite3.IntegrityError:
            raise AlvoJaExiste(alvo_id)
        return self.obter(alvo_id)

    def atualizar(self, alvo_id: str, definicao: dict) -> dict:
        if str(definicao.get("id", alvo_id)) != alvo_id:
            raise ErroConfig("o id de um alvo não pode ser alterado (o histórico é ligado a ele)")
        with self.con:
            cursor = self.con.execute(
                "UPDATE alvos SET ativo = ?, definicao = ?, atualizado_em = ? WHERE id = ?",
                (int(bool(definicao.get("ativo"))), _json({**definicao, "id": alvo_id}), _agora(), alvo_id))
        if cursor.rowcount == 0:
            raise AlvoNaoEncontrado(alvo_id)
        return self.obter(alvo_id)

    def definir_ativo(self, alvo_id: str, ativo: bool) -> dict:
        definicao = self.obter(alvo_id)
        return self.atualizar(alvo_id, {**definicao, "ativo": ativo})

    def apagar(self, alvo_id: str) -> None:
        """Apaga só a definição; itens, execuções e ledger do alvo continuam no histórico."""
        with self.con:
            cursor = self.con.execute("DELETE FROM alvos WHERE id = ?", (alvo_id,))
        if cursor.rowcount == 0:
            raise AlvoNaoEncontrado(alvo_id)

    def importar(self, definicoes: list[dict], substituir: bool = False) -> tuple[list[str], list[str]]:
        """Carga a partir do YAML. Devolve (importados, ignorados por já existirem)."""
        importados, ignorados = [], []
        for definicao in definicoes:
            alvo_id = str(definicao.get("id") or "")
            if not alvo_id:
                raise ErroConfig("há um alvo sem id no YAML")
            if self.existe(alvo_id):
                if not substituir:
                    ignorados.append(alvo_id)
                    continue
                self.atualizar(alvo_id, definicao)
            else:
                self.criar(definicao)
            importados.append(alvo_id)
        return importados, ignorados


def _json(definicao: dict) -> str:
    return json.dumps({k: v for k, v in definicao.items() if k not in ("id", "ativo")}, ensure_ascii=False)


def carregar_config_banco(caminho_yaml: Path, caminho_db: Path) -> Config:
    """Configuração usada pela CLI e pela API: globais do YAML + alvos do banco."""
    globais = carregar_globais(caminho_yaml)
    with RepositorioAlvos(caminho_db) as repo:
        definicoes = repo.listar()
    return montar_config(globais, definicoes)
