import { useRef, useState, type FormEvent, type ReactNode } from 'react'
import Alert from '@mui/material/Alert'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Checkbox from '@mui/material/Checkbox'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import FormControlLabel from '@mui/material/FormControlLabel'
import MenuItem from '@mui/material/MenuItem'
import TextField, { type TextFieldProps } from '@mui/material/TextField'
import Typography from '@mui/material/Typography'

import { useConfiguracao, useSalvarAlvo } from '../../api/consultas.ts'
import type { Alvo } from '../../api/tipos.ts'
import { PADRAO_ID, corpoDoFormulario, valoresIniciais, type ValoresFormulario } from './formularioAlvo.ts'

type Campo = keyof ValoresFormulario

/** Cadastro (alvo = null) ou edição de um alvo. Erros de validação do servidor aparecem no topo. */
export default function FormularioAlvo({ alvo, aoFechar, aoSalvar }: {
  alvo: Alvo | null
  aoFechar: () => void
  aoSalvar: (novo: boolean) => void
}) {
  const [v, setV] = useState<ValoresFormulario>(() => valoresIniciais(alvo))
  const [erro, setErro] = useState<string | null>(null)
  const regex = Object.keys(useConfiguracao().data?.regex ?? {})
  const salvar = useSalvarAlvo()
  const conteudo = useRef<HTMLDivElement>(null)

  const texto = (campo: Campo, rotulo: string, extra: TextFieldProps & { ajuda?: string } = {}) => {
    const { ajuda, ...props } = extra
    return (
      <TextField size="small" label={rotulo} name={campo} value={v[campo]} helperText={ajuda} fullWidth
        onChange={(e) => setV({ ...v, [campo]: e.target.value })} {...props} />
    )
  }

  const enviar = (e: FormEvent) => {
    e.preventDefault()
    setErro(null)
    salvar.mutate({ idOriginal: alvo?.id ?? null, corpo: corpoDoFormulario(v, alvo) }, {
      onSuccess: () => aoSalvar(!alvo),
      onError: (falha) => {
        setErro(falha.message)
        if (conteudo.current) conteudo.current.scrollTop = 0
      },
    })
  }

  const idInvalido = v.id !== '' && !PADRAO_ID.test(v.id.trim())

  return (
    <Dialog open onClose={aoFechar} maxWidth="md" fullWidth>
      <form onSubmit={enviar} aria-label={alvo ? `Editar ${alvo.id}` : 'Novo alvo'} noValidate>
        <DialogTitle>{alvo ? `Editar ${alvo.id}` : 'Novo alvo'}</DialogTitle>
        <DialogContent dividers ref={conteudo}>
          {erro && <Alert severity="error" sx={{ mb: 2 }}>{erro}</Alert>}
          <Grade>
            {texto('id', 'Identificador', {
              required: true, error: idInvalido, slotProps: { htmlInput: { readOnly: Boolean(alvo) } },
              ajuda: idInvalido ? 'use só minúsculas, números, - e _' : 'minúsculas, números e hífen; não muda depois',
            })}
            {texto('categoria', 'Categoria', { ajuda: 'nome exibido' })}
            {texto('site', 'Site')}
            {texto('prioridade', 'Prioridade', {
              select: true,
              children: [
                <MenuItem key="" value="">—</MenuItem>,
                <MenuItem key="alta" value="alta">alta</MenuItem>,
                <MenuItem key="media" value="media">média</MenuItem>,
                <MenuItem key="baixa" value="baixa">baixa</MenuItem>,
              ],
            })}
            <Largo>{texto('url', 'URL', { required: true, ajuda: 'pode conter {ano}', placeholder: 'https://www.anac.gov.br/.../{ano}' })}</Largo>
            {texto('anos', 'Anos', { ajuda: 'se a URL tiver {ano}: atual, anterior ou números' })}
            <FormControlLabel label="Ativo (roda na execução diária)" control={
              <Checkbox checked={v.ativo} onChange={(e) => setV({ ...v, ativo: e.target.checked })} />
            } />
          </Grade>

          <Secao titulo="Detecção">
            {texto('metodo', 'Método', {
              select: true,
              children: [
                <MenuItem key="l" value="lista_itens">lista de itens (tabela)</MenuItem>,
                <MenuItem key="h" value="hash_conteudo">hash do conteúdo</MenuItem>,
                <MenuItem key="d" value="data_modificacao">data de modificação</MenuItem>,
              ],
            })}
            {texto('chave_item', 'Campo-chave')}
            <Largo>{texto('detectar_mudanca_em', 'Campos que indicam alteração', { ajuda: 'separados por vírgula; vazio = todos' })}</Largo>
          </Secao>

          <Secao titulo="Extração (tabela)">
            {texto('tabela', 'Tabelas', {
              select: true,
              children: [
                <MenuItem key="p" value="primeira">só a primeira</MenuItem>,
                <MenuItem key="t" value="todas">todas</MenuItem>,
              ],
            })}
            {texto('regex_numero', 'Regex do número', {
              select: true,
              children: [
                <MenuItem key="" value="">— automático —</MenuItem>,
                ...[...new Set([...regex, ...(v.regex_numero ? [v.regex_numero] : [])])].map((r) => <MenuItem key={r} value={r}>{r}</MenuItem>),
              ],
            })}
            <Largo>{texto('colunas', 'Colunas', {
              multiline: true, minRows: 3, placeholder: 'Norma: norma\nPublicação: publicacao\nEmenta: ementa\nArquivo: link_arquivo',
              ajuda: 'uma por linha, "Cabeçalho: campo"; vazio = usar o cabeçalho da tabela',
            })}</Largo>
            <Largo>{texto('marcar_status', 'Marcar status', {
              multiline: true, minRows: 2, placeholder: 'revogada: revogada', ajuda: 'uma por linha, "status: nome da regex"',
            })}</Largo>
          </Secao>

          <Box sx={{ mt: 2 }}>{texto('observacoes', 'Observações', { multiline: true, minRows: 2 })}</Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={aoFechar}>Cancelar</Button>
          <Button type="submit" variant="contained" disabled={salvar.isPending || idInvalido || !v.id.trim() || !v.url.trim()}>
            {alvo ? 'Salvar' : 'Cadastrar'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  )
}

function Grade({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, alignItems: 'start', pt: 1 }}>
      {children}
    </Box>
  )
}

function Largo({ children }: { children: ReactNode }) {
  return <Box sx={{ gridColumn: '1 / -1' }}>{children}</Box>
}

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <Box component="fieldset" sx={{ border: 1, borderColor: 'divider', borderRadius: 1, mt: 2.5, px: 2, pb: 2 }}>
      <Typography component="legend" variant="subtitle2" sx={{ px: 0.5 }}>{titulo}</Typography>
      <Grade>{children}</Grade>
    </Box>
  )
}
