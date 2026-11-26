import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ErroApi, mensagemDeErro, query } from './cliente.ts'

afterEach(() => vi.unstubAllGlobals())

const resposta = (status: number, corpo?: unknown) =>
  new Response(corpo === undefined ? null : JSON.stringify(corpo), { status, headers: { 'Content-Type': 'application/json' } })

describe('query', () => {
  it('ignora vazios, nulos e false', () => {
    expect(query({ a: 1, b: '', c: null, d: false, e: undefined, f: true, g: 'x y' })).toBe('?a=1&f=true&g=x+y')
    expect(query({})).toBe('')
  })
})

describe('mensagemDeErro', () => {
  it('detail em texto', () => {
    expect(mensagemDeErro({ detail: 'alvo não existe' }, 404)).toBe('alvo não existe')
  })

  it('erros de validação do FastAPI viram "campo: mensagem"', () => {
    const dados = { detail: [
      { loc: ['body', 'url'], msg: 'Value error, a url deve começar com http:// ou https://' },
      { loc: ['body', 'deteccao', 'metodo'], msg: 'valor inválido' },
    ] }
    expect(mensagemDeErro(dados, 422)).toBe('url: a url deve começar com http:// ou https://; deteccao.metodo: valor inválido')
  })

  it('sem corpo', () => {
    expect(mensagemDeErro(null, 502)).toBe('erro HTTP 502')
  })
})

describe('api', () => {
  it('GET devolve o JSON', async () => {
    const fetch = vi.fn().mockResolvedValue(resposta(200, [{ id: 'a' }]))
    vi.stubGlobal('fetch', fetch)
    await expect(api('/alvos')).resolves.toEqual([{ id: 'a' }])
    expect(fetch).toHaveBeenCalledWith('/api/v1/alvos', { method: 'GET', headers: {} })
  })

  it('POST envia JSON e 204 devolve null', async () => {
    const fetch = vi.fn().mockResolvedValue(resposta(204))
    vi.stubGlobal('fetch', fetch)
    await expect(api('/x', { metodo: 'POST', corpo: { alvo: null } })).resolves.toBeNull()
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: 'POST', body: '{"alvo":null}' })
  })

  it('erro HTTP vira ErroApi com status e mensagem', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(resposta(409, { detail: 'outra execução em andamento' })))
    const erro = await api('/execucoes', { metodo: 'POST' }).catch((e) => e)
    expect(erro).toBeInstanceOf(ErroApi)
    expect(erro).toMatchObject({ status: 409, message: 'outra execução em andamento' })
  })

  it('servidor fora do ar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api('/alvos')).rejects.toMatchObject({ status: 0, message: 'não foi possível falar com o servidor' })
  })
})
