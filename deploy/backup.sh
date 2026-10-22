#!/usr/bin/env bash
# Cópia de dados/ (banco, ledger e âncoras) em MONITOR_NORMAS_BACKUP, um .tar.gz por dia.
# O SQLite é copiado pela API de backup (cópia consistente com o servidor no ar), e tudo é feito
# com a trava de dados/monitor.lock, para não pegar uma execução no meio.
# A chave das âncoras NÃO entra: guarde-a uma vez, à parte (ver deploy/README.md).
# Estas cópias ficam na própria VM; mande-as também para fora dela (rclone, scp, snapshot do disco).
set -euo pipefail

BASE="${MONITOR_NORMAS_BASE:-/var/lib/monitor-normas}"
DESTINO="${MONITOR_NORMAS_BACKUP:-/var/lib/monitor-normas-backups}"
MANTER_DIAS="${MONITOR_NORMAS_BACKUP_DIAS:-30}"
PYTHON="${PYTHON:-/opt/monitor-normas/.venv/bin/python}"

umask 077
temporaria=$(mktemp -d)
trap 'rm -rf "$temporaria"' EXIT
mkdir -p "$temporaria/dados" "$DESTINO"

copiar() {
    "$PYTHON" -c '
import sqlite3, sys
origem, destino = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
origem.backup(destino)
destino.close(); origem.close()
' "$BASE/dados/estado.db" "$temporaria/dados/estado.db"
    for arquivo in ledger.jsonl ancoras.jsonl; do
        if [ -f "$BASE/dados/$arquivo" ]; then cp -p "$BASE/dados/$arquivo" "$temporaria/dados/"; fi
    done
}

# Espera até 1 hora por uma execução em andamento.
exec 9>>"$BASE/dados/monitor.lock"
flock -w 3600 9
copiar
flock -u 9

arquivo="$DESTINO/monitor-normas_$(date +%Y-%m-%d_%H%M).tar.gz"
tar -czf "$arquivo" -C "$temporaria" dados
find "$DESTINO" -name 'monitor-normas_*.tar.gz' -mtime +"$MANTER_DIAS" -delete
echo "backup: $arquivo"
