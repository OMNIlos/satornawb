import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

it('applies Avito statistics draft dates only on Apply on the actual React page', async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const mutation = process.env.SATORNA_AVITO_STATS_TEST_MUTATION
  if (mutation && mutation !== 'apply') throw new Error('Unknown Avito statistics test mutation')
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [
      { name: 'synthetic-avito-stats-mutation', enforce: 'pre', transform(code, id) {
        if (!mutation || !id.endsWith('/VellaHtmlParityPage.tsx')) return
        const target = 'window.applyAvitoStatsPeriod = () => {'
        if (code.split(target).length !== 2) throw new Error('Avito statistics mutation target is not unique')
        // In-memory test bundle only: disabling Apply must fail the behavior test.
        return code.replace(target, `${target}\n    return;`)
      } },
      react(),
    ],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)),
      formats: ['iife'], name: 'AvitoStatsPeriodTest',
    } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!bundle || bundle.type !== 'chunk') throw new Error('Missing synthetic Avito statistics bundle')
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
    const queries: string[] = [], unexpected: string[] = [], errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url())
      if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/avito/stats') return route.fulfill({ contentType: 'text/html', body: '<div id="root"></div>' })
      if (request.method() === 'GET' && request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
      if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com' && url.pathname === '/css2') return route.fulfill({ contentType: 'text/css', body: '' })
      if (request.method() !== 'GET' || url.origin !== 'http://satorna.test' || url.pathname !== '/api/v1/avito/stats') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      queries.push(url.search)
      const dateFrom = url.searchParams.get('dateFrom'), dateTo = url.searchParams.get('dateTo')
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        status: 'synced', period: { dateFrom, dateTo, days: 7 },
        summary: { impressions: null, views: null, contactsMessenger: null, contacts: null,
          contactsShowPhone: null, contactsShowPhoneAndMessenger: null, favorites: null,
          spendKopecks: null, orders: null, buyouts: null, conversionPct: null,
          orderConversionPct: null, buyoutPct: null, problemRows: 0 },
        timeline: [], accounts: [], rows: [], source: {},
      }) })
    })
    await page.goto('http://satorna.test/avito/stats')
    await page.addScriptTag({ content: bundle.code })
    const surface = page.locator('#tab-avito-stats')
    await surface.getByText('За выбранный период данных нет', { exact: true }).waitFor({ state: 'visible', timeout: 15_000 })
    expect(queries).toHaveLength(1)
    const initial = new URLSearchParams(queries[0])
    expect(initial.get('forceRefresh')).toBeNull()
    const from = surface.getByLabel('Дата начала статистики Авито', { exact: true })
    const to = surface.getByLabel('Дата окончания статистики Авито', { exact: true })
    expect(await from.inputValue()).toBe(initial.get('dateFrom'))
    expect(await to.inputValue()).toBe(initial.get('dateTo'))
    await from.fill('2026-08-01')
    await to.fill('2026-08-07')
    expect(await from.inputValue()).toBe('2026-08-01')
    expect(await to.inputValue()).toBe('2026-08-07')
    // Draft controls must leave both the displayed applied period and network unchanged.
    expect(await surface.locator('.avito-stats-empty-state').innerText()).toContain(`${initial.get('dateFrom')} — ${initial.get('dateTo')}`)
    expect(queries).toHaveLength(1)
    await surface.getByRole('button', { name: 'Применить', exact: true }).click()
    await expect.poll(() => queries.length, { timeout: 15_000 }).toBe(2)
    await surface.getByText('2026-08-01 — 2026-08-07', { exact: true }).waitFor({ state: 'visible' })
    await surface.getByText('За выбранный период данных нет', { exact: true }).waitFor({ state: 'visible' })
    expect([...new URLSearchParams(queries[1]).entries()]).toEqual([['dateFrom', '2026-08-01'], ['dateTo', '2026-08-07']])
    await page.getByRole('button', { name: 'Clear synthetic report session', exact: true }).click()
    await surface.getByText('Статистика временно недоступна', { exact: true }).waitFor({ state: 'visible' })
    expect(await surface.locator('#avitoStatsKpiViews').innerText()).toBe('—')
    expect(queries).toHaveLength(2)
    expect(unexpected, JSON.stringify(unexpected)).toEqual([])
    expect(errors).toEqual([])
  } finally { await browser.close() }
}, 60_000)
