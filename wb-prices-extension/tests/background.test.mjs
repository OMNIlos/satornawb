import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const TOKEN = `sat_wbp_${'a'.repeat(43)}`
const API = 'https://api.elfprint-system.ru/api/v1/wb/browser-prices'
const clone = (value) => JSON.parse(JSON.stringify(value))
const card = (id) => `https://www.wildberries.ru/catalog/${id}/detail.aspx`
const seller = 'https://www.wildberries.ru/seller/4405572'
const offer = (nmId, sizeId = 123) => ({ nmId, sizeId, sellerPriceKopecks: 170000, sellerPriceObservedAt: new Date().toISOString() })

function harness({ offers = [offer(1025784485)], postStatuses = [], catalogStatus = 200, catalogStatuses = [], refreshStatus = 200, local = {}, session = {}, existingTabs = [], postGate = null, catalogGate = null, productionEnvelope = false } = {}) {
  const calls = []; const access = []; const timers = new Map(); let timerId = 0
  const tabs = new Map([[7, { id: 7, url: 'https://example.test', active: true }], ...existingTabs.map((tab) => [tab.id, clone(tab)])])
  const alarms = new Map()
  const navigations = []; const scrolls = []; const removed = []
  let listener; let removedListener; let alarmListener; let startupListener; let nextTab = 100; let revision = 'revision-1'
  const area = (values, name) => ({
    setAccessLevel: async (level) => access.push([name, level.accessLevel]),
    get: async (key) => typeof key === 'string' ? { [key]: clone(values[key] ?? null) } : clone(values),
    set: async (value) => { access.push([name, 'set']); Object.assign(values, clone(value)) },
    remove: async (key) => { delete values[key] },
  })
  const chrome = {
    storage: { local: area(local, 'local'), session: area(session, 'session') },
    runtime: { id: 'ext', getURL: (path) => `chrome-extension://ext/${path}`, onMessage: { addListener: (fn) => { listener = fn } }, onStartup: { addListener: (fn) => { startupListener = fn } } },
    alarms: {
      create: async (name, options) => alarms.set(name, clone(options)),
      clear: async (name) => alarms.delete(name), get: async (name) => alarms.get(name),
      onAlarm: { addListener: (fn) => { alarmListener = fn } },
    },
    tabs: {
      create: async (data) => { const tab = { id: nextTab++, ...data }; tabs.set(tab.id, tab); navigations.push(clone(tab)); return clone(tab) },
      get: async (id) => { if (!tabs.has(id)) throw new Error('not found'); return clone(tabs.get(id)) },
      update: async (id, data) => { assert.notEqual(id, 7, 'user tab is preserved'); Object.assign(tabs.get(id), data); navigations.push({ id, ...data }); return clone(tabs.get(id)) },
      remove: async (id) => { assert.notEqual(id, 7); removed.push(id); tabs.delete(id) },
      sendMessage: async (id, data) => { scrolls.push({ id, ...data }); return { ok: true } },
      onRemoved: { addListener: (fn) => { removedListener = fn } },
    },
  }
  const fetch = async (url, options) => {
    calls.push({ url, ...clone({ ...options, signal: undefined }) })
    assert.ok(url.startsWith(`${API}/`), 'requests stay on the fixed CRM API')
    assert.equal(options.credentials, 'omit')
    assert.equal(options.redirect, 'error')
    assert.equal(options.headers.Authorization, `Bearer ${TOKEN}`)
    const errorBody = (code) => productionEnvelope ? { error: { code, message: 'never-render-this', details: {} } }
      : { detail: { code, retryAfterSeconds: 60, unsafe: 'never-render-this' } }
    if (url.endsWith('/catalog/refresh')) {
      assert.equal(options.method, 'POST')
      assert.equal(options.body, undefined)
      if (refreshStatus === 200) revision = 'revision-2'
      return { ok: refreshStatus === 200, status: refreshStatus, headers: new Headers({ 'Retry-After': '60' }), json: async () => refreshStatus === 200
        ? { ok: true, goodsRevision: revision, total: offers.length }
        : errorBody(refreshStatus === 429 ? 'WB_BROWSER_REFRESH_COOLDOWN' : refreshStatus === 409 ? 'WB_BROWSER_REFRESH_BUSY' : 'WB_BROWSER_REFRESH_UNAVAILABLE') }
    }
    if (url.includes('/catalog?')) {
      if (catalogGate) { const gate = catalogGate; catalogGate = null; gate.started(); await gate.wait }
      const page = Number(new URL(url).searchParams.get('page'))
      const status = catalogStatuses.shift() ?? catalogStatus
      return { ok: status === 200, status, json: async () => status === 409
        ? errorBody('WB_BROWSER_GOODS_STALE')
        : ({ marketplaceAccountId: 2, goodsRevision: revision, page, pageSize: 100, total: offers.length, maxAgeSeconds: 1800, items: offers.slice((page - 1) * 100, page * 100) }) }
    }
    assert.equal(url, `${API}/snapshots`)
    if (postGate) { const gate = postGate; postGate = null; gate.started(); await gate.wait }
    const status = postStatuses.shift() ?? 200
    if (status === 409) revision = 'revision-2'
    const body = JSON.parse(options.body)
    return { ok: status === 200, status, json: async () => ({ ok: true, accepted: body.items.length, ignored: 0, observedAt: new Date().toISOString(), forbiddenEcho: 'must-not-render' }) }
  }
  const context = vm.createContext({ chrome, fetch, URL, Date, Object, Number, Promise, AbortSignal,
    setTimeout: (fn, delay) => { timers.set(++timerId, { fn, delay }); return timerId }, clearTimeout: (id) => timers.delete(id) })
  context.importScripts = (path) => vm.runInContext(readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8'), context)
  const path = new URL('../src/background.js', import.meta.url)
  assert.ok(existsSync(path), 'background collector is implemented')
  vm.runInContext(readFileSync(path, 'utf8'), context)
  const send = (message, sender) => new Promise((resolve) => { assert.equal(listener(message, sender, resolve), true) })
  const popup = (message) => send(message, { id: 'ext', url: 'chrome-extension://ext/src/popup.html' })
  const page = (message, overrides = {}) => {
    const tab = [...tabs.values()].find((tab) => tab.id !== 7)
    return send({ source: 'satorna-wb-prices-v1', type: 'observations', ...message }, { id: 'ext', frameId: 0, url: tab?.url, tab: clone(tab ?? {}), ...overrides })
  }
  const fire = (delay) => { const entry = [...timers].find(([, timer]) => timer.delay === delay); assert.ok(entry); timers.delete(entry[0]); return entry[1].fn() }
  return { popup, page, calls, local, session, access, tabs, navigations, scrolls, removed, timers, alarms,
    closeOwned: () => removedListener(100),
    fire, tick: async (delay) => { await fire(delay); await popup({ type: 'status' }) },
    alarm: async () => { assert.equal(typeof alarmListener, 'function'); await alarmListener({ name: 'wb-price-collector', scheduledTime: Date.now() }); return popup({ type: 'status' }) },
    startup: async () => { assert.equal(typeof startupListener, 'function'); await startupListener(); return popup({ type: 'status' }) },
  }
}

function gate() {
  let release; let started
  const wait = new Promise((resolve) => { release = resolve })
  const entered = new Promise((resolve) => { started = resolve })
  return { wait, release, started, entered }
}

test('production error envelope invokes one refresh and respects HTTP Retry-After', async () => {
  const h = harness({ catalogStatuses: [409, 200], productionEnvelope: true })
  assert.equal((await h.popup({ type: 'connect', token: TOKEN })).state.status, 'ready')
  assert.equal(h.calls.filter((call) => call.url.endsWith('/catalog/refresh')).length, 1)
  for (const status of [409, 429, 503]) {
    const limited = harness({ catalogStatuses: [409], refreshStatus: status, productionEnvelope: true })
    const result = await limited.popup({ type: 'connect', token: TOKEN })
    assert.equal(result.state.status, 'paused')
    assert.equal(result.state.retryAfterSeconds, 60)
    assert.equal(limited.calls.length, 2)
    assert.equal(JSON.stringify(result).includes('never-render-this'), false)
  }
})

test('the popup can reveal only the owned collector tab after a WB challenge', async () => {
  const h = harness()
  await h.popup({ type: 'connect', token: TOKEN })
  await h.popup({ type: 'start' })
  await h.page({ type: 'blocked', code: 'challenge' })
  const result = await h.popup({ type: 'show_tab' })
  assert.equal(result.ok, true)
  assert.equal(result.state.status, 'paused')
  assert.deepEqual(h.navigations.at(-1), { id: 100, active: true })
  h.tabs.get(100).url = 'https://example.test'
  assert.equal((await h.popup({ type: 'show_tab' })).code, 'tab_changed')
})

test('queued timeout from the previous card cannot interrupt the new seller page', async () => {
  const postGate = gate()
  const h = harness({ offers: [offer(1025784485), offer(200)], postGate })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const observation = h.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800, supplierId: 4405572 }] })
  await postGate.entered
  const expired = h.fire(25000)
  postGate.release()
  await observation; await expired
  const state = (await h.popup({ type: 'status' })).state
  assert.equal(state.status, 'running')
  assert.equal(state.partialSellers, 0)
  assert.equal(h.navigations.at(-1).url, seller)
})

