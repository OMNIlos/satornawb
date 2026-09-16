'use strict'
importScripts('contract.js')

const C = WbPricesContract
const API = 'https://api.elfprint-system.ru/api/v1/wb/browser-prices'
const ALARM = 'wb-price-collector'
const CYCLE_DELAY = 20 * 60 * 1000
const emptyState = () => ({ status: 'disconnected', reason: null, catalog: null, tabId: null, pageUrl: null,
  seen: {}, visited: [], sellers: [], pendingSellers: [], partialSellers: 0, catalogPage: 0,
  accepted: 0, ignored: 0, unmatched: 0, verifiedAt: null, lastAckAt: null, retryAfterSeconds: null,
  pendingRequest: null, nextRunAt: null, pageDeadline: null, scrollAt: null })
let state = emptyState()
let token = null
let stopped = false
let timeout = null
let scrollTimer = null
let timerGeneration = 0
let controlGeneration = 0
let savedControl = null
let serial = Promise.resolve()

const ready = (async () => {
  await chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' })
  await chrome.storage.session.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' })
  const local = await chrome.storage.local.get(['token', 'control', 'stopRequested'])
  token = local.token
  const stored = await chrome.storage.session.get(['state', 'stopRequested'])
  const saved = stored.state
  if (saved) state = { ...emptyState(), ...saved }
  else if (token && local.control) {
    state.pendingRequest = local.control.pendingRequest || null
    if (local.control.enabled) { state.status = 'waiting'; state.nextRunAt = local.control.nextRunAt || Date.now() }
    else if (local.control.reason) { state.status = 'paused'; state.reason = local.control.reason }
  }
  if (!token) state = emptyState()
  stopped = Boolean(stored.stopRequested || local.stopRequested)
  if (stopped && token) { state.status = 'paused'; state.reason = 'user_stopped' }
  else if (state.status !== 'paused' && state.pendingRequest?.kind === 'snapshot') { state.status = 'paused'; state.reason = 'submission_unknown' }
  else if (state.status !== 'paused' && state.pendingRequest?.kind === 'refresh') state.status = 'refreshing'
  if (state.status === 'running' && !state.pageDeadline && !state.scrollAt) state.pageDeadline = Date.now() + 25000
  await save()
  // Recover the short page deadline as well as the durable alarm after suspension.
  if (state.status === 'running') {
    const generation = timerGeneration
    timeout = setTimeout(() => enqueue(async () => {
      if (generation === timerGeneration) await runScheduled()
    }).catch(fail), Math.max(0, (state.scrollAt || state.pageDeadline) - Date.now()))
  }
})()

function enqueue(run) {
  const result = serial.then(() => ready).then(run)
  serial = result.catch(() => {})
  return result
}

function clearTimers() {
  timerGeneration += 1
  clearTimeout(timeout); clearTimeout(scrollTimer)
  timeout = scrollTimer = null
  state.pageDeadline = state.scrollAt = null
}

async function save() {
  await chrome.storage.session.set({ state })
  const control = { enabled: !stopped && ['running', 'waiting', 'refreshing'].includes(state.status),
    nextRunAt: state.nextRunAt, reason: state.status === 'paused' ? state.reason : null, pendingRequest: state.pendingRequest }
  const serialized = JSON.stringify(control)
  if (serialized !== savedControl) { await chrome.storage.local.set({ control }); savedControl = serialized }
  const due = state.status === 'refreshing' ? state.pendingRequest?.startedAt + 125000
    : state.status === 'waiting' ? state.nextRunAt : state.status === 'running' ? state.scrollAt || state.pageDeadline : null
  // One durable wakeup supplements short in-memory timers on Chromium 111+.
  if (!stopped && due) await chrome.alarms.create(ALARM, { when: Math.max(Date.now() + 60000, due) })
  else await chrome.alarms.clear(ALARM)
}

function seenFresh(offer) {
  const observation = state.seen[C.key(offer)]
  return observation && observation.seller === offer.sellerPriceKopecks
    && Date.now() - observation.time <= Math.min(state.catalog.maxAgeSeconds, 1800) * 1000
}

