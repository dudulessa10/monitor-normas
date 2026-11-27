import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import Alert from '@mui/material/Alert'
import Snackbar from '@mui/material/Snackbar'

// Substitui o avisar() da versão original: mensagens rápidas no canto da tela.
type Tipo = 'sucesso' | 'erro'
type Aviso = { id: number; mensagem: string; tipo: Tipo }
type Avisar = (mensagem: string, tipo?: Tipo) => void

const ContextoAvisos = createContext<Avisar>(() => {})

export function ProvedorAvisos({ children }: { children: ReactNode }) {
  const [fila, setFila] = useState<Aviso[]>([])
  const avisar = useCallback<Avisar>((mensagem, tipo = 'sucesso') => {
    setFila((atual) => [...atual, { id: Date.now() + Math.random(), mensagem, tipo }])
  }, [])
  const atual = fila[0]
  const fechar = () => setFila((f) => f.slice(1))

  return (
    <ContextoAvisos.Provider value={avisar}>
      {children}
      <Snackbar
        key={atual?.id}
        open={Boolean(atual)}
        autoHideDuration={atual?.tipo === 'erro' ? 8000 : 4500}
        onClose={(_, motivo) => motivo !== 'clickaway' && fechar()}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert severity={atual?.tipo === 'erro' ? 'error' : 'success'} variant="filled" onClose={fechar}>
          {atual?.mensagem}
        </Alert>
      </Snackbar>
    </ContextoAvisos.Provider>
  )
}

// oxlint-disable-next-line react/only-export-components
export const useAvisos = () => useContext(ContextoAvisos)
