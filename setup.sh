#!/usr/bin/env bash
# Prepara o Monitor de Normas para rodar nesta máquina (Linux ou macOS):
#   1. confere o Python (3.11+) e instala as dependências num .venv dentro do projeto;
#   2. confere o Node (versão do .nvmrc) e, se não houver, baixa o Node oficial para
#      .ferramentas/node, dentro do projeto;
#   3. roda npm ci e npm run build no frontend (gera frontend/dist, servido pelo Python).
#
# Tudo fica dentro desta pasta: o script não usa sudo e não altera ~/.bashrc, ~/.profile,
# variáveis de ambiente, nem o Python/Node do sistema ou de outras aplicações.
# Pode rodar quantas vezes quiser (por exemplo, depois de cada git pull).
#
# Uso:  ./setup.sh
set -euo pipefail

PROJETO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJETO"

verde=$'\033[32m'; amarelo=$'\033[33m'; vermelho=$'\033[31m'; negrito=$'\033[1m'; normal=$'\033[0m'
etapa() { echo; echo "${negrito}==> $*${normal}"; }
ok()    { echo "${verde}ok${normal}  $*"; }
aviso() { echo "${amarelo}aviso${normal}  $*"; }
falha() { echo "${vermelho}erro${normal}  $*" >&2; exit 1; }

NODE_MAJOR="$(tr -d '[:space:]v' < .nvmrc)"
[[ "$NODE_MAJOR" =~ ^[0-9]+$ ]] || falha ".nvmrc deve conter só o número da versão principal do Node (ex.: 26)"

# ---------------------------------------------------------------- 1. arquivos do projeto
etapa "Conferindo os arquivos do projeto"
faltando=()
for arquivo in requirements-lock.txt app.py monitor.py alvos.yaml frontend/package.json frontend/package-lock.json; do
    [ -f "$arquivo" ] || faltando+=("$arquivo")
done
[ ${#faltando[@]} -eq 0 ] || falha "arquivos ausentes (o clone está incompleto?): ${faltando[*]}"
ok "arquivos principais presentes"

if [ -f .env ]; then
    ok ".env encontrado"
    if [ "$(stat -c %a .env 2>/dev/null || stat -f %Lp .env)" != "600" ]; then
        aviso ".env pode ser lido por outros usuários; recomendado: chmod 600 .env"
    fi
else
    aviso ".env não encontrado. Crie a partir do modelo antes de ligar os serviços:"
    echo "       cp .env.example .env && chmod 600 .env && nano .env"
fi

# ---------------------------------------------------------------- 2. Python
etapa "Python"
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || falha "python3 não encontrado. Instale: sudo apt install python3 python3-venv"
"$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))' \
    || falha "é preciso Python 3.11 ou mais novo (encontrado: $("$PYTHON" --version 2>&1))"
ok "$("$PYTHON" --version)"

if [ ! -x .venv/bin/python ]; then
    "$PYTHON" -m venv .venv 2>/dev/null \
        || falha "não foi possível criar o .venv. No Ubuntu/Debian: sudo apt install python3-venv"
    ok ".venv criado"
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements-lock.txt
ok "dependências Python instaladas em .venv"

# ---------------------------------------------------------------- 3. Node
etapa "Node.js $NODE_MAJOR"
NODE_LOCAL="$PROJETO/.ferramentas/node"
versao_major() { "$1" -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0; }

if [ -x "$NODE_LOCAL/bin/node" ] && [ "$(versao_major "$NODE_LOCAL/bin/node")" = "$NODE_MAJOR" ]; then
    NODE_BIN="$NODE_LOCAL/bin"
    ok "usando o Node do projeto ($("$NODE_BIN/node" -v), em .ferramentas/node)"
elif command -v node >/dev/null && [ "$(versao_major node)" = "$NODE_MAJOR" ]; then
    NODE_BIN="$(dirname "$(command -v node)")"
    ok "usando o Node já instalado na máquina ($(node -v))"
else
    command -v node >/dev/null && aviso "o Node da máquina é $(node -v); o projeto usa a versão $NODE_MAJOR. O Node da máquina não será alterado."
    case "$(uname -s)-$(uname -m)" in
        Linux-x86_64)  plataforma=linux-x64 ;;
        Linux-aarch64) plataforma=linux-arm64 ;;
        Darwin-arm64)  plataforma=darwin-arm64 ;;
        Darwin-x86_64) plataforma=darwin-x64 ;;
        *) falha "plataforma $(uname -s)-$(uname -m) sem Node pronto; instale o Node $NODE_MAJOR manualmente" ;;
    esac
    command -v curl >/dev/null || falha "curl não encontrado. Instale: sudo apt install curl"
    base="https://nodejs.org/dist/latest-v${NODE_MAJOR}.x"
    temporaria="$(mktemp -d)"
    trap 'rm -rf "$temporaria"' EXIT
    echo "baixando o Node $NODE_MAJOR ($plataforma) de nodejs.org para .ferramentas/node ..."
    curl -fsSL "$base/SHASUMS256.txt" -o "$temporaria/SHASUMS256.txt" || falha "não foi possível acessar $base"
    pacote="$(grep -oE "node-v[0-9.]+-${plataforma}\.tar\.gz" "$temporaria/SHASUMS256.txt" | head -1)"
    [ -n "$pacote" ] || falha "pacote do Node para $plataforma não encontrado em $base"
    curl -fsSL "$base/$pacote" -o "$temporaria/$pacote"
    (cd "$temporaria" && grep " $pacote\$" SHASUMS256.txt | sha256sum -c --status) \
        || falha "o arquivo baixado não confere com o SHA-256 oficial; tente de novo"
    rm -rf "$NODE_LOCAL"
    mkdir -p "$NODE_LOCAL"
    tar -xzf "$temporaria/$pacote" -C "$NODE_LOCAL" --strip-components=1
    NODE_BIN="$NODE_LOCAL/bin"
    ok "Node $("$NODE_BIN/node" -v) instalado em .ferramentas/node (só para este projeto)"
fi
# Só para os comandos abaixo, dentro deste script; o PATH do seu terminal não muda.
export PATH="$NODE_BIN:$PATH"

# ---------------------------------------------------------------- 4. frontend
etapa "Frontend (npm ci + build)"
(
    cd frontend
    npm ci --no-audit --no-fund --loglevel=error
    npm run build --silent
)
[ -f frontend/dist/index.html ] || falha "o build não gerou frontend/dist/index.html"
ok "frontend compilado em frontend/dist"

# ---------------------------------------------------------------- fim
etapa "Pronto"
cat <<EOF
Para testar agora (Ctrl+C para parar):
    .venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000
e abra http://127.0.0.1:8000

Para os serviços (systemd, HTTPS, execução diária), veja docs/PROJETO.md.
Se os serviços já estão instalados, reinicie o servidor web para usar o build novo:
    sudo systemctl restart monitor-normas-web
EOF
