import { http, HttpResponse, delay, passthrough } from 'msw'
import {
  partialFixture,
  successFixture,
  warmupFixture,
  type Scenario,
} from '../features/wb-repricer/fixtures'
import { SKU_LIST } from '../features/wb-repricer/skuListFixtures'
import { getPriceGuardFixture } from '../features/wb-repricer/priceGuardFixtures'
import { CHANGELOG_ENTRIES } from '../features/wb-repricer/changelogFixtures'
import { computePMinKopecks, marginStatusAt } from '../features/wb-repricer/pricing'
import { PROMOTIONS, PROMOTION_SKUS, type WbPromotion } from '../features/wb-repricer/promotionsFixtures'
import { getAlerts, getExport, getReportById, normalizeDateRange } from '../features/wb-reports/repository'
import type { DatePreset, ReportGroupBy, ReportId } from '../features/wb-reports/types'
import { getNotifications } from '../features/notifications/repository'
import {
  getCurrentUserProfile,
  getMarketplaceCapabilities,
  getNotificationRoutes,
  getSessions,
  getSettingsAudit,
  getUsers,
  patchUserAccess,
  revokeSession,
  updateNotificationRoutes,
} from '../features/settings/repository'

// In-memory state for promotion Excel uploads (keyed by promo id)
const promotionOverrides = new Map<string, Partial<WbPromotion>>()


const ARTICLE_URL = '/api/v1/wb-repricer/sku/:articleId/settings'

function readScenario(request: Request): Scenario {
  const value = request.headers.get('x-scenario')
  return (value ?? 'success') as Scenario
}

