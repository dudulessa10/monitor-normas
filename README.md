# Monitor de Normas (protótipo)

Robô que vigia páginas de legislação da ANAC (que não tem API) e detecta normas
**novas**, **alteradas** ou **removidas**. O código é genérico: os alvos
(quais páginas vigiar) ficam no banco e são editados pela tela web ou pela API.

Há três formas de usar, todas sobre os mesmos dados:

- **Aplicativo web** (`uvicorn app:app`): telas de gestão e API REST em `/api/v1`.
- **Linha de comando** (`python monitor.py ...`).
- **Execução diária automática**, que chama a linha de comando (não o servidor).

## Instalação

Requer Python 3.11 ou mais novo.

```bash
# Windows (PowerShell)
py -3.14 -m venv .venv          # ou qualquer Python >= 3.11
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# só na primeira vez: carrega no banco os alvos do alvos_iniciais.yaml
python monitor.py importar-yaml
```

## Aplicativo web

```bash
uvicorn app:app --reload        # http://localhost:8000  (documentação da API em /docs)
```

`--reload` reinicia o servidor quando o código muda (use durante o
desenvolvimento). O servidor escuta só em `127.0.0.1` e, localmente, não pede
senha. Para rodar numa VM Linux, com senha, HTTPS e execução diária pelo
systemd, siga o [deploy/README.md](deploy/README.md).

| Tela | O que faz |
|---|---|
| **Painel** | última execução, botão "Rodar agora" (todos ou um alvo), integridade do ledger com a âncora atual, mudanças dos últimos 7 dias |
| **Alvos** | tabela com ativar/desativar, editar, rodar um alvo e excluir; formulário para cadastrar novo alvo |
| **Mudanças** | filtros por palavra-chave, alvo, tipo e períodos (publicação e detecção), link para a norma e "Baixar Excel" com os mesmos filtros |
| **Execuções** | histórico de todas as rodadas (web, linha de comando e agendadas), com os erros de cada alvo à vista |

### API REST (`/api/v1`)

| Método e caminho | Para quê |
|---|---|
| `GET /alvos`, `GET /alvos/{id}` | alvos com validade, itens vigentes e última execução |
| `POST /alvos`, `PUT /alvos/{id}`, `DELETE /alvos/{id}` | cadastrar, substituir, remover (o histórico e o ledger do alvo são mantidos) |
| `POST /alvos/{id}/ativar`, `POST /alvos/{id}/desativar` | liga e desliga; um alvo com definição inválida não pode ser ativado |
| `POST /execucoes` (`{"alvo": null}` = todos os ativos) | dispara em segundo plano: responde **202** com `rodada_id` na hora, ou **409** se outra execução (web, CLI ou agendada) está em andamento |
| `GET /execucoes`, `GET /execucoes/{id}` | histórico de rodadas, com uma execução por alvo (início, fim, status, itens, erros) |
| `GET /mudancas` | filtros `alvo`, `tipo`, `palavra`, `de`/`ate` (publicação), `registrado_de`/`registrado_ate` (detecção), `incluir_linha_base` |
| `GET /normas?q=` | normas vigentes (estado atual), com busca por texto |
| `GET /ledger`, `GET /ledger/verificar?ancora=` | blocos do ledger; verificação da cadeia e das âncoras |
| `GET /exportar/excel` | planilha com as abas Mudanças (com os filtros de `/mudancas`), Normas vigentes e Execuções |
| `GET /configuracao` | regex, palavras-chave, frequência e horário do `alvos.yaml` (somente leitura) |
| `GET /saude` | servidor no ar e início/status da última rodada (para monitoramento; não pede senha) |

- **Respostas:** listas vêm paginadas (`limite`, `deslocamento`, resposta
  `{total, limite, deslocamento, itens}`), e erros vêm como `{"detail": "mensagem"}`.
- **Validação dos alvos:** a API recusa campos desconhecidos (um erro de
  digitação vira 422 em vez de ser ignorado) e aplica a mesma validação da
  linha de comando (ex.: regex inexistente).
- **Servidor reiniciado no meio de uma execução:** ao subir de novo, a rodada
  fica marcada como `interrompida`.

## Linha de comando