test('a card without a price does not stop other products; a WB block still pauses', async () => {
  const h = harness({ offers: [offer(100), offer(200), offer(300)] })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  await h.tick(25000)
  assert.equal(h.navigations.at(-1).url, card(200))
  assert.equal((await h.popup({ type: 'status' })).state.observedOffers, 0)
  await h.page({ items: [{ nmId: 200, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }] })
  assert.equal(h.navigations.at(-1).url, card(300))
  await h.page({ type: 'blocked', code: 'http_429' })
  const state = (await h.popup({ type: 'status' })).state
  assert.equal(state.status, 'paused')
  assert.equal(state.observedOffers, 1)
  assert.equal(state.reason, 'http_429')
})

test('stop during an in-flight chunk preserves its acknowledgement and sends no second chunk', async () => {
  const postGate = gate()
  const offers = Array.from({ length: 101 }, (_, index) => offer(1000 + index))
  const h = harness({ offers, postGate })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const submitted = h.page({ items: offers.map((item) => ({ nmId: item.nmId, sizeId: item.sizeId, buyerPriceNoWalletKopecks: 130800 })) })
  await postGate.entered
  const stopped = h.popup({ type: 'stop' })
  const reopened = harness({ local: clone(h.local) })
  await reopened.startup()
  assert.equal((await reopened.popup({ type: 'status' })).state.status, 'paused', 'browser restart must retain a stop issued before the POST returned')
  assert.equal(reopened.calls.length, 0)
  postGate.release()
  await submitted; await stopped
  const state = (await h.popup({ type: 'status' })).state
  assert.equal(state.status, 'paused')
  assert.equal(state.accepted, 100)
  assert.equal(h.calls.filter((call) => call.url.endsWith('/snapshots')).length, 1)
})

