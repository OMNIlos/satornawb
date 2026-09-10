import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium, type Page } from 'playwright'
import { build } from 'vite'
import react from '@vitejs/plugin-react'
import { beforeAll, expect, it } from 'vitest'
import type { CanonicalAbcPnlPage } from '../wb-finance/canonicalAbcPnl'

// Synthetic contract values only; the page and its row renderers are real.
const item: CanonicalAbcPnlPage['items'][number] = {
  nmId: null, sellerArticle: 'SKU-1', catalogSkuId: null, operationCount: 1,
  revenueKopecks: 10000, salesRevenueKopecks: 10000, returnsRevenueKopecks: 0,
  mainRevenueKopecks: 10000, redemptionsRevenueKopecks: 0, lateCorrectionRevenueKopecks: 0,
  unknownRevenueKopecks: 0, salesUnits: 1, returnsUnits: 0, netUnits: 1,
  commissionKopecks: 0, logisticsKopecks: 0, storageKopecks: 0, acceptanceKopecks: 0,
  penaltyKopecks: 0, deductionKopecks: 0, additionalPaymentKopecks: 0, financeOtherExpensesKopecks: 0,
  compensationKopecks: 0, acquiringKopecks: 0, financeExpensesKopecks: 0,
  costValueState: 'missing', costEvidenceStatus: null, cogsKopecks: null, settlementProfitKopecks: null,
  economicsValueState: 'missing', economicsEvidenceStatus: null, taxKopecks: null, otherExpensesKopecks: null,
  profitBeforeAdsAndLoyaltyKopecks: null, advertisingSpendKopecks: null, profitBeforeLoyaltyKopecks: null,
  cashbackAmountKopecks: null, cashbackDiscountKopecks: null, cashbackCommissionChangeKopecks: null,
  loyaltyNetCostKopecks: null, profitAfterLoyaltyKopecks: null, salesClass: 'A', profitClass: null,
  abcCode: null, netProfitKopecks: null, blockerIds: ['WB_PNL_COST_MISSING'],
}
const payload: CanonicalAbcPnlPage = {
  items: Array.from({ length: 60 }, (_, i) => ({ ...item, nmId: 500000000 + i, sellerArticle: `SKU-${i + 1}` })),
  total: 60, limit: 500, offset: 0,
  summary: {
    operationCount: 60, skuCount: 60, revenueKopecks: 600000, salesRevenueKopecks: 600000,
    returnsRevenueKopecks: 0, salesUnits: 60, returnsUnits: 0, netUnits: 60, commissionKopecks: 0,
    logisticsKopecks: 0, storageKopecks: 0, acceptanceKopecks: 0, penaltyKopecks: 0, deductionKopecks: 0,
    financeOtherExpensesKopecks: 0, compensationKopecks: 0, acquiringKopecks: 0, financeExpensesKopecks: 0,
    cogsKopecks: null, settlementProfitKopecks: null, taxKopecks: null, otherExpensesKopecks: null,
    profitBeforeAdsAndLoyaltyKopecks: null, advertisingSpendKopecks: null, unattributedAdvertisingSpendKopecks: null,
    profitBeforeLoyaltyKopecks: null, cashbackAmountKopecks: null, cashbackDiscountKopecks: null,
    cashbackCommissionChangeKopecks: null, loyaltyNetCostKopecks: null, profitAfterLoyaltyKopecks: null, netProfitKopecks: null,
  },
  meta: {
    state: 'partial', marketplaceAccountId: 31, period: { dateFrom: '2026-09-01', dateTo: '2026-09-07',
      timezone: 'Europe/Moscow', startAt: '2026-08-31T21:00:00Z', endExclusiveAt: '2026-09-07T21:00:00Z', days: 7, temporalState: 'complete' },
    snapshot: null, formulaVersion: 'wb-abc-pnl-fullstats-loyalty-v1', costLedgerRevision: 0, economicsRevision: 0,
    advertisingSource: null, advertisingSnapshotChecksum: null, advertisingEvidenceStatus: null, blockerIds: ['WB_PNL_COST_MISSING'],
  }, timestamp: '2026-09-08T07:00:00Z',
}

