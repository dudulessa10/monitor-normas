"""Contrato da API (entrada e saída). É o que outra aplicação precisa conhecer."""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")

TipoMudanca = Literal["NOVO", "ALTERADO", "REMOVIDO", "LINHA_BASE"]
StatusRodada = Literal["em_andamento", "ok", "com_erros", "falhou", "interrompida"]


class Pagina(BaseModel, Generic[T]):
    total: int
    limite: int
    deslocamento: int
    itens: list[T]


class Erro(BaseModel):
    detail: str


# ---------------------------------------------------------------- alvos

class Deteccao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metodo: Literal["lista_itens", "hash_conteudo", "data_modificacao"] = "lista_itens"
    chave_item: str = Field("norma", description="campo que identifica cada linha da tabela")
    detectar_mudanca_em: list[str] | None = Field(
        None, description="campos que, se mudarem, tornam o item ALTERADO (vazio = todos os campos de texto)")


class Extracao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tabela: Literal["primeira", "todas"] = "primeira"
    colunas: dict[str, str] | Literal["auto"] = Field(
        "auto", description='"auto" ou mapeamento cabeçalho da tabela -> nome do campo')
    regex_numero: str | None = Field(None, description="nome de uma regex da seção regex do alvos.yaml")
    marcar_status: dict[str, str] = Field(default_factory=dict, description="status -> nome da regex")


class AlvoEntrada(BaseModel):
    """Mesmo formato de um alvo do alvos.yaml. Campos desconhecidos são recusados."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "id": "anac-resolucoes", "ativo": True, "site": "ANAC", "categoria": "Resoluções", "prioridade": "alta",
        "url": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/resolucoes/{ano}", "anos": ["atual"],
        "deteccao": {"metodo": "lista_itens", "chave_item": "norma"},
        "extracao": {"tabela": "primeira", "regex_numero": "resolucao",
                     "colunas": {"Norma": "norma", "Publicação": "publicacao", "Ementa": "ementa",
                                 "Arquivo": "link_arquivo"}}}]})

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$", description="minúsculas, números, - e _")
    ativo: bool = False
    site: str = ""
    categoria: str = ""
    prioridade: Literal["alta", "media", "baixa"] | None = None
    url: str = Field(description="pode conter {ano}")
    anos: list[Literal["atual", "anterior"] | int] = Field(default_factory=lambda: ["atual"])
    deteccao: Deteccao = Field(default_factory=Deteccao)
    extracao: Extracao = Field(default_factory=Extracao)
    observacoes: str = ""
    timeout_segundos: float | None = Field(None, gt=0, le=300)
    tentativas: int | None = Field(None, ge=1, le=10)
    pausa_entre_requisicoes_segundos: float | None = Field(None, ge=0, le=120)
    user_agent: str | None = None
    registrar_no_ledger: bool | None = None

    @field_validator("url")
    @classmethod
    def url_http(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor.startswith(("http://", "https://")):
            raise ValueError("a url deve começar com http:// ou https://")
        return valor

    def definicao(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class UltimaExecucao(BaseModel):
    inicio: str
    fim: str | None
    status: str
    total: int
    novos: int
    alterados: int
    removidos: int
    modificacao_pagina: str | None = None
    erro: str | None = None


class AlvoSaida(BaseModel):
    id: str
    ativo: bool
    site: str = ""
    categoria: str = ""
    prioridade: str | None = None
    url: str = ""
    metodo: str = ""
    valido: bool = Field(description="false se a definição tem erro (ver erro_config); o alvo não roda")
    erro_config: str | None = None
    itens_vigentes: int = 0
    ultima_execucao: UltimaExecucao | None = None
    definicao: dict[str, Any] = Field(description="definição completa, no formato de AlvoEntrada")


# ---------------------------------------------------------------- execuções

class PedidoExecucao(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alvo: str | None = Field(None, description="id de um alvo; vazio = todos os alvos ativos")


class ExecucaoDisparada(BaseModel):
    rodada_id: int
    status: StatusRodada = "em_andamento"
    url: str = Field(description="onde acompanhar a rodada")


class ExecucaoAlvo(BaseModel):
    id: int
    alvo: str
    inicio: str
    fim: str | None
    status: str = Field(description="ok | linha_base | erro")
    total: int
    novos: int
    alterados: int
    removidos: int
    modificacao_pagina: str | None = None
    erro: str | None = None


class Rodada(BaseModel):
    id: int
    origem: str = Field(description="cli | agendamento | web | historico")
    alvo: str | None = Field(description="null = todos os alvos ativos")
    inicio: str
    fim: str | None
    status: StatusRodada
    erro: str | None = None
    total: int
    novos: int
    alterados: int
    removidos: int
    erros: int = Field(description="alvos com erro nesta rodada")
    execucoes: list[ExecucaoAlvo]


# ---------------------------------------------------------------- ledger, mudanças, normas

class Bloco(BaseModel):
    indice: int
    timestamp: str
    alvo: str
    tipo_mudanca: TipoMudanca
    norma: str
    link: str | None = None
    data_publicacao: str | None = None
    ementa: str | None = None
    palavras_chave: list[str] = Field(default_factory=list)
    hash_anterior: str
    hash: str


class Norma(BaseModel):
    alvo: str
    chave: str
    tipo: str
    numero: str
    data_publicacao: str
    ementa: str
    link: str
    status: list[str]
    primeira_vez: str
    ultima_vez: str
    campos: dict[str, str]


class Verificacao(BaseModel):
    ok: bool
    blocos: int
    ancoras_conferidas: int
    ancora_atual: str | None = Field(description="INDICE:HASH do último bloco, se ancorado")
    erros: list[str]
    avisos: list[str]


class Configuracao(BaseModel):
    """Configurações globais (somente leitura; ficam no alvos.yaml)."""
    regex: dict[str, str]
    palavras_chave: list[str]
    frequencia: str
    horario: str


class Saude(BaseModel):
    status: str = Field(description="ok se o servidor responde e o banco abre")
    versao: str
    ultima_rodada_inicio: str | None = Field(description="para alertar se a execução diária parou")
    ultima_rodada_status: StatusRodada | None
