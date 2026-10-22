"""Estado persistente em SQLite: itens vistos por alvo, rodadas e histórico de execuções."""

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from .deteccao import REMOVIDO, Mudanca
from .extracao import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    alvo         TEXT NOT NULL,
    chave        TEXT NOT NULL,
    origem       TEXT,
    hash         TEXT NOT NULL,
    dados        TEXT NOT NULL,
    primeira_vez TEXT NOT NULL,
    ultima_vez   TEXT NOT NULL,
    removido_em  TEXT,
    PRIMARY KEY (alvo, chave)
);
CREATE TABLE IF NOT EXISTS execucoes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    alvo               TEXT NOT NULL,
    inicio             TEXT NOT NULL,
    fim                TEXT NOT NULL,
    status             TEXT NOT NULL,
    total              INTEGER NOT NULL DEFAULT 0,
    novos              INTEGER NOT NULL DEFAULT 0,
    alterados          INTEGER NOT NULL DEFAULT 0,
    removidos          INTEGER NOT NULL DEFAULT 0,
    modificacao_pagina TEXT,
    erro               TEXT
);
CREATE INDEX IF NOT EXISTS execucoes_alvo ON execucoes (alvo, id);
CREATE TABLE IF NOT EXISTS rodadas (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    origem  TEXT NOT NULL,      -- cli | agendamento | web | historico
    alvo    TEXT,               -- NULL = todos os alvos ativos
    inicio  TEXT NOT NULL,
    fim     TEXT,
    status  TEXT NOT NULL,      -- em_andamento | ok | com_erros | falhou | interrompida
    erro    TEXT
);
"""

# Uma rodada é uma chamada de "run" (CLI, agendamento ou web); ela tem uma execução por alvo.
EM_ANDAMENTO = "em_andamento"


class Estado:
    def __init__(self, caminho: Path):
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(caminho, timeout=30)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Bancos anteriores às rodadas: cria a coluna e agrupa o histórico em rodadas."""
        colunas = {r["name"] for r in self.con.execute("PRAGMA table_info(execucoes)")}
        if "rodada_id" in colunas:
            return
        with self.con:
            self.con.execute("ALTER TABLE execucoes ADD COLUMN rodada_id INTEGER")
            self.con.execute("CREATE INDEX IF NOT EXISTS execucoes_rodada ON execucoes (rodada_id)")
            grupo: list[sqlite3.Row] = []
            for linha in self.con.execute("SELECT * FROM execucoes ORDER BY id").fetchall():
                if grupo and _nova_rodada(grupo, linha):
                    self._rodada_historica(grupo)
                    grupo = []
                grupo.append(linha)
            if grupo:
                self._rodada_historica(grupo)

    def _rodada_historica(self, grupo: list[sqlite3.Row]) -> None:
        status = "com_erros" if any(r["status"] == "erro" for r in grupo) else "ok"
        cursor = self.con.execute(
            "INSERT INTO rodadas (origem, alvo, inicio, fim, status) VALUES ('historico', NULL, ?, ?, ?)",
            (grupo[0]["inicio"], grupo[-1]["fim"], status))
        self.con.executemany("UPDATE execucoes SET rodada_id = ? WHERE id = ?",
                             [(cursor.lastrowid, r["id"]) for r in grupo])

    def __enter__(self) -> "Estado":
        return self

    def __exit__(self, *exc) -> None:
        self.fechar()

    def fechar(self) -> None:
        self.con.close()

    def itens_vigentes(self, alvo: str) -> dict[str, dict]:
        cursor = self.con.execute(
            "SELECT chave, origem, hash, dados FROM itens WHERE alvo = ? AND removido_em IS NULL", (alvo,))
        return {r["chave"]: {"origem": r["origem"], "hash": r["hash"], "dados": json.loads(r["dados"])}
                for r in cursor}

    def tem_linha_base(self, alvo: str) -> bool:
        cursor = self.con.execute(
            "SELECT 1 FROM execucoes WHERE alvo = ? AND status IN ('ok', 'linha_base') LIMIT 1", (alvo,))
        return cursor.fetchone() is not None

    def salvar_itens(self, alvo: str, atuais: list[Item], mudancas: list[Mudanca], agora: str) -> None:
        """Grava os itens vistos agora e marca os removidos. Não faz commit."""
        self.con.executemany(
            """INSERT INTO itens (alvo, chave, origem, hash, dados, primeira_vez, ultima_vez)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (alvo, chave) DO UPDATE SET
                   origem = excluded.origem, hash = excluded.hash, dados = excluded.dados,
                   ultima_vez = excluded.ultima_vez, removido_em = NULL""",
            [(alvo, i.chave, i.origem, i.hash, json.dumps(asdict(i), ensure_ascii=False), agora, agora)
             for i in atuais])
        self.con.executemany(
            "UPDATE itens SET removido_em = ? WHERE alvo = ? AND chave = ?",
            [(agora, alvo, m.item.chave) for m in mudancas if m.tipo == REMOVIDO])

    def registrar_execucao(self, alvo: str, *, inicio: str, fim: str, status: str, total: int = 0,
                           novos: int = 0, alterados: int = 0, removidos: int = 0,
                           modificacao_pagina: str | None = None, erro: str | None = None,
                           rodada_id: int | None = None) -> None:
        """Registra uma execução. Não faz commit."""
        self.con.execute(
            """INSERT INTO execucoes (alvo, inicio, fim, status, total, novos, alterados, removidos,
                                      modificacao_pagina, erro, rodada_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alvo, inicio, fim, status, total, novos, alterados, removidos, modificacao_pagina, erro, rodada_id))

    # ------------------------------------------------------------ rodadas

    def criar_rodada(self, origem: str, alvo: str | None, inicio: str) -> int:
        with self.con:
            cursor = self.con.execute("INSERT INTO rodadas (origem, alvo, inicio, status) VALUES (?, ?, ?, ?)",
                                      (origem, alvo, inicio, EM_ANDAMENTO))
        return cursor.lastrowid

    def finalizar_rodada(self, rodada_id: int, fim: str, status: str, erro: str | None = None) -> None:
        with self.con:
            self.con.execute("UPDATE rodadas SET fim = ?, status = ?, erro = ? WHERE id = ?",
                             (fim, status, erro, rodada_id))

    def interromper_orfas(self, agora: str) -> int:
        """Rodadas que ficaram em andamento (processo morto). Só chamar com a trava livre."""
        with self.con:
            cursor = self.con.execute(
                "UPDATE rodadas SET status = 'interrompida', fim = ?, "
                "erro = 'o processo terminou antes de concluir a execução' WHERE status = ?", (agora, EM_ANDAMENTO))
        return cursor.rowcount

    def listar_rodadas(self, limite: int = 50, deslocamento: int = 0,
                       status: str | None = None) -> tuple[int, list[dict]]:
        filtro, parametros = ("WHERE status = ?", [status]) if status else ("", [])
        total = self.con.execute(f"SELECT COUNT(*) FROM rodadas {filtro}", parametros).fetchone()[0]
        linhas = self.con.execute(f"SELECT * FROM rodadas {filtro} ORDER BY id DESC LIMIT ? OFFSET ?",
                                  [*parametros, limite, deslocamento]).fetchall()
        return total, [self._rodada_completa(r) for r in linhas]

    def obter_rodada(self, rodada_id: int) -> dict | None:
        linha = self.con.execute("SELECT * FROM rodadas WHERE id = ?", (rodada_id,)).fetchone()
        return self._rodada_completa(linha) if linha else None

    def _rodada_completa(self, linha: sqlite3.Row) -> dict:
        rodada = dict(linha)
        rodada["execucoes"] = [dict(r) for r in self.con.execute(
            "SELECT id, alvo, inicio, fim, status, total, novos, alterados, removidos, modificacao_pagina, erro "
            "FROM execucoes WHERE rodada_id = ? ORDER BY id", (rodada["id"],))]
        for campo in ("total", "novos", "alterados", "removidos"):
            rodada[campo] = sum(e[campo] for e in rodada["execucoes"])
        rodada["erros"] = sum(1 for e in rodada["execucoes"] if e["status"] == "erro")
        return rodada

    def listar_itens(self, alvo: str | None = None) -> list[dict]:
        """Itens vigentes (não removidos), com as datas em que foram vistos."""
        sql = "SELECT alvo, chave, dados, primeira_vez, ultima_vez FROM itens WHERE removido_em IS NULL"
        parametros: list = []
        if alvo:
            sql += " AND alvo = ?"
            parametros.append(alvo)
        return [{"alvo": r["alvo"], "chave": r["chave"], "dados": json.loads(r["dados"]),
                 "primeira_vez": r["primeira_vez"], "ultima_vez": r["ultima_vez"]}
                for r in self.con.execute(sql + " ORDER BY alvo, ultima_vez DESC, chave", parametros)]

    def resumo(self) -> dict[str, dict]:
        """Última execução e quantidade de itens vigentes de cada alvo."""
        resultado: dict[str, dict] = {}
        for r in self.con.execute(
                """SELECT e.* FROM execucoes e
                   JOIN (SELECT alvo, MAX(id) AS id FROM execucoes GROUP BY alvo) u ON u.id = e.id"""):
            resultado[r["alvo"]] = dict(r)
        for r in self.con.execute(
                "SELECT alvo, COUNT(*) AS n FROM itens WHERE removido_em IS NULL GROUP BY alvo"):
            resultado.setdefault(r["alvo"], {})["vigentes"] = r["n"]
        return resultado


def _nova_rodada(grupo: list[sqlite3.Row], linha: sqlite3.Row) -> bool:
    """Execuções antigas sem rodada: começa outra se o alvo repete ou se houve uma pausa.

    Dentro de um "run" um alvo começa no mesmo segundo em que o anterior termina (a pausa entre
    requisições fica dentro da execução do alvo); mais de 3 s de intervalo é outra chamada.
    """
    if any(r["alvo"] == linha["alvo"] for r in grupo):
        return True
    try:
        return datetime.fromisoformat(linha["inicio"]) - datetime.fromisoformat(grupo[-1]["fim"]) > timedelta(seconds=3)
    except (TypeError, ValueError):
        return True
