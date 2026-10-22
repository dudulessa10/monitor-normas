"""Âncoras do ledger: detectam a reescrita completa da cadeia e o corte do final.

O encadeamento por SHA-256 só pega mudanças isoladas: quem reescrever o arquivo inteiro
pode recalcular todos os hashes, e quem apagar os últimos blocos deixa uma cadeia válida.
Por isso, a cada execução, o índice e o hash do último bloco são gravados como uma âncora
em dados/ancoras.jsonl, assinada com HMAC-SHA256. A chave fica FORA da pasta do projeto
(que está no OneDrive), em %LOCALAPPDATA%\\MonitorNormas; sem ela não dá para forjar âncoras.
As âncoras também são encadeadas, e uma cópia da última fica junto da chave, o que pega
âncoras apagadas.

Nada disso protege contra quem tem acesso a este computador (e, portanto, à chave). Para isso,
guarde a âncora fora dele (ela sai no relatório e em "monitor.py ancora") e confira depois com
"monitor.py verificar-ledger --ancora INDICE:HASH".
"""

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from pathlib import Path

from .ledger import Ledger, ResultadoVerificacao

VARIAVEL_PASTA = "MONITOR_NORMAS_PASTA_SEGURA"  # sobrescreve a pasta da chave (testes, outra máquina)
MINIMO_HEX_EXTERNA = 12


def pasta_segura() -> Path:
    if os.environ.get(VARIAVEL_PASTA):
        return Path(os.environ[VARIAVEL_PASTA])
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "MonitorNormas"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "monitor_normas"


def id_chave(chave: bytes) -> str:
    return hashlib.sha256(chave).hexdigest()[:16]


