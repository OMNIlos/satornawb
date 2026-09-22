import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const page = 'https://www.wildberries.ru/catalog/1025784485/detail.aspx'
const detail = 'https://www.wildberries.ru/__internal/u-card/cards/v4/detail?curr=rub&nm=1025784485'
const flush = () => new Promise((resolve) => setImmediate(resolve))

function load(status = 200) {
  const sent = []; const requests = []
  const response = { status, url: detail, clone: () => ({ json: async () => ({ products: [{ id: 1025784485, sizes: [{ optionId: 123, price: { product: 130800, wallet: 0 }, secret: 'hidden' }] }], credentials: 'hidden' }) }) }
  const original = (...args) => { requests.push(args); return Promise.resolve(response) }
  class XHR {
    open(method, url) { this.method = method; this.url = url }
    addEventListener(name, listener) { this.listener = listener }
    send() { this.status = status; this.responseURL = this.url; this.responseType = 'json'; this.response = { products: [{ id: 1025784485, sizes: [{ optionId: 123, price: { product: 130800 } }] }] }; this.listener?.() }
  }
  const context = vm.createContext({ URL, Date, Object, Number, Promise, location: new URL(page), fetch: original, XMLHttpRequest: XHR, postMessage: (data, origin) => sent.push({ data: JSON.parse(JSON.stringify(data)), origin }) })
  context.window = context
  for (const name of ['contract.js', 'observer.js']) {
    const path = new URL(`../src/${name}`, import.meta.url)
    assert.ok(existsSync(path), `${name} is implemented`)
    vm.runInContext(readFileSync(path, 'utf8'), context)
  }
  return { context, response, requests, sent }
}

test('passive fetch observer preserves the page response and emits only sanitized prices', async () => {
  const { context, response, requests, sent } = load()
  const options = { credentials: 'include', headers: { Authorization: 'page-private' } }
  assert.equal(await context.fetch(detail, options), response)
  await flush()
  assert.equal(requests.length, 1)
  assert.equal(requests[0][1], options)
  assert.deepEqual(sent, [{ origin: 'https://www.wildberries.ru', data: { source: 'satorna-wb-prices-v1', type: 'observations', items: [{ nmId: 1025784485, sizeId: 123, buyerPriceNoWalletKopecks: 130800 }], loadedNmId: 1025784485 } }])
})

test('passive XHR observer handles normal detail responses and does not fetch anything', () => {
  const { context, requests, sent } = load()
  const xhr = new context.XMLHttpRequest()
  xhr.open('GET', detail)
  xhr.send()
  assert.equal(requests.length, 0)
  assert.equal(sent[0].data.items[0].buyerPriceNoWalletKopecks, 130800)
})

test('403 and 429 are reported once without a retry; unrelated requests are ignored', async () => {
  for (const status of [403, 429]) {
    const { context, requests, sent } = load(status)
    await context.fetch(detail)
    await flush()
    assert.equal(requests.length, 1)
    assert.deepEqual(sent[0].data, { source: 'satorna-wb-prices-v1', type: 'blocked', code: `http_${status}` })
  }
  const { context, sent } = load()
  await context.fetch(detail.replace('/detail?', '/other?'))
  await flush()
  assert.deepEqual(sent, [])
})
