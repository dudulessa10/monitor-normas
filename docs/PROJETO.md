# Monitor de Normas: documentação do projeto (versão React)

## 1. Visão geral e objetivo

O **Monitor de Normas** é um robô que vigia as páginas de legislação da ANAC, que não oferece API
própria. A cada rodada ele detecta normas **novas**, **alteradas** ou **removidas** (RBAC, IS,
resoluções, portarias, decisões etc.) e registra cada mudança num **ledger** encadeado por SHA-256,
protegido por âncoras assinadas.

O projeto tem três formas de uso, todas sobre os mesmos dados:

- **Aplicativo web**: telas em React para acompanhar e gerenciar o robô, e a API REST em `/api/v1`.
- **Linha de comando**: `python monitor.py run`, `buscar`, `verificar-ledger` etc.
- **Execução diária automática**: systemd na VM Linux ou Agendador de Tarefas no Windows.

Esta versão trocou o frontend antigo (HTML + JavaScript puro, pasta `web/`) por uma aplicação
**React** (pasta `frontend/`), sem mudar o robô nem a API. O projeto foi preparado para ser
**totalmente importável**: quem clona o repositório numa VM Linux instala, compila e roda usando só
o que está no Git.

## 2. Stack e o papel de cada biblioteca

| Camada | Tecnologia | Para que serve |
|---|---|---|
| Robô | Python 3.11+, requests, BeautifulSoup + lxml, PyYAML, openpyxl, SQLite | baixar as páginas, extrair as tabelas, detectar mudanças, gerar relatórios e planilhas |
| API | FastAPI + uvicorn | expor `/api/v1` e entregar as telas compiladas (`frontend/dist`) |
| Telas | **React 19** | biblioteca de interface: cada parte da tela é um componente |
| | **Vite 8** | servidor de desenvolvimento (atualiza a tela ao salvar) e empacotador do build de produção |
| | **TypeScript 7** | "corretor" do código: aponta erros de nome e de tipo antes de rodar |
| | **MUI 9** (Material UI) | componentes prontos: tabelas, botões, diálogos, campos, selos, avisos e tema claro/escuro |
| | **React Router 8** | rotas da aplicação (`/`, `/alvos`, `/mudancas`, `/execucoes`) |
| | **TanStack React Query 5** | busca os dados da API com cache, estados de carregamento e erro, recarga após ações e atualização automática a cada 3 s quando há rodada em andamento |
| | Vitest + Testing Library | testes do frontend (funções e telas com a API simulada) |
| | oxlint | verificação de qualidade do código |
| Servidor | systemd, Caddy, logrotate | serviços, HTTPS e rotação de logs na VM |
| Qualidade | pytest, GitHub Actions | testes do backend e CI num Ubuntu limpo |

Versão do Node: **26** (arquivo `.nvmrc`). Versão do Python: 3.11 ou mais nova.

## 3. Estrutura de pastas

```
.
├── setup.sh                 prepara tudo na VM: .venv, Node do projeto, npm ci e build
├── .env.example             modelo das variáveis (sem valores reais)
├── .nvmrc                   versão do Node (26)
├── .gitignore, .gitattributes
├── app.py                   entrada do servidor web (uvicorn app:app)
├── monitor.py               linha de comando
├── alvos.yaml               configurações globais (regex, palavras-chave, horário)
├── alvos_iniciais.yaml      carga inicial dos alvos (importar-yaml)
├── requirements.txt         dependências Python (desenvolvimento e testes)
├── requirements-lock.txt    versões exatas para o servidor
├── monitor_normas/          ROBÔ (coleta, extração, detecção, ledger, âncoras, relatórios...)
├── api/                     API FastAPI
│   ├── main.py              criar_app(): rotas /api/v1 e telas em /
│   ├── frontend.py          entrega o frontend/dist e devolve o index.html nas rotas do React
│   ├── autenticacao.py      senha opcional (HTTP Basic)
│   ├── esquemas.py          contrato de entrada e saída
│   └── rotas/               alvos, execuções, consultas e saúde
├── frontend/                TELAS (React)
│   ├── package.json, package-lock.json
│   ├── vite.config.ts       proxy de desenvolvimento e configuração dos testes
│   ├── index.html
│   ├── scripts/verificar-imports.mjs   confere maiúsculas/minúsculas dos imports (Linux)
│   └── src/
│       ├── main.tsx         monta tema, React Query, avisos e rotas
│       ├── App.tsx          tabela de rotas
│       ├── tema.ts          cores (claro e escuro) e ajustes do MUI
│       ├── api/             cliente.ts (fetch), tipos.ts (formatos da API), consultas.ts (hooks)
│       ├── componentes/     Layout, CabecalhoTela, Cartao, Selos, Paginacao, LinkExterno, Estados, Confirmar, Avisos
│       ├── util/            formatacao.ts (datas), url.ts (links seguros), rotulos.ts (selos)
│       ├── paginas/         painel/, alvos/, mudancas/, execucoes/ (uma pasta por tela)
│       └── testes/          preparação e ajudantes dos testes de tela
├── deploy/                  VM: modelos systemd, Caddyfile, scripts de instalação, dados e backup
├── docs/PROJETO.md          este documento
├── tests/                   pytest (offline)
└── .github/workflows/ci.yml CI no Ubuntu
```

