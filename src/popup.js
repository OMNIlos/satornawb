const accessTokenInput = document.getElementById('accessToken')
const photoModeInput = document.getElementById('photoMode')
const sizeModeInput = document.getElementById('sizeMode')
const colorFromDescriptionInput = document.getElementById('colorFromDescription')
const articleFromDescriptionInput = document.getElementById('articleFromDescription')
const saveBtn = document.getElementById('saveBtn')
const collectBtn = document.getElementById('collectBtn')
const statusEl = document.getElementById('status')
const logsListEl = document.getElementById('logsList')
const clearLogsBtn = document.getElementById('clearLogsBtn')

const DEFAULT_COLLECT_OPTIONS = {
  photoMode: 'one',
  colorFromDescription: true,
  sizeMode: 'description',
  articleFromDescription: true,
}

function setStatus(text) {
  statusEl.textContent = text
}

function formatTime(value) {
  try {
    return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(value))
  } catch (_error) {
    return ''
  }
}

function renderLogs(logs) {
  const rows = Array.isArray(logs) ? logs.slice(-30).reverse() : []
  if (!rows.length) {
    logsListEl.textContent = 'Логов пока нет'
    return
  }
  logsListEl.innerHTML = rows.map((row) => {
    const data = row.data && Object.keys(row.data).length ? JSON.stringify(row.data, null, 2).slice(0, 900) : ''
    return [
      `<div class="log-row ${row.level || 'info'}">`,
      `<b>${formatTime(row.at)} · ${row.message || 'event'}</b>`,
      data ? `<code>${data.replace(/[<>&]/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[char]))}</code>` : '',
      '</div>',
    ].join('')
  }).join('')
}

async function loadLogs() {
  const response = await chrome.runtime.sendMessage({ type: 'AVITO_LOGS_GET' })
  renderLogs(response?.logs || [])
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get({
    accessToken: '',
    collectOptions: DEFAULT_COLLECT_OPTIONS,
    lastStatus: '',
    lastSnapshotAt: '',
  })
  const options = { ...DEFAULT_COLLECT_OPTIONS, ...(settings.collectOptions || {}) }
  accessTokenInput.value = settings.accessToken || ''
  photoModeInput.value = options.photoMode
  sizeModeInput.value = options.sizeMode
  colorFromDescriptionInput.checked = Boolean(options.colorFromDescription)
  articleFromDescriptionInput.checked = Boolean(options.articleFromDescription)
  setStatus(settings.lastStatus || 'Нажмите сбор. Расширение само откроет заказы Avito.')
  await loadLogs()
}

async function saveSettings() {
  await chrome.storage.sync.set({
    accessToken: accessTokenInput.value.trim(),
    collectOptions: {
      photoMode: photoModeInput.value,
      colorFromDescription: colorFromDescriptionInput.checked,
      sizeMode: sizeModeInput.value,
      articleFromDescription: articleFromDescriptionInput.checked,
    },
  })
  setStatus('Настройки сохранены')
}

async function collectOrders() {
  await saveSettings()
  setStatus('Открываем заказы Avito и собираем данные...')
  const posted = await chrome.runtime.sendMessage({ type: 'AVITO_ORDERS_OPEN_AND_COLLECT' })
  if (!posted?.ok) throw new Error(posted?.error || 'Не удалось отправить данные')
  setStatus(posted.message || 'Заказы собраны')
  await loadLogs()
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

clearLogsBtn.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'AVITO_LOGS_CLEAR' })
    .then(() => loadLogs())
    .catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
})

loadSettings()
