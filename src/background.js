const DEFAULT_BACKEND_URL = 'http://localhost:8000'
const SNAPSHOT_PATH = '/api/v1/avito/orders/browser-snapshot'

function normalizeBackendUrl(value) {
  const text = String(value || DEFAULT_BACKEND_URL).trim().replace(/\/+$/, '')
  return text || DEFAULT_BACKEND_URL
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
  const response = await fetch(`${normalizeBackendUrl(settings.backendUrl)}${SNAPSHOT_PATH}`, {
    method: 'POST',
    headers: {
      'Authorization': authorizationValue(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`Backend вернул ${response.status}`)
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
