import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Sem `globals: true` o Testing Library não desmonta as telas sozinho entre um teste e outro.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
