/**
 * One call, in full: the five layers, the evidence, and the transcript.
 *
 * The prototype's Call #89 is the reference. Two things it does that a
 * conventional detail page would not, and that are reproduced here deliberately:
 *
 * * A withheld score is shown **with** its number and the reason, not hidden. A
 *   reviewer needs to know how bad the call looks while it waits for sign-off.
 * * A layer that found nothing and a layer that could not run are drawn
 *   differently. "Nothing fired" is a finding; "L5 unavailable" is a fault, and
 *   presenting the second as the first would hide a broken pipeline.
 */

import type { ReactNode } from 'react'
import { useParams } from 'react-router-dom'

import { useCall } from '@/shared/api/queries'
import type { Analysis, Layer } from '@/shared/api/types'
import { LAYER_META, type LayerId } from '@/shared/api/types'
import {
  Alert,
  Card,
  Chip,
  Failure,
  Loading,
  Note,
  PageHeader,
} from '@/shared/ui/primitives'
import { toneForResolution, toneForSeverity } from '@/shared/ui/tone'
import { cx } from '@/shared/ui/cx'
import { TranscriptView } from './TranscriptView'
import styles from './CallDetail.module.css'

const BADGE_CLASS: Record<LayerId, string | undefined> = {
  L1: styles.badgeL1,
  L2: styles.badgeL2,
  L3: styles.badgeL3,
  L4: styles.badgeL4,
  L5: styles.badgeL5,
}

function ringClass(tier: string): string | undefined {
  if (tier === 'GOOD') return styles.ringGood
  if (tier === 'AVERAGE') return styles.ringAverage
  return styles.ringPoor
}

function layerPayload(analysis: Analysis, id: LayerId): Record<string, unknown> {
  const layer: Layer | undefined = analysis.layers.find((item) => item.layer === id)
  return (layer?.payload ?? {})
}

function isUnavailable(payload: Record<string, unknown>): boolean {
  return payload['unavailable'] === true
}

function text(payload: Record<string, unknown>, key: string): string {
  const value = payload[key]
  return typeof value === 'string' ? value : ''
}

