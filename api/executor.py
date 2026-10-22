"""Dispara rodadas em segundo plano sem prender a requisição."""

import logging
import threading
from typing import Callable

from monitor_normas.coleta import Coletor
from monitor_normas.config import Config
from monitor_normas.estado import EM_ANDAMENTO, Estado
from monitor_normas.execucao import Caminhos, Trava, agora_local
from monitor_normas.rodada import rodar

log = logging.getLogger(__name__)


class Executor:
    def __init__(self, caminhos: Caminhos, carregar_config: Callable[[], Config],
                 fabrica_coletor: Callable[[], Coletor] | None = None):
        self.caminhos = caminhos
        self.carregar_config = carregar_config
        self.fabrica_coletor = fabrica_coletor
        self._thread: threading.Thread | None = None

    def disparar(self, alvo_id: str | None) -> int:
        """Cria a rodada e a executa numa thread.

        A trava é adquirida aqui, na requisição, para que uma execução simultânea (web, CLI ou
        agendamento) dê ExecucaoEmAndamento na hora (HTTP 409). Levanta KeyError se o alvo não existe.
        """
        config = self.carregar_config()
        if alvo_id:
            config.alvo(alvo_id)
        trava = Trava(self.caminhos.trava).adquirir()
        try:
            with Estado(self.caminhos.estado_db) as estado:
                rodada_id = estado.criar_rodada("web", alvo_id, agora_local().isoformat())
            thread = threading.Thread(target=self._rodar, args=(config, alvo_id, trava, rodada_id),
                                      name=f"rodada-{rodada_id}", daemon=True)
            thread.start()
        except BaseException:
            trava.liberar()
            raise
        self._thread = thread
        return rodada_id

    def _rodar(self, config: Config, alvo_id: str | None, trava: Trava, rodada_id: int) -> None:
        try:
            coletor = self.fabrica_coletor() if self.fabrica_coletor else None
            rodar(config, self.caminhos, alvo_id=alvo_id, origem="web", trava=trava, rodada_id=rodada_id,
                  coletor=coletor)
        except Exception as e:  # noqa: BLE001 - a thread não tem a quem propagar
            log.exception("rodada %d falhou", rodada_id)
            with Estado(self.caminhos.estado_db) as estado:
                rodada = estado.obter_rodada(rodada_id)
                if rodada and rodada["status"] == EM_ANDAMENTO:
                    estado.finalizar_rodada(rodada_id, agora_local().isoformat(), "falhou",
                                            f"{type(e).__name__}: {e}")
        finally:
            trava.liberar()

    def esperar(self, timeout: float | None = None) -> None:
        """Espera a última rodada disparada terminar (usado nos testes)."""
        if self._thread is not None:
            self._thread.join(timeout)

    def interromper_orfas(self) -> int:
        """Ao subir o servidor: rodadas 'em_andamento' de um processo que morreu viram 'interrompida'."""
        trava = Trava(self.caminhos.trava)
        try:
            trava.adquirir()
        except Exception:  # noqa: BLE001 - alguém está rodando agora; as rodadas não são órfãs
            return 0
        try:
            with Estado(self.caminhos.estado_db) as estado:
                return estado.interromper_orfas(agora_local().isoformat())
        finally:
            trava.liberar()
