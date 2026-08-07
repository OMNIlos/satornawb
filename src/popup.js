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
const collectTab = document.getElementById('collectTab')
const settingsTab = document.getElementById('settingsTab')
const collectScreen = document.getElementById('collectScreen')
const settingsScreen = document.getElementById('settingsScreen')
const connectionBadge = document.getElementById('connectionBadge')
const lastRunText = document.getElementById('lastRunText')
const openSettingsHintBtn = document.getElementById('openSettingsHintBtn')

const DEFAULT_COLLECT_OPTIONS = {
  photoMode: 'one',
  colorFromDescription: true,
  sizeMode: 'description',
  articleFromDescription: true,
}

function setActiveScreen(screen) {
  const isSettings = screen === 'settings'
  document.body.dataset.screen = isSettings ? 'settings' : 'collect'
  collectTab.classList.toggle('active', !isSettings)
  settingsTab.classList.toggle('active', isSettings)
  collectScreen.classList.toggle('active', !isSettings)
  settingsScreen.classList.toggle('active', isSettings)
}

function setStatus(text) {
  statusEl.textContent = text
}

function formatTime(value) {
  try {
    return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
  } catch (_error) {
    return ''
  }
}

function updateConnectionState(settings) {
  const hasToken = Boolean(String(settings.accessToken || '').trim())
  connectionBadge.textContent = hasToken ? 'подключено' : 'не настроено'
  connectionBadge.classList.toggle('ok', hasToken)
  lastRunText.textContent = settings.lastSnapshotAt ? formatTime(settings.lastSnapshotAt) : 'ещё не запускался'
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
  updateConnectionState(settings)
  await loadLogs()
}

async function saveSettings() {
  const settings = {
    accessToken: accessTokenInput.value.trim(),
    collectOptions: {
      photoMode: photoModeInput.value,
      colorFromDescription: colorFromDescriptionInput.checked,
      sizeMode: sizeModeInput.value,
      articleFromDescription: articleFromDescriptionInput.checked,
    },
  }
  await chrome.storage.sync.set(settings)
  updateConnectionState(settings)
  setStatus('Настройки сохранены')
}

async function collectOrders() {
  await saveSettings()
  setActiveScreen('collect')
  setStatus('Открываем Avito и собираем заказы...')
  const posted = await chrome.runtime.sendMessage({ type: 'AVITO_ORDERS_OPEN_AND_COLLECT' })
  if (!posted?.ok) throw new Error(posted?.error || 'Не удалось отправить данные')
  setStatus(posted.message || 'Заказы собраны')
  const settings = await chrome.storage.sync.get({ accessToken: '', lastSnapshotAt: '' })
  updateConnectionState(settings)
  await loadLogs()
}

collectTab.addEventListener('click', () => setActiveScreen('collect'))
settingsTab.addEventListener('click', () => setActiveScreen('settings'))
openSettingsHintBtn.addEventListener('click', () => setActiveScreen('settings'))

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
