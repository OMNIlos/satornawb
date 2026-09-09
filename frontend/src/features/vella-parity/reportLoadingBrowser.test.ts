import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

const reports = [
  { report: 'stock', tab: 'stock', empty: 'За выбранный период нет остатков', error: 'Остатки не загрузились' },
  { report: 'week-over-week', tab: 'week', empty: 'За выбранный период нет сравнения', error: 'Сравнение недель не загрузилось' },
]
it.each(reports.flatMap(report => ['empty', 'failure'].map(outcome => ({ ...report, outcome }))))(
  'renders $report loading → $outcome without mock rows', async ({ report, tab, empty, error, outcome }) => {
    const root = fileURLToPath(new URL('../../../', import.meta.url))
    const result = await build({
      configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
      define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
      resolve: { alias: { '@': path.join(root, 'src') } },
      build: { write: false, minify: false,
        lib: { entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'ReportStateTest' } },
    })
    const outputs = Array.isArray(result) ? result : [result]
    const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
      .find(output => output.type === 'chunk' && output.isEntry)
    if (!bundle || bundle.type !== 'chunk') throw new Error('Missing synthetic report state bundle')
    const browser = await chromium.launch({ headless: true })
    let release = () => {}
    const gate = new Promise<void>(resolve => { release = resolve })
    try {
      const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
      const unexpected: string[] = [], errors: string[] = [], queries: string[] = []
      page.on('pageerror', event => errors.push(event.message))
      await page.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url())
        if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === `/wb/reports/${report}`) {
          return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
        }
        if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
        if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
        if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== `/api/wb/reports/${report}/latest-cache`) {
          unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
        }
        queries.push(url.search)
        await gate
        if (outcome === 'failure') return route.fulfill({ status: 503, contentType: 'application/json', body: '{"error":{"code":"SYNTHETIC_UNAVAILABLE","message":"Источник временно недоступен"}}' })
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
          filters: { dateRange: { from: url.searchParams.get('from'), to: url.searchParams.get('to') } },
          rows: [], kpis: [], formulaNotes: [], sourceEvidence: [], reportJob: null,
        }) })
      })
      await page.goto(`http://satorna.test/wb/reports/${report}`)
      await page.addScriptTag({ content: bundle.code })
      // Wait for the real React effect, not a one-second machine-speed assumption.
      await expect.poll(() => queries.length, { timeout: 15_000 }).toBe(1)
      const surface = page.locator(`#tab-${tab}`)
      await surface.locator('.report-progress-panel[role="status"]').waitFor({ state: 'visible' })
      expect(await surface.innerText()).toContain('Собираем показатели за выбранный период')
      expect(await surface.locator('[data-report-row]').count()).toBe(0)
      if (outcome === 'empty') await page.screenshot({ path: `/tmp/satorna-t4-${tab}-loading.png` })
      release()
      await surface.getByText(outcome === 'empty' ? empty : error, { exact: true }).waitFor({ state: 'visible' })
      expect(await surface.locator('.report-progress-panel').count()).toBe(0)
      expect(await surface.locator('[data-report-row]').count()).toBe(0)
      if (outcome === 'failure') expect(await surface.innerText()).toContain('Источник временно недоступен')
      if (outcome === 'empty') await page.screenshot({ path: `/tmp/satorna-t4-${tab}-empty.png` })
      await page.getByRole('button', { name: 'Clear synthetic report session', exact: true }).click()
      await surface.getByText(error, { exact: true }).waitFor({ state: 'visible' })
      // Failure already displayed this heading before logout. Observe the actual
      // session transition rather than racing the still-visible source error.
      await expect.poll(() => surface.innerText()).toContain('Сессия истекла')
      expect(queries).toHaveLength(1)
      const query = new URLSearchParams(queries[0])
      expect([query.get('groupBy'), query.get('source'), query.get('preset')]).toEqual(['sku', 'operational', 'custom'])
      expect(await page.title()).toBe('Satorna — Отчёты WB')
      expect(unexpected, `Unexpected fixture requests: ${JSON.stringify(unexpected)}`).toEqual([])
      expect(errors).toEqual([])
    } finally { release(); await browser.close() }
  }, 60_000,
)
