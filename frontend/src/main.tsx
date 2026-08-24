import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

const MSW_ENABLED = import.meta.env.DEV && import.meta.env.VITE_ENABLE_MSW === 'true'
const MSW_CLEANUP_RELOAD_KEY = 'ogni:msw-cleanup-reload'

async function stopMockServer() {
  if (!('serviceWorker' in navigator)) return false
  const controlledByMockWorker = navigator.serviceWorker.controller?.scriptURL.includes('mockServiceWorker') ?? false
  const registrations = await navigator.serviceWorker.getRegistrations()
  await Promise.all(
    registrations
      .filter((registration) => registration.active?.scriptURL.includes('mockServiceWorker'))
      .map((registration) => registration.unregister()),
  )
  if (controlledByMockWorker && sessionStorage.getItem(MSW_CLEANUP_RELOAD_KEY) !== 'done') {
    sessionStorage.setItem(MSW_CLEANUP_RELOAD_KEY, 'done')
    window.location.reload()
    return true
  }
  sessionStorage.removeItem(MSW_CLEANUP_RELOAD_KEY)
  return false
}

async function startMockServer() {
  if (!MSW_ENABLED) {
    const reloading = await stopMockServer()
    if (reloading) return false
    return true
  }

  if (navigator.webdriver) return

  if (!('serviceWorker' in navigator)) {
    if (import.meta.env.DEV) console.warn('[MSW] skipped: service workers are unavailable in this browser context')
    return
  }

  const { worker } = await import('./mocks/browser')
  await worker.start({
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
  return true
}

function mount() {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

startMockServer()
  .catch(() => {
    if (import.meta.env.DEV) console.warn('[MSW] skipped: failed to register service worker')
    return true
  })
  .then((shouldMount) => {
    if (shouldMount !== false) mount()
  })
