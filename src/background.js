importScripts('runtime-retry.js')
importScripts('connection.js')
importScripts('shipment-number.js')
importScripts('labels.js')
importScripts('listing-photos.js')

const DEFAULT_BACKEND_URL = 'https://ogni-frontend.vercel.app'
const SNAPSHOT_PATH = '/api/v1/avito/orders/browser-snapshot'
const AVITO_ORDERS_URL = 'https://www.avito.ru/orders'
const AVITO_RETURNS_URL = 'https://www.avito.ru/orders?status%5B%5D=on_return'
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
  return SatornaConnection.normalize(value || DEFAULT_BACKEND_URL)
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
    const response = await fetch(`${normalized}/api/config.js`, { method: 'GET', cache: 'no-store', redirect: 'error', credentials: 'omit' })
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
  const settings = await chrome.storage.sync.get({
    backendUrl: DEFAULT_BACKEND_URL,
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
  return { ...settings, ...await SatornaConnection.read() }
}

async function apiUrlFromSettings(settings) {
  return resolveBackendUrl(settings?.backendUrl || DEFAULT_BACKEND_URL)
}

async function readApiJson(response, { backendUrl, action }) {
  const text = await response.text()
  if (!response.ok) {
    const message = text ? `Backend вернул ${response.status}: ${text.slice(0, 240)}` : `Backend вернул ${response.status}`
    await writeLog('error', 'backend request failed', { action, status: response.status, backendUrl, message })
    throw new Error(message)
  }
  try {
    return text ? JSON.parse(text) : {}
  } catch (_error) {
    const preview = text.slice(0, 80).replace(/\s+/g, ' ')
    await writeLog('error', 'backend returned non-json response', {
      action,
      backendUrl,
      status: response.status,
      preview,
    })
    throw new Error('Satorna вернула страницу вместо API-ответа. Проверьте адрес backend в настройках расширения или обновите деплой Satorna.')
  }
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
    returns: payload?.returns?.length || 0,
    items: [...(payload?.orders || []), ...(payload?.returns || [])].reduce((sum, order) => sum + (order.items?.length || 0), 0),
  })
  const settings = await readSettings()
  const token = String(settings.accessToken || '').trim()
  if (!token) {
    throw new Error('Добавьте токен Satorna в настройках расширения')
  }
  const backendUrl = await apiUrlFromSettings(settings)
  const response = await fetch(`${backendUrl}${SNAPSHOT_PATH}`, {
    method: 'POST',
    redirect: 'error',
    credentials: 'omit',
    headers: {
      'Authorization': authorizationValue(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })
  if (response.status === 405 && looksLikeFrontendUrl(backendUrl)) {
    throw new Error('Фронт ещё не принимает заказы расширения. Обновите деплой фронта или проверьте, что на нём включён proxy в API backend.')
  }
  await writeLog('info', 'snapshot posted', { status: response.status })
  return readApiJson(response, { backendUrl, action: 'post_snapshot' })
}

async function postSnapshotWithFeedback(payload) {
  const settings = await readSettings()
  const target = normalizeBackendUrl(settings.backendUrl)
  try {
    const result = await postSnapshot(payload)
    if (result?.ok !== true) throw new Error('Сервер не подтвердил сохранение')
    await notifyUploadStatus(true, `Сохранено в Satorna: ${target}. Обновите страницу заказов.`)
    return result
  } catch (error) {
    await notifyUploadStatus(false, `Не сохранено в ${target}. ${error instanceof Error ? error.message : 'Ошибка отправки'}. Проверьте адрес и токен в настройках расширения.`)
    throw error
  }
}

async function notifyUploadStatus(ok, message) {
  try {
    const tabs = await tabsQuery({ url: 'https://www.avito.ru/*' })
    await Promise.all(tabs.map(tab => tabsSendMessage(tab.id, { type: 'AVITO_UPLOAD_STATUS', ok, message }).catch(() => {})))
  } catch { /* Display failures must not turn a successful save into a retry. */ }
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

function tabsSendMessage(tabId, message, options) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, options || {}, (response) => {
      const error = chrome.runtime.lastError
      if (error) {
        reject(new Error(error.message))
        return
      }
      resolve(response)
    })
  })
}

