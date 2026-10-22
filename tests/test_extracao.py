from dataclasses import replace

import pytest

from conftest import URLS_FIXTURES, ler_fixture
from monitor_normas.extracao import (ErroExtracao, data_modificacao_pagina, desambiguar, extrair_linhas,
                                     item_data_modificacao, item_hash_conteudo, montar_itens)


def itens_do_alvo(config, alvo_id):
    alvo = config.alvo(alvo_id)
    url = URLS_FIXTURES[alvo_id]
    linhas = extrair_linhas(ler_fixture(alvo_id), url, tabela=alvo.tabela, colunas=alvo.colunas)
    itens = montar_itens(linhas, alvo, config.regex, url)
    desambiguar(itens, alvo.chave_item)
    return itens


@pytest.mark.parametrize("alvo_id, quantidade, primeira", [
    ("anac-resolucoes", 29, "RESOLUÇÃO Nº 817, 07/10/2026"),
    ("anac-rbac", 55, "RBAC 01 EMD 18"),
    ("anac-portarias", 1260, "PORTARIA Nº 20180/SPO, 09/10/2026"),
    ("anac-portarias-regulatorias", 44, "PORTARIA REGULATÓRIA Nº 58/SAR, 30/09/2026"),
    ("anac-is", 237, "IS 00-001B"),
    ("anac-decisoes", 23, "DECISÃO Nº 760, 13/10/2026"),
    ("anac-instrucoes-normativas", 1, "INSTRUÇÃO NORMATIVA Nº 218, 19/01/2026"),
    ("anac-condicoes-especiais", 89, "CE/SC nº 23-002"),
])
def test_tabelas_reais(config_real, alvo_id, quantidade, primeira):
    itens = itens_do_alvo(config_real, alvo_id)
    assert len(itens) == quantidade
    assert itens[0].chave == primeira
    assert len({i.chave for i in itens}) == quantidade  # chaves únicas
    assert all(i.campos.get("ementa") for i in itens)
    assert all(i.link.startswith("https://www.anac.gov.br/") for i in itens)


def test_colunas_mapeadas_resolucoes(config_real):
    item = itens_do_alvo(config_real, "anac-resolucoes")[0]
    assert item.campos["publicacao"] == "DOU 14/10/2026, Seção 1, pág. 58"
    assert item.ementa.startswith("Estabelece procedimentos")
    assert item.link == "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/resolucoes/2026/resolucao-817"
    assert (item.numero, item.tipo) == ("817", "RESOLUÇÃO")
    assert (item.data_norma, item.data_publicacao) == ("2026-10-07", "2026-10-14")


def test_colunas_auto_usam_cabecalho(config_real):
    alvo = replace(config_real.alvo("anac-portarias"), colunas=None)
    url = URLS_FIXTURES["anac-portarias"]
    item = montar_itens(extrair_linhas(ler_fixture("anac-portarias"), url), alvo, config_real.regex, url)[0]
    assert {"norma", "publicacao", "ementa", "arquivo", "arquivo_link"} <= set(item.campos)
    assert item.link.endswith("/portarias/2026/portaria-20180")
    assert (item.numero, item.tipo) == ("20180", "PORTARIA")


def test_numero_rbac_e_is(config_real):
    rbac = itens_do_alvo(config_real, "anac-rbac")[0]
    assert (rbac.numero, rbac.tipo, rbac.data_publicacao) == ("RBAC 01 EMD 18", "RBAC", "2025-04-18")
    ist = itens_do_alvo(config_real, "anac-is")[0]
    assert (ist.numero, ist.tipo) == ("00-001B", "IS")


def test_numero_portaria_regulatoria(config_real):
    item = itens_do_alvo(config_real, "anac-portarias-regulatorias")[0]
    assert (item.numero, item.tipo) == ("58", "PORTARIA REGULATÓRIA")


