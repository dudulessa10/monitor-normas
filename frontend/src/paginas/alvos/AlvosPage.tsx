import { useState } from 'react'
import Button from '@mui/material/Button'

import { useAlternarAtivo, useAlvos, useExcluirAlvo, useRodar } from '../../api/consultas.ts'
import type { Alvo } from '../../api/tipos.ts'
import { useAvisos } from '../../componentes/Avisos.tsx'
import CabecalhoTela from '../../componentes/CabecalhoTela.tsx'
import Confirmar from '../../componentes/Confirmar.tsx'
import { Carregando, ErroCarga } from '../../componentes/Estados.tsx'
import FormularioAlvo from './FormularioAlvo.tsx'
import TabelaAlvos from './TabelaAlvos.tsx'

/** null = fechado; { alvo: null } = novo; { alvo } = editar. */
type Edicao = { alvo: Alvo | null } | null

export default function AlvosPage() {
  const { data: alvos, isPending, error } = useAlvos()
  const [edicao, setEdicao] = useState<Edicao>(null)
  const [excluindo, setExcluindo] = useState<Alvo | null>(null)
  const avisar = useAvisos()
  const alternar = useAlternarAtivo()
  const rodar = useRodar()
  const excluir = useExcluirAlvo()
  const nome = (a: Alvo) => a.categoria || a.id
  const erro = (e: Error) => avisar(e.message, 'erro')

  const acoes = {
    aoAlternar: (a: Alvo) => alternar.mutate(a, {
      onSuccess: () => avisar(`${nome(a)}: ${a.ativo ? 'desativado' : 'ativado'}.`),
      onError: erro,
    }),
    aoEditar: (a: Alvo) => setEdicao({ alvo: a }),
    aoRodar: (a: Alvo) => rodar.mutate(a.id, {
      onSuccess: (r) => avisar(`Execução #${r.rodada_id} iniciada para ${a.id}. Acompanhe em Execuções.`),
      onError: erro,
    }),
    aoExcluir: (a: Alvo) => setExcluindo(a),
  }

  const confirmarExclusao = () => {
    if (!excluindo) return
    const id = excluindo.id
    setExcluindo(null)
    excluir.mutate(id, { onSuccess: () => avisar(`Alvo ${id} excluído.`), onError: erro })
  }

  return (
    <>
      <CabecalhoTela
        titulo="Alvos"
        subtitulo="Páginas vigiadas pelo robô. Alvos inativos não rodam na execução diária."
        acoes={<Button variant="contained" onClick={() => setEdicao({ alvo: null })}>Novo alvo</Button>}
      />
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} contexto="carregar os alvos" /> : (
        <TabelaAlvos alvos={alvos} alternando={alternar.isPending ? alternar.variables?.id : undefined} {...acoes} />
      )}
      {edicao && (
        <FormularioAlvo
          alvo={edicao.alvo}
          aoFechar={() => setEdicao(null)}
          aoSalvar={(novo) => {
            setEdicao(null)
            avisar(novo ? 'Alvo cadastrado.' : 'Alvo salvo.')
          }}
        />
      )}
      <Confirmar
        aberto={Boolean(excluindo)}
        titulo="Excluir alvo"
        mensagem={`Excluir o alvo "${excluindo?.id ?? ''}"? O histórico e o ledger dele são mantidos.`}
        rotuloConfirmar="Excluir"
        perigo
        aoConfirmar={confirmarExclusao}
        aoCancelar={() => setExcluindo(null)}
      />
    </>
  )
}
