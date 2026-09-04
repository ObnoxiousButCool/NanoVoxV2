/**
 * The small set of building blocks every screen uses.
 *
 * Deliberately thin: each maps to a rule already in the prototype's stylesheet,
 * so the built application and the approved design cannot drift.
 */

import { useEffect, useId, useRef, useState } from 'react'
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

/**
 * How a figure is counted, behind an icon rather than under the chart.
 *
 * These explanations earn their place — a reader who does not know that a
 * category resolving nothing shows a dash instead of a zero will misread the
 * chart — but they are read once and then never again, while the chart is read
 * every day. As standing paragraphs they were most of the text on the screen.
 *
 * Opens on hover **and** on keyboard focus, and the trigger is a real button so
 * a touch device gets it too. Hover alone would put the explanation out of
 * reach of anyone not using a mouse. Escape closes it; the content is linked to
 * the button by `aria-describedby`, so a screen reader reaches it without any
 * of that.
 */
export function Hint({ children, label = 'How this is counted' }: { children: ReactNode; label?: string }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const wrapper = useRef<HTMLSpanElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    // A click anywhere else dismisses it. Without this a panel opened by tap
    // stays open until the same icon is tapped again, which reads as stuck.
    const onClick = (event: MouseEvent) => {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('click', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('click', onClick)
    }
  }, [open])

  return (
    <span
      className={styles.hint}
      ref={wrapper}
      onMouseEnter={() => {
        setOpen(true)
      }}
      onMouseLeave={() => {
        // Not while it is focused: a keyboard user whose mouse happens to pass
        // over the icon would otherwise have the panel taken away from them.
        if (document.activeElement !== button.current) setOpen(false)
      }}
    >
      <button
        type="button"
        ref={button}
        className={styles.hintButton}
        aria-label={label}
        aria-expanded={open}
        aria-describedby={id}
        // Opens rather than toggles. A press focuses the button first, which
        // opens the panel, so a toggle here would close it again in the same
        // gesture — on a touch screen that means it never opens at all.
        // Escape, a press outside, or leaving the icon all close it.
        onClick={() => {
          setOpen(true)
        }}
        onFocus={() => {
          setOpen(true)
        }}
        onBlur={() => {
          setOpen(false)
        }}
      >
        i
      </button>
      {/* Rendered whether or not it is open, so `aria-describedby` always has
          something to point at and the text is reachable without the icon ever
          being operated. `hidden` rather than a conditional render for the same
          reason. */}
      <span className={styles.hintPanel} id={id} role="note" hidden={!open}>
        {children}
      </span>
    </span>
  )
}

export function Card({
  title,
  subtitle,
  actions,
  hint,
  children,
  className,
}: {
  title?: string | undefined
  subtitle?: string | undefined
  /** Controls that act on this card, placed opposite its title. */
  actions?: ReactNode
  /** How this card's figures are counted. Shown behind an icon by its title. */
  hint?: ReactNode
  children: ReactNode
  className?: string | undefined
}) {
  return (
    <section className={cx(styles.card, className)}>
      {title ? (
        <div className={styles.cardHeader}>
          <div className={styles.cardTitle}>
            {/* The icon is a sibling of the heading, not a child of it. Nested,
                the panel's prose became part of the heading's own text, so a
                screen reader announcing the card read the whole explanation as
                the title. */}
            <div className={styles.titleRow}>
              <h3>{title}</h3>
              {hint ? <Hint>{hint}</Hint> : null}
            </div>
            {subtitle ? <p>{subtitle}</p> : null}
          </div>
          {actions}
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
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'primary' | 'danger' }) {
  return (
    <button
      type="button"
      className={cx(
        styles.button,
        variant === 'primary' && styles.buttonPrimary,
        // 'danger' is for the second press of a destructive action, never the
        // first: it should look different from the button that armed it.
        variant === 'danger' && styles.buttonDanger,
        className,
      )}
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
