import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { describe, expect, it } from 'vitest'

function ordersResponse(dateFrom: string) {
  return {
    status: 'synced', period: { dateFrom, days: 30 }, filters: { statuses: [], page: 1, limit: 20 },
    summary: { total: 1, shown: 1, confirmation: 0, readyToShip: 1, inTransit: 0, delivered: 0,
      closed: 0, canceled: 0, returns: 0, disputes: 0, requiredActions: 0, items: 2,
      totalKopecks: 10000, statusCounts: { ready_to_ship: 1 } },
    rows: [{
      orderId: 'TEST-ORDER-1', marketplaceId: 'TEST-MARKET-1', accountId: 'test-account', accountName: 'Test account',
      status: 'ready_to_ship', deliveryType: null, deliveryService: null, createdAt: null, updatedAt: null,
      buyerName: null, buyerId: null, buyerPhone: null, recipientName: null, recipientPhone: null, address: null,
      trackNumber: 'TEST-TRACK-1', returnStatus: null, totalKopecks: 10000, availableActions: [], schedules: [], sourceStatus: 'ready_to_ship',
      items: [{ itemId: 'TEST-ITEM-1', title: 'Test shirt', quantity: 2, priceKopecks: 5000,
        sellerArticle: 'TEST-SKU-1', size: 'M', color: 'white', imageUrl: null, returnMatches: [], reuseSuggestion: null }],
    }],
    source: { browserSnapshot: { capturedAt: '2026-09-09T00:00:00Z', orders: 1, items: 2 } },
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
        if (url.pathname === '/api/v1/avito/orders') data = ordersResponse(url.searchParams.get('dateFrom') ?? '')
        else if (url.pathname === '/api/v1/avito/orders/extension-token') data = { configured: false }
        else if (url.pathname === '/api/v1/avito/orders/returns-sync') data = { enabled: false, intervalMinutes: 30, periodDays: 30, status: { state: 'idle' }, inventory: { status: 'empty', candidates: 0 } }
        else { unexpected.push(`${request.method()} ${url.pathname}`); return route.abort() }
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) })
      })
      await page.goto('http://satorna.test/avito/orders')
      await page.addScriptTag({ content: bundle.code })
      const table = page.locator('table.orders-picking-table')
      await table.waitFor({ state: 'visible', timeout: 10_000 })
      expect(await table.innerText()).toContain('TEST-SKU-1')
      expect(await table.innerText()).not.toContain('КИЗ')
      expect(await table.locator('thead th').count()).toBe(15)
      const cells = table.locator('tbody tr').first().locator('td')
      expect(await cells.count()).toBe(15)
      expect(await cells.nth(2).innerText()).toContain('TEST-MARKET-1')
      expect(await cells.nth(6).innerText()).toBe('2')
      expect(await cells.nth(11).innerText()).toContain('Стикеры')
      expect(await cells.nth(12).innerText()).toBe('TEST-TRACK-1')
      expect(await cells.nth(13).innerText()).toBe('TEST-ITEM-1')
      await page.getByPlaceholder('Поиск по номеру, заданию, артикулу, названию', { exact: true }).fill('not-present-in-fixture')
      const empty = table.locator('tbody tr.avito-orders-empty-row td')
      await empty.waitFor({ state: 'visible' })
      expect(await empty.getAttribute('colspan')).toBe('15')
      expect(await empty.innerText()).toContain('Ничего не нашлось')
      expect(unexpected).toEqual([])
      expect(errors).toEqual([])
    } finally { await browser.close() }
  }, 60_000)
})