export const handlers = [
  // ── Settings / access governance ──────────────────────────────────────
  http.get('/api/settings/me', async () => {
    await delay(80)
    return HttpResponse.json(getCurrentUserProfile())
  }),

  http.get('/api/settings/users', async () => {
    await delay(120)
    return HttpResponse.json({ items: getUsers() })
  }),

  http.patch('/api/settings/users/:id/access', async ({ request, params }) => {
    await delay(180)
    const body = (await request.json()) as Parameters<typeof patchUserAccess>[1]
    return HttpResponse.json(patchUserAccess(params.id as string, body))
  }),

  http.get('/api/settings/marketplaces', async () => {
    await delay(140)
    return HttpResponse.json({ items: getMarketplaceCapabilities() })
  }),

  http.get('/api/settings/notifications', async () => {
    await delay(110)
    return HttpResponse.json({ items: getNotificationRoutes() })
  }),

  http.patch('/api/settings/notifications', async ({ request }) => {
    await delay(160)
    const body = (await request.json()) as { items: Parameters<typeof updateNotificationRoutes>[0] }
    return HttpResponse.json(updateNotificationRoutes(body.items))
  }),

  http.get('/api/settings/sessions', async () => {
    await delay(100)
    return HttpResponse.json({ items: getSessions() })
  }),

  http.post('/api/settings/sessions/:id/revoke', async ({ params }) => {
    await delay(150)
    return HttpResponse.json(revokeSession(params.id as string))
  }),

  http.get('/api/settings/audit', async () => {
    await delay(120)
    return HttpResponse.json({ items: getSettingsAudit() })
  }),

  // ── Notifications ─────────────────────────────────────────────────────
  http.get('/api/notifications', async () => {
    await delay(120)
    return HttpResponse.json(getNotifications())
  }),

  // ── WB Reports ─────────────────────────────────────────────────────────
  http.get('/api/wb/reports/alerts', async () => {
    await delay(100)
    return HttpResponse.json(getAlerts())
  }),

  http.get('/api/wb/reports/export/:reportId', async ({ params }) => {
    await delay(180)
    return HttpResponse.json(getExport(params.reportId as ReportId))
  }),

  http.get('/api/wb/reports/:reportId', async ({ request, params }) => {
    await delay(220)
    const url = new URL(request.url)
    const reportId = params.reportId as ReportId
    const dateRange = normalizeDateRange({
      preset: (url.searchParams.get('preset') ?? '7d') as DatePreset,
      from: url.searchParams.get('from') ?? undefined,
      to: url.searchParams.get('to') ?? undefined,
    })
    if (reportId === 'rnp' || reportId === 'pnl' || reportId === 'expenses') {
      return passthrough()
    }
    const groupBy = (url.searchParams.get('groupBy') ?? 'sku') as ReportGroupBy
    return HttpResponse.json(getReportById(reportId, dateRange, groupBy))
  }),

  http.get('/api/v1/wb-repricer/sku/:articleId/price-guard', async ({ params }) => {
    await delay(120)
    return HttpResponse.json(getPriceGuardFixture(params.articleId as string))
  }),

  // ── Карточка SKU (GET) ─────────────────────────────────────────────────
  http.get(ARTICLE_URL, async ({ request, params }) => {
    const scenario = readScenario(request)
    const articleId = params.articleId as string
    const fromList = SKU_LIST.find((r) => r.meta.articleId === articleId)

    if (scenario === 'loading') {
      await delay(5000)
      return HttpResponse.json(fromList ?? successFixture)
    }
    if (scenario === 'error') {
      await delay(300)
      return HttpResponse.json(
        { error: { code: 'WB_API_UNAVAILABLE', message: 'WB API недоступен' } },
        { status: 500 },
      )
    }
    if (scenario === 'partial') {
      await delay(200)
      return HttpResponse.json(partialFixture())
    }
    if (scenario === 'warmup') {
      await delay(200)
      return HttpResponse.json(warmupFixture)
    }
    await delay(200)
    return HttpResponse.json(fromList ?? successFixture)
  }),

  // ── Карточка SKU (PUT) ─────────────────────────────────────────────────
  http.put(ARTICLE_URL, async ({ request }) => {
    const scenario = readScenario(request)
    const body = (await request.json()) as Record<string, unknown>
    const freshMeta = {
      ...successFixture.meta,
      lastSavedAt: new Date().toISOString(),
      status: body.automationEnabled ? 'auto' : 'manual',
    }

    if (scenario === 'saving') {
      await delay(3000)
      return HttpResponse.json({ meta: freshMeta, settings: body, cachedAt: null })
    }
    if (scenario === 'save-error') {
      await delay(400)
      return HttpResponse.json(
        { error: { code: 'WB_API_UNAVAILABLE', message: 'Не удалось сохранить настройки' } },
        { status: 500 },
      )
    }

    await delay(400)
    return HttpResponse.json({ meta: freshMeta, settings: body, cachedAt: null })
  }),

  // ── Список SKU ─────────────────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/sku', async () => {
    await delay(300)
    return HttpResponse.json({ items: SKU_LIST, total: SKU_LIST.length })
  }),

  http.get('/api/v1/wb-repricer/finance-diagnostics', async () => {
    await delay(180)
    return HttpResponse.json({
      source: 'finance',
      state: 'ok',
      refreshed: false,
      periodDays: 30,
      dateFrom: '2026-05-27',
      dateTo: '2026-06-25',
      fetchedAt: new Date().toISOString(),
      count: 1,
      rowsCount: 4,
      rawRowsStrippedFromCache: true,
      diagnostics: {
        state: 'ok',
        tax: {
          taxPct: 6,
          taxKopecks: 15600,
          taxIncludedInExpenses: false,
          note: 'Налог считается справочно и не входит в expenses/margin.',
        },
        formula: {
          taxIncludedInExpenses: false,
          financeExpensesWithoutTax: 'commission + logistics + storage + acceptance + penalty + deduction + acquiring - additionalPayment',
        },
        totals: {
          sellerRevenueKopecks: 260000,
          taxKopecks: 15600,
          expensesWithoutTaxKopecks: 93000,
          expensesIfTaxIncludedKopecks: 108600,
          storageKopecks: 0,
          acceptanceKopecks: 0,
          penaltyReturnedKopecks: 2000,
          deductionCompensationKopecks: 3000,
          additionalPaymentKopecks: 11000,
        },
        storageAcceptance: {
          rawRowsAvailable: true,
          rawRowsCount: 4,
          source: 'raw_rows',
          requestedFields: ['paidStorage', 'paidAcceptance'],
          paidStorageFieldRequested: true,
          paidStorageRowsWithField: 4,
          paidStorageNonzeroRows: 1,
          paidStorageSum: 5000,
          paidStorageSumKopecks: 5000,
          paidStorageAggregateSumKopecks: 0,
          paidStorageNonzeroSkuCount: 0,
          paidStorageMissingNmRows: 1,
          paidStorageMissingNmSumKopecks: 5000,
          paidAcceptanceFieldRequested: true,
          paidAcceptanceRowsWithField: 4,
          paidAcceptanceNonzeroRows: 0,
          paidAcceptanceSum: 0,
          paidAcceptanceSumKopecks: 0,
          paidAcceptanceAggregateSumKopecks: 0,
          paidAcceptanceNonzeroSkuCount: 0,
          paidAcceptanceMissingNmRows: 0,
          paidAcceptanceMissingNmSumKopecks: 0,
          note: 'Raw Finance detailed row counters from current WB response.',
        },
        paidStorageNonzeroRows: 0,
        paidStorageSum: 0,
        paidAcceptanceNonzeroRows: 0,
        paidAcceptanceSum: 0,
        adjustmentRowsTotal: 1,
        adjustmentRowsReturned: 1,
        adjustmentRows: [
          {
            nmId: 123456,
            rrdId: 14,
            sellerOperName: 'Возврат штрафа',
            bonusTypeName: 'Компенсация продавцу',
            raw: {
              sellerOperName: 'Возврат штрафа',
              bonusTypeName: 'Компенсация продавцу',
              penalty: '-20',
              deduction: '-30',
              additionalPayment: '40',
              rrdId: 14,
            },
            normalized: {
              penaltyKopecks: -2000,
              deductionKopecks: -3000,
              additionalPaymentKopecks: 4000,
              expenseFormulaContributionKopecks: -9000,
            },
          },
        ],
        skuSummariesTotal: 1,
        skuSummariesReturned: 1,
        skuSummaries: [
          {
            nmId: '123456',
            taxIncludedInExpenses: false,
            expensesWithoutTaxKopecks: 93000,
            expensesIfTaxIncludedKopecks: 108600,
          },
        ],
        marginBreakdown: {
          formula: 'netProfit = revenue - cogs - commission - logistics - storage - acceptance - signed(penalty) - signed(deduction) - acquiring - ads - otherExpenses + additionalPayment',
          itemsReturned: 1,
          itemsTotalFromBuiltRows: 1,
          totals: {
            actualNetProfitKopecks: 72000,
            expectedNetProfitKopecks: 72000,
            revenue: 260000,
            revenueEffect: 260000,
            cogs: 90000,
            cogsEffect: -90000,
            expensesKopecks: 98000,
            commission: 60000,
            commissionEffect: -60000,
            logistics: 2000,
            logisticsEffect: -2000,
            storage: 5000,
            storageEffect: -5000,
            unassignedStorage: 5000,
            unassignedStorageEffect: -5000,
            unassignedExpensesKopecks: 5000,
            acceptance: 0,
            acceptanceEffect: 0,
            penalty: 3000,
            penaltyEffect: -3000,
            deduction: 3000,
            deductionEffect: -3000,
            acquiring: 8000,
            acquiringEffect: -8000,
            ads: 15000,
            adsEffect: -15000,
            otherExpenses: 13000,
            otherExpensesEffect: -13000,
            additionalPayment: 11000,
            additionalPaymentEffect: 11000,
            tax: 15600,
            taxEffect: 0,
          },
          unassignedComponentsReturned: 1,
          unassignedComponents: [
            {
              key: 'unassignedStorage',
              label: 'Хранение WB без SKU',
              operation: '-',
              amountKopecks: 5000,
              effectKopecks: -5000,
              source: 'diagnostics.storageAcceptance.paidStorageSumKopecks - sum(SKU storageKopecks)',
            },
          ],
          items: [
            {
              articleId: 'FBBT_42',
              nmId: 123456,
              actualNetProfitKopecks: 77000,
              expectedNetProfitKopecks: 77000,
              deltaKopecks: 0,
              components: [
                { key: 'revenue', label: 'Выручка продавца', operation: '+', amountKopecks: 260000, effectKopecks: 260000 },
                { key: 'cogs', label: 'Себестоимость продаж', operation: '-', amountKopecks: 90000, effectKopecks: -90000 },
                { key: 'commission', label: 'Комиссия WB', operation: '-', amountKopecks: 60000, effectKopecks: -60000 },
                { key: 'logistics', label: 'Логистика WB', operation: '-', amountKopecks: 2000, effectKopecks: -2000 },
                { key: 'storage', label: 'Хранение WB', operation: '-', amountKopecks: 0, effectKopecks: 0 },
                { key: 'acceptance', label: 'Приемка WB', operation: '-', amountKopecks: 0, effectKopecks: 0 },
                { key: 'penalty', label: 'Штрафы WB net', operation: '- signed', amountKopecks: 3000, effectKopecks: -3000 },
                { key: 'deduction', label: 'Удержания WB net', operation: '- signed', amountKopecks: 3000, effectKopecks: -3000 },
                { key: 'acquiring', label: 'Эквайринг', operation: '-', amountKopecks: 8000, effectKopecks: -8000 },
                { key: 'ads', label: 'Реклама WB', operation: '-', amountKopecks: 15000, effectKopecks: -15000 },
                { key: 'otherExpenses', label: 'Прочие расходы', operation: '-', amountKopecks: 13000, effectKopecks: -13000 },
                { key: 'additionalPayment', label: 'Доплаты WB', operation: '+ credit', amountKopecks: 11000, effectKopecks: 11000 },
                { key: 'tax', label: 'Налог', operation: '0 excluded', amountKopecks: 15600, effectKopecks: 0 },
              ],
            },
          ],
        },
      },
    })
  }),

  // ── Тоггл автоматики ───────────────────────────────────────────────────
  http.patch('/api/v1/wb-repricer/sku/:articleId/automation', async ({ request }) => {
    const body = (await request.json()) as { automationEnabled: boolean }
    await delay(200)
    return HttpResponse.json({ automationEnabled: body.automationEnabled })
  }),

  // ── Дашборд ────────────────────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/dashboard', async () => {
    await delay(250)

    const counts = { auto: 0, manual: 0, warmup: 0, liquidation: 0 }
    const typeCounts: Record<string, { total: number; auto: number; marginSum: number }> = {
      F: { total: 0, auto: 0, marginSum: 0 },
      H: { total: 0, auto: 0, marginSum: 0 },
      L: { total: 0, auto: 0, marginSum: 0 },
    }
    const attention: { articleId: string; name: string; reason: string; detail: string }[] = []

    for (const item of SKU_LIST) {
      counts[item.meta.status]++
      const typeKey = item.meta.articleId[0] as 'F' | 'H' | 'L'
      typeCounts[typeKey].total++
      if (item.meta.status === 'auto') typeCounts[typeKey].auto++

      const pMin = computePMinKopecks(
        item.settings.cogsKopecks,
        item.settings.wbCommissionPct,
        item.settings.logisticsKopecks,
        item.settings.minMarginPct,
      )
      const margin = marginStatusAt(
        item.meta.currentPriceKopecks,
        item.settings.cogsKopecks,
        item.settings.wbCommissionPct,
        item.settings.logisticsKopecks,
      )
      const net =
        item.meta.currentPriceKopecks * (1 - item.settings.wbCommissionPct / 100) -
        item.settings.logisticsKopecks -
        item.settings.cogsKopecks
      const marginPct = (net / item.meta.currentPriceKopecks) * 100
      typeCounts[typeKey].marginSum += marginPct

      if (margin === 'negative') {
        attention.push({
          articleId: item.meta.articleId,
          name: item.meta.name,
          reason: 'negative_margin',
          detail: `${marginPct.toFixed(1)}%`,
        })
      } else if (item.meta.basketsLast7d < item.meta.basketNorm * 0.25) {
        attention.push({
          articleId: item.meta.articleId,
          name: item.meta.name,
          reason: 'low_baskets',
          detail: `${item.meta.basketsLast7d}/${item.meta.basketNorm}`,
        })
      }

      void pMin
    }

    const typeStats = Object.entries(typeCounts).map(([type, v]) => ({
      type,
      total: v.total,
      autoPct: v.total > 0 ? Math.round((v.auto / v.total) * 100) : 0,
      avgMarginPct: v.total > 0 ? +(v.marginSum / v.total).toFixed(1) : 0,
    }))

    return HttpResponse.json({
      counts,
      total: SKU_LIST.length,
      attention: attention.slice(0, 8),
      typeStats,
      lastSyncAt: new Date(Date.now() - 2 * 3600_000).toISOString(),
    })
  }),

  // ── Шаблоны ────────────────────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/templates', async () => {
    await delay(200)
    return HttpResponse.json({
      globalCommissionPct: 25,
      types: {
        F: { cogsKopecks: 45000, logisticsKopecks: 5000, minMarginPct: 15, pMaxKopecks: 190000 },
        H: { cogsKopecks: 85000, logisticsKopecks: 5500, minMarginPct: 15, pMaxKopecks: 320000 },
        L: { cogsKopecks: 60000, logisticsKopecks: 5200, minMarginPct: 15, pMaxKopecks: 240000 },
      },
      skuCountByType: { F: 847, H: 420, L: 223 },
    })
  }),

  http.put('/api/v1/wb-repricer/templates', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    await delay(600)
    return HttpResponse.json({ ...body, savedAt: new Date().toISOString() })
  }),

  http.post('/api/v1/wb-repricer/templates/:type/apply', async ({ params }) => {
    const type = params.type as string
    const counts: Record<string, number> = { F: 847, H: 420, L: 223 }
    await delay(800)
    return HttpResponse.json({ updated: counts[type] ?? 0 })
  }),

  // ── Ликвидация ─────────────────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/liquidation', async () => {
    await delay(250)
    const candidates = SKU_LIST.filter(
      (s) =>
        s.meta.basketsLast7d < s.meta.basketNorm * 0.25 ||
        (s.meta.status === 'manual' &&
          marginStatusAt(
            s.meta.currentPriceKopecks,
            s.settings.cogsKopecks,
            s.settings.wbCommissionPct,
            s.settings.logisticsKopecks,
          ) === 'negative'),
    ).map((s) => ({
      articleId: s.meta.articleId,
      name: s.meta.name,
      currentPriceKopecks: s.meta.currentPriceKopecks,
      basketsLast7d: s.meta.basketsLast7d,
      basketNorm: s.meta.basketNorm,
      daysSinceLastSale: Math.floor(Math.random() * 35) + 7,
      recommendedPriceKopecks: Math.round(
        computePMinKopecks(
          s.settings.cogsKopecks,
          s.settings.wbCommissionPct,
          s.settings.logisticsKopecks,
          0,
        ) * 0.95,
      ),
    }))

    const active = [
      {
        articleId: 'FBBT_55',
        name: 'Футболка белая «Принт 55»',
        startPriceKopecks: 165000,
        currentPriceKopecks: 125000,
        targetPriceKopecks: 70000,
        startedAt: new Date(Date.now() - 3 * 86400_000).toISOString(),
        nextStepAt: new Date(Date.now() + 10 * 3600_000).toISOString(),
        stepPct: 5,
        requiresNegativeMarginConfirm: false,
      },
      {
        articleId: 'HCBT_19',
        name: 'Худи чёрное «Принт 19»',
        startPriceKopecks: 285000,
        currentPriceKopecks: 155000,
        targetPriceKopecks: 145000,
        startedAt: new Date(Date.now() - 5 * 86400_000).toISOString(),
        nextStepAt: new Date(Date.now() + 2 * 3600_000).toISOString(),
        stepPct: 5,
        requiresNegativeMarginConfirm: true,
      },
    ]

    return HttpResponse.json({ candidates, active, history: [] })
  }),

  http.post('/api/v1/wb-repricer/liquidation/start', async () => {
    await delay(500)
    return HttpResponse.json({ started: true })
  }),

  http.post('/api/v1/wb-repricer/liquidation/:articleId/stop', async () => {
    await delay(300)
    return HttpResponse.json({ stopped: true })
  }),

  http.post('/api/v1/wb-repricer/liquidation/:articleId/confirm-negative', async () => {
    await delay(300)
    return HttpResponse.json({ confirmed: true, expiresAt: new Date(Date.now() + 86400_000).toISOString() })
  }),

  // ── Акции WB ──────────────────────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/promotions', async () => {
    await delay(300)
    const result = PROMOTIONS.map((p) => ({ ...p, ...promotionOverrides.get(p.id) }))
    return HttpResponse.json(result)
  }),

  http.get('/api/v1/wb-repricer/promotions/:id/skus', async ({ params }) => {
    await delay(200)
    const skus = PROMOTION_SKUS[params.id as string] ?? []
    return HttpResponse.json(skus)
  }),

  http.post('/api/v1/wb-repricer/promotions/:id/upload-excel', async ({ params, request }) => {
    await delay(1500)
    const id = params.id as string
    const formData = await request.formData()
    const file = formData.get('file') as File | null
    const fileName = file?.name ?? 'upload.xlsx'
    const now = new Date().toISOString().slice(0, 10)
    const base = PROMOTIONS.find((p) => p.id === id)
    const override: Partial<WbPromotion> = {
      excelLoaded: true,
      excelFileName: fileName,
      excelLoadedAt: now,
    }
    promotionOverrides.set(id, override)
    return HttpResponse.json({ ...base, ...override })
  }),

  // ── Журнал изменений (глобальный) ─────────────────────────────────────────
  http.get('/api/v1/wb-repricer/changelog', async ({ request }) => {
    const url = new URL(request.url)
    const articleId = url.searchParams.get('articleId')
    const trigger = url.searchParams.getAll('trigger')
    const from = url.searchParams.get('from')
    const page = parseInt(url.searchParams.get('page') ?? '1', 10)
    const limit = parseInt(url.searchParams.get('limit') ?? '50', 10)

    await delay(200)

    let items = CHANGELOG_ENTRIES
    if (articleId) items = items.filter((e) => e.articleId === articleId)
    if (trigger.length) items = items.filter((e) => trigger.includes(e.trigger))
    if (from) items = items.filter((e) => new Date(e.timestamp) >= new Date(from))

    const total = items.length
    const start = (page - 1) * limit
    return HttpResponse.json({ items: items.slice(start, start + limit), total })
  }),

  // ── Журнал изменений (per-SKU) ────────────────────────────────────────────
  http.get('/api/v1/wb-repricer/sku/:articleId/changelog', async ({ params, request }) => {
    const articleId = params.articleId as string
    const url = new URL(request.url)
    const trigger = url.searchParams.getAll('trigger')
    const from = url.searchParams.get('from')
    const page = parseInt(url.searchParams.get('page') ?? '1', 10)
    const limit = parseInt(url.searchParams.get('limit') ?? '20', 10)

    await delay(200)

    let items = CHANGELOG_ENTRIES.filter((e) => e.articleId === articleId)
    if (trigger.length) items = items.filter((e) => trigger.includes(e.trigger))
    if (from) items = items.filter((e) => new Date(e.timestamp) >= new Date(from))

    const total = items.length
    const start = (page - 1) * limit
    return HttpResponse.json({ items: items.slice(start, start + limit), total })
  }),

]
