const DEFAULT_BACKEND_URL = 'https://ogni-frontend.vercel.app'
const SNAPSHOT_PATH = '/api/v1/avito/orders/browser-snapshot'
const AVITO_ORDERS_URL = 'https://www.avito.ru/orders'
const LOG_KEY = 'satornaAvitoLogs'

async function writeLog(level, message, data = {}) {
  const entry = {
    at: new Date().toISOString(),
    level,
    message,
    data,
  }
  const method = level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'info'
  console[method]('[Satorna Avito]', message, data)
  try {
    const stored = await chrome.storage.local.get({ [LOG_KEY]: [] })
    const logs = Array.isArray(stored[LOG_KEY]) ? stored[LOG_KEY] : []
    await chrome.storage.local.set({ [LOG_KEY]: [...logs, entry].slice(-200) })
  } catch (error) {
    console.warn('[Satorna Avito] log storage failed', error)
  }
}

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
    accessToken: '',
    collectOptions: {
      photoMode: 'one',
      colorFromDescription: true,
      sizeMode: 'description',
      articleFromDescription: true,
    },
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
  await writeLog('info', 'posting snapshot', {
    orders: payload?.orders?.length || 0,
    items: payload?.orders?.reduce?.((sum, order) => sum + (order.items?.length || 0), 0) || 0,
  })
  const settings = await readSettings()
  const token = String(settings.accessToken || '').trim()
  if (!token) {
    throw new Error('Добавьте токен Satorna в настройках расширения')
  }
  const backendUrl = await resolveBackendUrl(DEFAULT_BACKEND_URL)
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
      throw new Error('Фронт ещё не принимает заказы расширения. Обновите деплой фронта или проверьте, что на нём включён proxy в API backend.')
    }
    await writeLog('error', 'backend rejected snapshot', { status: response.status, message })
    throw new Error(message)
  }
  await writeLog('info', 'snapshot posted', { status: response.status })
  return response.json()
}

function tabsQuery(query) {
  return new Promise((resolve) => chrome.tabs.query(query, resolve))
}

function tabsCreate(createProperties) {
  return new Promise((resolve) => chrome.tabs.create(createProperties, resolve))
}

function tabsUpdate(tabId, updateProperties) {
  return new Promise((resolve) => chrome.tabs.update(tabId, updateProperties, resolve))
}

function tabsRemove(tabId) {
  return new Promise((resolve) => chrome.tabs.remove(tabId, resolve))
}

function tabsSendMessage(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      const error = chrome.runtime.lastError
      if (error) {
        reject(new Error(error.message))
        return
      }
      resolve(response)
    })
  })
}

function executeContentScript(tabId) {
  return chrome.scripting.executeScript({ target: { tabId }, files: ['src/content.js'] })
}

function waitForTabComplete(tabId, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(listener)
      reject(new Error('Avito долго загружается. Откройте страницу заказов и попробуйте ещё раз.'))
    }, timeoutMs)
    const listener = (updatedTabId, changeInfo) => {
      if (updatedTabId !== tabId || changeInfo.status !== 'complete') return
      clearTimeout(timer)
      chrome.tabs.onUpdated.removeListener(listener)
      resolve()
    }
    chrome.tabs.onUpdated.addListener(listener)
    chrome.tabs.get(tabId, (tab) => {
      if (chrome.runtime.lastError) return
      if (tab?.status === 'complete') {
        clearTimeout(timer)
        chrome.tabs.onUpdated.removeListener(listener)
        resolve()
      }
    })
  })
}

function assertAvitoUrl(value) {
  const url = new URL(String(value || ''))
  if (url.protocol !== 'https:' || url.hostname !== 'www.avito.ru') {
    throw new Error('Расширение может открывать детали только на www.avito.ru')
  }
  return url.toString()
}

