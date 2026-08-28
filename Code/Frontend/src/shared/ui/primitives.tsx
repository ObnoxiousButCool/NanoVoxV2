/**
 * The small set of building blocks every screen uses.
 *
 * Deliberately thin: each maps to a rule already in the prototype's stylesheet,
 * so the built application and the approved design cannot drift.
 */

import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { ApiError, NetworkError } from '@/shared/api/client'
import { cx } from '@/shared/ui/cx'
import type { Tone } from '@/shared/ui/tone'
import styles from './primitives.module.css'

const CHIP_TONE: Record<Tone, string | undefined> = {
  neutral: undefined,
  high: styles.chipHi,
  medium: styles.chipMd,
  low: styles.chipLo,
  broker: styles.chipBrk,
}

const ALERT_TONE: Record<Tone, string | undefined> = {
  neutral: styles.alertMd,
  high: styles.alertHi,
  medium: styles.alertMd,
  low: styles.alertHi,
  broker: styles.alertBrk,
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string | undefined
  actions?: ReactNode | undefined
}) {
  return (
    <header className={styles.pageHeader}>
      <div>
        <h1>{title}</h1>
        {subtitle ? <p>{subtitle}</p> : null}
      </div>
      {actions ? <div>{actions}</div> : null}
    </header>
  )
}

export function Card({
  title,
  subtitle,
  children,
  className,
}: {
  title?: string | undefined
  subtitle?: string | undefined
  children: ReactNode
  className?: string | undefined
}) {
  return (
    <section className={cx(styles.card, className)}>
      {title ? (
        <div className={styles.cardHeader}>
          <h3>{title}</h3>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
      ) : null}
      <div className={styles.pad}>{children}</div>
    </section>
  )
}

export function Chip({
  tone = 'neutral',
  children,
}: {
  tone?: Tone | undefined
  children: ReactNode
}) {
  return <span className={cx(styles.chip, CHIP_TONE[tone])}>{children}</span>
}

export function Alert({
  tone = 'high',
  title,
  children,
}: {
  tone?: Tone | undefined
  title?: string | undefined
  children: ReactNode
}) {
  return (
    <div className={cx(styles.alert, ALERT_TONE[tone])} role="alert">
      {title ? <strong>{title}</strong> : null}
      {children}
    </div>
  )
}

export function Button({
  variant = 'default',
  className,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' }) {
  return (
    <button
      type="button"
      className={cx(styles.button, variant === 'primary' && styles.buttonPrimary, className)}
      {...props}
    />
  )
}

export function Note({ children }: { children: ReactNode }) {
  return <p className={styles.note}>{children}</p>
}

export function Loading({ what }: { what: string }) {
  return (
    <p className={styles.state} role="status">
      Loading {what}…
    </p>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className={styles.state}>
      <p className={styles.stateTitle}>{title}</p>
      {children}
    </div>
  )
}

/**
 * A failure the user can act on.
 *
 * The correlation ID is shown because it is the one thing that ties what they
 * saw to the server-side log; "something went wrong" is not reportable.
 */
export function Failure({ error, what }: { error: Error; what: string }) {
  const correlationId = error instanceof ApiError ? error.correlationId : null
  const detail =
    error instanceof NetworkError
      ? 'The API did not respond. Check that the backend is running.'
      : error.message

  return (
    <div className={styles.state}>
      <Alert title={`Could not load ${what}`}>
        {detail}
        {correlationId ? (
          <p className={styles.correlation}>Correlation ID: {correlationId}</p>
        ) : null}
      </Alert>
    </div>
  )
}
