/**
 * Application shell and routes.
 *
 * Unknown routes land on the Overview, which itself points at Analyze when
 * nothing has been analyzed yet — so a fresh install never shows an empty room
 * without saying what to do about it.
 */

import { useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { AppShell } from '@/app/layout/AppShell'
import { AnalyzePage } from '@/features/analyze/AnalyzePage'
import { BrokersPage } from '@/features/brokers/BrokersPage'
import { InferencesPage } from '@/features/inferences/InferencesPage'
import { CallsPage } from '@/features/calls/CallsPage'
import { CorpusPage } from '@/features/corpus/CorpusPage'
import { ImportPage } from '@/features/corpus-import/ImportPage'
import { CallDetailPage } from '@/features/call-detail/CallDetailPage'
import { DiagnosticsPage } from '@/features/diagnostics/DiagnosticsPage'
import { OverviewPage } from '@/features/overview/OverviewPage'

/**
 * Resets scroll to the top of the page on every route change.
 *
 * The page itself scrolls — there is no separate inner scroll container —
 * and the router does not do this on its own. Without it, navigating away
 * from a page scrolled partway down carries that same pixel offset onto
 * whatever opens next, landing a reader mid-page on a screen they have not
 * read yet.
 */
function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}

export function App() {
  return (
    <AppShell>
      <ScrollToTop />
      <Routes>
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/inferences" element={<InferencesPage />} />
        <Route path="/calls" element={<CallsPage />} />
        <Route path="/brokers" element={<BrokersPage />} />
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/corpus" element={<CorpusPage />} />
        <Route path="/corpus-import" element={<ImportPage />} />
        <Route path="/calls/:callId" element={<CallDetailPage />} />
        <Route path="/diagnostics" element={<DiagnosticsPage />} />
        <Route path="*" element={<Navigate to="/overview" replace />} />
      </Routes>
    </AppShell>
  )
}
