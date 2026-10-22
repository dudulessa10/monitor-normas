"""Ledger append-only (JSON Lines) com encadeamento por SHA-256.

Cada bloco guarda o hash do bloco anterior; o próprio hash é o SHA-256 do
bloco inteiro (incluindo hash_anterior) sem o campo "hash". Alterar ou apagar
qualquer linha quebra a cadeia, o que `verificar()` detecta. Reescrever o arquivo
inteiro recalculando os hashes, ou cortar o final, só é detectado pelas âncoras
(ancora.py).
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

GENESIS = "0" * 64
CAMPOS = ("indice", "timestamp", "alvo", "tipo_mudanca", "norma", "link", "data_publicacao",
          "ementa", "palavras_chave", "hash_anterior", "hash")


def calcular_hash(bloco: dict) -> str:
    dados = {k: v for k, v in bloco.items() if k != "hash"}
    serializado = json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serializado.encode("utf-8")).hexdigest()


@dataclass
class ResultadoVerificacao:
    total: int = 0
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)  # não invalidam o ledger
    ancoras: int = 0  # âncoras conferidas

    @property
    def ok(self) -> bool:
        return not self.erros


class Ledger:
    def __init__(self, caminho: Path):
        self.caminho = Path(caminho)

    def ultimo(self) -> tuple[int, str]:
        if not self.caminho.exists():
            return -1, GENESIS
        ultima = ""
        with self.caminho.open(encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    ultima = linha
        if not ultima:
            return -1, GENESIS
        bloco = json.loads(ultima)
        return bloco["indice"], bloco["hash"]

    def anexar(self, registros: list[dict]) -> list[dict]:
        """Acrescenta blocos. Cada registro traz os campos de timestamp a palavras_chave."""
        if not registros:
            return []
        indice, hash_anterior = self.ultimo()
        blocos = []
        for registro in registros:
            indice += 1
            bloco = {"indice": indice}
            bloco.update({k: registro.get(k) for k in CAMPOS[1:-2]})
            bloco["hash_anterior"] = hash_anterior
            bloco["hash"] = hash_anterior = calcular_hash(bloco)
            blocos.append(bloco)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open("a", encoding="utf-8", newline="\n") as f:
            for bloco in blocos:
                f.write(json.dumps(bloco, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return blocos

    def tamanho(self) -> int:
        """Posição atual do fim do arquivo, para desfazer() voltar a ela."""
        return self.caminho.stat().st_size if self.caminho.exists() else 0

    def desfazer(self, tamanho: int) -> None:
        """Corta o que foi anexado depois de tamanho(): usado quando o estado (SQLite) não pôde ser gravado."""
        if not self.caminho.exists() or self.caminho.stat().st_size <= tamanho:
            return
        with self.caminho.open("r+b") as f:
            f.truncate(tamanho)
            f.flush()
            os.fsync(f.fileno())

    def blocos(self) -> Iterator[dict]:
        """Blocos na ordem do arquivo; linhas com JSON inválido são puladas (verificar() as aponta)."""
        if not self.caminho.exists():
            return
        with self.caminho.open(encoding="utf-8") as f:
            for linha in f:
                if linha.strip():
                    try:
                        yield json.loads(linha)
                    except json.JSONDecodeError:
                        continue

    def verificar(self) -> ResultadoVerificacao:
        resultado = ResultadoVerificacao()
        if not self.caminho.exists():
            return resultado
        hash_anterior, esperado = GENESIS, 0
        with self.caminho.open(encoding="utf-8") as f:
            for numero_linha, linha in enumerate(f, start=1):
                if not linha.strip():
                    continue
                resultado.total += 1
                try:
                    bloco = json.loads(linha)
                except json.JSONDecodeError as e:
                    resultado.erros.append(f"linha {numero_linha}: JSON inválido ({e})")
                    hash_anterior, esperado = None, esperado + 1
                    continue
                if bloco.get("indice") != esperado:
                    resultado.erros.append(f"linha {numero_linha}: índice {bloco.get('indice')}, esperado {esperado}")
                if hash_anterior is not None and bloco.get("hash_anterior") != hash_anterior:
                    resultado.erros.append(f"linha {numero_linha}: hash_anterior não confere com o bloco anterior")
                if calcular_hash(bloco) != bloco.get("hash"):
                    resultado.erros.append(f"linha {numero_linha}: hash do bloco não confere (conteúdo alterado)")
                hash_anterior, esperado = bloco.get("hash"), esperado + 1
        return resultado
