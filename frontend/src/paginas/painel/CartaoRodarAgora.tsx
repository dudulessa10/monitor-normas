import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import MenuItem from '@mui/material/MenuItem'
import TextField from '@mui/material/TextField'

import { useAlvos, useRodar } from '../../api/consultas.ts'
import { useAvisos } from '../../componentes/Avisos.tsx'
import Cartao from '../../componentes/Cartao.tsx'
import { Discreto } from '../../componentes/Estados.tsx'

const TODOS = ''

export default function CartaoRodarAgora({ emAndamento }: { emAndamento: boolean }) {
  const [alvo, setAlvo] = useState(TODOS)
  const { data: alvos = [] } = useAlvos()
  const rodar = useRodar()
  const avisar = useAvisos()

  const disparar = () =>
    rodar.mutate(alvo || null, {
      onSuccess: (r) => avisar(`Execução #${r.rodada_id} iniciada.`),
      onError: (erro) => avisar(erro.message, 'erro'),
    })

  return (
    <Cartao titulo="Rodar agora">
      <TextField select size="small" label="Alvo" value={alvo} onChange={(e) => setAlvo(e.target.value)} fullWidth>
        <MenuItem value={TODOS}>Todos os alvos ativos</MenuItem>
        {alvos.filter((a) => a.valido).map((a) => (
          <MenuItem key={a.id} value={a.id}>{a.categoria || a.id}{a.ativo ? '' : ' (inativo)'}</MenuItem>
        ))}
      </TextField>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mt: 1 }}>
        <Button variant="contained" onClick={disparar} disabled={emAndamento || rodar.isPending}>Rodar agora</Button>
        <Discreto>{rodar.isPending ? 'iniciando…' : emAndamento ? 'aguarde a execução atual' : ''}</Discreto>
      </Box>
    </Cartao>
  )
}
