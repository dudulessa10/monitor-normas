"""Leitura e validação do alvos.yaml."""

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

METODOS = {"lista_itens", "data_modificacao", "hash_conteudo"}
FREQUENCIAS = {"diaria", "semanal", "manual"}
HORARIO = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Valores usados quando nem "padroes" nem o alvo definem a opção.
PADROES_INTERNOS: dict[str, Any] = {
    "timeout_segundos": 30,
    "pausa_entre_requisicoes_segundos": 5,
    "tentativas": 3,
    "user_agent": "MonitorNormas/0.1",
    "baixar_arquivos": False,
    "registrar_no_ledger": True,
}


class ErroConfig(Exception):
    """Problema no alvos.yaml."""


@dataclass
class Alvo:
    id: str
    ativo: bool = False
    site: str = ""
    categoria: str = ""
    url: str = ""
    anos: list = field(default_factory=lambda: ["atual"])
    metodo: str = "lista_itens"
    chave_item: str = "norma"
    campos_hash: list[str] | None = None  # None = todos os campos de texto
    tabela: str = "primeira"
    colunas: dict[str, str] | None = None  # None = "auto"
    regex_numero: re.Pattern | None = None
    marcar_status: dict[str, re.Pattern] = field(default_factory=dict)
    opcoes: dict[str, Any] = field(default_factory=lambda: dict(PADROES_INTERNOS))
    erro_config: str | None = None

    @property
    def usa_ano(self) -> bool:
        return "{ano}" in self.url

    def urls(self, hoje: date) -> list[str]:
        """URLs a baixar, com {ano} expandido conforme "anos"."""
        if not self.usa_ano:
            return [self.url]
        urls: list[str] = []
        for ano in self.anos or ["atual"]:
            url = self.url.replace("{ano}", str(resolver_ano(ano, hoje)))
            if url not in urls:
                urls.append(url)
        return urls


@dataclass
class Config:
    caminho: Path
    alvos: list[Alvo]
    regex: dict[str, re.Pattern]
    palavras_chave: list[str]
    frequencia: str = "diaria"  # usada pelo comando "agendar"
    horario: str = "06:00"      # hora local do computador

    def alvo(self, alvo_id: str) -> Alvo:
        for alvo in self.alvos:
            if alvo.id == alvo_id:
                return alvo
        raise KeyError(alvo_id)


def resolver_ano(valor: Any, hoje: date) -> int:
    if valor == "atual":
        return hoje.year
    if valor == "anterior":
        return hoje.year - 1
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ErroConfig(f"valor inválido em anos: {valor!r} (use atual, anterior ou um número)")


def validar_horario(valor: Any) -> str:
    texto = str(valor).strip()
    if not HORARIO.match(texto):
        raise ErroConfig(f"horário inválido: {valor!r} (use HH:MM, ex.: 06:00)")
    return texto


def validar_frequencia(valor: Any) -> str:
    texto = str(valor).strip().lower()
    if texto not in FREQUENCIAS:
        raise ErroConfig(f"frequência inválida: {valor!r} (use {', '.join(sorted(FREQUENCIAS))})")
    return texto


def compilar(padrao: str, nome: str) -> re.Pattern:
    try:
        return re.compile(padrao, re.IGNORECASE)
    except re.error as e:
        raise ErroConfig(f"regex '{nome}' inválida: {e}")


@dataclass
class Globais:
    """Tudo do YAML menos os alvos: regex, padrões, palavras-chave e agendamento."""
    caminho: Path
    regex: dict[str, re.Pattern]
    padroes: dict[str, Any]
    palavras_chave: list[str]
    frequencia: str
    horario: str
    alvos_yaml: list[dict]  # seção "alvos" do arquivo, se houver (carga inicial)


def carregar_globais(caminho: Path) -> Globais:
    caminho = Path(caminho)
    try:
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErroConfig(f"YAML inválido em {caminho}: {e}")
    padroes = {**PADROES_INTERNOS, **(bruto.get("padroes") or {})}
    return Globais(
        caminho=caminho,
        regex={nome: compilar(str(p), nome) for nome, p in (bruto.get("regex") or {}).items()},
        padroes=padroes,
        palavras_chave=[str(p) for p in (bruto.get("palavras_chave_globais") or [])],
        frequencia=validar_frequencia(padroes.get("frequencia", "diaria")),
        horario=validar_horario(padroes.get("horario", "06:00")),
        alvos_yaml=[dict(d or {}) for d in (bruto.get("alvos") or [])],
    )


