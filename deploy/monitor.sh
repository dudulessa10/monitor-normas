#!/usr/bin/env bash
# Roda o monitor.py no servidor como o usuário do serviço e com as variáveis dele.
# Uso: sudo /opt/monitor-normas/deploy/monitor.sh list   (ou run, verificar-ledger, buscar...)
set -euo pipefail
set -a
. /etc/monitor-normas/monitor-normas.env
set +a
cd /opt/monitor-normas
exec runuser -u monitor-normas -- .venv/bin/python monitor.py "$@"
