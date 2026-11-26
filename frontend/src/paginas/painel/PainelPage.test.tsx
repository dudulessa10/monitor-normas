import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { apiFalsa, pagina, renderizar } from '../../testes/renderizar.tsx'
import { alvoComErro, alvoInvalido, alvoResolucoes, bloco, rodadaOk, verificacaoOk } from '../../testes/exemplos.ts'
import PainelPage from './PainelPage.tsx'

const rotasBase = {
  'GET /execucoes': pagina([rodadaOk], 1, 1),
  'GET /alvos': [alvoResolucoes, alvoComErro, alvoInvalido],
  'GET /ledger/verificar': verificacaoOk,
  'GET /mudancas': pagina([bloco], 3, 10),
}

describe('PainelPage', () => {
  it('mostra os quatro cartões e as mudanças recentes', async () => {
    apiFalsa(rotasBase)
    renderizar(<PainelPage />)

    const ultima = await screen.findByRole('region', { name: 'Última execução' })
    expect(await within(ultima).findByText('com erros')).toBeInTheDocument()
    expect(within(ultima).getByText(/1 alvo\(s\) com erro/)).toBeInTheDocument()

    const ledger = screen.getByRole('region', { name: 'Integridade do ledger' })
    expect(await within(ledger).findByText('íntegro')).toBeInTheDocument()
    expect(within(ledger).getByText('1969:70b1bc036c67aa')).toBeInTheDocument()

    const alvos = screen.getByRole('region', { name: 'Alvos' })
    expect(await within(alvos).findByText('1 com erro na última execução')).toBeInTheDocument()
    expect(within(alvos).getByText('de 3 ativos')).toBeInTheDocument()

    const recentes = screen.getByRole('region', { name: 'Mudanças recentes' })
    const link = await within(recentes).findByRole('link', { name: 'RESOLUÇÃO Nº 817' })
    expect(link).toHaveAttribute('href', 'https://www.anac.gov.br/r817.pdf')
    expect(within(recentes).getByText('e mais 2…')).toBeInTheDocument()
    expect(within(recentes).getByRole('link', { name: 'ver todas' }).getAttribute('href')).toMatch(/^\/mudancas\?registrado_de=\d{4}-\d{2}-\d{2}$/)
  })

  it('"Rodar agora" dispara a execução do alvo escolhido e avisa', async () => {
    const fetch = apiFalsa({
      ...rotasBase,
      'POST /execucoes': () => ({ status: 202, corpo: { rodada_id: 44, status: 'em_andamento', url: '/api/v1/execucoes/44' } }),
    })
    renderizar(<PainelPage />)

    const cartao = await screen.findByRole('region', { name: 'Rodar agora' })
    await userEvent.click(within(cartao).getByRole('combobox', { name: 'Alvo' }))
    const opcoes = await screen.findAllByRole('option')
    expect(opcoes.map((o) => o.textContent)).toEqual(['Todos os alvos ativos', 'Resoluções', 'IS']) // inválido fica de fora
    await userEvent.click(screen.getByRole('option', { name: 'Resoluções' }))
    await userEvent.click(within(cartao).getByRole('button', { name: 'Rodar agora' }))

    expect(await screen.findByText('Execução #44 iniciada.')).toBeInTheDocument()
    const post = fetch.mock.calls.find(([, o]) => o?.method === 'POST')
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ alvo: 'anac-resolucoes' })
  })

  it('execução já em andamento: avisa o erro 409 do servidor', async () => {
    apiFalsa({ ...rotasBase, 'POST /execucoes': () => ({ status: 409, corpo: { detail: 'outra execução está em andamento' } }) })
    renderizar(<PainelPage />)
    const cartao = await screen.findByRole('region', { name: 'Rodar agora' })
    await userEvent.click(within(cartao).getByRole('button', { name: 'Rodar agora' }))
    expect(await screen.findByText('outra execução está em andamento')).toBeInTheDocument()
  })

  it('ledger com problema mostra os erros', async () => {
    apiFalsa({ ...rotasBase, 'GET /ledger/verificar': { ...verificacaoOk, ok: false, erros: ['bloco 12 alterado'], ancora_atual: null } })
    renderizar(<PainelPage />)
    expect(await screen.findByText('com problemas')).toBeInTheDocument()
    expect(screen.getByText('bloco 12 alterado')).toBeInTheDocument()
  })
})
