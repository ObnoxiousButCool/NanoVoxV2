/**
 * Application configuration, read once from the Vite environment.
 *
 * Mirrors the backend's fail-fast approach (D4): a missing or malformed variable
 * throws at module load with a message naming the variable, rather than
 * producing a request to `undefined/health` at runtime.
 */

export interface AppConfig {
  readonly apiBaseUrl: string
  readonly appName: string
}

/** Only the variables this module actually reads — not the whole Vite env. */
export type ConfigSource = Pick<ImportMetaEnv, 'VITE_API_BASE_URL' | 'VITE_APP_NAME'>

function required(name: keyof ConfigSource, value: string | undefined): string {
  const trimmed = value?.trim()
  if (!trimmed) {
    throw new Error(
      `${name} is not set. Copy Code/Frontend/.env.example to .env and set it.`,
    )
  }
  return trimmed
}

function validateBaseUrl(value: string): string {
  // A root-relative path is the deployed form: the API is served by the same
  // process and origin as this bundle, so one build works on any host. Absolute
  // URLs remain valid for development against a separate backend.
  if (!value.startsWith('/')) {
    try {
      new URL(value)
    } catch {
      throw new Error(
        `VITE_API_BASE_URL must be an absolute URL or a root-relative path: ${value}`,
      )
    }
  }
  // A trailing slash would produce doubled separators when paths are appended.
  return value.replace(/\/+$/, '')
}

export function readConfig(env: ConfigSource): AppConfig {
  return {
    apiBaseUrl: validateBaseUrl(required('VITE_API_BASE_URL', env.VITE_API_BASE_URL)),
    appName: required('VITE_APP_NAME', env.VITE_APP_NAME),
  }
}

let cached: AppConfig | null = null

/**
 * The validated configuration, read once.
 *
 * Resolved lazily rather than at module load so that importing a module which
 * merely *uses* configuration cannot throw during an unrelated import. `main.tsx`
 * calls this during startup, which is where a misconfiguration should surface.
 */
export function getConfig(): AppConfig {
  cached ??= readConfig(import.meta.env)
  return cached
}

/** Testing seam: clears the memoised configuration. */
export function resetConfigCache(): void {
  cached = null
}
