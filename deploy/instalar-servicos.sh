#!/usr/bin/env bash
# Instala (ou atualiza) os serviços systemd do Monitor de Normas apontando para ESTA pasta do projeto.
# Rode depois do ./setup.sh e de criar o .env:   sudo deploy/instalar-servicos.sh
#
# O que este script altera na máquina (e nada além disso):
#   - cria o usuário de sistema monitor-normas, se ainda não existir;
#   - dá ao monitor-normas permissão só de ATRAVESSAR (x, por ACL) as pastas acima do projeto
#     (ex.: /home/voce), para o serviço conseguir ler o código; ele não consegue listar nem ler
#     os outros arquivos do seu home;
#   - grava /etc/systemd/system/monitor-normas-*.service|timer e /etc/logrotate.d/monitor-normas;
#   - cria /var/lib/monitor-normas (dados) se não existir; dados já existentes são mantidos.
# Não altera variáveis de ambiente, ~/.bashrc, /etc/environment nem outras aplicações.
set -euo pipefail

PASTA="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USUARIO=monitor-normas
falha() { echo "erro: $*" >&2; exit 1; }
ok() { echo "ok  $*"; }

[ "$(id -u)" -eq 0 ] || falha "rode com sudo: sudo $0"
command -v systemctl >/dev/null || falha "systemd não encontrado"

# ---------------------------------------------------------------- pré-requisitos
[ -f "$PASTA/.env" ] || falha "$PASTA/.env não existe. Crie: cp .env.example .env && chmod 600 .env && nano .env"
[ -x "$PASTA/.venv/bin/uvicorn" ] || falha "Python não preparado. Rode antes (sem sudo): ./setup.sh"
[ -f "$PASTA/frontend/dist/index.html" ] || falha "frontend não compilado. Rode antes (sem sudo): ./setup.sh"
case "$PASTA" in *[[:space:]]*) falha "a pasta do projeto não pode ter espaços: $PASTA" ;; esac
if grep -qE '^MONITOR_NORMAS_SENHA=\s*$' "$PASTA/.env"; then
    echo "aviso: MONITOR_NORMAS_SENHA está vazia no .env; as telas e a API ficarão sem senha."
fi

# ---------------------------------------------------------------- usuário do serviço
if ! id "$USUARIO" >/dev/null 2>&1; then
    useradd --system --home /var/lib/monitor-normas --shell /usr/sbin/nologin "$USUARIO"
    ok "usuário $USUARIO criado"
else
    ok "usuário $USUARIO já existe"
fi

# ---------------------------------------------------------------- acesso de leitura ao código
dir="$PASTA"
while [ "$dir" != "/" ]; do
    if ! runuser -u "$USUARIO" -- test -x "$dir"; then
        command -v setfacl >/dev/null || falha "setfacl não encontrado. Instale: sudo apt install acl"
        setfacl -m "u:$USUARIO:x" "$dir"
        ok "permissão de atravessar (só x) para $USUARIO em $dir"
    fi
    dir="$(dirname "$dir")"
done
for arquivo in app.py alvos.yaml .venv/bin/python frontend/dist/index.html deploy/backup.sh; do
    runuser -u "$USUARIO" -- test -r "$PASTA/$arquivo" \
        || falha "$USUARIO não consegue ler $PASTA/$arquivo (confira as permissões: chmod -R o+rX $PASTA)"
done
ok "$USUARIO consegue ler o código"

# ---------------------------------------------------------------- serviços
install -d -o "$USUARIO" -g "$USUARIO" -m 750 /var/lib/monitor-normas
for modelo in "$PASTA"/deploy/monitor-normas-*.service "$PASTA"/deploy/monitor-normas-*.timer; do
    destino="/etc/systemd/system/$(basename "$modelo")"
    sed "s#@PASTA@#$PASTA#g" "$modelo" > "$destino"
    chmod 644 "$destino"
done
install -m 644 "$PASTA/deploy/logrotate" /etc/logrotate.d/monitor-normas
ok "unidades systemd gravadas em /etc/systemd/system (pasta: $PASTA)"

systemctl daemon-reload
systemctl enable --quiet monitor-normas-web.service monitor-normas-run.timer monitor-normas-backup.timer
systemctl restart monitor-normas-web.service
systemctl start monitor-normas-run.timer monitor-normas-backup.timer
ok "serviços ativos"

# ---------------------------------------------------------------- conferência
for _ in $(seq 1 20); do
    if resposta="$(curl -fsS http://127.0.0.1:8000/api/v1/saude 2>/dev/null)"; then
        ok "servidor respondendo: $resposta"
        break
    fi
    sleep 0.5
done
[ -n "${resposta:-}" ] || falha "o servidor não respondeu; veja: journalctl -u monitor-normas-web -n 50"
systemctl list-timers 'monitor-normas*' --no-pager
