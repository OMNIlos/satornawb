import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

function load({ url = 'https://www.wildberries.ru/seller/4405572', title = 'Wildberries', next = null } = {}) {
  let now = Date.now(); let timer;
  class Clock extends Date { static now() { return now } }
  const sent = []; const scrolled = []; const listeners = {}; let runtimeListener
  const document = { title, readyState: 'complete', body: { innerText: '' }, documentElement: { scrollHeight: 5000 },
    querySelector: () => null, querySelectorAll: () => next ? [next] : [], addEventListener: (name, fn) => { listeners[name] = fn } }
  Object.defineProperty(document, 'cookie', { get() { throw new Error('WB cookies must never be read') } })
  const context = vm.createContext({ URL, Date: Clock, Object, Number, location: new URL(url), document,
    chrome: { runtime: { id: 'ext', sendMessage: async (value) => { sent.push(JSON.parse(JSON.stringify(value))); return { ok: true } }, onMessage: { addListener: (fn) => { runtimeListener = fn } } } },
    MutationObserver: class { observe() {} }, setTimeout: (fn) => { timer = fn; return 1 }, clearTimeout: () => { timer = null },
    addEventListener: (name, fn) => { listeners[name] = fn }, innerHeight: 800, scrollBy: (data) => scrolled.push(data) })
  context.window = context; context.top = context
  for (const name of ['contract.js', 'content.js']) {
    const path = new URL(`../src/${name}`, import.meta.url)
    assert.ok(existsSync(path), `${name} is implemented`)
    vm.runInContext(readFileSync(path, 'utf8'), context)
  }
  return { context, sent, scrolled, listeners, tick: (ms) => { now += ms; timer?.() }, document, runtime: (...args) => runtimeListener(...args) }
}

test('isolated bridge ignores foreign windows/origins and strips untrusted fields', () => {
  const h = load()
  const data = { source: 'satorna-wb-prices-v1', type: 'observations', items: [{ nmId: 100, sizeId: 200, buyerPriceNoWalletKopecks: 10000, token: 'secret', buyerPriceWithWalletKopecks: 1 }] }
  h.listeners.message({ source: {}, origin: 'https://www.wildberries.ru', data })
  h.listeners.message({ source: h.context, origin: 'https://evil.test', data })
  assert.equal(h.sent.length, 0)
  vm.runInContext(`window.dispatchForTest = (fn, data) => fn({ source: window, origin: 'https://www.wildberries.ru', data })`, h.context)
  h.context.dispatchForTest(h.listeners.message, data)
  assert.deepEqual(h.sent, [{ source: 'satorna-wb-prices-v1', type: 'observations', items: [{ nmId: 100, sizeId: 200, buyerPriceNoWalletKopecks: 10000 }] }])
})

test('collector scroll is a bounded native action and foreign commands do nothing', () => {
  const h = load(); const replies = []
  h.runtime({ type: 'scroll' }, { id: 'other' }, (value) => replies.push(value))
  assert.equal(h.scrolled.length, 0)
  h.runtime({ type: 'scroll' }, { id: 'ext' }, (value) => replies.push(value))
  assert.equal(h.scrolled.length, 1)
  assert.equal(h.scrolled[0].top, 640)
  assert.equal(replies.at(-1).ok, true)
  assert.equal(h.sent.length, 0)
  h.document.querySelectorAll = (selector) => {
    assert.ok(selector.includes('pagination') || selector === '.catalog-page__main article[data-nm-id]')
    return selector.includes('pagination') ? [] : [{ getClientRects: () => [1], scrollIntoView: (options) => h.scrolled.push(options) }]
  }
  h.runtime({ type: 'scroll' }, { id: 'ext' }, () => {})
  assert.equal(h.scrolled.at(-1).block, 'center')
})

test('an actually present next-page control is used without constructing a seller page URL', () => {
  let clicked = 0
  const next = { textContent: 'Следующая страница', disabled: false, href: 'https://www.wildberries.ru/seller/4405572?page=2',
    getClientRects: () => [1], getAttribute: () => null, click: () => clicked++ }
  const h = load({ next })
  h.runtime({ type: 'scroll' }, { id: 'ext' }, () => {})
  assert.equal(clicked, 1)
  assert.equal(h.scrolled.length, 0)
})

test('a challenge only emits a fixed stop code, without page text or cookies', () => {
  const h = load({ title: 'Access denied' })
  assert.equal(h.sent.length, 0)
  h.tick(10000)
  assert.deepEqual(h.sent, [{ source: 'satorna-wb-prices-v1', type: 'blocked', code: 'challenge' }])
  const transient = load({ title: 'Проверка браузера' })
  transient.document.title = 'Товар Wildberries'
  transient.tick(10000)
  assert.equal(transient.sent.length, 0)
})
