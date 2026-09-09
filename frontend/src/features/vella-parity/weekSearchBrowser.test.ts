import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

// Existing WeekBackendRow fields; statuses come from the response, not a derived business rule.
type WeekSearchRow = { sku: string; productName: string; productStatus: string | null; photoUrl: null; nmId: null }
const rows: WeekSearchRow[] = [
  { sku: 'SYNTHETIC-WEEK-A', productName: 'Synthetic Alpha garment', productStatus: 'новинка', photoUrl: null, nmId: null },
  { sku: 'SYNTHETIC-WEEK-B', productName: 'Synthetic Beta garment', productStatus: 'средний', photoUrl: null, nmId: null },
  { sku: 'SYNTHETIC-WEEK-C', productName: 'Synthetic Gamma garment', productStatus: null, photoUrl: null, nmId: null },
]

it('searches Week by SKU, product name and the supplied product segment without inventing unknown segments', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'WeekSearchTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const chunk = outputs.flatMap(output => 'output' in output ? output.output : []).find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing Week search browser fixture bundle')
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    await page.clock.setFixedTime(new Date('2026-09-09T12:00:00Z'))
    const queries: string[] = [], unexpected: string[] = [], errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/wb/reports/week-over-week') return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
      if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== '/api/wb/reports/week-over-week/latest-cache') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      queries.push(url.search)
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        meta: { freshnessState: 'fresh', sourceType: 'operational' },
        filters: { dateRange: { from: url.searchParams.get('from'), to: url.searchParams.get('to') } },
        rows, reportJob: null,
      }) })
    })
    await page.goto('http://satorna.test/wb/reports/week-over-week')
    await page.evaluate(() => {
      window.__vellaReportPeriods = { week: { days: 7, mode: 'custom', fromIso: '2026-08-01', toIso: '2026-08-07', label: 'Synthetic Week period' } }
    })
    await page.addScriptTag({ content: chunk.code })
    const surface = page.locator('#tab-week')
    const dataRows = surface.locator('tr[data-report-row="week"]')
    await surface.getByText('Synthetic Alpha garment', { exact: true }).waitFor({ timeout: 15_000 })
    expect(await dataRows.count()).toBe(3)
    const search = surface.getByPlaceholder('Артикул, товар или сегмент...')
    for (const [query, expectedProduct] of [
      ['SYNTHETIC-WEEK-B', 'Synthetic Beta garment'],
      ['Alpha garment', 'Synthetic Alpha garment'],
      ['новинка', 'Synthetic Alpha garment'],
      ['средний', 'Synthetic Beta garment'],
    ]) {
      await search.fill(query)
      const visible = surface.locator('tr[data-report-row="week"]:visible')
      expect(await visible.count(), `Visible rows for ${query}`).toBe(1)
      expect(await visible.innerText()).toContain(expectedProduct)
    }
    await search.fill('absent-synthetic-segment')
    expect(await surface.locator('tr[data-report-row="week"]:visible').count()).toBe(0)
    await search.fill('')
    expect(await surface.locator('tr[data-report-row="week"]:visible').count()).toBe(3)
    expect(queries).toHaveLength(1)
    const query = new URLSearchParams(queries[0])
    expect([query.get('from'), query.get('to'), query.get('groupBy'), query.get('source'), query.get('preset')])
      .toEqual(['2026-08-01', '2026-08-07', 'sku', 'operational', 'custom'])
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  } finally { await browser.close() }
}, 60_000)
