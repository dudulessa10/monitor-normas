"""Leitura: mudanças, normas vigentes, ledger, configuração e exportação."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from monitor_normas import consultas, planilha
from monitor_normas.ancora import ler_externa, verificar_tudo
from monitor_normas.busca import Filtros
from monitor_normas.ledger import Ledger
from monitor_normas.rodada import situacao_ancora

from ..contexto import Contexto, contexto
from ..esquemas import Bloco, Configuracao, Norma, Pagina, TipoMudanca, Verificacao

router = APIRouter()


def _iso(valor: date | None) -> str | None:
    return valor.isoformat() if valor else None


def filtros_mudancas(
    alvo: str | None = Query(None, description="id do alvo"),
    tipo: TipoMudanca | None = Query(None),
    palavra: str = Query("", description="palavras na norma, ementa ou palavras-chave (todas, sem acento)"),
    de: date | None = Query(None, description="publicadas a partir de"),
    ate: date | None = Query(None, description="publicadas até"),
    registrado_de: date | None = Query(None, description="detectadas a partir de"),
    registrado_ate: date | None = Query(None, description="detectadas até"),
    incluir_linha_base: bool = Query(False, description="incluir os itens da primeira execução de cada alvo"),
) -> Filtros:
    return Filtros(termo=palavra, alvo=alvo, tipo=tipo, de=_iso(de), ate=_iso(ate),
                   registrado_de=_iso(registrado_de), registrado_ate=_iso(registrado_ate),
                   sem_linha_base=not incluir_linha_base)


@router.get("/mudancas", response_model=Pagina[Bloco], tags=["Mudanças"],
            summary="Mudanças detectadas (do ledger), mais recentes primeiro")
def mudancas(filtros: Filtros = Depends(filtros_mudancas), limite: int = Query(50, ge=1, le=1000),
             deslocamento: int = Query(0, ge=0), ctx: Contexto = Depends(contexto)):
    return consultas.paginar(consultas.mudancas(ctx.caminhos, filtros), limite, deslocamento)


@router.get("/normas", response_model=Pagina[Norma], tags=["Normas"], summary="Normas vigentes (estado atual)")
def normas(q: str = Query("", description="texto (todas as palavras, sem acento)"), alvo: str | None = None,
           limite: int = Query(50, ge=1, le=1000), deslocamento: int = Query(0, ge=0),
           ctx: Contexto = Depends(contexto)):
    return consultas.paginar(consultas.normas(ctx.caminhos, q, alvo), limite, deslocamento)


@router.get("/ledger", response_model=Pagina[Bloco], tags=["Ledger"], summary="Blocos do ledger, mais recentes primeiro")
def ledger(limite: int = Query(50, ge=1, le=1000), deslocamento: int = Query(0, ge=0),
           ctx: Contexto = Depends(contexto)):
    return consultas.paginar(consultas.blocos_ledger(ctx.caminhos), limite, deslocamento)


@router.get("/ledger/verificar", response_model=Verificacao, tags=["Ledger"],
            summary="Confere a cadeia de hashes e as âncoras")
def verificar(ancora: list[str] = Query([], description="âncoras externas INDICE:HASH (pode repetir)"),
              ctx: Contexto = Depends(contexto)):
    try:
        externas = [ler_externa(a) for a in ancora]
    except ValueError as e:
        raise HTTPException(422, str(e))
    resultado = verificar_tudo(Ledger(ctx.caminhos.ledger), externas)
    atual, _ = situacao_ancora(ctx.caminhos)
    return Verificacao(ok=resultado.ok, blocos=resultado.total, ancoras_conferidas=resultado.ancoras,
                       ancora_atual=atual, erros=resultado.erros, avisos=resultado.avisos)


@router.get("/exportar/excel", tags=["Exportação"], summary="Planilha .xlsx (Mudanças, Normas vigentes, Execuções)",
            description="A aba Mudanças usa os mesmos filtros de GET /mudancas.",
            responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}})
def exportar_excel(filtros: Filtros = Depends(filtros_mudancas), ctx: Contexto = Depends(contexto)):
    _, rodadas = consultas.rodadas(ctx.caminhos, limite=500)
    conteudo = planilha.gerar(consultas.mudancas(ctx.caminhos, filtros), consultas.normas(ctx.caminhos), rodadas)
    nome = f"monitor_normas_{date.today().isoformat()}.xlsx"
    return Response(conteudo, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/configuracao", response_model=Configuracao, tags=["Configuração"],
            summary="Configurações globais do alvos.yaml (somente leitura)")
def configuracao(ctx: Contexto = Depends(contexto)):
    g = ctx.globais()
    return Configuracao(regex={k: v.pattern for k, v in g.regex.items()}, palavras_chave=g.palavras_chave,
                        frequencia=g.frequencia, horario=g.horario)
