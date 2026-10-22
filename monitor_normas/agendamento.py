"""Execução automática: tarefa no Agendador de Tarefas do Windows (ou linha de cron nos outros sistemas).

A tarefa é criada a partir de um XML porque o "schtasks /SC DAILY" não permite ligar
"executar assim que possível se um horário for perdido" (StartWhenAvailable), que cobre
os dias em que o computador estava desligado ou dormindo no horário marcado.
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

NOME_TAREFA = "MonitorNormas"
NUNCA_EXECUTADA = 0x41303  # LastTaskResult de uma tarefa que ainda não rodou


class ErroAgendamento(Exception):
    """Falha ao criar, remover ou consultar a tarefa agendada."""


@dataclass
class StatusTarefa:
    estado: str           # Ready, Running, Disabled...
    ultima_execucao: str  # ISO, ou "" se nunca rodou
    ultimo_resultado: int | None
    proxima_execucao: str


def interpretador() -> Path:
    """pythonw.exe (sem janela de console) ao lado do Python atual, se existir."""
    atual = Path(sys.executable)
    sem_janela = atual.with_name("pythonw.exe")
    return sem_janela if os.name == "nt" and sem_janela.exists() else atual


def argumentos_run(script: Path, config: Path) -> str:
    return f'"{script}" --config "{config}" run --origem agendamento'


def xml_tarefa(python: Path, script: Path, config: Path, horario: str, frequencia: str, hoje: date) -> str:
    if frequencia == "semanal":
        agenda = "<ScheduleByWeek><WeeksInterval>1</WeeksInterval><DaysOfWeek><Monday /></DaysOfWeek></ScheduleByWeek>"
    elif frequencia == "diaria":
        agenda = "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    else:
        raise ErroAgendamento(f"frequência '{frequencia}' não pode ser agendada")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Monitor de Normas: roda "monitor.py run" ({frequencia}, {horario}).</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{hoje.isoformat()}T{horario}:00</StartBoundary>
      <Enabled>true</Enabled>
      {agenda}
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(str(python))}</Command>
      <Arguments>{escape(argumentos_run(script, config))}</Arguments>
      <WorkingDirectory>{escape(str(script.parent))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def linha_cron(python: Path, script: Path, config: Path, horario: str, frequencia: str) -> str:
    hora, minuto = (int(p) for p in horario.split(":"))
    dia_semana = "1" if frequencia == "semanal" else "*"
    return f'{minuto} {hora} * * {dia_semana} cd "{script.parent}" && "{python}" {argumentos_run(script, config)}'


def _rodar(comando: list[str], executar) -> subprocess.CompletedProcess:
    try:
        resultado = executar(comando, capture_output=True, text=True, encoding="oem", errors="replace")
    except OSError as e:
        raise ErroAgendamento(f"não foi possível executar {comando[0]}: {e}")
    if resultado.returncode != 0:
        mensagem = (resultado.stderr or resultado.stdout or "").strip()
        raise ErroAgendamento(f"{comando[0]} falhou (código {resultado.returncode}): {mensagem}")
    return resultado


def instalar(xml: str, executar=subprocess.run) -> None:
    """Cria ou substitui a tarefa (não precisa de administrador)."""
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / "tarefa.xml"
        arquivo.write_text(xml, encoding="utf-16")
        _rodar(["schtasks", "/Create", "/TN", NOME_TAREFA, "/XML", str(arquivo), "/F"], executar)


def remover(executar=subprocess.run) -> None:
    _rodar(["schtasks", "/Delete", "/TN", NOME_TAREFA, "/F"], executar)


def status(executar=subprocess.run) -> StatusTarefa | None:
    """Estado da tarefa pelo PowerShell (saída independente do idioma do Windows). None se não existe."""
    script = (
        f"$t = Get-ScheduledTask -TaskName '{NOME_TAREFA}' -ErrorAction SilentlyContinue; "
        "if (-not $t) { exit 3 }; "
        f"$i = Get-ScheduledTaskInfo -TaskName '{NOME_TAREFA}'; "
        "$u = if ($i.LastRunTime -and $i.LastRunTime.Year -gt 2000) { $i.LastRunTime.ToString('s') } else { '' }; "
        "$p = if ($i.NextRunTime) { $i.NextRunTime.ToString('s') } else { '' }; "
        "'{0}|{1}|{2}|{3}' -f $t.State, $u, $i.LastTaskResult, $p"
    )
    try:
        resultado = executar(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                             capture_output=True, text=True, encoding="oem", errors="replace")
    except OSError as e:
        raise ErroAgendamento(f"não foi possível executar o PowerShell: {e}")
    if resultado.returncode == 3:
        return None
    if resultado.returncode != 0:
        raise ErroAgendamento(f"consulta da tarefa falhou: {(resultado.stderr or '').strip()}")
    estado, ultima, codigo, proxima = resultado.stdout.strip().split("|")
    return StatusTarefa(estado, ultima, int(codigo) if codigo.lstrip("-").isdigit() else None, proxima)


def descrever_resultado(codigo: int | None) -> str:
    if codigo is None or codigo == NUNCA_EXECUTADA:
        return "ainda não executou"
    if codigo == 0:
        return "ok (código 0)"
    if codigo == 1:
        return "algum alvo falhou (código 1; veja logs/monitor.log)"
    return f"falhou (código {codigo}; veja logs/monitor.log)"
