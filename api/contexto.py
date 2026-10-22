"""O que as rotas precisam: caminhos, configuração e executor (injetados via Depends)."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from monitor_normas.alvos import carregar_config_banco
from monitor_normas.config import Config, Globais, carregar_globais
from monitor_normas.execucao import Caminhos

from .executor import Executor


@dataclass
class Contexto:
    caminhos: Caminhos
    caminho_yaml: Path
    executor: Executor

    def config(self) -> Config:
        return carregar_config_banco(self.caminho_yaml, self.caminhos.estado_db)

    def globais(self) -> Globais:
        return carregar_globais(self.caminho_yaml)


def contexto(request: Request) -> Contexto:
    return request.app.state.contexto
