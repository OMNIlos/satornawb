import { describe, expect, it, vi } from 'vitest'

import {
  adaptCanonicalAbcReport,
  adaptCanonicalPnlReport,
  buildCanonicalAbcPnlPath,
  canonicalAbcPnlEmptyMessage,
  canonicalPnlRowStatus,
  fetchCanonicalAbcPnl,
  parseCanonicalAbcPnlPage,
  resolveCanonicalAbcPnlRollout,
  shouldUseCanonicalAbcPnl,
} from './canonicalAbcPnl'
import { ApiError } from '@/lib/api'

const row = {
  nmId: 453200669,
  sellerArticle: 'FBBT_1133',
  catalogSkuId: 11,
  operationCount: 2,
  revenueKopecks: 120_800,
  salesRevenueKopecks: 125_000,
  returnsRevenueKopecks: -4_200,
  mainRevenueKopecks: 120_800,
  redemptionsRevenueKopecks: 0,
  lateCorrectionRevenueKopecks: 0,
  unknownRevenueKopecks: 0,
  salesUnits: 2,
  returnsUnits: 1,
  netUnits: 1,
  commissionKopecks: 10_000,
  logisticsKopecks: 2_000,
  storageKopecks: 500,
  acceptanceKopecks: 100,
  penaltyKopecks: 0,
  deductionKopecks: 0,
  additionalPaymentKopecks: 0,
  financeOtherExpensesKopecks: 300,
  compensationKopecks: 0,
  acquiringKopecks: 800,
  financeExpensesKopecks: 13_700,
  costValueState: 'assumed' as const,
  costEvidenceStatus: 'undated' as const,
  cogsKopecks: null,
  settlementProfitKopecks: null,
  economicsValueState: 'assumed' as const,
  economicsEvidenceStatus: 'undated' as const,
  taxKopecks: null,
  otherExpensesKopecks: null,
  profitBeforeAdsAndLoyaltyKopecks: null,
  advertisingSpendKopecks: 2_283,
  profitBeforeLoyaltyKopecks: null,
  cashbackAmountKopecks: 1_000,
  cashbackDiscountKopecks: 250,
  cashbackCommissionChangeKopecks: -50,
  loyaltyNetCostKopecks: 700,
  profitAfterLoyaltyKopecks: null,
  salesClass: 'A' as const,
  profitClass: null,
  abcCode: null,
  netProfitKopecks: null,
  blockerIds: ['WB_PNL_COST_ASSUMED'],
}

const summary = {
  operationCount: 2,
  skuCount: 1,
  revenueKopecks: 120_800,
  salesRevenueKopecks: 125_000,
  returnsRevenueKopecks: -4_200,
  salesUnits: 2,
  returnsUnits: 1,
  netUnits: 1,
  commissionKopecks: 10_000,
  logisticsKopecks: 2_000,
  storageKopecks: 500,
  acceptanceKopecks: 100,
  penaltyKopecks: 0,
  deductionKopecks: 0,
  financeOtherExpensesKopecks: 300,
  compensationKopecks: 0,
  acquiringKopecks: 800,
  financeExpensesKopecks: 13_700,
  cogsKopecks: null,
  settlementProfitKopecks: null,
  taxKopecks: null,
  otherExpensesKopecks: null,
  profitBeforeAdsAndLoyaltyKopecks: null,
  advertisingSpendKopecks: 2_283,
  unattributedAdvertisingSpendKopecks: 0,
  profitBeforeLoyaltyKopecks: null,
  cashbackAmountKopecks: 1_000,
  cashbackDiscountKopecks: 250,
  cashbackCommissionChangeKopecks: -50,
  loyaltyNetCostKopecks: 700,
  profitAfterLoyaltyKopecks: null,
  netProfitKopecks: null,
}

function page(state: 'ready' | 'partial' | 'future' | 'empty' | 'missing' = 'partial') {
  return {
    items: state === 'future' || state === 'empty' || state === 'missing' ? [] : [row],
    total: state === 'future' || state === 'empty' || state === 'missing' ? 0 : 1,
    limit: 500,
    offset: 0,
    summary: state === 'future' || state === 'empty' || state === 'missing'
      ? { ...summary, operationCount: 0, skuCount: 0, revenueKopecks: 0 }
      : summary,
    meta: {
      state,
      marketplaceAccountId: 31,
      period: {
        dateFrom: '2026-09-01',
        dateTo: '2026-09-07',
        timezone: 'Europe/Moscow' as const,
        startAt: '2026-08-31T21:00:00Z',
        endExclusiveAt: '2026-09-07T21:00:00Z',
        days: 7,
        temporalState: state === 'future' ? 'future' as const : 'complete' as const,
      },
      snapshot: null,
      formulaVersion: 'wb-abc-pnl-fullstats-loyalty-v1' as const,
      costLedgerRevision: 4,
      economicsRevision: 2,
      advertisingSource: 'ads_fullstats' as const,
      advertisingSnapshotChecksum: 'ads-checksum',
      advertisingEvidenceStatus: 'raw' as const,
      blockerIds: ['WB_PNL_COST_ASSUMED', 'WB_PNL_ECONOMICS_ASSUMED'],
    },
    timestamp: '2026-09-08T07:00:00Z',
  }
}