```bash
python monitor.py run                       # roda todos os alvos ativos
python monitor.py run --alvo anac-resolucoes  # roda só um alvo
python monitor.py list                      # alvos e último estado de cada um
python monitor.py importar-yaml             # carga inicial dos alvos (alvos_iniciais.yaml)
python monitor.py exportar                  # planilha em relatorios/monitor_normas_DATA.xlsx
python monitor.py verificar-ledger          # confere a cadeia de hashes e as âncoras do ledger
python monitor.py ancora                    # mostra a âncora atual, para guardar fora do computador
python monitor.py buscar aerodromo          # procura normas no ledger
python monitor.py agendar                   # instala a execução automática diária
python -m pytest                            # testes (offline, usam tests/fixtures)
```

A **primeira execução** de cada alvo registra tudo como linha de base (nada
aparece como NOVO). A partir da segunda, o relatório mostra só as mudanças.

Códigos de saída de `run`: 0 se tudo deu certo, 1 se algum alvo falhou ou o
ledger não pôde ser ancorado, 2 para alvo ou configuração inválidos e 3 se outra
execução já estava em andamento.

`run` e o botão "Rodar agora" passam pelo mesmo código (`rodada.py`): os dois
geram o relatório, conferem a âncora e aparecem no mesmo histórico, com a
origem `cli`, `agendamento` ou `web`.

## Execução automática

```bash
python monitor.py agendar                   # instala (ou atualiza) a tarefa
python monitor.py agendar --horario 07:30   # outro horário, sem editar o YAML
python monitor.py agendar --status          # última execução, resultado e próxima
python monitor.py agendar --remover         # desinstala
python monitor.py run                       # forçar uma execução a qualquer momento
```

No Windows, `agendar` cria a tarefa `MonitorNormas` no Agendador de Tarefas
usando `frequencia` e `horario` da seção `padroes` do `alvos.yaml` (`diaria`,
`semanal` às segundas, ou `manual` para não agendar). Não precisa de
administrador. Depois de editar `frequencia` ou `horario`, rode `agendar` de
novo. A tarefa usa o mesmo Python que rodou o comando (o `pythonw.exe` do
`.venv`, sem abrir janela) e chama `monitor.py run --origem agendamento`; ela não
depende do servidor web estar no ar.

- Se o computador estiver desligado ou dormindo no horário, a execução acontece
  assim que possível depois.
- A tarefa só roda com o usuário logado no Windows.
- Duas execuções nunca rodam ao mesmo tempo, venham da web, da linha de comando
  ou do agendamento: a segunda é recusada (código 3 na CLI, HTTP 409 na API).
  A trava é o arquivo `dados/monitor.lock`, e o sistema a libera mesmo se o
  processo morrer.

Fora do Windows, `agendar` imprime a linha para colocar no `crontab -e`.

## Variáveis de ambiente

Todas são opcionais; sem elas, tudo fica na pasta do projeto, como no uso local.

| Variável | Para quê |
|---|---|
| `MONITOR_NORMAS_BASE` | pasta de `dados/`, `relatorios/` e `logs/` (o `alvos.yaml` continua na pasta do código) |
| `MONITOR_NORMAS_PASTA_SEGURA` | pasta da chave e da cópia da última âncora (padrão: `%LOCALAPPDATA%\MonitorNormas` ou `~/.config/monitor_normas`) |
| `MONITOR_NORMAS_SENHA`, `MONITOR_NORMAS_USUARIO` | ligam a senha (HTTP Basic) nas telas e na API; usuário padrão `admin` |

## Integridade do ledger (âncoras)

O encadeamento por SHA-256 pega a alteração de um bloco, mas não pega quem
reescreve o arquivo inteiro recalculando os hashes, nem quem apaga os últimos
blocos. Para isso existem as âncoras:

| Camada | Onde | Protege contra |
|---|---|---|
| Âncora assinada (HMAC-SHA256) do último bloco, gravada a cada execução | `dados/ancoras.jsonl` | reescrita completa e corte do final por quem só tem acesso à pasta do projeto (OneDrive, backup, colega) |
| Chave da assinatura | `%LOCALAPPDATA%\MonitorNormas\chave_ledger.bin` (fora do OneDrive) | forjar âncoras sem a chave |
| Cópia da última âncora | `%LOCALAPPDATA%\MonitorNormas\ultima_ancora_*.json` | apagar `ancoras.jsonl` junto com o final do ledger |
| Âncora externa | o que você guardar fora do computador | qualquer um, inclusive quem tem acesso a este computador e à chave |

