"""Busca no ledger por termo, alvo, tipo de mudança e período de publicação."""

import re
from dataclasses import dataclass
from typing import Iterable

from .extracao import normalizar


@dataclass
class Filtros:
    termo: str = ""           # todas as palavras precisam aparecer (início de palavra)
    alvo: str | None = None
    tipo: str | None = None   # NOVO | ALTERADO | REMOVIDO | LINHA_BASE
    de: str | None = None     # AAAA-MM-DD, compara com data_publicacao
    ate: str | None = None
    registrado_de: str | None = None   # AAAA-MM-DD, compara com o timestamp do bloco
    registrado_ate: str | None = None
    sem_linha_base: bool = False       # só mudanças de fato (NOVO, ALTERADO, REMOVIDO)


def texto_pesquisavel(bloco: dict) -> str:
    partes = [bloco.get("norma") or "", bloco.get("ementa") or "", *(bloco.get("palavras_chave") or [])]
    return normalizar(" ".join(str(p) for p in partes))


def casa(bloco: dict, filtros: Filtros) -> bool:
    if filtros.alvo and bloco.get("alvo") != filtros.alvo:
        return False
    if filtros.tipo and bloco.get("tipo_mudanca") != filtros.tipo:
        return False
    if filtros.sem_linha_base and not filtros.tipo and bloco.get("tipo_mudanca") == "LINHA_BASE":
        return False
    registrado = str(bloco.get("timestamp") or "")[:10]
    if filtros.registrado_de and registrado < filtros.registrado_de:
        return False
    if filtros.registrado_ate and registrado > filtros.registrado_ate:
        return False
    data = bloco.get("data_publicacao") or ""
    if filtros.de and not (data and data >= filtros.de):
        return False
    if filtros.ate and not (data and data <= filtros.ate):
        return False
    texto = texto_pesquisavel(bloco)
    # Início de palavra: "drone" acha "drones", "817" não acha "1817".
    return all(re.search(rf"(?<!\w){re.escape(p)}", texto) for p in normalizar(filtros.termo).split())


def buscar(blocos: Iterable[dict], filtros: Filtros) -> list[dict]:
    """Blocos que atendem aos filtros, do mais recente para o mais antigo."""
    return sorted((b for b in blocos if casa(b, filtros)), key=lambda b: b.get("indice", 0), reverse=True)


def formatar(bloco: dict, largura_ementa: int = 160) -> str:
    ementa = bloco.get("ementa") or ""
    if len(ementa) > largura_ementa:
        ementa = ementa[:largura_ementa - 1].rstrip() + "…"
    registrado = (bloco.get("timestamp") or "")[:16].replace("T", " ")
    cabecalho = (f"#{bloco.get('indice')}  {bloco.get('tipo_mudanca')}  {bloco.get('alvo')}  "
                 f"publicação {bloco.get('data_publicacao') or '?'}  registrado {registrado}")
    linhas = [cabecalho, f"  {bloco.get('norma')}"]
    if ementa:
        linhas.append(f"  {ementa}")
    if bloco.get("link"):
        linhas.append(f"  {bloco['link']}")
    if bloco.get("palavras_chave"):
        linhas.append(f"  palavras-chave: {', '.join(bloco['palavras_chave'])}")
    return "\n".join(linhas)
