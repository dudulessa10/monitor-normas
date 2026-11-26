import { createTheme } from '@mui/material/styles'

// Mesmas cores da versão original (tokens do antigo estilo.css), com claro e escuro automáticos
// conforme a preferência do sistema.
export const tema = createTheme({
  cssVariables: { colorSchemeSelector: 'media' },
  colorSchemes: {
    light: {
      palette: {
        primary: { main: '#1f5fa8' },
        success: { main: '#1e7a46', light: '#e3f4ea' },
        warning: { main: '#8a5a00', light: '#fdf1d8' },
        error: { main: '#b42318', light: '#fde8e6' },
        info: { main: '#1f5fa8', light: '#e5eefb' },
        background: { default: '#f5f6f8', paper: '#ffffff' },
        text: { primary: '#1c2430', secondary: '#5b6573' },
        divider: '#dde1e7',
      },
    },
    dark: {
      palette: {
        primary: { main: '#5b9bea' },
        success: { main: '#5fd08f', light: '#173526' },
        warning: { main: '#f2c46b', light: '#3a2f14' },
        error: { main: '#ff8a7f', light: '#3d1d1a' },
        info: { main: '#8ab8f2', light: '#1b2c44' },
        background: { default: '#12161c', paper: '#1a2028' },
        text: { primary: '#e6eaf0', secondary: '#9aa5b4' },
        divider: '#2e3744',
      },
    },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
    fontSize: 14,
    h1: { fontSize: '1.4rem', fontWeight: 700 },
    h2: { fontSize: '1.05rem', fontWeight: 600 },
  },
  components: {
    MuiButton: { defaultProps: { disableElevation: true }, styleOverrides: { root: { textTransform: 'none' } } },
    MuiTab: { styleOverrides: { root: { textTransform: 'none', fontSize: '0.95rem' } } },
    MuiPaper: { defaultProps: { variant: 'outlined' } },
    MuiTableCell: { styleOverrides: { root: { verticalAlign: 'top' } } },
  },
})
