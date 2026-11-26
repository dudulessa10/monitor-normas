#!/usr/bin/env bash
# Roda o monitor.py no servidor como o usuário do serviço e com as variáveis do .env do projeto
# (só para este comando: nada fica no seu terminal).
# Uso: sudo ~/monitor-legislacao-anac/deploy/monitor.sh list   (ou run, verificar-ledger, buscar...)
set -euo pipefail
PASTA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$PASTA/.env" ] || { echo "erro: $PASTA/.env não existe (veja .env.example)" >&2; exit 1; }
set -a
. "$PASTA/.env"
set +a
cd "$PASTA"
exec runuser -u monitor-normas -- .venv/bin/python monitor.py "$@"