let bundleCode: string
beforeAll(async () => {
  const root = fileURLToPath(new URL('../../../', import.meta.url))
  const result = await build({
    configFile: false, envFile: false, root, logLevel: 'silent',
    plugins: [{ name: 'canonical-auth-fixture', enforce: 'pre', transform(source, id) {
      if (!id.endsWith('/__fixtures__/reportLoadingBrowser.tsx')) return
      return source.replace('cabinetMe: null', `cabinetMe: window.location.hash === '#legacy' ? null : ({ organization: { organizationId: 7 }, user: { userId: 1, permissions: [] } } as AuthContextValue['cabinetMe'])`)
    } }, react()],
    define: { 'process.env.NODE_ENV': '"test"', 'import.meta.env.VITE_API_BASE_URL': '""',
      'import.meta.env.VITE_CANONICAL_WB_ABC_PNL_ROLLOUT': '"7:31"' },
    resolve: { alias: { '@': path.join(root, 'src') } },
    build: { write: false, minify: false, lib: {
      entry: fileURLToPath(new URL('./__fixtures__/reportLoadingBrowser.tsx', import.meta.url)), formats: ['iife'], name: 'AbcPnlReliability',
    } },
  })
  const chunk = (Array.isArray(result) ? result : [result]).flatMap(output => 'output' in output ? output.output : [])
    .find(output => output.type === 'chunk' && output.isEntry)
  if (!chunk || chunk.type !== 'chunk') throw new Error('Missing ABC/P&L browser bundle')
  bundleCode = chunk.code
}, 60_000)