test('stop during catalog GET prevents another page or a stale-cache refresh POST', async () => {
  for (const catalogStatus of [200, 409]) {
    const catalogGate = gate()
    const h = harness({ offers: Array.from({ length: 101 }, (_, index) => offer(1000 + index)), catalogStatus, catalogGate })
    const connected = h.popup({ type: 'connect', token: TOKEN })
    await catalogGate.entered
    const stopped = h.popup({ type: 'stop' })
    catalogGate.release()
    await connected; await stopped
    assert.equal(h.calls.length, 1)
    assert.equal(h.navigations.length, 0)
    assert.equal((await h.popup({ type: 'status' })).state.reason, 'user_stopped')
  }
})

test('stop during a recurring catalog read remains paused after closing the browser', async () => {
  const catalogGate = gate()
  const h = harness({ local: { token: TOKEN, control: { enabled: true, nextRunAt: Date.now() - 1 } }, catalogGate })
  const running = h.startup()
  await catalogGate.entered
  const stopping = h.popup({ type: 'stop' })
  const reopened = harness({ local: clone(h.local) })
  await reopened.startup()
  catalogGate.release()
  await running; await stopping
  assert.equal((await reopened.popup({ type: 'status' })).state.status, 'paused')
  assert.equal(reopened.calls.length, 0)
})

test('manual resume revisits the paused seller instead of skipping its offers', async () => {
  const h = harness({ offers: [offer(1025784485), offer(200)] })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  await h.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800, supplierId: 4405572 }] })
  await h.page({ type: 'blocked', code: 'http_429' })
  await h.popup({ type: 'resume' })
  assert.equal(h.navigations.at(-1).url, seller)
})

