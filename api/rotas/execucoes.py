from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response

from monitor_normas import consultas
from monitor_normas.estado import Estado
from monitor_normas.execucao import ExecucaoEmAndamento

from ..contexto import Contexto, contexto
from ..esquemas import Erro, ExecucaoDisparada, Pagina, PedidoExecucao, Rodada, StatusRodada

router = APIRouter(prefix="/execucoes", tags=["Execuções"])


@router.post("", response_model=ExecucaoDisparada, status_code=202,
             summary="Dispara uma execução em segundo plano",
             description="Responde na hora com o id da rodada; acompanhe em GET /execucoes/{id}.",
             responses={404: {"model": Erro, "description": "alvo não existe"},
                        409: {"model": Erro, "description": "outra execução (web, CLI ou agendada) em andamento"}})
def disparar(request: Request, response: Response, pedido: PedidoExecucao | None = Body(None),
             ctx: Contexto = Depends(contexto)):
    alvo = pedido.alvo if pedido else None
    try:
        rodada_id = ctx.executor.disparar(alvo)
    except KeyError:
        raise HTTPException(404, f"alvo não encontrado: {alvo}")
    except ExecucaoEmAndamento:
        raise HTTPException(409, "já existe uma execução em andamento; aguarde ela terminar")
    url = request.app.url_path_for("obter_rodada", rodada_id=str(rodada_id))
    response.headers["Location"] = url
    return ExecucaoDisparada(rodada_id=rodada_id, url=url)


@router.get("", response_model=Pagina[Rodada], summary="Histórico de execuções (mais recentes primeiro)")
def listar(limite: int = Query(50, ge=1, le=500), deslocamento: int = Query(0, ge=0),
           status: StatusRodada | None = None, ctx: Contexto = Depends(contexto)):
    total, itens = consultas.rodadas(ctx.caminhos, limite, deslocamento, status)
    return {"total": total, "limite": limite, "deslocamento": deslocamento, "itens": itens}


@router.get("/{rodada_id}", response_model=Rodada, responses={404: {"model": Erro}}, summary="Uma rodada",
            name="obter_rodada")
def obter(rodada_id: int, ctx: Contexto = Depends(contexto)):
    with Estado(ctx.caminhos.estado_db) as estado:
        rodada = estado.obter_rodada(rodada_id)
    if rodada is None:
        raise HTTPException(404, f"rodada não encontrada: {rodada_id}")
    return rodada
