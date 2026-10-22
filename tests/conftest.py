import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(RAIZ))

from monitor_normas.coleta import ErroColeta  # noqa: E402
from monitor_normas.config import carregar_globais, montar_config  # noqa: E402

HOJE = date(2026, 10, 15)
URLS_FIXTURES = {
    "anac-resolucoes": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/resolucoes/2026",
    "anac-rbac": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/rbha-e-rbac/rbac",
    "anac-portarias": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/portarias/2026",
    "anac-portarias-regulatorias": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/portaria-regulatoria/2026",
    "anac-is": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/iac-e-is/is",
    "anac-decisoes": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/decisoes/2026",
    "anac-instrucoes-normativas": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/instrucoes-normativas/2026",
    "anac-condicoes-especiais": "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/cesc-condicao-especial",
}


def ler_fixture(nome: str) -> bytes:
    return (FIXTURES / f"{nome}.html").read_bytes()


@pytest.fixture(autouse=True)
def pasta_segura_isolada(tmp_path_factory, monkeypatch):
    """Chave e cópia da âncora numa pasta temporária, nunca no %LOCALAPPDATA% real."""
    pasta = tmp_path_factory.mktemp("pasta_segura")
    monkeypatch.setenv("MONITOR_NORMAS_PASTA_SEGURA", str(pasta))
    for variavel in ("MONITOR_NORMAS_BASE", "MONITOR_NORMAS_SENHA", "MONITOR_NORMAS_USUARIO"):
        monkeypatch.delenv(variavel, raising=False)  # as do servidor não podem vazar para os testes
    return pasta


@pytest.fixture(scope="session")
def config_real():
    """Globais do alvos.yaml + alvos do alvos_iniciais.yaml (garante que a carga inicial continua válida)."""
    globais = carregar_globais(RAIZ / "alvos.yaml")
    return montar_config(globais, carregar_globais(RAIZ / "alvos_iniciais.yaml").alvos_yaml)


class ColetorFalso:
    """Substitui o Coletor: devolve HTML de um dicionário url -> bytes (ou exceção)."""

    def __init__(self, paginas: dict):
        self.paginas = dict(paginas)
        self.chamadas: list[str] = []

    def baixar(self, url, **opcoes):
        self.chamadas.append(url)
        conteudo = self.paginas.get(url)
        if conteudo is None:
            raise ErroColeta(f"HTTP 404 em {url}", 404)
        if isinstance(conteudo, Exception):
            raise conteudo
        return conteudo


class Relogio:
    def __init__(self, inicio: datetime | None = None):
        self.atual = inicio or datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.atual