test('MV3 suspension preserves running progress and completed cycles repeat through a native alarm', async () => {
  const h = harness()
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const restored = harness({ local: clone(h.local), session: clone(h.session), existingTabs: [...h.tabs.values()].filter((tab) => tab.id !== 7) })
  assert.equal((await restored.popup({ type: 'status' })).state.status, 'running')
  await restored.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }] })
  assert.equal((await restored.popup({ type: 'status' })).state.status, 'waiting')
  assert.ok(restored.alarms.size)
  const next = clone(restored.session)
  next.state.nextRunAt = Date.now() - 1
  const nextCycle = harness({ local: clone(restored.local), session: next })
  await nextCycle.alarm()
  assert.equal((await nextCycle.popup({ type: 'status' })).state.status, 'running')
  assert.equal(nextCycle.navigations.at(-1).url, card(1025784485))
  await nextCycle.popup({ type: 'stop' })
  await nextCycle.alarm()
  assert.equal((await nextCycle.popup({ type: 'status' })).state.status, 'paused')
  assert.equal(nextCycle.alarms.size, 0)
})

test('interrupted POSTs recover safely: refresh reads only, unknown snapshot pauses', async () => {
  const h = harness(); await h.popup({ type: 'connect', token: TOKEN })
  const base = { ...clone(h.session.state), pendingRequest: { kind: 'refresh', startedAt: Date.now() - 130000, resumeStatus: 'ready' } }
  const refresh = harness({ local: { token: TOKEN }, session: { state: base } })
  await refresh.alarm()
  assert.equal((await refresh.popup({ type: 'status' })).state.status, 'ready')
  assert.equal(refresh.calls.length, 1)
  assert.equal(refresh.calls[0].method, 'GET')
  const snapshot = harness({ local: { token: TOKEN }, session: { state: { ...base, status: 'running', pendingRequest: { kind: 'snapshot' } } } })
  const state = (await snapshot.popup({ type: 'status' })).state
  assert.equal(state.status, 'paused')
  assert.equal(state.reason, 'submission_unknown')
  assert.equal(snapshot.calls.length, 0)
})

test('browser restart restores enabled collection, but never revives an explicit pause', async () => {
  const h = harness()
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const local = clone(h.local)
  assert.equal(local.control.enabled, true)
  assert.equal(JSON.stringify(local.control).includes('sellerPrice'), false)
  const reopened = harness({ local })
  await reopened.startup()
  assert.equal((await reopened.popup({ type: 'status' })).state.status, 'running')
  assert.equal(reopened.navigations.filter((tab) => tab.url.startsWith('https://')).length, 1)
  await reopened.popup({ type: 'stop' })
  const paused = harness({ local: clone(reopened.local) })
  await paused.startup(); await paused.alarm()
  assert.equal((await paused.popup({ type: 'status' })).state.status, 'paused')
  assert.equal(paused.calls.length, 0)
  assert.equal(paused.navigations.length, 0)
})

test('known refresh rejection remains paused after a worker restart', async () => {
  const h = harness({ catalogStatuses: [409], refreshStatus: 429, productionEnvelope: true })
  await h.popup({ type: 'connect', token: TOKEN })
  const restored = harness({ local: clone(h.local), session: clone(h.session) })
  await restored.alarm()
  assert.equal((await restored.popup({ type: 'status' })).state.status, 'paused')
  assert.equal(restored.calls.length, 0)
})

test('connection is verified by CRM, token is trusted-local only, and page messages cannot configure it', async () => {
  const h = harness()
  assert.equal((await h.popup({ type: 'status' })).state.status, 'disconnected')
  const connected = await h.popup({ type: 'connect', token: TOKEN, apiUrl: 'https://evil.test' })
  assert.equal(connected.state.status, 'ready')
  assert.equal(h.local.token, TOKEN)
  assert.equal(JSON.stringify(h.session).includes(TOKEN), false)
  assert.equal(JSON.stringify(connected).includes(TOKEN), false)
  assert.deepEqual(h.access[0], ['local', 'TRUSTED_CONTEXTS'])
  assert.equal(h.calls.length, 1)
  const rejected = await h.page({ type: 'connect', token: TOKEN }, { tab: { id: 7, url: card(1025784485) }, url: card(1025784485) })
  assert.equal(rejected.ok, false)
  assert.equal(h.calls.length, 1)
})

