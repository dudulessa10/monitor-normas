import type { ReactNode } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import CircularProgress from '@mui/material/CircularProgress'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'

export function Carregando({ texto = 'Carregando…' }: { texto?: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary', py: 1 }}>
      <CircularProgress size={16} color="inherit" />
      <Typography variant="body2">{texto}</Typography>
    </Box>
  )
}

export function ErroCarga({ erro, contexto = 'carregar os dados' }: { erro: unknown; contexto?: string }) {
  const mensagem = erro instanceof Error ? erro.message : String(erro)
  return <Alert severity="error">Não foi possível {contexto}: {mensagem}</Alert>
}

export function Vazio({ children }: { children: ReactNode }) {
  return (
    <Paper sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
      {children}
    </Paper>
  )
}

/** Texto discreto (cinza, menor) usado nos detalhes das tabelas e cartões. */
export function Discreto({ children, mono = false }: { children: ReactNode; mono?: boolean }) {
  return (
    <Typography variant="body2" component="div" color="text.secondary"
      sx={mono ? { fontFamily: 'ui-monospace, Consolas, monospace', fontSize: '0.8rem', wordBreak: 'break-all' } : undefined}>
      {children}
    </Typography>
  )
}

export function TextoErro({ children }: { children: ReactNode }) {
  return <Typography variant="body2" component="div" color="error.main">{children}</Typography>
}
