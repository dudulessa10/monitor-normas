import json
from dataclasses import asdict

from monitor_normas.deteccao import ALTERADO, NOVO, REMOVIDO, comparar
from monitor_normas.extracao import Item, calcular_hash
from monitor_normas.ledger import GENESIS, Ledger
from monitor_normas.palavras_chave import encontrar, palavras_do_item


def item(chave, ementa="x", origem="https://a"):
    campos = {"norma": chave, "ementa": ementa}
    return Item(chave=chave, campos=campos, origem=origem, hash=calcular_hash(campos, list(campos)))


def salvo(i: Item) -> dict:
    return {"hash": i.hash, "origem": i.origem, "dados": asdict(i)}


def test_comparar_novo_alterado_removido():
    anteriores = {i.chave: salvo(i) for i in [item("A"), item("B"), item("C")]}
    atuais = [item("A"), item("B", ementa="nova"), item("D")]
    mudancas = comparar(atuais, anteriores, {"https://a"})
    assert [(m.tipo, m.item.chave) for m in mudancas] == [(NOVO, "D"), (ALTERADO, "B"), (REMOVIDO, "C")]
    assert mudancas[1].diferencas == {"ementa": ("x", "nova")}


def test_mudar_colunas_no_yaml_nao_gera_alterado():
    """Antes 'auto' (campo arquivo='Abrir'); agora mapeado (link_arquivo, fora do hash)."""
    antigo = Item(chave="A", campos={"norma": "A", "ementa": "x", "arquivo": "Abrir"}, origem="https://a")
    antigo.hash = calcular_hash(antigo.campos, list(antigo.campos))
    novo = Item(chave="A", campos={"norma": "A", "ementa": "x", "link_arquivo": "https://pdf"},
                origem="https://a", campos_monitorados=["norma", "ementa"])
    novo.hash = calcular_hash(novo.campos, novo.campos_monitorados)
    assert comparar([novo], {"A": salvo(antigo)}, {"https://a"}) == []
    novo.campos["ementa"] = "y"
    novo.hash = calcular_hash(novo.campos, novo.campos_monitorados)
    [mudanca] = comparar([novo], {"A": salvo(antigo)}, {"https://a"})
    assert mudanca.diferencas == {"ementa": ("x", "y")}


def test_removido_so_se_a_pagina_de_origem_foi_coletada():
    anteriores = {"V": salvo(item("V", origem="https://ano/2025"))}
    assert comparar([], anteriores, {"https://ano/2026"}) == []


def test_palavras_chave():
    assert encontrar("Regras para AERODROMOS e drones", ["aeródromo", "drone", "tarifa"]) == ["aeródromo", "drone"]
    i = item("RESOLUÇÃO Nº 1", ementa="Aprova a Emenda ao RBAC nº 91")
    i.tipo, i.numero = "RESOLUÇÃO", "1"
    assert palavras_do_item(i, ["RBAC", "tarifa"]) == ["RBAC", "RESOLUÇÃO", "1"]


def registro(n):
    return {"timestamp": "2026-10-15T06:00:00+00:00", "alvo": "a", "tipo_mudanca": NOVO, "norma": f"N{n}",
            "link": "https://x", "data_publicacao": "2026-10-14", "ementa": "é", "palavras_chave": ["RBAC"]}


def test_ledger_encadeia_e_verifica(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    primeiro = ledger.anexar([registro(1), registro(2)])
    segundo = ledger.anexar([registro(3)])
    assert primeiro[0]["hash_anterior"] == GENESIS
    assert segundo[0]["indice"] == 2 and segundo[0]["hash_anterior"] == primeiro[1]["hash"]
    assert list(primeiro[0]) == ["indice", "timestamp", "alvo", "tipo_mudanca", "norma", "link",
                                 "data_publicacao", "ementa", "palavras_chave", "hash_anterior", "hash"]
    resultado = ledger.verificar()
    assert resultado.ok and resultado.total == 3


def test_ledger_detecta_adulteracao(tmp_path):
    caminho = tmp_path / "ledger.jsonl"
    Ledger(caminho).anexar([registro(1), registro(2), registro(3)])
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    bloco = json.loads(linhas[1])
    bloco["ementa"] = "adulterada"
    linhas[1] = json.dumps(bloco, ensure_ascii=False)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    resultado = Ledger(caminho).verificar()
    assert not resultado.ok
    assert any("linha 2" in e for e in resultado.erros)


def test_ledger_detecta_bloco_apagado(tmp_path):
    caminho = tmp_path / "ledger.jsonl"
    Ledger(caminho).anexar([registro(1), registro(2), registro(3)])
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    caminho.write_text("\n".join([linhas[0], linhas[2]]) + "\n", encoding="utf-8")
    assert not Ledger(caminho).verificar().ok