test('stale seller cache refreshes once, restarts pagination, and cooldown does not loop', async () => {
  const h = harness({ offers: Array.from({ length: 101 }, (_, index) => offer(1000 + index)), catalogStatuses: [200, 409, 200, 200] })
  assert.equal((await h.popup({ type: 'connect', token: TOKEN })).state.status, 'ready')
  assert.deepEqual(h.calls.map((call) => call.url.slice(API.length)), [
    '/catalog?page=1&pageSize=100', '/catalog?page=2&pageSize=100', '/catalog/refresh', '/catalog?page=1&pageSize=100', '/catalog?page=2&pageSize=100',
  ])
  for (const status of [429, 503]) {
    const limited = harness({ catalogStatuses: [409], refreshStatus: status })
    const result = await limited.popup({ type: 'connect', token: TOKEN })
    assert.equal(result.ok, false)
    assert.equal(result.state.status, 'paused')
    assert.equal(result.state.retryAfterSeconds, 60)
    assert.equal(limited.calls.length, 2)
    assert.equal(limited.timers.size, 0)
    assert.equal(JSON.stringify(result).includes('never-render-this'), false)
  }
  const stillStale = harness({ catalogStatuses: [409, 409] })
  assert.equal((await stillStale.popup({ type: 'connect', token: TOKEN })).ok, false)
  assert.equal(stillStale.calls.filter((call) => call.url.endsWith('/catalog/refresh')).length, 1)
})

test('owned top-frame observations produce an exact snapshot once; all user tabs survive', async () => {
  const h = harness()
  await h.popup({ type: 'connect', token: TOKEN })
  await h.popup({ type: 'start' })
  assert.equal(h.navigations[0].active, false)
  assert.equal(h.navigations[0].url, 'about:blank', 'claim the owned tab before starting a WB document')
  assert.equal(h.navigations[1].url, card(1025784485))
  const observation = { items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800, buyerPriceWithWalletKopecks: 1 }] }
  await h.page(observation, { frameId: 1 })
  assert.equal(h.calls.filter((call) => call.method === 'POST').length, 0)
  await h.page(observation)
  const posts = h.calls.filter((call) => call.method === 'POST')
  assert.equal(posts.length, 1)
  const body = JSON.parse(posts[0].body)
  assert.equal(body.goodsRevision, 'revision-1')
  assert.deepEqual({ ...body.items[0], observedAt: 'time' }, { nmId: 1025784485, sizeId: 123, sellerPriceKopecks: 170000, buyerPriceNoWalletKopecks: 130800, buyerPriceWithWalletKopecks: null, observedAt: 'time' })
  const state = (await h.popup({ type: 'status' })).state
  assert.equal(state.status, 'waiting')
  assert.equal(state.accepted, 1)
  assert.equal(state.observedOffers, 1)
  await h.page(observation)
  assert.equal(h.calls.filter((call) => call.method === 'POST').length, 1)
  assert.equal(h.tabs.get(7).url, 'https://example.test')
})

test('discovered seller is visited normally; bulk prices are filtered then remaining products continue', async () => {
  const h = harness({ offers: [offer(1025784485), offer(200), offer(300)] })
  await h.popup({ type: 'connect', token: TOKEN })
  await h.popup({ type: 'start' })
  await h.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800, supplierId: 4405572 }] })
  assert.equal(h.navigations.at(-1).url, seller)
  await h.page({ items: [
    { nmId: 200, sizeId: 123, buyerPriceNoWalletKopecks: 120000, supplierId: 4405572 },
    { nmId: 999, sizeId: 123, buyerPriceNoWalletKopecks: 120000, supplierId: 4405572 },
  ], catalogPage: 1, productCount: 2 })
  const posts = h.calls.filter((call) => call.method === 'POST')
  assert.equal(JSON.parse(posts.at(-1).body).items.length, 1)
  await h.tick(1500)
  assert.equal(h.scrolls.at(-1).type, 'scroll')
  await h.page({ items: [], catalogPage: 2, productCount: 0 })
  assert.equal(h.navigations.at(-1).url, card(300))
})

