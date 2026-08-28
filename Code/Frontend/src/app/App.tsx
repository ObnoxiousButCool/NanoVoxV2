/**
 * Application shell and routes.
 *
 * The Overview, Calls and Brokers screens arrive in P6; until they exist they
 * are absent from the rail rather than present and empty.
 */

import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '@/app/layout/AppShell'
import { AnalyzePage } from '@/features/analyze/AnalyzePage'
import { CallDetailPage } from '@/features/call-detail/CallDetailPage'
import { DiagnosticsPage } from '@/features/diagnostics/DiagnosticsPage'

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/analyze" element={<AnalyzePage />} />
        <Route path="/calls/:callId" element={<CallDetailPage />} />
        <Route path="/diagnostics" element={<DiagnosticsPage />} />
        <Route path="*" element={<Navigate to="/analyze" replace />} />
      </Routes>
    </AppShell>
  )
}
