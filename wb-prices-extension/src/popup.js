'use strict'
const element = (id) => document.getElementById(id)
const labels = { disconnected: 'Не подключено', ready: 'Каталог проверен', running: 'Собираем цены', refreshing: 'Обновляем каталог продавца', paused: 'Сбор приостановлен', waiting: 'Следующий проход запланирован' }
const reasons = {
  user_stopped: 'Остановлено вами. Можно продолжить с оставшихся товаров.',
  submission_unknown: 'Браузер прервал запрос сохранения. Его результат неизвестен; повтор не выполнялся. Продолжите вручную.',
  background_unavailable: 'Фоновый процесс недоступен. Откройте расширение заново.',
  partial_coverage: 'Для части размеров нет свежего наблюдения. Цены для них не подставлены.',
  page_timeout: 'Предыдущий проход остановился на странице без цены. Нажмите «Продолжить».',
  http_403: 'WB ограничил доступ. Сбор остановлен; автоматических повторов нет.',
  http_429: 'WB ограничил частоту запросов. Продолжите позже вручную.',
  challenge: 'WB показал страницу проверки в фоновой вкладке. Откройте её кнопкой ниже. Если там уже обычная страница товара, нажмите «Продолжить».',
  token_invalid: 'Вставьте действующий токен расширения из Satorna.',
  crm_http_401: 'Токен недействителен или истёк и удалён из расширения. Подключитесь заново.',
  crm_http_403: 'Satorna не разрешила операцию. Проверьте доступ к кабинету.',
  crm_http_409: 'Каталог изменился. Сбор приостановлен; можно продолжить после проверки каталога.',
  crm_http_429: 'Satorna ограничила частоту запросов. Продолжите позже вручную.',
  refresh_cooldown: 'Каталог недавно обновлялся. Продолжите позже вручную.',
  refresh_unavailable: 'Не удалось обновить цены продавца из WB. Сбор приостановлен.',
  refresh_busy: 'Каталог уже обновляется. Дождитесь завершения и продолжите вручную.',
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

function render(next = state) {
  state = next
  element('status').textContent = labels[state.status] || 'Состояние неизвестно'
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
  element('next-run').textContent = state.nextRunAt
    ? `Следующий проход: ${new Date(state.nextRunAt).toLocaleTimeString('ru-RU')}.` : 'Автоповтор — через 20 минут после завершения прохода.'
  const active = ['running', 'refreshing', 'waiting'].includes(state.status)
  element('connect').disabled = busy || active
  element('token').disabled = busy || active
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
  const token = element('token').value.trim()
  element('token').value = ''
  await request({ type: 'connect', token })
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
