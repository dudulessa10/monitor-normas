"""Alvos no banco, importação do YAML, migração do histórico e a CLI sobre o banco."""

import sqlite3

import monitor
from monitor_normas.alvos import RepositorioAlvos, carregar_config_banco
from monitor_normas.estado import Estado

YAML_GLOBAL = "regex:\n  resolucao: 'Resolução\\s+n[º°o]\\.?\\s*(\\d+)'\n"
YAML_ALVOS = """
alvos:
  - {id: a, ativo: true, url: 'https://x/a', extracao: {regex_numero: resolucao}}
  - {id: b, ativo: false, url: 'https://x/b', extracao: {tipo: rss}}
"""


def preparar(tmp_path):
    (tmp_path / "alvos.yaml").write_text(YAML_GLOBAL, encoding="utf-8")
    (tmp_path / "alvos_iniciais.yaml").write_text(YAML_ALVOS, encoding="utf-8")
    return tmp_path / "alvos.yaml", tmp_path / "dados" / "estado.db"


def test_importar_yaml_e_config_do_banco(tmp_path, capsys):
    config_yaml, db = preparar(tmp_path)
    assert monitor.main(["--config", str(config_yaml), "importar-yaml"]) == 0
    assert "2 alvo(s) importado(s)" in capsys.readouterr().out

    config = carregar_config_banco(config_yaml, db)
    assert [a.id for a in config.alvos] == ["a", "b"]
    assert config.alvo("a").ativo and config.alvo("a").regex_numero.pattern.startswith("Resolução")
    assert "rss" in config.alvo("b").erro_config  # importado mesmo inválido, como no YAML

    # Reimportar não sobrescreve alterações feitas pela web/API...
    with RepositorioAlvos(db) as repo:
        repo.definir_ativo("a", False)
    assert monitor.main(["--config", str(config_yaml), "importar-yaml"]) == 0
    assert "já existiam" in capsys.readouterr().out
    assert not carregar_config_banco(config_yaml, db).alvo("a").ativo
    # ...a não ser com --substituir.
    assert monitor.main(["--config", str(config_yaml), "importar-yaml", "--substituir"]) == 0
    assert carregar_config_banco(config_yaml, db).alvo("a").ativo


def test_cli_pede_importacao_quando_banco_vazio(tmp_path, capsys):
    config_yaml, _ = preparar(tmp_path)
    (tmp_path / "alvos.yaml").write_text(YAML_GLOBAL + YAML_ALVOS, encoding="utf-8")  # YAML antigo, com alvos
    assert monitor.main(["--config", str(config_yaml), "run"]) == 2
    assert "importar-yaml" in capsys.readouterr().out
    assert monitor.main(["--config", str(config_yaml), "list"]) == 2


def test_list_mostra_alvos_do_banco(tmp_path, capsys):
    config_yaml, _ = preparar(tmp_path)
    monitor.main(["--config", str(config_yaml), "importar-yaml"])
    capsys.readouterr()
    assert monitor.main(["--config", str(config_yaml), "list"]) == 0
    saida = capsys.readouterr().out
    assert "a " in saida and "config inválida" in saida


def test_migracao_agrupa_execucoes_antigas_em_rodadas(tmp_path):
    db = tmp_path / "estado.db"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE execucoes (id INTEGER PRIMARY KEY AUTOINCREMENT, alvo TEXT NOT NULL, inicio TEXT NOT NULL,
            fim TEXT NOT NULL, status TEXT NOT NULL, total INTEGER NOT NULL DEFAULT 0, novos INTEGER NOT NULL DEFAULT 0,
            alterados INTEGER NOT NULL DEFAULT 0, removidos INTEGER NOT NULL DEFAULT 0, modificacao_pagina TEXT, erro TEXT);
        INSERT INTO execucoes (alvo, inicio, fim, status) VALUES
            ('a', '2026-10-15T15:25:00-03:00', '2026-10-15T15:25:10-03:00', 'linha_base'),
            ('b', '2026-10-15T15:25:10-03:00', '2026-10-15T15:25:20-03:00', 'erro'),
            ('c', '2026-10-15T15:25:25-03:00', '2026-10-15T15:25:30-03:00', 'ok'),
            ('a', '2026-10-15T15:34:00-03:00', '2026-10-15T15:34:10-03:00', 'ok'),
            ('b', '2026-10-15T15:34:11-03:00', '2026-10-15T15:34:20-03:00', 'ok'),
            ('a', '2026-10-16T06:00:00-03:00', '2026-10-16T06:00:10-03:00', 'ok');
    """)
    con.close()
    with Estado(db) as estado:
        total, rodadas = estado.listar_rodadas()
    # 'c' veio 5 s depois (outra chamada do run); o 'a' repetido também abre outra rodada.
    assert total == 4
    assert [[e["alvo"] for e in r["execucoes"]] for r in reversed(rodadas)] == [["a", "b"], ["c"], ["a", "b"], ["a"]]
    assert rodadas[-1]["status"] == "com_erros" and rodadas[-1]["origem"] == "historico"
    with Estado(db) as estado:  # rodar de novo não duplica
        assert estado.listar_rodadas()[0] == 4
