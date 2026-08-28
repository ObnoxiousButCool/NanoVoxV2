/**
 * Provider and model selection.
 *
 * Unusable providers are listed with the reason rather than hidden (D3): a user
 * whose choice has silently vanished has no idea why, whereas "OPENAI_API_KEY is
 * not set" tells them exactly what to do.
 */

import { useProviders } from '@/shared/api/queries'
import type { Provider } from '@/shared/api/types'
import { Failure, Note } from '@/shared/ui/primitives'
import styles from './AnalyzePage.module.css'

export interface ProviderSelection {
  readonly provider: string | null
  readonly model: string | null
}

function optionLabel(provider: Provider): string {
  const base = `${provider.name} · ${provider.model}`
  return provider.selectable ? base : `${base} — unavailable`
}

export function ProviderPicker({
  selection,
  onChange,
  disabled,
}: {
  selection: ProviderSelection
  onChange: (selection: ProviderSelection) => void
  disabled: boolean
}) {
  const { data, isPending, error } = useProviders()

  if (isPending) {
    return <Note>Checking which providers are available…</Note>
  }
  if (error) {
    return <Failure error={error} what="the provider list" />
  }

  const chosen = selection.provider ?? data.default
  const active = data.providers.find((provider) => provider.name === chosen)

  return (
    <>
      <div className={styles.field}>
        <label className={styles.label} htmlFor="provider">
          Provider
        </label>
        <select
          id="provider"
          className={styles.select}
          value={chosen}
          disabled={disabled}
          onChange={(event) => {
            onChange({ provider: event.target.value, model: null })
          }}
        >
          {data.providers.map((provider) => (
            <option key={provider.name} value={provider.name} disabled={!provider.selectable}>
              {optionLabel(provider)}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.field}>
        <label className={styles.label} htmlFor="model">
          Model
        </label>
        <input
          id="model"
          className={styles.select}
          type="text"
          disabled={disabled}
          placeholder={active?.model ?? ''}
          value={selection.model ?? ''}
          onChange={(event) => {
            onChange({ provider: chosen, model: event.target.value || null })
          }}
        />
      </div>

      {active && !active.selectable ? (
        <p className={styles.unavailable}>{active.detail ?? 'This provider cannot be used.'}</p>
      ) : (
        <Note>Leave the model blank to use the provider&rsquo;s configured default.</Note>
      )}
    </>
  )
}
