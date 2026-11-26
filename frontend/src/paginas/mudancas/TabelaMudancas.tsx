import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'

import type { Bloco } from '../../api/tipos.ts'
import { Discreto } from '../../componentes/Estados.tsx'
import LinkExterno from '../../componentes/LinkExterno.tsx'
import { SeloTipo } from '../../componentes/Selos.tsx'
import { data, dataHora } from '../../util/formatacao.ts'

export default function TabelaMudancas({ blocos }: { blocos: Bloco[] }) {
  return (
    <TableContainer component={Paper}>
      <Table size="small" aria-label="Mudanças">
        <TableHead>
          <TableRow>
            <TableCell>Detectada</TableCell>
            <TableCell>Tipo</TableCell>
            <TableCell>Norma</TableCell>
            <TableCell>Ementa</TableCell>
            <TableCell>Publicação</TableCell>
            <TableCell>Alvo</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {blocos.map((b) => (
            <TableRow key={b.indice}>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{dataHora(b.timestamp)}</TableCell>
              <TableCell><SeloTipo tipo={b.tipo_mudanca} /></TableCell>
              <TableCell sx={{ fontWeight: 700 }}><LinkExterno url={b.link}>{b.norma}</LinkExterno></TableCell>
              <TableCell sx={{ minWidth: 280 }}>
                {b.ementa}
                {b.palavras_chave.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                    {b.palavras_chave.map((p) => <Chip key={p} label={p} size="small" variant="outlined" />)}
                  </Box>
                )}
              </TableCell>
              <TableCell sx={{ whiteSpace: 'nowrap' }}>{data(b.data_publicacao)}</TableCell>
              <TableCell><Discreto>{b.alvo}</Discreto></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
