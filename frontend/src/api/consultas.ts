// Hooks do React Query: cada tela pede os dados por aqui (cache, carregamento, erro e recarga).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, query } from './cliente.ts'
import type {
  Alvo, AlvoEntrada, Bloco, Configuracao, ExecucaoDisparada, FiltrosMudancas, Pagina, Rodada, Verificacao,
} from './tipos.ts'

/** Intervalo de atualização enquanto há rodada em andamento (igual à versão original). */
export const ATUALIZAR_A_CADA_MS = 3000

const emAndamento = (pagina?: Pagina<Rodada>) => Boolean(pagina?.itens.some((r) => r.status === 'em_andamento'))

export const chaves = {
  alvos: ['alvos'] as const,
  configuracao: ['configuracao'] as const,
  execucoes: (limite: number, deslocamento: number) => ['execucoes', limite, deslocamento] as const,
  verificacao: ['ledger', 'verificar'] as const,
  mudancas: (filtros: FiltrosMudancas, limite: number, deslocamento: number) =>
    ['mudancas', filtros, limite, deslocamento] as const,
}

// ---------------------------------------------------------------- leituras

export function useAlvos() {
  return useQuery({ queryKey: chaves.alvos, queryFn: () => api<Alvo[]>('/alvos') })
}

export function useConfiguracao() {
  return useQuery({ queryKey: chaves.configuracao, queryFn: () => api<Configuracao>('/configuracao'), staleTime: Infinity })
}

/** Histórico de rodadas; recarrega sozinho a cada 3 s enquanto alguma estiver em andamento. */
export function useExecucoes(limite: number, deslocamento = 0) {
  return useQuery({
    queryKey: chaves.execucoes(limite, deslocamento),
    queryFn: () => api<Pagina<Rodada>>(`/execucoes${query({ limite, deslocamento })}`),
    refetchInterval: (q) => (emAndamento(q.state.data) ? ATUALIZAR_A_CADA_MS : false),
  })
}

export function useVerificacaoLedger() {
  return useQuery({ queryKey: chaves.verificacao, queryFn: () => api<Verificacao>('/ledger/verificar') })
}

export function useMudancas(filtros: FiltrosMudancas, limite: number, deslocamento = 0) {
  return useQuery({
    queryKey: chaves.mudancas(filtros, limite, deslocamento),
    queryFn: () => api<Pagina<Bloco>>(`/mudancas${query({ ...filtros, limite, deslocamento })}`),
    placeholderData: (anterior) => anterior, // mantém a tabela na tela enquanto troca de página
  })
}

// ---------------------------------------------------------------- ações

/** Depois de qualquer ação, as telas recarregam o que pode ter mudado. */
function useRecarregar() {
  const cliente = useQueryClient()
  return () => cliente.invalidateQueries()
}

export function useRodar() {
  const recarregar = useRecarregar()
  return useMutation({
    mutationFn: (alvo: string | null) => api<ExecucaoDisparada>('/execucoes', { metodo: 'POST', corpo: { alvo } }),
    onSettled: recarregar,
  })
}

export function useAlternarAtivo() {
  const recarregar = useRecarregar()
  return useMutation({
    mutationFn: (alvo: Alvo) =>
      api<Alvo>(`/alvos/${encodeURIComponent(alvo.id)}/${alvo.ativo ? 'desativar' : 'ativar'}`, { metodo: 'POST' }),
    onSettled: recarregar,
  })
}

export function useExcluirAlvo() {
  const recarregar = useRecarregar()
  return useMutation({
    mutationFn: (id: string) => api<null>(`/alvos/${encodeURIComponent(id)}`, { metodo: 'DELETE' }),
    onSettled: recarregar,
  })
}

/** Cadastra (idOriginal vazio) ou substitui um alvo. */
export function useSalvarAlvo() {
  const recarregar = useRecarregar()
  return useMutation({
    mutationFn: ({ idOriginal, corpo }: { idOriginal: string | null; corpo: AlvoEntrada }) =>
      idOriginal
        ? api<Alvo>(`/alvos/${encodeURIComponent(idOriginal)}`, { metodo: 'PUT', corpo })
        : api<Alvo>('/alvos', { metodo: 'POST', corpo }),
    onSuccess: recarregar,
  })
}