Pastas geradas, que **não vão para o Git**: `.venv/`, `frontend/node_modules/`, `frontend/dist/`,
`.ferramentas/` (Node baixado pelo `setup.sh`), `dados/`, `relatorios/`, `logs/` e `.env`.

## 4. Arquitetura

### Camadas

```
navegador ──HTTP──▶ FastAPI (api/) ──chama──▶ robô (monitor_normas/) ──▶ SQLite + ledger
   ▲                    │
   └── telas React ◀────┘ (frontend/dist, servido em /)
```

A dependência tem um só sentido: `frontend → api → monitor_normas`. O robô não sabe que a web
existe; a API valida a entrada, chama o robô e devolve JSON; o React usa **só** a API JSON, a mesma
que outra aplicação usaria.

### Fluxo de dados no frontend

1. Uma tela chama um hook de `src/api/consultas.ts` (ex.: `useAlvos()`).
2. O hook usa `src/api/cliente.ts`, que faz o `fetch` em `/api/v1/...` e transforma erros do
   FastAPI (`{"detail": ...}`) em mensagens legíveis.
3. O React Query guarda a resposta em cache e devolve `data`, `isPending` e `error` para a tela.
4. Ações (rodar, salvar, excluir, ativar) usam mutações; ao terminar, o React Query recarrega o que
   pode ter mudado e a tela é atualizada sozinha.
5. Avisos rápidos ("Execução #44 iniciada.") são mostrados pelo componente `Avisos` (Snackbar).

### Estado

- **Dados do servidor:** React Query (não há Redux nem estado global manual).
- **Estado da tela:** `useState` (página atual, linhas expandidas, formulário aberto).
- **Filtros de Mudanças:** no endereço (`/mudancas?alvo=x&tipo=NOVO`), via `useSearchParams`.
  Recarregar a página ou compartilhar o link mantém os filtros.
- **Navegador:** nada é guardado (sem localStorage nem cookies); a senha HTTP Basic fica com o próprio navegador.

### Rotas

| Rota | Tela |
|---|---|
| `/` | Painel |
| `/alvos` | Alvos |
| `/mudancas` | Mudanças (com filtros na query string) |
| `/execucoes` | Execuções |
| qualquer outra | volta para o Painel |

O FastAPI (`api/frontend.py`) devolve o `index.html` para essas rotas, então recarregar ou abrir um
link direto funciona. Endereços de arquivo inexistentes (`/assets/x.js`) e de API inexistentes
(`/api/v1/x`) continuam dando 404. Sem o build, `/` mostra uma página explicando como gerá-lo.

### API usada pelas telas

| Tela | Endpoints |
|---|---|
| Painel | `GET /execucoes?limite=1`, `POST /execucoes`, `GET /ledger/verificar`, `GET /alvos`, `GET /mudancas` |
| Alvos | `GET /alvos`, `GET /configuracao`, `POST /alvos`, `PUT/DELETE /alvos/{id}`, `POST /alvos/{id}/ativar` e `/desativar`, `POST /execucoes` |
| Mudanças | `GET /alvos`, `GET /mudancas`, `GET /exportar/excel` |
| Execuções | `GET /execucoes` |

