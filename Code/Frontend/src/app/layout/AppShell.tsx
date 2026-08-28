/**
 * The application shell: collapsible navigation rail plus the content area.
 *
 * Collapsed, the rail shows icons only, and every link keeps its accessible name
 * plus a tooltip — an icon nobody can identify is not a smaller menu, it is a
 * worse one.
 */

import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { NAVIGATION } from '@/app/layout/navigation'
import { useHealth } from '@/shared/api/queries'
import { useCollapsibleRail } from '@/shared/hooks/useCollapsibleRail'
import { cx } from '@/shared/ui/cx'
import styles from './AppShell.module.css'

function RailStatus({ collapsed }: { collapsed: boolean }) {
  const { data, isError } = useHealth()
  const down = isError || data?.status === 'down'

  if (collapsed) {
    return (
      <span
        className={cx(styles.dot, down && styles.dotDown)}
        title={down ? 'Backend unreachable' : 'Backend healthy'}
        aria-label={down ? 'Backend unreachable' : 'Backend healthy'}
        role="img"
      />
    )
  }

  return (
    <>
      <span className={cx(styles.dot, down && styles.dotDown)} aria-hidden="true" />
      {down ? 'Backend unreachable' : 'Local model · on-prem'}
      <br />
      {down ? 'Check that the API is running' : 'Nothing leaves this environment'}
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
          {NAVIGATION.map((item) => (
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
