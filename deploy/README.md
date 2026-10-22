# Servidor Linux (VM)

Roteiro para rodar o Monitor de Normas numa VM Linux (testado no papel para Ubuntu 24.04 /
Debian 12, com systemd). No Windows nada muda: sem as variáveis abaixo, tudo continua na pasta
do projeto, como antes.

| Onde | O quê |
|---|---|
| `/opt/monitor-normas` | o código (clone do repositório) e o `.venv` |
| `/var/lib/monitor-normas` | `dados/`, `relatorios/` e `logs/` (`MONITOR_NORMAS_BASE`) |
| `/var/lib/monitor-normas/chave` | chave e cópia da última âncora do ledger (`MONITOR_NORMAS_PASTA_SEGURA`) |
| `/var/lib/monitor-normas-backups` | um `.tar.gz` de `dados/` por dia, guardados por 30 dias |
| `/etc/monitor-normas/monitor-normas.env` | variáveis, incluindo a senha (dono root, permissão 600) |

Três unidades systemd:

- `monitor-normas-web.service`: o aplicativo web, em `127.0.0.1:8000`, publicado pelo Caddy com HTTPS.
- `monitor-normas-run.timer`: roda `monitor.py run --origem agendamento` todo dia às 06:00
  (substitui o `monitor.py agendar`, que é só para o Windows).
- `monitor-normas-backup.timer`: cópia de `dados/` às 07:00.

## 1. Preparar a VM

```bash
sudo timedatectl set-timezone America/Sao_Paulo      # o horário 06:00 é a hora local
sudo apt update && sudo apt install -y python3 python3-venv git caddy
sudo useradd --system --home /var/lib/monitor-normas --shell /usr/sbin/nologin monitor-normas
```

Python 3.11 ou mais novo (o Ubuntu 24.04 traz o 3.12).

## 2. Código e dependências

```bash
sudo git clone <url-do-repositório> /opt/monitor-normas
cd /opt/monitor-normas
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements-lock.txt
```

O código fica com dono root: o serviço só lê. O `alvos.yaml` (horário, regex, palavras-chave)
é editado no repositório e chega à VM pelo `git pull`.

## 3. Variáveis e senha

```bash
sudo install -d -m 755 /etc/monitor-normas
sudo install -m 600 deploy/monitor-normas.env.exemplo /etc/monitor-normas/monitor-normas.env
sudo nano /etc/monitor-normas/monitor-normas.env      # troque a senha
```

Com `MONITOR_NORMAS_SENHA` definida, as telas e a API pedem usuário e senha (o navegador mostra
a janela de login). Só `/api/v1/saude` fica aberta, para o monitoramento. A senha passa em
texto pela requisição: por isso o acesso é sempre pelo HTTPS do Caddy.

## 4. Trazer os dados do Windows

Sem isso, a VM começa do zero: a primeira execução de cada alvo vira linha de base, e o
histórico e o ledger atuais ficam para trás.

No Windows, **sem nenhuma execução em andamento**:

```powershell
# na pasta do projeto
python monitor.py verificar-ledger                    # confira que está tudo OK antes de mover
tar -czf $env:USERPROFILE\Desktop\monitor-dados.tar.gz dados
tar -czf $env:USERPROFILE\Desktop\monitor-chave.tar.gz -C $env:LOCALAPPDATA MonitorNormas
```

Copie os dois arquivos para a VM (por exemplo, `scp` para `/tmp`) e, nela:

```bash
sudo install -d -o monitor-normas -g monitor-normas -m 750 /var/lib/monitor-normas /var/lib/monitor-normas/chave
sudo tar -xzf /tmp/monitor-dados.tar.gz -C /var/lib/monitor-normas
sudo tar -xzf /tmp/monitor-chave.tar.gz -C /var/lib/monitor-normas/chave --strip-components=1
sudo rm -f /var/lib/monitor-normas/dados/monitor.lock
sudo chown -R monitor-normas:monitor-normas /var/lib/monitor-normas
sudo chmod 600 /var/lib/monitor-normas/chave/*
```

