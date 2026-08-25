import { afterEach, describe, expect, test, vi } from 'vitest'
import { loadLiveBasketsDetailStatus, loadLiveRepricerCacheCoverage, loadLiveRepricerStats, mapLiveRepricerRowToParityProduct, refreshLiveRepricerAllSources, startLiveBasketsDetail } from './liveParityData'

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(data: unknown) {
  return new Response(JSON.stringify(data), {
    headers: { 'content-type': 'application/json' },
  })
}

describe('basket detail background job API', () => {
  test('starts daily basket detail for the exact applied range', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      runId: 'run-1', state: 'running', cached: false, dateFrom: '2026-06-12', dateTo: '2026-07-12',
      periodDays: 31, requestsCompleted: 0, requestsTotal: 124, progressPercent: 0, updatedAt: 'now',
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await startLiveBasketsDetail('token', { dateFrom: '2026-06-12', dateTo: '2026-07-12' })

    expect(result.runId).toBe('run-1')
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/wb-repricer/baskets/detail/start'), expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ dateFrom: '2026-06-12', dateTo: '2026-07-12', scenario: 'complete', force: false }),
    }))
  })

  test('loads progress only for the requested run id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      runId: 'run with space', state: 'running', cached: false, dateFrom: '2026-06-12', dateTo: '2026-07-12',
      periodDays: 31, requestsCompleted: 17, requestsTotal: 124, progressPercent: 14, updatedAt: 'now',
      phase: 'requesting', day: '2026-06-16', dayIndex: 5, daysTotal: 31, batch: 1, batchesTotal: 4,
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadLiveBasketsDetailStatus('token', 'run with space')

    expect(result.requestsCompleted).toBe(17)
    expect(fetchMock.mock.calls[0]?.[0]).toContain('runId=run+with+space')
  })
})

describe('repricer stats live API', () => {
  test('loads diagnostics from the stats backend endpoint with the selected period and page', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      items: [],
      total: 0,
      summary: { skuCount: 0, canRecalculate: 0, priceBlocked: 0 },
      page: 2,
      pageSize: 50,
      periodDays: 14,
      cache: {},
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadLiveRepricerStats('token', undefined, {
      periodDays: 14,
      page: 2,
      pageSize: 50,
      q: 'FBBT',
    })

    expect(result.page).toBe(2)
    const requestUrl = String(fetchMock.mock.calls[0]?.[0])
    expect(requestUrl).toContain('/api/v1/wb-repricer/stats?')
    expect(requestUrl).toContain('periodDays=14')
    expect(requestUrl).toContain('page=2')
    expect(requestUrl).toContain('pageSize=50')
    expect(requestUrl).toContain('q=FBBT')
    expect(requestUrl).not.toContain('/api/v1/wb-repricer/sku?')
  })
})

describe('repricer cache coverage API', () => {
  test('loads cache coverage for the selected date range', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      dateFrom: '2026-06-10',
      dateTo: '2026-06-12',
      sources: ['period-stats', 'finance', 'ads', 'baskets'],
      days: [],
      summary: { totalDays: 3, completeDays: 0, partialDays: 0, missingDays: 3 },
    }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await loadLiveRepricerCacheCoverage('token', { dateFrom: '2026-06-10', dateTo: '2026-06-12' })

    expect(result?.summary.totalDays).toBe(3)
    const requestUrl = String(fetchMock.mock.calls[0]?.[0])
    expect(requestUrl).toContain('/api/v1/wb-repricer/cache/coverage?')
    expect(requestUrl).toContain('dateFrom=2026-06-10')
    expect(requestUrl).toContain('dateTo=2026-06-12')
  })
})

