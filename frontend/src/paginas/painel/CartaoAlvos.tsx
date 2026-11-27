import { Link as LinkRouter } from 'react-router'
import Link from '@mui/material/Link'
import Typography from '@mui/material/Typography'

import { useAlvos } from '../../api/consultas.ts'
import Cartao from '../../componentes/Cartao.tsx'
import { Carregando, Discreto, ErroCarga, TextoErro } from '../../componentes/Estados.tsx'

export default function CartaoAlvos() {
  const { data: alvos, isPending, error } = useAlvos()

  return (
    <Cartao titulo="Alvos">
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} /> : (() => {
        const ativos = alvos.filter((a) => a.ativo).length
        const comErro = alvos.filter((a) => a.ativo && a.ultima_execucao?.status === 'erro').length
        return (
          <>
            <Typography sx={{ fontSize: '1.8rem', fontWeight: 700, lineHeight: 1.2 }}>
              {ativos}{' '}
              <Typography component="span" color="text.secondary">de {alvos.length} ativos</Typography>
            </Typography>
            {comErro ? <TextoErro>{comErro} com erro na última execução</TextoErro> : <Discreto>nenhum com erro</Discreto>}
            <Link component={LinkRouter} to="/alvos" underline="hover">gerenciar</Link>
          </>
        )
      })()}
    </Cartao>
  )
}
