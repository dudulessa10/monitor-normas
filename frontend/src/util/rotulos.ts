// Textos e cores dos selos de status, tipo de mudança e origem.

export type CorSelo = 'success' | 'warning' | 'error' | 'info' | 'default'

export const STATUS: Record<string, [CorSelo, string]> = {
  em_andamento: ['info', 'em andamento'],
  ok: ['success', 'ok'],
  linha_base: ['info', 'linha de base'],
  com_erros: ['warning', 'com erros'],
  erro: ['error', 'erro'],
  falhou: ['error', 'falhou'],
  interrompida: ['warning', 'interrompida'],
}

export const TIPOS: Record<string, [CorSelo, string]> = {
  NOVO: ['success', 'novo'],
  ALTERADO: ['warning', 'alterado'],
  REMOVIDO: ['error', 'removido'],
  LINHA_BASE: ['default', 'linha de base'],
}

export const ORIGENS: Record<string, string> = {
  cli: 'linha de comando',
  agendamento: 'agendada',
  web: 'web',
  historico: 'histórico',
}

export const rotuloOrigem = (origem: string) => ORIGENS[origem] ?? origem
