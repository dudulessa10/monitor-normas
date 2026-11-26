import { describe, expect, it } from 'vitest'

import { data, dataHora, duracao, hojeMenos, plural } from './formatacao.ts'
import { urlSegura } from './url.ts'

describe('formatação', () => {
  it('data: AAAA-MM-DD vira DD/MM/AAAA', () => {
    expect(data('2026-11-26')).toBe('26/11/2026')
    expect(data('2026-11-26T10:00:00-03:00')).toBe('26/11/2026')
    expect(data(null)).toBe('—')
    expect(data('ontem')).toBe('—')
  })

  it('dataHora: vazio vira traço e texto inválido é mantido', () => {
    expect(dataHora(undefined)).toBe('—')
    expect(dataHora('sem data')).toBe('sem data')
    expect(dataHora('2026-11-26T19:15:00-03:00')).toMatch(/\d{2}\/\d{2}\/\d{4}/)
  })

  it('duracao: segundos e minutos', () => {
    expect(duracao('2026-01-01T10:00:00Z', '2026-01-01T10:00:42Z')).toBe('42 s')
    expect(duracao('2026-01-01T10:00:00Z', '2026-01-01T10:03:05Z')).toBe('3 min 5 s')
    expect(duracao('2026-01-01T10:00:00Z', null)).toBe('—')
  })

  it('hojeMenos: subtrai dias no fuso local', () => {
    expect(hojeMenos(7, new Date(2026, 10, 26, 23, 30))).toBe('2026-11-19')
    expect(hojeMenos(1, new Date(2026, 0, 1, 0, 10))).toBe('2025-12-31')
  })

  it('plural', () => {
    expect(plural(1, 'item')).toBe('1 item')
    expect(plural(3, 'item', 'itens')).toBe('3 itens')
  })
})

describe('urlSegura', () => {
  it('aceita só http e https', () => {
    expect(urlSegura('https://www.anac.gov.br/x.pdf')).toBe('https://www.anac.gov.br/x.pdf')
    expect(urlSegura('HTTP://exemplo.com')).toBe('HTTP://exemplo.com')
    expect(urlSegura('javascript:alert(1)')).toBeNull()
    expect(urlSegura('data:text/html,oi')).toBeNull()
    expect(urlSegura('/relativo')).toBeNull()
    expect(urlSegura(null)).toBeNull()
  })
})