describe('repricer WB sync API', () => {
  test('routes all-source refresh through cold onboarding sync', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      state: 'queued',
      running: true,
      syncProfile: 'onboarding-full',
    }))
    vi.stubGlobal('fetch', fetchMock)

    await refreshLiveRepricerAllSources('token', undefined, { periodDays: 7, dateFrom: '2026-06-10', dateTo: '2026-06-16' }, ['finance'])

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/api/v1/wb-repricer/sync/run'), expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ scenario: 'complete', mode: 'onboarding', force: true }),
    }))
  })
})

describe('mapLiveRepricerRowToParityProduct', () => {
  test('uses direct SPP API buyer price for price after SPP instead of wallet final price', () => {
    const product = mapLiveRepricerRowToParityProduct({
      meta: {
        articleId: 'SKU-1',
        nmId: 123,
        name: 'Test product',
        status: 'auto',
        currentPriceKopecks: 220000,
        basketsLast7d: 0,
        basketNorm: 1,
        subject: 'Футболки',
        brand: 'Brand',
        chrtIds: [],
      },
      strategy: { id: 'baskets_orders', name: 'Корзины', assignmentSource: 'derived' },
      settings: {
        cogsKopecks: 50000,
        logisticsKopecks: 5000,
        minMarginPct: 15,
        wbCommissionPct: 15,
      },
      analytics: {
        buyerPriceNoWalletKopecks: 142500,
        avgPriceWithSppKopecks: 150000,
        accountedBuyerPriceKopecks: 165000,
        buyerPriceWithWalletKopecks: 160000,
        sppPct: 35.23,
        basePriceKopecks: 220000,
        sellerDiscountedPriceKopecks: 220000,
        basketsState: 'ok',
        periodStatsState: 'ok',
        stockState: 'ok',
      },
    } as any, 0)

    expect(product.avgPriceSpp).toBe(1500)
    expect(product.buyerPriceNoWallet).toBe(1425)
    expect(product.priceWithSpp).toBe(1425)
    expect(product.priceFinal).toBe(1425)
    expect(product.priceWithWallet).toBe(1650)
    expect(product.spp).toBe(35.23)
  })

  test('does not use period average as current SPP price', () => {
    const product = mapLiveRepricerRowToParityProduct({
      meta: {
        articleId: 'SKU-AVG-ONLY',
        nmId: 124,
        name: 'Average only',
        status: 'auto',
        currentPriceKopecks: 220000,
        basketsLast7d: 1,
        basketNorm: 1,
      },
      strategy: { id: 'auto', name: 'Auto' },
      settings: { cogsKopecks: 50000, logisticsKopecks: 5000, minMarginPct: 15, wbCommissionPct: 15 },
      analytics: {
        buyerPriceNoWalletKopecks: null,
        avgPriceWithSppKopecks: 150000,
        basketsState: 'ok',
        periodStatsState: 'ok',
        stockState: 'ok',
      },
    } as any, 0)

    expect(product.priceWithSpp).toBeNull()
    expect(product.avgPriceSpp).toBe(1500)
  })

  test('recomputes invalid SPP percent from seller and buyer prices', () => {
    const product = mapLiveRepricerRowToParityProduct({
      meta: {
        articleId: 'SKU-BAD-SPP',
        nmId: 456,
        name: 'Bad SPP product',
        status: 'auto',
        currentPriceKopecks: 147000,
        basketsLast7d: 0,
        basketNorm: 1,
        subject: 'Футболки',
        brand: 'Brand',
        chrtIds: [],
      },
      settings: {
        cogsKopecks: 50000,
        logisticsKopecks: 5000,
        minMarginPct: 15,
        wbCommissionPct: 15,
      },
      analytics: {
        buyerPriceNoWalletKopecks: 93900,
        buyerPriceWithWalletKopecks: 90100,
        sppPct: -6287.76,
        basketsState: 'ok',
        periodStatsState: 'ok',
        stockState: 'ok',
      },
    } as any, 0)

    expect(product.price).toBe(1470)
    expect(product.priceWithSpp).toBe(939)
    expect(product.priceWithWallet).toBe(901)
    expect(product.spp).toBe(36.12)
  })
})
