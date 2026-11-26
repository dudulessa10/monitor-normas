import { describe, expect, it } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { apiFalsa, renderizar } from '../../testes/renderizar.tsx'
import { alvoComErro, alvoInvalido, alvoResolucoes } from '../../testes/exemplos.ts'
import AlvosPage from './AlvosPage.tsx'

const configuracao = { regex: { resolucao: 'x', rbac: 'y' }, palavras_chave: [], frequencia: 'diaria', horario: '06:00' }
const rotas = { 'GET /alvos': [alvoResolucoes, alvoComErro, alvoInvalido], 'GET /configuracao': configuracao }

const chamada = (fetch: ReturnType<typeof apiFalsa>, metodo: string) =>
  fetch.mock.calls.find(([, o]) => o?.method === metodo)

describe('AlvosPage', () => {
  it('tabela com status, erros e definição inválida', async () => {
    apiFalsa(rotas)
    renderizar(<AlvosPage />)
    const tabela = await screen.findByRole('table', { name: 'Alvos' })
    expect(within(tabela).getByText('Resoluções')).toBeInTheDocument()
    expect(within(tabela).getByText('+1 ~0 −0')).toBeInTheDocument()
    expect(within(tabela).getByText('timeout')).toBeInTheDocument()
    expect(within(tabela).getByText('Definição inválida: regex inexistente: xyz')).toBeInTheDocument()
    expect(within(tabela).getByText('nunca executado')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Rodar quebrado' })).toBeDisabled()
    expect(screen.getByRole('switch', { name: 'Ativar anac-resolucoes' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Ativar quebrado' })).not.toBeChecked()
  })

  it('sem alvos mostra como importar', async () => {
    apiFalsa({ ...rotas, 'GET /alvos': [] })
    renderizar(<AlvosPage />)
    expect(await screen.findByText(/Nenhum alvo cadastrado/)).toBeInTheDocument()
  })

  it('desativar chama a API e avisa', async () => {
    const fetch = apiFalsa({ ...rotas, 'POST /alvos/anac-resolucoes/desativar': { ...alvoResolucoes, ativo: false } })
    renderizar(<AlvosPage />)
    await userEvent.click(await screen.findByRole('switch', { name: 'Ativar anac-resolucoes' }))
    expect(await screen.findByText('Resoluções: desativado.')).toBeInTheDocument()
    expect(chamada(fetch, 'POST')?.[0]).toBe('/api/v1/alvos/anac-resolucoes/desativar')
  })

  it('ativar alvo inválido mostra o erro do servidor', async () => {
    apiFalsa({ ...rotas, 'POST /alvos/quebrado/ativar': () => ({ status: 422, corpo: { detail: 'definição inválida' } }) })
    renderizar(<AlvosPage />)
    await userEvent.click(await screen.findByRole('switch', { name: 'Ativar quebrado' }))
    expect(await screen.findByText('definição inválida')).toBeInTheDocument()
  })

  it('rodar um alvo', async () => {
    const fetch = apiFalsa({ ...rotas, 'POST /execucoes': () => ({ status: 202, corpo: { rodada_id: 50, status: 'em_andamento', url: '' } }) })
    renderizar(<AlvosPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Rodar anac-is' }))
    expect(await screen.findByText('Execução #50 iniciada para anac-is. Acompanhe em Execuções.')).toBeInTheDocument()
    expect(JSON.parse(String(chamada(fetch, 'POST')?.[1]?.body))).toEqual({ alvo: 'anac-is' })
  })

  it('excluir pede confirmação; cancelar não apaga', async () => {
    const fetch = apiFalsa({ ...rotas, 'DELETE /alvos/anac-is': () => ({ status: 204 }) })
    renderizar(<AlvosPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Excluir anac-is' }))
    const dialogo = await screen.findByRole('dialog', { name: 'Excluir alvo' })
    expect(within(dialogo).getByText('Excluir o alvo "anac-is"? O histórico e o ledger dele são mantidos.')).toBeInTheDocument()
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(chamada(fetch, 'DELETE')).toBeUndefined()

    await userEvent.click(screen.getByRole('button', { name: 'Excluir anac-is' }))
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Excluir alvo' })).getByRole('button', { name: 'Excluir' }))
    expect(await screen.findByText('Alvo anac-is excluído.')).toBeInTheDocument()
    expect(chamada(fetch, 'DELETE')?.[0]).toBe('/api/v1/alvos/anac-is')
  })

  it('cadastrar novo alvo envia o corpo convertido', async () => {
    const fetch = apiFalsa({ ...rotas, 'POST /alvos': () => ({ status: 201, corpo: alvoResolucoes }) })
    renderizar(<AlvosPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Novo alvo' }))
    const form = await screen.findByRole('form', { name: 'Novo alvo' })

    const cadastrar = within(form).getByRole('button', { name: 'Cadastrar' })
    expect(cadastrar).toBeDisabled() // id e url obrigatórios
    await userEvent.type(within(form).getByLabelText(/Identificador/), 'Errado')
    expect(within(form).getByText('use só minúsculas, números, - e _')).toBeInTheDocument()
    await userEvent.clear(within(form).getByLabelText(/Identificador/))
    await userEvent.type(within(form).getByLabelText(/Identificador/), 'anac-novo')
    await userEvent.type(within(form).getByLabelText(/^URL/), 'https://www.anac.gov.br/novo/{{ano}')
    await userEvent.type(within(form).getByLabelText(/^Colunas/), 'Norma: norma')
    await userEvent.click(within(form).getByLabelText('Ativo (roda na execução diária)'))
    await userEvent.click(within(form).getByRole('combobox', { name: 'Regex do número' }))
    await userEvent.click(await screen.findByRole('option', { name: 'rbac' }))
    await userEvent.click(cadastrar)

    expect(await screen.findByText('Alvo cadastrado.')).toBeInTheDocument()
    expect(JSON.parse(String(chamada(fetch, 'POST')?.[1]?.body))).toEqual({
      id: 'anac-novo', ativo: true, categoria: '', site: '', url: 'https://www.anac.gov.br/novo/{ano}', anos: ['atual'],
      observacoes: '', deteccao: { metodo: 'lista_itens', chave_item: 'norma' },
      extracao: { tabela: 'primeira', colunas: { Norma: 'norma' }, regex_numero: 'rbac', marcar_status: {} },
    })
    await waitFor(() => expect(screen.queryByRole('form', { name: 'Novo alvo' })).not.toBeInTheDocument())
  }, 20000)

  it('editar: id fica travado e erro de validação do servidor aparece no formulário', async () => {
    const fetch = apiFalsa({
      ...rotas,
      'PUT /alvos/anac-resolucoes': () => ({ status: 422, corpo: { detail: [{ loc: ['body', 'url'], msg: 'Value error, a url deve começar com http:// ou https://' }] } }),
    })
    renderizar(<AlvosPage />)
    await userEvent.click(await screen.findByRole('button', { name: 'Editar anac-resolucoes' }))
    const form = await screen.findByRole('form', { name: 'Editar anac-resolucoes' })
    expect(within(form).getByLabelText(/Identificador/)).toHaveAttribute('readonly')
    expect(within(form).getByLabelText(/^Colunas/)).toHaveValue('Norma: norma\nPublicação: publicacao')

    await userEvent.click(within(form).getByRole('button', { name: 'Salvar' }))
    expect(await within(form).findByText('url: a url deve começar com http:// ou https://')).toBeInTheDocument()
    expect(chamada(fetch, 'PUT')?.[0]).toBe('/api/v1/alvos/anac-resolucoes')
    expect(screen.getByRole('form', { name: 'Editar anac-resolucoes' })).toBeInTheDocument() // continua aberto
  })
})
