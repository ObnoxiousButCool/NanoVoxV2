/**
 * Re-analyse the authored corpus, with live progress (DEC-06).
 *
 * This screen spends either hours of local compute or real money, so it says
 * what it is about to do before it does it: how many calls, against which model,
 * and — for a provider that charges — that this will be billed. The confirmation
 * is not decoration; the API refuses a paid run without it.
 *
 * While a run works, the screen is driven by the event stream but never *relies*
 * on it: every figure shown comes from a progress snapshot the backend computed
 * from the run record, so a dropped connection changes nothing but latency.
 */

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ProviderPicker, type ProviderSelection } from '@/features/analyze/ProviderPicker'
import { useRunStream } from '@/features/corpus/useRunStream'
import { ApiError } from '@/shared/api/client'
import {
  useCancelRun,
  useCorpusStatus,
  useProviders,
  useRefreshAfterRun,
  useResumeRun,
  useRun,
  useRuns,
  useClearCorpus,
  useStartRun,
} from '@/shared/api/queries'
import type { CorpusRun, CorpusRunItem, RunProgress } from '@/shared/api/types'
import { cx } from '@/shared/ui/cx'
import {
  Alert,
  Button,
  Card,
  Chip,
  Empty,
  Failure,
  Loading,
  Note,
  PageHeader,
} from '@/shared/ui/primitives'
import styles from './CorpusPage.module.css'

/** Layers per call — the corpus is analyzed five times over. */
const LAYERS_PER_CALL = 5

function statusTone(status: string): 'high' | 'medium' | 'low' | 'neutral' {
  if (status === 'FAILED') return 'high'
  if (status === 'COMPLETED') return 'low'
  if (status === 'CANCELLED' || status === 'INTERRUPTED') return 'medium'
  return 'neutral'
}

function itemTone(status: string): 'high' | 'medium' | 'low' | 'neutral' {
  if (status === 'FAILED') return 'high'
  if (status === 'COMPLETED') return 'low'
  if (status === 'SKIPPED') return 'neutral'
  return 'medium'
}

function seconds(durationMs: number | null): string {
  if (durationMs === null) return ''
  return `${(durationMs / 1000).toFixed(1)}s`
}

