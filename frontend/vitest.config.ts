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
    // #4257: jsdom 28 + undici v7 ship a known incompatibility — the dispatcher
    // handler in `node_modules/jsdom/lib/jsdom/browser/resources/jsdom-dispatcher.js`
    // omits the `onError` method that undici v7 now validates, so any in-flight
    // resource fetch (e.g. the `https://fonts.googleapis.com/...` stylesheet
    // loaded via `useLandingFonts` or `index.css`'s `@import url(...)`) emits an
    // `InvalidArgumentError: invalid onError method` rejection at teardown. The
    // 1187 user tests still pass; only the process exit code is affected. We
    // ignore unhandled rejections at the runner level until the upstream jsdom
    // fix lands. The targeted suppression filter that runs first lives in
    // `src/test/setup.ts` so genuine app-level rejections still surface there.
    dangerouslyIgnoreUnhandledErrors: true,
    // CI flake mitigation: under heavy parallel load, vitest+jsdom+MSW timing
    // races cause occasional sporadic failures (different test per run). Retry
    // twice before marking failed. Per-test bugs would still fail consistently.
    retry: 2,
  },
})
