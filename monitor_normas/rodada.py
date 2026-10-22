"""Uma rodada completa: trava, execução dos alvos, relatório e conferência da âncora.

É o mesmo caminho para "monitor.py run" (CLI e agendamento) e para POST /execucoes (web),
para que as três origens se comportem igual e apareçam no mesmo histórico.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import relatorio
from .ancora import Ancoras, formatar
from .coleta import Coletor
from .config import Config
from .estado import Estado
from .execucao import Caminhos, ResultadoAlvo, Trava, agora_local, executar, selecionar_alvos
from .ledger import Ledger

ORIGENS = ("cli", "agendamento", "web")


@dataclass
class ResultadoRodada:
    rodada_id: int
    status: str  # ok | com_erros
    resultados: list[ResultadoAlvo]
    relatorio: Path | None
    ancora: str | None         # "INDICE:HASH" do último bloco, se ancorado
    alerta_ledger: str | None  # preenchido se o ledger não pôde ser ancorado


def situacao_ancora(caminhos: Caminhos) -> tuple[str | None, str | None]:
    """(âncora atual, alerta). O alerta aparece se o último bloco do ledger não está ancorado."""
    ledger = Ledger(caminhos.ledger)
    indice, hash_ = ledger.ultimo()
    if indice < 0:
        return None, None
    ultima = Ancoras(ledger).ultima()
    if ultima is not None and ultima.get("indice") == indice and ultima.get("hash") == hash_:
        return formatar(indice, hash_), None
    return None, ("o ledger não foi ancorado nesta execução por problemas de integridade; "
                  "rode 'python monitor.py verificar-ledger'")


def rodar(config: Config, caminhos: Caminhos, *, alvo_id: str | None = None, origem: str = "cli",
          trava: Trava | None = None, rodada_id: int | None = None, coletor: Coletor | None = None,
          relogio: Callable[[], datetime] = agora_local) -> ResultadoRodada:
    """Roda os alvos ativos (ou um alvo) e registra a rodada.

    trava: já adquirida por quem chama (a API adquire na requisição para responder 409 na hora);
    quem a passa também a libera. Sem trava, ela é adquirida aqui (ExecucaoEmAndamento se ocupada).
    """
    selecionar_alvos(config, alvo_id)  # KeyError antes de qualquer efeito
    propria = trava is None
    if propria:
        trava = Trava(caminhos.trava).adquirir()
    try:
        if rodada_id is None:
            with Estado(caminhos.estado_db) as estado:
                rodada_id = estado.criar_rodada(origem, alvo_id, relogio().isoformat())
        try:
            resultados = executar(config, caminhos, alvo_id=alvo_id, coletor=coletor, relogio=relogio,
                                  rodada_id=rodada_id, travar=False)
            ancora, alerta = situacao_ancora(caminhos)
            caminho = (relatorio.gerar(resultados, caminhos.relatorios, relogio(), config.palavras_chave,
                                       ancora, alerta) if resultados else None)
        except Exception as e:
            with Estado(caminhos.estado_db) as estado:
                estado.finalizar_rodada(rodada_id, relogio().isoformat(), "falhou", f"{type(e).__name__}: {e}")
            raise
        status = "com_erros" if alerta or any(r.status == "erro" for r in resultados) else "ok"
        with Estado(caminhos.estado_db) as estado:
            estado.finalizar_rodada(rodada_id, relogio().isoformat(), status, alerta)
        return ResultadoRodada(rodada_id, status, resultados, caminho, ancora, alerta)
    finally:
        if propria:
            trava.liberar()
