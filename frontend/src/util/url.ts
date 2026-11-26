// Links vêm dos sites monitorados (texto externo). O React já escapa o texto, mas NÃO bloqueia
// endereços como "javascript:...": por isso só viram link os que começam com http:// ou https://.
export function urlSegura(url: string | null | undefined): string | null {
  return /^https?:\/\//i.test(url ?? '') ? (url as string) : null
}
