import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

it('searches actual Ads campaign rows by supplied SKU and campaign without additional loads', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'AdsSkuTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const chunk = outputs.flatMap(output => 'output' in output ? output.output : []).find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing Ads browser fixture bundle')
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    await page.clock.setFixedTime(new Date('2026-09-09T12:00:00Z'))
    const requests: string[] = [], unexpected: string[] = [], errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/wb/reports/ads') return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
      if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== '/api/wb/reports/ads/latest-cache') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      requests.push(url.search)
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        meta: { title: 'Synthetic Ads', freshnessState: 'fresh', lastUpdatedAt: '2026-09-09T12:00:00Z' },
        rows: [
          { campaignId: 910001, campaignName: 'Synthetic campaign-alpha', sku: 'FBBT_42', productName: 'Synthetic Alpha', managerId: null },
          { campaignId: 910002, campaignName: 'Synthetic campaign-beta', sku: 'FBBT_42', productName: 'Synthetic Alpha', managerId: null },
          { campaignId: 910003, campaignName: 'Synthetic campaign-gamma', sku: 'LBBT_33', productName: 'Synthetic Gamma', managerId: null },
        ], kpis: [], chart: null,
      }) })
    })
    await page.goto('http://satorna.test/wb/reports/ads')
    await page.evaluate(() => {
      window.__vellaReportPeriods = { ads: { days: 7, mode: 'custom', fromIso: '2026-08-01', toIso: '2026-08-07', label: 'Synthetic Ads period' } }
    })
    await page.addScriptTag({ content: chunk.code })
    const surface = page.locator('#tab-ads')
    await surface.getByText('Synthetic campaign-alpha', { exact: true }).waitFor({ timeout: 15_000 })
    const visible = surface.locator('tr[data-report-row="ads"]:visible')
    expect(await visible.count()).toBe(3)
    // Current React toolbar uses search, not the standalone prototype's select.
    const search = surface.getByPlaceholder('nmID, SKU или рекламная кампания...')
    await search.fill('FBBT_42')
    expect(await visible.count()).toBe(2)
    expect(await visible.allTextContents()).toEqual(expect.arrayContaining([
      expect.stringContaining('Synthetic campaign-alpha'), expect.stringContaining('Synthetic campaign-beta'),
    ]))
    await search.fill('campaign-beta')
    expect(await visible.count()).toBe(1)
    expect(await visible.innerText()).toContain('Synthetic campaign-beta')
    await search.fill('absent-synthetic-campaign')
    expect(await visible.count()).toBe(0)
    await search.fill('')
    expect(await visible.count()).toBe(3)
    expect(requests).toHaveLength(1)
    const query = new URLSearchParams(requests[0])
    expect([query.get('from'), query.get('to'), query.get('groupBy'), query.get('source'), query.get('preset')])
      .toEqual(['2026-08-01', '2026-08-07', 'campaign', 'operational', 'custom'])
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  } finally { await browser.close() }
}, 60_000)
