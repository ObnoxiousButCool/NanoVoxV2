/**
 * Diagnostics: is the backend reachable, and is each of its components up?
 *
 * The first screen built, because it is the one that answers "why is nothing
 * loading?" — and it demonstrates the loading, empty and error states every data
 * surface in this application is required to have.
 */

import type { ComponentHealth, ComponentStatus } from '@/shared/api/types'
import { useHealth } from '@/shared/api/queries'
import { PageHeader } from '@/shared/ui/primitives'
import { ApiError, NetworkError } from '@/shared/api/client'
import { cx } from '@/shared/ui/cx'
import styles from './DiagnosticsPage.module.css'

function StatusBadge({ status }: { status: ComponentStatus }) {
  const variant = status === 'up' ? styles.badgeUp : styles.badgeDown
  return <span className={cx(styles.badge, variant)}>{status.toUpperCase()}</span>
}

function ComponentRow({ component }: { component: ComponentHealth }) {
  return (
    <div className={styles.row}>
      <dt>{component.name}</dt>
      <dd>
        <StatusBadge status={component.status} />
        {component.detail ? ` ${component.detail}` : null}
      </dd>
    </div>
  )
}

function ErrorPanel({ error }: { error: Error }) {
  const correlationId = error instanceof ApiError ? error.correlationId : null
  const description =
    error instanceof NetworkError
      ? 'The API did not respond. Check that the backend is running and that VITE_API_BASE_URL points at it.'
      : error.message

  return (
    <div className={styles.alert} role="alert">
      <strong>Cannot reach the NanoVox API</strong>
      {description}
      {correlationId ? (
        <p className={styles.correlation}>Correlation ID: {correlationId}</p>
      ) : null}
    </div>
  )
}

export function DiagnosticsPage() {
  const { data, error, isPending, isFetching } = useHealth()

  return (
    <>
      <PageHeader
        title="Diagnostics"
        subtitle="Live status of the backend and every dependency it declares."
      />

      <section className={styles.card} aria-labelledby="system-status">
        <div className={styles.cardHeader}>
          <h2 id="system-status">System status</h2>
          {data ? <StatusBadge status={data.status} /> : null}
        </div>
        <div className={styles.body}>
          {isPending ? <p role="status">Checking…</p> : null}

          {error ? <ErrorPanel error={error} /> : null}

          {data ? (
            <>
              <dl>
                <div className={styles.row}>
                  <dt>Application</dt>
                  <dd>{data.application}</dd>
                </div>
                <div className={styles.row}>
                  <dt>Version</dt>
                  <dd>{data.version}</dd>
                </div>
                <div className={styles.row}>
                  <dt>Environment</dt>
                  <dd>{data.environment}</dd>
                </div>
                <div className={styles.row}>
                  <dt>Checked at</dt>
                  <dd>{new Date(data.checked_at).toLocaleString()}</dd>
                </div>
                {(data.components ?? []).map((component) => (
                  <ComponentRow key={component.name} component={component} />
                ))}
              </dl>
              {(data.components ?? []).length === 0 ? (
                <p className={styles.note}>
                  The backend declares no dependencies to check. Shown so the absence is
                  visible rather than implied.
                </p>
              ) : null}
              <p className={styles.note}>
                Refreshes every 30 seconds.{isFetching ? ' Refreshing…' : ''}
              </p>
            </>
          ) : null}
        </div>
      </section>
    </>
  )
}