function publicState() {
  const items = state.catalog?.items || []
  return { status: state.status, reason: state.reason, totalOffers: items.length,
    observedOffers: items.filter(seenFresh).length, totalProducts: new Set(items.map((item) => item.nmId)).size,
    visitedProducts: state.visited.length, sellersVisited: state.sellers.length, partialSellers: state.partialSellers,
    accepted: state.accepted, ignored: state.ignored, unmatched: state.unmatched,
    verifiedAt: state.verifiedAt, lastAckAt: state.lastAckAt, retryAfterSeconds: state.retryAfterSeconds, nextRunAt: state.nextRunAt }
}

async function pause(reason) {
  stopped = true
  clearTimers()
  state.status = token ? 'paused' : 'disconnected'
  state.reason = reason
  state.nextRunAt = null
  await save()
}

function safeError(error) {
  const code = error?.message
  return /^(catalog_(invalid|changed|stale)|refresh_(cooldown|unavailable|busy)|observation_stale|ack_invalid|token_invalid|stop_first|page_timeout|tab_closed|tab_changed|crm_http_(401|403|409|429|500|502|503))$/.test(code || '') ? code : 'request_failed'
}

async function fail(error) {
  const code = safeError(error)
  state.pendingRequest = null
  state.retryAfterSeconds = error?.retryAfterSeconds || null
  if (code === 'crm_http_401') {
    token = null
    await chrome.storage.local.remove('token')
  }
  await pause(code)
  return { ok: false, code, state: publicState() }
}

