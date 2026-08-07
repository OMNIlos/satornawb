importScripts('runtime-retry.js')

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
  return chrome.scripting.executeScript({ target: { tabId, allFrames }, files: ['src/content.js'] })
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
      if ((isOrderDetail && hasOrderContent && (hasListingLink || Date.now() - startedAt > 3500)) || hasListingContent) break
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
