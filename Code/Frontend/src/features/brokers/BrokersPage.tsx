/**
 * Broker conduct signals members named aloud during calls.
 *
 * This screen names real people, so the rule governing it is stated on the page
 * rather than left implicit: a signal exists only where the member said the
 * broker's name, and every one links to the call it came from.
 *
 * Scoring is net, not cumulative. A broker with one error against otherwise
 * strong performance is a coaching signal, not a conduct case — treating every
 * error as conduct would make the scorecard unusable, and unfair.
 */

import { Link } from 'react-router-dom'

import { useBrokers } from '@/shared/api/queries'
import type { BrokerScorecard } from '@/shared/api/types'
import { Alert, Card, Chip, Empty, Failure, Loading, Note, PageHeader } from '@/shared/ui/primitives'
import { cx } from '@/shared/ui/cx'
import styles from '@/features/overview/OverviewPage.module.css'

function BrokerCard({ broker }: { broker: BrokerScorecard }) {
  const netPositive = broker.is_net_positive

  return (
    <article className={cx(styles.item, netPositive ? styles.itemLow : styles.itemBroker)}>
      <div>
        <h4>{broker.broker_name}</h4>
        <p className={styles.why}>
          {netPositive
            ? `Net positive: ${String(broker.positive)} of ${String(broker.signals)} signals reflect well on this broker.`
            : `${String(broker.negative)} of ${String(broker.signals)} signals record a failure members reported themselves.`}
        </p>
        <div className={styles.meta}>
          <Chip tone={netPositive ? 'low' : 'broker'}>
            {netPositive ? 'Best practice' : 'Conduct review'}
          </Chip>
          {broker.call_references.map((reference) => (
            <span key={reference} className={styles.reference}>
              <Chip>{reference}</Chip>
            </span>
          ))}
        </div>
      </div>
      <div className={styles.count}>
        <b>{broker.signals}</b>
        <span>
          {broker.positive} POSITIVE · {broker.negative} NEGATIVE
        </span>
      </div>
    </article>
  )
}

export function BrokersPage() {
  const { data, isPending, error } = useBrokers()

  const totalSignals = data?.reduce((sum, broker) => sum + broker.signals, 0) ?? 0

  return (
    <>
      <PageHeader
        title="Brokers"
        subtitle={
          data && data.length > 0
            ? `${String(totalSignals)} signals across ${String(data.length)} named brokers.`
            : 'Conduct signals members named aloud during calls.'
        }
      />

      <div style={{ marginBottom: 16 }}>
        <Alert tone="broker" title="How attribution works">
          A signal is recorded only when the member names the broker in the call, or the member ID
          resolves to a broker of record. Nothing is inferred, and an attribution whose quoted
          evidence does not appear in the transcript is discarded rather than stored.
        </Alert>
      </div>

      {isPending ? <Loading what="brokers" /> : null}
      {error ? <Failure error={error} what="the broker scorecard" /> : null}

      {data && data.length === 0 ? (
        <Card>
          <Empty title="No broker signals recorded">
            No member has named a broker in an analysed call. Shown as an empty result rather than
            omitted, so the absence is visible.
          </Empty>
        </Card>
      ) : null}

      {data && data.length > 0 ? (
        <>
          <div className={styles.queue}>
            {data.map((broker) => (
              <BrokerCard key={broker.broker_name} broker={broker} />
            ))}
          </div>
          <Note>
            Scoring is net, not cumulative. Every signal links to the call that produced it — open
            one from <Link to="/calls">Calls</Link> to read the sentence behind it.
          </Note>
        </>
      ) : null}
    </>
  )
}
