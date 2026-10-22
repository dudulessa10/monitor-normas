"""Download das páginas: respeita robots.txt, timeout, tentativas e pausa."""

import logging
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)


class ErroColeta(Exception):
    def __init__(self, mensagem: str, status: int | None = None):
        super().__init__(mensagem)
        self.status = status


class Coletor:
    """Baixa páginas mantendo uma pausa mínima entre requisições ao mesmo servidor."""

    def __init__(self, session: requests.Session | None = None, dormir=time.sleep, relogio=time.monotonic):
        self.session = session or requests.Session()
        self._dormir = dormir
        self._relogio = relogio
        self._ultima_requisicao: float | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def baixar(self, url: str, *, user_agent: str, timeout: float, tentativas: int, pausa: float) -> bytes:
        self._checar_robots(url, user_agent, timeout, pausa)
        ultimo_erro: ErroColeta | None = None
        for tentativa in range(1, max(1, int(tentativas)) + 1):
            self._aguardar(pausa * tentativa)  # pausa maior a cada nova tentativa
            try:
                resposta = self._get(url, user_agent, timeout)
            except requests.RequestException as e:
                ultimo_erro = ErroColeta(f"falha de rede em {url}: {e}")
            else:
                if resposta.status_code == 200:
                    return resposta.content
                ultimo_erro = ErroColeta(f"HTTP {resposta.status_code} em {url}", resposta.status_code)
                if resposta.status_code < 500 and resposta.status_code != 429:
                    raise ultimo_erro  # erro do cliente (404 etc.): repetir não adianta
            log.warning("tentativa %d/%d falhou: %s", tentativa, tentativas, ultimo_erro)
        assert ultimo_erro is not None
        raise ultimo_erro

    def _get(self, url: str, user_agent: str, timeout: float) -> requests.Response:
        try:
            return self.session.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
        finally:
            self._ultima_requisicao = self._relogio()

    def _aguardar(self, pausa: float) -> None:
        if self._ultima_requisicao is None:
            return
        restante = pausa - (self._relogio() - self._ultima_requisicao)
        if restante > 0:
            self._dormir(restante)

    def _checar_robots(self, url: str, user_agent: str, timeout: float, pausa: float) -> None:
        partes = urlsplit(url)
        origem = f"{partes.scheme}://{partes.netloc}"
        regras = self._robots.get(origem)
        if regras is None:
            regras = urllib.robotparser.RobotFileParser(origem + "/robots.txt")
            self._aguardar(pausa)
            try:
                resposta = self._get(origem + "/robots.txt", user_agent, timeout)
            except requests.RequestException as e:
                raise ErroColeta(f"não foi possível ler {origem}/robots.txt: {e}")
            if resposta.status_code == 200:
                regras.parse(resposta.text.splitlines())
            elif 400 <= resposta.status_code < 500:
                regras.allow_all = True  # sem robots.txt: acesso liberado
            else:
                raise ErroColeta(f"robots.txt de {origem} respondeu HTTP {resposta.status_code}")
            regras.modified()
            self._robots[origem] = regras
        if not regras.can_fetch(user_agent, url):
            raise ErroColeta(f"robots.txt de {origem} não permite acessar {url}")
