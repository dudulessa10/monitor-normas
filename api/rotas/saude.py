"""Rota de saúde para o monitoramento do servidor (aberta mesmo com senha)."""

from fastapi import APIRouter, Depends

from monitor_normas import __version__, consultas

from ..contexto import Contexto, contexto
from ..esquemas import Saude

router = APIRouter(tags=["Saúde"])


@router.get("/saude", response_model=Saude, summary="Servidor no ar e banco acessível")
def saude(ctx: Contexto = Depends(contexto)):
    _, rodadas = consultas.rodadas(ctx.caminhos, limite=1)
    ultima = rodadas[0] if rodadas else None
    return Saude(status="ok", versao=__version__,
                 ultima_rodada_inicio=ultima["inicio"] if ultima else None,
                 ultima_rodada_status=ultima["status"] if ultima else None)
