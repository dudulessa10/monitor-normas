from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from api.main import criar_app
from conftest import ColetorFalso, ler_fixture
from monitor_normas.alvos import RepositorioAlvos
from monitor_normas.estado import Estado
from monitor_normas.execucao import Caminhos, Trava
from test_execucao import URL_2026, html_modificado

GLOBAIS = r"""
padroes: {pausa_entre_requisicoes_segundos: 0}
regex:
  resolucao: 'Resolução\s+n[º°o]\.?\s*(\d+)'
  revogada: '\bRevogad[ao]\b'
palavras_chave_globais: [RBAC, aeroporto, tarifa]
"""

RESOLUCOES = {
    "id": "resolucoes", "ativo": True, "site": "ANAC", "categoria": "Resoluções", "prioridade": "alta",
    "url": URL_2026,  # sem {ano}: o teste não pode depender do ano do relógio
    "deteccao": {"metodo": "lista_itens", "chave_item": "norma"},
    "extracao": {"tabela": "primeira", "regex_numero": "resolucao",
                 "colunas": {"Norma": "norma", "Publicação": "publicacao", "Ementa": "ementa",
                             "Arquivo": "link_arquivo"}},
}


@pytest.fixture
def ambiente(tmp_path):
    (tmp_path / "alvos.yaml").write_text(GLOBAIS, encoding="utf-8")
    coletor = ColetorFalso({URL_2026: ler_fixture("anac-resolucoes")})
    app = criar_app(tmp_path, fabrica_coletor=lambda: coletor, registrar_log=False)
    with TestClient(app) as cliente:
        yield cliente, coletor, app.state.contexto


def rodar_e_esperar(cliente, ctx, corpo=None):
    resposta = cliente.post("/api/v1/execucoes", json=corpo)
    assert resposta.status_code == 202, resposta.text
    ctx.executor.esperar(timeout=30)
    assert resposta.headers["location"] == resposta.json()["url"] == f"/api/v1/execucoes/{resposta.json()['rodada_id']}"
    return cliente.get(resposta.json()["url"]).json()


# ---------------------------------------------------------------- servidor

def test_frontend_e_documentacao(ambiente):
    cliente, _, _ = ambiente
    pagina = cliente.get("/")
    assert pagina.status_code == 200 and "Monitor de Normas" in pagina.text
    assert cliente.get("/js/app.js").status_code == 200
    assert cliente.get("/docs").status_code == 200
    caminhos = cliente.get("/openapi.json").json()["paths"]
    for caminho in ("/api/v1/alvos", "/api/v1/alvos/{alvo_id}/ativar", "/api/v1/execucoes", "/api/v1/mudancas",
                    "/api/v1/normas", "/api/v1/ledger", "/api/v1/ledger/verificar", "/api/v1/exportar/excel"):
        assert caminho in caminhos


# ---------------------------------------------------------------- alvos

def test_crud_de_alvos(ambiente):
    cliente, _, _ = ambiente
    criado = cliente.post("/api/v1/alvos", json=RESOLUCOES)
    assert criado.status_code == 201, criado.text
    assert criado.headers["location"] == "/api/v1/alvos/resolucoes"
    assert criado.json()["valido"] and criado.json()["ultima_execucao"] is None

    assert cliente.post("/api/v1/alvos", json=RESOLUCOES).status_code == 409
    assert [a["id"] for a in cliente.get("/api/v1/alvos").json()] == ["resolucoes"]

    alterado = cliente.put("/api/v1/alvos/resolucoes", json={**RESOLUCOES, "categoria": "Resoluções ANAC"})
    assert alterado.status_code == 200 and alterado.json()["categoria"] == "Resoluções ANAC"
    assert cliente.put("/api/v1/alvos/resolucoes", json={**RESOLUCOES, "id": "outro"}).status_code == 422
    assert cliente.put("/api/v1/alvos/nao-existe", json={**RESOLUCOES, "id": "nao-existe"}).status_code == 404

    assert cliente.post("/api/v1/alvos/resolucoes/desativar").json()["ativo"] is False
    assert cliente.post("/api/v1/alvos/resolucoes/ativar").json()["ativo"] is True

    assert cliente.delete("/api/v1/alvos/resolucoes").status_code == 204
    assert cliente.get("/api/v1/alvos/resolucoes").status_code == 404
    assert cliente.delete("/api/v1/alvos/resolucoes").status_code == 404