def assinar(ancora: dict, chave: bytes) -> str:
    dados = {k: ancora.get(k) for k in ("indice", "hash", "timestamp", "chave_id", "anterior")}
    mensagem = json.dumps(dados, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(chave, mensagem, hashlib.sha256).hexdigest()


def formatar(indice: int, hash_: str) -> str:
    return f"{indice}:{hash_}"


def ler_externa(texto: str) -> tuple[int, str]:
    """"1739:16981e4ac237..." -> (1739, "16981e4ac237..."). Aceita prefixo do hash (mín. 12)."""
    indice, _, hash_ = texto.strip().partition(":")
    hash_ = hash_.strip().lower()
    if not indice.strip().isdigit() or len(hash_) < MINIMO_HEX_EXTERNA or any(c not in "0123456789abcdef" for c in hash_):
        raise ValueError(f"âncora inválida: {texto!r} (use INDICE:HASH, com pelo menos {MINIMO_HEX_EXTERNA} "
                         "caracteres do hash)")
    return int(indice), hash_


class Ancoras:
    def __init__(self, ledger: Ledger, pasta: Path | None = None):
        self.ledger = ledger
        self.caminho = ledger.caminho.with_name("ancoras.jsonl")
        self.pasta = pasta or pasta_segura()
        self.arquivo_chave = self.pasta / "chave_ledger.bin"
        # Uma cópia por ledger: a mesma máquina pode ter mais de um projeto.
        ident = hashlib.sha256(str(ledger.caminho.resolve()).encode("utf-8")).hexdigest()[:12]
        self.copia_local = self.pasta / f"ultima_ancora_{ident}.json"

    # ------------------------------------------------------------ leitura

    def _linhas(self) -> list[tuple[int, dict | None]]:
        if not self.caminho.exists():
            return []
        linhas = []
        with self.caminho.open(encoding="utf-8") as f:
            for numero, linha in enumerate(f, start=1):
                if linha.strip():
                    try:
                        linhas.append((numero, json.loads(linha)))
                    except json.JSONDecodeError:
                        linhas.append((numero, None))
        return linhas

    def lista(self) -> list[dict]:
        return [a for _, a in self._linhas() if a is not None]

    def ultima(self) -> dict | None:
        lista = self.lista()
        return lista[-1] if lista else None

    def _chave(self, criar: bool) -> bytes | None:
        if self.arquivo_chave.exists():
            return self.arquivo_chave.read_bytes()
        if not criar:
            return None
        self.pasta.mkdir(parents=True, exist_ok=True)
        chave = secrets.token_bytes(32)
        with open(self.arquivo_chave, "xb") as f:  # "x": nunca sobrescreve uma chave existente
            f.write(chave)
        if os.name != "nt":
            os.chmod(self.arquivo_chave, 0o600)
        return chave

    # ------------------------------------------------------------ escrita

    def registrar(self, quando: datetime) -> dict | None:
        """Ancora o último bloco do ledger (se ainda não estiver). Não verifica o ledger: ver ancorar()."""
        indice, hash_ = self.ledger.ultimo()
        if indice < 0:
            return None
        ultima = self.ultima()
        if ultima and ultima.get("indice") == indice and ultima.get("hash") == hash_:
            return ultima
        chave = self._chave(criar=True)
        ancora = {"indice": indice, "hash": hash_, "timestamp": quando.isoformat(), "chave_id": id_chave(chave),
                  "anterior": ultima.get("hmac", "") if ultima else ""}
        ancora["hmac"] = assinar(ancora, chave)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.caminho.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(ancora) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.copia_local.write_text(json.dumps(ancora), encoding="utf-8")
        return ancora

    # ------------------------------------------------------------ verificação

    def verificar(self, externas: list[tuple[int, str]] = ()) -> tuple[list[str], list[str], int]:
        """Confere as âncoras contra o ledger. Devolve (erros, avisos, âncoras conferidas)."""
        erros: list[str] = []
        avisos: list[str] = []
        hashes = {b.get("indice"): b.get("hash") for b in self.ledger.blocos()}
        ultimo = max((i for i in hashes if isinstance(i, int)), default=-1)
        chave = self._chave(criar=False)
        cid = id_chave(chave) if chave else None

        linhas = self._linhas()
        anterior, sem_assinatura, conferidas = "", 0, 0
        for numero, ancora in linhas:
            nome = f"âncora da linha {numero}"
            if ancora is None:
                erros.append(f"{nome}: JSON inválido")
                anterior = None
                continue
            nome += f" ({str(ancora.get('timestamp'))[:10]})"
            if anterior is not None and ancora.get("anterior") != anterior:
                erros.append(f"{nome}: encadeamento das âncoras não confere (âncora apagada, inserida ou alterada)")
            anterior = ancora.get("hmac")
            if cid is None or ancora.get("chave_id") != cid:
                sem_assinatura += 1
            elif not hmac.compare_digest(assinar(ancora, chave), str(ancora.get("hmac") or "")):
                erros.append(f"{nome}: assinatura inválida (arquivo de âncoras alterado)")
            erros += _conferir(nome, ancora.get("indice"), str(ancora.get("hash") or ""), hashes, ultimo)
            conferidas += 1

        if sem_assinatura:
            avisos.append(f"{sem_assinatura} âncora(s) com assinatura não conferida: a chave "
                          f"{self.arquivo_chave} não existe ou é de outra máquina")
        if not linhas and hashes:
            avisos.append("o ledger ainda não tem âncoras; a próxima execução ou 'monitor.py ancora' cria a primeira")

        copia = self._ler_copia_local()
        if copia and not any(a and a.get("hmac") == copia.get("hmac") for _, a in linhas):
            erros.append(f"a última âncora gravada neste computador (bloco {copia.get('indice')}, "
                         f"{str(copia.get('timestamp'))[:10]}) não está em {self.caminho.name}: âncoras apagadas "
                         f"ou substituídas (se você apagou os dados de propósito, apague também {self.copia_local})")
            erros += _conferir("cópia local da última âncora", copia.get("indice"), str(copia.get("hash") or ""),
                               hashes, ultimo)

        for indice, prefixo in externas:
            erros += _conferir(f"âncora externa {indice}:{prefixo[:12]}…", indice, prefixo, hashes, ultimo)
            conferidas += 1
        return erros, avisos, conferidas

    def _ler_copia_local(self) -> dict | None:
        try:
            return json.loads(self.copia_local.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None


def _conferir(nome: str, indice, hash_: str, hashes: dict, ultimo: int) -> list[str]:
    if not isinstance(indice, int) or not hash_:
        return [f"{nome}: sem índice ou hash"]
    if indice > ultimo:
        return [f"{nome}: registra o bloco {indice}, mas o ledger termina no bloco {ultimo} "
                "(blocos apagados do final)"]
    if not str(hashes.get(indice) or "").startswith(hash_):
        return [f"{nome}: o bloco {indice} não confere com a âncora (ledger reescrito)"]
    return []


def verificar_tudo(ledger: Ledger, externas: list[tuple[int, str]] = ()) -> ResultadoVerificacao:
    """Cadeia de hashes + âncoras."""
    resultado = ledger.verificar()
    erros, avisos, conferidas = Ancoras(ledger).verificar(externas)
    resultado.erros += erros
    resultado.avisos += avisos
    resultado.ancoras = conferidas
    return resultado


def ancorar(ledger: Ledger, quando: datetime) -> tuple[dict | None, ResultadoVerificacao]:
    """Ancora o ledger só se a verificação completa passar (não abençoa um ledger adulterado)."""
    verificacao = verificar_tudo(ledger)
    if not verificacao.ok:
        return None, verificacao
    return Ancoras(ledger).registrar(quando), verificacao
