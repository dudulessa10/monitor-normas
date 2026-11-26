import { Navigate, Route, Routes } from 'react-router'

import Layout from './componentes/Layout.tsx'
import PainelPage from './paginas/painel/PainelPage.tsx'
import AlvosPage from './paginas/alvos/AlvosPage.tsx'
import MudancasPage from './paginas/mudancas/MudancasPage.tsx'
import ExecucoesPage from './paginas/execucoes/ExecucoesPage.tsx'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<PainelPage />} />
        <Route path="alvos" element={<AlvosPage />} />
        <Route path="mudancas" element={<MudancasPage />} />
        <Route path="execucoes" element={<ExecucoesPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
