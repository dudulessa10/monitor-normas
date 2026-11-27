# Empacota os dados do Windows para levar à VM: dados/ (banco, ledger, âncoras), relatorios/ e a chave das âncoras.
# Esses arquivos NÃO vão pelo Git (são gerados pelo robô e mudam todo dia); por isso a VM começa "vazia"
# se este passo for pulado.
#
# Uso, na pasta do projeto, SEM nenhuma execução em andamento:
#   powershell -ExecutionPolicy Bypass -File deploy\exportar-dados.ps1
# Gera na Área de Trabalho (ou em -Destino): monitor-dados.tar.gz e monitor-chave.tar.gz
param([string]$Destino = [Environment]::GetFolderPath("Desktop"))
$ErrorActionPreference = "Stop"
$projeto = Split-Path -Parent $PSScriptRoot
Set-Location $projeto

$python = Join-Path $projeto ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

# Mesma trava do robô: se outra execução (agendada, web ou CLI) está rodando, não exporta pela metade.
& $python -c "import sys; from pathlib import Path; from monitor_normas.execucao import Trava, ExecucaoEmAndamento
try: Trava(Path('dados/monitor.lock')).adquirir().liberar()
except ExecucaoEmAndamento: sys.exit(3)"
if ($LASTEXITCODE -eq 3) { throw "Há uma execução em andamento. Espere terminar e rode de novo." }
if ($LASTEXITCODE -ne 0) { throw "Não foi possível conferir a trava de execução (veja a mensagem acima)." }

Write-Host "Conferindo o ledger antes de exportar..."
& $python monitor.py verificar-ledger
if ($LASTEXITCODE -ne 0) { throw "O ledger não passou na verificação; não exporte assim. Veja a mensagem acima." }

$destino = $Destino
$pastas = @("dados")
if (Test-Path "relatorios") { $pastas += "relatorios" }
tar --exclude=monitor.lock -czf "$destino\monitor-dados.tar.gz" @pastas
if ($LASTEXITCODE -ne 0) { throw "falha ao criar monitor-dados.tar.gz" }

$segura = if ($env:MONITOR_NORMAS_PASTA_SEGURA) { $env:MONITOR_NORMAS_PASTA_SEGURA } else { Join-Path $env:LOCALAPPDATA "MonitorNormas" }
if (Test-Path $segura) {
    tar -czf "$destino\monitor-chave.tar.gz" -C (Split-Path -Parent $segura) (Split-Path -Leaf $segura)
    if ($LASTEXITCODE -ne 0) { throw "falha ao criar monitor-chave.tar.gz" }
} else {
    Write-Warning "Pasta da chave não encontrada ($segura); só os dados serão exportados."
}

Write-Host ""
Write-Host "Pronto. Arquivos em ${destino}:"
Get-ChildItem "$destino\monitor-*.tar.gz" | ForEach-Object { Write-Host ("  {0}  ({1:N0} KB)" -f $_.Name, ($_.Length / 1KB)) }
Write-Host ""
Write-Host "Copie para a VM (exemplo):  scp `"$destino\monitor-dados.tar.gz`" `"$destino\monitor-chave.tar.gz`" usuario@vm:/tmp/"
Write-Host "Na VM:                       sudo ~/monitor-legislacao-anac/deploy/importar-dados.sh /tmp/monitor-dados.tar.gz /tmp/monitor-chave.tar.gz"
Write-Host "A chave (monitor-chave.tar.gz) é sigilosa: apague as cópias temporárias depois."
