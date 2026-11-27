/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

// Um único .env para o projeto todo, na raiz do repositório (ao lado do setup.sh).
const PASTA_ENV = '..'

export default defineConfig(({ mode }) => {
  // FRONTEND_PROXY_API só é usado aqui, no `npm run dev`; não vai para o navegador
  // (o Vite só expõe ao navegador variáveis que começam com VITE_, e o projeto não usa nenhuma).
  const env = loadEnv(mode, PASTA_ENV, '')
  const api = env.FRONTEND_PROXY_API || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    envDir: PASTA_ENV,
    server: {
      // Em desenvolvimento o React roda em :5173 e repassa a API para o servidor Python.
      proxy: { '/api': api, '/docs': api, '/openapi.json': api },
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/testes/preparacao.ts',
    },
  }
})
