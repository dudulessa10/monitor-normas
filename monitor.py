"""CLI do robô de monitoramento de normas.

    python monitor.py run                      roda todos os alvos ativos
    python monitor.py run --alvo anac-rbac     roda só um alvo
    python monitor.py list                     mostra os alvos e o último estado
    python monitor.py verificar-ledger         confere a cadeia de hashes e as âncoras do ledger
    python monitor.py ancora                   mostra a âncora atual, para guardar fora deste computador
    python monitor.py buscar drone --de 2026-01-01   procura normas no ledger
    python monitor.py agendar                  instala a execução automática (horário do alvos.yaml)
    python monitor.py agendar --status         mostra a última e a próxima execução agendada
    python monitor.py agendar --remover        remove a execução automática
    python monitor.py importar-yaml            carrega os alvos do alvos_iniciais.yaml no banco
    python monitor.py exportar                 gera a planilha Excel (mudanças, normas, execuções)

Os alvos ficam no banco (dados/estado.db) e podem ser editados pela web ou pela API;
o alvos.yaml guarda as configurações globais (regex, palavras-chave, frequência e horário).
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from monitor_normas import agendamento, consultas, planilha, relatorio
from monitor_normas.alvos import RepositorioAlvos
from monitor_normas.ancora import ancorar, ler_externa, verificar_tudo
from monitor_normas.ancora import formatar as formatar_ancora
from monitor_normas.busca import Filtros, buscar, formatar
from monitor_normas.config import ErroConfig, carregar_globais, montar_config, validar_horario
from monitor_normas.deteccao import ALTERADO, LINHA_BASE, NOVO, REMOVIDO
from monitor_normas.estado import Estado
from monitor_normas.execucao import (Caminhos, ExecucaoEmAndamento, agora_local, caminhos_padrao, handler_log,
                                     trava_exclusiva)
from monitor_normas.ledger import Ledger
from monitor_normas.rodada import rodar

PASTA = Path(__file__).resolve().parent


def configurar_log(caminhos: Caminhos) -> None:
    handlers: list[logging.Handler] = [handler_log(caminhos)]
    if sys.stderr is not None:  # com pythonw.exe (execução agendada) não há console
        tela = logging.StreamHandler(sys.stderr)
        tela.setLevel(logging.WARNING)
        tela.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handlers.append(tela)
    logging.basicConfig(level=logging.INFO, handlers=handlers)


def relativo(caminho: Path, base: Path) -> Path:
    try:
        return caminho.relative_to(base)
    except ValueError:
        return caminho


def cmd_run(args, config, caminhos: Caminhos) -> int:
    try:
        rodada = rodar(config, caminhos, alvo_id=args.alvo, origem=args.origem)
    except KeyError:
        print(f"Alvo não encontrado: {args.alvo}. Use 'python monitor.py list' para ver os ids.")
        return 2
    except ExecucaoEmAndamento as e:
        logging.getLogger("monitor").warning("%s; esta execução foi cancelada", e)
        return 3
    if not rodada.resultados:
        print("Nenhum alvo ativo. Ative um alvo pela tela Alvos ou pela API.")
        return 0
    print(relatorio.resumo(rodada.resultados))
    if rodada.alerta_ledger:
        print(f"ATENÇÃO: {rodada.alerta_ledger}")
    print(f"Relatório: {relativo(rodada.relatorio, caminhos.base)}")
    print(f"Log: {relativo(caminhos.logs / 'monitor.log', caminhos.base)}")
    return 0 if rodada.status == "ok" else 1


def cmd_importar_yaml(args, caminhos: Caminhos) -> int:
    arquivo = args.arquivo or args.config.resolve().parent / "alvos_iniciais.yaml"
    try:
        definicoes = carregar_globais(arquivo).alvos_yaml
    except (ErroConfig, OSError) as e:
        print(f"Não foi possível ler {arquivo}: {e}")
        return 2
    if not definicoes:
        print(f"{arquivo} não tem a seção 'alvos'.")
        return 1
    try:
        with RepositorioAlvos(caminhos.estado_db) as repo:
            importados, ignorados = repo.importar(definicoes, substituir=args.substituir)
    except ErroConfig as e:
        print(f"Importação cancelada: {e}")
        return 2
    print(f"{len(importados)} alvo(s) importado(s) de {arquivo.name}" + (f": {', '.join(importados)}" if importados else "."))
    if ignorados:
        print(f"{len(ignorados)} já existiam e foram mantidos ({', '.join(ignorados)}); "
              "use --substituir para sobrescrever.")
    return 0


def cmd_exportar(args, config, caminhos: Caminhos) -> int:
    saida = args.saida or caminhos.relatorios / f"monitor_normas_{date.today().isoformat()}.xlsx"
    _, rodadas = consultas.rodadas(caminhos, limite=500)
    conteudo = planilha.gerar(consultas.mudancas(caminhos, Filtros(sem_linha_base=True)),
                              consultas.normas(caminhos), rodadas)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_bytes(conteudo)
    print(f"Planilha: {relativo(saida.resolve(), caminhos.base)}")
    return 0


def cmd_list(args, config, caminhos: Caminhos) -> int:
    if not config.alvos:
        print("Nenhum alvo cadastrado. Use 'python monitor.py importar-yaml' ou a tela Alvos (uvicorn app:app).")
        return 0
    with Estado(caminhos.estado_db) as estado:
        resumo = estado.resumo()
    largura = max(len(a.id) for a in config.alvos) if config.alvos else 10
    print(f"  {'alvo':<{largura}}  {'ativo':<5}  {'método':<16}  {'itens':>5}  {'última execução':<19}  status")
    for alvo in config.alvos:
        r = resumo.get(alvo.id, {})
        if alvo.erro_config:
            status = f"config inválida: {alvo.erro_config}"
        elif "status" not in r:
            status = "nunca executado"
        elif r["status"] == "erro":
            status = f"ERRO: {r['erro']}"
        elif r["status"] == "linha_base":
            status = "linha de base"
        else:
            status = f"ok (+{r['novos']} ~{r['alterados']} -{r['removidos']})"
        if r.get("modificacao_pagina"):
            status += f" | página modificada em {r['modificacao_pagina']}"
        quando = (r.get("fim") or "")[:19].replace("T", " ")
        print(f"  {alvo.id:<{largura}}  {'sim' if alvo.ativo else 'não':<5}  {alvo.metodo:<16}  "
              f"{r.get('vigentes', 0):>5}  {quando:<19}  {status}")
    return 0


def cmd_verificar_ledger(args, config, caminhos: Caminhos) -> int:
    resultado = verificar_tudo(Ledger(caminhos.ledger), args.ancora or [])
    if not resultado.ok:
        print(f"Ledger com problemas ({len(resultado.erros)}; {resultado.total} blocos):")
        for erro in resultado.erros:
            print(f"  - {erro}")
    elif resultado.total == 0:
        print("Ledger vazio ou inexistente.")
    else:
        print(f"Ledger íntegro: {resultado.total} blocos, cadeia de hashes válida, "
              f"{resultado.ancoras} âncora(s) conferida(s).")
    for aviso in resultado.avisos:
        print(f"Aviso: {aviso}")
    return 0 if resultado.ok else 1


def cmd_ancora(args, config, caminhos: Caminhos) -> int:
    ledger = Ledger(caminhos.ledger)
    try:
        with trava_exclusiva(caminhos.trava):
            ancora, verificacao = ancorar(ledger, agora_local())
    except ExecucaoEmAndamento as e:
        print(f"{e}; tente de novo quando ela terminar.")
        return 3
    if not verificacao.ok:
        print(f"O ledger NÃO foi ancorado: {len(verificacao.erros)} problema(s) de integridade:")
        for erro in verificacao.erros:
            print(f"  - {erro}")
        return 1
    if ancora is None:
        print("Ledger vazio: nada a ancorar.")
        return 0
    texto = formatar_ancora(ancora["indice"], ancora["hash"])
    print(f"Âncora do ledger (bloco {ancora['indice']}, registrada em {ancora['timestamp'][:16].replace('T', ' ')}):")
    print(f"  {texto}")
    print("Guarde esta linha fora deste computador (e-mail, anotação, outro serviço). Para conferir depois:")
    print(f"  python monitor.py verificar-ledger --ancora {texto}")
    return 0


def cmd_buscar(args, config, caminhos: Caminhos) -> int:
    ledger = Ledger(caminhos.ledger)
    if not ledger.caminho.exists():
        print("Ledger vazio ou inexistente. Rode 'python monitor.py run' primeiro.")
        return 1
    verificacao = verificar_tudo(ledger)
    if not verificacao.ok:
        print(f"ATENÇÃO: o ledger tem {len(verificacao.erros)} problema(s) de integridade; "
              "rode 'python monitor.py verificar-ledger'.", file=sys.stderr)
    filtros = Filtros(termo=" ".join(args.termo), alvo=args.alvo, tipo=args.tipo, de=args.de, ate=args.ate)
    encontrados = buscar(ledger.blocos(), filtros)
    mostrados = encontrados if args.limite == 0 else encontrados[:args.limite]
    if args.json:
        print(json.dumps(mostrados, ensure_ascii=False, indent=2))
        return 0
    for bloco in mostrados:
        print(formatar(bloco))
        print()
    if len(mostrados) < len(encontrados):
        print(f"Mostrando {len(mostrados)} de {len(encontrados)} resultados (use --limite 0 para ver todos).")
    else:
        print(f"{len(encontrados)} resultado(s).")
    return 0


def cmd_agendar(args, config, caminhos: Caminhos) -> int:
    horario = args.horario or config.horario
    if os.name != "nt":
        if args.status or args.remover:
            print("Fora do Windows o agendamento é feito pelo cron: use 'crontab -l' ou 'crontab -e'.")
            return 0
        print("Acrescente esta linha com 'crontab -e':")
        print(agendamento.linha_cron(Path(sys.executable), PASTA / "monitor.py", config.caminho.resolve(),
                                     horario, config.frequencia))
        return 0
    try:
        if args.remover:
            agendamento.remover()
            print(f"Tarefa '{agendamento.NOME_TAREFA}' removida do Agendador de Tarefas.")
            return 0
        if not args.status:
            if config.frequencia == "manual":
                print("frequencia: manual no alvos.yaml; nada foi agendado. "
                      "Use 'agendar --remover' para tirar um agendamento existente.")
                return 1
            xml = agendamento.xml_tarefa(agendamento.interpretador(), PASTA / "monitor.py",
                                         config.caminho.resolve(), horario, config.frequencia, date.today())
            agendamento.instalar(xml)
            quando = "toda segunda-feira" if config.frequencia == "semanal" else "todos os dias"
            print(f"Agendado: {quando} às {horario} (tarefa '{agendamento.NOME_TAREFA}' no Agendador de Tarefas).")
            print("Se o computador estiver desligado nesse horário, roda assim que possível depois.")
            print("Só roda com o usuário logado no Windows. Resultado em logs/monitor.log e relatorios/.")
        status = agendamento.status()
    except agendamento.ErroAgendamento as e:
        print(f"Erro no agendamento: {e}")
        return 1
    if status is None:
        print("Nenhuma execução automática instalada. Use 'python monitor.py agendar'.")
        return 1
    print(f"  estado:            {status.estado}")
    print(f"  última execução:   {status.ultima_execucao.replace('T', ' ') or '-'} "
          f"({agendamento.descrever_resultado(status.ultimo_resultado)})")
    print(f"  próxima execução:  {status.proxima_execucao.replace('T', ' ') or '-'}")
    return 0


def data_iso(texto: str) -> str:
    try:
        return date.fromisoformat(texto).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"data inválida: {texto!r} (use AAAA-MM-DD)")


def ancora_externa(texto: str) -> tuple[int, str]:
    try:
        return ler_externa(texto)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def horario_hhmm(texto: str) -> str:
    try:
        return validar_horario(texto)
    except ErroConfig as e:
        raise argparse.ArgumentTypeError(str(e))


def main(argv: list[str] | None = None) -> int:
    for fluxo in (sys.stdout, sys.stderr):  # acentos corretos também quando a saída é redirecionada
        if hasattr(fluxo, "reconfigure"):
            fluxo.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Robô de monitoramento de normas (ANAC).")
    parser.add_argument("--config", type=Path, default=PASTA / "alvos.yaml",
                        help="configurações globais (padrão: alvos.yaml ao lado deste script); "
                             "dados/, relatorios/ e logs/ ficam na mesma pasta")
    sub = parser.add_subparsers(dest="comando", required=True)
    p_run = sub.add_parser("run", help="roda os alvos ativos")
    p_run.add_argument("--alvo", help="roda só este alvo (id; veja 'list')")
    p_run.add_argument("--origem", choices=["cli", "agendamento"], default="cli",
                       help="como a execução aparece no histórico (a tarefa agendada usa 'agendamento')")
    p_run.set_defaults(funcao=cmd_run)
    p_importar = sub.add_parser("importar-yaml", help="carrega no banco os alvos de um YAML (carga inicial)")
    p_importar.add_argument("--arquivo", type=Path, help="YAML com a seção 'alvos' (padrão: alvos_iniciais.yaml)")
    p_importar.add_argument("--substituir", action="store_true", help="sobrescreve alvos que já existem no banco")
    p_importar.set_defaults(funcao=cmd_importar_yaml)
    p_exportar = sub.add_parser("exportar", help="gera a planilha Excel (mudanças, normas vigentes e execuções)")
    p_exportar.add_argument("--saida", type=Path, help="arquivo .xlsx (padrão: relatorios/monitor_normas_DATA.xlsx)")
    p_exportar.set_defaults(funcao=cmd_exportar)
    sub.add_parser("list", help="mostra os alvos e o último estado").set_defaults(funcao=cmd_list)
    p_verificar = sub.add_parser("verificar-ledger", help="confere a cadeia do ledger e as âncoras")
    p_verificar.add_argument("--ancora", type=ancora_externa, action="append", metavar="INDICE:HASH",
                             help="confere também uma âncora guardada fora deste computador (pode repetir)")
    p_verificar.set_defaults(funcao=cmd_verificar_ledger)
    sub.add_parser("ancora", help="ancora o ledger agora e mostra a âncora para guardar fora deste computador"
                   ).set_defaults(funcao=cmd_ancora)

    p_buscar = sub.add_parser("buscar", help="procura normas no ledger (mais recentes primeiro)")
    p_buscar.add_argument("termo", nargs="*",
                          help="palavras procuradas na norma, ementa e palavras-chave; todas precisam aparecer "
                               "(ignora maiúsculas e acentos)")
    p_buscar.add_argument("--alvo", help="só este alvo (id do alvos.yaml)")
    p_buscar.add_argument("--tipo", type=str.upper, choices=[NOVO, ALTERADO, REMOVIDO, LINHA_BASE],
                          help="só este tipo de registro")
    p_buscar.add_argument("--de", type=data_iso, help="publicadas a partir de AAAA-MM-DD")
    p_buscar.add_argument("--ate", type=data_iso, help="publicadas até AAAA-MM-DD")
    p_buscar.add_argument("--limite", type=int, default=50, help="máximo de resultados (0 = todos; padrão 50)")
    p_buscar.add_argument("--json", action="store_true", help="saída em JSON")
    p_buscar.set_defaults(funcao=cmd_buscar)

    p_agendar = sub.add_parser("agendar", help="instala a execução automática (frequencia/horario do alvos.yaml)")
    acao = p_agendar.add_mutually_exclusive_group()
    acao.add_argument("--status", action="store_true", help="só mostra a última e a próxima execução")
    acao.add_argument("--remover", action="store_true", help="remove a execução automática")
    p_agendar.add_argument("--horario", type=horario_hhmm, help="HH:MM; sobrescreve o horario do alvos.yaml")
    p_agendar.set_defaults(funcao=cmd_agendar)
    args = parser.parse_args(argv)

    caminhos = caminhos_padrao(args.config.resolve().parent)
    configurar_log(caminhos)
    if args.funcao is cmd_importar_yaml:
        return cmd_importar_yaml(args, caminhos)
    log = logging.getLogger("monitor")
    try:
        globais = carregar_globais(args.config)
        with RepositorioAlvos(caminhos.estado_db) as repo:
            definicoes = repo.listar()
        config = montar_config(globais, definicoes)
    except (ErroConfig, OSError) as e:
        log.error("configuração: %s", e)
        return 2
    if globais.alvos_yaml and not definicoes and args.funcao in (cmd_run, cmd_list):
        print("Os alvos agora ficam no banco de dados. Faça a carga inicial com:\n"
              f"  python monitor.py importar-yaml --arquivo {args.config}")
        return 2
    if globais.alvos_yaml and definicoes:
        log.warning("a seção 'alvos' de %s é ignorada: os alvos ficam no banco (edite pela web ou pela API)",
                    args.config.name)
    return args.funcao(args, config, caminhos)


if __name__ == "__main__":
    sys.exit(main())