def test_numero_generico_quando_nao_ha_regex(config_real):
    ce = itens_do_alvo(config_real, "anac-condicoes-especiais")[0]
    assert (ce.numero, ce.tipo) == ("23-002", "CE/SC")
    alvo = replace(config_real.alvo("anac-is"), regex_numero=None)
    url = URLS_FIXTURES["anac-is"]
    linhas = extrair_linhas(ler_fixture("anac-is"), url, colunas=alvo.colunas)
    assert montar_itens(linhas, alvo, config_real.regex, url)[0].numero == "00-001B"


def test_status_alterada_rbac(config_real):
    itens = {i.chave: i for i in itens_do_alvo(config_real, "anac-rbac")}
    assert itens["RBAC 21 EMD 15 [rbac-21-emd-15]"].status == ["alterada"]
    assert itens["RBAC 21 EMD 15 [rbac-21]"].status == []


def test_chaves_duplicadas_usam_link(config_real):
    chaves = {i.chave for i in itens_do_alvo(config_real, "anac-rbac")}
    assert {"RBAC 108 EMD 10 [rbac-108-emd-10]", "RBAC 108 EMD 10 [rbac-108-emd-10-1]"} <= chaves
    assert "RBAC 108 EMD 10" not in chaves


def test_duplicata_sem_link_recebe_numero_sequencial(config_real):
    html = ("<table><tr><th>Norma</th><th>Ementa</th></tr>"
            "<tr><td>X 1</td><td>a</td></tr><tr><td>X 1</td><td>b</td></tr></table>")
    alvo = config_real.alvo("anac-portarias")
    itens = montar_itens(extrair_linhas(html, "https://x/"), alvo, config_real.regex, "https://x/")
    avisos = desambiguar(itens)
    assert [i.chave for i in itens] == ["X 1 #1", "X 1 #2"]
    assert avisos


def test_data_modificacao_da_pagina(config_real):
    assert data_modificacao_pagina(ler_fixture("anac-resolucoes"), config_real.regex["data_modificacao"]) \
        == "14/10/2026 11h13"


def test_pagina_sem_tabela():
    with pytest.raises(ErroExtracao, match="nenhuma tabela"):
        extrair_linhas("<html><body><div id='content-core'><a href='/2026'>2026</a></div></body></html>", "https://x/")


def test_coluna_mapeada_ausente():
    html = "<table><tr><th>Norma</th><th>Data</th></tr><tr><td>A</td><td>01/01/2026</td></tr></table>"
    with pytest.raises(ErroExtracao, match="Ementa"):
        extrair_linhas(html, "https://x/", colunas={"Norma": "norma", "Ementa": "ementa"})


def test_tabela_todas():
    html = ("<table><tr><th>Norma</th></tr><tr><td>Lei 1</td></tr></table>"
            "<table><tr><th>Norma</th></tr><tr><td>Decreto 2</td></tr></table>")
    assert len(extrair_linhas(html, "https://x/", tabela="primeira")) == 1
    assert [l["norma"] for l in extrair_linhas(html, "https://x/", tabela="todas")] == ["Lei 1", "Decreto 2"]


def test_metodos_de_pagina_inteira():
    a = item_hash_conteudo("<div id='content-core'>texto A</div>", "https://x/")
    b = item_hash_conteudo("<div id='content-core'>texto B</div>", "https://x/")
    assert a.chave == "https://x/" and a.hash != b.hash
    item = item_data_modificacao(ler_fixture("anac-rbac"), "https://x/")
    assert item.campos["modificacao"].count("/") == 2


def test_link_com_espaco_nao_e_cortado():
    html = """<table><tr><th>Norma</th><th>Arquivo</th></tr>
    <tr><td>RESOLUÇÃO Nº 1</td><td><a href="/pasta/resolucao 1.pdf">pdf</a> <a href="/outro.pdf">pdf</a></td></tr>
    </table>"""
    [linha] = extrair_linhas(html, "https://exemplo.gov.br/x", colunas={"Norma": "norma", "Arquivo": "link_arquivo"})
    assert linha["link_arquivo"] == "https://exemplo.gov.br/pasta/resolucao%201.pdf https://exemplo.gov.br/outro.pdf"