def test_validacao_de_alvos(ambiente):
    cliente, _, _ = ambiente
    # Campo desconhecido (erro de digitação) é recusado, em vez de ignorado como no YAML.
    erro = cliente.post("/api/v1/alvos", json={**RESOLUCOES, "deteccao": {"detectar_mudanca_en": ["x"]}})
    assert erro.status_code == 422 and "detectar_mudanca_en" in erro.text
    # Regex inexistente: mesma validação de montar_alvo, com a mensagem dela.
    erro = cliente.post("/api/v1/alvos", json={**RESOLUCOES, "extracao": {"regex_numero": "nao_existe"}})
    assert erro.status_code == 422 and "nao_existe" in erro.json()["detail"]
    assert cliente.post("/api/v1/alvos", json={**RESOLUCOES, "url": "ftp://x"}).status_code == 422
    assert cliente.post("/api/v1/alvos", json={**RESOLUCOES, "id": "Com Espaço"}).status_code == 422


def test_alvo_invalido_importado_nao_pode_ser_ativado(ambiente):
    cliente, _, ctx = ambiente
    with RepositorioAlvos(ctx.caminhos.estado_db) as repo:
        repo.criar({"id": "rss", "ativo": False, "url": "https://x/rss", "extracao": {"tipo": "rss"}})
    [alvo] = cliente.get("/api/v1/alvos").json()
    assert alvo["valido"] is False and "rss" in alvo["erro_config"]
    resposta = cliente.post("/api/v1/alvos/rss/ativar")
    assert resposta.status_code == 422 and "corrija" in resposta.json()["detail"]


# ---------------------------------------------------------------- execuções e consultas

def test_execucao_em_segundo_plano_mudancas_normas_ledger_e_excel(ambiente):
    cliente, coletor, ctx = ambiente
    cliente.post("/api/v1/alvos", json=RESOLUCOES)

    rodada = rodar_e_esperar(cliente, ctx)
    assert rodada["status"] == "ok" and rodada["origem"] == "web" and rodada["total"] == 29
    assert rodada["execucoes"][0]["status"] == "linha_base"
    assert cliente.get("/api/v1/mudancas").json()["total"] == 0  # linha de base não é mudança

    coletor.paginas[URL_2026] = html_modificado()
    rodada = rodar_e_esperar(cliente, ctx, {"alvo": "resolucoes"})
    assert (rodada["novos"], rodada["alterados"], rodada["removidos"]) == (1, 1, 1)

    historico = cliente.get("/api/v1/execucoes").json()
    assert historico["total"] == 2 and [r["id"] for r in historico["itens"]] == [rodada["id"], rodada["id"] - 1]

    mudancas = cliente.get("/api/v1/mudancas").json()
    assert [m["tipo_mudanca"] for m in mudancas["itens"]] == ["REMOVIDO", "ALTERADO", "NOVO"]
    assert cliente.get("/api/v1/mudancas", params={"tipo": "NOVO"}).json()["total"] == 1
    [novo] = cliente.get("/api/v1/mudancas", params={"palavra": "aeroporto"}).json()["itens"]
    assert novo["norma"].startswith("RESOLUÇÃO Nº 818") and "aeroporto" in novo["palavras_chave"]
    assert cliente.get("/api/v1/mudancas", params={"incluir_linha_base": True}).json()["total"] == 32
    assert cliente.get("/api/v1/mudancas", params={"de": "2027-01-01"}).json()["total"] == 0
    pagina = cliente.get("/api/v1/mudancas", params={"limite": 2, "deslocamento": 2}).json()
    assert pagina["total"] == 3 and len(pagina["itens"]) == 1

    normas = cliente.get("/api/v1/normas").json()
    assert normas["total"] == 29
    [n818] = cliente.get("/api/v1/normas", params={"q": "818"}).json()["itens"]
    assert n818["numero"] == "818" and n818["link"].startswith("https://")

    assert cliente.get("/api/v1/ledger", params={"limite": 1}).json()["itens"][0]["indice"] == 31
    verificacao = cliente.get("/api/v1/ledger/verificar").json()
    assert verificacao["ok"] and verificacao["blocos"] == 32 and verificacao["ancora_atual"].startswith("31:")
    externa = verificacao["ancora_atual"][:20]
    assert cliente.get("/api/v1/ledger/verificar", params={"ancora": externa}).json()["ok"]
    assert cliente.get("/api/v1/ledger/verificar", params={"ancora": "31:abc"}).status_code == 422

    planilha = cliente.get("/api/v1/exportar/excel", params={"tipo": "NOVO"})
    assert planilha.status_code == 200
    assert "attachment" in planilha.headers["content-disposition"]
    wb = load_workbook(BytesIO(planilha.content))
    assert wb.sheetnames == ["Mudanças", "Normas vigentes", "Execuções"]
    assert wb["Mudanças"].max_row == 2 and wb["Normas vigentes"].max_row == 30
    assert wb["Mudanças"]["H2"].hyperlink is not None


