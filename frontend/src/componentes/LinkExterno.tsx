import type { ReactNode } from 'react'
import Link from '@mui/material/Link'

import { urlSegura } from '../util/url.ts'

/** Link para a norma no site de origem; se o endereço não for http(s), mostra só o texto. */
export default function LinkExterno({ url, children }: { url: string | null | undefined; children: ReactNode }) {
  const seguro = urlSegura(url)
  if (!seguro) return <>{children}</>
  return (
    <Link href={seguro} target="_blank" rel="noopener noreferrer" underline="hover">
      {children}
    </Link>
  )
}
