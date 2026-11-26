import { Link as LinkRouter } from 'react-router'
import Box from '@mui/material/Box'
import Link from '@mui/material/Link'
import Typography from '@mui/material/Typography'

import { useExecucoes } from '../../api/consultas.ts'
import Cartao from '../../componentes/Cartao.tsx'
import { Carregando, Discreto, ErroCarga, TextoErro } from '../../componentes/Estados.tsx'
import { SeloStatus } from '../../componentes/Selos.tsx'
import { dataHora, duracao, plural } from '../../util/formatacao.ts'
import { rotuloOrigem } from '../../util/rotulos.ts'

export default function CartaoUltimaExecucao() {
  const { data, isPending, error } = useExecucoes(1)
  const r = data?.itens[0]

  return (
    <Cartao titulo="Última execução">
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} /> : !r ? (
        <Discreto>Nenhuma execução ainda.</Discreto>
      ) : (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SeloStatus status={r.status} />
            <Discreto>{rotuloOrigem(r.origem)}</Discreto>
          </Box>
          <Typography>
            {dataHora(r.inicio)} · {r.status === 'em_andamento' ? 'rodando…' : duracao(r.inicio, r.fim)}
          </Typography>
          <Discreto>
            {plural(r.total, 'item', 'itens')} · {r.novos} novos · {r.alterados} alterados · {r.removidos} removidos
            {r.erros > 0 && <> · <Box component="span" sx={{ color: 'error.main' }}>{r.erros} alvo(s) com erro</Box></>}
          </Discreto>
          {r.erro && <TextoErro>{r.erro}</TextoErro>}
          <Link component={LinkRouter} to="/execucoes" underline="hover">histórico</Link>
        </>
      )}
    </Cartao>
  )
}
