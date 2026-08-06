import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import './styles/global.css'
import App from './App.tsx'

// StrictMode is kept on deliberately. Runs are created in an explicit click
// handler, never in an effect, so the development double-mount cannot trigger a
// second paid pipeline — it only opens a second read-only SSE subscription whose
// replayed history the reducer's seq guard discards.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
