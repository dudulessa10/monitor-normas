import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Switch from '@mui/material/Switch'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'

import type { Alvo } from '../../api/tipos.ts'
import { Discreto, TextoErro } from '../../componentes/Estados.tsx'
import { SeloStatus } from '../../componentes/Selos.tsx'
import { dataHora } from '../../util/formatacao.ts'

type Acao = (alvo: Alvo) => void

export default function TabelaAlvos({ alvos, alternando, aoAlternar, aoEditar, aoRodar, aoExcluir }: {
  alvos: Alvo[]
  /** id do alvo que está sendo ativado/desativado (interruptor fica bloqueado). */
  alternando?: string
  aoAlternar: Acao
  aoEditar: Acao
  aoRodar: Acao
  aoExcluir: Acao
}) {
  return (
    <TableContainer component={Paper}>
      <Table size="small" aria-label="Alvos">
        <TableHead>
          <TableRow>
            <TableCell>Ativo</TableCell>
            <TableCell>Alvo</TableCell>
            <TableCell>Método</TableCell>
            <TableCell align="right">Itens</TableCell>
            <TableCell>Última execução</TableCell>
            <TableCell />
          </TableRow>
        </TableHead>
        <TableBody>
          {!alvos.length && (
            <TableRow>
              <TableCell colSpan={6} sx={{ textAlign: 'center', color: 'text.secondary', py: 3 }}>
                Nenhum alvo cadastrado. Use "Novo alvo" ou rode <code>python monitor.py importar-yaml</code>.
              </TableCell>
            </TableRow>
          )}
          {alvos.map((a) => {
            const u = a.ultima_execucao
            return (
              <TableRow key={a.id} sx={u?.status === 'erro' ? { bgcolor: 'error.light' } : undefined}>
                <TableCell>
                  <Switch checked={a.ativo} onChange={() => aoAlternar(a)} disabled={alternando === a.id}
                    slotProps={{ input: { 'aria-label': `Ativar ${a.id}`, role: 'switch' } }} />
                </TableCell>
                <TableCell sx={{ maxWidth: 420 }}>
                  <strong>{a.categoria || a.id}</strong>
                  <Discreto>{a.id}{a.site ? ` · ${a.site}` : ''}</Discreto>
                  <Discreto mono>{a.url}</Discreto>
                  {!a.valido && <TextoErro>Definição inválida: {a.erro_config}</TextoErro>}
                </TableCell>
                <TableCell>{a.metodo}</TableCell>
                <TableCell align="right">{a.itens_vigentes}</TableCell>
                <TableCell>
                  {u ? (
                    <>
                      <SeloStatus status={u.status} />
                      <Discreto>{dataHora(u.fim || u.inicio)}</Discreto>
                      {u.status === 'ok' && <Discreto>+{u.novos} ~{u.alterados} −{u.removidos}</Discreto>}
                      {u.erro && <TextoErro>{u.erro}</TextoErro>}
                    </>
                  ) : <Discreto>nunca executado</Discreto>}
                </TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                    <Button size="small" variant="outlined" onClick={() => aoEditar(a)} aria-label={`Editar ${a.id}`}>Editar</Button>
                    <Button size="small" variant="outlined" onClick={() => aoRodar(a)} disabled={!a.valido} aria-label={`Rodar ${a.id}`}>Rodar</Button>
                    <Button size="small" variant="outlined" color="error" onClick={() => aoExcluir(a)} aria-label={`Excluir ${a.id}`}>Excluir</Button>
                  </Box>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </TableContainer>
  )
}
