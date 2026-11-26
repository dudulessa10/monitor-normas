import { useState } from 'react'
import Paper from '@mui/material/Paper'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'

import { useExecucoes } from '../../api/consultas.ts'
import CabecalhoTela from '../../componentes/CabecalhoTela.tsx'
import { Carregando, ErroCarga, Vazio } from '../../componentes/Estados.tsx'
import Paginacao from '../../componentes/Paginacao.tsx'
import LinhaRodada from './LinhaRodada.tsx'

const POR_PAGINA = 25

export default function ExecucoesPage() {
  const [deslocamento, setDeslocamento] = useState(0)
  const [abertas, setAbertas] = useState<Set<number>>(() => new Set())
  const { data: pagina, isPending, error } = useExecucoes(POR_PAGINA, deslocamento)

  const alternar = (id: number) =>
    setAbertas((atual) => {
      const nova = new Set(atual)
      if (nova.has(id)) nova.delete(id)
      else nova.add(id)
      return nova
    })

  return (
    <>
      <CabecalhoTela titulo="Execuções" subtitulo="Histórico de todas as rodadas: web, linha de comando e agendadas." />
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} contexto="carregar as execuções" /> : !pagina.itens.length ? (
        <Vazio>Nenhuma execução ainda.</Vazio>
      ) : (
        <>
          <TableContainer component={Paper}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell align="right">Rodada</TableCell>
                  <TableCell>Início</TableCell>
                  <TableCell>Origem</TableCell>
                  <TableCell>Alvo</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Itens</TableCell>
                  <TableCell align="right">Novos / alt. / rem.</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {pagina.itens.map((r) => (
                  <LinhaRodada key={r.id} rodada={r} aberta={abertas.has(r.id)} aoAlternar={() => alternar(r.id)} />
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Paginacao pagina={pagina} aoMudar={setDeslocamento} />
        </>
      )}
    </>
  )
}