function ProgressBar({ progress }: { progress: RunProgress }) {
  return (
    <div className={styles.progress}>
      <div
        className={styles.track}
        role="progressbar"
        aria-valuenow={Math.round(progress.percent_complete)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Corpus run progress"
      >
        <span className={styles.done} style={{ width: `${String(progress.percent_complete)}%` }} />
      </div>
      <div className={styles.counts}>
        <span>
          <b>{progress.finished}</b> of {progress.total}
        </span>
        <span className={styles.tallies}>
          {progress.completed} analyzed
          {progress.skipped > 0 ? ` · ${String(progress.skipped)} skipped` : ''}
          {progress.failed > 0 ? ` · ${String(progress.failed)} failed` : ''}
          {progress.cancelled > 0 ? ` · ${String(progress.cancelled)} cancelled` : ''}
        </span>
      </div>
    </div>
  )
}

function FinishedItem({ item }: { item: CorpusRunItem }) {
  return (
    <li className={styles.item}>
      <Chip tone={itemTone(item.status)}>{item.status}</Chip>
      <span className={styles.itemRef}>
        {item.call_id !== null ? (
          <Link to={`/calls/${String(item.call_id)}`}>{item.reference}</Link>
        ) : (
          item.reference
        )}
      </span>
      <span className={styles.itemTitle}>{item.message || item.title}</span>
      <span className={styles.itemTime}>{seconds(item.duration_ms)}</span>
    </li>
  )
}

/**
 * The live panel for the run being watched.
 *
 * Falls back to the run record whenever the stream has not said anything yet,
 * which is also what happens after a page refresh mid-run.
 */
function ActiveRun({ run, onFinished }: { run: CorpusRun; onFinished: () => void }) {
  const watching = run.is_active ? run.id : null
  const stream = useRunStream(watching)
  const cancel = useCancelRun()

  const progress = stream.latest?.progress ?? run.progress
  const status = stream.latest?.run_status ?? run.status
  const running = run.items.filter((item) => item.status === 'RUNNING')
  const finished = stream.recent.length > 0 ? stream.recent : recentFrom(run)

  useEffect(() => {
    if (stream.done) {
      onFinished()
    }
  }, [stream.done, onFinished])

  return (
    <Card
      title={`Run ${String(run.id)}`}
      actions={
        run.is_active ? (
          <Button
            disabled={cancel.isPending || status === 'CANCELLING'}
            onClick={() => {
              cancel.mutate(run.id)
            }}
          >
            {status === 'CANCELLING' ? 'Stopping…' : 'Cancel'}
          </Button>
        ) : null
      }
    >
      <div className={styles.runMeta}>
        <Chip tone={statusTone(status)}>{status}</Chip>
        <span>
          {run.provider} · {run.model}
        </span>
        {run.is_active ? (
          <span className={styles.link} aria-live="polite">
            {stream.connected ? 'Live' : 'Reconnecting…'}
          </span>
        ) : null}
      </div>

      <ProgressBar progress={progress} />

      {status === 'CANCELLING' ? (
        <Note>
          Stopping after the call in flight. The call being analyzed is left to finish rather than
          abandoned half-written.
        </Note>
      ) : null}

      {running.length > 0 && stream.latest?.kind !== 'run_finished' ? (
        <Note>
          Analysing {running.map((item) => item.reference).join(', ')}. A local model takes minutes
          per call.
        </Note>
      ) : null}

      {run.message ? <Note>{run.message}</Note> : null}

      {finished.length > 0 ? (
        <ul className={styles.items}>
          {finished.map((item) => (
            <FinishedItem key={item.source_id} item={item} />
          ))}
        </ul>
      ) : null}

      {cancel.error ? <Failure error={cancel.error} what="the cancel request" /> : null}
    </Card>
  )
}

function recentFrom(run: CorpusRun): readonly CorpusRunItem[] {
  return run.items.filter((item) => item.status !== 'PENDING' && item.status !== 'RUNNING').slice(-8)
}

export function CorpusPage() {
  const status = useCorpusStatus()
  const runs = useRuns()
  const providers = useProviders()
  const start = useStartRun()
  const clear = useClearCorpus()
  const resume = useResumeRun()
  const refreshAfterRun = useRefreshAfterRun()

  const [selection, setSelection] = useState<ProviderSelection>({ provider: null, model: null })
  const [force, setForce] = useState(false)
  const [acknowledged, setAcknowledged] = useState(false)
  const [watchedId, setWatchedId] = useState<number | null>(null)
  // Clearing is irreversible and cannot be undone from this screen, so the
  // button arms first and acts second. One stray click must not empty the
  // corpus.
  const [confirmingClear, setConfirmingClear] = useState(false)

  const activeId = status.data?.active_run_id ?? null
  const shownId = watchedId ?? activeId ?? runs.data?.[0]?.id ?? null
  const run = useRun(shownId)

  const chosen = selection.provider ?? providers.data?.default ?? null
  const provider = providers.data?.providers.find((entry) => entry.name === chosen)
  const billable = provider?.billable ?? false
  const blocked = billable && !acknowledged

  const total = status.data?.total_calls ?? 0
  const outstanding = force ? total : (status.data?.outstanding ?? 0)

  return (
    <>
      <PageHeader
        title="Corpus run"
        subtitle="Re-analyse the authored call corpus and rebuild every dashboard figure from it."
      />

      {status.isPending ? <Loading what="the corpus" /> : null}
      {status.error ? <Failure error={status.error} what="the corpus" /> : null}

      {status.data ? (
        <Card title="What will be analyzed">
          <div className={styles.summary}>
            <div>
              <b>{status.data.total_calls}</b>
              <span>calls in the corpus</span>
            </div>
            <div>
              <b>{status.data.analysed_calls}</b>
              <span>already analyzed</span>
            </div>
            <div>
              <b>{outstanding}</b>
              <span>{force ? 'to re-analyse' : 'outstanding'}</span>
            </div>
          </div>
          <Note>
            Read from <code>{status.data.location}</code>.
          </Note>

          <div className={styles.controls}>
            <ProviderPicker
              selection={selection}
              onChange={(next) => {
                setSelection(next)
                setAcknowledged(false)
              }}
              disabled={start.isPending || activeId !== null}
            />

            <label className={styles.check}>
              <input
                type="checkbox"
                checked={force}
                disabled={activeId !== null}
                onChange={(event) => {
                  setForce(event.target.checked)
                }}
              />
              Re-analyse calls that already have an analysis, replacing them
            </label>
          </div>

          {billable ? (
            <Alert tone="high" title="This run will be charged for">
              <p>
                {chosen} bills per token, and a run sends every one of the {total} calls through{' '}
                {LAYERS_PER_CALL} layers — {total * LAYERS_PER_CALL} model calls. Nothing here
                estimates the bill, because a wrong estimate would be worse than none.
              </p>
              <label className={styles.check}>
                <input
                  type="checkbox"
                  checked={acknowledged}
                  onChange={(event) => {
                    setAcknowledged(event.target.checked)
                  }}
                />
                I understand this run will be billed
              </label>
            </Alert>
          ) : null}

          <div className={styles.actions}>
            <Button
              variant="primary"
              disabled={start.isPending || activeId !== null || blocked || total === 0}
              onClick={() => {
                start.mutate(
                  {
                    provider: selection.provider,
                    model: selection.model,
                    force,
                    acknowledge_cost: acknowledged,
                  },
                  { onSuccess: (created) => { setWatchedId(created.id) } },
                )
              }}
            >
              {start.isPending ? 'Starting…' : 'Analyse the corpus'}
            </Button>
            {activeId !== null ? <Note>A run is already in progress.</Note> : null}
            {confirmingClear ? (
              <>
                <Button
                  variant="danger"
                  disabled={clear.isPending}
                  onClick={() => {
                    clear.mutate(undefined, {
                      onSuccess: () => {
                        setConfirmingClear(false)
                        setWatchedId(null)
                      },
                    })
                  }}
                >
                  {clear.isPending ? 'Clearing…' : 'Yes, delete every analysis'}
                </Button>
                <Button
                  disabled={clear.isPending}
                  onClick={() => {
                    setConfirmingClear(false)
                  }}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <Button
                disabled={activeId !== null || status.data.analysed_calls === 0}
                onClick={() => {
                  setConfirmingClear(true)
                }}
              >
                Clear analyses
              </Button>
            )}
            {!force && outstanding === 0 && total > 0 && activeId === null ? (
              <Note>
                Every call is already analyzed. Tick the box above to replace them.
              </Note>
            ) : null}
          </div>

          {confirmingClear ? (
            <Alert tone="broker" title="This deletes every analyzed call">
              All {status.data.analysed_calls} analyzed call
              {status.data.analysed_calls === 1 ? '' : 's'} and their layers, signals, scores and
              run history will be removed. The transcripts in the corpus folder are untouched, so
              they can be analyzed again. <b>Ground truth is kept</b> — it is hand-labelled and
              re-analysis cannot regenerate it. This cannot be undone.
            </Alert>
          ) : null}
          {clear.isSuccess && !confirmingClear ? (
            <Note>
              Cleared {clear.data.calls} call{clear.data.calls === 1 ? '' : 's'} and{' '}
              {clear.data.runs} run{clear.data.runs === 1 ? '' : 's'}. Ground truth was kept.
            </Note>
          ) : null}
          {clear.error ? (
            // Not <Failure>: that says "Could not load", which is the wrong verb
            // for a delete and would read as though nothing had been attempted.
            <Alert tone="high" title="The corpus was not cleared">
              {clear.error.message}
              {clear.error instanceof ApiError && clear.error.detail
                ? ` ${clear.error.detail}`
                : null}
            </Alert>
          ) : null}
          {start.error ? <Failure error={start.error} what="the run" /> : null}
        </Card>
      ) : null}

      {run.data ? (
        <div className={styles.spacer}>
          <ActiveRun run={run.data} onFinished={refreshAfterRun} />
          {run.data.can_resume ? (
            <div className={styles.actions}>
              <Button
                disabled={resume.isPending}
                onClick={() => {
                  resume.mutate(run.data.id, {
                    onSuccess: (resumed) => { setWatchedId(resumed.id) },
                  })
                }}
              >
                {resume.isPending ? 'Resuming…' : 'Resume this run'}
              </Button>
              <Note>
                {run.data.progress.remaining + run.data.progress.failed} calls still need work.
                Resuming keeps what is already done.
              </Note>
            </div>
          ) : null}
          {resume.error ? <Failure error={resume.error} what="the resume request" /> : null}
        </div>
      ) : null}

      {runs.data && runs.data.length > 0 ? (
        <Card title="Earlier runs">
          <ul className={styles.runs}>
            {runs.data.map((entry) => (
              <li key={entry.id}>
                <button
                  type="button"
                  className={cx(styles.runRow, entry.id === shownId && styles.runRowActive)}
                  onClick={() => {
                    setWatchedId(entry.id)
                  }}
                >
                  <Chip tone={statusTone(entry.status)}>{entry.status}</Chip>
                  <span className={styles.runId}>Run {entry.id}</span>
                  <span className={styles.runModel}>
                    {entry.provider} · {entry.model}
                  </span>
                  <span className={styles.runCounts}>
                    {entry.progress.completed}/{entry.progress.total} analyzed
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {runs.data && runs.data.length === 0 ? (
        <Card>
          <Empty title="No runs yet">
            Nothing has been analyzed in bulk. Starting a run rebuilds every dashboard figure from
            the corpus.
          </Empty>
        </Card>
      ) : null}
    </>
  )
}
