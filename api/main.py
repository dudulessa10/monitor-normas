"""Aplicação FastAPI: API REST em /api/v1 e o frontend estático em /."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from monitor_normas import __version__
from monitor_normas.coleta import Coletor
from monitor_normas.config import ErroConfig
from monitor_normas.execucao import Caminhos, caminhos_padrao, handler_log

from .autenticacao import credenciais_do_ambiente, exigir_senha
from .contexto import Contexto
from .executor import Executor
from .rotas import alvos, consultas, execucoes, saude

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"
PREFIXO = "/api/v1"

DESCRICAO = """
API do robô que vigia páginas de legislação (começando pela ANAC) e registra as
mudanças num ledger encadeado. As execuções feitas pela CLI e pelo agendamento
diário aparecem no mesmo histórico.

Erros vêm como `{"detail": "mensagem"}`. Listas são paginadas com `limite` e `deslocamento`.
"""


def criar_app(base: Path | None = None, *, fabrica_coletor: Callable[[], Coletor] | None = None,
              registrar_log: bool = True, credenciais: tuple[str, str] | None = None) -> FastAPI:
    """base: pasta com alvos.yaml, dados/, relatorios/ e logs/.

    Sem base: alvos.yaml da pasta do projeto, e dados/ em MONITOR_NORMAS_BASE se definida.
    credenciais: (usuário, senha) exigidos em tudo menos /saude; padrão: MONITOR_NORMAS_SENHA.
    """
    caminhos = Caminhos(Path(base).resolve()) if base else caminhos_padrao(RAIZ)
    caminho_yaml = Path(base or RAIZ).resolve() / "alvos.yaml"
    ctx = Contexto(caminhos, caminho_yaml, executor=None)  # type: ignore[arg-type]
    ctx.executor = Executor(caminhos, ctx.config, fabrica_coletor)
    if registrar_log:
        _configurar_log(caminhos)

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        orfas = ctx.executor.interromper_orfas()
        if orfas:
            logging.getLogger(__name__).warning("%d rodada(s) interrompida(s) encontradas ao iniciar", orfas)
        yield

    app = FastAPI(title="Monitor de Normas", version=__version__, description=DESCRICAO, lifespan=ciclo_de_vida,
                  docs_url="/docs", redoc_url=None)
    app.state.contexto = ctx

    @app.exception_handler(ErroConfig)
    async def erro_config(request: Request, erro: ErroConfig):
        return JSONResponse(status_code=500, content={"detail": f"configuração inválida: {erro}"})

    credenciais = credenciais or credenciais_do_ambiente()
    if credenciais:
        exigir_senha(app, *credenciais, livres={f"{PREFIXO}/saude"})

    for modulo in (alvos, execucoes, consultas, saude):
        app.include_router(modulo.router, prefix=PREFIXO)
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")  # depois das rotas da API
    return app


def _configurar_log(caminhos: Caminhos) -> None:
    """Execuções disparadas pela web vão para o mesmo logs/monitor.log da CLI."""
    handler = handler_log(caminhos)
    logger = logging.getLogger("monitor_normas")
    if any(getattr(h, "baseFilename", None) == handler.baseFilename for h in logger.handlers):
        handler.close()
        return
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