function executeContentScript(tabId, allFrames = false) {
  return chrome.scripting.executeScript({
    target: { tabId, allFrames },
    files: [
      'src/item-size.js',
      'src/item-photo.js',
      'src/order-chat.js',
      'src/size-policy.js',
      'src/page-state.js',
      'src/shipment-number.js',
      'src/return-details.js',
      'src/content.js',
    ],
  })
}

async function classifyFrames(tabId, expectedTitle) {
  const frames = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    args: [String(expectedTitle || '')],
    func: (rawExpectedTitle) => {
      const text = document.body?.innerText || ''
      const expected = String(rawExpectedTitle || '').toLowerCase()
      const hasExpectedTitle = expected ? text.toLowerCase().includes(expected) : false
      const hasOrderWords = /заказ|трек|доставка|получатель|отправьте|чат|стоимость|итого/i.test(text)
      const hasOnlyPublicShell = text.includes('Продавать') && text.includes('Покупать') && text.includes('Карьера') && !hasExpectedTitle && !hasOrderWords
      return {
        url: location.href,
        documentTitle: document.title,
        bodyLength: text.length,
        bodyPreview: text.slice(0, 1000),
        hasExpectedTitle,
        hasOrderWords,
        hasOnlyPublicShell,
        anchorsCount: document.querySelectorAll('a[href]').length,
        imagesCount: document.querySelectorAll('img').length,
      }
    },
  })
  return frames.map((frame) => ({ frameId: frame.frameId, ...(frame.result || {}) }))
}

