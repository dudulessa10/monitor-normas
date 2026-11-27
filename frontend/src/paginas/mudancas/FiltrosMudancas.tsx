import { useState, type FormEvent } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import TextField from '@mui/material/TextField'

import type { Alvo, FiltrosMudancas, TipoMudanca } from '../../api/tipos.ts'

const TIPOS_VALIDOS: TipoMudanca[] = ['NOVO', 'ALTERADO', 'REMOVIDO', 'LINHA_BASE']
const VAZIO: Required<FiltrosMudancas> = {
  palavra: '', alvo: '', tipo: '', de: '', ate: '', registrado_de: '', registrado_ate: '', incluir_linha_base: false,
}

// oxlint-disable-next-line react/only-export-components
export function filtrosDaUrl(p: URLSearchParams): FiltrosMudancas {
  const tipo = p.get('tipo') as TipoMudanca | null
  return {
    palavra: p.get('palavra') ?? '',
    alvo: p.get('alvo') ?? '',
    tipo: tipo && TIPOS_VALIDOS.includes(tipo) ? tipo : '',
    de: p.get('de') ?? '',
    ate: p.get('ate') ?? '',
    registrado_de: p.get('registrado_de') ?? '',
    registrado_ate: p.get('registrado_ate') ?? '',
    incluir_linha_base: p.get('incluir_linha_base') === 'true',
  }
}

export default function FiltrosMudancasForm({ inicial, alvos, aoAplicar }: {
  inicial: FiltrosMudancas
  alvos: Alvo[]
  aoAplicar: (filtros: FiltrosMudancas) => void
}) {
  const [f, setF] = useState<Required<FiltrosMudancas>>({ ...VAZIO, ...inicial })
  const mudar = (campo: keyof FiltrosMudancas) => (e: { target: { value: string } }) => setF({ ...f, [campo]: e.target.value })
  const data = (campo: 'de' | 'ate' | 'registrado_de' | 'registrado_ate', rotulo: string) => (
    <TextField type="date" size="small" label={rotulo} value={f[campo]} onChange={mudar(campo)}
      slotProps={{ inputLabel: { shrink: true } }} />
  )
  const enviar = (e: FormEvent) => {
    e.preventDefault()
    aoAplicar({ ...f, palavra: f.palavra.trim() })
  }

  return (
    <Paper component="form" onSubmit={enviar} aria-label="Filtros" sx={{
      p: 2, mb: 2, display: 'grid', gap: 1.5, alignItems: 'center',
      gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
    }}>
      <TextField size="small" label="Palavra-chave" placeholder="ex.: aeródromo" value={f.palavra} onChange={mudar('palavra')} />
      <TextField select size="small" label="Alvo" value={f.alvo} onChange={mudar('alvo')}>
        <MenuItem value="">Todos</MenuItem>
        {alvos.map((a) => <MenuItem key={a.id} value={a.id}>{a.categoria || a.id}</MenuItem>)}
      </TextField>
      <TextField select size="small" label="Tipo" value={f.tipo} onChange={mudar('tipo')}>
        <MenuItem value="">Novas, alteradas e removidas</MenuItem>
        <MenuItem value="NOVO">Novas</MenuItem>
        <MenuItem value="ALTERADO">Alteradas</MenuItem>
        <MenuItem value="REMOVIDO">Removidas</MenuItem>
        <MenuItem value="LINHA_BASE">Linha de base</MenuItem>
      </TextField>
      {data('de', 'Publicadas de')}
      {data('ate', 'até')}
      {data('registrado_de', 'Detectadas de')}
      {data('registrado_ate', 'até')}
      <FormControlLabel label="Incluir linha de base" control={
        <Checkbox checked={f.incluir_linha_base} onChange={(e) => setF({ ...f, incluir_linha_base: e.target.checked })} />
      } />
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button type="submit" variant="contained">Filtrar</Button>
        <Button type="button" variant="outlined" onClick={() => aoAplicar(VAZIO)}>Limpar</Button>
      </Box>
    </Paper>
  )
}
