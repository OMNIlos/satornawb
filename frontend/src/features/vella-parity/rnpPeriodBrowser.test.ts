import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

it('hides the old RNP period while the next scoped cache response is pending', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false,
      lib: { entry: fileURLToPath(new URL('./__fixtures__/rnpPeriodBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'RnpPeriodTest' } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!bundle || bundle.type !== 'chunk') throw new Error('Missing synthetic RNP bundle')
  const browser = await chromium.launch({ headless: true })
  let releaseSecond = () => {}
  const secondGate = new Promise<void>(resolve => { releaseSecond = resolve })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' })
    const unexpected: string[] = []
    const errors: string[] = []
    const periods: string[][] = []
    const queryScopes: Array<Array<string | null>> = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', async route => {
      const request = route.request()
      const url = new URL(request.url())
      if (url.origin !== 'http://satorna.test' || request.method() !== 'GET') {
        unexpected.push(`${request.method()} ${url.pathname}`)
        return route.abort()
      }
      if (url.pathname === '/wb/reports/rnp') return route.fulfill({ contentType: 'text/html', body: '<div class="vella-html-parity-root" id="root"></div>' })
      if (url.pathname === '/favicon.ico') return route.fulfill({ status: 204 })
      if (url.pathname !== '/api/wb/reports/rnp/latest-cache') {
        unexpected.push(`${request.method()} ${url.pathname}`)
        return route.abort()
      }
      const from = url.searchParams.get('from') ?? ''
      const to = url.searchParams.get('to') ?? ''
      periods.push([from, to])
      queryScopes.push(['groupBy', 'source', 'preset'].map(key => url.searchParams.get(key)))
      const second = from === '2026-08-08'
      if (second) await secondGate
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        filters: { dateRange: { from, to } },
        rows: [{ sku: second ? 'SECOND-PERIOD-SKU' : 'FIRST-PERIOD-SKU', productName: 'Synthetic product', nmId: 101,
          photoUrl: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7' }],
        kpis: [], formulaNotes: [], sourceEvidence: [], reportJob: null,
      }) })
    })
    await page.goto('http://satorna.test/wb/reports/rnp')
    await page.addScriptTag({ content: bundle.code })
    const first = page.getByText('Артикул: FIRST-PERIOD-SKU', { exact: true }).first()
    await first.waitFor({ state: 'visible', timeout: 10_000 })
    await page.evaluate(() => {
      window.__vellaReportPeriods = {
        rnp: { days: 7, fromIso: '2026-08-08', toIso: '2026-08-14', label: 'Synthetic second', mode: 'custom' },
      }
      window.dispatchEvent(new CustomEvent('vella:report-period-updated', { detail: { reportKey: 'rnp' } }))
    })
    await expect.poll(() => periods.length, { timeout: 3000 }).toBe(2)
    await first.waitFor({ state: 'hidden', timeout: 3000 })
    expect(await page.getByText('Загружаем РНП', { exact: true }).count()).toBeGreaterThan(0)
    releaseSecond()
    await page.getByText('Артикул: SECOND-PERIOD-SKU', { exact: true }).first().waitFor({ state: 'visible', timeout: 5000 })
    expect(await first.count()).toBe(0)
    expect(periods).toEqual([['2026-08-01', '2026-08-07'], ['2026-08-08', '2026-08-14']])
    expect(queryScopes).toEqual([['sku', 'operational', 'custom'], ['sku', 'operational', 'custom']])
    await page.getByRole('button', { name: 'Clear test session', exact: true }).click()
    await page.getByText('Сессия истекла. Войдите снова, чтобы открыть РНП.', { exact: true }).waitFor({ state: 'visible', timeout: 3000 })
    expect(await page.getByText('Артикул: SECOND-PERIOD-SKU', { exact: true }).count()).toBe(0)
    expect(periods).toHaveLength(2)
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  } finally { releaseSecond(); await browser.close() }
}, 60_000)
