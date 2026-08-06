const backendUrlInput = document.getElementById('backendUrl')
const accessTokenInput = document.getElementById('accessToken')
const saveBtn = document.getElementById('saveBtn')
const collectBtn = document.getElementById('collectBtn')
const statusEl = document.getElementById('status')

function setStatus(text) {
  statusEl.textContent = text
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get({
    backendUrl: 'http://localhost:8000',
    accessToken: '',
    lastStatus: '',
    lastSnapshotAt: '',
  })
  backendUrlInput.value = settings.backendUrl || 'http://localhost:8000'
  accessTokenInput.value = settings.accessToken || ''
  setStatus(settings.lastStatus || 'Откройте страницу заказов Avito и нажмите сбор.')
}

async function saveSettings() {
  await chrome.storage.sync.set({
    backendUrl: backendUrlInput.value.trim() || 'http://localhost:8000',
    accessToken: accessTokenInput.value.trim(),
  })
  setStatus('Настройки сохранены')
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id || !String(tab.url || '').startsWith('https://www.avito.ru/')) {
    throw new Error('Откройте страницу Avito с заказами')
  }
  return tab
}

async function collectOrders() {
  await saveSettings()
  const tab = await activeTab()
  const response = await chrome.tabs.sendMessage(tab.id, { type: 'AVITO_ORDERS_COLLECT_NOW' })
  if (!response?.ok) throw new Error(response?.error || 'Не удалось прочитать страницу Avito')
  const payload = response.payload
  setStatus(`Нашли заказов на странице: ${payload.orders.length}. Отправляем в Satorna...`)
  const posted = await chrome.runtime.sendMessage({ type: 'AVITO_ORDERS_COLLECTED', payload })
  if (!posted?.ok) throw new Error(posted?.error || 'Не удалось отправить данные')
  setStatus(posted.message || `Собрано заказов: ${payload.orders.length}`)
}

saveBtn.addEventListener('click', () => {
  saveSettings().catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
})

collectBtn.addEventListener('click', () => {
  collectBtn.disabled = true
  collectOrders()
    .catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
    .finally(() => {
      collectBtn.disabled = false
    })
})

loadSettings()
