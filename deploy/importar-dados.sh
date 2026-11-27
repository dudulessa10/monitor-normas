#!/usr/bin/env bash
# Coloca na VM os dados trazidos do Windows (gerados por deploy/exportar-dados.ps1).
# Uso: sudo deploy/importar-dados.sh /tmp/monitor-dados.tar.gz [/tmp/monitor-chave.tar.gz]
#
# Antes de substituir, guarda uma cópia do que já existe na VM em
# /var/lib/monitor-normas-backups/antes-da-importacao_DATA.tar.gz (nada é perdido).
# Usa as pastas do .env do projeto (MONITOR_NORMAS_BASE e MONITOR_NORMAS_PASTA_SEGURA).
set -euo pipefail

PASTA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USUARIO=monitor-normas
falha() { echo "erro: $*" >&2; exit 1; }
ok() { echo "ok  $*"; }

[ "$(id -u)" -eq 0 ] || falha "rode com sudo"
DADOS_TGZ="${1:-}"; CHAVE_TGZ="${2:-}"
[ -f "$DADOS_TGZ" ] || falha "uso: sudo $0 monitor-dados.tar.gz [monitor-chave.tar.gz]"
[ -z "$CHAVE_TGZ" ] || [ -f "$CHAVE_TGZ" ] || falha "arquivo não encontrado: $CHAVE_TGZ"
[ -f "$PASTA/.env" ] || falha "$PASTA/.env não existe"
id "$USUARIO" >/dev/null 2>&1 || falha "usuário $USUARIO não existe; rode antes: sudo deploy/instalar-servicos.sh"

# Lê só as duas variáveis necessárias, sem carregar o .env no ambiente deste shell.
valor() { grep -E "^$1=" "$PASTA/.env" | tail -1 | cut -d= -f2-; }
BASE="$(valor MONITOR_NORMAS_BASE)"; BASE="${BASE:-/var/lib/monitor-normas}"
SEGURA="$(valor MONITOR_NORMAS_PASTA_SEGURA)"; SEGURA="${SEGURA:-$BASE/chave}"
BACKUPS="$(valor MONITOR_NORMAS_BACKUP)"; BACKUPS="${BACKUPS:-/var/lib/monitor-normas-backups}"

tar -tzf "$DADOS_TGZ" | grep -q '^dados/ledger.jsonl$' || falha "$DADOS_TGZ não contém dados/ledger.jsonl"

echo "Parando os serviços durante a importação..."
systemctl stop monitor-normas-run.timer monitor-normas-backup.timer monitor-normas-web.service 2>/dev/null || true

install -d -m 700 "$BACKUPS"
if [ -d "$BASE/dados" ] || [ -d "$BASE/relatorios" ]; then
    copia="$BACKUPS/antes-da-importacao_$(date +%Y-%m-%d_%H%M%S).tar.gz"
    tar -czf "$copia" -C "$BASE" $(cd "$BASE" && ls -d dados relatorios 2>/dev/null)
    ok "dados que já estavam na VM guardados em $copia"
fi

install -d -o "$USUARIO" -g "$USUARIO" -m 750 "$BASE"
rm -rf "$BASE/dados" "$BASE/relatorios"
tar -xzf "$DADOS_TGZ" -C "$BASE"
rm -f "$BASE/dados/monitor.lock"
install -d -o "$USUARIO" -g "$USUARIO" -m 750 "$BASE/logs"
ok "dados/ e relatorios/ copiados para $BASE"

if [ -n "$CHAVE_TGZ" ]; then
    install -d -o "$USUARIO" -g "$USUARIO" -m 700 "$SEGURA"
    tar -xzf "$CHAVE_TGZ" -C "$SEGURA" --strip-components=1
    # A cópia da última âncora tem no nome um código do caminho do ledger, que mudou do Windows para cá.
    novo="$(cd "$PASTA" && PYTHONDONTWRITEBYTECODE=1 MONITOR_NORMAS_PASTA_SEGURA="$SEGURA" .venv/bin/python -c "
from monitor_normas.ancora import Ancoras; from monitor_normas.ledger import Ledger
print(Ancoras(Ledger('$BASE/dados/ledger.jsonl')).copia_local)")"
    antigas=("$SEGURA"/ultima_ancora_*.json)
    if [ -e "${antigas[0]}" ] && [ ! -e "$novo" ]; then
        mv "$(ls -t "$SEGURA"/ultima_ancora_*.json | head -1)" "$novo"
    fi
    chmod 600 "$SEGURA"/*
    ok "chave das âncoras copiada para $SEGURA"
fi

chown -R "$USUARIO:$USUARIO" "$BASE" "$SEGURA" 2>/dev/null || chown -R "$USUARIO:$USUARIO" "$BASE"

echo "Conferindo o ledger importado..."
if "$PASTA/deploy/monitor.sh" verificar-ledger; then
    ok "ledger íntegro"
else
    echo "aviso: a verificação acusou problema (veja acima). Os dados anteriores estão em $BACKUPS."
fi

systemctl start monitor-normas-web.service monitor-normas-run.timer monitor-normas-backup.timer
for _ in $(seq 1 30); do
    curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/saude 2>/dev/null && break
    sleep 0.5
done
curl -fsS -o /dev/null http://127.0.0.1:8000/api/v1/saude \
    || falha "o servidor não voltou a responder; veja: journalctl -u monitor-normas-web -n 50"
ok "serviços religados e servidor respondendo"
echo
echo "Agora desative a execução automática no Windows (senão os dois ledgers divergem):"
echo "    python monitor.py agendar --remover"
echo "E apague as cópias temporárias: rm $DADOS_TGZ ${CHAVE_TGZ}"