def test_erro_de_um_alvo_aparece_na_rodada(ambiente):
    cliente, coletor, ctx = ambiente
    cliente.post("/api/v1/alvos", json=RESOLUCOES)
    del coletor.paginas[URL_2026]
    rodada = rodar_e_esperar(cliente, ctx)
    assert rodada["status"] == "com_erros" and rodada["erros"] == 1
    assert "HTTP 404" in rodada["execucoes"][0]["erro"]
    assert cliente.get("/api/v1/alvos/resolucoes").json()["ultima_execucao"]["status"] == "erro"


def test_execucao_simultanea_e_alvo_inexistente(ambiente):
    cliente, _, ctx = ambiente
    cliente.post("/api/v1/alvos", json=RESOLUCOES)
    trava = Trava(ctx.caminhos.trava).adquirir()  # como se a CLI ou o agendamento estivessem rodando
    try:
        resposta = cliente.post("/api/v1/execucoes", json={})
        assert resposta.status_code == 409 and "em andamento" in resposta.json()["detail"]
    finally:
        trava.liberar()
    assert cliente.post("/api/v1/execucoes", json={"alvo": "nao-existe"}).status_code == 404
    assert cliente.get("/api/v1/execucoes").json()["total"] == 0  # nada foi registrado
    assert cliente.post("/api/v1/execucoes").status_code == 202  # sem corpo = todos os ativos
    ctx.executor.esperar(timeout=30)


def test_rodadas_orfas_viram_interrompidas_ao_subir(tmp_path):
    (tmp_path / "alvos.yaml").write_text(GLOBAIS, encoding="utf-8")
    with Estado(Caminhos(tmp_path).estado_db) as estado:
        rodada_id = estado.criar_rodada("web", None, "2026-10-16T10:00:00-03:00")
    with TestClient(criar_app(tmp_path, registrar_log=False)) as cliente:
        rodada = cliente.get(f"/api/v1/execucoes/{rodada_id}").json()
    assert rodada["status"] == "interrompida" and rodada["erro"]


def test_configuracao(ambiente):
    cliente, _, _ = ambiente
    config = cliente.get("/api/v1/configuracao").json()
    assert set(config["regex"]) == {"resolucao", "revogada"} and config["horario"] == "06:00"


def test_saude_sem_rodadas(ambiente):
    cliente, _, _ = ambiente
    resposta = cliente.get("/api/v1/saude")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "ok" and resposta.json()["ultima_rodada_inicio"] is None


def test_senha_protege_tudo_menos_a_saude(tmp_path):
    (tmp_path / "alvos.yaml").write_text(GLOBAIS, encoding="utf-8")
    app = criar_app(tmp_path, registrar_log=False, credenciais=("ana", "s3gr3d0"))
    with TestClient(app) as cliente:
        assert cliente.get("/api/v1/saude").status_code == 200
        for caminho in ("/", "/api/v1/alvos", "/docs"):
            resposta = cliente.get(caminho)
            assert resposta.status_code == 401 and resposta.headers["www-authenticate"].startswith("Basic")
        assert cliente.get("/api/v1/alvos", auth=("ana", "errada")).status_code == 401
        assert cliente.get("/api/v1/alvos", headers={"Authorization": "Basic !!!"}).status_code == 401
        assert cliente.get("/api/v1/alvos", auth=("ana", "s3gr3d0")).status_code == 200
        assert cliente.post("/api/v1/execucoes", json={"alvo": None}).status_code == 401


def test_senha_vem_do_ambiente(tmp_path, monkeypatch):
    (tmp_path / "alvos.yaml").write_text(GLOBAIS, encoding="utf-8")
    monkeypatch.setenv("MONITOR_NORMAS_SENHA", "abc")
    with TestClient(criar_app(tmp_path, registrar_log=False)) as cliente:
        assert cliente.get("/api/v1/alvos").status_code == 401
        assert cliente.get("/api/v1/alvos", auth=("admin", "abc")).status_code == 200
