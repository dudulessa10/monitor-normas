"""Palavras-chave de cada item: as globais encontradas na ementa + tipo e número da norma."""

import re

from .extracao import Item, normalizar


def encontrar(texto: str, palavras: list[str]) -> list[str]:
    """Busca sem diferenciar maiúsculas nem acentos; aceita plural simples (s/es)."""
    base = normalizar(texto)
    return [p for p in palavras
            if re.search(rf"(?<!\w){re.escape(normalizar(p))}(?:e?s)?(?!\w)", base)]


def palavras_do_item(item: Item, globais: list[str]) -> list[str]:
    resultado = encontrar(item.ementa, globais)
    vistos = {normalizar(p) for p in resultado}
    for extra in (item.tipo, item.numero):
        if extra and normalizar(extra) not in vistos:
            resultado.append(extra)
            vistos.add(normalizar(extra))
    return resultado
