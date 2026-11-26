// Conversão entre o formulário de alvo (campos de texto) e o corpo aceito pela API (AlvoEntrada).
// Mesmas regras da versão original (web/js/alvos.js).
import type { Alvo, AlvoEntrada, MetodoDeteccao, Prioridade } from '../../api/tipos.ts'

/** Campos aceitos pela API. Os demais da definição (ex.: de uma importação antiga) são descartados ao salvar. */
export const PERMITIDOS = ['id', 'ativo', 'site', 'categoria', 'prioridade', 'url', 'anos', 'deteccao', 'extracao',
  'observacoes', 'timeout_segundos', 'tentativas', 'pausa_entre_requisicoes_segundos', 'user_agent',
  'registrar_no_ledger'] as const

export const PADRAO_ID = /^[a-z0-9][a-z0-9_-]*$/

export interface ValoresFormulario {
  id: string
  categoria: string
  site: string
  prioridade: Prioridade | ''
  url: string
  anos: string
  ativo: boolean
  metodo: MetodoDeteccao
  chave_item: string
  detectar_mudanca_em: string
  tabela: 'primeira' | 'todas'
  regex_numero: string
  colunas: string
  marcar_status: string
  observacoes: string
}

/** "Norma: norma\nPublicação: publicacao" -> {Norma: "norma", Publicação: "publicacao"} (linhas sem ":" são ignoradas). */
export function linhasParaMapa(texto: string): Record<string, string> {
  const mapa: Record<string, string> = {}
  for (const linha of texto.split('\n')) {
    const i = linha.indexOf(':')
    if (i > 0) mapa[linha.slice(0, i).trim()] = linha.slice(i + 1).trim()
  }
  return mapa
}

export const mapaParaLinhas = (mapa: Record<string, string> | null | undefined) =>
  Object.entries(mapa ?? {}).map(([k, v]) => `${k}: ${v}`).join('\n')

/** "a, b,, c" -> ["a", "b", "c"] */
export const lista = (texto: string) => texto.split(',').map((s) => s.trim()).filter(Boolean)

export function valoresIniciais(alvo: Alvo | null): ValoresFormulario {
  const d = alvo?.definicao ?? { ativo: false, anos: ['atual'], deteccao: {}, extracao: {} }
  const det = d.deteccao ?? {}
  const ext = d.extracao ?? {}
  return {
    id: d.id ?? '',
    categoria: d.categoria ?? '',
    site: d.site ?? '',
    prioridade: (d.prioridade ?? '') as Prioridade | '',
    url: d.url ?? '',
    anos: (d.anos ?? ['atual']).join(', '),
    ativo: Boolean(d.ativo),
    metodo: det.metodo ?? 'lista_itens',
    chave_item: det.chave_item ?? 'norma',
    detectar_mudanca_em: (det.detectar_mudanca_em ?? []).join(', '),
    tabela: ext.tabela ?? 'primeira',
    regex_numero: ext.regex_numero ?? '',
    colunas: typeof ext.colunas === 'object' && ext.colunas ? mapaParaLinhas(ext.colunas) : '',
    marcar_status: mapaParaLinhas(ext.marcar_status),
    observacoes: d.observacoes ?? '',
  }
}

/** Monta o corpo do POST/PUT preservando os campos permitidos da definição que o formulário não mostra. */
export function corpoDoFormulario(v: ValoresFormulario, alvo: Alvo | null): AlvoEntrada {
  const base = Object.fromEntries(
    Object.entries(alvo?.definicao ?? {}).filter(([k]) => (PERMITIDOS as readonly string[]).includes(k)),
  ) as Partial<AlvoEntrada>
  const colunas = linhasParaMapa(v.colunas)
  const detectar = lista(v.detectar_mudanca_em)
  const anos = lista(v.anos).map((a) => (/^\d+$/.test(a) ? Number(a) : a)) as AlvoEntrada['anos'] & unknown[]

  const corpo: AlvoEntrada = {
    ...base,
    id: v.id.trim(),
    ativo: v.ativo,
    categoria: v.categoria.trim(),
    site: v.site.trim(),
    url: v.url.trim(),
    anos: anos.length ? anos : ['atual'],
    observacoes: v.observacoes.trim(),
    deteccao: {
      metodo: v.metodo,
      chave_item: v.chave_item.trim() || 'norma',
      ...(detectar.length ? { detectar_mudanca_em: detectar } : {}),
    },
    extracao: {
      tabela: v.tabela,
      colunas: Object.keys(colunas).length ? colunas : 'auto',
      ...(v.regex_numero ? { regex_numero: v.regex_numero } : {}),
      marcar_status: linhasParaMapa(v.marcar_status),
    },
  }
  if (v.prioridade) corpo.prioridade = v.prioridade
  else delete corpo.prioridade
  return corpo
}
