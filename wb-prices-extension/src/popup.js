'use strict'
const element = (id) => document.getElementById(id)
const labels = { disconnected: 'Не подключено', ready: 'Каталог проверен', running: 'Собираем цены', refreshing: 'Обновляем каталог продавца', paused: 'Сбор приостановлен', waiting: 'Проход завершён', retrying: 'Автоматически продолжим сбор' }
const reasons = {
  server_invalid: 'Укажите HTTPS-адрес сервера без пути /api, параметров и пароля.',
  server_permission_denied: 'Разрешите расширению доступ к выбранному серверу и повторите подключение.',
  collector_hidden: 'WB приостановил подгрузку скрытой вкладки. Нажмите «Показать вкладку WB» и оставьте её видимой: сбор продолжится автоматически, без «Продолжить».',
  user_stopped: 'Остановлено вами. Можно продолжить с оставшихся товаров.',
  submission_unknown: 'Браузер прервал сохранение. Старый запрос не повторяется: оставшиеся цены будут проверены заново автоматически.',
  retry_exhausted: 'Три автоматических повтора не помогли. Проверьте доступность WB и Satorna; затем можно продолжить вручную.',
  request_failed: 'Временная ошибка сети. Во время активного сбора повтор выполняется автоматически с задержкой.',
  background_unavailable: 'Фоновый процесс недоступен. Откройте расширение заново.',
  partial_coverage: 'Для части размеров нет свежего наблюдения. Цены для них не подставлены.',
  page_timeout: 'Предыдущий проход остановился на странице без цены. Нажмите «Продолжить».',
  http_403: 'WB ограничил доступ. Сбор остановлен; автоматических повторов нет.',
  http_429: 'WB ограничил частоту запросов. Ждём перед автоматическим продолжением.',
  challenge: 'WB показал страницу проверки в фоновой вкладке. Откройте её кнопкой ниже. Если там уже обычная страница товара, нажмите «Продолжить».',
  token_invalid: 'Вставьте действующий токен расширения из Satorna.',
  crm_http_401: 'Токен недействителен или истёк и удалён из расширения. Подключитесь заново.',
  crm_http_403: 'Satorna не разрешила операцию. Проверьте доступ к кабинету.',
  crm_http_409: 'Каталог изменился. Сбор приостановлен; можно продолжить после проверки каталога.',
  crm_http_429: 'Satorna ограничила частоту запросов. Ждём перед автоматическим продолжением.',
  refresh_cooldown: 'Каталог недавно обновлялся. Ждём перед автоматическим продолжением.',
  refresh_unavailable: 'Каталог временно недоступен. Повторим автоматически во время активного сбора.',
  refresh_busy: 'Каталог уже обновляется. Дождёмся завершения автоматически.',
  catalog_stale: 'Цены продавца в Satorna старше допустимого срока. Обновите каталог перед сбором.',
  catalog_changed: 'Каталог изменился во время чтения. Повторите подключение.',
  catalog_invalid: 'Каталог Satorna не прошёл проверку. Данные не отправлены.',
  ack_invalid: 'Ответ Satorna не подтвердил сохранение. Автоматического повтора нет.',
  observation_stale: 'Наблюдение устарело до отправки. Продолжите сбор заново.',
  tab_closed: 'Вкладка сборщика закрыта. Нажмите «Продолжить», чтобы открыть новую.',
  tab_changed: 'Вкладка сборщика открыла другой адрес. Она оставлена без изменений.',
  stop_first: 'Сначала остановите текущий сбор.',
}
let state = { status: 'disconnected' }
let busy = false
let serverInitialized = false

