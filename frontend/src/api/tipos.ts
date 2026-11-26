// Formatos da API /api/v1 (espelham api/esquemas.py do servidor Python).

export type TipoMudanca = 'NOVO' | 'ALTERADO' | 'REMOVIDO' | 'LINHA_BASE'
export type StatusRodada = 'em_andamento' | 'ok' | 'com_erros' | 'falhou' | 'interrompida'
export type MetodoDeteccao = 'lista_itens' | 'hash_conteudo' | 'data_modificacao'
export type Prioridade = 'alta' | 'media' | 'baixa'

export interface Pagina<T> {
  total: number
  limite: number
  deslocamento: number
  itens: T[]
}

// ---------------------------------------------------------------- alvos

export interface Deteccao {
  metodo?: MetodoDeteccao
  chave_item?: string
  detectar_mudanca_em?: string[] | null
}

export interface Extracao {
  tabela?: 'primeira' | 'todas'
  colunas?: Record<string, string> | 'auto'
  regex_numero?: string | null
  marcar_status?: Record<string, string>
}

/** Corpo de POST /alvos e PUT /alvos/{id}. A API recusa campos desconhecidos. */
export interface AlvoEntrada {
  id: string
  ativo?: boolean
  site?: string
  categoria?: string
  prioridade?: Prioridade | null
  url: string
  anos?: ('atual' | 'anterior' | number)[]
  deteccao?: Deteccao
  extracao?: Extracao
  observacoes?: string
  timeout_segundos?: number | null
  tentativas?: number | null
  pausa_entre_requisicoes_segundos?: number | null
  user_agent?: string | null
  registrar_no_ledger?: boolean | null
}

export interface UltimaExecucao {
  inicio: string
  fim: string | null
  status: string
  total: number
  novos: number
  alterados: number
  removidos: number
  modificacao_pagina?: string | null
  erro?: string | null
}

export interface Alvo {
  id: string
  ativo: boolean
  site: string
  categoria: string
  prioridade: string | null
  url: string
  metodo: string
  valido: boolean
  erro_config: string | null
  itens_vigentes: number
  ultima_execucao: UltimaExecucao | null
  /** Definição completa, no formato de AlvoEntrada (pode trazer campos antigos). */
  definicao: Partial<AlvoEntrada> & Record<string, unknown>
}

// ---------------------------------------------------------------- execuções

export interface ExecucaoDisparada {
  rodada_id: number
  status: StatusRodada
  url: string
}

export interface ExecucaoAlvo {
  id: number
  alvo: string
  inicio: string
  fim: string | null
  status: string
  total: number
  novos: number
  alterados: number
  removidos: number
  modificacao_pagina?: string | null
  erro?: string | null
}

export interface Rodada {
  id: number
  origem: string
  alvo: string | null
  inicio: string
  fim: string | null
  status: StatusRodada
  erro?: string | null
  total: number
  novos: number
  alterados: number
  removidos: number
  erros: number
  execucoes: ExecucaoAlvo[]
}

// ---------------------------------------------------------------- ledger e configuração

export interface Bloco {
  indice: number
  timestamp: string
  alvo: string
  tipo_mudanca: TipoMudanca
  norma: string
  link?: string | null
  data_publicacao?: string | null
  ementa?: string | null
  palavras_chave: string[]
  hash_anterior: string
  hash: string
}

export interface Verificacao {
  ok: boolean
  blocos: number
  ancoras_conferidas: number
  ancora_atual: string | null
  erros: string[]
  avisos: string[]
}

export interface Configuracao {
  regex: Record<string, string>
  palavras_chave: string[]
  frequencia: string
  horario: string
}

/** Filtros de GET /mudancas e GET /exportar/excel (strings vazias são ignoradas). */
export interface FiltrosMudancas {
  palavra?: string
  alvo?: string
  tipo?: TipoMudanca | ''
  de?: string
  ate?: string
  registrado_de?: string
  registrado_ate?: string
  incluir_linha_base?: boolean
}
