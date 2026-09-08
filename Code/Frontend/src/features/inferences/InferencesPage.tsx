/**
 * The inferences: what the system concluded from the calls, ranked, with an
 * owner and a way through to the evidence.
 *
 * This was a card at the top of the dashboard. It outgrew that: a dashboard
 * card answers "is anything wrong" in one glance, and the answer here is a
 * worklist somebody owns and works through. Six items with a paragraph of
 * reasoning each were pushing everything a leader reads for direction — the
 * weekly trend, the totals — below the fold.
 *
 * Two rules govern the screen, both stated on it rather than left implicit:
 *
 * * **Every figure is counted, never written by a model.** A claim like "13 of
 *   50 calls raise a Process Breakdown finding" is either counted or invented,
 *   and only the counted version can be acted on. The thresholds that decide
 *   what appears live in `dashboard.yaml`, so the business owns them.
 * * **Every item opens its own evidence.** An inference the reader cannot check
 *   is one they have to take on trust. The query that reproduces each count
 *   comes from the API rather than being rebuilt here — see `call_filter`.
 */

import { Link } from 'react-router-dom'

import { useOverview } from '@/shared/api/queries'
import type { Overview } from '@/shared/api/types'
import { Card, Chip, Empty, Failure, Loading, Note, PageHeader } from '@/shared/ui/primitives'
import { cx } from '@/shared/ui/cx'
import styles from '@/shared/ui/queue.module.css'

type AttentionItem = Overview['attention'][number]

function severityClass(severity: string): string | undefined {
  if (severity === 'CRITICAL' || severity === 'HIGH') return styles.itemHigh
  if (severity === 'MEDIUM') return styles.itemMedium
  return styles.itemLow
}

/**
 * Where an item's evidence lives, as a calls-list address.
 *
 * The parameters are the server's, not this page's: the rule kinds are a
 * backend vocabulary, and a client deriving the query itself would produce a
 * link that silently returned every call the first time a kind was added. An
 * item whose filter is empty gets no link rather than a link to everything.
 */
function evidenceHref(item: AttentionItem): string | null {
  const entries = Object.entries(item.call_filter)
  if (entries.length === 0) return null

  const query = new URLSearchParams(entries)
  return `/calls?${query.toString()}`
}

function InferenceItem({ item }: { item: AttentionItem }) {
  const href = evidenceHref(item)
  const calls = item.count === 1 ? 'call' : 'calls'

  return (
    <article className={cx(styles.item, severityClass(item.severity))}>
      <div>
        <h4>
          {href ? (
            <Link className={styles.nameLink} to={href}>
              {item.title}
            </Link>
          ) : (
            item.title
          )}
        </h4>
        <p className={styles.why}>{item.why}</p>
        <div className={styles.meta}>
          <span className={styles.owner}>{item.owner}</span>
          <Chip tone="high">{item.severity}</Chip>
          {item.references.length > 0 ? (
            <span className={styles.reference}>
              <Chip>{item.references.slice(0, 6).join(' ')}</Chip>
            </span>
          ) : null}
          {href ? (
            /* Stated as well as linked from the title. A heading that navigates
               is easy to miss, and the whole point of the screen is that the
               reader can go and check the claim. */
            <Link className={styles.action} to={href}>
              Open {item.count} {calls} in call history →
            </Link>
          ) : null}
        </div>
      </div>
      <div className={styles.count}>
        <b>{item.count}</b>
        <span>{item.unresolved > 0 ? `CALLS · ${String(item.unresolved)} OPEN` : 'CALLS'}</span>
      </div>
    </article>
  )
}

export function InferencesPage() {
  const overview = useOverview()

  if (overview.isPending) return <Loading what="the inferences" />
  if (overview.error) return <Failure error={overview.error} what="the inferences" />

  const items = overview.data.attention

  return (
    <>
      <PageHeader title="Inferences" />

      {items.length === 0 ? (
        <Card title="Nothing has crossed a threshold">
          <Empty title="No inference to report">
            <Note>
              {/* The distinction matters operationally: one of these means the
                  system is working and the month was clean, the other means
                  nobody would know if it were not. */}
              The rules ran and found nothing — which is not the same as nothing
              having been checked. What counts as worth raising, and how many
              calls it takes, lives in <code>dashboard.yaml</code>.
            </Note>
          </Empty>
        </Card>
      ) : (
        <>
          <div className={styles.queue}>
            {items.map((item) => (
              <InferenceItem key={`${item.rule_id}-${item.subject}`} item={item} />
            ))}
          </div>
        </>
      )}
    </>
  )
}
