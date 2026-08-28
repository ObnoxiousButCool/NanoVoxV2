/**
 * Application shell.
 *
 * P0 routes only to Diagnostics. The navigation rail, the dashboard screens and
 * the collapsible menu arrive in P5/P6 — this file is where they will be hung.
 */

import { Navigate, Route, Routes } from 'react-router-dom'

import { DiagnosticsPage } from '@/features/diagnostics/DiagnosticsPage'

export function App() {
  return (
    <Routes>
      <Route path="/diagnostics" element={<DiagnosticsPage />} />
      <Route path="*" element={<Navigate to="/diagnostics" replace />} />
    </Routes>
  )
}
