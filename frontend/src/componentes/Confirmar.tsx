import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogTitle from '@mui/material/DialogTitle'

/** Pergunta de confirmação (substitui o confirm() do navegador). */
export default function Confirmar({ aberto, titulo, mensagem, rotuloConfirmar = 'Confirmar', perigo = false, aoConfirmar, aoCancelar }: {
  aberto: boolean
  titulo: string
  mensagem: string
  rotuloConfirmar?: string
  perigo?: boolean
  aoConfirmar: () => void
  aoCancelar: () => void
}) {
  return (
    <Dialog open={aberto} onClose={aoCancelar} maxWidth="xs" fullWidth>
      <DialogTitle>{titulo}</DialogTitle>
      <DialogContent>
        <DialogContentText>{mensagem}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={aoCancelar}>Cancelar</Button>
        <Button variant="contained" color={perigo ? 'error' : 'primary'} onClick={aoConfirmar} autoFocus>
          {rotuloConfirmar}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