```bash
python monitor.py ancora                                   # ancora agora e mostra INDICE:HASH
python monitor.py verificar-ledger --ancora 1739:70b1bc036c67   # confere uma âncora guardada (12+ caracteres do hash)
```

A âncora também sai no fim de cada execução do relatório. Guardá-la fora do
computador de tempos em tempos (e-mail para si mesmo, outro serviço) é o que dá
a proteção mais forte.

- Uma execução só ancora o ledger se a verificação completa passar; se não
  passar, o relatório traz um alerta e `run` termina com código 1.
- Sem a chave (outra máquina, chave perdida), `verificar-ledger` ainda confere os
  hashes das âncoras, mas avisa que as assinaturas não foram conferidas. Faça
  backup da chave se for trocar de computador.
- Se apagar `dados/` de propósito para recomeçar, apague também o
  `ultima_ancora_*.json` correspondente; senão `verificar-ledger` acusa
  âncoras apagadas.

## Busca no ledger

```bash
python monitor.py buscar aerodromo                      # ignora maiúsculas e acentos
python monitor.py buscar rbac 91                        # todas as palavras precisam aparecer
python monitor.py buscar --tipo NOVO --de 2026-10-01    # novidades publicadas desde 01/10
python monitor.py buscar tripulada --alvo anac-is --json  # saída em JSON
```

Procura nas colunas norma e ementa e nas palavras-chave de cada bloco,
casando pelo começo das palavras ("tripulada" acha "tripuladas"; "817" não
acha "1817"). `--de` e `--ate` filtram pela data de publicação (registros sem
data ficam de fora). Os resultados vêm do mais recente para o mais antigo,
até 50 (`--limite 0` mostra todos). Se o ledger não passar na verificação de
integridade, a busca mostra um aviso.

## O que é gerado

| Caminho | Conteúdo |
|---|---|
| `dados/estado.db` | SQLite com os alvos, os itens vistos por alvo (hash, primeira e última vez visto), as rodadas e o histórico de execuções |
| `dados/ledger.jsonl` | Registro append-only das mudanças, encadeado por SHA-256. Guarda só as referências (link), não os PDFs |
| `dados/ancoras.jsonl` | Âncoras assinadas do ledger (ver "Integridade do ledger") |
| `relatorios/relatorio_AAAA-MM-DD.md` | Mudanças por alvo. Várias execuções no mesmo dia são acrescentadas ao mesmo arquivo |
| `logs/monitor.log` | Log detalhado, incluindo os erros |

Um erro em um alvo (página fora do ar, tabela mudou de formato) é registrado e
não interrompe os demais.

## Configuração e alvos

| Arquivo | Conteúdo |
|---|---|
| `alvos.yaml` | configurações **globais**: `padroes` (frequência, horário, timeout...), `regex` e `palavras_chave_globais`. Editado à mão |
| banco (`dados/estado.db`) | os **alvos**. Editados pela tela Alvos ou pela API |
| `alvos_iniciais.yaml` | carga inicial dos alvos, usada só por `importar-yaml`. Editar depois da carga não muda nada |

`importar-yaml` não sobrescreve alvos que já estão no banco (para não desfazer
o que foi editado pela web). Use `--substituir` para sobrescrever, ou
`--arquivo outro.yaml` para importar de outro arquivo.

Campos de um alvo (os mesmos na tela, na API e no YAML de importação):

| Campo | Para que serve |
|---|---|
| `url` | Pode conter `{ano}`, que é trocado pelo ano. `anos: [atual, anterior]` vigia os dois anos, o que é útil em janeiro |
| `deteccao.metodo` | `lista_itens` (linha a linha da tabela), `hash_conteudo` (texto da página) ou `data_modificacao` ("última modificação" do Plone) |
| `deteccao.chave_item` | Campo que identifica cada linha (normalmente `norma`) |
| `deteccao.detectar_mudanca_em` | Campos que, se mudarem, tornam o item ALTERADO. Sem esse campo, valem todos os campos de texto (os links ficam de fora). Mudar esse campo ou `colunas` não gera ALTERADO falso: a comparação usa sempre os campos configurados no momento |
| `extracao.tabela` | `primeira` ou `todas` |
| `extracao.colunas` | `auto` (usa o cabeçalho da tabela: "Publicação" vira `publicacao`) ou um mapeamento `Cabeçalho: campo`. Um campo cujo nome começa com `link` recebe o endereço do link em vez do texto |
| `extracao.regex_numero` | Nome de uma regex da seção `regex` para extrair o número da norma |
| `extracao.marcar_status` | `status: nome_da_regex`, aplicado à norma e à ementa (ex.: revogada, alterada) |
| `timeout_segundos`, `tentativas`, `pausa_entre_requisicoes_segundos`, `user_agent` | Definidos em `padroes`; cada alvo pode sobrescrever |

