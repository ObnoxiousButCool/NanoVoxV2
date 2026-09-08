/**
 * Paste a transcript and run the five-layer analysis.
 *
 * The wait is the design problem here: a local model takes minutes on a full
 * transcript. The screen says so before the user commits, and keeps saying it
 * while the request is in flight, rather than showing a spinner that looks stuck.
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAnalyzeTranscript } from '@/shared/api/queries'
import { ApiError, NetworkError } from '@/shared/api/client'
import { Alert, Button, Card, Note, PageHeader } from '@/shared/ui/primitives'
import { countTurns, transcriptWarning } from './countTurns'
import styles from './AnalyzePage.module.css'

const PLACEHOLDER = `Agent Sarah: Choice Administrators member services, this is Sarah.
Member: Hi, I have a question about a claim I received...`

function AnalysisFailure({ error }: { error: Error }) {
  const correlationId = error instanceof ApiError ? error.correlationId : null
  const detail = error instanceof ApiError ? error.detail : null

  const message =
    error instanceof NetworkError
      ? 'The API did not respond. Check that the backend is running.'
      : error.message

  return (
    <Alert title="The analysis did not complete">
      {message}
      {detail ? <p>{detail}</p> : null}
      {correlationId ? <p>Correlation ID: {correlationId}</p> : null}
    </Alert>
  )
}

export function AnalyzePage() {
  const [transcript, setTranscript] = useState('')
  const navigate = useNavigate()
  const analyse = useAnalyzeTranscript()

  const turns = countTurns(transcript)
  // Advisory. A transcript can parse into turns and still not read the way it
  // will be scored — the case this catches costs a provider call to discover.
  const warning = transcriptWarning(transcript)
  const running = analyse.isPending
  const canSubmit = turns > 0 && !running

  const submit = () => {
    analyse.mutate(
      { transcript, provider: null, model: null },
      {
        onSuccess: (analysis) => {
          navigate(`/calls/${String(analysis.id)}`)
        },
      },
    )
  }

  return (
    <>
      <PageHeader
        title="Analyze a call"
        subtitle="Paste a transcript. Processing runs on the configured provider."
      />

      <Card title="Transcript" subtitle="One speaker turn per line, formatted as Speaker: text">
        <label className="visually-hidden" htmlFor="transcript">
          Transcript
        </label>
        <textarea
          id="transcript"
          className={styles.textarea}
          placeholder={PLACEHOLDER}
          value={transcript}
          disabled={running}
          onChange={(event) => {
            setTranscript(event.target.value)
          }}
        />

        <div className={styles.actions}>
          <span className={styles.counter} role="status">
            {turns} turn{turns === 1 ? '' : 's'} detected
          </span>
          <div className={styles.buttons}>
            <Button
              onClick={() => {
                setTranscript('')
                analyse.reset()
              }}
              disabled={running || transcript.length === 0}
            >
              Clear
            </Button>
            <Button variant="primary" onClick={submit} disabled={!canSubmit}>
              {running ? 'Analyzing…' : 'Analyze'}
            </Button>
          </div>
        </div>

        {warning ? (
          /* Above the general guidance, because it is about this paste rather
             than about the format in general. Submission is still allowed:
             the mid-line test can fire on an ordinary sentence, and refusing
             a transcript on a heuristic is worse than scoring one badly with
             the reason on screen. */
          <Alert tone="medium" title="This will not parse the way it reads">
            {warning}
          </Alert>
        ) : null}

        {transcript.length > 0 && turns === 0 ? (
          /* Shown only when the paste actually has no prefixes. The standing
             explanation that used to sit here in every other case told a
             reader whose transcript was parsing fine something they did not
             need. */
          <Note>
            No speaker prefixes found. Every line needs one, like
            &ldquo;Agent Sarah:&rdquo; or &ldquo;Member:&rdquo; — the parser uses them to
            separate speakers.
          </Note>
        ) : null}

        {running ? (
          <div className={styles.running} style={{ marginTop: 12 }}>
            <span className={styles.spinner} aria-hidden="true" />
            <span>
              Running five layers. On a local model this takes several minutes for a full
              transcript.
            </span>
          </div>
        ) : null}

        {analyse.error ? (
          <div style={{ marginTop: 12 }}>
            <AnalysisFailure error={analyse.error} />
          </div>
        ) : null}
      </Card>
    </>
  )
}