describe('canonical ABC/P&L rollout', () => {
  it('is default-off and resolves an explicit organization/account mapping', () => {
    expect(resolveCanonicalAbcPnlRollout(7, '')).toBeNull()
    expect(resolveCanonicalAbcPnlRollout(7, ' 2:31, 7:44 ')).toEqual({ organizationId: 7, marketplaceAccountId: 44 })
    expect(resolveCanonicalAbcPnlRollout(7, '7:not-a-number,7:0,broken')).toBeNull()
  })

  it('always serializes the selected preset or custom range as exact dates', () => {
    const path = buildCanonicalAbcPnlPath({
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      limit: 500,
      offset: 0,
    })
    const url = new URL(path, 'https://frontend.test')
    expect(url.pathname).toBe('/api/v2/wb/reports/abc-pnl')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      marketplaceAccountId: '31',
      dateFrom: '2026-09-01',
      dateTo: '2026-09-07',
      limit: '500',
      offset: '0',
    })
    expect(url.searchParams.has('periodDays')).toBe(false)
  })

  it('uses canonical only for an allowlisted organization and financial P&L', () => {
    const rollout = resolveCanonicalAbcPnlRollout(7, '7:44')
    expect(shouldUseCanonicalAbcPnl(rollout, 'abc')).toBe(true)
    expect(shouldUseCanonicalAbcPnl(rollout, 'pnl', 'financial')).toBe(true)
    expect(shouldUseCanonicalAbcPnl(rollout, 'pnl', 'operational')).toBe(false)
    expect(shouldUseCanonicalAbcPnl(null, 'abc')).toBe(false)
    expect(shouldUseCanonicalAbcPnl(null, 'pnl', 'financial')).toBe(false)
  })
})

