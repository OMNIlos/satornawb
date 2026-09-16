import assert from 'node:assert/strict'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { resolve, join } from 'node:path'

// Optional real Chromium smoke using the workspace's existing Playwright install.
const require = createRequire(new URL('../../frontend/package.json', import.meta.url))
const { chromium } = require('playwright')
const profile = await mkdtemp(join(tmpdir(), 'satorna-wb-extension-check-'))
const output = resolve('output/playwright')
await mkdir(output, { recursive: true })
const errors = []; const blocked = []
let context
// A local deny-only proxy is installed before Chromium starts, so even the first
// navigation of a tabs.create target cannot escape Playwright interception.
let deniedConnections = 0
const denyProxy = createServer((socket) => { deniedConnections += 1; socket.destroy() })
await new Promise((resolve) => denyProxy.listen(0, '127.0.0.1', resolve))
try {
  context = await chromium.launchPersistentContext(profile, {
    channel: 'chromium', headless: true, viewport: { width: 380, height: 600 },
    proxy: { server: `http://127.0.0.1:${denyProxy.address().port}` },
    args: [`--disable-extensions-except=${resolve('dist')}`, `--load-extension=${resolve('dist')}`],
  })
  await context.setOffline(true)
  context.on('page', (page) => { page.on('pageerror', (error) => errors.push(error.message)) })
  await context.route(/https?:\/\//, async (route) => {
    const url = new URL(route.request().url())
    if (url.origin !== 'https://www.wildberries.ru') { blocked.push(url.origin); return route.abort() }
    let payload
    if (url.pathname === '/__internal/u-card/cards/v4/detail' && url.searchParams.get('nm') === '1001') {
      payload = { products: [{ id: 1001, supplierId: 101, sizes: [{ optionId: 11, price: { product: 130800, wallet: 0 } }] }] }
    } else if (url.pathname === '/__internal/u-catalog/sellers/v4/catalog') {
      payload = { products: [{ id: 2002, supplierId: 101, sizes: [{ optionId: 22, price: { product: 120000 } }] }] }
    }
    if (payload) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
    const request = url.pathname === '/catalog/1001/detail.aspx' ? '/__internal/u-card/cards/v4/detail?curr=rub&nm=1001'
      : url.pathname === '/seller/101' ? '/__internal/u-catalog/sellers/v4/catalog?curr=rub&supplier=101&page=1' : null
    if (!request) { blocked.push(url.pathname); return route.abort() }
    return route.fulfill({ status: 200, contentType: 'text/html', body: `<!doctype html><html><head><title>Synthetic WB fixture</title></head><body><article data-nm-id="1001">Offline fixture</article><script>fetch(${JSON.stringify(request)}).then(r=>r.json())</script></body></html>` })
  })
  const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker')
  const extensionId = new URL(worker.url()).host
  await worker.evaluate(() => {
    self.fixtureCalls = { catalog: 0, snapshots: 0 }
    self.fetch = async (url, options) => {
      const prefix = 'https://api.elfprint-system.ru/api/v1/wb/browser-prices'
      if (!url.startsWith(prefix) || options.credentials !== 'omit' || options.redirect !== 'error') throw new Error('Fixture destination rejected')
      const json = (value) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } })
      if (url === `${prefix}/catalog?page=1&pageSize=100`) {
        self.fixtureCalls.catalog += 1
        return json({ marketplaceAccountId: 2, goodsRevision: 'a'.repeat(64), page: 1, pageSize: 100, total: 3, maxAgeSeconds: 1800,
          items: [[1001, 11], [2002, 22], [3003, 33]].map(([nmId, sizeId]) => ({ nmId, sizeId, sellerPriceKopecks: 170000, sellerPriceObservedAt: new Date().toISOString() })) })
      }
      if (url === `${prefix}/snapshots` && options.method === 'POST') {
        const value = JSON.parse(options.body)
        if (value.items.some((item) => item.buyerPriceWithWalletKopecks !== null)) throw new Error('Wallet must remain unknown')
        self.fixtureCalls.snapshots += 1
        return json({ ok: true, accepted: value.items.length, ignored: 0, observedAt: new Date().toISOString() })
      }
      throw new Error('Unexpected fixture request')
    }
  })
  const popup = await context.newPage()
  // Chromium's action popup is not a Playwright Page in headless mode. Keep the
  // production sender guard intact; this local UI bridge calls worker commands.
  await popup.exposeFunction('fixtureCommand', (message) => worker.evaluate(async (value) => {
    await ready
    return command(value)
  }, message))
  await popup.addInitScript(() => { chrome.runtime.sendMessage = (message) => window.fixtureCommand(message) })
  popup.on('pageerror', (error) => errors.push(error.message))
  await popup.goto(`chrome-extension://${extensionId}/src/popup.html`)
  await popup.getByText('Не подключено', { exact: true }).waitFor()
  assert.equal(await popup.locator('#start').isDisabled(), true)
  await popup.locator('#token').fill(`sat_wbp_${'a'.repeat(43)}`)
  await popup.getByRole('button', { name: 'Проверить подключение', exact: true }).click()
  await popup.getByText('Каталог проверен', { exact: true }).waitFor()
  assert.equal(await popup.locator('#token').inputValue(), '')
  await popup.getByRole('button', { name: 'Начать сбор', exact: true }).click()
  await popup.waitForFunction(() => document.getElementById('coverage').textContent === '2 / 3', null, { timeout: 12000 }).catch(async (error) => {
    console.error(JSON.stringify(await worker.evaluate(() => ({ state: publicState(), calls: self.fixtureCalls }))))
    console.error(JSON.stringify({ errors, blocked }))
    for (const page of context.pages().filter((item) => item.url().startsWith('https://www.wildberries.ru/'))) {
      console.error(JSON.stringify(await page.evaluate(() => ({ fixturePath: location.pathname, contractInstalled: typeof WbPricesContract,
        fetchWrapped: fetch.toString().includes('Reflect.apply'), resources: performance.getEntriesByType('resource').map((entry) => new URL(entry.name).pathname),
        contentLength: document.body?.textContent.length, fetchSource: fetch.toString() }))))
    }
    await popup.screenshot({ path: join(output, 'popup-failed.png'), fullPage: true })
    throw error
  })
  assert.equal(await popup.locator('#accepted').textContent(), '2')
  await popup.screenshot({ path: join(output, 'popup-running.png'), fullPage: true })
  await popup.getByRole('button', { name: 'Остановить', exact: true }).click()
  await popup.getByText('Сбор приостановлен', { exact: true }).waitFor()
  assert.equal(await popup.locator('#resume').isDisabled(), false)
  await popup.screenshot({ path: join(output, 'popup-paused.png'), fullPage: true })
  await popup.getByRole('button', { name: 'Забыть ключ', exact: true }).click()
  await popup.getByText('Не подключено', { exact: true }).waitFor()
  const local = await worker.evaluate(() => chrome.storage.local.get('token'))
  assert.equal(local.token, undefined)
  assert.deepEqual(await worker.evaluate(() => self.fixtureCalls), { catalog: 1, snapshots: 2 })
  assert.deepEqual(errors, [])
  assert.deepEqual(blocked, [])
  const manifest = JSON.parse(await readFile('dist/manifest.json', 'utf8'))
  const result = { ok: true, browser: await context.browser().version(), permissions: manifest.permissions,
    externalNetwork: 'offline; all HTTP page requests fulfilled by exact fixtures or aborted',
    checks: ['MV3 loaded', 'MAIN observer to isolated bridge to trusted background', 'exact offers 2/3', 'server acknowledgements 2', 'manual pause', 'local token deletion', 'wallet null'],
    popupTransport: 'local fixture bridge to worker command; native popup sender checked separately by VM tests',
    transportBoundary: 'deny-only loopback proxy; no upstream forwarding', deniedConnections,
    screenshots: ['popup-running.png', 'popup-paused.png'] }
  await writeFile(join(output, 'browser-check.json'), `${JSON.stringify(result, null, 2)}\n`)
  console.log(JSON.stringify(result))
} finally {
  await context?.close()
  await new Promise((resolve) => denyProxy.close(resolve))
  await rm(profile, { recursive: true, force: true })
}
