"""Extração de itens de páginas HTML (tabelas de normas, hash e data de modificação)."""

import hashlib
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from requests.utils import requote_uri

from .config import Alvo

# Usadas quando o alvos.yaml não define "data_br" / "dou" / "data_modificacao".
DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
DOU = re.compile(r"DOU\s+(?:de\s+)?(\d{2}/\d{2}/\d{4})", re.IGNORECASE)
DATA_MODIFICACAO = re.compile(r"última modificação\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}h\d{2})", re.IGNORECASE)
# Número genérico ("Nº 58/SAR") quando o alvo não tem regex_numero ou ela não casa.
NUMERO_GENERICO = re.compile(r"\bn[º°o]\.?\s*([\w.\-/]+)", re.IGNORECASE)
PRIMEIRO_NUMERO = re.compile(r"(\d[\w.\-/]*)")  # último recurso: "IS 00-001B" -> "00-001B"
# Tipo = texto antes do número: "RESOLUÇÃO Nº 817" -> "RESOLUÇÃO", "RBAC-E 94" -> "RBAC-E".
TIPO = re.compile(r"^(.*?)\s*(?:\bn[º°o]\.?\s*)?\d", re.IGNORECASE)


class ErroExtracao(Exception):
    """A página não tem a estrutura esperada."""


@dataclass
class Item:
    chave: str
    campos: dict[str, str]
    origem: str
    link: str = ""
    numero: str = ""
    tipo: str = ""
    data_norma: str = ""
    data_publicacao: str = ""
    status: list[str] = field(default_factory=list)
    hash: str = ""
    campos_monitorados: list[str] = field(default_factory=list)  # campos que entram no hash

    @property
    def ementa(self) -> str:
        return self.campos.get("ementa", "")


# ---------------------------------------------------------------- utilidades

def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples (para comparar cabeçalhos)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalizar(texto)).strip("_")


def texto_limpo(elemento) -> str:
    return " ".join(elemento.get_text(" ", strip=True).split())


