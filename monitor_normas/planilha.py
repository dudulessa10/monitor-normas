"""Planilha .xlsx com três abas: Mudanças, Normas vigentes e Execuções."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

CABECALHO = Font(bold=True, color="FFFFFF")
FUNDO = PatternFill("solid", fgColor="1F4E79")
LINK = Font(color="0563C1", underline="single")


def _aba(wb: Workbook, titulo: str, colunas: list[tuple[str, int]], linhas: list[list], col_link: int | None = None):
    ws = wb.create_sheet(titulo)
    ws.append([nome for nome, _ in colunas])
    for celula in ws[1]:
        celula.font, celula.fill = CABECALHO, FUNDO
    for linha in linhas:
        ws.append([_texto(v) for v in linha])
        if col_link is not None:
            celula = ws.cell(row=ws.max_row, column=col_link + 1)
            if str(celula.value or "").startswith(("http://", "https://")):
                celula.hyperlink, celula.font = celula.value, LINK
    for i, (_, largura) in enumerate(colunas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = largura
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    return ws


def _texto(valor):
    if isinstance(valor, list):
        return ", ".join(str(v) for v in valor)
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@"):
        return "'" + valor  # o conteúdo vem de sites: nunca vira fórmula no Excel
    return valor


def gerar(mudancas: list[dict], normas: list[dict], rodadas: list[dict]) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    _aba(wb, "Mudanças",
         [("Registrado em", 20), ("Tipo", 12), ("Alvo", 26), ("Norma", 36), ("Publicação", 12),
          ("Ementa", 80), ("Palavras-chave", 30), ("Link", 50), ("Bloco", 8)],
         [[b.get("timestamp", "")[:19].replace("T", " "), b.get("tipo_mudanca"), b.get("alvo"), b.get("norma"),
           b.get("data_publicacao"), b.get("ementa"), b.get("palavras_chave") or [], b.get("link"), b.get("indice")]
          for b in mudancas], col_link=7)
    _aba(wb, "Normas vigentes",
         [("Alvo", 26), ("Norma", 36), ("Tipo", 14), ("Número", 12), ("Publicação", 12), ("Ementa", 80),
          ("Status", 14), ("Vista pela 1ª vez", 20), ("Vista por último", 20), ("Link", 50)],
         [[n["alvo"], n["chave"], n["tipo"], n["numero"], n["data_publicacao"], n["ementa"], n["status"],
           n["primeira_vez"][:19].replace("T", " "), n["ultima_vez"][:19].replace("T", " "), n["link"]]
          for n in normas], col_link=9)
    _aba(wb, "Execuções",
         [("Rodada", 8), ("Origem", 12), ("Alvo", 26), ("Início", 20), ("Fim", 20), ("Status", 12),
          ("Itens", 8), ("Novos", 8), ("Alterados", 10), ("Removidos", 10), ("Erro", 80)],
         [[r["id"], r["origem"], e["alvo"], e["inicio"][:19].replace("T", " "), (e["fim"] or "")[:19].replace("T", " "),
           e["status"], e["total"], e["novos"], e["alterados"], e["removidos"], e["erro"] or ""]
          for r in rodadas for e in r["execucoes"]])
    saida = BytesIO()
    wb.save(saida)
    return saida.getvalue()