A documentação interativa completa da API fica em `/docs`.

## 5. Componentes principais

| Componente | Onde | O que faz |
|---|---|---|
| `Layout` | `componentes/` | barra superior com marca, abas das 4 telas e link para a API; título da aba do navegador |
| `PainelPage` | `paginas/painel/` | grade com `CartaoUltimaExecucao`, `CartaoRodarAgora`, `CartaoLedger`, `CartaoAlvos` e `MudancasRecentes`; avisa quando uma execução termina e recarrega os cartões |
| `AlvosPage` | `paginas/alvos/` | `TabelaAlvos` (interruptor, editar, rodar, excluir), `FormularioAlvo` (diálogo de cadastro/edição) e `Confirmar` (exclusão) |
| `formularioAlvo.ts` | `paginas/alvos/` | converte o formulário em texto para o formato da API e vice-versa (mesmas regras da versão original; testado à parte) |
| `MudancasPage` | `paginas/mudancas/` | `FiltrosMudancas` (8 filtros), `TabelaMudancas`, paginação de 50 e "Baixar Excel" com os mesmos filtros |
| `ExecucoesPage` | `paginas/execucoes/` | histórico paginado (25), `LinhaRodada` com erros à vista e detalhe por alvo |
| `SeloStatus`, `SeloTipo` | `componentes/Selos.tsx` | selos coloridos de status e de tipo de mudança |
| `LinkExterno` | `componentes/` | link para a norma; só aceita `http(s)://` (bloqueia `javascript:` vindo dos sites) |
| `Paginacao`, `Estados`, `Cartao`, `CabecalhoTela` | `componentes/` | peças de layout reutilizadas pelas telas |

## 6. Variáveis de ambiente

Todas ficam no arquivo `.env` na raiz do projeto (modelo: `.env.example`). No Windows, em
desenvolvimento, o `.env` é opcional: sem ele tudo fica na pasta do projeto.

| Variável | Para quê | Padrão |
|---|---|---|
| `MONITOR_NORMAS_BASE` | pasta de `dados/`, `relatorios/` e `logs/` | a pasta do projeto |
| `MONITOR_NORMAS_PASTA_SEGURA` | chave e cópia da última âncora do ledger | `%LOCALAPPDATA%\MonitorNormas` ou `~/.config/monitor_normas` |
| `MONITOR_NORMAS_USUARIO` | usuário das telas e da API | `admin` |
| `MONITOR_NORMAS_SENHA` | liga a senha (HTTP Basic); sem ela o servidor fica aberto | vazio |
| `MONITOR_NORMAS_BACKUP` | pasta das cópias diárias (VM) | `/var/lib/monitor-normas-backups` |
| `MONITOR_NORMAS_BACKUP_DIAS` | por quantos dias manter as cópias | `30` |
| `TZ` | fuso horário | `America/Sao_Paulo` |
| `FRONTEND_PROXY_API` | só no `npm run dev`: para onde repassar `/api` | `http://127.0.0.1:8000` |

- O `.env` é lido **apenas** pelos serviços systemd deste projeto e pelo `deploy/monitor.sh`. Ele não
  é carregado no terminal nem afeta outras aplicações da máquina.
- O frontend não usa variáveis no navegador (o Vite só exporia as que começam com `VITE_`, e o
  projeto não tem nenhuma). Nunca coloque segredos em variáveis `VITE_`.
