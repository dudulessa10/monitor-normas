import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path, PurePosixPath

import pytest

import monitor
from monitor_normas import agendamento
from monitor_normas.busca import Filtros, buscar
from monitor_normas.config import ErroConfig, carregar_config
from monitor_normas.execucao import ExecucaoEmAndamento, trava_exclusiva
from monitor_normas.ledger import Ledger

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
PY = Path(r"C:\proj\.venv\Scripts\pythonw.exe")
SCRIPT = Path(r"C:\proj & cia\monitor.py")
CONFIG = Path(r"C:\proj & cia\alvos.yaml")


# ---------------------------------------------------------------- configuração

def test_frequencia_e_horario_do_yaml(config_real, tmp_path):
    assert (config_real.frequencia, config_real.horario) == ("diaria", "06:00")
    arquivo = tmp_path / "alvos.yaml"
    arquivo.write_text("padroes: {frequencia: Semanal, horario: '7:30'}\nalvos: []\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match="horário"):
        carregar_config(arquivo)
    arquivo.write_text("padroes: {frequencia: mensal}\nalvos: []\n", encoding="utf-8")
    with pytest.raises(ErroConfig, match="frequência"):
        carregar_config(arquivo)
    arquivo.write_text("padroes: {frequencia: Semanal, horario: '23:59'}\nalvos: []\n", encoding="utf-8")
    assert carregar_config(arquivo).frequencia == "semanal"


# ---------------------------------------------------------------- agendamento

def test_xml_da_tarefa_diaria():
    xml = agendamento.xml_tarefa(PY, SCRIPT, CONFIG, "06:00", "diaria", date(2026, 10, 16))
    raiz = ET.fromstring(xml.split("?>", 1)[1])  # o ET não aceita a declaração UTF-16 em str
    gatilho = raiz.find("t:Triggers/t:CalendarTrigger", NS)
    assert gatilho.find("t:StartBoundary", NS).text == "2026-10-16T06:00:00"
    assert gatilho.find("t:ScheduleByDay/t:DaysInterval", NS).text == "1"
    assert raiz.find("t:Settings/t:StartWhenAvailable", NS).text == "true"
    assert raiz.find("t:Settings/t:MultipleInstancesPolicy", NS).text == "IgnoreNew"
    exec_ = raiz.find("t:Actions/t:Exec", NS)
    assert exec_.find("t:Command", NS).text == str(PY)
    assert exec_.find("t:Arguments", NS).text == f'"{SCRIPT}" --config "{CONFIG}" run --origem agendamento'  # "&" escapado e lido de volta
    assert exec_.find("t:WorkingDirectory", NS).text == str(SCRIPT.parent)


def test_xml_semanal_e_manual():
    xml = agendamento.xml_tarefa(PY, SCRIPT, CONFIG, "22:15", "semanal", date(2026, 10, 16))
    assert "<Monday />" in xml and "T22:15:00" in xml
    with pytest.raises(agendamento.ErroAgendamento):
        agendamento.xml_tarefa(PY, SCRIPT, CONFIG, "06:00", "manual", date(2026, 10, 16))


def test_linha_cron():
    linha = agendamento.linha_cron(PurePosixPath("/usr/bin/python3"), PurePosixPath("/srv/m/monitor.py"),
                                   PurePosixPath("/srv/m/alvos.yaml"), "06:05", "diaria")
    assert linha.startswith("5 6 * * * ")
    assert linha.endswith('"/srv/m/monitor.py" --config "/srv/m/alvos.yaml" run --origem agendamento')


def test_instalar_chama_schtasks_com_xml_utf16():
    chamadas = []

    def falso(comando, **kw):
        arquivo = Path(comando[comando.index("/XML") + 1])
        chamadas.append((comando, arquivo.read_bytes()[:2]))
        return subprocess.CompletedProcess(comando, 0, "", "")

    agendamento.instalar("<Task/>", executar=falso)
    [(comando, bom)] = chamadas
    assert comando[:4] == ["schtasks", "/Create", "/TN", agendamento.NOME_TAREFA] and comando[-1] == "/F"
    assert bom == b"\xff\xfe"  # UTF-16 LE com BOM, como o schtasks espera


def test_erros_do_schtasks_e_status():
    def falha(comando, **kw):
        return subprocess.CompletedProcess(comando, 1, "", "ERRO: acesso negado.")

    with pytest.raises(agendamento.ErroAgendamento, match="acesso negado"):
        agendamento.remover(executar=falha)

    def inexistente(comando, **kw):
        return subprocess.CompletedProcess(comando, 3, "", "")

    assert agendamento.status(executar=inexistente) is None

    def pronta(comando, **kw):
        return subprocess.CompletedProcess(comando, 0, "Ready||267011|2026-10-17T06:00:00\n", "")

    status = agendamento.status(executar=pronta)
    assert status.proxima_execucao == "2026-10-17T06:00:00" and status.ultima_execucao == ""
    assert agendamento.descrever_resultado(status.ultimo_resultado) == "ainda não executou"


# ---------------------------------------------------------------- trava

def test_trava_impede_execucao_simultanea(tmp_path):
    caminho = tmp_path / "dados" / "monitor.lock"
    with trava_exclusiva(caminho):
        with pytest.raises(ExecucaoEmAndamento):
            with trava_exclusiva(caminho):
                pass
    with trava_exclusiva(caminho):  # liberada ao sair
        pass


# ---------------------------------------------------------------- busca

def registro(norma, ementa, palavras, data, alvo="anac-resolucoes", tipo="NOVO"):
    return {"timestamp": "2026-10-15T06:00:00-03:00", "alvo": alvo, "tipo_mudanca": tipo, "norma": norma,
            "link": f"https://x/{norma}", "data_publicacao": data, "ementa": ementa, "palavras_chave": palavras}


@pytest.fixture
def ledger(tmp_path):
    ledger = Ledger(tmp_path / "dados" / "ledger.jsonl")
    ledger.anexar([
        registro("RESOLUÇÃO Nº 810", "Regras para aeronaves não tripuladas (drones)", ["drone", "RESOLUÇÃO", "810"],
                 "2026-03-01", tipo="LINHA_BASE"),
        registro("RESOLUÇÃO Nº 817", "Inspeção nos aeroportos", ["RESOLUÇÃO", "817"], "2026-10-14"),
        registro("RBAC 21 EMD 15", "Certificação de produto aeronáutico", ["certificação", "RBAC", "21"],
                 "", alvo="anac-rbac", tipo="ALTERADO"),
        registro("RESOLUÇÃO Nº 1817", "Outra", ["RESOLUÇÃO", "1817"], "2025-01-01"),
    ])
    return ledger


def normas(resultado):
    return [b["norma"] for b in resultado]


def test_busca_por_termo_sem_acento_e_plural(ledger):
    assert normas(buscar(ledger.blocos(), Filtros(termo="DRONE"))) == ["RESOLUÇÃO Nº 810"]
    assert normas(buscar(ledger.blocos(), Filtros(termo="certificacao rbac"))) == ["RBAC 21 EMD 15"]
    assert normas(buscar(ledger.blocos(), Filtros(termo="817"))) == ["RESOLUÇÃO Nº 817"]  # não acha 1817
    assert buscar(ledger.blocos(), Filtros(termo="drone tarifa")) == []  # todas as palavras precisam aparecer


def test_busca_por_filtros_e_ordem(ledger):
    todos = buscar(ledger.blocos(), Filtros())
    assert [b["indice"] for b in todos] == [3, 2, 1, 0]  # mais recente primeiro
    assert normas(buscar(ledger.blocos(), Filtros(alvo="anac-rbac"))) == ["RBAC 21 EMD 15"]
    assert normas(buscar(ledger.blocos(), Filtros(tipo="LINHA_BASE"))) == ["RESOLUÇÃO Nº 810"]
    # Sem data de publicação não entra quando há filtro de data.
    assert normas(buscar(ledger.blocos(), Filtros(de="2026-01-01"))) == ["RESOLUÇÃO Nº 817", "RESOLUÇÃO Nº 810"]
    assert normas(buscar(ledger.blocos(), Filtros(de="2026-01-01", ate="2026-06-30"))) == ["RESOLUÇÃO Nº 810"]


def test_cli_buscar(ledger, tmp_path, capsys):
    config = tmp_path / "alvos.yaml"
    config.write_text("alvos: []\n", encoding="utf-8")
    assert monitor.main(["--config", str(config), "buscar", "resolucao", "--limite", "1"]) == 0
    saida = capsys.readouterr().out
    assert "RESOLUÇÃO Nº 1817" in saida and "Mostrando 1 de 3 resultados" in saida

    assert monitor.main(["--config", str(config), "buscar", "drone", "--json"]) == 0
    [bloco] = json.loads(capsys.readouterr().out)
    assert bloco["link"] == "https://x/RESOLUÇÃO Nº 810" and bloco["hash"]

    with pytest.raises(SystemExit):
        monitor.main(["--config", str(config), "buscar", "--de", "15/10/2026"])


def test_cli_buscar_avisa_ledger_adulterado(ledger, tmp_path, capsys):
    config = tmp_path / "alvos.yaml"
    config.write_text("alvos: []\n", encoding="utf-8")
    linhas = ledger.caminho.read_text(encoding="utf-8").splitlines()
    bloco = json.loads(linhas[0])
    bloco["ementa"] = "adulterada"
    linhas[0] = json.dumps(bloco, ensure_ascii=False)
    ledger.caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    assert monitor.main(["--config", str(config), "buscar", "adulterada"]) == 0
    saida = capsys.readouterr()
    assert "integridade" in saida.err and "1 resultado(s)" in saida.out
