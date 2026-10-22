import pytest
import requests

from monitor_normas.coleta import Coletor, ErroColeta

UA = "MonitorNormas/0.1"
ROBOTS = "User-agent: *\nDisallow: /rss\n"


class Resposta:
    def __init__(self, status, texto=""):
        self.status_code = status
        self.text = texto
        self.content = texto.encode("utf-8")


class SessaoFalsa:
    def __init__(self, respostas: dict):
        self.respostas = {url: list(r) for url, r in respostas.items()}
        self.chamadas = []

    def get(self, url, headers, timeout):
        self.chamadas.append((url, headers["User-Agent"], timeout))
        fila = self.respostas[url]
        resposta = fila.pop(0) if len(fila) > 1 else fila[0]
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


def coletor(respostas):
    pausas = []
    relogio = iter(range(0, 10_000))
    c = Coletor(session=SessaoFalsa(respostas), dormir=pausas.append, relogio=lambda: next(relogio))
    return c, pausas


def baixar(c, url, tentativas=3):
    return c.baixar(url, user_agent=UA, timeout=30, tentativas=tentativas, pausa=5)


def test_respeita_robots():
    c, _ = coletor({"https://site/robots.txt": [Resposta(200, ROBOTS)], "https://site/rss": [Resposta(200, "x")]})
    with pytest.raises(ErroColeta, match="robots.txt"):
        baixar(c, "https://site/rss")
    assert [u for u, *_ in c.session.chamadas] == ["https://site/robots.txt"]


def test_envia_user_agent_timeout_e_pausa():
    c, pausas = coletor({"https://site/robots.txt": [Resposta(200, ROBOTS)],
                         "https://site/a": [Resposta(200, "A")], "https://site/b": [Resposta(200, "B")]})
    assert baixar(c, "https://site/a") == b"A"
    assert baixar(c, "https://site/b") == b"B"
    assert all(ua == UA and t == 30 for _, ua, t in c.session.chamadas)
    assert pausas and all(p > 0 for p in pausas)  # esperou entre as requisições
    assert len(c.session.chamadas) == 3  # robots.txt lido uma vez só


def test_tenta_de_novo_em_erro_de_servidor():
    c, _ = coletor({"https://site/robots.txt": [Resposta(404)],
                    "https://site/a": [Resposta(503), requests.ConnectionError("caiu"), Resposta(200, "ok")]})
    assert baixar(c, "https://site/a") == b"ok"


def test_desiste_apos_as_tentativas():
    c, _ = coletor({"https://site/robots.txt": [Resposta(404)], "https://site/a": [Resposta(500)]})
    with pytest.raises(ErroColeta, match="HTTP 500"):
        baixar(c, "https://site/a", tentativas=2)
    assert len(c.session.chamadas) == 3


def test_404_nao_repete():
    c, _ = coletor({"https://site/robots.txt": [Resposta(404)], "https://site/a": [Resposta(404)]})
    with pytest.raises(ErroColeta) as erro:
        baixar(c, "https://site/a")
    assert erro.value.status == 404
    assert len(c.session.chamadas) == 2
