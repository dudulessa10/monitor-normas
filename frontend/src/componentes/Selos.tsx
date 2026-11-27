import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'

import { STATUS, TIPOS, type CorSelo } from '../util/rotulos.ts'

function Selo({ cor, rotulo, girando = false }: { cor: CorSelo; rotulo: string; girando?: boolean }) {
  return (
    <Chip
      size="small"
      color={cor}
      variant={cor === 'default' ? 'outlined' : 'filled'}
      label={
        <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}>
          {girando && <CircularProgress size={10} color="inherit" aria-hidden />}
          {rotulo}
        </Box>
      }
      sx={{ fontWeight: 600 }}
    />
  )
}

/** Status de uma rodada ou execução (ok, com erros, em andamento...). */
export function SeloStatus({ status }: { status: string }) {
  const [cor, rotulo] = STATUS[status] ?? ['default', status]
  return <Selo cor={cor} rotulo={rotulo} girando={status === 'em_andamento'} />
}

/** Tipo de mudança de uma norma (novo, alterado, removido, linha de base). */
export function SeloTipo({ tipo }: { tipo: string }) {
  const [cor, rotulo] = TIPOS[tipo] ?? ['default', tipo]
  return <Selo cor={cor} rotulo={rotulo} />
}

/** Selo livre (ex.: "íntegro" / "com problemas" no painel). */
export function SeloTexto({ cor, children }: { cor: CorSelo; children: string }) {
  return <Selo cor={cor} rotulo={children} />
}
