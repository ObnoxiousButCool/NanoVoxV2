/**
 * The application shell: collapsible navigation rail plus the content area.
 *
 * Collapsed, the rail shows icons only, and every link keeps its accessible name
 * plus a tooltip — an icon nobody can identify is not a smaller menu, it is a
 * worse one.
 */

import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { visibleNavigation } from '@/app/layout/navigation'
import { getConfig } from '@/shared/config/env'
import {
  SHOW_PROVIDER_STATUS,
  SHOW_RAIL_STATUS,
  providerStatus,
} from '@/app/layout/providerStatus'
import { useHealth, useProviders } from '@/shared/api/queries'
import { useCollapsibleRail } from '@/shared/hooks/useCollapsibleRail'
import { cx } from '@/shared/ui/cx'
import styles from './AppShell.module.css'

function RailStatus({ collapsed }: { collapsed: boolean }) {
  const { data, isError } = useHealth()
  const providers = useProviders()
  const down = isError || data?.status === 'down'
  const status = providerStatus(providers.data)

  // Hidden, not removed. The health and provider queries above still run — they
  // are shared with the rest of the app and cost nothing extra — so flipping the
  // switch brings the block straight back with no other change.
  if (!SHOW_RAIL_STATUS) {
    return null
  }

  if (collapsed) {
    const healthy = SHOW_PROVIDER_STATUS ? `Backend healthy — ${status.detail}` : 'Backend healthy'
    const label = down ? 'Backend unreachable' : healthy
    return (
      <span
        className={cx(styles.dot, down && styles.dotDown)}
        title={label}
        aria-label={label}
        role="img"
      />
    )
  }

  return (
    <>
      <span className={cx(styles.dot, down && styles.dotDown)} aria-hidden="true" />
      {/* Each line is its own element rather than text either side of a <br>:
          the second is a privacy statement, and it should be addressable on its
          own by anything reading the page. */}
      <span className={styles.statusHeadline}>
        {down ? 'Backend unreachable' : 'Backend healthy'}
      </span>
      {down ? (
        <span className={styles.statusDetail}>Check that the API is running</span>
      ) : SHOW_PROVIDER_STATUS ? (
        <span className={styles.statusDetail}>{status.detail}</span>
      ) : null}
    </>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const { collapsed, toggle } = useCollapsibleRail()

  const toggleLabel = collapsed ? 'Expand navigation' : 'Collapse navigation'

  return (
    <div className={styles.app} data-collapsed={String(collapsed)}>
      <nav
        className={cx(styles.rail, collapsed && styles.collapsed)}
        aria-label="Main navigation"
      >
        <div className={styles.brand}>
          {collapsed ? (
            <span className={styles.mark} aria-hidden="true">
              N
            </span>
          ) : (
            <span className={styles.brandText}>
              <b>NanoVox</b>
              <span>Call Intelligence</span>
            </span>
          )}
          {!collapsed && (
            <button
              type="button"
              className={styles.toggle}
              onClick={toggle}
              aria-expanded={!collapsed}
              aria-label={toggleLabel}
              title={toggleLabel}
            >
              «
            </button>
          )}
        </div>

        {collapsed && (
          <button
            type="button"
            className={cx(styles.toggle, styles.collapsedToggle)}
            onClick={toggle}
            aria-expanded={!collapsed}
            aria-label={toggleLabel}
            title={toggleLabel}
          >
            »
          </button>
        )}

        <div className={styles.nav}>
          {visibleNavigation(getConfig()).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={styles.link ?? ''}
              title={collapsed ? item.label : item.description}
            >
              <span className={styles.glyph} aria-hidden="true">
                {item.glyph}
              </span>
              {/* The label is always in the DOM so the link keeps its
                  accessible name; it is only hidden visually when collapsed. */}
              <span className={collapsed ? 'visually-hidden' : undefined}>{item.label}</span>
            </NavLink>
          ))}
        </div>

        <footer className={styles.footer}>
          <RailStatus collapsed={collapsed} />
        </footer>
      </nav>

      <main className={styles.main}>{children}</main>
    </div>
  )
}
