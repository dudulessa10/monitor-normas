from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from monitor_normas.alvos import AlvoJaExiste, AlvoNaoEncontrado, RepositorioAlvos
from monitor_normas.config import ErroConfig, validar_definicao
from monitor_normas.estado import Estado

from ..contexto import Contexto, contexto
from ..esquemas import AlvoEntrada, AlvoSaida, Erro

router = APIRouter(prefix="/alvos", tags=["Alvos"])
NAO_ENCONTRADO = {404: {"model": Erro, "description": "alvo não existe"}}
INVALIDO = {422: {"model": Erro, "description": "definição inválida (ex.: regex inexistente)"}}


def _saidas(ctx: Contexto, somente: str | None = None) -> list[AlvoSaida]:
    config = ctx.config()
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        definicoes = repo.listar()
    with Estado(ctx.caminhos.estado_db) as estado:
        resumo = estado.resumo()
    saidas = []
    for definicao in definicoes:
        if somente and definicao["id"] != somente:
            continue
        alvo = config.alvo(definicao["id"])
        r = resumo.get(alvo.id, {})
        saidas.append(AlvoSaida(
            id=alvo.id, ativo=bool(definicao.get("ativo")), site=str(definicao.get("site", "")),
            categoria=str(definicao.get("categoria", "")), prioridade=definicao.get("prioridade"),
            url=str(definicao.get("url", "")), metodo=str((definicao.get("deteccao") or {}).get("metodo", "lista_itens")),
            valido=alvo.erro_config is None, erro_config=alvo.erro_config, itens_vigentes=r.get("vigentes", 0),
            ultima_execucao=r if "status" in r else None, definicao=definicao))
    return saidas


def _uma(ctx: Contexto, alvo_id: str) -> AlvoSaida:
    saidas = _saidas(ctx, alvo_id)
    if not saidas:
        raise HTTPException(404, f"alvo não encontrado: {alvo_id}")
    return saidas[0]


def _validar(ctx: Contexto, definicao: dict) -> None:
    try:
        validar_definicao(ctx.globais(), definicao)
    except ErroConfig as e:
        raise HTTPException(422, str(e))


@router.get("", response_model=list[AlvoSaida], summary="Lista os alvos")
def listar(ctx: Contexto = Depends(contexto)):
    return _saidas(ctx)


@router.get("/{alvo_id}", response_model=AlvoSaida, responses=NAO_ENCONTRADO, summary="Um alvo", name="obter_alvo")
def obter(alvo_id: str, ctx: Contexto = Depends(contexto)):
    return _uma(ctx, alvo_id)


@router.post("", response_model=AlvoSaida, status_code=201, summary="Cadastra um alvo",
             responses={409: {"model": Erro, "description": "já existe um alvo com esse id"}, **INVALIDO})
def criar(entrada: AlvoEntrada, request: Request, response: Response, ctx: Contexto = Depends(contexto)):
    definicao = entrada.definicao()
    _validar(ctx, definicao)
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        try:
            repo.criar(definicao)
        except AlvoJaExiste:
            raise HTTPException(409, f"já existe um alvo com o id {entrada.id}")
    response.headers["Location"] = request.app.url_path_for("obter_alvo", alvo_id=entrada.id)
    return _uma(ctx, entrada.id)


@router.put("/{alvo_id}", response_model=AlvoSaida, responses={**NAO_ENCONTRADO, **INVALIDO},
            summary="Substitui a definição de um alvo")
def atualizar(alvo_id: str, entrada: AlvoEntrada, ctx: Contexto = Depends(contexto)):
    if entrada.id != alvo_id:
        raise HTTPException(422, "o id de um alvo não pode ser alterado (o histórico é ligado a ele)")
    definicao = entrada.definicao()
    _validar(ctx, definicao)
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        try:
            repo.atualizar(alvo_id, definicao)
        except AlvoNaoEncontrado:
            raise HTTPException(404, f"alvo não encontrado: {alvo_id}")
    return _uma(ctx, alvo_id)


@router.delete("/{alvo_id}", status_code=204, responses=NAO_ENCONTRADO,
               summary="Remove um alvo (o histórico e o ledger são mantidos)")
def apagar(alvo_id: str, ctx: Contexto = Depends(contexto)):
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        try:
            repo.apagar(alvo_id)
        except AlvoNaoEncontrado:
            raise HTTPException(404, f"alvo não encontrado: {alvo_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _definir_ativo(ctx: Contexto, alvo_id: str, ativo: bool) -> AlvoSaida:
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        try:
            definicao = repo.obter(alvo_id)
            if ativo:
                try:
                    validar_definicao(ctx.globais(), definicao)
                except ErroConfig as e:
                    raise HTTPException(422, f"corrija a definição antes de ativar: {e}")
            repo.definir_ativo(alvo_id, ativo)
        except AlvoNaoEncontrado:
            raise HTTPException(404, f"alvo não encontrado: {alvo_id}")
    return _uma(ctx, alvo_id)


@router.post("/{alvo_id}/ativar", response_model=AlvoSaida, responses={**NAO_ENCONTRADO, **INVALIDO},
             summary="Ativa um alvo (passa a rodar)")
def ativar(alvo_id: str, ctx: Contexto = Depends(contexto)):
    return _definir_ativo(ctx, alvo_id, True)


@router.post("/{alvo_id}/desativar", response_model=AlvoSaida, responses=NAO_ENCONTRADO,
             summary="Desativa um alvo (deixa de rodar)")
def desativar(alvo_id: str, ctx: Contexto = Depends(contexto)):
    return _definir_ativo(ctx, alvo_id, False)
