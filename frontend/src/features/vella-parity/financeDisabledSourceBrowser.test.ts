import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Page } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { beforeAll, expect, it } from 'vitest'

const unavailableTitle = 'Операционные расходы недоступны'
const unavailableMessage = 'Интеграция с 1С отключена. Данные расходов за выбранный период не получены.'
let bundleCode: string

beforeAll(async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent', plugins: [react()],
    define: { 'process.env.NODE_ENV': '"test"', 'import.meta.env.VITE_API_BASE_URL': '""' },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'FinanceDisabledSourceTest',
    } },
  })
  const chunk = (Array.isArray(result) ? result : [result]).flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing finance disabled source bundle')
  bundleCode = chunk.code
}, 60_000)

async function mount(page: Page, report: 'pnl' | 'expenses', operationalOutcome: 'disabled' | 'blocker' | 'error' = 'disabled') {
  const requests: string[] = [], errors: string[] = [], consoleProblems: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => {
    if (!['error', 'warning'].includes(message.type())) return
    const text = message.text()
    if (text.startsWith('An empty string')) return // Existing legacy shell image warning.
    if (operationalOutcome === 'error' && text.includes('503')) return
    consoleProblems.push(text)
  })
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url())
    if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === `/wb/reports/${report}`) {
      return route.fulfill({ contentType: 'text/html', body: '<title>Synthetic disabled 1C</title><div id="root"></div>' })
    }
    if (request.method() === 'GET' && request.resourceType() === 'image') {
      return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
    }
    if (request.method() === 'GET' && url.origin === 'https://fonts.googleapis.com') return route.fulfill({ contentType: 'text/css', body: '' })
    if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname === '/api/wb/reports/pnl') {
      requests.push(`${request.method()} ${url.pathname}${url.search}`)
      return route.fulfill({ json: { rows: [], kpis: [], cashFlow: { status: 'disabled' }, reportJob: { state: 'completed' } } })
    }
    if (request.method() === 'GET' && url.origin === 'http://satorna.test' && url.pathname.endsWith('/latest-cache')) {
      requests.push(`${request.method()} ${url.pathname}${url.search}`)
      if (url.pathname === '/api/wb/reports/pnl/latest-cache' && url.searchParams.get('source') === 'financial') {
        return route.fulfill({ json: { rows: [], kpis: [], cashFlow: null, reportJob: { state: 'completed' } } })
      }
      if (operationalOutcome === 'error') {
        return route.fulfill({ status: 503, json: { error: { code: 'SYNTHETIC_UNAVAILABLE', message: 'Источник временно недоступен' } } })
      }
      return route.fulfill({ json: {
        meta: { state: 'partial' }, warning: unavailableMessage,
        kpis: [{ id: 'revenue', value: 123400 }, { id: 'net_profit', value: null }, { id: 'operational_expenses', value: null }],
        rows: report === 'pnl' ? [{ articleId: 'SYNTHETIC-WB', revenueKopecks: 123400, netProfitKopecks: null, overheadKopecks: null, marginPct: null }] : [],
        cashFlow: operationalOutcome === 'blocker' ? null : { status: 'disabled' },
        blockerIds: operationalOutcome === 'blocker' ? ['ONE_C_DISABLED'] : [],
        reportJob: { state: 'completed' },
      } })
    }
    requests.push(`${request.method()} ${url.pathname}${url.search}`)
    return route.abort()
  })
  await page.goto(`http://satorna.test/wb/reports/${report}`)
  await page.addScriptTag({ content: bundleCode })
  return { requests, errors, consoleProblems }
}

it.each(['pnl', 'expenses'] as const)('renders disabled 1C as unavailable on %s without waiting or zero amounts', async report => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
    const evidence = await mount(page, report)
    const surface = page.locator(`#tab-${report}`)
    if (report === 'pnl') {
      await surface.getByText('Операционный 1С', { exact: true }).click()
    }
    await surface.getByText(unavailableTitle, { exact: true }).waitFor({ timeout: 15_000 })
    expect(await surface.innerText()).toContain(unavailableMessage)
    expect(await surface.locator('.finance-1c-wait, [role="progressbar"], .stats, [data-report-row]').count()).toBe(0)
    expect(await surface.getByText('0 ₽', { exact: true }).count()).toBe(0)
    expect(evidence.requests.some(request => request.includes('/jobs'))).toBe(false)
    expect(evidence.errors).toEqual([])
    expect(evidence.consoleProblems).toEqual([])
    expect(page.url()).toBe(`http://satorna.test/wb/reports/${report}`)
    expect(await page.title()).toBe('Satorna — Отчёты WB')
    expect(await page.locator('vite-error-overlay, nextjs-portal').count()).toBe(0)
    if (process.env.SATORNA_REPORT_UI_SCREENSHOTS) {
      await page.screenshot({ path: `/tmp/finance-disabled-${report}-desktop.png` })
      await page.setViewportSize({ width: 390, height: 844 })
      await page.screenshot({ path: `/tmp/finance-disabled-${report}-mobile.png` })
    }
  } finally { await browser.close() }
}, 60_000)

it('recognizes the finance-safe ONE_C_DISABLED blocker when cash flow details are hidden', async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' })
    const evidence = await mount(page, 'pnl', 'blocker')
    const surface = page.locator('#tab-pnl')
    await surface.getByText('Операционный 1С', { exact: true }).click()
    await surface.getByText(unavailableTitle, { exact: true }).waitFor({ timeout: 15_000 })
    expect(await surface.locator('.finance-1c-wait').count()).toBe(0)
    expect(evidence.errors).toEqual([])
    expect(evidence.consoleProblems).toEqual([])
  } finally { await browser.close() }
}, 60_000)

it('renders an operational P&L error instead of waiting for 1C', async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1440, height: 1000 } })
    const evidence = await mount(page, 'pnl', 'error')
    const surface = page.locator('#tab-pnl')
    await surface.getByText('Операционный 1С', { exact: true }).click()
    await expect.poll(() => surface.innerText()).toContain('Не удалось загрузить P&L')
    expect(await surface.innerText()).toContain('Источник временно недоступен')
    expect(await surface.locator('.finance-1c-wait, [role="progressbar"]').count()).toBe(0)
    expect(evidence.errors).toEqual([])
    expect(evidence.consoleProblems).toEqual([])
  } finally { await browser.close() }
}, 60_000)
