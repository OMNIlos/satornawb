const accessTokenInput = document.getElementById('accessToken')
const backendUrlInput = document.getElementById('backendUrl')
const localServerBtn = document.getElementById('localServerBtn')
let savedBackendUrl = ''
let connectionDirty = false
const photoModeInput = document.getElementById('photoMode')
const sizeModeInput = document.getElementById('sizeMode')
const colorFromDescriptionInput = document.getElementById('colorFromDescription')
const articleFromDescriptionInput = document.getElementById('articleFromDescription')
const saveBtn = document.getElementById('saveBtn')
const collectBtn = document.getElementById('collectBtn')
const labelsBtn = document.getElementById('labelsBtn')
const listingPhotosBtn = document.getElementById('listingPhotosBtn')
const stopListingPhotosBtn = document.getElementById('stopListingPhotosBtn')
const listingPhotosStatus = document.getElementById('listingPhotosStatus')

async function renderListingPhotos() {
  const [stored, worker] = await Promise.all([
    chrome.storage.local.get('listingPhotosStatus'),
    chrome.runtime.sendMessage({ type: 'AVITO_LISTING_PHOTOS_STATE' }),
  ])
  const status = stored.listingPhotosStatus
  const running = Boolean(worker?.running && (!status || status.stage === 'running'))
  listingPhotosBtn.disabled = running
  stopListingPhotosBtn.hidden = !running
  stopListingPhotosBtn.disabled = false
  if (status) {
    const label = running ? 'Сбор' : status.stage === 'done' ? 'Готово' : 'Можно продолжить сбор'
    listingPhotosStatus.textContent = `${label}${running && status.phase ? ': ' + status.phase : ''}. В базе: ${status.saved || 0} из ${status.total || 0}. Найдено в списках: ${status.found || 0}. Проверено за запуск: ${status.processed || 0}. Не получено: ${status.failed || 0}.${status.message && status.stage !== 'done' ? ' ' + status.message : ''}`
  }
}
listingPhotosBtn.addEventListener('click', async () => {
  if (connectionDirty || !accessTokenInput.value.trim()) {
    setActiveScreen('settings'); setStatus('Сначала сохраните адрес и токен Satorna'); return
  }
  await chrome.runtime.sendMessage({ type: 'AVITO_LISTING_PHOTOS_COLLECT' })
  await renderListingPhotos()
})
stopListingPhotosBtn.addEventListener('click', async () => {
  await chrome.runtime.sendMessage({ type: 'AVITO_LISTING_PHOTOS_STOP' })
  stopListingPhotosBtn.disabled = true
})
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.listingPhotosStatus) void renderListingPhotos()
})
void renderListingPhotos().catch(() => {})
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
const collectTokenHint = document.getElementById('collectTokenHint')

let saveFeedbackTimer = 0

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
  connectionBadge.textContent = hasToken ? 'настроено' : 'не настроено'
  connectionBadge.classList.toggle('ok', hasToken)
  lastRunText.textContent = settings.lastSnapshotAt ? formatTime(settings.lastSnapshotAt) : 'ещё не запускался'
  syncCollectButtonState(hasToken)
}

function syncCollectButtonState(hasToken = Boolean(accessTokenInput.value.trim())) {
  collectBtn.disabled = !hasToken
  labelsBtn.disabled = !hasToken
  collectTokenHint.classList.toggle('visible', !hasToken)
}

function setSaveFeedback(saved) {
  window.clearTimeout(saveFeedbackTimer)
  if (saved) {
    saveBtn.classList.add('saved')
  } else {
    saveBtn.classList.remove('saved')
  }
  saveBtn.textContent = saved ? 'Сохранено' : 'Сохранить настройки'
  if (saved) {
    saveFeedbackTimer = window.setTimeout(() => setSaveFeedback(false), 1800)
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
  Object.assign(settings, await SatornaConnection.read())
  savedBackendUrl = SatornaConnection.normalize(settings.backendUrl)
  backendUrlInput.value = savedBackendUrl
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
  const connection = await SatornaConnection.save(backendUrlInput.value, settings.accessToken)
  const { accessToken: _token, ...options } = settings
  await chrome.storage.sync.set(options)
  savedBackendUrl = connection.backendUrl
  backendUrlInput.value = savedBackendUrl
  connectionDirty = false
  updateConnectionState(settings)
  setSaveFeedback(true)
  setStatus('Настройки сохранены')
}

async function collectOrders() {
  if (connectionDirty) {
    setActiveScreen('settings')
    throw new Error('Сначала сохраните адрес и токен Satorna')
  }
  const accessToken = accessTokenInput.value.trim()
  if (!accessToken) {
    setActiveScreen('settings')
    setStatus('Сначала вставьте токен Satorna')
    syncCollectButtonState(false)
    return
  }
  setActiveScreen('collect')
  setStatus('Открываем Avito и собираем заказы...')
  const posted = await chrome.runtime.sendMessage({ type: 'AVITO_ORDERS_OPEN_AND_COLLECT' })
  if (!posted?.ok) throw new Error(posted?.error || 'Не удалось отправить данные')
  setStatus(posted.message || 'Заказы собраны')
  const settings = await chrome.storage.sync.get({ accessToken: '', lastSnapshotAt: '' })
  Object.assign(settings, await SatornaConnection.read())
  updateConnectionState(settings)
  await loadLogs()
}

collectTab.addEventListener('click', () => setActiveScreen('collect'))
settingsTab.addEventListener('click', () => setActiveScreen('settings'))
openSettingsHintBtn.addEventListener('click', () => setActiveScreen('settings'))

saveBtn.addEventListener('click', () => {
  saveSettings().catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
})

accessTokenInput.addEventListener('input', () => {
  connectionDirty = true
  setSaveFeedback(false)
  syncCollectButtonState()
})

backendUrlInput.addEventListener('input', () => {
  connectionDirty = true
  // Do not carry an existing credential to a different server.
  if (backendUrlInput.value.replace(/\/+$/, '') !== savedBackendUrl) accessTokenInput.value = ''
  setSaveFeedback(false)
  syncCollectButtonState()
})
localServerBtn.addEventListener('click', () => {
  backendUrlInput.value = SatornaConnection.localUrl
  backendUrlInput.dispatchEvent(new Event('input'))
  accessTokenInput.focus()
})

collectBtn.addEventListener('click', () => {
  if (!accessTokenInput.value.trim()) {
    setActiveScreen('settings')
    setStatus('Сначала вставьте токен Satorna')
    syncCollectButtonState(false)
    return
  }
  collectBtn.disabled = true
  collectOrders()
    .catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
    .finally(() => {
      syncCollectButtonState()
    })
})

labelsBtn.addEventListener('click', async () => {
  if (connectionDirty || !accessTokenInput.value.trim()) {
    setActiveScreen('settings'); setStatus('Сначала сохраните адрес и токен Satorna'); return
  }
  labelsBtn.disabled = true
  setStatus('Открываем печать этикеток. Ждём PDF Авито…')
  try {
    const result = await chrome.runtime.sendMessage({ type: 'AVITO_LABELS_COLLECT' })
    setStatus(result?.ok ? result.message : result?.error || 'Не удалось получить этикетки')
  } catch { setStatus('Связь с расширением прервалась. Повторите получение этикеток.') }
  finally { labelsBtn.disabled = false }
})

clearLogsBtn.addEventListener('click', () => {
  chrome.runtime.sendMessage({ type: 'AVITO_LOGS_CLEAR' })
    .then(() => loadLogs())
    .catch((error) => setStatus(error instanceof Error ? error.message : String(error)))
})

loadSettings()
