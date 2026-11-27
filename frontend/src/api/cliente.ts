// Único ponto de acesso à API. Outra aplicação usaria exatamente estes endpoints.
export const BASE = '/api/v1'

export class ErroApi extends Error {
  readonly status: number

  constructor(status: number, mensagem: string) {
    super(mensagem)
    this.name = 'ErroApi'
    this.status = status
  }
}

type ItemValidacao = { loc?: (string | number)[]; msg?: unknown }

/** Transforma {"detail": ...} do FastAPI numa frase. Erros de validação viram "campo: mensagem; ...". */
export function mensagemDeErro(dados: unknown, status: number): string {
  const detalhe = (dados as { detail?: unknown } | null)?.detail
  if (typeof detalhe === 'string') return detalhe
  if (Array.isArray(detalhe)) {
    return (detalhe as ItemValidacao[])
      .map((e) => {
        const campo = (e.loc ?? []).filter((p) => p !== 'body').join('.')
        return `${campo}: ${String(e.msg).replace(/^Value error, /, '')}`
      })
      .join('; ')
  }
  return `erro HTTP ${status}`
}

type Metodo = 'GET' | 'POST' | 'PUT' | 'DELETE'

export async function api<T>(caminho: string, { metodo = 'GET', corpo }: { metodo?: Metodo; corpo?: unknown } = {}): Promise<T> {
  const opcoes: RequestInit = { method: metodo, headers: {} }
  if (corpo !== undefined) {
    opcoes.headers = { 'Content-Type': 'application/json' }
    opcoes.body = JSON.stringify(corpo)
  }
  let resposta: Response
  try {
    resposta = await fetch(BASE + caminho, opcoes)
  } catch {
    throw new ErroApi(0, 'não foi possível falar com o servidor')
  }
  if (resposta.status === 204) return null as T
  const dados: unknown = await resposta.json().catch(() => null)
  if (!resposta.ok) throw new ErroApi(resposta.status, mensagemDeErro(dados, resposta.status))
  return dados as T
}

/** {a: 1, b: "", c: null, d: false} -> "?a=1" */
export function query(parametros: Record<string, string | number | boolean | null | undefined>): string {
  const busca = new URLSearchParams()
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === undefined || valor === null || valor === '' || valor === false) continue
    busca.append(chave, String(valor))
  }
  const texto = busca.toString()
  return texto ? `?${texto}` : ''
}
