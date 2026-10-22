import copy
import json
from datetime import timedelta

from bs4 import BeautifulSoup

from conftest import ColetorFalso, Relogio, ler_fixture
from monitor_normas import relatorio
from monitor_normas.coleta import ErroColeta
from monitor_normas.config import carregar_config
from monitor_normas.estado import Estado
from monitor_normas.execucao import Caminhos, executar
from monitor_normas.ledger import Ledger

URL_RES = "https://www.anac.gov.br/assuntos/legislacao/legislacao-1/resolucoes/{ano}"
URL_2026 = URL_RES.format(ano=2026)
URL_2025 = URL_RES.format(ano=2025)

YAML = f"""
regex:
  resolucao: 'Resolução\\s+n[º°o]\\.?\\s*(\\d+)'
  data_modificacao: 'última modificação\\s+(\\d{{2}}/\\d{{2}}/\\d{{4}})\\s+(\\d{{2}}h\\d{{2}})'
palavras_chave_globais: [RBAC, aeroporto]
alvos:
  - id: resolucoes
    ativo: true
    categoria: Resoluções
    url: "{URL_RES}"
    anos: [atual]
    deteccao: {{metodo: lista_itens, chave_item: norma}}
    extracao:
      colunas: {{Norma: norma, Publicação: publicacao, Ementa: ementa, Arquivo: link_arquivo}}
      regex_numero: resolucao
  - id: quebrado
    ativo: true
    url: "https://www.anac.gov.br/quebrado"
  - id: inativo
    ativo: false
    url: "https://www.anac.gov.br/inativo"
"""


def preparar(tmp_path):
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text(YAML, encoding="utf-8")
    return carregar_config(arquivo), Caminhos(tmp_path)


def html_modificado() -> bytes:
    """Resoluções 2026 com: 1 linha nova (818), 816 com ementa alterada e 789 removida."""
    sopa = BeautifulSoup(ler_fixture("anac-resolucoes"), "lxml")
    corpo = sopa.find("table").find("tbody")
    linhas = corpo.find_all("tr", recursive=False)
    nova = copy.copy(linhas[0])
    for a in nova.find_all("a"):
        a["href"] = a["href"].replace("817", "818")
        a.string = a.get_text().replace("817", "818")
    nova.find("td", class_="tbEmenta").string = "Altera regras de tarifa em aeroporto"
    linhas[0].insert_before(nova)
    linhas[1].find("td", class_="tbEmenta").string = "Aprova a Emenda nº 09 ao RBAC nº 91"
    linhas[-1].decompose()
    return str(sopa).encode("utf-8")


def test_primeira_execucao_e_linha_de_base_e_depois_detecta_mudancas(tmp_path):
    config, caminhos = preparar(tmp_path)
    relogio = Relogio()
    coletor = ColetorFalso({URL_2026: ler_fixture("anac-resolucoes"),
                            "https://www.anac.gov.br/quebrado": ErroColeta("HTTP 500")})

    resultados = executar(config, caminhos, coletor=coletor, relogio=relogio)
    por_id = {r.alvo.id: r for r in resultados}
    assert set(por_id) == {"resolucoes", "quebrado"}  # inativo não roda
    assert por_id["resolucoes"].status == "linha_base" and por_id["resolucoes"].total == 29
    assert por_id["quebrado"].status == "erro"

    blocos = [json.loads(l) for l in caminhos.ledger.read_text(encoding="utf-8").splitlines()]
    assert len(blocos) == 29 and {b["tipo_mudanca"] for b in blocos} == {"LINHA_BASE"}
    secao = relatorio.secao_execucao(resultados, relogio(), config.palavras_chave)
    assert "linha de base" in secao and "#### NOVO" not in secao

    # Segunda execução, com a página alterada.
    relogio.atual += timedelta(days=1)
    coletor.paginas[URL_2026] = html_modificado()
    resultados = executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=relogio)
    r = resultados[0]
    assert r.status == "ok"
    assert [(m.tipo, m.item.numero) for m in r.mudancas] == [("NOVO", "818"), ("ALTERADO", "816"), ("REMOVIDO", "789")]
    assert r.mudancas[1].diferencas["ementa"][1] == "Aprova a Emenda nº 09 ao RBAC nº 91"

    blocos = [json.loads(l) for l in caminhos.ledger.read_text(encoding="utf-8").splitlines()]
    novo = blocos[29]
    assert novo["tipo_mudanca"] == "NOVO" and novo["norma"] == "RESOLUÇÃO Nº 818, 07/10/2026"
    assert novo["palavras_chave"] == ["aeroporto", "RESOLUÇÃO", "818"]
    assert novo["data_publicacao"] == "2026-10-14"
    assert Ledger(caminhos.ledger).verificar().ok

    caminho = relatorio.gerar(resultados, caminhos.relatorios, relogio(), config.palavras_chave)
    assert caminho.name == "relatorio_2026-10-16.md"
    texto = caminho.read_text(encoding="utf-8")
    assert "#### NOVO — [RESOLUÇÃO Nº 818" in texto and "#### REMOVIDO" in texto

    with Estado(caminhos.estado_db) as estado:
        vigentes = estado.itens_vigentes("resolucoes")
        resumo = estado.resumo()
    assert len(vigentes) == 29 and "RESOLUÇÃO Nº 789, 16/01/2026" not in vigentes
    assert resumo["resolucoes"]["novos"] == 1 and resumo["quebrado"]["status"] == "erro"

    # Terceira execução, sem mudanças: nada novo no ledger.
    executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=relogio)
    assert Ledger(caminhos.ledger).verificar().total == 32


