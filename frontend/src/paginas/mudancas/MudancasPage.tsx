import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'
import Button from '@mui/material/Button'

import { BASE, query } from '../../api/cliente.ts'
import { useAlvos, useMudancas } from '../../api/consultas.ts'
import type { FiltrosMudancas } from '../../api/tipos.ts'
import CabecalhoTela from '../../componentes/CabecalhoTela.tsx'
import { Carregando, ErroCarga, Vazio } from '../../componentes/Estados.tsx'
import Paginacao from '../../componentes/Paginacao.tsx'
import FiltrosMudancasForm, { filtrosDaUrl } from './FiltrosMudancas.tsx'
import TabelaMudancas from './TabelaMudancas.tsx'

const POR_PAGINA = 50

export default function MudancasPage() {
  // Os filtros ficam no endereço (/mudancas?alvo=x&tipo=NOVO): dá para recarregar e compartilhar o link.
  const [parametros, setParametros] = useSearchParams()
  const filtros = useMemo(() => filtrosDaUrl(parametros), [parametros])
  const [deslocamento, setDeslocamento] = useState(0)
  const { data: alvos = [] } = useAlvos()
  const { data: pagina, isPending, error } = useMudancas(filtros, POR_PAGINA, deslocamento)

  const aplicar = (novos: FiltrosMudancas) => {
    setDeslocamento(0)
    setParametros(new URLSearchParams(query({ ...novos })), { replace: true })
  }

  return (
    <>
      <CabecalhoTela
        titulo="Mudanças"
        subtitulo="Normas novas, alteradas e removidas registradas no ledger."
        acoes={<Button variant="outlined" href={`${BASE}/exportar/excel${query({ ...filtros })}`}>Baixar Excel</Button>}
      />
      <FiltrosMudancasForm key={parametros.toString()} inicial={filtros} alvos={alvos} aoAplicar={aplicar} />
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} contexto="carregar as mudanças" /> : !pagina.itens.length ? (
        <Vazio>Nenhuma mudança encontrada com esses filtros.</Vazio>
      ) : (
        <>
          <TabelaMudancas blocos={pagina.itens} />
          <Paginacao pagina={pagina} aoMudar={setDeslocamento} />
        </>
      )}
    </>
  )
}
