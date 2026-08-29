/**
 * Provider and model selection.
 *
 * Unusable providers are listed with the reason rather than hidden (D3): a user
 * whose choice has silently vanished has no idea why, whereas "OPENAI_API_KEY is
 * not set" tells them exactly what to do.
 *
 * The provider is chosen here; the model is not. It is shown read-only because it
 * is a property of the provider's configuration — an editable box invites a typo
 * that the API would accept as a genuine model name, and on the corpus screen
 * that mistake is only visible a hundred calls later.
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
        <span className={styles.label} id="model-label">
          Model
        </span>
        {/* Shown, not offered. The model belongs to the provider's configuration,
            and a typo here would reach the API as a real model name — on the
            corpus screen, a hundred calls after the mistake was made. */}
        <p className={styles.readOnlyValue} aria-labelledby="model-label">
          {active?.model ?? '—'}
        </p>
      </div>

      {active && !active.selectable ? (
        <p className={styles.unavailable}>{active.detail ?? 'This provider cannot be used.'}</p>
      ) : (
        <Note>
          The model is set per provider in the backend configuration, so a run cannot be sent to
          one that was mistyped here.
        </Note>
      )}
    </>
  )
}