Observações:

- **Regex:** as regex ignoram maiúsculas e minúsculas, porque o site escreve
  "RESOLUÇÃO Nº 817". Com um só grupo de captura, o número é esse grupo; com
  vários grupos (como em `rbac`), o número é o trecho inteiro encontrado. Se a
  regex não casar, o robô tenta achar "Nº ..." sozinho.
- **Tipo da norma:** é o texto antes do número (RESOLUÇÃO, RBAC, IS, CE/SC...).
  Ele entra nas palavras-chave junto com o número e com as
  `palavras_chave_globais` encontradas na ementa. Essa busca ignora acentos e
  aceita plural simples.
- **Chaves duplicadas:** quando duas linhas têm a mesma chave (por exemplo, duas
  versões do "RBAC 21 EMD 15"), o robô acrescenta o final do link da linha:
  `RBAC 21 EMD 15 [rbac-21-emd-15]`.
- **Página vazia:** se uma página que tinha itens vier vazia, o alvo dá erro e o
  estado não é alterado. Isso evita marcar tudo como REMOVIDO por uma falha
  temporária do site.
- **robots.txt:** o robô respeita o robots.txt de cada site. Por isso o
  `www.anac.gov.br/rss` é bloqueado mesmo se for ativado.
- **Nova emenda de RBAC:** como a chave é o texto "RBAC XX EMD NN", uma nova
  emenda aparece como REMOVIDO (emenda antiga) + NOVO (emenda nova).

## Estrutura

Três camadas, com dependência num só sentido: `web → api → monitor_normas`. O
robô não sabe que a web existe, e a API não tem regra de negócio: ela valida a
entrada, chama o robô e devolve JSON. O frontend usa só a API JSON, a mesma que
outra aplicação usaria.

```
monitor_normas/         ROBÔ (usado pela CLI e pela API)
  coleta.py             download (robots.txt, timeout, tentativas, pausa)
  extracao.py           tabelas, regex, hash e "última modificação"
  deteccao.py           NOVO / ALTERADO / REMOVIDO
  palavras_chave.py     palavras-chave
  config.py             configurações globais (YAML) e validação dos alvos
  alvos.py              alvos no SQLite (CRUD e importação do YAML)
  estado.py             SQLite: itens, rodadas e execuções
  execucao.py           execução por alvo e trava entre processos
  rodada.py             uma rodada completa (trava, execução, relatório, âncora)
  ledger.py             ledger encadeado e verificação
  ancora.py             âncoras assinadas do ledger
  busca.py              filtros sobre o ledger
  consultas.py          leituras para a API e a exportação
  planilha.py           planilha .xlsx
  relatorio.py          relatório Markdown e resumo
  agendamento.py        tarefa do Agendador do Windows / linha de cron
api/                    CAMADA HTTP (FastAPI)
  main.py               criar_app(): rotas em /api/v1 e o frontend em /
  autenticacao.py       senha opcional (HTTP Basic)
  esquemas.py           contrato de entrada e saída (Pydantic)
  executor.py           rodadas em segundo plano (thread + trava)
  contexto.py           dependências das rotas
  rotas/                alvos, execuções, consultas e saúde
web/                    FRONTEND (HTML + JS puro, sem build)
  index.html, estilo.css
  js/api.js             único ponto de acesso à API
  js/painel.js, alvos.js, mudancas.js, execucoes.js
app.py                  "uvicorn app:app"
monitor.py              CLI
tests/                  pytest (offline): robô, CLI, banco e API (test_api.py)
deploy/                 servidor Linux: systemd, Caddy, backup, logrotate e roteiro (README.md)
requirements-lock.txt   versões exatas para o servidor
```
