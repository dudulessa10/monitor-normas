import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'

import type { Pagina } from '../api/tipos.ts'

/** "1–50 de 312" com Anterior/Próxima (mesmo comportamento da versão original). */
export default function Paginacao({ pagina, aoMudar }: {
  pagina: Pick<Pagina<unknown>, 'total' | 'limite' | 'deslocamento'>
  aoMudar: (deslocamento: number) => void
}) {
  const { total, limite, deslocamento } = pagina
  const fim = Math.min(total, deslocamento + limite)
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1, mt: 1.5 }}>
      <Typography variant="body2" color="text.secondary" sx={{ mr: 1 }}>
        {total ? `${deslocamento + 1}–${fim} de ${total}` : 'nenhum resultado'}
      </Typography>
      <Button size="small" variant="outlined" disabled={deslocamento === 0}
        onClick={() => aoMudar(Math.max(0, deslocamento - limite))}>
        Anterior
      </Button>
      <Button size="small" variant="outlined" disabled={fim >= total} onClick={() => aoMudar(deslocamento + limite)}>
        Próxima
      </Button>
    </Box>
  )
}