def montar_config(globais: Globais, definicoes: list[dict]) -> Config:
    """Config a partir das definições dos alvos (do YAML ou do banco)."""
    alvos: list[Alvo] = []
    vistos: set[str] = set()
    for i, dados in enumerate(definicoes):
        alvo_id = str((dados or {}).get("id") or f"<alvo #{i + 1} sem id>")
        if alvo_id in vistos:
            raise ErroConfig(f"id de alvo repetido: {alvo_id}")
        vistos.add(alvo_id)
        try:
            alvos.append(validar_definicao(globais, dados))
        except ErroConfig as e:
            # Um alvo mal configurado não impede os demais de rodar.
            alvos.append(Alvo(id=alvo_id, ativo=bool(dados.get("ativo")), erro_config=str(e)))
    return Config(caminho=globais.caminho, alvos=alvos, regex=globais.regex, palavras_chave=globais.palavras_chave,
                  frequencia=globais.frequencia, horario=globais.horario)


def validar_definicao(globais: Globais, dados: dict) -> Alvo:
    """Monta o Alvo ou levanta ErroConfig com a mesma mensagem que aparece no "list"."""
    return montar_alvo(dados, globais.padroes, globais.regex)


def carregar_config(caminho: Path) -> Config:
    """Config só a partir do YAML (alvos incluídos). A CLI e a API usam alvos.carregar_config_banco."""
    globais = carregar_globais(caminho)
    return montar_config(globais, globais.alvos_yaml)


def montar_alvo(dados: dict, padroes: dict, regexes: dict[str, re.Pattern]) -> Alvo:
    if not dados.get("id"):
        raise ErroConfig("alvo sem id")
    if not dados.get("url"):
        raise ErroConfig("alvo sem url")

    deteccao = dados.get("deteccao") or {}
    extracao = dados.get("extracao") or {}
    metodo = deteccao.get("metodo", "lista_itens")
    if metodo not in METODOS:
        raise ErroConfig(f"método de detecção desconhecido: {metodo}")
    if extracao.get("tipo") not in (None, "html"):
        raise ErroConfig(f"tipo de extração não suportado: {extracao.get('tipo')}")

    def regex_por_nome(nome: str) -> re.Pattern:
        if nome not in regexes:
            raise ErroConfig(f"regex '{nome}' não está definida na seção regex")
        return regexes[nome]

    colunas = extracao.get("colunas", "auto")
    if colunas == "auto" or colunas is None:
        colunas = None
    elif not isinstance(colunas, dict):
        raise ErroConfig("colunas deve ser 'auto' ou um mapeamento cabeçalho -> campo")

    tabela = extracao.get("tabela", "primeira")
    if tabela not in ("primeira", "todas"):
        raise ErroConfig(f"tabela deve ser 'primeira' ou 'todas', não {tabela!r}")

    anos = dados.get("anos") or ["atual"]
    for ano in anos:
        resolver_ano(ano, date.today())  # só valida

    opcoes = {k: dados.get(k, padroes.get(k)) for k in PADROES_INTERNOS}

    return Alvo(
        id=str(dados["id"]),
        ativo=bool(dados.get("ativo", False)),
        site=str(dados.get("site", "")),
        categoria=str(dados.get("categoria", dados["id"])),
        url=str(dados["url"]),
        anos=list(anos),
        metodo=metodo,
        chave_item=str(deteccao.get("chave_item", "norma")),
        campos_hash=deteccao.get("detectar_mudanca_em"),
        tabela=tabela,
        colunas={str(k): str(v) for k, v in colunas.items()} if colunas else None,
        regex_numero=regex_por_nome(extracao["regex_numero"]) if extracao.get("regex_numero") else None,
        marcar_status={str(k): regex_por_nome(v) for k, v in (extracao.get("marcar_status") or {}).items()},
        opcoes=opcoes,
    )
