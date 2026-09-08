/**
 * Turn a corpus PDF into sample call files, from the browser.
 *
 * The corpus arrived as a PDF for the first six versions of this product and was
 * converted by a script somebody had to remember to run, in a Python
 * environment somebody had to have. This is that conversion as something an
 * operator can do.
 *
 * The screen's job is not to say "done". It is to let a reader judge whether
 * extraction actually worked, because the failure mode here is silent: the v5
 * corpus once converted at 82 of 100 calls and reported success, and the 18 it
 * dropped were the broker calls. So the result is a table of every call with the
 * fields that would be empty if a header had been misread — and anything
 * missing is called out above it rather than left for the reader to notice.
 */

import { useRef, useState } from 'react'

import { useCorpusImports, useImportCorpusDocument } from '@/shared/api/queries'
import type { CorpusImport, ImportedCall } from '@/shared/api/types'
import { ApiError } from '@/shared/api/client'
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
import styles from './ImportPage.module.css'

/** Below this many transcript lines a call has almost certainly been misread. */
const SUSPICIOUS_TURNS = 4

function tierTone(tier: string | null): 'high' | 'medium' | 'low' | 'neutral' {
  if (tier === 'POOR') return 'high'
  if (tier === 'AVERAGE') return 'medium'
  if (tier === 'GOOD') return 'low'
  return 'neutral'
}

/**
 * What is missing across the whole import.
 *
 * Reported as counts rather than per row: a header shape that changed breaks
 * the same field on every call, and one line saying "no agent on 100 calls" is
 * the finding. A hundred empty cells is the same fact, told badly.
 */
function gaps(calls: readonly ImportedCall[]): string[] {
  const missing = (label: string, predicate: (call: ImportedCall) => boolean) => {
    const count = calls.filter(predicate).length
    return count > 0 ? `${String(count)} ${count === 1 ? 'call has' : 'calls have'} no ${label}` : null
  }

  return [
    missing('agent name', (call) => !call.agent),
    missing('caller type', (call) => !call.caller),
    missing('score', (call) => call.score === null),
    missing('resolution', (call) => !call.resolution),
    missing('authored insights panel', (call) => !call.has_panel),
    missing('usable transcript', (call) => call.turns < SUSPICIOUS_TURNS),
  ].filter((line): line is string => line !== null)
}

function Result({ result }: { result: CorpusImport }) {
  const problems = gaps(result.calls)
  const brokers = result.calls.filter((call) => call.broker).length
  const repeats = result.calls.filter((call) => call.repeat).length

  return (
    <>
      <Card title="What was extracted">
        <div className={styles.summary}>
          <div>
            <b>{result.total}</b>
            <span>calls</span>
          </div>
          <div>
            <b>{brokers}</b>
            <span>broker signals</span>
          </div>
          <div>
            <b>{repeats}</b>
            <span>repeat contacts</span>
          </div>
        </div>
        <Note>
          Saved as <code>{result.name}</code> in <code>{result.directory}</code>. The corpus
          currently being analyzed is untouched — nothing points at these files until you copy
          them over it.
        </Note>
        {problems.length > 0 ? (
          <Alert tone="medium" title="Some fields did not come through">
            <ul className={styles.gaps}>
              {problems.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
            A field missing on every call usually means the document changed shape rather than
            that the document omits it.
          </Alert>
        ) : (
          <Alert tone="low" title="Every field came through">
            All {result.total} calls carry an agent, caller type, score, resolution and authored
            panel.
          </Alert>
        )}
      </Card>

      <Card title="Every call in the document">
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Ref</th>
                <th scope="col">Title</th>
                <th scope="col">Agent</th>
                <th scope="col">Caller</th>
                <th scope="col">Tier</th>
                <th scope="col" className={styles.numeric}>
                  Score
                </th>
                <th scope="col">Outcome</th>
                <th scope="col" className={styles.numeric}>
                  Lines
                </th>
                <th scope="col">Flags</th>
              </tr>
            </thead>
            <tbody>
              {result.calls.map((call) => (
                <tr key={call.filename}>
                  <td className={styles.mono}>{call.reference}</td>
                  <td>{call.title}</td>
                  <td>{call.agent ?? '—'}</td>
                  <td>{call.caller ?? '—'}</td>
                  <td>
                    {call.tier ? <Chip tone={tierTone(call.tier)}>{call.tier}</Chip> : '—'}
                  </td>
                  <td className={styles.numeric}>{call.score ?? '—'}</td>
                  <td>{call.resolution ?? '—'}</td>
                  <td
                    className={
                      call.turns < SUSPICIOUS_TURNS ? styles.numericWarn : styles.numeric
                    }
                  >
                    {call.turns}
                  </td>
                  <td className={styles.flags}>
                    {call.broker ? <Chip tone="high">broker</Chip> : null}
                    {call.repeat ? <Chip tone="medium">repeat</Chip> : null}
                    {!call.has_panel ? <Chip tone="high">no panel</Chip> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  )
}

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const importDocument = useImportCorpusDocument()
  const imports = useCorpusImports()

  const submit = () => {
    if (file) {
      importDocument.mutate(file)
    }
  }

  const error = importDocument.error
  const problem = error instanceof ApiError ? error : null

  return (
    <>
      <PageHeader
        title="Corpus import"
        subtitle="Convert a call-corpus PDF into the sample files a corpus run reads"
      />

      <Card title="Upload a document">
        <div className={styles.picker}>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            aria-label="Corpus PDF"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null)
            }}
          />
          <Button
            variant="primary"
            onClick={submit}
            disabled={!file || importDocument.isPending}
          >
            {importDocument.isPending ? 'Extracting…' : 'Extract calls'}
          </Button>
        </div>
        <Note>
          Extraction is all or nothing. A document whose header shape has changed is refused with
          the calls it could not read, rather than converted with holes in it — a corpus missing
          calls still analyzes and still reports success.
        </Note>
        {problem ? (
          <Alert title={problem.message}>
            {problem.detail ?? 'The document could not be read.'}
          </Alert>
        ) : null}
        {error && !problem ? <Failure error={error} what="the import" /> : null}
      </Card>

      {importDocument.isPending ? <Loading what="calls from the document" /> : null}
      {importDocument.data ? <Result result={importDocument.data} /> : null}

      <Card title="Previously imported">
        {imports.isLoading ? <Loading what="imported corpora" /> : null}
        {imports.error ? <Failure error={imports.error} what="the import list" /> : null}
        {imports.data?.length === 0 ? (
          <Empty title="Nothing imported yet">
            An imported corpus is kept under its own name so it cannot overwrite the one your
            stored analyses were made from.
          </Empty>
        ) : null}
        {imports.data && imports.data.length > 0 ? (
          <ul className={styles.versions}>
            {imports.data.map((version) => (
              <li key={version.name}>
                <b>{version.name}</b>
                <span>
                  {version.files} {version.files === 1 ? 'file' : 'files'}
                </span>
                <code>{version.directory}</code>
              </li>
            ))}
          </ul>
        ) : null}
      </Card>
    </>
  )
}
