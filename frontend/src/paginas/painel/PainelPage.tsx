import { useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import { useQueryClient } from '@tanstack/react-query'

import { useExecucoes } from '../../api/consultas.ts'
import { useAvisos } from '../../componentes/Avisos.tsx'
import CabecalhoTela from '../../componentes/CabecalhoTela.tsx'
import CartaoAlvos from './CartaoAlvos.tsx'
import CartaoLedger from './CartaoLedger.tsx'
import CartaoRodarAgora from './CartaoRodarAgora.tsx'
import CartaoUltimaExecucao from './CartaoUltimaExecucao.tsx'
import MudancasRecentes from './MudancasRecentes.tsx'

export default function PainelPage() {
  // A última rodada é a mesma consulta do cartão "Última execução" (o React Query não repete o pedido).
  const ultima = useExecucoes(1).data?.itens[0]
  const emAndamento = ultima?.status === 'em_andamento'
  useAvisoAoConcluir(emAndamento)

  return (
    <>
      <CabecalhoTela titulo="Painel" subtitulo="Situação do monitoramento e mudanças dos últimos 7 dias." />
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', mb: 2 }}>
        <CartaoUltimaExecucao />
        <CartaoRodarAgora emAndamento={emAndamento} />
        <CartaoLedger />
        <CartaoAlvos />
      </Box>
      <MudancasRecentes />
    </>
  )
}

/** Quando a rodada em andamento termina: avisa e recarrega mudanças, ledger e alvos. */
function useAvisoAoConcluir(emAndamento: boolean) {
  const avisar = useAvisos()
  const cliente = useQueryClient()
  const antes = useRef(emAndamento)
  useEffect(() => {
    if (antes.current && !emAndamento) {
      avisar('Execução concluída.')
      cliente.invalidateQueries({ predicate: (q) => q.queryKey[0] !== 'execucoes' })
    }
    antes.current = emAndamento
  }, [emAndamento, avisar, cliente])
}
