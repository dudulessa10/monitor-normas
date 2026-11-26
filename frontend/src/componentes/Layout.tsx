import { useEffect } from 'react'
import { Link as LinkRouter, Outlet, useLocation } from 'react-router'
import AppBar from '@mui/material/AppBar'
import Box from '@mui/material/Box'
import Container from '@mui/material/Container'
import Link from '@mui/material/Link'
import Tab from '@mui/material/Tab'
import Tabs from '@mui/material/Tabs'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'

const TELAS = [
  { caminho: '/', titulo: 'Painel' },
  { caminho: '/alvos', titulo: 'Alvos' },
  { caminho: '/mudancas', titulo: 'Mudanças' },
  { caminho: '/execucoes', titulo: 'Execuções' },
]

export default function Layout() {
  const { pathname } = useLocation()
  const atual = TELAS.find((t) => t.caminho === pathname) ?? TELAS[0]

  useEffect(() => {
    document.title = `${atual.titulo} · Monitor de Normas`
  }, [atual])

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 3, flexWrap: 'wrap' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              aria-hidden
              sx={{
                width: 28, height: 28, borderRadius: 1.5, bgcolor: 'primary.main', color: 'primary.contrastText',
                display: 'grid', placeItems: 'center', fontFamily: 'Georgia, serif', fontWeight: 700,
              }}
            >
              §
            </Box>
            <Typography sx={{ fontWeight: 700 }}>Monitor de Normas</Typography>
          </Box>
          <Tabs value={atual.caminho} component="nav" aria-label="Telas" sx={{ flexGrow: 1 }}>
            {TELAS.map((t) => (
              <Tab key={t.caminho} value={t.caminho} label={t.titulo} component={LinkRouter} to={t.caminho} />
            ))}
          </Tabs>
          <Link href="/docs" target="_blank" rel="noopener" underline="hover">API</Link>
        </Toolbar>
      </AppBar>
      <Container component="main" maxWidth="xl" sx={{ py: 3 }}>
        <Outlet />
      </Container>
    </Box>
  )
}
