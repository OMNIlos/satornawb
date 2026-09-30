import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { describe, expect, it } from 'vitest'

function ordersResponse(search = '', refreshing = false) {
  return {
    status: refreshing ? 'blocked' : 'synced', filters: { mode: 'active', accountId: null, page: 1, limit: 50, search, historyFrom: null },
    summary: { total: search || refreshing ? 0 : 1, shown: search || refreshing ? 0 : 1, confirmation: 0, readyToShip: 1, inTransit: 0, delivered: 0,
      closed: 0, canceled: 0, returns: 0, disputes: 0, requiredActions: 0, items: 2,
      totalKopecks: 10000, statusCounts: { ready_to_ship: 1 } },
    rows: search || refreshing ? [] : [{
      orderId: 'TEST-ORDER-1', jobNumber: 'TEST-JOB-1', shipmentNumber: 'TEST-SHIP-1', stickerNumber: 'TEST-STICKER-1', accountId: 'test-account', accountName: 'Test account',
      status: 'ready_to_ship', deliveryType: null, deliveryService: null, createdAt: null, updatedAt: null,
      buyerName: null, buyerId: null, buyerPhone: null, recipientName: null, recipientPhone: null, address: null,
      trackNumber: 'TEST-TRACK-1', returnStatus: null, totalKopecks: 10000, availableActions: [], schedules: [], sourceStatus: 'ready_to_ship',
      items: [{ itemId: 'TEST-ITEM-1', title: 'Test shirt', quantity: 2, priceKopecks: 5000, barcode: 'TEST-BARCODE-1',
        sellerArticle: 'TEST-SKU-1', size: 'M', color: 'white', imageUrl: null, returnMatches: [], reuseSuggestion: null }],
    }],
    source: { complete: !refreshing, error: refreshing ? { code: 'refresh_in_progress' } : null },
  }
}

describe('Avito picking without the empty marking slot', () => {
  it('aligns loaded row and search-empty colspan while preserving order and sticker identifiers', async () => {
    const root = fileURLToPath(new URL('../../../', import.meta.url))
    const result = await build({
      configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
      define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
      resolve: { alias: { '@': path.join(root, 'src') } },
      build: { write: false, minify: false,
        lib: { entry: fileURLToPath(new URL('./__fixtures__/avitoPickingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'AvitoPickingTest' } },
    })
    const outputs = Array.isArray(result) ? result : [result]
    const bundle = outputs.flatMap((output) => 'output' in output ? output.output : [])
      .find((output) => output.type === 'chunk' && output.isEntry)
    if (!bundle || bundle.type !== 'chunk') throw new Error('Missing local test bundle')
    const browser = await chromium.launch({ headless: true })
    try {
      const page = await browser.newPage({ serviceWorkers: 'block' })
      const unexpected: string[] = []
      const errors: string[] = []
      let queueRequests = 0
      page.on('pageerror', (error) => errors.push(error.message))
      await page.route('**/*', async (route) => {
        const request = route.request()
        const url = new URL(request.url())
        if (request.method() !== 'GET' || url.origin !== 'http://satorna.test') {
          unexpected.push(`${request.method()} ${url.pathname}`)
          return route.abort()
        }
        if (url.pathname === '/avito/orders') return route.fulfill({ contentType: 'text/html', body: '<body class="vella-html-parity-root"><div id="root"></div></body>' })
        if (url.pathname === '/favicon.ico') return route.fulfill({ status: 204 })
        let data: unknown
        if (url.pathname === '/api/v1/avito/orders/queue') data = ordersResponse(url.searchParams.get('search') ?? '', ++queueRequests === 1)
        else if (url.pathname === '/api/v1/avito/orders/extension-token') data = { configured: false }
        else if (url.pathname === '/api/v1/avito/orders/returns-sync') data = { enabled: false, intervalMinutes: 30, periodDays: 30, status: { state: 'ready' }, inventory: { status: 'ready', candidates: 54 } }
        else { unexpected.push(`${request.method()} ${url.pathname}`); return route.abort() }
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
      })
      await page.goto('http://satorna.test/avito/orders')
      await page.addScriptTag({ content: bundle.code })
      const table = page.locator('table.orders-picking-table')
      await table.waitFor({ state: 'visible', timeout: 10_000 })
      await table.getByText('TEST-SKU-1', { exact: true }).waitFor({ timeout: 10_000 })
      expect(queueRequests).toBe(2)
      expect(await table.innerText()).toContain('TEST-SKU-1')
      expect(await table.innerText()).not.toContain('КИЗ')
      expect(await table.locator('thead th').count()).toBe(16)
      const cells = table.locator('tbody tr').first().locator('td')
      expect(await cells.count()).toBe(16)
      expect(await cells.nth(2).innerText()).toContain('TEST-JOB-1')
      expect(await cells.nth(3).innerText()).toContain('TEST-SHIP-1')
      expect(await cells.nth(7).innerText()).toBe('2')
      expect(await cells.nth(12).innerText()).toContain('TEST-STICKER-1')
      expect(await cells.nth(13).innerText()).toBe('TEST-BARCODE-1')
      expect(await cells.nth(14).innerText()).toBe('TEST-ITEM-1')
      expect(await page.getByText('54 поз. · синхронизация: готово').isVisible()).toBe(true)
      await page.getByPlaceholder('Поиск по номеру, заданию, артикулу, названию', { exact: true }).fill('not-present-in-fixture')
      const empty = table.locator('tbody tr.avito-orders-empty-row td')
      await empty.waitFor({ state: 'visible' })
      expect(await empty.getAttribute('colspan')).toBe('16')
      expect(await empty.innerText()).toContain('Ничего не нашлось')
      expect(unexpected).toEqual([])
      expect(errors).toEqual([])
    } finally { await browser.close() }
  }, 60_000)
})