function bestFrame(frames, isOrderDetail) {
  if (!Array.isArray(frames) || !frames.length) return null
  const sorted = [...frames].sort((a, b) => {
    const score = (frame) => {
      let value = 0
      if (frame.hasExpectedTitle) value += 100
      if (frame.hasOrderWords) value += 50
      if (!frame.hasOnlyPublicShell) value += 10
      value += Math.min(20, Math.floor((frame.bodyLength || 0) / 500))
      if (!isOrderDetail && /_[0-9]{6,12}/.test(frame.url || '')) value += 100
      return value
    }
    return score(b) - score(a)
  })
  return sorted[0]
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

function isAvitoListingUrl(value) {
  try {
    const url = new URL(String(value || ''))
    if (url.protocol !== 'https:' || url.hostname !== 'www.avito.ru') return false
    if (/\/orders(?:\/|$)/i.test(url.pathname)) return false
    return /_[0-9]{5,}(?:\/)?$/i.test(url.pathname) || /\/items\/[0-9]+(?:\/)?$/i.test(url.pathname)
  } catch (_error) {
    return false
  }
}

async function waitForTabListingUrl(tabId, timeoutMs = 9000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const tab = await chrome.tabs.get(tabId)
    if (isAvitoListingUrl(tab?.url)) return tab.url
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  return null
}

async function extractPageRuntimeDiagnostics(tabId, frameId, title, pageUrl) {
  const target = Number.isInteger(frameId) ? { tabId, frameIds: [frameId] } : { tabId }
  try {
    const diagnostics = await globalThis.SatornaRuntimeRetry.retryPageStateInspection(async () => {
      await chrome.scripting.executeScript({
        target,
        world: 'MAIN',
        files: ['src/page-state.js'],
      })
      const results = await chrome.scripting.executeScript({
        target,
        world: 'MAIN',
        func: async (expectedTitle, orderPageUrl) => {
          const api = globalThis.SatornaAvitoPageState
          if (!api) {
            return {
              apiAvailable: false,
              candidates: [],
              reactRoots: 0,
              resourceUrls: [],
            }
          }
          const inspected = api.inspectDocument(document, expectedTitle) || {
            candidates: [],
            reactRoots: 0,
            resourceUrls: [],
          }
          inspected.apiAvailable = true
          const stateCandidates = Array.isArray(inspected.candidates) ? inspected.candidates : []
          let timezone = ''
          try {
            timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
          } catch (_error) {
            // The profile order endpoint also works without this hint.
          }
          const directResource = api.profileOrderResourceUrl(orderPageUrl, timezone)
          inspected.resourceUrls = Array.from(new Set([
            ...(inspected.resourceUrls || []),
            directResource,
          ].filter(Boolean)))
          if (inspected.resourceUrls.length) {
            const loaded = await api.loadCandidatesFromOrderResources(inspected.resourceUrls, expectedTitle)
            inspected.candidates = loaded?.candidates?.length ? loaded.candidates : stateCandidates
            inspected.candidateSource = loaded?.candidates?.length ? 'profile-order-api' : 'page-state'
            inspected.resourceRequests = loaded?.requests || []
            inspected.resourceText = loaded?.resourceText || ''
          }
          return inspected
        },
        args: [title || '', pageUrl || ''],
      })
      return results.map((entry) => entry?.result).find((result) => result && typeof result === 'object') || {
        apiAvailable: false,
        candidates: [],
        reactRoots: 0,
        resourceUrls: [],
      }
    }, 3, async () => {
      await new Promise((resolve) => setTimeout(resolve, 250))
    })
    return diagnostics || { candidates: [], reactRoots: 0, resourceUrls: [] }
  } catch (error) {
    await writeLog('warn', 'react page state extraction failed', {
      tabId,
      frameId: Number.isInteger(frameId) ? frameId : null,
      error: error instanceof Error ? error.message : String(error),
    })
    return { candidates: [], reactRoots: 0, resourceUrls: [], error: error instanceof Error ? error.message : String(error) }
  }
}

async function extractDetailsInTab(url, options) {
  const resolvedUrl = assertAvitoUrl(url)
  await writeLog('info', 'opening detail tab', { url: resolvedUrl })
  const isOrderDetail = /\/orders\//i.test(resolvedUrl)
  const tab = await tabsCreate({ url: resolvedUrl, active: isOrderDetail })
  if (!tab?.id) throw new Error('Не удалось открыть деталку Avito')
  try {
    await waitForTabComplete(tab.id, 45000)
    await executeContentScript(tab.id, true)
    let response = null
    const startedAt = Date.now()
    let selectedFrame = null
    let frameDebug = []
    while (Date.now() - startedAt < 9000) {
      frameDebug = await classifyFrames(tab.id, options?.orderItemTitle || '')
      selectedFrame = bestFrame(frameDebug, isOrderDetail)
      const messageOptions = selectedFrame?.frameId ? { frameId: selectedFrame.frameId } : undefined
      response = await tabsSendMessage(tab.id, { type: 'AVITO_PAGE_EXTRACT_DETAILS', options: options || {} }, messageOptions)
      if (!response?.ok) throw new Error(response?.error || 'Не удалось прочитать деталку Avito')
      response.frameDebug = frameDebug
      response.selectedFrame = selectedFrame
      const hasListingLink = Array.isArray(response.itemUrls) && response.itemUrls.length > 0
      const hasListingContent = !isOrderDetail && ((response.description?.length || 0) > 20 || (response.images?.length || 0) > 0)
      const hasOrderContent = !isOrderDetail || selectedFrame?.hasExpectedTitle || selectedFrame?.hasOrderWords
      const waitingForInstruction = isOrderDetail && SatornaAvitoShipmentNumber.shouldWaitForInstruction(
        response, options?.requireShipmentNumber === true, Date.now() - startedAt,
      )
      if (!waitingForInstruction && ((isOrderDetail && hasOrderContent && (hasListingLink || Date.now() - startedAt > 3500)) || hasListingContent)) break
      await new Promise((resolve) => setTimeout(resolve, 700))
    }
    if (!response?.ok) throw new Error(response?.error || 'Не удалось прочитать деталку Avito')
    if (isOrderDetail && !selectedFrame?.hasExpectedTitle && !selectedFrame?.hasOrderWords) {
      response.detailNotRendered = true
      response.detailNotRenderedReason = 'DETAIL_PAGE_NOT_RENDERED'
      await writeLog('warn', 'order detail did not render expected content', {
        url: resolvedUrl,
        expectedTitle: options?.orderItemTitle || '',
        selectedFrame,
        frames: frameDebug,
      })
    }
    if (isOrderDetail && (!Array.isArray(response.itemUrls) || response.itemUrls.length === 0)) {
      const runtime = await extractPageRuntimeDiagnostics(
        tab.id,
        selectedFrame?.frameId,
        options?.orderItemTitle || '',
        resolvedUrl,
      )
      const stateCandidates = Array.isArray(runtime.candidates) ? runtime.candidates : []
      response.reactStateCandidates = stateCandidates.slice(0, 20)
      response.reactItemIds = stateCandidates.map((candidate) => candidate.itemId).filter(Boolean)
      response.runtimeResourceUrls = Array.isArray(runtime.resourceUrls) ? runtime.resourceUrls : []
      if (runtime.resourceText) {
        response.pageText = [response.pageText, runtime.resourceText].filter(Boolean).join('\n')
      }
      await writeLog('info', 'order detail runtime diagnostics', {
        orderUrl: resolvedUrl,
        frameId: Number.isInteger(selectedFrame?.frameId) ? selectedFrame.frameId : null,
        reactRoots: runtime.reactRoots || 0,
        statePropertyKeys: Array.isArray(runtime.statePropertyKeys) ? runtime.statePropertyKeys.slice(0, 40) : [],
        reactCandidates: stateCandidates.length,
        reactItemIds: response.reactItemIds.slice(0, 10),
        resourceUrls: response.runtimeResourceUrls.slice(-20),
        resourceRequests: Array.isArray(runtime.resourceRequests) ? runtime.resourceRequests.slice(-10) : [],
        resourceTextLength: String(runtime.resourceText || '').length,
        candidateSource: runtime.candidateSource || null,
        apiAvailable: Boolean(runtime.apiAvailable),
        inspectorAttempts: runtime.inspectorAttempts || 0,
        error: runtime.error || null,
      })
      const stateItemUrl = stateCandidates.find((candidate) => candidate.itemUrl)?.itemUrl
      if (stateItemUrl) {
        response.itemUrls = [stateItemUrl]
        response.itemUrlCandidates = [
          {
            url: stateItemUrl,
            source: runtime.candidateSource || 'page-state',
            score: stateCandidates[0]?.score || 100,
          },
          ...(response.itemUrlCandidates || []),
        ]
        await writeLog('info', 'order listing url found from order data', {
          orderUrl: resolvedUrl,
          listingUrl: stateItemUrl,
          itemId: stateCandidates[0]?.itemId || null,
        })
      }
    }
    if (isOrderDetail && (!Array.isArray(response.itemUrls) || response.itemUrls.length === 0)) {
      const clicked = await tabsSendMessage(tab.id, {
        type: 'AVITO_OPEN_LISTING_FROM_ORDER',
        title: options?.orderItemTitle || '',
        options: options || {},
      }, selectedFrame?.frameId ? { frameId: selectedFrame.frameId } : undefined)
      await writeLog(clicked?.ok ? 'info' : 'warn', 'order listing click attempted', {
        url: resolvedUrl,
        clicked: Boolean(clicked?.ok),
        title: options?.orderItemTitle || '',
        text: clicked?.text || null,
        error: clicked?.error || null,
      })
      if (clicked?.ok) {
        const listingUrl = await waitForTabListingUrl(tab.id, 9000)
        if (listingUrl) {
          response.itemUrls = [listingUrl]
          await writeLog('info', 'order listing url captured after click', { orderUrl: resolvedUrl, listingUrl })
        }
      }
    }
    await writeLog('info', 'detail extracted', {
      url: resolvedUrl,
      title: response.title,
      images: response.images?.length || 0,
      itemUrls: response.itemUrls?.length || 0,
      itemUrl: response.itemUrls?.[0] || null,
      candidates: response.itemUrlCandidates?.slice?.(0, 5) || [],
      linksCount: response.linksCount || 0,
      imagesCount: response.imagesCount || 0,
      htmlItemIds: response.htmlItemIds || [],
      reactItemIds: response.reactItemIds || [],
      reactStateCandidates: response.reactStateCandidates?.slice?.(0, 5) || [],
      selectedFrame: response.selectedFrame || null,
      detailNotRendered: Boolean(response.detailNotRendered),
      linkSamples: response.linkSamples || [],
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

async function avitoOrdersTab(url = AVITO_ORDERS_URL) {
  const tabs = await tabsQuery({ url: 'https://www.avito.ru/orders*' })
  const existing = tabs.find((tab) => tab.id)
  if (existing?.id) {
    await tabsUpdate(existing.id, { active: true, url })
    return existing
  }
  return tabsCreate({ url, active: true })
}

async function collectFromAvitoOrdersPage(url = AVITO_ORDERS_URL, collectionLabel = 'заказов') {
  const tab = await avitoOrdersTab(url)
  if (!tab?.id) throw new Error('Не удалось открыть страницу заказов Avito')
  await waitForTabComplete(tab.id)
  const settings = await readSettings()
  const message = { type: 'AVITO_ORDERS_COLLECT_NOW', options: { ...(settings.collectOptions || {}), collectionLabel } }
  try {
    return await tabsSendMessage(tab.id, message)
  } catch (_error) {
    await executeContentScript(tab.id)
    return tabsSendMessage(tab.id, message)
  }
}

function combineCollections(ordersPayload, returnsPayload) {
  const orders = Array.isArray(ordersPayload?.orders) ? ordersPayload.orders : []
  const returns = (Array.isArray(returnsPayload?.orders) ? returnsPayload.orders : [])
    .map((order) => ({ ...order, status: 'on_return' }))
  const all = [...orders, ...returns]
  const missing = ['imageUrl', 'size', 'color', 'sellerArticle'].reduce((result, key) => {
    result[key] = (ordersPayload?.collector?.missing?.[key] || 0) + (returnsPayload?.collector?.missing?.[key] || 0)
    return result
  }, {})
  return {
    capturedAt: new Date().toISOString(),
    pageUrl: ordersPayload?.pageUrl || AVITO_ORDERS_URL,
    collector: {
      ...(ordersPayload?.collector || {}),
      status: 'completed',
      pages: {
        orders: ordersPayload?.pageUrl || AVITO_ORDERS_URL,
        returns: returnsPayload?.pageUrl || AVITO_RETURNS_URL,
      },
      orders: orders.length,
      returns: returns.length,
      items: all.reduce((sum, order) => sum + (order.items?.length || 0), 0),
      missing,
      notes: [
        'Собраны данные со страниц заказов и возвратов Avito.',
        'Возвраты собираются тем же способом, что и обычные заказы.',
      ],
    },
    orders,
    returns,
  }
}

async function collectAndPostFromAvito() {
  await writeLog('info', 'collection requested from popup')
  await saveStatus({ ok: false, message: 'Открываем заказы Avito...' })
  const collected = await collectFromAvitoOrdersPage(AVITO_ORDERS_URL, 'заказов')
  if (!collected?.ok) throw new Error(collected?.error || 'Не удалось прочитать страницу заказов Avito')
  await saveStatus({ ok: false, message: `Заказы собраны: ${collected.payload?.orders?.length || 0}. Открываем возвраты Avito...` })
  const collectedReturns = await collectFromAvitoOrdersPage(AVITO_RETURNS_URL, 'возвратов')
  if (!collectedReturns?.ok) throw new Error(collectedReturns?.error || 'Не удалось прочитать страницу возвратов Avito')
  const payload = combineCollections(collected.payload, collectedReturns.payload)
  const missing = payload?.collector?.missing || {}
  await saveStatus({ ok: false, message: `Нашли заказов: ${payload?.orders?.length || 0}, возвратов: ${payload?.returns?.length || 0}. Не найдено: фото ${missing.imageUrl || 0}, размер ${missing.size || 0}, цвет ${missing.color || 0}. Отправляем в Satorna...` })
  const result = await postSnapshotWithFeedback(payload)
  let labelStatus = ''
  try {
    const labels = await collectLabels(payload)
    labelStatus = ` Этикеток сохранено: ${labels.labels || 0}.${labels.warnings?.length ? ' Есть этикетки, требующие проверки.' : ''}`
  } catch (error) {
    labelStatus = ` Заказы сохранены, этикетки не завершены: ${error instanceof Error ? error.message : 'ошибка получения'}`
  }
  const meta = result?.browserSnapshot
  const ai = meta?.aiExtraction || {}
  const sizeText = payload?.collector?.options?.sizeMode === 'chat_ai'
    ? ` Размеры: AI ${ai.aiSizeCount || 0}, из характеристик ${ai.descriptionFallbackCount || 0}, не найдено ${ai.missingFinalSizeCount || 0}.`
    : ''
  const text = `Собрано заказов: ${meta?.orders ?? payload?.orders?.length ?? 0}, возвратов: ${meta?.returns ?? payload?.returns?.length ?? 0}.${sizeText}${labelStatus}`
  await saveStatus({ ok: true, message: text })
  await writeLog('info', 'collection finished', { message: text, aiExtraction: ai })
  return { ok: true, result, message: text }
}

let labelsRunning = false
async function collectLabels(payload) {
  if (labelsRunning) throw new Error('Получение этикеток уже выполняется')
  const settings = await readSettings()
  if (!settings.accessToken) throw new Error('Сначала сохраните подключение к Satorna')
  const backendUrl = await apiUrlFromSettings(settings)
  const headers = { Authorization: authorizationValue(settings.accessToken) }
  let accounts = [...new Set((payload?.orders || []).map(order => order.accountId || ''))]
  if (!payload) {
    const response = await fetch(`${backendUrl}/api/v1/avito/orders/labels/collection-context`, { headers, redirect: 'error', credentials: 'omit' })
    if (!response.ok) throw new Error('Проверьте локальный адрес и токен расширения')
    accounts = (await response.json()).accountIds || []
  }
  if (accounts.length !== 1) throw new Error('Сначала соберите заказы одного аккаунта Авито')
  async function stage(value) {
    await fetch(`${backendUrl}/api/v1/avito/orders/labels/collection-status`, {
      method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, redirect: 'error', credentials: 'omit',
      body: JSON.stringify({ stage: value }), signal: AbortSignal.timeout(5000),
    }).catch(() => {})
  }
  labelsRunning = true
  let tab
  try {
    await stage('opening')
    await saveStatus({ ok: false, message: 'Заказы сохранены. Авито формирует PDF этикеток…' })
    tab = await chrome.tabs.create({ url: 'https://www.avito.ru/orders/print-labels', active: false })
    await waitForTabComplete(tab.id)
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, world: 'MAIN', func: SatornaLabels.observeDownloads })
    await stage('selecting')
    const generated = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: SatornaLabels.selectAndGenerate })
    const expected = generated[0]?.result || 0
    await stage('waiting_pdf')
    let url = null
    for (let i = 0; i < 45 && !url; i++) {
      await new Promise(resolve => setTimeout(resolve, 700))
      const tabs = await chrome.tabs.query({})
      url = tabs.filter(candidate => candidate.id === tab.id || candidate.openerTabId === tab.id)
        .map(candidate => SatornaLabels.downloadUrl(candidate.url || candidate.pendingUrl)).find(Boolean)
      if (url) break
      const results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, world: 'MAIN', func: () => [
        ...(window.__satornaLabels?.urls || []),
        ...performance.getEntriesByType('resource').map(entry => entry.name),
        ...[...document.querySelectorAll('a[href]')].map(a => a.href),
      ] }).catch(() => [])
      url = (results[0]?.result || []).map(SatornaLabels.downloadUrl).find(Boolean)
    }
    if (!url) throw new Error('Авито не предоставило ссылку на PDF. Страница этикеток оставлена открытой.')
    await stage('downloading')
    const pdf = await SatornaLabels.boundedPdf(await fetch(url, { credentials: 'include', redirect: 'error', signal: AbortSignal.timeout(30000) }))
    await stage('uploading')
    const response = await fetch(`${backendUrl}/api/v1/avito/orders/labels/import?accountId=${encodeURIComponent(accounts[0])}`, {
      method: 'POST', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(120000),
      headers: { Authorization: authorizationValue(settings.accessToken), 'Content-Type': 'application/pdf' }, body: pdf,
    })
    if (!response.ok) throw new Error(`Satorna не сохранила этикетки (HTTP ${response.status})`)
    const result = await response.json()
    if (result.ok !== true) throw new Error('Satorna не подтвердила сохранение PDF')
    if (result.labels < expected) result.warnings = [...(result.warnings || []), 'Не все выбранные этикетки распознаны']
    await notifyUploadStatus(result.labels >= expected, result.labels >= expected
      ? `Этикеток сохранено: ${result.labels}. Обновите заказы в Satorna.`
      : `PDF сохранён, распознано этикеток: ${result.labels} из ${expected}. Нераспознанные этикетки требуют проверки.`)
    return result
  } catch (error) {
    await stage('error')
    await notifyUploadStatus(false, error instanceof Error ? error.message : 'Не удалось получить этикетки')
    throw error
  } finally {
    if (tab?.id) await chrome.scripting.executeScript({ target: { tabId: tab.id }, world: 'MAIN', func: () => window.__satornaLabels?.restore?.() }).catch(() => {})
    labelsRunning = false
  }
}