def data_iso(texto: str) -> str:
    m = DATA_BR.search(texto or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def calcular_hash(campos: dict[str, str], nomes: list[str]) -> str:
    dados = {nome: campos.get(nome, "") for nome in nomes}
    return hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _sopa(html: bytes | str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _conteudo(sopa: BeautifulSoup):
    """Área principal da página no Plone; cai para o corpo inteiro se não achar."""
    return sopa.select_one("#content-core") or sopa.select_one("#content") or sopa.body or sopa


# ---------------------------------------------------------------- tabelas

def extrair_linhas(html: bytes | str, url_base: str, *, tabela: str = "primeira",
                   colunas: dict[str, str] | None = None) -> list[dict[str, str]]:
    """Lê as linhas da(s) tabela(s). colunas=None usa o cabeçalho da própria tabela."""
    sopa = _sopa(html)
    tabelas = _conteudo(sopa).find_all("table") or sopa.find_all("table")
    if not tabelas:
        raise ErroExtracao("nenhuma tabela encontrada na página")
    if tabela == "primeira":
        tabelas = tabelas[:1]
    linhas: list[dict[str, str]] = []
    for t in tabelas:
        linhas.extend(_ler_tabela(t, url_base, colunas))
    return linhas


def _ler_tabela(tabela, url_base: str, colunas: dict[str, str] | None) -> list[dict[str, str]]:
    trs = tabela.find_all("tr")
    indice_cabecalho = next((i for i, tr in enumerate(trs) if tr.find("th")), None)
    if indice_cabecalho is None:
        raise ErroExtracao("tabela sem linha de cabeçalho (<th>)")
    cabecalho = [texto_limpo(c) for c in trs[indice_cabecalho].find_all(["th", "td"])]

    if colunas is None:
        nomes = [slug(c) or f"coluna_{i + 1}" for i, c in enumerate(cabecalho)]
    else:
        mapa = {normalizar(k): v for k, v in colunas.items()}
        presentes = {normalizar(c) for c in cabecalho}
        faltando = [k for k in colunas if normalizar(k) not in presentes]
        if faltando:
            raise ErroExtracao(f"colunas {faltando} não estão no cabeçalho da tabela {cabecalho}")
        nomes = [mapa.get(normalizar(c)) for c in cabecalho]

    linhas = []
    for tr in trs[indice_cabecalho + 1:]:
        celulas = tr.find_all(["td", "th"], recursive=False)
        if not tr.find("td", recursive=False):
            continue
        linha: dict[str, str] = {}
        for nome, celula in zip(nomes, celulas):
            if not nome:
                continue
            # requote_uri troca espaços por %20: as colunas link* juntam vários links separados por espaço.
            links = [requote_uri(urljoin(url_base, a["href"].strip())) for a in celula.find_all("a", href=True)]
            if nome.startswith("link"):
                linha[nome] = " ".join(links)
            else:
                linha[nome] = texto_limpo(celula)
                if links:
                    linha[f"{nome}_link"] = links[0]
        if any(v for k, v in linha.items() if not k.endswith("_link")):
            linhas.append(linha)
    return linhas


def montar_itens(linhas: list[dict[str, str]], alvo: Alvo, regex: dict[str, re.Pattern], origem: str) -> list[Item]:
    """Transforma linhas da tabela em itens com número, tipo, datas, status e hash."""
    if linhas and not any(alvo.chave_item in linha for linha in linhas):
        disponiveis = sorted({k for linha in linhas for k in linha})
        raise ErroExtracao(f"campo chave '{alvo.chave_item}' não existe; campos disponíveis: {disponiveis}")

    re_data = regex.get("data_br", DATA_BR)
    re_dou = regex.get("dou", DOU)
    itens = []
    for linha in linhas:
        chave = linha.get(alvo.chave_item, "").strip()
        if not chave:
            continue
        publicacao = linha.get("publicacao") or linha.get("data") or ""
        m_dou = re_dou.search(publicacao)
        m_data = re_data.search(publicacao)
        campos_hash = alvo.campos_hash or [k for k in linha if not _eh_link(k)]
        texto_status = f"{chave} {linha.get('ementa', '')}"
        itens.append(Item(
            chave=chave,
            campos=linha,
            origem=origem,
            link=_link_principal(linha),
            numero=_numero(chave, alvo.regex_numero),
            tipo=_tipo(chave),
            data_norma=data_iso(chave),
            data_publicacao=data_iso(m_dou.group(1) if m_dou else (m_data.group(0) if m_data else "")),
            status=[nome for nome, rx in alvo.marcar_status.items() if rx.search(texto_status)],
            hash=calcular_hash(linha, campos_hash),
            campos_monitorados=list(campos_hash),
        ))
    return itens


def desambiguar(itens: list[Item], chave_item: str = "norma") -> list[str]:
    """Torna as chaves únicas usando o final do link da linha. Devolve avisos."""
    avisos = []
    contagem = Counter(i.chave for i in itens)
    for item in itens:
        if contagem[item.chave] > 1:
            link = item.campos.get(f"{chave_item}_link") or item.link
            sufixo = urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1] if link else ""
            if sufixo:
                item.chave = f"{item.chave} [{sufixo}]"
    restantes = Counter(i.chave for i in itens)
    ordem: Counter = Counter()
    for item in itens:
        if restantes[item.chave] > 1:
            ordem[item.chave] += 1
            item.chave = f"{item.chave} #{ordem[item.chave]}"
    repetidas = [k for k, n in contagem.items() if n > 1]
    if repetidas:
        avisos.append(f"chaves repetidas desambiguadas pelo link: {repetidas}")
    return avisos


def _eh_link(nome: str) -> bool:
    return nome.startswith("link") or nome.endswith("_link")


def _link_principal(linha: dict[str, str]) -> str:
    for preferencia in (lambda k: k.startswith("link"), lambda k: "arquivo" in k and k.endswith("_link"),
                        lambda k: k.endswith("_link")):
        for nome, valor in linha.items():
            if preferencia(nome) and valor:
                return valor.split()[0]
    return ""


def _numero(texto: str, regex: re.Pattern | None) -> str:
    m = regex.search(texto) if regex else None
    if m:
        return m.group(1) if m.re.groups == 1 else " ".join(m.group(0).split())
    m = NUMERO_GENERICO.search(texto) or PRIMEIRO_NUMERO.search(texto)
    return m.group(1).rstrip(".-/") if m else ""


def _tipo(texto: str) -> str:
    m = TIPO.match(texto)
    return m.group(1).strip(" ,-") if m else ""


# ---------------------------------------------------------------- página inteira

def data_modificacao_pagina(html: bytes | str, regex: re.Pattern | None = None) -> str | None:
    """Texto "última modificação" do Plone, ex.: "14/10/2026 11h13"."""
    m = (regex or DATA_MODIFICACAO).search(texto_limpo(_sopa(html)))
    if not m:
        return None
    return " ".join(g for g in m.groups() if g) or m.group(0)


def item_hash_conteudo(html: bytes | str, url: str, categoria: str = "") -> Item:
    texto = texto_limpo(_conteudo(_sopa(html)))
    if not texto:
        raise ErroExtracao("página sem conteúdo")
    campos = {"hash_conteudo": hashlib.sha256(texto.encode("utf-8")).hexdigest()}
    return Item(chave=url, campos=campos, origem=url, link=url, tipo=categoria,
                hash=calcular_hash(campos, list(campos)), campos_monitorados=list(campos))


def item_data_modificacao(html: bytes | str, url: str, regex: re.Pattern | None = None, categoria: str = "") -> Item:
    valor = data_modificacao_pagina(html, regex)
    if not valor:
        raise ErroExtracao("texto de 'última modificação' não encontrado na página")
    campos = {"modificacao": valor}
    return Item(chave=url, campos=campos, origem=url, link=url, tipo=categoria,
                data_publicacao=data_iso(valor), hash=calcular_hash(campos, list(campos)),
                campos_monitorados=list(campos))