async function mount(page: Page, tab: 'abc' | 'pnl', legacy = false) {
  const errors: string[] = [], unexpected: string[] = [], queries: string[] = [], coverageQueries: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  // The unchanged legacy shell emits React's empty image src warning.
  page.on('console', message => { if (message.type() === 'error' && !message.text().startsWith('An empty string')) errors.push(message.text()) })
  await page.clock.setFixedTime(new Date('2026-09-11T12:00:00Z'))
  await page.route('**/*', route => {
    const request = route.request(), url = new URL(request.url())
    if (request.method() === 'GET' && url.origin === 'http://satorna.test') {
      if (url.pathname === `/wb/reports/${tab}`) return route.fulfill({ contentType: 'text/html', body: '<title>Synthetic report reliability</title><div id="root"></div>' })
      if (url.pathname === '/api/v1/cabinet/team/users') return route.fulfill({ json: { data: [] } })
      if (url.pathname === '/api/v1/cabinet/wb-token') return route.fulfill({ json: { data: { userId: '1', hasToken: false, tokenMasked: null, updatedAt: null } } })
      if (url.pathname === '/api/v1/cabinet/avito-credentials') return route.fulfill({ json: { data: { userId: '1', hasCredentials: false, clientIdMasked: null, clientSecretMasked: null, accessTokenExpiresAt: null, updatedAt: null } } })
      if (!legacy && url.pathname === '/api/v2/wb/reports/abc-pnl') {
        queries.push(url.search)
        const dateFrom = url.searchParams.get('dateFrom') ?? '2026-09-01', dateTo = url.searchParams.get('dateTo') ?? '2026-09-07'
        const start = new Date(`${dateFrom}T00:00:00+03:00`), end = new Date(`${dateTo}T00:00:00+03:00`)
        const days = (end.getTime() - start.getTime()) / 86400000 + 1
        return route.fulfill({ json: { ...payload, meta: { ...payload.meta, period: { ...payload.meta.period,
          dateFrom, dateTo, days, startAt: start.toISOString(), endExclusiveAt: new Date(end.getTime() + 86400000).toISOString(),
        } } } })
      }
      if (legacy && url.pathname === '/api/wb/reports/pnl/latest-cache') return route.fulfill({ json: {
        meta: { dateRange: { from: '2026-09-01', to: '2026-09-07' }, sourceType: 'financial' },
        rows: ['blocked', 'partial', 'ready'].map(sourceStatus => ({ articleId: `STATUS-${sourceStatus}`, productName: sourceStatus, sourceStatus, confidence: sourceStatus === 'ready' ? 'high' : 'blocked' })),
      } })
      if (!legacy && url.pathname === '/api/wb/reports/pnl/latest-cache' && url.searchParams.get('source') === 'operational') return route.fulfill({ json: {
        meta: { dateRange: { from: '2026-09-01', to: '2026-09-07' }, sourceType: 'operational' },
        rows: [], cashFlow: null, reportJob: null,
      } })
      if (url.pathname === '/api/v1/wb-repricer/cache/coverage') {
        coverageQueries.push(url.search)
        return route.fulfill({ json: { dateFrom: '2026-06-14', dateTo: '2026-09-11', sources: [], days: [], summary: { totalDays: 90, completeDays: 0, partialDays: 0, missingDays: 90 } } })
      }
    }
    if (request.resourceType() === 'image') return route.fulfill({ contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7', 'base64') })
    if (url.origin === 'https://fonts.googleapis.com') return route.fulfill({ contentType: 'text/css', body: '' })
    unexpected.push(`${request.method()} ${url.pathname}`)
    return route.abort()
  })
  await page.goto(`http://satorna.test/wb/reports/${tab}${legacy ? '#legacy' : ''}`)
  await page.evaluate(tab => { window.__vellaReportPeriods = { [tab]: { days: 7, mode: 'custom', fromIso: '2026-09-01', toIso: '2026-09-07', label: 'Synthetic period' } } }, tab)
  await page.addScriptTag({ content: bundleCode })
  await page.locator(`#tab-${tab} [data-report-row]`).first().waitFor({ timeout: 15_000 }).catch(async error => {
    throw new Error(`${error.message}\n${JSON.stringify({ errors, unexpected, queries, text: await page.locator('body').innerText() })}`)
  })
  expect(page.url()).toContain(`/wb/reports/${tab}`)
  expect(await page.title()).toBeTruthy()
  return { errors, unexpected, queries, coverageQueries }
}

it.each(['abc', 'pnl'] as const)('searches all loaded %s rows before pagination and preserves filters', async tab => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    const evidence = await mount(page, tab)
    const surface = page.locator(`#tab-${tab}`), rows = surface.locator('[data-report-row]:visible')
    const search = surface.locator('.search input'), more = surface.getByRole('button', { name: /^Показать ещё/ })
    expect(await rows.count()).toBe(50)
    await search.fill('SKU-60')
    await expect.poll(() => rows.count()).toBe(1)
    expect(await rows.innerText()).toContain('SKU-60')
    expect(await more.count()).toBe(0)
    await search.fill('SKU-')
    await expect.poll(() => rows.count()).toBe(50)
    await more.click()
    await expect.poll(() => rows.count()).toBe(60)
    await search.fill('SKU-60')
    await expect.poll(() => rows.count()).toBe(1)
    expect(await rows.innerText()).toContain('SKU-60')
    await search.fill('absent')
    await expect.poll(() => rows.count()).toBe(0)
    await search.fill('')
    await expect.poll(() => rows.count()).toBe(50)
    await more.click()
    await expect.poll(() => rows.count()).toBe(60)
    if (tab === 'pnl') {
      await surface.locator('select.adv-select').selectOption('mine')
      await expect.poll(() => rows.count()).toBe(0)
      await search.fill('SKU-60')
      expect(await rows.count()).toBe(0)
      await surface.locator('select.adv-select').selectOption('unassigned')
      await expect.poll(() => rows.count()).toBe(1)
    } else {
      await surface.locator('.chips .chip').filter({ hasText: /^Новинки$/ }).click()
      await expect.poll(() => rows.count()).toBe(0)
      await search.fill('SKU-60')
      expect(await rows.count()).toBe(0)
      await surface.locator('.chips .chip').filter({ hasText: /^Все товары$/ }).click()
      await expect.poll(() => rows.count()).toBe(1)
    }
    if (process.env.SATORNA_REPORT_UI_SCREENSHOTS) {
      await surface.locator('.report-table-wrap').evaluate(element => { element.scrollLeft = 0 })
      await page.screenshot({ path: `/tmp/report-ui-${tab}-search.png` })
    }
    expect(evidence.errors).toEqual([])
    expect(evidence.unexpected).toEqual([])
  } finally { await browser.close() }
}, 45_000)

