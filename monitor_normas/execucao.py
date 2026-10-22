"""Orquestração: roda os alvos, atualiza estado e ledger. Erro em um alvo não afeta os outros."""

import logging
import logging.handlers
import os
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .ancora import ancorar, formatar
from .coleta import Coletor, ErroColeta
from .config import Alvo, Config, ErroConfig
from .deteccao import ALTERADO, LINHA_BASE, NOVO, REMOVIDO, Mudanca, comparar
from .estado import Estado
from .extracao import (ErroExtracao, Item, data_modificacao_pagina, desambiguar, extrair_linhas,
                       item_data_modificacao, item_hash_conteudo, montar_itens)
from .ledger import Ledger
from .palavras_chave import palavras_do_item

log = logging.getLogger(__name__)


@dataclass
class Caminhos:
    """Pastas do projeto, todas relativas a uma base (por padrão, a pasta do alvos.yaml)."""
    base: Path

    @property
    def dados(self) -> Path:
        return self.base / "dados"

    @property
    def estado_db(self) -> Path:
        return self.dados / "estado.db"

    @property
    def ledger(self) -> Path:
        return self.dados / "ledger.jsonl"

    @property
    def trava(self) -> Path:
        return self.dados / "monitor.lock"

    @property
    def relatorios(self) -> Path:
        return self.base / "relatorios"

    @property
    def logs(self) -> Path:
        return self.base / "logs"


VARIAVEL_BASE = "MONITOR_NORMAS_BASE"  # dados/, relatorios/ e logs/ fora da pasta do código (servidor)


def caminhos_padrao(pasta_projeto: Path) -> Caminhos:
    """A pasta de MONITOR_NORMAS_BASE, se definida; senão a pasta do projeto."""
    return Caminhos(Path(os.environ.get(VARIAVEL_BASE) or pasta_projeto).resolve())


