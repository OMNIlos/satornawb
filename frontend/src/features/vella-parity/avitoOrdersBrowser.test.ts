import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { beforeAll, expect, it } from 'vitest'

let code: string
beforeAll(async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    root, configFile: false, envFile: false, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'AvitoOrdersTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const chunk = outputs.flatMap(output => 'output' in output ? output.output : []).find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing Avito Orders fixture bundle')
  code = chunk.code
}, 60_000)

it.each(['populated', 'empty', 'error'])('renders read-only Avito Orders %s with one request owner', async outcome => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
    await page.clock.setFixedTime(new Date('2026-09-09T12:00:00Z'))
    const queries: string[] = [], auxiliary: string[] = [], unexpected: string[] = [], errors: string[] = []
    let phase = 'initial'
    const queryPhases: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/avito/orders') return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && ['/api/v1/avito/orders/extension-token', '/api/v1/avito/orders/returns-sync'].includes(url.pathname)) {
        auxiliary.push(url.pathname)
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(url.pathname.endsWith('extension-token')
          ? { configured: false } : { enabled: false, intervalMinutes: 60, periodDays: 30 }) })
      }
      if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== '/api/v1/avito/orders') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      queries.push(url.search)
      queryPhases.push(phase)
      if (outcome === 'error') return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":{"code":"SYNTHETIC_ORDERS_UNAVAILABLE","message":"Synthetic Orders unavailable"}}' })
      const populated = outcome === 'populated'
      // Full required AvitoOrdersBackendResponse/AvitoOrderRow/AvitoOrderItem fields from the consumer.
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        status: 'synced', period: { dateFrom: url.searchParams.get('dateFrom'), days: 30 },
        filters: { statuses: [], page: 1, limit: 20 },
        summary: { total: populated ? 1 : 0, shown: populated ? 1 : 0, confirmation: 0, readyToShip: populated ? 1 : 0,
          inTransit: 0, delivered: 0, closed: 0, canceled: 0, returns: 0, disputes: 0, requiredActions: 0,
          items: populated ? 1 : 0, totalKopecks: populated ? 450000 : 0, statusCounts: populated ? { ready_to_ship: 1 } : {} },
        rows: populated ? [{ orderId: 'synthetic-order-1', marketplaceId: 'synthetic-market-1', accountId: 'synthetic-account', accountName: 'Synthetic account',
          status: 'ready_to_ship', deliveryType: null, deliveryService: null, createdAt: '2026-09-09T10:00:00Z', updatedAt: '2026-09-09T12:00:00Z',
          buyerName: null, buyerId: null, buyerPhone: null, recipientName: null, recipientPhone: null, address: null, trackNumber: null,
          returnStatus: null, totalKopecks: 450000, availableActions: [], schedules: [], sourceStatus: 'synced',
          items: [{ itemId: 'synthetic-item-1', title: 'Synthetic read-only order product', quantity: 1, priceKopecks: 450000,
            sellerArticle: 'SYNTHETIC-ORDER-SKU', size: 'M', color: 'Synthetic blue', imageUrl: null, returnMatches: [], reuseSuggestion: null }],
        }] : [],
        source: { browserSnapshot: { capturedAt: '2026-09-09T12:00:00Z', orders: populated ? 1 : 0, items: populated ? 1 : 0, collector: {} } },
      }) })
    })
    await page.goto('http://satorna.test/avito/orders')
    const response = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/avito/orders')
    await page.addScriptTag({ content: code })
    await response
    await expect.poll(() => auxiliary.length, { timeout: 15_000 }).toBe(2)
    expect(queries).toHaveLength(1)
    const query = new URLSearchParams(queries[0])
    expect([query.get('dateFrom'), query.get('periodDays'), query.get('page'), query.get('limit'), query.get('status'), query.get('forceRefresh')])
      .toEqual(['2026-08-11', '30', '1', '20', null, null])
    const surface = page.locator('#tab-orders-print')
    if (outcome === 'populated') {
      await surface.getByText('Synthetic read-only order product', { exact: true }).first().waitFor({ timeout: 15_000 })
      expect(await surface.innerText()).toContain('SYNTHETIC-ORDER-SKU')
      const beforeLogout = [...queries]
      phase = 'logout'
      await page.getByRole('button', { name: 'Clear synthetic report session', exact: true }).click()
      await expect.poll(() => surface.getByText('Synthetic read-only order product', { exact: true }).count()).toBe(0)
      await surface.getByText('Не удалось загрузить заказы', { exact: true }).waitFor()
      expect(await surface.locator('.avito-orders-extension-empty').isVisible()).toBe(false)
      expect({ beforeLogout, queries, queryPhases, auxiliary, unexpected, errors }).toEqual({
        beforeLogout: [queries[0]], queries: [queries[0]], queryPhases: ['initial'],
        auxiliary: ['/api/v1/avito/orders/extension-token', '/api/v1/avito/orders/returns-sync'], unexpected: [], errors: [],
      })
      expect(auxiliary).toHaveLength(2)
    } else if (outcome === 'empty') {
      // Characterize the existing zero-row onboarding policy; do not invent a
      // new empty-snapshot product policy while repairing request/error ownership.
      await surface.locator('.avito-orders-extension-empty').waitFor({ state: 'visible' })
      expect(await surface.getByText('Synthetic read-only order product', { exact: true }).count()).toBe(0)
    } else {
      const expectedTitle = 'Не удалось загрузить заказы'
      await expect.poll(async () => ({
        expectedStateVisible: await surface.getByText(expectedTitle, { exact: true }).isVisible(),
        onboardingVisible: await surface.locator('.avito-orders-extension-empty').isVisible(),
      }), { timeout: 3000 }).toEqual({ expectedStateVisible: true, onboardingVisible: false })
    }
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  } finally { await browser.close() }
}, 45_000)
