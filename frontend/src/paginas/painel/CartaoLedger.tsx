import Box from '@mui/material/Box'
import Button from '@mui/material/Button'

import { useVerificacaoLedger } from '../../api/consultas.ts'
import { useAvisos } from '../../componentes/Avisos.tsx'
import Cartao from '../../componentes/Cartao.tsx'
import { Carregando, Discreto, ErroCarga, TextoErro } from '../../componentes/Estados.tsx'
import { SeloTexto } from '../../componentes/Selos.tsx'

export default function CartaoLedger() {
  const { data: v, isPending, error } = useVerificacaoLedger()
  const avisar = useAvisos()

  const copiar = async (texto: string) => {
    try {
      await navigator.clipboard.writeText(texto)
      avisar('Âncora copiada.')
    } catch {
      avisar('Não foi possível copiar; selecione o texto.', 'erro')
    }
  }

  return (
    <Cartao titulo="Integridade do ledger">
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} /> : (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {v.ok ? <SeloTexto cor="success">íntegro</SeloTexto> : <SeloTexto cor="error">com problemas</SeloTexto>}
            <Discreto>{v.blocos} blocos · {v.ancoras_conferidas} âncora(s)</Discreto>
          </Box>
          {v.erros.map((e) => <TextoErro key={e}>{e}</TextoErro>)}
          {v.avisos.map((a) => <Discreto key={a}>{a}</Discreto>)}
          {v.ancora_atual && (
            <>
              <Discreto>Âncora atual (guarde fora deste computador):</Discreto>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Discreto mono>{v.ancora_atual}</Discreto>
                <Button size="small" variant="outlined" onClick={() => copiar(v.ancora_atual!)}>Copiar</Button>
              </Box>
            </>
          )}
        </>
      )}
    </Cartao>
  )
}