def handler_log(caminhos: Caminhos) -> logging.Handler:
    """Arquivo logs/monitor.log, compartilhado pela CLI e pelo servidor.

    Fora do Windows o arquivo é reaberto se o logrotate o mover (os dois processos escrevem nele).
    """
    caminhos.logs.mkdir(parents=True, exist_ok=True)
    arquivo = caminhos.logs / "monitor.log"
    if os.name == "nt":
        handler: logging.Handler = logging.FileHandler(arquivo, encoding="utf-8")
    else:
        handler = logging.handlers.WatchedFileHandler(arquivo, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    return handler


@dataclass
class ResultadoAlvo:
    alvo: Alvo
    status: str  # ok | linha_base | erro
    mudancas: list[Mudanca] = field(default_factory=list)
    total: int = 0
    modificacao_pagina: str | None = None
    erro: str | None = None
    avisos: list[str] = field(default_factory=list)

    def contar(self, tipo: str) -> int:
        return sum(1 for m in self.mudancas if m.tipo == tipo)


class ExecucaoEmAndamento(Exception):
    """Outra execução (agendada ou manual) está usando o mesmo estado e ledger."""


class Trava:
    """Trava de arquivo entre processos (CLI, agendamento, servidor web).

    O sistema a libera mesmo se o processo morrer. Pode ser adquirida numa thread e
    liberada em outra (o servidor web adquire na requisição e libera na thread da execução).
    """

    def __init__(self, caminho: Path):
        self.caminho = caminho
        self._arquivo = None

    @property
    def adquirida(self) -> bool:
        return self._arquivo is not None

    def adquirir(self) -> "Trava":
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = open(self.caminho, "a+b")
        try:
            if os.name == "nt":
                import msvcrt
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            arquivo.close()
            raise ExecucaoEmAndamento(f"outra execução está em andamento ({self.caminho})")
        self._arquivo = arquivo
        return self

    def liberar(self) -> None:
        arquivo, self._arquivo = self._arquivo, None
        if arquivo is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                arquivo.seek(0)
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            arquivo.close()

    def livre(self) -> bool:
        """True se ninguém está com a trava (testa adquirindo e liberando)."""
        try:
            Trava(self.caminho).adquirir().liberar()
            return True
        except ExecucaoEmAndamento:
            return False


@contextmanager
def trava_exclusiva(caminho: Path):
    trava = Trava(caminho).adquirir()
    try:
        yield trava
    finally:
        trava.liberar()


def agora_local() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def selecionar_alvos(config: Config, alvo_id: str | None = None) -> list[Alvo]:
    if alvo_id:
        return [config.alvo(alvo_id)]  # KeyError se não existir
    return [a for a in config.alvos if a.ativo]


def executar(config: Config, caminhos: Caminhos, *, alvo_id: str | None = None,
             coletor: Coletor | None = None, relogio: Callable[[], datetime] = agora_local,
             rodada_id: int | None = None, travar: bool = True) -> list[ResultadoAlvo]:
    """Roda os alvos. travar=False quando quem chama já tem a Trava (ver rodada.rodar)."""
    alvos = selecionar_alvos(config, alvo_id)
    coletor = coletor or Coletor()
    ledger = Ledger(caminhos.ledger)
    resultados = []
    with (trava_exclusiva(caminhos.trava) if travar else nullcontext()), Estado(caminhos.estado_db) as estado:
        for alvo in alvos:
            resultados.append(processar_alvo(alvo, config, coletor, estado, ledger, relogio, rodada_id))
        registrar_ancora(ledger, relogio())
    return resultados


def registrar_ancora(ledger: Ledger, quando: datetime) -> None:
    try:
        ancora, verificacao = ancorar(ledger, quando)
    except Exception:  # noqa: BLE001 - a âncora não pode desfazer a execução
        log.exception("não foi possível registrar a âncora do ledger")
        return
    if ancora is None and not verificacao.ok:
        log.error("ledger NÃO ancorado: %d problema(s) de integridade: %s", len(verificacao.erros),
                  "; ".join(verificacao.erros[:3]))
    elif ancora is not None:
        log.info("âncora do ledger: %s", formatar(ancora["indice"], ancora["hash"]))


def processar_alvo(alvo: Alvo, config: Config, coletor: Coletor, estado: Estado, ledger: Ledger,
                   relogio: Callable[[], datetime] = agora_local, rodada_id: int | None = None) -> ResultadoAlvo:
    inicio = relogio()
    log.info("alvo %s: início", alvo.id)
    try:
        if alvo.erro_config:
            raise ErroConfig(alvo.erro_config)
        if alvo.opcoes.get("baixar_arquivos"):
            log.warning("alvo %s: baixar_arquivos ainda não é suportado; só as referências são guardadas", alvo.id)

        atuais, origens, modificacao, avisos = coletar_itens(alvo, config, coletor, inicio.date())
        anteriores = estado.itens_vigentes(alvo.id)

        if estado.tem_linha_base(alvo.id):
            verificar_paginas_vazias(atuais, anteriores, origens)
            mudancas = comparar(atuais, anteriores, origens)
            status = "ok"
        else:
            mudancas = [Mudanca(LINHA_BASE, item) for item in atuais]
            status = "linha_base"

        fim = relogio()
        resultado = ResultadoAlvo(alvo, status, mudancas, len(atuais), modificacao, avisos=avisos)
        # Estado e ledger andam juntos: o ledger é gravado por último dentro da transação, e se ele
        # ou o commit falharem, a transação é desfeita e o que entrou no ledger é cortado.
        posicao_ledger = ledger.tamanho()
        try:
            with estado.con:
                estado.salvar_itens(alvo.id, atuais, mudancas, fim.isoformat())
                estado.registrar_execucao(
                    alvo.id, inicio=inicio.isoformat(), fim=fim.isoformat(), status=status, total=len(atuais),
                    novos=resultado.contar(NOVO), alterados=resultado.contar(ALTERADO),
                    removidos=resultado.contar(REMOVIDO), modificacao_pagina=modificacao, rodada_id=rodada_id)
                if alvo.opcoes.get("registrar_no_ledger", True):
                    ledger.anexar([registro_ledger(alvo, m, config.palavras_chave, fim) for m in mudancas])
        except BaseException:
            ledger.desfazer(posicao_ledger)
            raise
        for aviso in avisos:
            log.warning("alvo %s: %s", alvo.id, aviso)
        log.info("alvo %s: %s, %d itens, %d mudanças", alvo.id, status, len(atuais),
                 len(mudancas) if status == "ok" else 0)
        return resultado

    except Exception as e:  # noqa: BLE001 - um alvo com problema não pode parar os outros
        mensagem = str(e) if isinstance(e, (ErroColeta, ErroExtracao, ErroConfig)) else f"{type(e).__name__}: {e}"
        log.error("alvo %s: %s", alvo.id, mensagem, exc_info=not isinstance(e, (ErroColeta, ErroExtracao, ErroConfig)))
        try:
            with estado.con:
                estado.registrar_execucao(alvo.id, inicio=inicio.isoformat(), fim=relogio().isoformat(),
                                          status="erro", erro=mensagem, rodada_id=rodada_id)
        except Exception:  # noqa: BLE001
            log.exception("alvo %s: não foi possível registrar o erro no estado", alvo.id)
        return ResultadoAlvo(alvo, "erro", erro=mensagem)


def coletar_itens(alvo: Alvo, config: Config, coletor: Coletor,
                  hoje: date) -> tuple[list[Item], set[str], str | None, list[str]]:
    """Baixa as páginas do alvo e devolve (itens, URLs coletadas, última modificação, avisos)."""
    urls = alvo.urls(hoje)
    opcoes = alvo.opcoes
    itens: list[Item] = []
    origens: set[str] = set()
    modificacoes: list[str] = []
    avisos: list[str] = []

    for url in urls:
        try:
            html = coletor.baixar(url, user_agent=opcoes["user_agent"], timeout=opcoes["timeout_segundos"],
                                  tentativas=opcoes["tentativas"], pausa=opcoes["pausa_entre_requisicoes_segundos"])
        except ErroColeta as e:
            # Na virada do ano a página do ano novo pode ainda não existir.
            if e.status == 404 and alvo.usa_ano and len(urls) > 1:
                avisos.append(f"página ainda não existe, ignorada: {url}")
                continue
            raise
        origens.add(url)
        modificacao = data_modificacao_pagina(html, config.regex.get("data_modificacao"))
        if modificacao:
            modificacoes.append(modificacao)

        if alvo.metodo == "lista_itens":
            linhas = extrair_linhas(html, url, tabela=alvo.tabela, colunas=alvo.colunas)
            itens.extend(montar_itens(linhas, alvo, config.regex, url))
        elif alvo.metodo == "hash_conteudo":
            itens.append(item_hash_conteudo(html, url, alvo.categoria))
        else:
            itens.append(item_data_modificacao(html, url, config.regex.get("data_modificacao"), alvo.categoria))

    if not origens:
        raise ErroColeta("nenhuma página do alvo pôde ser baixada")
    avisos.extend(desambiguar(itens, alvo.chave_item))
    ultima = max(modificacoes, key=_ordem_modificacao) if modificacoes else None
    return itens, origens, ultima, avisos


def _ordem_modificacao(texto: str) -> str:
    # "14/10/2026 11h13" -> "2026-10-14 11h13" para ordenar
    partes = texto.split()
    d = partes[0].split("/") if partes else []
    return f"{d[2]}-{d[1]}-{d[0]} {' '.join(partes[1:])}" if len(d) == 3 else texto


def verificar_paginas_vazias(atuais: list[Item], anteriores: dict[str, dict], origens: set[str]) -> None:
    """Se uma página que tinha itens vier vazia, aborta em vez de marcar tudo como REMOVIDO."""
    por_origem = {o: 0 for o in origens}
    for item in atuais:
        por_origem[item.origem] = por_origem.get(item.origem, 0) + 1
    for origem in origens:
        antes = sum(1 for a in anteriores.values() if a["origem"] == origem)
        if antes and not por_origem[origem]:
            raise ErroExtracao(f"{origem} veio sem itens, mas havia {antes}; nada foi alterado no estado")


def registro_ledger(alvo: Alvo, mudanca: Mudanca, palavras_globais: list[str], quando: datetime) -> dict:
    item = mudanca.item
    return {
        "timestamp": quando.isoformat(),
        "alvo": alvo.id,
        "tipo_mudanca": mudanca.tipo,
        "norma": item.chave,
        "link": item.link,
        "data_publicacao": item.data_publicacao or item.data_norma,
        "ementa": item.ementa,
        "palavras_chave": palavras_do_item(item, palavras_globais),
    }
