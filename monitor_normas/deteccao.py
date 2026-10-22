"""Comparação entre a coleta atual e o estado salvo."""

from dataclasses import dataclass, field

from .extracao import Item, calcular_hash

NOVO = "NOVO"
ALTERADO = "ALTERADO"
REMOVIDO = "REMOVIDO"
LINHA_BASE = "LINHA_BASE"


@dataclass
class Mudanca:
    tipo: str
    item: Item
    diferencas: dict[str, tuple[str, str]] = field(default_factory=dict)


def item_de_dados(dados: dict) -> Item:
    return Item(**dados)


def comparar(atuais: list[Item], anteriores: dict[str, dict], origens_coletadas: set[str]) -> list[Mudanca]:
    """Classifica cada item como NOVO, ALTERADO ou REMOVIDO.

    anteriores: chave -> {"hash", "origem", "dados"} (itens vigentes no estado).
    Só é REMOVIDO o item cuja página de origem foi baixada nesta execução; assim,
    na virada do ano, os itens do ano que saiu da lista não somem do estado.
    """
    novos, alterados, removidos = [], [], []
    chaves_atuais = set()
    for item in atuais:
        chaves_atuais.add(item.chave)
        anterior = anteriores.get(item.chave)
        if anterior is None:
            novos.append(Mudanca(NOVO, item))
            continue
        # O hash anterior é recalculado com os campos monitorados de agora; assim, editar
        # colunas ou detectar_mudanca_em no YAML não faz todos os itens parecerem ALTERADOS.
        antes = anterior["dados"]["campos"]
        nomes = item.campos_monitorados or sorted(set(antes) | set(item.campos))
        if calcular_hash(antes, nomes) != item.hash:
            diferencas = {campo: (antes.get(campo, ""), item.campos.get(campo, ""))
                          for campo in nomes if antes.get(campo, "") != item.campos.get(campo, "")}
            alterados.append(Mudanca(ALTERADO, item, diferencas))
    for chave, anterior in anteriores.items():
        if chave not in chaves_atuais and anterior["origem"] in origens_coletadas:
            removidos.append(Mudanca(REMOVIDO, item_de_dados(anterior["dados"])))
    return novos + alterados + removidos