- Valores sem aspas, sem espaços em volta do `=` e sem `$` ou `` ` `` (o arquivo também é lido pelo bash).

## 7. Como rodar localmente (Windows)

Pré-requisitos: Python 3.11+, Node 26 e Git.

```powershell
git clone https://github.com/dudulessa10/monitor-normas.git
cd monitor-normas
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python monitor.py importar-yaml            # só na primeira vez
cd frontend; npm ci; npm run build; cd ..
uvicorn app:app --reload                   # http://localhost:8000
```

Para **desenvolver as telas** com atualização instantânea, use dois terminais:

```powershell
# terminal 1 (pasta do projeto): API
uvicorn app:app --reload
# terminal 2 (pasta frontend): telas em http://localhost:5173, repassando /api para :8000
npm run dev
```

## 8. Instalação na VM Linux (passo a passo)

Testado em Ubuntu 24.04. Tudo fica em `~/monitor-legislacao-anac`. O projeto **não altera** variáveis
de ambiente, `~/.bashrc`, o Python ou o Node do sistema, nem outras aplicações do home.

**1. Pacotes do sistema** (uma vez):

```bash
sudo timedatectl set-timezone America/Sao_Paulo
sudo apt update && sudo apt install -y git python3 python3-venv curl acl
```

O Node **não** precisa ser instalado: o `setup.sh` baixa o Node 26 oficial para dentro do projeto
(`.ferramentas/node`) se a máquina não tiver essa versão.

**2. Clonar no home:**

```bash
cd ~
git clone https://github.com/dudulessa10/monitor-normas.git monitor-legislacao-anac
cd ~/monitor-legislacao-anac
```

(Enquanto a migração não estiver no `master`, acrescente `-b migracao-react` ao `git clone`. Se o
repositório for privado, o Git pede seu usuário e um token do GitHub como senha.)

**3. Criar o `.env`:**

```bash
cp .env.example .env
chmod 600 .env
nano .env          # defina MONITOR_NORMAS_SENHA (ex.: gere com: openssl rand -hex 16)
```

Já havia uma instalação antiga com `/etc/monitor-normas/monitor-normas.env`? Copie esse arquivo em vez
do modelo, para manter exatamente as mesmas variáveis e valores:
`sudo cp /etc/monitor-normas/monitor-normas.env .env && sudo chown "$USER": .env && chmod 600 .env`.

**4. Rodar o `setup.sh`** (sem sudo):

```bash
./setup.sh
```

Ele confere os arquivos, avisa se faltar o `.env`, cria o `.venv` com as dependências Python, prepara
o Node, roda `npm ci` e `npm run build`. Pode ser repetido quantas vezes quiser.

**5. Instalar os serviços** (com sudo, uma vez, e de novo se os modelos em `deploy/` mudarem):

```bash
sudo deploy/instalar-servicos.sh
```

Liga o aplicativo web (`127.0.0.1:8000`), a execução diária às 06:00 e o backup às 07:00, e confere
se o servidor responde.

**6. Dados:**

- **Vindos do Windows** (para a VM ficar igual ao PC): no Windows, rode
  `powershell -ExecutionPolicy Bypass -File deploy\exportar-dados.ps1`, copie os dois `.tar.gz`
  para a VM e rode `sudo deploy/importar-dados.sh /tmp/monitor-dados.tar.gz /tmp/monitor-chave.tar.gz`.
  Depois desative o agendamento no Windows (`python monitor.py agendar --remover`).
- **Instalação nova:** `sudo deploy/monitor.sh importar-yaml`.

**7. HTTPS:** configure o Caddy com `deploy/Caddyfile` (ver [deploy/README.md](../deploy/README.md#https-caddy)).

**8. Atualizar com `git pull`:**

```bash
cd ~/monitor-legislacao-anac
git pull
./setup.sh
sudo systemctl restart monitor-normas-web
```

Os detalhes de operação (logs, horários, backups, âncora externa) estão em
[deploy/README.md](../deploy/README.md).

## 9. Scripts do `package.json` (pasta `frontend/`)

| Script | O que faz |
|---|---|
| `npm run dev` | servidor de desenvolvimento em `http://localhost:5173`, com proxy de `/api` para o Python |
| `npm run build` | confere os tipos (TypeScript) e gera `frontend/dist`, servido pelo FastAPI |
| `npm run preview` | serve o `dist` localmente para conferir o build |
| `npm run lint` | oxlint e conferência de maiúsculas/minúsculas dos imports |
| `npm test` | roda os testes uma vez (Vitest) |
| `npm run test:watch` | testes em modo contínuo, enquanto você edita |

Use sempre `npm ci` (e não `npm install`) para instalar: ele usa exatamente as versões do
`package-lock.json`, igual em todas as máquinas.

## 10. Problemas comuns e soluções

