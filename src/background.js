const DEFAULT_BACKEND_URL = 'http://localhost:8000'
const SNAPSHOT_PATH = '/api/v1/avito/orders/browser-snapshot'

function normalizeBackendUrl(value) {
  const text = String(value || DEFAULT_BACKEND_URL).trim().replace(/\/+$/, '')
  return text || DEFAULT_BACKEND_URL
}

function looksLikeFrontendUrl(value) {
  try {
    const url = new URL(value)
    return url.hostname.includes('vercel.app') || url.hostname.includes('frontend') || url.pathname.includes('/wb/') || url.pathname.includes('/avito/')
  } catch (_error) {
    return false
  }
}

async function resolveBackendUrl(value) {
  const normalized = normalizeBackendUrl(value)
  if (!looksLikeFrontendUrl(normalized)) return normalized
  try {
    const response = await fetch(`${normalized}/api/config.js`, { method: 'GET', cache: 'no-store' })
    const text = await response.text()
    const match = text.match(/VITE_API_BASE_URL["']?\s*[:=]\s*["']([^"']+)["']/)
      || text.match(/apiBaseUrl["']?\s*[:=]\s*["']([^"']+)["']/i)
    if (match?.[1]) return normalizeBackendUrl(match[1])
  } catch (_error) {
    // Keep the explicit frontend-url error below.
  }
  return normalized
}

function authorizationValue(value) {
  const token = String(value || '').trim()
  if (!token) return ''
  return /^bearer\s+/i.test(token) ? token : `Bearer ${token}`
}

async function readSettings() {
  return chrome.storage.sync.get({
    backendUrl: DEFAULT_BACKEND_URL,
    accessToken: '',
    lastStatus: '',
    lastSnapshotAt: '',
  })
}

async function saveStatus(status) {
  await chrome.storage.sync.set({
    lastStatus: status.message,
    lastSnapshotAt: status.ok ? new Date().toISOString() : '',
  })
}

async function postSnapshot(payload) {
  const settings = await readSettings()
  const token = String(settings.accessToken || '').trim()
  if (!token) {
    throw new Error('Добавьте токен Satorna в настройках расширения')
  }
  const backendUrl = await resolveBackendUrl(settings.backendUrl)
  const response = await fetch(`${backendUrl}${SNAPSHOT_PATH}`, {
    method: 'POST',
    headers: {
      'Authorization': authorizationValue(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    let message = `Backend вернул ${response.status}`
    try {
      const text = await response.text()
      if (text) message = `${message}: ${text.slice(0, 240)}`
    } catch (_error) {
      // Ignore body read failures.
    }
    if (response.status === 405 && looksLikeFrontendUrl(backendUrl)) {
      throw new Error('В Backend URL вставлен адрес фронта. Скопируйте именно API Backend URL на странице /avito/orders и сохраните его в расширении.')
    }
    throw new Error(message)
  }
  return response.json()
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'AVITO_ORDERS_COLLECTED') return false
  postSnapshot(message.payload)
    .then((result) => {
      const meta = result?.browserSnapshot
      const text = `Собрано заказов: ${meta?.orders ?? message.payload?.orders?.length ?? 0}`
      return saveStatus({ ok: true, message: text }).then(() => sendResponse({ ok: true, result, message: text }))
    })
    .catch((error) => {
      const text = error instanceof Error ? error.message : String(error)
      return saveStatus({ ok: false, message: text }).then(() => sendResponse({ ok: false, error: text }))
    })
  return true
})
