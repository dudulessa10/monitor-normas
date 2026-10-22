"""Relatório em Markdown (relatorios/relatorio_AAAA-MM-DD.md) e resumo para o terminal."""

from datetime import datetime
from pathlib import Path

from .deteccao import ALTERADO, NOVO, REMOVIDO, Mudanca
from .execucao import ResultadoAlvo
from .palavras_chave import palavras_do_item

ROTULOS = {"ok": "ok", "linha_base": "linha de base", "erro": "ERRO"}


def gerar(resultados: list[ResultadoAlvo], pasta: Path, quando: datetime, palavras_globais: list[str],
          ancora: str | None = None, alerta_ledger: str | None = None) -> Path:
    """Acrescenta a execução ao relatório do dia (várias execuções no mesmo dia ficam no mesmo arquivo)."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"relatorio_{quando:%Y-%m-%d}.md"
    novo_arquivo = not caminho.exists()
    with caminho.open("a", encoding="utf-8", newline="\n") as f:
        if novo_arquivo:
            f.write(f"# Relatório de monitoramento de normas — {quando:%d/%m/%Y}\n")
        f.write(secao_execucao(resultados, quando, palavras_globais, ancora, alerta_ledger))
    return caminho


def secao_execucao(resultados: list[ResultadoAlvo], quando: datetime, palavras_globais: list[str],
                   ancora: str | None = None, alerta_ledger: str | None = None) -> str:
    com_mudancas = [r for r in resultados if r.status == "ok" and r.mudancas]
    erros = [r for r in resultados if r.status == "erro"]
    bases = [r for r in resultados if r.status == "linha_base"]
    linhas = [
        "", f"## Execução das {quando:%H:%M:%S}", "",
        f"{len(resultados)} alvo(s) · {len(com_mudancas)} com mudanças · "
        f"{len(bases)} linha(s) de base · {len(erros)} com erro", "",
    ]
    for r in resultados:
        linhas.append(f"### {r.alvo.categoria or r.alvo.id} (`{r.alvo.id}`)")
        linhas.append("")
        if r.status == "erro":
            linhas += [f"**Erro:** {r.erro}", ""]
            continue
        info = f"- Itens na página: {r.total}"
        if r.modificacao_pagina:
            info += f" · última modificação da página: {r.modificacao_pagina}"
        linhas.append(info)
        if r.status == "linha_base":
            linhas += ["- Primeira execução: itens registrados como linha de base (não são novidades).", ""]
            continue
        if not r.mudancas:
            linhas += ["- Sem mudanças.", ""]
            continue
        linhas += [f"- Novos: {r.contar(NOVO)} · Alterados: {r.contar(ALTERADO)} · Removidos: {r.contar(REMOVIDO)}", ""]
        for m in r.mudancas:
            linhas += _bloco_mudanca(m, palavras_globais)
    if alerta_ledger:
        linhas += [f"**Atenção — ledger:** {alerta_ledger}", ""]
    if ancora:
        linhas += [f"Âncora do ledger: `{ancora}`  ",
                   "(guarde fora deste computador; confira com `python monitor.py verificar-ledger --ancora ...`)", ""]
    return "\n".join(linhas) + "\n"


def _bloco_mudanca(m: Mudanca, palavras_globais: list[str]) -> list[str]:
    item = m.item
    titulo = f"[{item.chave}]({item.link})" if item.link else item.chave
    linhas = [f"#### {m.tipo} — {titulo}", ""]
    if item.data_publicacao:
        linhas.append(f"- Publicação: {item.data_publicacao}")
    if item.ementa:
        linhas.append(f"- Ementa: {item.ementa}")
    if item.status:
        linhas.append(f"- Status: {', '.join(item.status)}")
    palavras = palavras_do_item(item, palavras_globais)
    if palavras:
        linhas.append(f"- Palavras-chave: {', '.join(palavras)}")
    for campo, (antes, depois) in m.diferencas.items():
        linhas.append(f"- `{campo}`: ~~{antes or '(vazio)'}~~ → {depois or '(vazio)'}")
    linhas.append("")
    return linhas


def resumo(resultados: list[ResultadoAlvo]) -> str:
    largura = max((len(r.alvo.id) for r in resultados), default=10)
    linhas = []
    for r in resultados:
        rotulo = ROTULOS[r.status]
        if r.status == "erro":
            detalhe = r.erro or ""
        elif r.status == "linha_base":
            detalhe = f"{r.total} itens registrados"
        else:
            detalhe = (f"{r.total} itens | novos {r.contar(NOVO)} | alterados {r.contar(ALTERADO)} | "
                       f"removidos {r.contar(REMOVIDO)}")
        linhas.append(f"  {r.alvo.id:<{largura}}  {rotulo:<13}  {detalhe}")
    erros = sum(1 for r in resultados if r.status == "erro")
    mudancas = sum(len(r.mudancas) for r in resultados if r.status == "ok")
    linhas.append(f"\n{len(resultados)} alvo(s), {mudancas} mudança(s), {erros} erro(s).")
    return "\n".join(linhas)
