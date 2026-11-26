import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { apiFalsa, pagina, renderizar } from '../../testes/renderizar.tsx'
import { rodadaEmAndamento, rodadaOk } from '../../testes/exemplos.ts'
import ExecucoesPage from './ExecucoesPage.tsx'

describe('ExecucoesPage', () => {
  it('lista rodadas com erros à vista e detalhe por alvo ao expandir', async () => {
    apiFalsa({ 'GET /execucoes': pagina([rodadaOk], 1, 25) })
    renderizar(<ExecucoesPage />)

    expect(await screen.findByText('#42')).toBeInTheDocument()
    expect(screen.getByText('agendada')).toBeInTheDocument()
    expect(screen.getByText('todos os ativos')).toBeInTheDocument()
    expect(screen.getByText('com erros')).toBeInTheDocument()
    expect(screen.getByText('1 / 2 / 0')).toBeInTheDocument()
    expect(screen.getByText('timeout')).toBeInTheDocument() // erro do alvo visível sem expandir
    expect(screen.getByText('1–1 de 1')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '2 alvo(s)' }))
    const detalhe = screen.getByRole('table', { name: 'Alvos da rodada 42' })
    expect(within(detalhe).getByText('anac-resolucoes')).toBeInTheDocument()
    expect(within(detalhe).getByText('2026-11-25')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Ocultar' }))
    expect(screen.queryByRole('table', { name: 'Alvos da rodada 42' })).not.toBeInTheDocument()
  })

  it('paginação pede o próximo deslocamento', async () => {
    const fetch = apiFalsa({ 'GET /execucoes': pagina([rodadaOk], 60, 25) })
    renderizar(<ExecucoesPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Próxima' }))
    expect(fetch).toHaveBeenLastCalledWith('/api/v1/execucoes?limite=25&deslocamento=25', expect.anything())
  })

  it('rodada em andamento mostra "rodando…"', async () => {
    apiFalsa({ 'GET /execucoes': pagina([rodadaEmAndamento], 1, 25) })
    renderizar(<ExecucoesPage />)
    expect(await screen.findByText('rodando…')).toBeInTheDocument()
    expect(screen.getByText('em andamento')).toBeInTheDocument()
  })

  it('sem execuções', async () => {
    apiFalsa({ 'GET /execucoes': pagina([], 0, 25) })
    renderizar(<ExecucoesPage />)
    expect(await screen.findByText('Nenhuma execução ainda.')).toBeInTheDocument()
  })
})
