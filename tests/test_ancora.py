import json
from datetime import datetime, timezone

import pytest

import monitor
from monitor_normas.ancora import Ancoras, ancorar, ler_externa, verificar_tudo
from monitor_normas.ledger import GENESIS, Ledger, calcular_hash

QUANDO = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)


def registro(n):
    return {"timestamp": "2026-10-15T06:00:00+00:00", "alvo": "a", "tipo_mudanca": "NOVO", "norma": f"N{n}",
            "link": "https://x", "data_publicacao": "2026-10-14", "ementa": f"ementa {n}", "palavras_chave": []}


@pytest.fixture
def ledger(tmp_path):
    ledger = Ledger(tmp_path / "dados" / "ledger.jsonl")
    ledger.anexar([registro(0), registro(1), registro(2)])
    Ancoras(ledger).registrar(QUANDO)
    ledger.anexar([registro(3)])
    Ancoras(ledger).registrar(QUANDO)
    return ledger


def reescrever(ledger, mudar):
    """Adulteração 'inteligente': muda blocos e recalcula a cadeia inteira."""
    blocos = list(ledger.blocos())
    mudar(blocos)
    anterior = GENESIS
    linhas = []
    for i, bloco in enumerate(blocos):
        bloco["indice"], bloco["hash_anterior"] = i, anterior
        bloco["hash"] = anterior = calcular_hash(bloco)
        linhas.append(json.dumps(bloco, ensure_ascii=False))
    ledger.caminho.write_text("".join(l + "\n" for l in linhas), encoding="utf-8")


def erros(ledger, externas=()):
    return verificar_tudo(ledger, list(externas)).erros


def test_ledger_ancorado_e_integro(ledger):
    resultado = verificar_tudo(ledger)
    assert resultado.ok and resultado.ancoras == 2 and resultado.avisos == []
    [a1, a2] = Ancoras(ledger).lista()
    assert (a1["indice"], a2["indice"]) == (2, 3) and a2["anterior"] == a1["hmac"]


def test_registrar_e_idempotente(ledger):
    Ancoras(ledger).registrar(QUANDO)
    assert len(Ancoras(ledger).lista()) == 2


def test_reescrita_completa_com_hashes_recalculados(ledger):
    reescrever(ledger, lambda b: b[1].update(ementa="adulterada"))
    assert ledger.verificar().ok  # a cadeia sozinha não percebe
    assert any("bloco 2 não confere" in e and "reescrito" in e for e in erros(ledger))


def test_blocos_apagados_do_final(ledger):
    reescrever(ledger, lambda b: b.pop())
    assert ledger.verificar().ok
    assert any("ledger termina no bloco 2" in e for e in erros(ledger))


def test_ledger_inteiro_apagado_nao_passa_como_vazio(ledger, tmp_path, capsys):
    ledger.caminho.unlink()
    config = tmp_path / "alvos.yaml"
    config.write_text("alvos: []\n", encoding="utf-8")
    assert monitor.main(["--config", str(config), "verificar-ledger"]) == 1
    assert "blocos apagados do final" in capsys.readouterr().out


def test_ancora_alterada_sem_a_chave(ledger):
    reescrever(ledger, lambda b: b[3].update(ementa="adulterada"))
    caminho = Ancoras(ledger).caminho
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    ancora = json.loads(linhas[1])
    ancora["hash"] = list(ledger.blocos())[3]["hash"]  # aponta para o bloco forjado
    linhas[1] = json.dumps(ancora)
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    assert any("assinatura inválida" in e for e in erros(ledger))


def test_ancora_do_meio_apagada(ledger):
    caminho = Ancoras(ledger).caminho
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    caminho.write_text(linhas[1] + "\n", encoding="utf-8")
    assert any("encadeamento das âncoras" in e for e in erros(ledger))


def test_arquivo_de_ancoras_apagado_junto_com_o_final(ledger):
    """Quem só tem a pasta do projeto apaga ancoras.jsonl e corta o ledger: a cópia local denuncia."""
    reescrever(ledger, lambda b: b.pop())
    Ancoras(ledger).caminho.unlink()
    lista = erros(ledger)
    assert any("não está em ancoras.jsonl" in e for e in lista)
    assert any("ledger termina no bloco 2" in e for e in lista)


def test_sem_a_chave_confere_hashes_e_avisa(ledger, pasta_segura_isolada):
    (pasta_segura_isolada / "chave_ledger.bin").unlink()
    resultado = verificar_tudo(ledger)
    assert resultado.ok and "2 âncora(s) com assinatura não conferida" in resultado.avisos[0]
    reescrever(ledger, lambda b: b[0].update(ementa="x"))
    assert not verificar_tudo(ledger).ok


def test_ledger_sem_ancoras_so_avisa(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.anexar([registro(0)])
    resultado = verificar_tudo(ledger)
    assert resultado.ok and "ainda não tem âncoras" in resultado.avisos[0]


def test_ancora_externa(ledger):
    """Protege até contra quem tem a chave: refaz cadeia E âncoras."""
    blocos = list(ledger.blocos())
    externa = (3, blocos[3]["hash"][:12])
    assert erros(ledger, [externa]) == []
    reescrever(ledger, lambda b: b[0].update(ementa="x"))
    Ancoras(ledger).caminho.unlink()
    Ancoras(ledger).copia_local.unlink()
    Ancoras(ledger).registrar(QUANDO)  # atacante com a chave reancora
    assert erros(ledger) == []
    assert any("âncora externa" in e and "reescrito" in e for e in erros(ledger, [externa]))
    assert any("ledger termina no bloco 3" in e for e in erros(ledger, [(9, "a" * 12)]))


def test_ler_externa():
    assert ler_externa(" 1739:16981E4AC237daaf ") == (1739, "16981e4ac237daaf")
    for ruim in ("1739", "x:16981e4ac237", "1739:16981e", "1739:zz981e4ac237"):
        with pytest.raises(ValueError):
            ler_externa(ruim)


def test_ancorar_recusa_ledger_adulterado(ledger):
    reescrever(ledger, lambda b: b[1].update(ementa="adulterada"))
    ancora, verificacao = ancorar(ledger, QUANDO)
    assert ancora is None and not verificacao.ok
    assert len(Ancoras(ledger).lista()) == 2


def test_cli_ancora_e_verificar(ledger, tmp_path, capsys):
    config = tmp_path / "alvos.yaml"
    config.write_text("alvos: []\n", encoding="utf-8")
    ledger.anexar([registro(4)])
    assert monitor.main(["--config", str(config), "ancora"]) == 0
    saida = capsys.readouterr().out
    hash4 = list(ledger.blocos())[4]["hash"]
    assert f"4:{hash4}" in saida

    assert monitor.main(["--config", str(config), "verificar-ledger", "--ancora", f"4:{hash4[:16]}"]) == 0
    assert "5 blocos, cadeia de hashes válida, 4 âncora(s) conferida(s)" in capsys.readouterr().out

    assert monitor.main(["--config", str(config), "verificar-ledger", "--ancora", f"4:{'0' * 16}"]) == 1
    assert "âncora externa" in capsys.readouterr().out

    with pytest.raises(SystemExit):
        monitor.main(["--config", str(config), "verificar-ledger", "--ancora", "4"])
