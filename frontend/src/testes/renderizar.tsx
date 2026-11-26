// Ajudantes para testar telas: monta os provedores (tema, React Query, avisos, rotas) e simula a API.
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from '@mui/material/styles'
import { render } from '@testing-library/react'
import { vi } from 'vitest'

import { ProvedorAvisos } from '../componentes/Avisos.tsx'
import { tema } from '../tema.ts'

export type Resposta = { status?: number; corpo?: unknown }
/** Chave: "MÉTODO /caminho" (sem /api/v1) ou "MÉTODO /caminho?query" (mais específica).
 *  Valor: o corpo JSON da resposta (status 200) ou uma função que devolve {status, corpo}. */
export type RotasFalsas = Record<string, unknown | ((url: URL, corpo: unknown) => Resposta)>

export function apiFalsa(rotas: RotasFalsas) {
  const fetch = vi.fn(async (entrada: string, opcoes: RequestInit = {}) => {
    const url = new URL(entrada, 'http://teste')
    const caminho = url.pathname.replace(/^\/api\/v1/, '')
    const metodo = opcoes.method ?? 'GET'
    const corpo = opcoes.body ? JSON.parse(String(opcoes.body)) : undefined
    const rota = rotas[`${metodo} ${caminho}${url.search}`] ?? rotas[`${metodo} ${caminho}`]
    if (rota === undefined) return new Response(JSON.stringify({ detail: `sem rota falsa: ${metodo} ${caminho}` }), { status: 404 })
    const r: Resposta = typeof rota === 'function' ? rota(url, corpo) : { corpo: rota }
    return new Response(r.corpo === undefined ? null : JSON.stringify(r.corpo), { status: r.status ?? 200 })
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

export function renderizar(elemento: ReactElement, { rota = '/' }: { rota?: string } = {}) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <ThemeProvider theme={tema}>
      <QueryClientProvider client={cliente}>
        <ProvedorAvisos>
          <MemoryRouter initialEntries={[rota]}>{elemento}</MemoryRouter>
        </ProvedorAvisos>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

export const pagina = <T,>(itens: T[], total = itens.length, limite = 50, deslocamento = 0) =>
  ({ total, limite, deslocamento, itens })