async function extractDetailsInTab(url, options) {
  const resolvedUrl = assertAvitoUrl(url)
  await writeLog('info', 'opening detail tab', { url: resolvedUrl })
  const tab = await tabsCreate({ url: resolvedUrl, active: false })
  if (!tab?.id) throw new Error('Не удалось открыть деталку Avito')
  try {
    await waitForTabComplete(tab.id, 45000)
    await executeContentScript(tab.id)
    await new Promise((resolve) => setTimeout(resolve, 600))
    const response = await tabsSendMessage(tab.id, { type: 'AVITO_PAGE_EXTRACT_DETAILS', options: options || {} })
    if (!response?.ok) throw new Error(response?.error || 'Не удалось прочитать деталку Avito')
    await writeLog('info', 'detail extracted', {
      url: resolvedUrl,
      title: response.title,
      images: response.images?.length || 0,
      itemUrls: response.itemUrls?.length || 0,
    })
    return response
  } catch (error) {
    await writeLog('error', 'detail extraction failed', { url: resolvedUrl, error: error instanceof Error ? error.message : String(error) })
    throw error
  } finally {
    await tabsRemove(tab.id)
    await writeLog('info', 'detail tab closed', { url: resolvedUrl })
  }
}

async function avitoOrdersTab() {
  const tabs = await tabsQuery({ url: 'https://www.avito.ru/orders*' })
  const existing = tabs.find((tab) => tab.id)
  if (existing?.id) {
    await tabsUpdate(existing.id, { active: true })
    return existing
  }
  return tabsCreate({ url: AVITO_ORDERS_URL, active: true })
}

async function collectFromAvitoOrdersPage() {
  const tab = await avitoOrdersTab()
  if (!tab?.id) throw new Error('Не удалось открыть страницу заказов Avito')
  await waitForTabComplete(tab.id)
  const settings = await readSettings()
  const message = { type: 'AVITO_ORDERS_COLLECT_NOW', options: settings.collectOptions || {} }
  try {
    return await tabsSendMessage(tab.id, message)
  } catch (_error) {
    await executeContentScript(tab.id)
    return tabsSendMessage(tab.id, message)
  }
}

async function collectAndPostFromAvito() {
  await writeLog('info', 'collection requested from popup')
  await saveStatus({ ok: false, message: 'Открываем заказы Avito...' })
  const collected = await collectFromAvitoOrdersPage()
  if (!collected?.ok) throw new Error(collected?.error || 'Не удалось прочитать страницу заказов Avito')
  const payload = collected.payload
  const missing = payload?.collector?.missing || {}
  await saveStatus({ ok: false, message: `Нашли заказов: ${payload?.orders?.length || 0}. Не найдено: фото ${missing.imageUrl || 0}, размер ${missing.size || 0}, цвет ${missing.color || 0}. Отправляем в Satorna...` })
  const result = await postSnapshot(payload)
  const meta = result?.browserSnapshot
  const text = `Собрано заказов: ${meta?.orders ?? payload?.orders?.length ?? 0}`
  await saveStatus({ ok: true, message: text })
  await writeLog('info', 'collection finished', { message: text })
  return { ok: true, result, message: text }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'AVITO_LOG') {
    writeLog(message.level || 'info', message.message || 'event', message.data || {})
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }))
    return true
  }
  if (message?.type === 'AVITO_LOGS_GET') {
    chrome.storage.local.get({ [LOG_KEY]: [] }).then((stored) => sendResponse({ ok: true, logs: stored[LOG_KEY] || [] }))
    return true
  }
  if (message?.type === 'AVITO_LOGS_CLEAR') {
    chrome.storage.local.set({ [LOG_KEY]: [] }).then(() => sendResponse({ ok: true }))
    return true
  }
  if (message?.type === 'AVITO_EXTRACT_DETAILS_TAB') {
    extractDetailsInTab(message.url, message.options)
      .then((response) => sendResponse({ ok: true, details: response }))
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }))
    return true
  }
  if (message?.type === 'AVITO_ORDERS_OPEN_AND_COLLECT') {
    collectAndPostFromAvito()
      .then(sendResponse)
      .catch((error) => {
        const text = error instanceof Error ? error.message : String(error)
        return saveStatus({ ok: false, message: text }).then(() => sendResponse({ ok: false, error: text }))
      })
    return true
  }
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
