// Confere se cada import relativo em src/ aponta para um arquivo que existe com EXATAMENTE as mesmas
// maiúsculas e minúsculas. O Windows e o macOS aceitam './layout.tsx' para 'Layout.tsx'; o Linux da VM
// não, e o build quebraria lá. Uso: node scripts/verificar-imports.mjs (roda dentro de `npm run lint`).
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SRC = join(RAIZ, 'src')
const EXTENSOES = ['', '.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx']
const IMPORT = /(?:import|export)\s[^'"]*?from\s*['"](\.{1,2}\/[^'"]+)['"]|import\s*\(?\s*['"](\.{1,2}\/[^'"]+)['"]/g

function arquivos(pasta) {
  return readdirSync(pasta, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? arquivos(join(pasta, e.name)) : /\.(tsx?|jsx?)$/.test(e.name) ? [join(pasta, e.name)] : [],
  )
}

function existe(caminho) {
  try {
    return statSync(caminho).isFile()
  } catch {
    return false
  }
}

// Caminho existe com a grafia exata? Compara cada parte com o nome real listado na pasta.
function grafiaExata(caminho) {
  const partes = relative(RAIZ, caminho).split(sep)
  let atual = RAIZ
  for (const parte of partes) {
    if (!readdirSync(atual).includes(parte)) return false
    atual = join(atual, parte)
  }
  return true
}

const erros = []
for (const arquivo of arquivos(SRC)) {
  const texto = readFileSync(arquivo, 'utf8')
  for (const m of texto.matchAll(IMPORT)) {
    const alvo = m[1] ?? m[2]
    const candidatos = EXTENSOES.map((ext) => resolve(dirname(arquivo), alvo + ext)).filter(existe)
    const local = `${relative(RAIZ, arquivo)}: '${alvo}'`
    if (!candidatos.length) erros.push(`${local} não existe`)
    else if (!candidatos.some(grafiaExata)) erros.push(`${local} difere em maiúsculas/minúsculas do arquivo real`)
  }
}

if (erros.length) {
  console.error(`Imports com problema (quebrariam no Linux):\n  ${erros.join('\n  ')}`)
  process.exit(1)
}
console.log('Imports conferidos: todos batem com os nomes reais dos arquivos.')