function list(payload: Record<string, unknown>, key: string): string[] {
  const value = payload[key]
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function LayerBlock({
  id,
  children,
  unavailableReason,
}: {
  id: LayerId
  children: ReactNode
  unavailableReason?: string | undefined
}) {
  const meta = LAYER_META[id]
  return (
    <div className={styles.layer}>
      <div className={cx(styles.badge, BADGE_CLASS[id])}>{id}</div>
      <h3>{meta.title}</h3>
      <div className={styles.layerSub}>{meta.subtitle}</div>
      <div className={styles.box}>
        {unavailableReason ? (
          <Alert title={`${id} could not be produced`}>
            {unavailableReason}
            <Note>
              This is a failure, not an empty result. The rest of the analysis is unaffected.
            </Note>
          </Alert>
        ) : (
          children
        )}
      </div>
    </div>
  )
}

export function CallDetailPage() {
  const params = useParams<{ callId: string }>()
  const callId = Number(params.callId)
  const { data, isPending, error } = useCall(callId)

  if (isPending) {
    return <Loading what="the call" />
  }
  if (error) {
    return <Failure error={error} what="this call" />
  }

  const l1 = layerPayload(data, 'L1')
  const l2 = layerPayload(data, 'L2')
  const l4 = layerPayload(data, 'L4')
  const l5 = layerPayload(data, 'L5')
  const provisional = data.score.status === 'provisional'
  const gaps = data.assist_events.filter((event) => event.is_gap)

  return (
    <>
      <PageHeader
        title={`Call ${data.reference}`}
        subtitle={[
          data.category_label,
          data.duration_minutes ? `${String(data.duration_minutes)} min` : null,
          `${String(data.transcript.length)} turns`,
        ]
          .filter(Boolean)
          .join(' · ')}
      />

      {provisional ? (
        <div style={{ marginBottom: 14 }}>
          <Alert title={data.score.gate_messages[0] ?? 'Score withheld'}>
            The rubric score of {data.score.value} is provisional. Calls raising this signal are
            reviewed by a clinician before a score is confirmed.
          </Alert>
        </div>
      ) : null}

      <div className={styles.layout}>
        <div>
          <div className={styles.hero}>
            <div className={cx(styles.ring, ringClass(data.score.tier))}>{data.score.value}</div>
            <div>
              <h2>{data.title}</h2>
              <p>{data.summary}</p>
              <div className={styles.chips}>
                <Chip tone={toneForResolution(data.resolution)}>{data.resolution}</Chip>
                {data.signal_codes.map((code) => (
                  <Chip key={code} tone="high">
                    {code.replace(/_/g, ' ')}
                  </Chip>
                ))}
                {data.agent_name ? <Chip>Agent: {data.agent_name}</Chip> : null}
              </div>
            </div>
          </div>

          <LayerBlock id="L1" unavailableReason={isUnavailable(l1) ? text(l1, 'reason') : undefined}>
            <dl>
              <div className={styles.kv}>
                <dt>Call type</dt>
                <dd>{text(l1, 'call_type') || '—'}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Member sentiment</dt>
                <dd>
                  {data.sentiment_start} → {data.sentiment_end}
                </dd>
              </div>
              <div className={styles.kv}>
                <dt>Agent tone</dt>
                <dd>{text(l1, 'agent_tone') || '—'}</dd>
              </div>
            </dl>
            <div className={styles.chips} style={{ marginTop: 10 }}>
              {list(l1, 'key_terms').map((term) => (
                <Chip key={term}>{term}</Chip>
              ))}
            </div>
          </LayerBlock>

          <LayerBlock id="L2" unavailableReason={isUnavailable(l2) ? text(l2, 'reason') : undefined}>
            <p className={styles.summary}>{data.summary}</p>
            <div className={styles.chips}>
              {list(l2, 'topics').map((topic) => (
                <Chip key={topic}>{topic}</Chip>
              ))}
            </div>
          </LayerBlock>

          <LayerBlock id="L3">
            {data.markers.length === 0 ? (
              <Note>No observations survived evidence checking for this call.</Note>
            ) : (
              data.markers.map((marker, index) => (
                <div
                  key={`${marker.dimension}-${String(index)}`}
                  className={cx(
                    styles.marker,
                    marker.polarity === 'POSITIVE' ? styles.markerPositive : styles.markerNegative,
                  )}
                >
                  <i className={styles.markerIcon}>{marker.polarity === 'POSITIVE' ? '✓' : '✕'}</i>
                  <span>
                    {marker.description}
                    <a
                      className={styles.markerQuote}
                      href={`#turn-${String(marker.evidence_turn_seq)}`}
                    >
                      turn {marker.evidence_turn_seq}: &ldquo;{marker.quote}&rdquo;
                    </a>
                  </span>
                </div>
              ))
            )}
            {data.rejected_marker_notes.length > 0 ? (
              <Note>
                {data.rejected_marker_notes.length} observation
                {data.rejected_marker_notes.length === 1 ? ' was' : 's were'} discarded because the
                quoted evidence did not appear in the transcript.
              </Note>
            ) : null}
          </LayerBlock>

          <LayerBlock id="L4" unavailableReason={isUnavailable(l4) ? text(l4, 'reason') : undefined}>
            <div className={styles.stack}>
              {data.l4_signals.length === 0 ? (
                <Note>No operational findings were raised by this call.</Note>
              ) : (
                data.l4_signals.map((signal, index) => (
                  <Alert
                    key={`${signal.category}-${String(index)}`}
                    tone={toneForSeverity(signal.severity)}
                    title={`${signal.category.replace(/_/g, ' ')} · Owner: ${signal.owner}`}
                  >
                    {signal.narrative}
                    {signal.recommended_action ? <p>{signal.recommended_action}</p> : null}
                  </Alert>
                ))
              )}
              {data.broker_signals.map((signal, index) => (
                <Alert
                  key={`broker-${String(index)}`}
                  tone="broker"
                  title={`Broker attribution · ${signal.broker_name}`}
                >
                  {signal.issue}
                  <p className={styles.markerQuote}>
                    Member said, turn {signal.evidence_turn_seq}: &ldquo;{signal.quote}&rdquo;
                  </p>
                </Alert>
              ))}
              {data.rejected_attribution_notes.length > 0 ? (
                <Note>
                  {data.rejected_attribution_notes.length} broker attribution
                  {data.rejected_attribution_notes.length === 1 ? ' was' : 's were'} discarded for
                  lack of evidence.
                </Note>
              ) : null}
            </div>
          </LayerBlock>

          <LayerBlock id="L5" unavailableReason={isUnavailable(l5) ? text(l5, 'reason') : undefined}>
            {data.assist_events.length === 0 ? (
              <Note>No assist activity was recorded for this call.</Note>
            ) : (
              <div className={styles.stack}>
                {data.assist_events.map((event, index) => (
                  <div key={`assist-${String(index)}`}>
                    {event.is_gap ? (
                      <div className={styles.miss}>
                        <strong>
                          Did not fire{event.timestamp_label ? ` · ${event.timestamp_label}` : ''}
                        </strong>
                        {event.trigger}. {event.recommendation}
                      </div>
                    ) : (
                      <Alert tone="low" title={`Fired · ${event.trigger}`}>
                        {event.recommendation}
                      </Alert>
                    )}
                  </div>
                ))}
              </div>
            )}
            {gaps.length > 0 ? (
              <Note>
                Shown as a gap rather than an empty state, because the absence is the finding.
              </Note>
            ) : null}
          </LayerBlock>

          <div className={styles.layer}>
            <div className={cx(styles.badge, styles.badgeTr)}>TR</div>
            <h3>Transcript</h3>
            <div className={styles.layerSub}>
              {data.transcript.length} turns · speaker separated
            </div>
            <div className={styles.box}>
              <TranscriptView turns={data.transcript} markers={data.markers} />
            </div>
          </div>
        </div>

        <aside>
          <Card title="Call" className={styles.sidebarCard}>
            <dl>
              <div className={styles.kv}>
                <dt>Reference</dt>
                <dd>{data.reference}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Category</dt>
                <dd>{data.category_label}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Outcome</dt>
                <dd>{data.resolution}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Agent</dt>
                <dd>{data.agent_name ?? '—'}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Source</dt>
                <dd>{data.source}</dd>
              </div>
            </dl>
            {data.member_context ? <Note>{data.member_context}</Note> : null}
          </Card>

          <Card title="How this score was reached" className={styles.sidebarCard}>
            <dl>
              <div className={styles.kv}>
                <dt>Score</dt>
                <dd>
                  {data.score.value} · {data.score.tier}
                </dd>
              </div>
              <div className={styles.kv}>
                <dt>Status</dt>
                <dd>{data.score.status}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Penalties</dt>
                <dd>−{data.score.total_negative}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Offset by positives</dt>
                <dd>+{data.score.applied_offset}</dd>
              </div>
            </dl>
            <Note>
              Computed from a fixed rubric, not written by the model. Every deduction traces to a
              quoted line above.
            </Note>
          </Card>

          <Card title="Provenance" className={styles.sidebarCard}>
            <dl>
              <div className={styles.kv}>
                <dt>Provider</dt>
                <dd>{data.provenance.provider}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Model</dt>
                <dd>{data.provenance.model}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Rubric</dt>
                <dd>{data.provenance.rubric_version}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Prompts</dt>
                <dd>{data.provenance.prompt_version}</dd>
              </div>
              <div className={styles.kv}>
                <dt>Tokens</dt>
                <dd>
                  {data.provenance.input_tokens}+{data.provenance.output_tokens}
                </dd>
              </div>
            </dl>
          </Card>
        </aside>
      </div>
    </>
  )
}
