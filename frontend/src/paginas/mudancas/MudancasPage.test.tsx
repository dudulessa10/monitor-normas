import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { apiFalsa, pagina, renderizar } from '../../testes/renderizar.tsx'
import { alvoComErro, alvoResolucoes, bloco } from '../../testes/exemplos.ts'
import MudancasPage from './MudancasPage.tsx'

const ultimaUrlMudancas = (fetch: ReturnType<typeof apiFalsa>) =>
  fetch.mock.calls.map(([url]) => String(url)).filter((u) => u.startsWith('/api/v1/mudancas')).at(-1)

describe('MudancasPage', () => {
  it('lista as mudanças com link, palavras-chave e Excel', async () => {
    apiFalsa({ 'GET /alvos': [alvoResolucoes], 'GET /mudancas': pagina([bloco], 1) })
    renderizar(<MudancasPage />, { rota: '/mudancas' })

    const tabela = await screen.findByRole('table', { name: 'Mudanças' })
    expect(within(tabela).getByRole('link', { name: 'RESOLUÇÃO Nº 817' })).toHaveAttribute('href', 'https://www.anac.gov.br/r817.pdf')
    expect(within(tabela).getByText('tarifa')).toBeInTheDocument()
    expect(within(tabela).getByText('25/11/2026')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Baixar Excel' })).toHaveAttribute('href', '/api/v1/exportar/excel')
  })

  it('link com javascript: não vira link', async () => {
    apiFalsa({ 'GET /alvos': [], 'GET /mudancas': pagina([{ ...bloco, link: 'javascript:alert(1)' }], 1) })
    renderizar(<MudancasPage />, { rota: '/mudancas' })
    expect(await screen.findByText('RESOLUÇÃO Nº 817')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'RESOLUÇÃO Nº 817' })).not.toBeInTheDocument()
  })

  it('filtros do endereço já vêm preenchidos e vão para a API e para o Excel', async () => {
    const fetch = apiFalsa({ 'GET /alvos': [alvoResolucoes, alvoComErro], 'GET /mudancas': pagina([bloco], 1) })
    renderizar(<MudancasPage />, { rota: '/mudancas?registrado_de=2026-11-19&tipo=NOVO' })

    await screen.findByRole('table', { name: 'Mudanças' })
    expect(ultimaUrlMudancas(fetch)).toBe('/api/v1/mudancas?tipo=NOVO&registrado_de=2026-11-19&limite=50&deslocamento=0')
    expect(screen.getByLabelText('Detectadas de')).toHaveValue('2026-11-19')
    expect(screen.getByRole('link', { name: 'Baixar Excel' }))
      .toHaveAttribute('href', '/api/v1/exportar/excel?tipo=NOVO&registrado_de=2026-11-19')
  })

  it('Filtrar envia palavra, alvo e linha de base; Limpar zera tudo', async () => {
    const fetch = apiFalsa({ 'GET /alvos': [alvoResolucoes, alvoComErro], 'GET /mudancas': pagina([bloco], 1) })
    renderizar(<MudancasPage />, { rota: '/mudancas' })
    await screen.findByRole('table', { name: 'Mudanças' })

    await userEvent.type(screen.getByLabelText('Palavra-chave'), '  aeródromo ')
    await userEvent.click(screen.getByRole('combobox', { name: 'Alvo' }))
    await userEvent.click(await screen.findByRole('option', { name: 'IS' }))
    await userEvent.click(screen.getByLabelText('Incluir linha de base'))
    await userEvent.click(screen.getByRole('button', { name: 'Filtrar' }))

    await waitFor(() => expect(ultimaUrlMudancas(fetch))
      .toBe('/api/v1/mudancas?palavra=aer%C3%B3dromo&alvo=anac-is&incluir_linha_base=true&limite=50&deslocamento=0'))

    await userEvent.click(screen.getByRole('button', { name: 'Limpar' }))
    await waitFor(() => expect(ultimaUrlMudancas(fetch)).toBe('/api/v1/mudancas?limite=50&deslocamento=0'))
    expect(screen.getByLabelText('Palavra-chave')).toHaveValue('')
  })

  it('paginação de 50 em 50', async () => {
    const fetch = apiFalsa({ 'GET /alvos': [], 'GET /mudancas': pagina([bloco], 120) })
    renderizar(<MudancasPage />, { rota: '/mudancas' })
    await userEvent.click(await screen.findByRole('button', { name: 'Próxima' }))
    await waitFor(() => expect(ultimaUrlMudancas(fetch)).toBe('/api/v1/mudancas?limite=50&deslocamento=50'))
  })

  it('sem resultados', async () => {
    apiFalsa({ 'GET /alvos': [], 'GET /mudancas': pagina([], 0) })
    renderizar(<MudancasPage />, { rota: '/mudancas' })
    expect(await screen.findByText('Nenhuma mudança encontrada com esses filtros.')).toBeInTheDocument()
  })
})