async function api(path, { method = 'GET', body, accessToken = token } = {}) {
  if (stopped) throw new Error('stopped')
  const response = await fetch(`${API}${path}`, { method, credentials: 'omit', redirect: 'error',
    headers: { Accept: 'application/json', Authorization: `Bearer ${accessToken}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}), signal: AbortSignal.timeout(path === '/catalog/refresh' ? 125000 : 20000) })
  if (!response.ok) {
    const error = new Error(`crm_http_${response.status}`)
    error.httpStatus = response.status
    const allowed = {
      WB_BROWSER_GOODS_STALE: [409, 'catalog_stale'], WB_BROWSER_GOODS_CHANGED: [409, 'catalog_changed'],
      WB_BROWSER_REFRESH_BUSY: [409, 'refresh_busy'], WB_BROWSER_REFRESH_COOLDOWN: [429, 'refresh_cooldown'],
      WB_BROWSER_REFRESH_UNAVAILABLE: [503, 'refresh_unavailable'],
    }
    if ([409, 429, 503].includes(response.status)) {
      try {
        const payload = await response.json()
        const detail = payload?.error || payload?.detail
        if (allowed[detail?.code]?.[0] === response.status) {
          error.serverCode = detail.code
          error.message = allowed[detail.code][1]
          const header = response.headers?.get('Retry-After')
          const retry = detail.details?.retryAfterSeconds ?? detail.retryAfterSeconds ?? (/^\d+$/.test(header || '') ? Number(header) : null)
          if (Number.isSafeInteger(retry) && retry > 0 && retry <= 86400) error.retryAfterSeconds = retry
        }
      } catch { /* Raw error bodies never reach UI or storage. */ }
    }
    throw error
  }
  return response.json()
}

async function loadCatalog(accessToken = token, refreshed = false) {
  try {
  let catalog = null
  const items = []; const keys = new Set()
  for (let page = 1; !catalog || items.length < catalog.total; page++) {
    const value = C.validateCatalogPage(await api(`/catalog?page=${page}&pageSize=100`, { accessToken }), page, catalog)
    catalog ||= value
    for (const item of value.items) {
      if (keys.has(C.key(item))) throw new Error('catalog_invalid')
      keys.add(C.key(item)); items.push(item)
    }
  }
  state.catalog = { ...catalog, items }
  state.verifiedAt = new Date().toISOString()
  } catch (error) {
    if (error.serverCode !== 'WB_BROWSER_GOODS_STALE') throw error
    // This specific response establishes that the extension bearer was verified.
    error.catalogAuthenticated = true
    if (refreshed) throw error
    try {
      token = accessToken
      await chrome.storage.local.set({ token })
      state.pendingRequest = { kind: 'refresh', startedAt: Date.now(), resumeStatus: state.status }
      state.status = 'refreshing'
      await save()
      const ack = await api('/catalog/refresh', { method: 'POST', accessToken })
      if (ack?.ok !== true || typeof ack.goodsRevision !== 'string' || !ack.goodsRevision || !Number.isSafeInteger(ack.total) || ack.total < 0) throw new Error('ack_invalid')
      await loadCatalog(accessToken, true)
      state.status = state.pendingRequest.resumeStatus
      state.pendingRequest = null
    } catch (refreshError) { refreshError.catalogAuthenticated = true; throw refreshError }
  }
}

async function closeOwnedTab() {
  const tabId = state.tabId
  state.tabId = null
  if (tabId === null) return
  try {
    const tab = await chrome.tabs.get(tabId)
    // A tab navigated by the user is no longer ours to close or redirect.
    if (C.pageIdentity(tab.url) === C.pageIdentity(state.pageUrl)) await chrome.tabs.remove(tabId)
  } catch { /* The user may already have closed the collector. */ }
}

async function navigate(url) {
  if (stopped || state.status !== 'running') return
  clearTimers()
  let owned = null
  if (state.tabId !== null) {
    try { owned = await chrome.tabs.get(state.tabId) } catch { /* Create a new owned tab below. */ }
    if (owned && C.pageIdentity(owned.url) !== C.pageIdentity(state.pageUrl)) throw new Error('tab_changed')
  }
  state.pageUrl = url
  state.catalogPage = 0
  // Persist the expected URL before navigation can deliver document_start messages.
  await save()
  if (stopped) return
  if (owned) await chrome.tabs.update(state.tabId, { url, active: false })
  else {
    state.tabId = (await chrome.tabs.create({ url: 'about:blank', active: false })).id
    await save()
    if (stopped) return
    await chrome.tabs.update(state.tabId, { url, active: false })
  }
  await save()
  await waitForPage()
}

async function pageTimeout() {
  if (C.sellerId(state.pageUrl)) { state.partialSellers += 1; await nextPage() }
  else await pause('page_timeout')
}

async function waitForPage() {
  clearTimeout(timeout)
  const generation = ++timerGeneration
  state.scrollAt = null
  state.pageDeadline = Date.now() + 25000
  await save()
  if (stopped || state.status !== 'running' || generation !== timerGeneration) return
  timeout = setTimeout(() => enqueue(async () => {
    if (generation !== timerGeneration || stopped || state.status !== 'running') return
    await pageTimeout()
  }).catch(fail), 25000)
}

async function nextPage() {
  if (stopped || state.status !== 'running') return
  const remaining = state.catalog.items.filter((item) => !seenFresh(item))
  if (remaining.length && state.pendingSellers.length) {
    const supplier = state.pendingSellers.shift()
    state.sellers.push(supplier)
    return navigate(`${C.WB_ORIGIN}/seller/${supplier}`)
  }
  const item = remaining.find((item) => !state.visited.includes(item.nmId))
  if (item) return navigate(`${C.WB_ORIGIN}/catalog/${item.nmId}/detail.aspx`)
  clearTimers()
  state.status = 'waiting'
  state.nextRunAt = Date.now() + CYCLE_DELAY
  state.reason = remaining.length ? 'partial_coverage' : null
  await closeOwnedTab()
  await save()
}

async function submit(observations, receivedAt) {
  if (Date.now() - receivedAt > 300000) throw new Error('observation_stale')
  if (state.catalog.items.some((item) => Date.now() - Date.parse(item.sellerPriceObservedAt) > state.catalog.maxAgeSeconds * 1000)) await loadCatalog()
  const observedAt = new Date(receivedAt).toISOString()
  const current = C.snapshotItems(observations, state.catalog.items, observedAt)
  state.unmatched += current.ignored
  const pending = current.items.filter((item) => {
    const seen = state.seen[C.key(item)]
    return !seen || seen.buyer !== item.buyerPriceNoWalletKopecks || seen.seller !== item.sellerPriceKopecks || !seenFresh(item)
  })
  for (let start = 0; start < pending.length && !stopped; start += 100) {
    if (Date.now() - receivedAt > 300000) throw new Error('observation_stale')
    let items = C.snapshotItems(pending.slice(start, start + 100), state.catalog.items, observedAt).items
    if (!items.length) continue
    let ack
    state.pendingRequest = { kind: 'snapshot', startedAt: Date.now() }
    await save()
    try { ack = await api('/snapshots', { method: 'POST', body: { goodsRevision: state.catalog.goodsRevision, items } }) }
    catch (error) {
      if (error.httpStatus !== 409 || stopped) throw error
      await loadCatalog()
      items = C.snapshotItems(items, state.catalog.items, observedAt).items
      if (!items.length || stopped) { state.pendingRequest = null; continue }
      state.pendingRequest = { kind: 'snapshot', startedAt: Date.now() }
      await save()
      ack = await api('/snapshots', { method: 'POST', body: { goodsRevision: state.catalog.goodsRevision, items } })
    }
    if (ack?.ok !== true || !Number.isSafeInteger(ack.accepted) || ack.accepted < 0
      || !Number.isSafeInteger(ack.ignored) || ack.ignored < 0 || ack.accepted + ack.ignored !== items.length
      || !Number.isFinite(Date.parse(ack.observedAt))) throw new Error('ack_invalid')
    state.accepted += ack.accepted
    state.ignored += ack.ignored
    state.lastAckAt = ack.observedAt
    for (const item of items) state.seen[C.key(item)] = { buyer: item.buyerPriceNoWalletKopecks, seller: item.sellerPriceKopecks, time: receivedAt }
    state.pendingRequest = null
    await save()
  }
}

async function observe(message, sender, receivedAt) {
  if (state.status !== 'running' || !C.isTrustedPageSender(sender, chrome.runtime.id, state.tabId, state.pageUrl)) return { ok: false, code: 'sender_not_allowed' }
  const observation = C.sanitizePageMessage(message, state.pageUrl)
  if (!observation) return { ok: false, code: 'observation_invalid' }
  if (observation.type === 'blocked') { await pause(observation.code); return { ok: true } }
  if (stopped) return { ok: false, code: 'stopped' }
  const pageUrl = state.pageUrl
  await submit(observation.items, receivedAt)
  if (stopped) return { ok: true }
  const nmIds = new Set(state.catalog.items.map((item) => item.nmId))
  for (const item of observation.items) {
    if (nmIds.has(item.nmId) && C.integer(item.supplierId) && !state.sellers.includes(item.supplierId) && !state.pendingSellers.includes(item.supplierId)) state.pendingSellers.push(item.supplierId)
  }
  const nmId = C.cardNmId(pageUrl)
  if (nmId && observation.items.some((item) => item.nmId === nmId)) {
    if (!state.visited.includes(nmId)) state.visited.push(nmId)
    await nextPage()
  } else if (C.sellerId(pageUrl) && observation.catalogPage > state.catalogPage) {
    state.catalogPage = observation.catalogPage
    clearTimers()
    if (observation.productCount === 0 || state.catalog.items.every(seenFresh)) await nextPage()
    else {
      state.scrollAt = Date.now() + 1500
      const generation = timerGeneration
      await save()
      scrollTimer = setTimeout(() => enqueue(async () => {
        if (generation !== timerGeneration || stopped || state.status !== 'running' || state.pageUrl !== pageUrl) return
        await chrome.tabs.sendMessage(state.tabId, { type: 'scroll' })
        await waitForPage()
      }).catch(fail), 1500)
    }
  }
  await save()
  return { ok: true }
}

async function command(message, generation = controlGeneration) {
  if (message.type === 'status') return { ok: true, state: publicState() }
  if (message.type === 'stop') { await pause('user_stopped'); return { ok: true, state: publicState() } }
  if (message.type === 'disconnect') {
    stopped = true; clearTimers()
    await closeOwnedTab()
    token = null; await chrome.storage.local.remove('token')
    state = emptyState(); await save()
    return { ok: true, state: publicState() }
  }
  if (!['connect', 'start', 'resume'].includes(message.type)) return { ok: false, code: 'command_invalid' }
  if (generation !== controlGeneration) return { ok: false, code: 'stopped', state: publicState() }
  if (state.status === 'running') throw new Error('stop_first')
  stopped = false
  await chrome.storage.session.remove('stopRequested')
  await chrome.storage.local.remove('stopRequested')
  if (message.type === 'connect') {
    const candidate = message.token?.trim() || token
    if (typeof candidate !== 'string' || !/^sat_wbp_[A-Za-z0-9_-]{32,256}$/.test(candidate)) throw new Error('token_invalid')
    await closeOwnedTab()
    state = emptyState()
    try { await loadCatalog(candidate) }
    catch (error) {
      if (error.catalogAuthenticated && error.httpStatus !== 401) {
        token = candidate
        await chrome.storage.local.set({ token })
      }
      throw error
    }
    token = candidate
    await chrome.storage.local.set({ token })
    state.status = stopped ? 'paused' : 'ready'
  } else {
    if (!token) throw new Error('token_invalid')
    if (message.type === 'resume' || !state.catalog) await loadCatalog(token, state.pendingRequest?.kind === 'refresh')
    if (stopped) return { ok: false, code: 'stopped', state: publicState() }
    if (message.type === 'start') {
      state.seen = {}; state.visited = []; state.sellers = []; state.pendingSellers = []
      state.accepted = state.ignored = state.unmatched = state.partialSellers = 0
    }
    state.status = 'running'; state.reason = null; state.retryAfterSeconds = state.nextRunAt = state.pendingRequest = null
    if (message.type === 'resume' && C.pageIdentity(state.pageUrl)) await navigate(state.pageUrl)
    else await nextPage()
  }
  await save()
  return { ok: true, state: publicState() }
}

chrome.runtime.onMessage.addListener((message, sender, respond) => {
  const popup = C.isTrustedPopupSender(sender, chrome.runtime.id)
  if (popup && message?.type === 'status') {
    void ready.then(() => respond({ ok: true, state: publicState() })).catch(() => respond({ ok: false, code: 'request_failed' }))
    return true
  }
  const receivedAt = Date.now()
  if (popup && ['stop', 'disconnect'].includes(message?.type)) {
    stopped = true; controlGeneration += 1; clearTimers()
    void chrome.storage.session.set({ stopRequested: true })
    void chrome.storage.local.set({ stopRequested: true })
  }
  if (!popup && C.isTrustedPageSender(sender, chrome.runtime.id, state.tabId, state.pageUrl)
    && C.sanitizePageMessage(message, state.pageUrl)?.type === 'blocked') { stopped = true; clearTimers() }
  const generation = controlGeneration
  void enqueue(() => popup ? command(message || {}, generation) : observe(message, sender, receivedAt)).catch(fail).then(respond)
  return true
})

async function runScheduled() {
    if (stopped) return
    if (state.status === 'refreshing' && Date.now() >= state.pendingRequest.startedAt + 125000) {
      const previous = state.pendingRequest.resumeStatus
      await loadCatalog(token, true) // The prior POST may have completed; never repeat it on recovery.
      state.pendingRequest = null
      state.status = previous === 'running' ? 'running' : 'ready'
      if (state.status === 'running') {
        if (C.pageIdentity(state.pageUrl)) await navigate(state.pageUrl)
        else await nextPage()
      }
    } else if (state.status === 'waiting' && Date.now() >= state.nextRunAt) {
      await loadCatalog()
      await command({ type: 'start' })
    } else if (state.status === 'running') {
      if (state.scrollAt && Date.now() >= state.scrollAt) {
        await chrome.tabs.sendMessage(state.tabId, { type: 'scroll' })
        await waitForPage()
      } else if (state.pageDeadline && Date.now() >= state.pageDeadline) await pageTimeout()
    }
    await save()
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM) return enqueue(runScheduled).catch(fail)
})

chrome.runtime.onStartup.addListener(() => enqueue(runScheduled).catch(fail))

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === state.tabId) {
    stopped = true; clearTimers()
    void enqueue(async () => { state.tabId = null; await pause('tab_closed') }).catch(fail)
  }
})