test('page 403/429/challenge pauses the run without automatic retries', async () => {
  for (const code of ['http_403', 'http_429', 'challenge']) {
    const h = harness()
    await h.popup({ type: 'connect', token: TOKEN })
    await h.popup({ type: 'start' })
    await h.page({ type: 'blocked', code })
    const state = (await h.popup({ type: 'status' })).state
    assert.equal(state.status, 'paused')
    assert.equal(state.reason, code)
    assert.equal(h.navigations.filter((tab) => tab.url.startsWith('https://')).length, 1)
    assert.equal(h.timers.size, 0)
    assert.equal(h.calls.filter((call) => call.method === 'POST').length, 0)
  }
})

test('409 refreshes catalog once and revalidates before one retry', async () => {
  const h = harness({ postStatuses: [409, 200] })
  await h.popup({ type: 'connect', token: TOKEN })
  await h.popup({ type: 'start' })
  await h.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }] })
  const posts = h.calls.filter((call) => call.method === 'POST')
  assert.deepEqual(posts.map((call) => JSON.parse(call.body).goodsRevision), ['revision-1', 'revision-2'])
  assert.equal((await h.popup({ type: 'status' })).state.accepted, 1)
  const failed = harness({ postStatuses: [409, 409] })
  await failed.popup({ type: 'connect', token: TOKEN }); await failed.popup({ type: 'start' })
  await failed.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }] })
  assert.equal(failed.calls.filter((call) => call.method === 'POST').length, 2)
  assert.equal((await failed.popup({ type: 'status' })).state.status, 'paused')
})

test('401 removes the token and stale seller catalog cannot establish a connection', async () => {
  const h = harness({ postStatuses: [401] })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  await h.page({ items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }] })
  assert.equal(h.local.token, undefined)
  assert.equal((await h.popup({ type: 'status' })).state.status, 'disconnected')
  const stale = harness({ offers: [{ ...offer(1025784485), sellerPriceObservedAt: '2020-01-01T00:00:00Z' }] })
  assert.equal((await stale.popup({ type: 'connect', token: TOKEN })).ok, false)
  assert.equal(stale.local.token, undefined)
  assert.notEqual((await stale.popup({ type: 'status' })).state.status, 'ready')
})

test('bulk submissions are bounded to 100 and serialized', async () => {
  const offers = Array.from({ length: 101 }, (_, index) => offer(1000 + index))
  const h = harness({ offers })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const message = { items: offers.map((item) => ({ nmId: item.nmId, sizeId: item.sizeId, buyerPriceNoWalletKopecks: 130800 })) }
  await Promise.all([h.page(message), h.page(message)])
  assert.deepEqual(h.calls.filter((call) => call.method === 'POST').map((call) => JSON.parse(call.body).items.length), [100, 1])
  assert.equal((await h.popup({ type: 'status' })).state.accepted, 101)
})

test('stop, disconnect and a worker restart never take control of an existing user tab', async () => {
  const h = harness()
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  const saved = clone(h.session)
  await h.popup({ type: 'stop' })
  assert.equal((await h.popup({ type: 'status' })).state.status, 'paused')
  await h.popup({ type: 'disconnect' })
  assert.equal(h.local.token, undefined)
  assert.equal(h.tabs.has(7), true)
  const restarted = harness({ local: { token: TOKEN }, session: saved })
  assert.equal((await restarted.popup({ type: 'status' })).state.status, 'running')
  assert.equal(restarted.navigations.length, 0)
})

 test('a loaded sold-out card advances without waiting or inventing a price', async () => {
  const h = harness({ offers: [offer(100), offer(200)] })
  await h.popup({ type: 'connect', token: TOKEN }); await h.popup({ type: 'start' })
  await h.page({ items: [], loadedNmId: 100 })
  const state = (await h.popup({ type: 'status' })).state
  assert.equal(state.status, 'running')
  assert.equal(state.observedOffers, 0)
  assert.equal(state.visitedProducts, 1)
  assert.equal(h.navigations.at(-1).url, card(200))
  assert.equal(h.calls.filter((call) => call.url.endsWith('/snapshots')).length, 0)
})
