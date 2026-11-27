import type { ReactNode } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'

export default function CabecalhoTela({ titulo, subtitulo, acoes }: {
  titulo: string
  subtitulo: string
  acoes?: ReactNode
}) {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 2, mb: 2.5, flexWrap: 'wrap' }}>
      <Box>
        <Typography variant="h1" gutterBottom>{titulo}</Typography>
        <Typography color="text.secondary">{subtitulo}</Typography>
      </Box>
      {acoes}
    </Box>
  )
}