function render(next = state) {
  state = next
  if (!serverInitialized) {
    element('backend-url').value = state.backendUrl || WbPricesConnection.DEFAULT_SERVER_URL
    serverInitialized = true
  }
  element('status').textContent = labels[state.status] || 'Состояние неизвестно'
  if (state.status === 'waiting' && state.reason === 'partial_coverage') element('status').textContent = 'Проход завершён частично'
  element('reason').textContent = state.reason ? (reasons[state.reason] || 'Операция не завершена. Проверьте подключение и повторите вручную.')
    + (state.retryAfterSeconds ? ` Сервер просит подождать ${state.retryAfterSeconds} с.` : '') : ''
  const known = state.observedOffers || 0
  const total = state.totalOffers || 0
  element('coverage').textContent = `${known} / ${total}`
  element('missing').textContent = String(Math.max(0, total - known))
  element('accepted').textContent = String(state.accepted || 0)
  element('ignored').textContent = String(state.ignored || 0)
  element('partial').textContent = String(state.partialSellers || 0)
  element('processed').textContent = `${state.visitedProducts || 0} / ${state.totalProducts || 0}`
  element('last-ack').textContent = state.lastAckAt
    ? `Последнее подтверждение: ${new Date(state.lastAckAt).toLocaleTimeString('ru-RU')}` : 'Подтверждений сохранения пока нет.'
  const metrics = state.metrics
  element('performance').textContent = metrics?.startedAt
    ? `Время прохода: ${Math.max(0, Math.round(((metrics.finishedAt || Date.now()) - metrics.startedAt) / 1000))} с · пакетов WB: ${metrics.publicRequests || 0} · страниц магазина: ${metrics.sellerPages || 0} · переходов: ${metrics.navigations || 0} · сохранений: ${metrics.snapshotRequests || 0}` : ''
  element('next-run').textContent = state.retryAt ? `Автопродолжение: ${new Date(state.retryAt).toLocaleTimeString('ru-RU')}.` : state.nextRunAt
    ? `Продолжение: ${new Date(state.nextRunAt).toLocaleTimeString('ru-RU')}.` : 'Один проход. Прогресс сохраняется; автоматического второго круга нет.'
  const active = ['running', 'refreshing', 'retrying'].includes(state.status)
  element('connect').disabled = busy || active
  element('token').disabled = busy || active
  element('backend-url').disabled = busy || active
  element('start').disabled = busy || state.status !== 'ready'
  element('resume').disabled = busy || state.status !== 'paused'
  element('stop').disabled = !active
  element('show-tab').disabled = busy || !state.collectorTabAvailable
  element('disconnect').disabled = busy
}

async function request(message) {
  busy = true; render()
  try {
    const result = await chrome.runtime.sendMessage(message)
    if (result?.state) render(result.ok ? result.state : { ...result.state, reason: result.code || result.state.reason })
    else state = { ...state, reason: 'background_unavailable' }
  } catch { state = { ...state, reason: 'background_unavailable' } }
  finally { busy = false; render() }
}

element('connect-form').addEventListener('submit', async (event) => {
  event.preventDefault()
  if (busy) return
  let backendUrl
  try { backendUrl = WbPricesConnection.normalizeServerUrl(element('backend-url').value) }
  catch { render({ ...state, reason: 'server_invalid' }); return }
  // Called directly from the submit gesture, before sending any credential.
  busy = true; render()
  let granted
  try { granted = await chrome.permissions.request({ origins: [WbPricesConnection.permissionOrigin(backendUrl)] }) }
  catch { granted = false }
  busy = false
  if (!granted) { render({ ...state, reason: 'server_permission_denied' }); return }
  const token = element('token').value.trim()
  element('token').value = ''
  await request({ type: 'connect', backendUrl, token })
})
for (const type of ['start', 'resume', 'stop', 'disconnect']) element(type).addEventListener('click', () => request({ type }))
element('show-tab').addEventListener('click', () => request({ type: 'show_tab' }))

async function refresh() {
  try {
    const result = await chrome.runtime.sendMessage({ type: 'status' })
    if (result?.state) render(result.state)
    else render({ ...state, reason: 'background_unavailable' })
  } catch { element('reason').textContent = 'Не удалось прочитать состояние расширения.' }
}
void refresh()
setInterval(refresh, 1500)
