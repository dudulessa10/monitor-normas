# Servidor Linux (VM): referência de operação

Passo a passo resumido da instalação: [docs/PROJETO.md](../docs/PROJETO.md#8-instalação-na-vm-linux-passo-a-passo).
Este arquivo detalha o que cada peça faz e como operar no dia a dia. Testado em Ubuntu 24.04
(também serve para Debian 12), com systemd. No Windows nada disso é necessário.

## Onde fica cada coisa

| Onde | O quê |
|---|---|
| `~/monitor-legislacao-anac` | o código (clone do repositório), o `.venv`, o Node do projeto (`.ferramentas/`), o build do frontend e o `.env` |
| `~/monitor-legislacao-anac/.env` | variáveis do projeto, incluindo a senha (permissão 600). Lido **só** pelos serviços deste projeto e pelo `deploy/monitor.sh` |
| `/var/lib/monitor-normas` | `dados/`, `relatorios/` e `logs/` (`MONITOR_NORMAS_BASE`) |
| `/var/lib/monitor-normas/chave` | chave e cópia da última âncora do ledger (`MONITOR_NORMAS_PASTA_SEGURA`) |
| `/var/lib/monitor-normas-backups` | um `.tar.gz` de `dados/` por dia, guardado por 30 dias |
| `/etc/systemd/system/monitor-normas-*` | as unidades systemd, geradas pelo `deploy/instalar-servicos.sh` a partir dos modelos desta pasta |

Os serviços rodam com o usuário de sistema `monitor-normas`, que **lê** o código no seu home
(`ProtectHome=read-only`: não consegue alterar nada lá) e só escreve em `/var/lib/monitor-normas*`.
Para conseguir ler, ele recebe permissão apenas de *atravessar* (`x`, por ACL) as pastas acima do
projeto. Ele não lista nem lê os outros arquivos do seu home.

**Isolamento:** nada do projeto altera `~/.bashrc`, `~/.profile`, `/etc/environment`, o Python ou o
Node do sistema, nem variáveis ou arquivos de outras aplicações do home.

## Scripts desta pasta

| Script | Onde roda | O que faz |
|---|---|---|
| `../setup.sh` | VM, **sem** sudo | `.venv` + dependências Python, Node do projeto, `npm ci` e build do frontend |
| `instalar-servicos.sh` | VM, com sudo | cria o usuário `monitor-normas` (se faltar), grava as unidades systemd apontando para a pasta do projeto, liga web, execução diária e backup |
| `exportar-dados.ps1` | Windows | confere o ledger e empacota `dados/`, `relatorios/` e a chave das âncoras |
| `importar-dados.sh` | VM, com sudo | guarda uma cópia do que já existe, coloca os dados do Windows em `/var/lib/monitor-normas`, ajusta a âncora e confere o ledger |
| `monitor.sh` | VM, com sudo | roda qualquer comando do `monitor.py` como o usuário do serviço e com as variáveis do `.env` |
| `backup.sh` | serviço | cópia diária consistente de `dados/` (usado pelo `monitor-normas-backup.timer`) |

Unidades systemd:

- `monitor-normas-web.service`: telas + API em `127.0.0.1:8000`, publicadas pelo Caddy com HTTPS.
- `monitor-normas-run.timer`: roda `monitor.py run --origem agendamento` todo dia às 06:00
  (substitui o `monitor.py agendar`, que é só para o Windows).
- `monitor-normas-backup.timer`: cópia de `dados/` às 07:00.

## Trazer os dados do Windows

Os dados (`dados/`, `relatorios/`) e a chave das âncoras **não vão pelo Git**: são gerados pelo robô
e mudam todo dia. Sem este passo, a VM começa do zero (a primeira execução vira linha de base, e o
histórico e o ledger ficam no Windows). É o motivo mais comum de "a VM não está igual ao meu PC".

No Windows, na pasta do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\exportar-dados.ps1
scp "$env:USERPROFILE\Desktop\monitor-dados.tar.gz" "$env:USERPROFILE\Desktop\monitor-chave.tar.gz" usuario@vm:/tmp/
```

(Se a Área de Trabalho estiver no OneDrive, o script mostra o caminho certo no fim.)

Na VM:

```bash
sudo ~/monitor-legislacao-anac/deploy/importar-dados.sh /tmp/monitor-dados.tar.gz /tmp/monitor-chave.tar.gz
rm /tmp/monitor-dados.tar.gz /tmp/monitor-chave.tar.gz
```

Depois, **desative a execução automática no Windows** (`python monitor.py agendar --remover`),
senão as duas máquinas vigiam a ANAC e os ledgers divergem. Guarde o `monitor-chave.tar.gz` num
lugar seguro fora da VM.

Instalação nova, sem dados do Windows: em vez disso, faça a carga inicial dos alvos:
`sudo ~/monitor-legislacao-anac/deploy/monitor.sh importar-yaml`.

## Migrar a instalação antiga (`/opt/monitor-normas`)

Se a VM já tinha a versão anterior em `/opt/monitor-normas` com `/etc/monitor-normas/monitor-normas.env`:

```bash
cd ~/monitor-legislacao-anac
sudo cp /etc/monitor-normas/monitor-normas.env .env    # mesmas variáveis, mesmos valores
sudo chown "$USER": .env && chmod 600 .env
./setup.sh
sudo deploy/instalar-servicos.sh                      # substitui as unidades antigas (mesmos nomes)
```

Os dados em `/var/lib/monitor-normas` continuam onde estão e são usados pela nova instalação. Se
eles estiverem incompletos em relação ao Windows, faça a importação acima. Quando tudo estiver
funcionando, a pasta antiga pode ser apagada (`sudo rm -rf /opt/monitor-normas`); o arquivo
`/etc/monitor-normas/monitor-normas.env` deixa de ser usado e pode ser apagado também.

## HTTPS (Caddy)

```bash
sudo apt install -y caddy
sudo cp ~/monitor-legislacao-anac/deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile        # troque monitor.exemplo.com.br pelo seu domínio
sudo systemctl reload caddy
```

Libere só as portas 22, 80 e 443 no firewall da VM (e do provedor). A porta 8000 não deve ficar
acessível de fora. Com `MONITOR_NORMAS_SENHA` definida, as telas e a API pedem usuário e senha (o
navegador mostra a janela de login); só `/api/v1/saude` fica aberta, para monitoramento. A senha
passa em texto pela requisição: por isso o acesso é sempre pelo HTTPS do Caddy.

## Dia a dia

| Para | Comando |
|---|---|
| atualizar o código | `cd ~/monitor-legislacao-anac && git pull && ./setup.sh && sudo systemctl restart monitor-normas-web` |
| ver se o servidor está no ar | `systemctl status monitor-normas-web` ou `curl https://<domínio>/api/v1/saude` |
| próxima execução agendada | `systemctl list-timers 'monitor-normas*'` |
| rodar agora | `sudo systemctl start monitor-normas-run` (ou o botão "Rodar agora") |
| outros comandos da CLI | `sudo ~/monitor-legislacao-anac/deploy/monitor.sh list` (ou `buscar`, `ancora`, `exportar`, `verificar-ledger`...) |
| resultado da última execução | `journalctl -u monitor-normas-run -n 50` |
| log detalhado | `sudo less /var/lib/monitor-normas/logs/monitor.log` |
| mudar o horário | editar `OnCalendar` em `deploy/monitor-normas-run.timer` e rodar `sudo deploy/instalar-servicos.sh` |
| mudou a senha ou outra variável | editar `.env` e `sudo systemctl restart monitor-normas-web` |

- Se uma atualização trouxer mudança em `deploy/*.service` ou `*.timer`, rode de novo
  `sudo deploy/instalar-servicos.sh` (pode rodar sempre; ele só regrava as unidades).
- **Alerta de execução parada:** um monitor externo (UptimeRobot, Healthchecks etc.) pode consultar
  `/api/v1/saude` e avisar se `ultima_rodada_inicio` ficar com mais de um dia.
- **Backups fora da VM:** os de `/var/lib/monitor-normas-backups` ficam no mesmo disco. Mande-os para
  fora (rclone para um bucket, `scp` para outra máquina) ou ative snapshots do disco no provedor. A
  chave das âncoras não entra nesses backups de propósito: quem tem só o backup não consegue forjar
  âncoras.
- **Âncora externa:** continue guardando de tempos em tempos o `INDICE:HASH` que sai no relatório
  (`monitor.sh ancora`) fora da VM.
