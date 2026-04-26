import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    exclude: ['e2e/**', 'node_modules/**'],
    // CI flake mitigation: under heavy parallel load, vitest+jsdom+MSW timing
    // races cause occasional sporadic failures (different test per run). Retry
    // twice before marking failed. Per-test bugs would still fail consistently.
    retry: 2,
  },
})
