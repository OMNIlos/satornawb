import path from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { chromium } from 'playwright'
import { build } from 'vite'
import { expect, it } from 'vitest'

const product = (index: number) => ({
  meta: {
    articleId: `SKU-${index}`,
    nmId: 100_000 + index,
    name: `Товар ${index}`,
    status: 'auto',
    currentPriceKopecks: 200_000,
    basketsLast7d: 1,
    basketNorm: 10,
  },
  settings: { wbCommissionPct: 15, minMarginPct: 20, cogsKopecks: 80_000, logisticsKopecks: 10_000 },
  analytics: { baskets: 1, financeState: 'ok' },
})

it('keeps catalog totals in the table without duplicating unscoped navigation counts', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: {
      'process.env.NODE_ENV': JSON.stringify('test'),
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(''),
      'import.meta.env.VITE_WB_LIVE_ENABLED': JSON.stringify('false'),
    },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/productsCatalogCountBrowser.tsx', import.meta.url)),
      formats: ['iife'], name: 'ProductsCatalogCountTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!bundle || bundle.type !== 'chunk') throw new Error('Missing products count fixture bundle')

  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
    const errors: string[] = [], productQueries: string[] = [], unexpected: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin === 'http://satorna.test' && url.pathname === '/wb/repricer') {
        return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      }
      if (request.resourceType() === 'image') {
        return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      }
      if (url.origin === 'https://fonts.googleapis.com') return route.fulfill({ contentType: 'text/css', body: '' })
      if (url.pathname === '/api/v1/wb-repricer/sku') {
        productQueries.push(url.search)
        const filtered = Boolean(url.searchParams.get('q'))
        const items = filtered ? [product(3410)] : Array.from({ length: 150 }, (_, index) => product(index + 1))
        return route.fulfill({ json: {
          items, total: filtered ? 1 : 3410, totalCached: 3410, itemsReturned: items.length, page: 1, pageSize: 150,
          summary: { skuCount: filtered ? 1 : 3410, totalBaskets: items.length },
          cache: { pagesCached: 4, totalCached: 3410, nextOffset: 4000, pageLimit: 1000, basketsMatchedNmIds: 3410 },
        } })
      }
      if (url.pathname === '/api/v1/wb-repricer/strategies/catalog') return route.fulfill({ json: { items: [], total: 0 } })
      if (url.pathname === '/api/v1/wb-repricer/sku-groups') return route.fulfill({ json: { items: [], total: 0 } })
      if (url.pathname === '/api/v1/wb-repricer/sync/status') return route.fulfill({ json: { state: 'completed', running: false, steps: [] } })
      if (url.pathname === '/api/v1/wb-repricer/worker/status') return route.fulfill({ json: { available: true, tasks: [] } })
      if (url.pathname === '/api/v1/wb-repricer/changelog') return route.fulfill({ json: { items: [], total: 0 } })
      unexpected.push(`${request.method()} ${url.pathname}`)
      return route.abort()
    })

    await page.goto('http://satorna.test/wb/repricer')
    await page.addScriptTag({ content: bundle.code })
    const sidebarCount = page.locator('#sidebar [data-tab="products"] > .nav-badge')
    const subtabCount = page.locator('.subtabs [data-tab="products"] > .subtab-count')
    await expect.poll(() => productQueries.length, { timeout: 15_000 }).toBeGreaterThan(0)
    await page.waitForFunction(() => window.__vellaProductsCacheMeta?.totalCached === 3410)
    expect(await sidebarCount.count()).toBe(0)
    expect(await subtabCount.count()).toBe(0)
    expect(await page.evaluate(() => window.__vellaProductsCacheMeta?.totalCached)).toBe(3410)
    await expect.poll(() => page.locator('[data-vella-island="products-sticky-pagination"] span').first().innerText()).toBe('1-150 из 3410 SKU')
    if (process.env.SATORNA_PRODUCTS_COUNT_SCREENSHOTS) {
      await page.screenshot({ path: '/tmp/satorna-products-count-desktop.png' })
      await page.setViewportSize({ width: 390, height: 844 })
      await page.screenshot({ path: '/tmp/satorna-products-count-mobile.png' })
      await page.setViewportSize({ width: 1440, height: 1000 })
    }

    await page.locator('#searchTable').fill('SKU-3410')
    await expect.poll(() => productQueries.some(query => new URLSearchParams(query).get('q') === 'SKU-3410'), { timeout: 15_000 }).toBe(true)
    await expect.poll(() => page.locator('#totalCount').innerText(), { timeout: 15_000 }).toBe('1')
    expect(await sidebarCount.count()).toBe(0)
    expect(await subtabCount.count()).toBe(0)
    expect(await page.evaluate(() => window.__vellaProductsCacheMeta?.totalCached)).toBe(3410)
    if (process.env.SATORNA_PRODUCTS_COUNT_SCREENSHOTS) {
      await page.screenshot({ path: '/tmp/satorna-products-count-filtered.png' })
    }

    expect(errors).toEqual([])
    expect(unexpected).toEqual([])
  } finally {
    await browser.close()
  }
}, 60_000)