describe('canonical ABC/P&L contract', () => {
  it.each(['ready', 'partial', 'future', 'empty', 'missing'] as const)('preserves the %s source state', (state) => {
    expect(parseCanonicalAbcPnlPage(page(state)).meta.state).toBe(state)
  })

  it('distinguishes zero from unavailable final fields', () => {
    const parsed = parseCanonicalAbcPnlPage({
      ...page('ready'),
      items: [{ ...row, advertisingSpendKopecks: 0, profitAfterLoyaltyKopecks: 0 }],
      summary: { ...summary, advertisingSpendKopecks: 0, profitAfterLoyaltyKopecks: 0 },
    })
    expect(parsed.items[0].advertisingSpendKopecks).toBe(0)
    expect(parsed.items[0].profitAfterLoyaltyKopecks).toBe(0)
    expect(parsed.items[0].netProfitKopecks).toBeNull()
    expect(parsed.items[0].abcCode).toBeNull()
  })

  it('rejects a response that invents final profit or a second ABC letter', () => {
    expect(() => parseCanonicalAbcPnlPage({ ...page(), items: [{ ...row, netProfitKopecks: 1 }] })).toThrow(/canonical ABC\/P&L response/i)
    expect(() => parseCanonicalAbcPnlPage({ ...page(), items: [{ ...row, abcCode: 'AA' }] })).toThrow(/canonical ABC\/P&L response/i)
  })

  it('keeps source evidence and blockers in both compatibility adapters', () => {
    const parsed = parseCanonicalAbcPnlPage(page())
    const abc = adaptCanonicalAbcReport(parsed)
    const pnl = adaptCanonicalPnlReport(parsed)

    expect(abc.canonical).toMatchObject({
      state: 'partial',
      advertisingSource: 'ads_fullstats',
      advertisingEvidenceStatus: 'raw',
      blockerIds: ['WB_PNL_COST_ASSUMED', 'WB_PNL_ECONOMICS_ASSUMED'],
    })
    expect(abc.rows[0]).toMatchObject({
      abcCode: null,
      profitAfterLoyaltyKopecks: null,
      blockerIds: ['WB_PNL_COST_ASSUMED'],
    })
    expect(abc.rows[0]).not.toHaveProperty('netTotalKopecks')
    expect(pnl.rows[0]).toMatchObject({
      netProfitKopecks: null,
      profitAfterLoyaltyKopecks: null,
      sourceStatus: 'partial',
      blockerIds: ['WB_PNL_COST_ASSUMED'],
    })
    expect(pnl.canonicalSummary.netProfitKopecks).toBeNull()
  })

  it('renders partial and blocked canonical P&L rows as partial', () => {
    expect(canonicalPnlRowStatus({ sourceStatus: 'partial', confidence: 'canonical', blockerIds: [] })).toBe('частично')
    expect(canonicalPnlRowStatus({ sourceStatus: 'ready', confidence: 'blocked', blockerIds: [] })).toBe('частично')
    expect(canonicalPnlRowStatus({ sourceStatus: 'ready', confidence: 'canonical', blockerIds: [] })).toBe('ready')
  })

  it('gives future, missing, and empty states distinct customer-facing copy', () => {
    expect(canonicalAbcPnlEmptyMessage('abc', 'future')).toContain('будущем')
    expect(canonicalAbcPnlEmptyMessage('abc', 'missing')).toContain('еще нет canonical finance snapshot')
    expect(canonicalAbcPnlEmptyMessage('pnl', 'empty')).toContain('операций за период нет')
    expect(canonicalAbcPnlEmptyMessage('pnl', 'partial')).toBeNull()
    expect(canonicalAbcPnlEmptyMessage('abc', 'ready')).toBeNull()
  })

  it('loads all pages and keeps one stable snapshot', async () => {
    const first = { ...page('ready'), total: 2, limit: 1, items: [row] }
    const second = { ...page('ready'), total: 2, limit: 1, offset: 1, items: [{ ...row, nmId: 453200670, sellerArticle: 'SECOND' }] }
    const request = vi.fn(async (path: string) => path.includes('offset=0') ? first : second)

    const result = await fetchCanonicalAbcPnl({
      accessToken: 'token',
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      pageSize: 1,
      request,
    })

    expect(request).toHaveBeenCalledTimes(2)
    expect(request).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining('marketplaceAccountId=31'),
      expect.objectContaining({ headers: { Authorization: 'Bearer token' } }),
    )
    expect(result.items.map((item) => item.sellerArticle)).toEqual(['FBBT_1133', 'SECOND'])
    expect(result.total).toBe(2)
  })

  it('rejects pagination drift instead of combining different snapshots', async () => {
    const first = { ...page('ready'), total: 2, limit: 1, items: [row] }
    const second = {
      ...page('ready'),
      total: 2,
      limit: 1,
      offset: 1,
      items: [{ ...row, nmId: 453200670 }],
      meta: { ...page('ready').meta, economicsRevision: 3 },
    }
    const request = vi.fn(async (path: string) => path.includes('offset=0') ? first : second)

    await expect(fetchCanonicalAbcPnl({
      accessToken: 'token',
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      pageSize: 1,
      request,
    })).rejects.toMatchObject({ code: 'CANONICAL_PAGINATION_DRIFT' })
  })

  it.each([
    ['response period', { meta: { ...page('ready').meta, period: { ...page('ready').meta.period, dateTo: '2026-09-06' } } }],
    ['response page size', { limit: 499 }],
  ])('rejects a mismatched %s', async (_label, override) => {
    const request = vi.fn(async () => ({ ...page('ready'), ...override }))

    await expect(fetchCanonicalAbcPnl({
      accessToken: 'token',
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      request,
    })).rejects.toMatchObject({ code: 'CANONICAL_PAGINATION_DRIFT' })
  })

  it('preserves a scoped no-access response for the consumer state', async () => {
    const denied = new ApiError('WB account is outside the actor scope', 403, 'WB_ACCOUNT_SCOPE_FORBIDDEN')
    const request = vi.fn(async () => { throw denied })

    await expect(fetchCanonicalAbcPnl({
      accessToken: 'token',
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      request,
    })).rejects.toBe(denied)
  })

  it('propagates aborts so stale period requests cannot publish', async () => {
    const aborted = new DOMException('The operation was aborted', 'AbortError')
    const request = vi.fn(async () => { throw aborted })

    await expect(fetchCanonicalAbcPnl({
      accessToken: 'token',
      marketplaceAccountId: 31,
      period: { fromIso: '2026-09-01', toIso: '2026-09-07' },
      request,
    })).rejects.toBe(aborted)
  })
})
