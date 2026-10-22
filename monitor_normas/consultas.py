"""Consultas de leitura usadas pela API e pela exportação (sem nada de HTTP aqui)."""

import re

from .busca import Filtros, buscar
from .estado import Estado
from .execucao import Caminhos
from .extracao import normalizar
from .ledger import Ledger


def mudancas(caminhos: Caminhos, filtros: Filtros) -> list[dict]:
    """Blocos do ledger que atendem aos filtros, do mais recente para o mais antigo."""
    return buscar(Ledger(caminhos.ledger).blocos(), filtros)


def blocos_ledger(caminhos: Caminhos) -> list[dict]:
    return sorted(Ledger(caminhos.ledger).blocos(), key=lambda b: b.get("indice", 0), reverse=True)


def normas(caminhos: Caminhos, texto: str = "", alvo: str | None = None) -> list[dict]:
    """Itens vigentes no estado, com busca por texto (todas as palavras, sem acento)."""
    with Estado(caminhos.estado_db) as estado:
        itens = estado.listar_itens(alvo)
    palavras = normalizar(texto).split()
    resultado = []
    for linha in itens:
        norma = _norma(linha)
        pesquisavel = normalizar(" ".join([norma["chave"], norma["ementa"], norma["tipo"], norma["numero"],
                                           *norma["campos"].values()]))
        if all(re.search(rf"(?<!\w){re.escape(p)}", pesquisavel) for p in palavras):
            resultado.append(norma)
    return resultado


def _norma(linha: dict) -> dict:
    dados = linha["dados"]
    campos = {k: v for k, v in (dados.get("campos") or {}).items() if isinstance(v, str)}
    return {
        "alvo": linha["alvo"],
        "chave": linha["chave"],
        "tipo": dados.get("tipo") or "",
        "numero": dados.get("numero") or "",
        "data_publicacao": dados.get("data_publicacao") or dados.get("data_norma") or "",
        "ementa": campos.get("ementa", ""),
        "link": dados.get("link") or "",
        "status": dados.get("status") or [],
        "primeira_vez": linha["primeira_vez"],
        "ultima_vez": linha["ultima_vez"],
        "campos": campos,
    }


def rodadas(caminhos: Caminhos, limite: int = 50, deslocamento: int = 0,
            status: str | None = None) -> tuple[int, list[dict]]:
    with Estado(caminhos.estado_db) as estado:
        return estado.listar_rodadas(limite, deslocamento, status)


def paginar(itens: list, limite: int, deslocamento: int) -> dict:
    return {"total": len(itens), "limite": limite, "deslocamento": deslocamento,
            "itens": itens[deslocamento:deslocamento + limite] if limite else itens[deslocamento:]}
