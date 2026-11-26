import Button from '@mui/material/Button'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'

import type { Rodada } from '../../api/tipos.ts'
import { Discreto, TextoErro } from '../../componentes/Estados.tsx'
import { SeloStatus } from '../../componentes/Selos.tsx'
import { dataHora, duracao } from '../../util/formatacao.ts'
import { rotuloOrigem } from '../../util/rotulos.ts'

const fundoErro = { bgcolor: 'error.light' }

/** Uma rodada: linha principal, linha de erros (se houver) e detalhe por alvo (se aberta). */
export default function LinhaRodada({ rodada: r, aberta, aoAlternar }: { rodada: Rodada; aberta: boolean; aoAlternar: () => void }) {
  const comErro = r.erros > 0 || r.status === 'falhou' || r.status === 'interrompida'
  const errosAlvos = r.execucoes.filter((e) => e.erro)

  return (
    <>
      <TableRow sx={comErro ? fundoErro : undefined}>
        <TableCell align="right">#{r.id}</TableCell>
        <TableCell>
          {dataHora(r.inicio)}
          <Discreto>{r.status === 'em_andamento' ? 'rodando…' : duracao(r.inicio, r.fim)}</Discreto>
        </TableCell>
        <TableCell>{rotuloOrigem(r.origem)}</TableCell>
        <TableCell>{r.alvo ?? <Discreto>todos os ativos</Discreto>}</TableCell>
        <TableCell><SeloStatus status={r.status} /></TableCell>
        <TableCell align="right">{r.total}</TableCell>
        <TableCell align="right">{r.novos} / {r.alterados} / {r.removidos}</TableCell>
        <TableCell>
          {r.execucoes.length > 0 && (
            <Button size="small" variant="outlined" onClick={aoAlternar} aria-expanded={aberta}>
              {aberta ? 'Ocultar' : `${r.execucoes.length} alvo(s)`}
            </Button>
          )}
        </TableCell>
      </TableRow>

      {(r.erro || errosAlvos.length > 0) && (
        <TableRow sx={fundoErro}>
          <TableCell />
          <TableCell colSpan={7}>
            {r.erro && <TextoErro>{r.erro}</TextoErro>}
            {errosAlvos.map((e) => <TextoErro key={e.id}><strong>{e.alvo}:</strong> {e.erro}</TextoErro>)}
          </TableCell>
        </TableRow>
      )}

      {aberta && (
        <TableRow>
          <TableCell />
          <TableCell colSpan={7} sx={{ bgcolor: 'action.hover' }}>
            <Table size="small" aria-label={`Alvos da rodada ${r.id}`}>
              <TableHead>
                <TableRow>
                  <TableCell>Alvo</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Itens</TableCell>
                  <TableCell align="right">Novos</TableCell>
                  <TableCell align="right">Alterados</TableCell>
                  <TableCell align="right">Removidos</TableCell>
                  <TableCell>Duração</TableCell>
                  <TableCell>Página modificada em</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {r.execucoes.map((e) => (
                  <TableRow key={e.id}>
                    <TableCell>{e.alvo}{e.erro && <TextoErro>{e.erro}</TextoErro>}</TableCell>
                    <TableCell><SeloStatus status={e.status} /></TableCell>
                    <TableCell align="right">{e.total}</TableCell>
                    <TableCell align="right">{e.novos}</TableCell>
                    <TableCell align="right">{e.alterados}</TableCell>
                    <TableCell align="right">{e.removidos}</TableCell>
                    <TableCell>{duracao(e.inicio, e.fim)}</TableCell>
                    <TableCell>{e.modificacao_pagina || '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}
