import React from 'react'
import ReactDOM from 'react-dom/client'
import * as Sentry from '@sentry/react'
import App from './app/App'
import './styles/globals.css'

// Sentry is initialized only when VITE_SENTRY_DSN is set.
// Add VITE_SENTRY_DSN to your .env file to enable frontend error tracking.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN as string,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.05,
    integrations: [Sentry.browserTracingIntegration()],
  })
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Sentry.ErrorBoundary fallback={<p className="p-8 text-red-600">Ha ocurrido un error inesperado.</p>}>
      <App />
    </Sentry.ErrorBoundary>
  </React.StrictMode>
)
