// Dados de exemplo no formato da API, usados pelos testes de tela.
import type { Alvo, Bloco, Rodada, Verificacao } from '../api/tipos.ts'

export const alvoResolucoes: Alvo = {
  id: 'anac-resolucoes', ativo: true, site: 'ANAC', categoria: 'Resoluções', prioridade: 'alta',
  url: 'https://www.anac.gov.br/resolucoes/{ano}', metodo: 'lista_itens', valido: true, erro_config: null,
  itens_vigentes: 29,
  ultima_execucao: { inicio: '2026-11-26T06:00:00-03:00', fim: '2026-11-26T06:00:10-03:00', status: 'ok', total: 29, novos: 1, alterados: 0, removidos: 0 },
  definicao: {
    id: 'anac-resolucoes', ativo: true, site: 'ANAC', categoria: 'Resoluções', prioridade: 'alta',
    url: 'https://www.anac.gov.br/resolucoes/{ano}', anos: ['atual', 'anterior'],
    deteccao: { metodo: 'lista_itens', chave_item: 'norma' },
    extracao: { tabela: 'primeira', regex_numero: 'resolucao', colunas: { Norma: 'norma', 'Publicação': 'publicacao' }, marcar_status: { revogada: 'revogada' } },
    observacoes: 'principal',
    campo_antigo_da_importacao: 'descartar',
  },
}

export const alvoComErro: Alvo = {
  ...alvoResolucoes, id: 'anac-is', categoria: 'IS', ativo: true, valido: true, itens_vigentes: 0,
  ultima_execucao: { inicio: '2026-11-26T06:00:00-03:00', fim: '2026-11-26T06:00:05-03:00', status: 'erro', total: 0, novos: 0, alterados: 0, removidos: 0, erro: 'timeout' },
  definicao: { id: 'anac-is', url: 'https://www.anac.gov.br/is' },
}

export const alvoInvalido: Alvo = {
  ...alvoResolucoes, id: 'quebrado', categoria: '', ativo: false, valido: false, erro_config: 'regex inexistente: xyz',
  itens_vigentes: 0, ultima_execucao: null, definicao: { id: 'quebrado', url: 'https://exemplo.com' },
}

export const rodadaOk: Rodada = {
  id: 42, origem: 'agendamento', alvo: null, inicio: '2026-11-26T06:00:00-03:00', fim: '2026-11-26T06:01:05-03:00',
  status: 'com_erros', erro: null, total: 29, novos: 1, alterados: 2, removidos: 0, erros: 1,
  execucoes: [
    { id: 1, alvo: 'anac-resolucoes', inicio: '2026-11-26T06:00:00-03:00', fim: '2026-11-26T06:00:10-03:00', status: 'ok', total: 29, novos: 1, alterados: 2, removidos: 0, modificacao_pagina: '2026-11-25' },
    { id: 2, alvo: 'anac-is', inicio: '2026-11-26T06:00:10-03:00', fim: '2026-11-26T06:00:15-03:00', status: 'erro', total: 0, novos: 0, alterados: 0, removidos: 0, erro: 'timeout' },
  ],
}

export const rodadaEmAndamento: Rodada = {
  ...rodadaOk, id: 43, origem: 'web', status: 'em_andamento', fim: null, erros: 0, execucoes: [],
}

export const bloco: Bloco = {
  indice: 1970, timestamp: '2026-11-26T06:00:09-03:00', alvo: 'anac-resolucoes', tipo_mudanca: 'NOVO',
  norma: 'RESOLUÇÃO Nº 817', link: 'https://www.anac.gov.br/r817.pdf', data_publicacao: '2026-11-25',
  ementa: 'Dispõe sobre tarifas aeroportuárias.', palavras_chave: ['RESOLUÇÃO', '817', 'tarifa'],
  hash_anterior: 'a', hash: 'b',
}

export const verificacaoOk: Verificacao = {
  ok: true, blocos: 1970, ancoras_conferidas: 24, ancora_atual: '1969:70b1bc036c67aa', erros: [], avisos: [],
}
