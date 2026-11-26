import { useMemo } from 'react'
import { Link as LinkRouter } from 'react-router'
import Box from '@mui/material/Box'
import Link from '@mui/material/Link'
import List from '@mui/material/List'
import ListItem from '@mui/material/ListItem'
import Typography from '@mui/material/Typography'

import { useMudancas } from '../../api/consultas.ts'
import Cartao from '../../componentes/Cartao.tsx'
import { Carregando, Discreto, ErroCarga } from '../../componentes/Estados.tsx'
import LinkExterno from '../../componentes/LinkExterno.tsx'
import { SeloTipo } from '../../componentes/Selos.tsx'
import { data, dataHora, hojeMenos } from '../../util/formatacao.ts'

const LIMITE = 10

export default function MudancasRecentes() {
  const desde = useMemo(() => hojeMenos(7), [])
  const { data: pagina, isPending, error } = useMudancas({ registrado_de: desde }, LIMITE)

  return (
    <Cartao
      titulo="Mudanças recentes"
      acao={<Link component={LinkRouter} to={`/mudancas?registrado_de=${desde}`} underline="hover">ver todas</Link>}
    >
      {isPending ? <Carregando /> : error ? <ErroCarga erro={error} /> : !pagina.itens.length ? (
        <Discreto>Nenhuma norma nova, alterada ou removida nos últimos 7 dias.</Discreto>
      ) : (
        <>
          <List disablePadding>
            {pagina.itens.map((b) => (
              <ListItem key={b.indice} divider disableGutters sx={{ display: 'block', py: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <SeloTipo tipo={b.tipo_mudanca} />
                  <Typography component="strong" sx={{ fontWeight: 700 }}>
                    <LinkExterno url={b.link}>{b.norma}</LinkExterno>
                  </Typography>
                </Box>
                {b.ementa && <Typography variant="body2">{b.ementa}</Typography>}
                <Discreto>
                  {b.alvo} · publicada em {data(b.data_publicacao)} · detectada em {dataHora(b.timestamp)}
                </Discreto>
              </ListItem>
            ))}
          </List>
          {pagina.total > pagina.itens.length && <Discreto>e mais {pagina.total - pagina.itens.length}…</Discreto>}
        </>
      )}
    </Cartao>
  )
}