it.each(['abc', 'pnl'] as const)('allows past canonical %s dates without legacy coverage and rejects future dates', async tab => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    const evidence = await mount(page, tab)
    await page.getByRole('button', { name: 'Начало периода аналитики WB', exact: true }).click()
    const past = page.locator('.products-cache-calendar-day[aria-label^="2026-09-02:"]')
    await expect.poll(() => past.getAttribute('aria-disabled')).toBe('false')
    expect(await page.locator('.products-cache-calendar-day[aria-label^="2026-09-12:"]').getAttribute('aria-disabled')).toBe('true')
    if (process.env.SATORNA_REPORT_UI_SCREENSHOTS) await page.screenshot({ path: `/tmp/report-ui-${tab}-calendar.png` })
    await past.click()
    await page.locator('.products-cache-calendar-day[aria-label^="2026-09-06:"]').click()
    await page.getByRole('button', { name: 'Применить', exact: true }).click()
    await expect.poll(() => evidence.queries.some(query => query.includes('dateFrom=2026-09-02') && query.includes('dateTo=2026-09-06'))).toBe(true)
    await expect.poll(() => page.locator(`#tab-${tab} [data-report-row]:visible`).count()).toBe(50)
    expect(evidence.errors).toEqual([])
    expect(evidence.unexpected).toEqual([])
  } finally { await browser.close() }
}, 45_000)

it('labels blocked and partial legacy P&L rows without claiming readiness', async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block' })
    const evidence = await mount(page, 'pnl', true)
    for (const status of ['blocked', 'partial', 'ready']) {
      const row = page.locator('#tab-pnl [data-report-row]').filter({ hasText: `STATUS-${status}` })
      if (status === 'ready') expect(await row.innerText()).toContain('готово')
      else expect(await row.innerText()).not.toContain('готово')
    }
    await page.getByRole('button', { name: 'Начало периода аналитики WB', exact: true }).click()
    // The rollout-disabled legacy report still uses its existing coverage gate.
    expect(await page.locator('.products-cache-calendar-day[aria-label^="2026-09-02:"]').getAttribute('aria-disabled')).toBe('true')
    expect(evidence.errors).toEqual([])
    expect(evidence.unexpected).toEqual([])
  } finally { await browser.close() }
}, 45_000)

it('keeps operational P&L coverage gating inside a canonical rollout organization', async () => {
  const browser = await chromium.launch({ headless: true })
  try {
    const page = await browser.newPage({ serviceWorkers: 'block', viewport: { width: 1512, height: 982 } })
    const evidence = await mount(page, 'pnl')
    const openCalendar = page.getByRole('button', { name: 'Начало периода аналитики WB', exact: true })
    const pastDate = page.locator('.products-cache-calendar-day[aria-label^="2026-09-02:"]')
    await openCalendar.click()
    await expect.poll(() => pastDate.getAttribute('aria-disabled')).toBe('false')
    expect(evidence.coverageQueries).toHaveLength(0)
    await page.keyboard.press('Escape')
    await page.locator('#tab-pnl .chip').filter({ hasText: 'Операционный 1С' }).click()
    await page.getByText('Ждём операционные расходы из 1С', { exact: true }).waitFor()
    await openCalendar.click()
    await expect.poll(() => evidence.coverageQueries.length).toBe(1)
    await expect.poll(() => pastDate.getAttribute('aria-disabled')).toBe('true')
    await page.keyboard.press('Escape')
    await page.locator('#tab-pnl .chip').filter({ hasText: 'Финансовый WB' }).click()
    await page.locator('#tab-pnl [data-report-row]').first().waitFor()
    await openCalendar.click()
    await expect.poll(() => pastDate.getAttribute('aria-disabled')).toBe('false')
    expect(evidence.coverageQueries).toHaveLength(1)
    expect(evidence.errors).toEqual([])
    expect(evidence.unexpected).toEqual([])
  } finally { await browser.close() }
}, 45_000)
