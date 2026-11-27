// Datas e durações no formato brasileiro (mesmas regras da versão original).

/** "2026-11-26T19:15:21-03:00" -> "26/11/2026, 19:15" ("—" se vazio). */
export function dataHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

/** "2026-11-26" -> "26/11/2026" ("—" se vazio ou fora do formato). */
export function data(isoData: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoData ?? '')
  return m ? `${m[3]}/${m[2]}/${m[1]}` : '—'
}

/** Diferença entre dois instantes: "42 s" ou "3 min 5 s" ("—" se faltar um deles). */
export function duracao(inicio: string | null | undefined, fim: string | null | undefined): string {
  if (!inicio || !fim) return '—'
  const s = Math.max(0, Math.round((new Date(fim).getTime() - new Date(inicio).getTime()) / 1000))
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`
}

/** Data de hoje menos N dias, no formato AAAA-MM-DD (fuso local). */
export function hojeMenos(dias: number, hoje = new Date()): string {
  const d = new Date(hoje)
  d.setDate(d.getDate() - dias)
  const mes = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mes}-${dia}`
}

export const plural = (n: number, singular: string, pluralTexto = `${singular}s`) =>
  `${n} ${n === 1 ? singular : pluralTexto}`