| Sintoma | Causa provável | Solução |
|---|---|---|
| `/` mostra "as telas ainda não foram compiladas" | falta o `frontend/dist` | `./setup.sh` (ou `cd frontend && npm ci && npm run build`) e reinicie o servidor |
| A VM não mostra o mesmo histórico do PC | `dados/` e `relatorios/` não vão pelo Git | exporte no Windows e importe na VM (passo 6) |
| `setup.sh`: "não foi possível criar o .venv" | falta o pacote do venv | `sudo apt install python3-venv` |
| `setup.sh`: erro ao baixar o Node | VM sem acesso a nodejs.org | libere o acesso ou instale o Node 26 manualmente; o script usa o da máquina se for a versão 26 |
| `instalar-servicos.sh`: "setfacl não encontrado" | falta o pacote `acl` | `sudo apt install acl` |
| `instalar-servicos.sh`: "não consegue importar/ler ..." | permissões alteradas na pasta do projeto | rode de novo `sudo deploy/instalar-servicos.sh` (ele refaz as permissões de leitura por ACL) |
| Serviço web não sobe | ver o log | `journalctl -u monitor-normas-web -n 50` |
| `Permission denied` ao rodar `deploy/*.sh` | arquivo copiado sem permissão de execução | use o `git clone` (o Git guarda a permissão) ou `chmod +x setup.sh deploy/*.sh` |
| Build quebra só no Linux com "não encontrado" | import com maiúscula/minúscula diferente do arquivo | `npm run lint` aponta o import exato |
| Navegador pede senha e não aceita | usuário/senha diferentes do `.env` | confira `MONITOR_NORMAS_USUARIO` e `MONITOR_NORMAS_SENHA` e reinicie o serviço |
| "outra execução está em andamento" (409) | já há uma rodada (web, CLI ou agendada) | aguarde; o Painel atualiza sozinho |
| Scripts com `\r` ("bad interpreter") | arquivo editado no Windows com CRLF | o `.gitattributes` força LF; rode `git checkout -- setup.sh deploy/` para restaurar |

## 11. O que mudou em relação à versão original

| Item | Antes | Agora |
|---|---|---|
| Telas | HTML + JS puro em `web/`, sem build | React + TypeScript + MUI em `frontend/`, com build (`frontend/dist`) |
| Rotas | `#painel`, `#mudancas?...` | `/`, `/mudancas?...` (links antigos com `#` caem no Painel) |
| Dados na tela | `fetch` manual e `setTimeout` | React Query (cache, recarga automática, atualização a cada 3 s em execução) |
| Estilos | `estilo.css` | tema do MUI com as mesmas cores, claro e escuro automáticos |
| Confirmação de exclusão | `confirm()` do navegador | diálogo próprio |
| Servidor | servia `web/` | serve `frontend/dist` e devolve o `index.html` nas rotas do React |
| Instalação na VM | código em `/opt`, variáveis em `/etc/monitor-normas` | código e `.env` em `~/monitor-legislacao-anac`, `setup.sh` e `deploy/instalar-servicos.sh` |
| Dados do Windows para a VM | comandos manuais | `deploy/exportar-dados.ps1` e `deploy/importar-dados.sh` |
| Permissão de execução | `backup.sh` e `monitor.sh` sem `+x` no Git (o backup falhava na VM) | corrigida |
| Testes | pytest | pytest + 44 testes do frontend + CI no Ubuntu (incluindo a instalação completa) |

O robô, a API (endpoints e formatos), a CLI, o ledger e as âncoras **não mudaram**. A versão
original continua disponível na tag `v1-js-puro`.

## 12. Melhorias futuras

- Tela de **normas vigentes** (`GET /normas`), que a API já oferece e as telas ainda não usam.
- Tela do **ledger** com busca e verificação de âncora externa (`GET /ledger/verificar?ancora=`).
- Login por formulário (sessão) em vez da janela HTTP Basic do navegador.
- Divisão do JavaScript em partes menores (carregamento por tela) para abrir mais rápido.
- Gerar `api/tipos.ts` automaticamente a partir do `/openapi.json`, evitando divergência entre backend e frontend.
- Testes de ponta a ponta no navegador (Playwright) na CI.
- Notificação por e-mail ou chat quando surgir norma nova.
