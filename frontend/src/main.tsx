import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CssBaseline from '@mui/material/CssBaseline'
import { ThemeProvider } from '@mui/material/styles'

import App from './App.tsx'
import { tema } from './tema.ts'
import { ProvedorAvisos } from './componentes/Avisos.tsx'

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false, // como a versão original: recarrega ao navegar, não ao trocar de janela
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={tema} defaultMode="system">
      <CssBaseline />
      <QueryClientProvider client={clienteConsultas}>
        <ProvedorAvisos>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </ProvedorAvisos>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
