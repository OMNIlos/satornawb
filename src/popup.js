const accessTokenInput = document.getElementById('accessToken')
const saveBtn = document.getElementById('saveBtn')
const collectBtn = document.getElementById('collectBtn')
const statusEl = document.getElementById('status')

function setStatus(text) {
  statusEl.textContent = text
}

async function loadSettings() {
  const settings = await chrome.storage.sync.get({
    accessToken: '',
    lastStatus: '',
    lastSnapshotAt: '',
  })
  accessTokenInput.value = settings.accessToken || ''
  setStatus(settings.lastStatus || 'Нажмите сбор. Расширение само откроет заказы Avito.')
}

async function saveSettings() {
  await chrome.storage.sync.set({
    accessToken: accessTokenInput.value.trim(),
  })
  setStatus('Настройки сохранены')
}

async function collectOrders() {
  await saveSettings()
  setStatus('Открываем заказы Avito и собираем данные...')
  const posted = await chrome.runtime.sendMessage({ type: 'AVITO_ORDERS_OPEN_AND_COLLECT' })
  if (!posted?.ok) throw new Error(posted?.error || 'Не удалось отправить данные')
  setStatus(posted.message || 'Заказы собраны')
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
