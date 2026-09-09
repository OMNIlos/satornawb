import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { expect, it } from 'vitest'

it.each(['success', 'error', 'logout', 'pagination', 'pagination-error'] as const)('ignores stale repricer statistics: %s', async scenario => {
  const paginated = scenario.startsWith('pagination')
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': JSON.stringify('test'), 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('') },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false,
      lib: { entry: fileURLToPath(new URL('./__fixtures__/repricerStatsRaceBrowser.ts', import.meta.url)), formats: ['iife'], name: 'StatsRaceTest' } },
  })
  const outputs = Array.isArray(result) ? result : [result]
  const bundle = outputs.flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!bundle || bundle.type !== 'chunk') throw new Error('Missing synthetic stats bundle')
  const browser = await chromium.launch({ headless: true })
  let releaseFirst = () => {}
  const firstGate = new Promise<void>(resolve => { releaseFirst = resolve })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1280, height: 720 } })
    const unexpected: string[] = [], errors: string[] = [], requests: [string, number][] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url())
      if (url.origin !== 'http://satorna.test' || request.method() !== 'GET') {
        unexpected.push(`${request.method()} ${url.pathname}`); return route.abort()
      }
      if (url.pathname === '/wb/repricer/stats') return route.fulfill({ contentType: 'text/html', body:
        '<title>Synthetic repricer statistics</title><button id="reload">Reload filtered statistics</button><button id="logout">Clear test session</button><section id="tab-repricer-stats"><div class="search"><input></div><table><tbody id="repricerStatsBody"></tbody></table><div data-filter-summary><span></span></div></section>' })
      if (url.pathname === '/favicon.ico') return route.fulfill({ status: 204 })
      if (url.pathname !== '/api/v1/wb-repricer/stats') { unexpected.push(url.pathname); return route.abort() }
      const query = url.searchParams.get('q') ?? ''
      const pageNumber = Number(url.searchParams.get('page'))
      requests.push([query, pageNumber])
      if (!query && (!paginated || pageNumber === 2)) await firstGate
      if (!query && (scenario === 'error' || scenario === 'pagination-error' && pageNumber === 2)) return route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":{"code":"SYNTHETIC_ERROR"}}' })
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify({
        items: [{ articleId: query ? 'NEWER-SKU' : 'OLDER-SKU', nmId: 101, name: 'Synthetic product',
          brand: 'Synthetic', managerName: '', metrics: {}, decision: {}, sources: {}, priceProtection: {}, flags: [] }],
        total: !query && paginated ? 501 : 1, itemsReturned: 1, page: pageNumber, pageSize: 500,
      }) })
    })
    await page.goto('http://satorna.test/wb/repricer/stats')
    await page.addScriptTag({ content: bundle.code })
    await expect.poll(() => requests.length).toBe(paginated ? 2 : 1)
    await page.getByRole('button', { name: 'Reload filtered statistics', exact: true }).click()
    await page.getByText('NEWER-SKU', { exact: true }).waitFor({ state: 'visible' })
    if (scenario === 'logout') await page.getByRole('button', { name: 'Clear test session', exact: true }).click()
    releaseFirst()
    await page.waitForFunction(() => document.body.dataset.firstSettled === 'true')
    expect(await page.getByText('NEWER-SKU', { exact: true }).count()).toBe(scenario === 'logout' ? 0 : 1)
    expect(await page.getByText('OLDER-SKU', { exact: true }).count()).toBe(0)
    expect(await page.title()).toBe('Synthetic repricer statistics')
    if (scenario === 'success') await page.screenshot({ path: '/tmp/satorna-t4-repricer-stats-race.png' })
    await page.getByRole('button', { name: 'Clear test session', exact: true }).click()
    expect(await page.getByText('NEWER-SKU', { exact: true }).count()).toBe(0)
    expect(await page.locator('#repricerStatsBody').innerText()).toContain('Статистика репрайсера недоступна')
    expect(requests).toEqual(paginated ? [['', 1], ['', 2], ['second', 1]] : [['', 1], ['second', 1]])
    expect(unexpected).toEqual([])
    expect(errors).toEqual([])
  } finally { releaseFirst(); await browser.close() }
}, 60_000)