def test_pagina_vazia_nao_apaga_o_estado(tmp_path):
    config, caminhos = preparar(tmp_path)
    coletor = ColetorFalso({URL_2026: ler_fixture("anac-resolucoes")})
    executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=Relogio())
    sopa = BeautifulSoup(ler_fixture("anac-resolucoes"), "lxml")
    for tr in sopa.find("tbody").find_all("tr"):
        tr.decompose()
    coletor.paginas[URL_2026] = str(sopa).encode("utf-8")
    r = executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=Relogio())[0]
    assert r.status == "erro" and "sem itens" in r.erro
    with Estado(caminhos.estado_db) as estado:
        assert len(estado.itens_vigentes("resolucoes")) == 29


def test_virada_de_ano(tmp_path):
    """Com anos [atual, anterior], a página do ano novo ainda inexistente vira aviso, não erro."""
    config, caminhos = preparar(tmp_path)
    config.alvo("resolucoes").anos = ["atual", "anterior"]
    relogio = Relogio()
    relogio.atual = relogio.atual.replace(year=2027, month=1, day=2)
    coletor = ColetorFalso({URL_RES.format(ano=2026): ler_fixture("anac-resolucoes")})
    r = executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=relogio)[0]
    assert r.status == "linha_base" and r.total == 29
    assert any("ainda não existe" in a for a in r.avisos)


def test_ano_novo_conta_como_novo_depois_da_linha_de_base(tmp_path):
    config, caminhos = preparar(tmp_path)
    coletor = ColetorFalso({URL_2026: ler_fixture("anac-resolucoes")})
    executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=Relogio())
    # Em 2027 o alvo passa a ler 2027 e 2026; os itens de 2027 são NOVOS e os de 2026 não mudam.
    config.alvo("resolucoes").anos = ["atual", "anterior"]
    relogio = Relogio()
    relogio.atual = relogio.atual.replace(year=2027, month=1, day=20)
    url_2027 = URL_RES.format(ano=2027)
    html_2027 = (html_modificado().replace(b"/2026/", b"/2027/")
                 .replace("RESOLUÇÃO Nº ".encode(), "RESOLUÇÃO Nº 1".encode()))
    coletor.paginas[url_2027] = html_2027
    r = executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=relogio)[0]
    assert r.status == "ok"
    assert r.contar("REMOVIDO") == 0 and r.contar("NOVO") == 29 and r.contar("ALTERADO") == 0


def test_alvo_inexistente(tmp_path):
    config, caminhos = preparar(tmp_path)
    try:
        executar(config, caminhos, alvo_id="nao-existe", coletor=ColetorFalso({}))
    except KeyError:
        pass
    else:
        raise AssertionError("esperava KeyError")


def test_execucao_ancora_o_ledger_e_nao_ancora_se_adulterado(tmp_path):
    from monitor_normas.ancora import Ancoras, verificar_tudo

    config, caminhos = preparar(tmp_path)
    coletor = ColetorFalso({URL_2026: ler_fixture("anac-resolucoes")})
    executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=Relogio())
    ledger = Ledger(caminhos.ledger)
    [ancora] = Ancoras(ledger).lista()
    assert (ancora["indice"], ancora["hash"]) == ledger.ultimo()
    assert verificar_tudo(ledger).ok

    # Adultera um bloco: a próxima execução (com mudança) não pode ancorar o ledger.
    linhas = caminhos.ledger.read_text(encoding="utf-8").splitlines()
    bloco = json.loads(linhas[0])
    bloco["ementa"] = "adulterada"
    linhas[0] = json.dumps(bloco, ensure_ascii=False)
    caminhos.ledger.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    coletor.paginas[URL_2026] = html_modificado()
    executar(config, caminhos, alvo_id="resolucoes", coletor=coletor, relogio=Relogio())
    assert len(Ancoras(ledger).lista()) == 1


def test_falha_ao_gravar_o_estado_desfaz_o_ledger(tmp_path, monkeypatch):
    config, caminhos = preparar(tmp_path)
    executar(config, caminhos, alvo_id="resolucoes", coletor=ColetorFalso({URL_2026: ler_fixture("anac-resolucoes")}),
             relogio=Relogio())
    antes = caminhos.ledger.read_bytes()

    anexar = Ledger.anexar

    def anexar_e_falhar(self, registros):  # simula o commit do SQLite falhando depois do ledger gravado
        anexar(self, registros)
        raise RuntimeError("disco cheio")
    monkeypatch.setattr(Ledger, "anexar", anexar_e_falhar)
    [resultado] = executar(config, caminhos, alvo_id="resolucoes", coletor=ColetorFalso({URL_2026: html_modificado()}),
                           relogio=Relogio())
    assert resultado.status == "erro"
    assert caminhos.ledger.read_bytes() == antes  # nada do ledger sem o estado correspondente
    with Estado(caminhos.estado_db) as estado:
        assert len(estado.itens_vigentes("resolucoes")) == 29  # e o estado também não mudou


def test_ledger_desfazer_corta_so_o_que_foi_anexado(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.anexar([{"norma": "A"}])
    posicao = ledger.tamanho()
    ledger.anexar([{"norma": "B"}, {"norma": "C"}])
    ledger.desfazer(posicao)
    assert [b["norma"] for b in ledger.blocos()] == ["A"] and ledger.verificar().ok


def test_dados_em_outra_pasta_pela_variavel_de_ambiente(tmp_path, monkeypatch):
    from monitor_normas.execucao import caminhos_padrao
    assert caminhos_padrao(tmp_path).base == tmp_path.resolve()
    monkeypatch.setenv("MONITOR_NORMAS_BASE", str(tmp_path / "srv"))
    assert caminhos_padrao(tmp_path).estado_db == (tmp_path / "srv" / "dados" / "estado.db").resolve()
