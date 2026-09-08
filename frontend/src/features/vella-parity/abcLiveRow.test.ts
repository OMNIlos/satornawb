import { describe, expect, it, vi } from 'vitest'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

import { AbcKpiStripIsland, ABC_TABLE_COLUMNS, installAbcLiveDataBridge, mapBackendAbcRowToParity, renderAbcRowHtml } from './VellaHtmlParityPage'

describe('ABC live row', () => {
  it('renders WB-backed values in the same order as the table headers', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        reportSkuOpenAttrs: () => '',
        reportThumb: () => '',
        abcBadgeClass: () => 'aa',
        promoStateHTML: (value: string) => value,
        managerCellHTML: () => 'manager',
        pairMetricCell: (value: string) => value,
        reportCommentCell: () => 'comment',
        warehouseMetrics: () => ({ ktr: 9.99, localization: 77, tag: 'warn' }),
      },
    })

    const row = mapBackendAbcRowToParity({
      sku: 'FBBT_11',
      nmId: 111,
      productName: 'Футболка',
      productStatus: 'locomotive',
      abcCode: 'AA',
      promotionStatus: 'no',
      priceBeforeSppKopecks: 130_000,
      priceWithSppKopecks: 110_000,
      cogsPerUnitKopecks: 45_000,
      cogsKopecks: 90_000,
      marginKopecks: 65_000,
      marginPct: 50,
      marginDeltaPct: null,
      impressions: 1_000,
      clicks: 200,
      clicksDeltaPct: 10,
      ctrPct: 20,
      baskets: 90,
      basketsDeltaPct: 30,
      cartCrPct: 44.44,
      ordersComposite: { units: 40, kopecks: 4_000_000, deltaPct: 25 },
      salesComposite: { units: 25, kopecks: 2_500_000, deltaPct: -10 },
      adSpendKopecks: 50_000,
      drrSalesPct: 2,
      netTotalKopecks: 650_000,
      netPerUnitKopecks: 65_000,
      logisticsCostPct: 5,
      logisticsDeltaPct: null,
      commissionCostPct: 10,
      commissionDeltaPct: null,
      storageCostPct: 1,
      storageDeltaPct: null,
      ktrIndex: null,
      localizationPct: 46,
      wbStockUnits: 15,
      wbStockKopecks: 1_650_000,
      ruleEvaluation: { status: 'risk' },
    })
    const html = renderAbcRowHtml(row, 0)
    const cells = Array.from(html.matchAll(/data-vella-cell="([^"]+)"/g), (match) => match[1])

    expect(ABC_TABLE_COLUMNS.map((column) => column.label)).toContain('Показы')
    expect(cells).toEqual([
      'abc-product-cell', 'abc-wb-cell', 'abc-status-cell', 'abc-code-cell', 'abc-action-cell', 'abc-promo-cell',
      'abc-manager-cell', 'abc-price-cell', 'abc-cogs-cell', 'abc-margin-cell', 'abc-impressions-cell', 'abc-clicks-cell',
      'abc-baskets-cell', 'abc-cr-cell', 'abc-orders-cell', 'abc-sales-cell', 'abc-ads-cell', 'abc-net-cell',
      'abc-logistics-cell', 'abc-commission-cell', 'abc-storage-cell', 'abc-warehouse-cell', 'abc-stock-cell', 'abc-comment-cell',
    ])
    expect(row).toMatchObject({
      price: '1 300 ₽',
      spp: 'с СПП 1 100 ₽',
      cogs: '450 ₽',
      margin: '650 ₽ / 50%',
      views: '1 000',
      clicks: '200',
      clicksSub: 'CTR 20% · +10%',
      basketDelta: '+30%',
      cr: '44,4%',
      warehouse: '—',
      localization: '46%',
    })
    expect(String(row.orders)).toContain('+25%')
    expect(String(row.sales)).toContain('−10%')
    expect(row.action).toBe('аудит')
    expect(html).not.toContain('9.99')
    expect(html).not.toContain('лок. 77%')
    expect(mapBackendAbcRowToParity({ priceWithSppKopecks: 110_000 }).price).toBe('—')
    expect(mapBackendAbcRowToParity({ abcCode: 'CC', ruleEvaluation: { status: 'normal' } }).action).toBe('наблюдать')
  })

  it('renders the backend attention count instead of a local ABC heuristic', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        __vellaAbcLiveLoading: false,
        __vellaAbcLiveRows: [],
        __vellaAbcLiveReport: {
          filteredSummary: { attentionCount: 2, ordersCount: 0, profitKopecks: 0 },
          rows: [
            { abcCode: 'AA', ruleEvaluation: { status: 'risk' }, salesComposite: { kopecks: 0 } },
            { abcCode: 'BB', ruleEvaluation: { status: 'risk' }, salesComposite: { kopecks: 0 } },
          ],
        },
      },
    })

    const html = renderToStaticMarkup(createElement(AbcKpiStripIsland, { replacementKey: 'abc-test' }))

    expect(html).toContain('Требуют внимания')
    expect(html).toContain('<div class="stat-val">2</div>')
  })

  it('renders canonical sales class and preliminary profit without inventing final values', () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: {
        reportSkuOpenAttrs: () => '',
        reportThumb: () => '',
        abcBadgeClass: () => 'neutral',
        pairMetricCell: (value: string) => value,
      },
    })
    const unavailable = mapBackendAbcRowToParity({
      sku: 'FBBT_11',
      nmId: 111,
      salesClass: 'A',
      abcCode: null,
      profitAfterLoyaltyKopecks: null,
      adSpendKopecks: 0,
      canonicalSourceState: 'partial',
      blockerIds: ['WB_PNL_COST_ASSUMED'],
      salesComposite: { units: 1, kopecks: 10_000, deltaPct: null },
    })

    expect(unavailable).toMatchObject({
      abc: 'A·—',
      net: '—',
      netCls: '',
      status: 'нет данных',
      action: 'нет данных',
      orders: '—',
      ordersKnown: false,
      profitKnown: false,
      adsKnown: true,
    })
    expect(renderAbcRowHtml(unavailable, 0)).toContain('не финальная чистая прибыль')

    const zero = mapBackendAbcRowToParity({
      salesClass: null,
      abcCode: null,
      profitAfterLoyaltyKopecks: 0,
      canonicalSourceState: 'ready',
    })
    expect(zero).toMatchObject({ abc: '—', net: '0 ₽', profitKnown: true })
  })

  it('uses canonical no-access copy only while the canonical rollout is active', async () => {
    function installWindow() {
      Object.defineProperty(globalThis, 'window', {
        configurable: true,
        value: Object.assign(new EventTarget(), {
          location: { pathname: '/wb/reports/abc', search: '', origin: 'http://localhost' },
          localStorage: { getItem: () => null, setItem: () => undefined },
          setTimeout: (callback: () => void) => { callback(); return 0 },
          __vellaReportPeriods: {
            abc: { days: 7, fromIso: '2026-09-01', toIso: '2026-09-07', label: '7 дней', mode: 'custom' as const },
          },
          __vellaPublishAbcRowsSnapshot: () => undefined,
        }),
      })
    }

    const deniedResponse = () => new Response(JSON.stringify({ detail: 'legacy forbidden' }), {
      status: 403,
      headers: { 'content-type': 'application/json' },
    })
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    installWindow()
    const canonicalFetch = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () => deniedResponse())
    vi.stubGlobal('fetch', canonicalFetch)
    installAbcLiveDataBridge('token', { organizationId: 7, marketplaceAccountId: 31 })
    await window.__vellaLoadLiveAbcReport?.()
    expect(String(canonicalFetch.mock.calls[0]?.[0])).toContain('/api/v2/wb/reports/abc-pnl?')
    expect(window.__vellaAbcLiveAccessDenied).toBe(true)
    expect(window.__vellaAbcLiveError).toContain('canonical ABC/P&L')

    installWindow()
    const legacyFetch = vi.fn<(input: RequestInfo | URL, init?: RequestInit) => Promise<Response>>(async () => deniedResponse())
    vi.stubGlobal('fetch', legacyFetch)
    installAbcLiveDataBridge('token')
    await window.__vellaLoadLiveAbcReport?.()
    expect(String(legacyFetch.mock.calls[0]?.[0])).toContain('/api/wb/reports/abc/latest-cache?')
    expect(window.__vellaAbcLiveAccessDenied).toBe(false)
    expect(window.__vellaAbcLiveError).toBe('legacy forbidden')

    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('publishes canonical loading and generic error states without inventing no-access', async () => {
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: Object.assign(new EventTarget(), {
        location: { pathname: '/wb/reports/abc', search: '', origin: 'http://localhost' },
        localStorage: { getItem: () => null, setItem: () => undefined },
        setTimeout: (callback: () => void) => { callback(); return 0 },
        __vellaReportPeriods: {
          abc: { days: 7, fromIso: '2026-09-01', toIso: '2026-09-07', label: '7 дней', mode: 'custom' as const },
        },
        __vellaPublishAbcRowsSnapshot: () => undefined,
      }),
    })
    let rejectRequest!: (reason: Error) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((_resolve, reject) => {
      rejectRequest = reject
    })))
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)

    installAbcLiveDataBridge('token', { organizationId: 7, marketplaceAccountId: 31 })
    const load = window.__vellaLoadLiveAbcReport?.()
    expect(window.__vellaAbcLiveLoading).toBe(true)
    rejectRequest(new Error('network down'))
    await load

    expect(window.__vellaAbcLiveLoading).toBe(false)
    expect(window.__vellaAbcLiveAccessDenied).toBe(false)
    expect(window.__vellaAbcLiveError).toBe('network down')

    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('restores a previously visited period without another request', async () => {
    const periods = {
      first: { days: 7, fromIso: '2026-08-18', toIso: '2026-08-24', label: '7 дней', mode: 'custom' as const },
      second: { days: 14, fromIso: '2026-08-11', toIso: '2026-08-24', label: '14 дней', mode: 'custom' as const },
    }
    const storage = new Map<string, string>()
    Object.defineProperty(globalThis, 'window', {
      configurable: true,
      value: Object.assign(new EventTarget(), {
        location: { pathname: '/wb/reports/abc', search: '', origin: 'http://localhost' },
        localStorage: {
          getItem: (key: string) => storage.get(key) ?? null,
          setItem: (key: string, value: string) => storage.set(key, value),
        },
        setTimeout: (callback: () => void) => { callback(); return 0 },
        __vellaReportPeriods: { abc: periods.first },
        __vellaPublishAbcRowsSnapshot: () => undefined,
        applyAbcFilter: () => undefined,
      }),
    })
    let resolveSecond!: (response: Response) => void
    const fetchMock = vi.fn((input: string | URL | Request) => {
      const url = String(input)
      const sku = url.includes('2026-08-11') ? 'SECOND' : 'FIRST'
      const response = new Response(JSON.stringify({ rows: [{ sku }], filteredSummary: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      })
      return sku === 'SECOND'
        ? new Promise<Response>((resolve) => { resolveSecond = resolve })
        : Promise.resolve(response)
    })
    vi.stubGlobal('fetch', fetchMock)

    try {
      installAbcLiveDataBridge('token')
      await window.__vellaLoadLiveAbcReport?.()
      window.__vellaReportPeriods = { abc: periods.second }
      const secondLoad = window.__vellaLoadLiveAbcReport?.()
      await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
      window.__vellaReportPeriods = { abc: periods.first }
      await window.__vellaLoadLiveAbcReport?.()
      resolveSecond(new Response(JSON.stringify({ rows: [{ sku: 'SECOND' }], filteredSummary: {} }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }))
      await secondLoad

      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(window.__vellaAbcLiveRows?.[0]?.sku).toBe('FIRST')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
