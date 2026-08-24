import { describe, expect, test } from 'vitest'
import {
  BulkRepricerActionRequestSchema,
  ManualPriceActionRequestSchema,
  PriceChangeEntrySchema,
  PriceGuardResponseSchema,
  PricingStatusResponseSchema,
  SkuAuditEventSchema,
  SkuSettingsResponseSchema,
  SkuTimeseriesResponseSchema,
} from './schemas'
import { CHANGELOG_ENTRIES } from './changelogFixtures'
import { getPriceGuardFixture } from './priceGuardFixtures'
import { SKU_LIST } from './skuListFixtures'

const systemActor = { id: 'system', name: 'Система', role: 'system' as const }
const managerActor = { id: 'manager-maria', name: 'Мария', role: 'manager' as const }

describe('repricer comments and audit schemas', () => {
  test('manual price action requires reason', () => {
    expect(ManualPriceActionRequestSchema.safeParse({ newPriceKopecks: 129000, reason: '' }).success).toBe(false)
    expect(ManualPriceActionRequestSchema.safeParse({ newPriceKopecks: 129000, reason: 'Проверена маржа после СПП' }).success).toBe(true)
  })

  test('bulk repricer action requires reason', () => {
    expect(BulkRepricerActionRequestSchema.safeParse({ skuIds: ['FBBT_42'], action: 'manual_mode', reason: '' }).success).toBe(false)
    expect(BulkRepricerActionRequestSchema.safeParse({ skuIds: ['FBBT_42'], action: 'manual_mode', reason: 'Разбор рекламы' }).success).toBe(true)
  })

  test('system audit can omit human reason, manual audit cannot', () => {
    expect(SkuAuditEventSchema.safeParse({
      id: 'audit-system',
      sku: 'FBBT_42',
      createdAt: new Date().toISOString(),
      actor: systemActor,
      source: 'system',
      scope: 'sku',
      action: 'Пересчёт репрайсера',
    }).success).toBe(true)

    expect(SkuAuditEventSchema.safeParse({
      id: 'audit-manual',
      sku: 'FBBT_42',
      createdAt: new Date().toISOString(),
      actor: managerActor,
      source: 'manager',
      scope: 'sku',
      action: 'Ручное изменение цены',
    }).success).toBe(false)
  })

  test('fixtures expose comments and audit events on SKU responses', () => {
    const parsed = SkuSettingsResponseSchema.parse(SKU_LIST.find((sku) => sku.meta.articleId === 'FBBT_42'))
    expect(parsed.comments.length).toBeGreaterThan(0)
    expect(parsed.commentSummary?.count).toBe(parsed.comments.length)
    expect(parsed.auditEvents.length).toBeGreaterThan(0)
  })

  test('manual and bulk changelog entries carry actor and reason', () => {
    const manual = PriceChangeEntrySchema.parse(CHANGELOG_ENTRIES.find((entry) => entry.source === 'manager'))
    const bulk = PriceChangeEntrySchema.parse(CHANGELOG_ENTRIES.find((entry) => entry.source === 'bulk'))

    expect(manual.reason).toBeTruthy()
    expect(manual.actor.role).toBe('manager')
    expect(bulk.reason).toBeTruthy()
    expect(bulk.scope).toBe('bulk')
  })

  test('pricing status exposes liquidation progress and changelog timeline', () => {
    const liquidationEvent = PriceChangeEntrySchema.parse(CHANGELOG_ENTRIES.find((entry) => entry.trigger === 'liquidation'))
    const parsed = PricingStatusResponseSchema.parse({
      articleId: liquidationEvent.articleId,
      skuName: liquidationEvent.skuName,
      stage: 'active_liquidation',
      status: 'liquidation',
      strategy: {
        id: 'liq',
        name: 'Ликвидация',
        type: 'liquidation',
        typedStrategyId: null,
        assignmentSource: 'manual',
        assignedAt: null,
        rules: [{ label: 'Шаг цены', value: '5% каждые 24 часа' }],
      },
      progress: {
        kind: 'liquidation',
        currentDay: 2,
        totalDays: 8,
        startedAt: liquidationEvent.timestamp,
        nextStepAt: new Date().toISOString(),
        stepPct: 5,
        startPriceKopecks: 175000,
        currentPriceKopecks: liquidationEvent.newPriceKopecks,
        targetPriceKopecks: 90000,
        requiresNegativeMarginConfirm: false,
      },
      current: {
        priceKopecks: liquidationEvent.newPriceKopecks,
        pMinKopecks: 90000,
        pMaxKopecks: 240000,
        marginPct: liquidationEvent.marginAfterPct,
        basketsLast7d: 2,
        basketNorm: 20,
        ordersUnits: 1,
        stockUnits: 40,
      },
      lastDecision: {
        timestamp: liquidationEvent.timestamp,
        trigger: liquidationEvent.trigger,
        reason: liquidationEvent.reason,
        oldPriceKopecks: liquidationEvent.oldPriceKopecks,
        newPriceKopecks: liquidationEvent.newPriceKopecks,
        changePct: liquidationEvent.changePct,
      },
      recentChanges: [liquidationEvent],
      changelogTotal: 1,
    })

    expect(parsed.progress.kind).toBe('liquidation')
    expect(parsed.recentChanges[0].trigger).toBe('liquidation')
  })

  test('SKU timeseries accepts real daily rows and source diagnostics', () => {
    const parsed = SkuTimeseriesResponseSchema.parse({
      articleId: 'FBBT_42',
      nmId: 123456789,
      skuName: 'Футболка',
      period: { days: 30, startDate: '2026-05-13', endDate: '2026-06-12' },
      sourceStatus: 'partial',
      sources: [
        { source: 'period-statistics', status: 'ok', rows: 2 },
        { source: 'ads-fullstats', status: 'empty', rows: 0, message: 'Нет рекламных строк за период' },
      ],
      daily: [{
        date: '2026-06-12',
        ordersUnits: 7,
        salesUnits: 5,
        returnsUnits: 1,
        revenueKopecks: 535000,
        avgPriceWithSppKopecks: 107000,
        avgSellerPriceKopecks: 139000,
        buyoutPct: 71.4,
        openCount: 410,
        cartCount: 93,
        funnelOrderCount: 7,
        crPct: 1.7,
        funnelBuyoutPct: 62,
        cartToOrderPct: 7.5,
        adSpendKopecks: null,
        adImpressions: null,
        adClicks: null,
        adCartAdds: null,
        adOrders: null,
        adRevenueKopecks: null,
        drrPct: null,
        stockUnits: 29,
        inWayToClient: 3,
        inWayFromClient: 1,
        warehouses: 4,
        stockSourceGranularity: 'snapshot',
        priceKopecks: 139000,
      }],
      hourlyOrders: [{ hour: 14, ordersUnits: 3, revenueKopecks: 321000 }],
      priceEvents: [{
        timestamp: '2026-06-12T09:30:00.000Z',
        date: '2026-06-12',
        oldPriceKopecks: 150600,
        newPriceKopecks: 139000,
        trigger: 'algorithm',
        reason: 'Strategy step',
      }],
      currentPriceKopecks: 139000,
      rawRows: null,
    })

    expect(parsed.daily[0].cartCount).toBe(93)
    expect(parsed.sources[1].status).toBe('empty')
  })

  test('SPP price guard requires an explicit blocked state when apply is unavailable', () => {
    expect(PriceGuardResponseSchema.safeParse({
      articleId: 'FBBT_42',
      currentPriceKopecks: 129000,
      buyerPriceKopecks: null,
      sppSnapshot: {
        sourceStatus: 'unknown',
        sppPct: null,
        buyerPriceKopecks: null,
        capturedAt: null,
        blockerIds: ['WB-06'],
      },
      recommendedSellerPriceKopecks: null,
      lastKnownGoodPriceKopecks: 129000,
      canApply: false,
      blockedReason: 'SPP source is not confirmed',
      freezeState: 'source_blocked',
      guardTriggers: [{
        type: 'source_stale',
        severity: 'blocker',
        observedValue: 'unknown',
        previousValue: null,
        threshold: null,
        message: 'SPP source must be confirmed before price apply',
      }],
      sourceEvidence: [{
        sourceId: 'wb-spp',
        sourceType: 'mock',
        sourceName: 'SPP discovery placeholder',
        lastSyncedAt: null,
        freshnessTtlMinutes: null,
        fieldsUsed: [],
      }],
      blockerIds: ['WB-06', 'WB-22', 'WB-23'],
    }).success).toBe(true)
  })

  test('SPP price guard rejects apply when freeze or blocker state remains', () => {
    expect(PriceGuardResponseSchema.safeParse({
      articleId: 'FBBT_42',
      currentPriceKopecks: 129000,
      buyerPriceKopecks: 101000,
      sppSnapshot: {
        sourceStatus: 'fresh',
        sppPct: 21.7,
        buyerPriceKopecks: 101000,
        capturedAt: new Date().toISOString(),
        blockerIds: [],
      },
      recommendedSellerPriceKopecks: 129000,
      lastKnownGoodPriceKopecks: 129000,
      canApply: true,
      blockedReason: null,
      freezeState: 'requires_review',
      guardTriggers: [{
        type: 'spp_jump',
        severity: 'blocker',
        observedValue: 21.7,
        previousValue: 11.2,
        threshold: 5,
        message: 'SPP jump requires review',
      }],
      sourceEvidence: [{
        sourceId: 'wb-spp',
        sourceType: 'wb_api',
        sourceName: 'WB SPP',
        lastSyncedAt: new Date().toISOString(),
        freshnessTtlMinutes: 60,
        fieldsUsed: ['sppPct'],
      }],
      blockerIds: ['WB-06'],
    }).success).toBe(false)
  })

  test('SPP runtime guard stub stays blocked until source discovery is closed', () => {
    const guard = getPriceGuardFixture('FBBT_42')

    expect(PriceGuardResponseSchema.safeParse(guard).success).toBe(true)
    expect(guard.canApply).toBe(false)
    expect(guard.freezeState).toBe('source_blocked')
    expect(guard.blockerIds).toEqual(expect.arrayContaining(['WB-06', 'WB-22', 'WB-23']))
  })
})