A cópia da última âncora tem no nome um código do caminho do ledger, que mudou. Renomeie-a
para o nome novo:

```bash
cd /opt/monitor-normas
sudo bash -c 'set -a; . /etc/monitor-normas/monitor-normas.env; .venv/bin/python -c "
from monitor_normas.ancora import Ancoras; from monitor_normas.ledger import Ledger
print(Ancoras(Ledger(\"/var/lib/monitor-normas/dados/ledger.jsonl\")).copia_local)"'
# mostra algo como /var/lib/monitor-normas/chave/ultima_ancora_XXXXXXXXXXXX.json
sudo mv /var/lib/monitor-normas/chave/ultima_ancora_*.json <o caminho mostrado acima>
```

Confira (deve dar OK, com as assinaturas conferidas):

```bash
sudo deploy/monitor.sh verificar-ledger
```

Depois de conferir, **desative a tarefa no Windows** (`python monitor.py agendar --remover`),
senão as duas máquinas vigiam a ANAC e os ledgers divergem. Guarde a chave
(`monitor-chave.tar.gz`) num lugar seguro fora da VM e apague as cópias em `/tmp`.

Instalação nova, sem dados do Windows: em vez deste passo, rode a carga inicial dos alvos:

```bash
sudo deploy/monitor.sh importar-yaml
```

## 5. Serviços

```bash
sudo cp deploy/monitor-normas-*.service deploy/monitor-normas-*.timer /etc/systemd/system/
sudo cp deploy/logrotate /etc/logrotate.d/monitor-normas
sudo systemctl daemon-reload
sudo systemctl enable --now monitor-normas-web.service monitor-normas-run.timer monitor-normas-backup.timer
curl http://127.0.0.1:8000/api/v1/saude
```

## 6. HTTPS (Caddy)

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo nano /etc/caddy/Caddyfile        # troque monitor.exemplo.com.br pelo seu domínio
sudo systemctl reload caddy
```

Libere só as portas 22, 80 e 443 no firewall da VM (e do provedor). A porta 8000 não deve ficar
acessível de fora.

## Dia a dia

| Para | Comando |
|---|---|
| ver se o servidor está no ar | `systemctl status monitor-normas-web` ou `curl https://<domínio>/api/v1/saude` |
| próxima execução agendada | `systemctl list-timers 'monitor-normas*'` |
| rodar agora | `sudo systemctl start monitor-normas-run` (ou o botão "Rodar agora") |
| outros comandos da CLI | `sudo /opt/monitor-normas/deploy/monitor.sh list` (ou `buscar`, `ancora`, `exportar`...) |
| resultado da última execução | `journalctl -u monitor-normas-run -n 50` |
| log detalhado | `/var/lib/monitor-normas/logs/monitor.log` |
| mudar o horário | editar `OnCalendar` em `/etc/systemd/system/monitor-normas-run.timer` e `sudo systemctl daemon-reload` |
| atualizar o código | `cd /opt/monitor-normas && sudo git pull && sudo .venv/bin/pip install -r requirements-lock.txt && sudo systemctl restart monitor-normas-web` |

- **Alerta de execução parada:** um monitor externo (UptimeRobot, Healthchecks etc.) pode
  consultar `/api/v1/saude` e avisar se `ultima_rodada_inicio` ficar com mais de um dia.
- **Backups fora da VM:** os de `/var/lib/monitor-normas-backups` ficam no mesmo disco. Mande-os
  para fora (rclone para um bucket, `scp` para outra máquina) ou ative snapshots do disco no
  provedor. A chave das âncoras não entra nesses backups de propósito: quem tem só o backup não
  consegue forjar âncoras.
- **Âncora externa:** continue guardando de tempos em tempos o `INDICE:HASH` que sai no relatório
  (`monitor.py ancora`) fora da VM.
