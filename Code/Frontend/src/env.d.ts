/// <reference types="vite/client" />

/**
 * Environment variables exposed to the browser.
 *
 * Declared optional because Vite cannot guarantee a variable was defined at
 * build time; `shared/config/env.ts` validates them once and fails loudly if one
 * is missing, so the rest of the application can treat them as present.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_APP_NAME?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
