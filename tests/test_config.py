from datetime import date

import pytest

from conftest import HOJE
from monitor_normas.config import Alvo, ErroConfig, carregar_config


def test_alvos_yaml_do_projeto_carrega(config_real):
    ids = [a.id for a in config_real.alvos]
    assert "anac-resolucoes" in ids
    assert all(a.erro_config is None for a in config_real.alvos if a.ativo)
    assert "aeródromo" in config_real.palavras_chave


def test_colunas_auto_e_mapeadas(config_real, tmp_path):
    assert config_real.alvo("anac-resolucoes").colunas["Publicação"] == "publicacao"
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text("alvos:\n  - {id: a, url: 'https://x', extracao: {colunas: auto}}\n", encoding="utf-8")
    assert carregar_config(arquivo).alvo("a").colunas is None


def test_regex_ignora_maiusculas(config_real):
    assert config_real.regex["resolucao"].search("RESOLUÇÃO Nº 817, 07/10/2026").group(1) == "817"


def test_expansao_de_anos():
    alvo = Alvo(id="x", url="https://exemplo/{ano}", anos=["atual", "anterior"])
    assert alvo.urls(HOJE) == ["https://exemplo/2026", "https://exemplo/2025"]
    assert Alvo(id="y", url="https://exemplo/fixo").urls(HOJE) == ["https://exemplo/fixo"]
    assert Alvo(id="z", url="https://exemplo/{ano}", anos=[2020]).urls(date(2026, 1, 1)) == ["https://exemplo/2020"]


def test_padroes_sobrescritos_pelo_alvo(tmp_path):
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text(
        "padroes: {timeout_segundos: 30, tentativas: 3}\n"
        "alvos:\n"
        "  - {id: a, ativo: true, url: 'https://x', tentativas: 1}\n", encoding="utf-8")
    alvo = carregar_config(arquivo).alvo("a")
    assert alvo.opcoes["tentativas"] == 1
    assert alvo.opcoes["timeout_segundos"] == 30


def test_alvo_invalido_nao_derruba_os_outros(tmp_path):
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text(
        "alvos:\n"
        "  - {id: ruim, ativo: true, url: 'https://x', extracao: {regex_numero: nao_existe}}\n"
        "  - {id: bom, ativo: true, url: 'https://y'}\n", encoding="utf-8")
    config = carregar_config(arquivo)
    assert "nao_existe" in config.alvo("ruim").erro_config
    assert config.alvo("bom").erro_config is None


def test_id_repetido_e_erro(tmp_path):
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text("alvos:\n  - {id: a, url: 'https://x'}\n  - {id: a, url: 'https://y'}\n", encoding="utf-8")
    with pytest.raises(ErroConfig):
        carregar_config(arquivo)
