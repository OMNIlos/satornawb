import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'
import test from 'node:test'

const source = await readFile(new URL('../src/connection.js', import.meta.url), 'utf8')
const background = await readFile(new URL('../src/background.js', import.meta.url), 'utf8')
const popup = await readFile(new URL('../src/popup.js', import.meta.url), 'utf8')
function harness() {
  const sync = { backendUrl: 'https://ogni-frontend.vercel.app', accessToken: 'synthetic-legacy' }
  const local = {}
  const store = (data) => ({
    get: async (defaults) => ({ ...defaults, ...data }),
    set: async (values) => Object.assign(data, values),
    remove: async (keys) => keys.forEach(key => delete data[key]),
  })
  const calls = []
  const context = vm.createContext({ URL, console: { info() {}, error() {}, warn() {} },
    chrome: { storage: { sync: store(sync), local: store(local) }, runtime: { onMessage: { addListener() {} } } },
    importScripts() {}, fetch: async (url, options) => {
      calls.push({ url, options })
      return { ok: true, status: 200, text: async () => JSON.stringify({ ok: true }) }
    },
  })
  vm.runInContext(source, context)
  vm.runInContext(background, context)
  return { connection: context.SatornaConnection, context, sync, local, calls }
}

test('accepts loopback HTTP and explicit HTTPS origins', () => {
  const { connection } = harness()
  for (const url of ['http://127.0.0.1:5177', 'http://localhost:58017', 'http://[::1]:5177', 'https://app.elfprint-system.ru', 'https://satorna.example']) {
    assert.equal(connection.normalize(` ${url}/ `), url)
  }
})

test('uses current production and migrates the retired hosted origins', () => {
  const { connection } = harness()
  assert.equal(connection.defaultUrl, 'https://app.elfprint-system.ru')
  for (const retired of ['https://ogni-frontend.vercel.app', 'https://satorna-wb.vercel.app', 'https://satorna-wb.vercel.app/']) {
    assert.equal(connection.normalize(retired), connection.defaultUrl)
  }
})

test('rejects unsafe or ambiguous server addresses', () => {
  const { connection } = harness()
  for (const url of ['', 'javascript:alert(1)', 'http://example.com', 'https://user:pass@example.com', 'https://example.com/avito/orders', 'https://example.com/?token=x', 'https://example.com/#x', 'http://localhost.evil.test']) {
    assert.throws(() => connection.normalize(url))
  }
})

test('legacy configuration is preserved until explicit save, then connection stays local', async () => {
  const { connection, sync, local } = harness()
  assert.equal((await connection.read()).accessToken, 'synthetic-legacy')
  await connection.save('http://127.0.0.1:5177/', 'synthetic-local')
  assert.equal((await connection.read()).backendUrl, 'http://127.0.0.1:5177')
  assert.equal(local.connection.accessToken, 'synthetic-local')
  assert.equal(sync.accessToken, undefined)
})

test('snapshot goes only to loopback, keeps photo metadata, forbids redirects and cookies', async () => {
  const { connection, context, calls } = harness()
  await connection.save('http://127.0.0.1:5177', 'synthetic-local')
  const payload = { orders: [{ orderId: 'synthetic', items: [{ imageUrl: 'https://70.img.avito.st/synthetic.jpg', size: 'M', color: 'синий', sellerArticle: 'TEST' }] }] }
  context.payload = payload
  await vm.runInContext('postSnapshot(payload)', context)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].url, 'http://127.0.0.1:5177/api/v1/avito/orders/browser-snapshot')
  assert.equal(calls[0].options.headers.Authorization, 'Bearer synthetic-local')
  assert.equal(calls[0].options.redirect, 'error')
  assert.equal(calls[0].options.credentials, 'omit')
  assert.deepEqual(JSON.parse(calls[0].options.body), payload)
})

test('failed localhost delivery never falls back to hosted Satorna', async () => {
  const { connection, context, calls } = harness()
  await connection.save('http://127.0.0.1:5177', 'synthetic-local')
  context.fetch = async (url) => { calls.push(url); throw new Error('offline') }
  await assert.rejects(vm.runInContext('postSnapshot({ orders: [] })', context), /offline/)
  assert.deepEqual(calls, ['http://127.0.0.1:5177/api/v1/avito/orders/browser-snapshot'])
})

test('collector shows upload failure or confirmed save, not premature success', async () => {
  const { connection, context } = harness()
  await connection.save('http://127.0.0.1:5177', 'synthetic-local')
  const notifications = []
  context.chrome.tabs = {
    query: (_query, done) => done([{ id: 1 }]),
    sendMessage: (_id, message, _options, done) => { notifications.push(message); done({ ok: true }) },
  }
  await vm.runInContext('postSnapshotWithFeedback({ orders: [] })', context)
  assert.equal(notifications[0].ok, true)
  context.fetch = async () => { throw new Error('offline') }
  await assert.rejects(vm.runInContext('postSnapshotWithFeedback({ orders: [] })', context), /offline/)
  assert.equal(notifications[1].ok, false)
  assert.match(notifications[1].message, /127.0.0.1:5177/)
})

test('popup clears token when switching server, requires save, and persists local configuration', async () => {
  const { context, local } = harness()
  const elements = new Map()
  const messages = []
  context.document = { body: { dataset: {} }, getElementById(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', textContent: '', classList: { toggle() {}, add() {}, remove() {} }, handlers: {},
      addEventListener(type, handler) { this.handlers[type] = handler },
      dispatchEvent(event) { this.handlers[event.type]?.(event) }, focus() {},
    })
    return elements.get(id)
  } }
  context.window = { clearTimeout() {}, setTimeout() {} }
  context.Event = class { constructor(type) { this.type = type } }
  context.chrome.runtime.sendMessage = async (message) => { messages.push(message); return { ok: true, logs: [] } }
  context.chrome.storage.onChanged = { addListener() {} }
  vm.runInContext(popup, context)
  await vm.runInContext('loadSettings()', context)
  assert.equal(elements.get('accessToken').value, 'synthetic-legacy')
  elements.get('localServerBtn').handlers.click()
  assert.equal(elements.get('backendUrl').value, 'http://127.0.0.1:5177')
  assert.equal(elements.get('accessToken').value, '')
  elements.get('accessToken').value = 'synthetic-local'
  elements.get('accessToken').handlers.input()
  await assert.rejects(vm.runInContext('collectOrders()', context), /сохраните/)
  assert.equal(messages.some(m => m.type === 'AVITO_ORDERS_OPEN_AND_COLLECT'), false)
  await vm.runInContext('saveSettings()', context)
  assert.equal(local.connection.accessToken, 'synthetic-local')
  await vm.runInContext('loadSettings()', context)
  assert.equal(elements.get('backendUrl').value, 'http://127.0.0.1:5177')
  assert.equal(elements.get('accessToken').value, 'synthetic-local')
})