let listingPhotosRunning = false
let listingPhotosStop = false
async function collectListingPhotos() {
  const settings = await readSettings()
  if (!settings.accessToken) throw new Error('Сначала сохраните подключение к Satorna')
  const backendUrl = await apiUrlFromSettings(settings)
  let photoTab = null, batchTab = null, blockedTabId = null
  const replacementTabs = new Map()
  function onPhotoTabReplaced(addedTabId, removedTabId) {
    replacementTabs.set(removedTabId, addedTabId)
    if (photoTab?.id === removedTabId) photoTab.id = addedTabId
    if (batchTab?.id === removedTabId) batchTab.id = addedTabId
    if (blockedTabId === removedTabId) blockedTabId = addedTabId
  }
  chrome.tabs.onReplaced.addListener(onPhotoTabReplaced)
  async function pagePhotos(tabId, ids, detailId = null) {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['src/item-photo.js', 'src/listing-photo-page.js'] })
    const result = await chrome.scripting.executeScript({ target: { tabId },
      func: (ids, detail) => globalThis.SatornaListingPhotoPage.read(ids, detail), args: [ids, detailId] })
    return result[0]?.result || { photos: {} }
  }
  function assertPhotoPage(result) {
    if (!result.blocked) return
    const error = new Error('Авито показывает проверку безопасности. Откройте вкладку Авито, пройдите проверку вручную и продолжите сбор. Фото в базе сохранятся.')
    error.stop = true
    throw error
  }
  async function readyPhotos(tabId, ids, detailId = null, previous = null, timeout = 8000) {
    const deadline = Date.now() + timeout
    let latest = { photos: {} }
    let stableSignature = '', stableSince = 0
    while (!listingPhotosStop && Date.now() < deadline) {
      try {
        while (replacementTabs.has(tabId)) tabId = replacementTabs.get(tabId)
        latest = await pagePhotos(tabId, ids, detailId)
        assertPhotoPage(latest)
        if (detailId && latest.photos[detailId]) return latest
        if (!detailId && latest.signature && latest.signature !== previous) {
          if (stableSignature !== latest.signature) { stableSignature = latest.signature; stableSince = Date.now() }
          if (latest.listReady && Date.now() - stableSince >= 750) return latest
        }
      } catch (error) {
        if (error.stop) {
          blockedTabId = tabId
          await chrome.tabs.update(tabId, { active: true })
          throw error
        }
        // A navigation may briefly replace the frame; read the next DOM, not window.load.
      }
      await new Promise(resolve => setTimeout(resolve, 250))
    }
    return latest
  }
  try { return await SatornaListingPhotos.collect({
    backendUrl, authorization: authorizationValue(settings.accessToken),
    shouldStop: () => listingPhotosStop,
    progress: status => chrome.storage.local.set({ listingPhotosStatus: { ...status, updatedAt: Date.now() } }),
    preparePhotos: async (rows, reportFound) => {
      const photos = {}, ids = rows.map(row => row.itemId)
      for (const tab of await chrome.tabs.query({ url: 'https://www.avito.ru/*' })) {
        if (listingPhotosStop) break
        try { Object.assign(photos, (await pagePhotos(tab.id, ids)).photos) } catch { /* Closed/reloading tab. */ }
      }
      await reportFound(Object.keys(photos).length)
      // A tiny remainder is faster to resolve directly than rescanning every list page.
      if (!listingPhotosStop && ids.length - Object.keys(photos).length > 5) {
        batchTab = await chrome.tabs.create({ url: 'https://www.avito.ru/profile/pro/items', active: true })
        let previous = null
        const seen = new Set()
        for (let page = 0; page < 50 && !listingPhotosStop; page++) {
          const result = await readyPhotos(batchTab.id, ids, null, previous, page === 0 ? 25000 : 8000)
          assertPhotoPage(result)
          Object.assign(photos, result.photos)
          await reportFound(Object.keys(photos).length, { pages: page + 1, pageItems: result.count || 0 })
          if (!result.signature || seen.has(result.signature) || Object.keys(photos).length >= ids.length) break
          seen.add(result.signature)
          previous = result.signature
          const advanced = await chrome.scripting.executeScript({ target: { tabId: batchTab.id }, func: () => globalThis.SatornaListingPhotoPage.advance() })
          if (!advanced[0]?.result) break
        }
      }
      return photos
    },
    loadPhoto: async row => {
      if (photoTab && !await chrome.tabs.get(photoTab.id).catch(() => null)) photoTab = null
      if (!photoTab) photoTab = await chrome.tabs.create({ url: row.url, active: false })
      else await chrome.tabs.update(photoTab.id, { url: row.url })
      const result = await readyPhotos(photoTab.id, [row.itemId], row.itemId, null, 10000)
      return result.photos[row.itemId] || null
    },
  }) } finally {
    chrome.tabs.onReplaced.removeListener(onPhotoTabReplaced)
    if (photoTab && photoTab.id !== blockedTabId) await chrome.tabs.remove(photoTab.id).catch(() => {})
    if (batchTab && batchTab.id !== blockedTabId) await chrome.tabs.remove(batchTab.id).catch(() => {})
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'AVITO_LISTING_PHOTOS_STATE') {
    sendResponse({ running: listingPhotosRunning })
    return false
  }
  if (message?.type === 'AVITO_LISTING_PHOTOS_STOP') {
    listingPhotosStop = true
    sendResponse({ ok: true })
    return false
  }
  if (message?.type === 'AVITO_LISTING_PHOTOS_COLLECT') {
    if (!listingPhotosRunning) {
      listingPhotosRunning = true
      listingPhotosStop = false
      void collectListingPhotos().catch(async error => {
        const stored = await chrome.storage.local.get('listingPhotosStatus')
        await chrome.storage.local.set({ listingPhotosStatus: { ...stored.listingPhotosStatus, stage: 'error', message: error.message, updatedAt: Date.now() } })
      }).finally(() => { listingPhotosRunning = false })
    }
    sendResponse({ ok: true })
    return false
  }
  if (message?.type === 'AVITO_LABELS_COLLECT') {
    collectLabels().then(result => sendResponse({ ok: true, message: `Распознано этикеток: ${result.labels}`, result }))
      .catch(error => sendResponse({ ok: false, error: error instanceof Error ? error.message : 'Не удалось получить этикетки' }))
    return true
  }
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
  postSnapshotWithFeedback(message.payload)
    .then(async (result) => {
      const meta = result?.browserSnapshot
      let labelText = ''
      try { labelText = ` Этикеток: ${(await collectLabels(message.payload)).labels}` }
      catch (error) { labelText = ` Этикетки не получены: ${error instanceof Error ? error.message : 'ошибка'}` }
      const text = `Собрано заказов: ${meta?.orders ?? message.payload?.orders?.length ?? 0}.${labelText}`
      return saveStatus({ ok: true, message: text }).then(() => sendResponse({ ok: true, result, message: text }))
    })
    .catch((error) => {
      const text = error instanceof Error ? error.message : String(error)
      return saveStatus({ ok: false, message: text }).then(() => sendResponse({ ok: false, error: text }))
    })
  return true
})
