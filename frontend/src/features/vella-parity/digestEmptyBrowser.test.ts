import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { beforeAll, expect, it } from 'vitest'
import type { DigestResponse } from '../wb-reports/types'

let code: string
beforeAll(async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'DigestEmptyTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const chunk = outputs.flatMap(output => 'output' in output ? output.output : []).find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing Digest browser fixture bundle')
  code = chunk.code
}, 60_000)

it.each(['empty', 'one-point'])('renders Digest balance %s visibly from a valid cached report', async scenario => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    await page.clock.setFixedTime(new Date('2026-09-09T12:00:00Z'))
    const requests: string[] = [], planMonths: string[] = [], unexpected: string[] = [], errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/wb/reports/digest') return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/api/wb/reports/digest/plan') {
        planMonths.push(url.searchParams.get('month') ?? '')
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ company: { revenuePlanKopecks: 0, marginPlanKopecks: 0 }, managers: [] }) })
      }
      if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== '/api/wb/reports/digest/latest-cache') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      requests.push(url.search)
      const from = url.searchParams.get('from') ?? '', to = url.searchParams.get('to') ?? ''
      const report: DigestResponse = {
        meta: { id: 'digest', title: 'Synthetic Digest', description: 'Local browser fixture', sourceType: 'operational', freshnessState: 'fresh', lastUpdatedAt: '2026-09-09T12:00:00Z' },
        headline: 'Synthetic cached Digest', dateRange: { preset: 'custom', from, to },
        kpis: [], planFactRows: [], freshness: [], alerts: [], charts: [], problemRows: [], quickLinks: [], periodCards: [],
        weeklyBalance: { title: 'Synthetic daily balance', valueLabel: 'Заказы', compareLabel: 'Выкупили',
          points: scenario === 'empty' ? [] : [{ label: 'Synthetic day', date: from, value: 12, compareValue: 9, returnsUnits: 2, buyoutPct: 75 }] },
      }
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(report) })
    })
    await page.goto('http://satorna.test/wb/reports/digest')
    await page.addScriptTag({ content: code })
    const panel = page.locator('#tab-digest [data-vella-island="digest-balance-panel"]')
    await panel.waitFor({ state: 'visible', timeout: 15_000 })
    await expect.poll(() => page.evaluate(() => Boolean(window.__vellaDigestLiveReport) && !window.__vellaDigestLiveLoading), { timeout: 15_000 }).toBe(true)
    // Initial route loading legitimately prefetches four preset scopes; do not assert a single GET.
    const expectedFrom = ['2026-08-10', '2026-08-26', '2026-09-02', '2026-09-08']
    await expect.poll(() => [...new Set(requests.map(search => new URLSearchParams(search).get('from')))].sort(), { timeout: 15_000 }).toEqual(expectedFrom)
    for (const search of requests) {
      const query = new URLSearchParams(search)
      expect([query.get('groupBy'), query.get('source'), query.get('preset'), query.get('to')]).toEqual(['sku', 'operational', 'custom', '2026-09-08'])
      expect(expectedFrom).toContain(query.get('from'))
    }
    for (const month of planMonths) expect(month).toBe('2026-09')
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
    const empty = panel.locator('#digestBalanceEmpty')
    if (scenario === 'empty') {
      expect(await panel.locator('.chart-hit-zone').count()).toBe(0)
      expect(await empty.textContent()).toBe('За выбранный период нет продаж, заказов и возвратов.')
      // Regression contract: actual CSS visibility, not merely hidden text in the DOM.
      expect(await empty.isVisible()).toBe(true)
    } else {
      expect(await empty.isVisible()).toBe(false)
      expect(await panel.locator('.chart-hit-zone').count()).toBe(1)
      const heights = await panel.locator('.balance-chart-bar').evaluateAll(bars => bars.map(bar => Number(bar.getAttribute('height'))))
      expect(heights).toHaveLength(2)
      expect(heights.every(height => height > 0)).toBe(true)
      await panel.locator('.chart-hit-zone').hover()
      const tip = page.locator('#g-tip.show')
      await tip.waitFor({ state: 'visible' })
      expect(await tip.innerText()).toContain('Выкупили')
      expect(await tip.innerText()).toContain('Заказы')
      expect(await tip.innerText()).toContain('Возвраты')
    }
  } finally { await browser.close() }
}, 45_000)
