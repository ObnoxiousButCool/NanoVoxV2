import { fileURLToPath, URL } from 'node:url'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// The dev server port is fixed rather than auto-incrementing: the backend's
// CORS_ORIGINS names it, so a silent shift to 5174 would produce CORS failures
// that look like application bugs.
const DEV_SERVER_PORT = 5173

// Bind IPv4 explicitly. Vite's default host resolves to ::1 on Windows, while the
// backend binds 127.0.0.1 and CORS_ORIGINS names it — so http://127.0.0.1:5173
// would refuse connections while http://localhost:5173 worked, which reads as
// "the frontend is down" rather than as an address mismatch.
const DEV_SERVER_HOST = '127.0.0.1'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: DEV_SERVER_HOST,
    port: DEV_SERVER_PORT,
    strictPort: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Tests must not depend on a developer's .env file. Vite still *loads*
    // that file, so every flag a test asserts on has to be pinned here or the
    // suite's result turns on whatever the developer last toggled locally —
    // flipping VITE_SHOW_CORPUS_RUN to false in .env failed the rail tests
    // while nothing about the rail had changed.
    env: {
      VITE_API_BASE_URL: 'http://api.test/api/v1',
      VITE_APP_NAME: 'NanoVox',
      VITE_SHOW_CORPUS_RUN: 'true',
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/main.tsx',
        'src/**/*.d.ts',
        // Type-only modules: they compile to nothing, so coverage is meaningless.
        'src/entities/**',
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
    },
  },
})
