import { z } from 'zod'

import { ApiError, apiRequest } from '@/lib/api'

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
const utcDateTime = z.string().datetime({ offset: true })
const nullableInteger = z.number().int().nullable()

const periodSchema = z.object({
  dateFrom: isoDate,
  dateTo: isoDate,
  timezone: z.literal('Europe/Moscow'),
  startAt: utcDateTime,
  endExclusiveAt: utcDateTime,
  days: z.number().int().min(1).max(90),
  temporalState: z.enum(['complete', 'partial', 'future']),
}).strict()

const snapshotSchema = z.object({
  syncRunId: z.string(),
  snapshotChecksum: z.string(),
  formulaVersion: z.string(),
  operationCount: z.number().int().nonnegative(),
  capturedAt: utcDateTime,
  lastObservedAt: utcDateTime,
}).strict()

const rowSchema = z.object({
  nmId: z.number().int().positive().nullable(),
  sellerArticle: z.string().nullable(),
  catalogSkuId: z.number().int().positive().nullable(),
  operationCount: z.number().int().nonnegative(),
  revenueKopecks: z.number().int(),
  salesRevenueKopecks: z.number().int(),
  returnsRevenueKopecks: z.number().int(),
  mainRevenueKopecks: z.number().int(),
  redemptionsRevenueKopecks: z.number().int(),
  lateCorrectionRevenueKopecks: z.number().int(),
  unknownRevenueKopecks: z.number().int(),
  salesUnits: z.number().int().nonnegative(),
  returnsUnits: z.number().int().nonnegative(),
  netUnits: z.number().int(),
  commissionKopecks: z.number().int(),
  logisticsKopecks: z.number().int(),
  storageKopecks: z.number().int(),
  acceptanceKopecks: z.number().int(),
  penaltyKopecks: z.number().int().nonnegative(),
  deductionKopecks: z.number().int().nonnegative(),
  additionalPaymentKopecks: z.number().int(),
  financeOtherExpensesKopecks: z.number().int().nonnegative(),
  compensationKopecks: z.number().int().nonnegative(),
  acquiringKopecks: z.number().int(),
  financeExpensesKopecks: z.number().int(),
  costValueState: z.enum(['configured', 'assumed', 'missing']),
  costEvidenceStatus: z.enum(['dated', 'undated', 'period_end_fallback']).nullable(),
  cogsKopecks: nullableInteger,
  settlementProfitKopecks: nullableInteger,
  economicsValueState: z.enum(['configured', 'assumed', 'missing']),
  economicsEvidenceStatus: z.enum(['dated', 'undated', 'period_end_fallback']).nullable(),
  taxKopecks: nullableInteger,
  otherExpensesKopecks: nullableInteger,
  profitBeforeAdsAndLoyaltyKopecks: nullableInteger,
  advertisingSpendKopecks: nullableInteger,
  profitBeforeLoyaltyKopecks: nullableInteger,
  cashbackAmountKopecks: nullableInteger,
  cashbackDiscountKopecks: nullableInteger,
  cashbackCommissionChangeKopecks: nullableInteger,
  loyaltyNetCostKopecks: nullableInteger,
  profitAfterLoyaltyKopecks: nullableInteger,
  salesClass: z.enum(['A', 'B', 'C']).nullable(),
  profitClass: z.literal(null),
  abcCode: z.literal(null),
  netProfitKopecks: z.literal(null),
  blockerIds: z.array(z.string()),
}).strict()

const summarySchema = z.object({
  operationCount: z.number().int().nonnegative(),
  skuCount: z.number().int().nonnegative(),
  revenueKopecks: z.number().int(),
  salesRevenueKopecks: z.number().int(),
  returnsRevenueKopecks: z.number().int(),
  salesUnits: z.number().int().nonnegative(),
  returnsUnits: z.number().int().nonnegative(),
  netUnits: z.number().int(),
  commissionKopecks: z.number().int(),
  logisticsKopecks: z.number().int(),
  storageKopecks: z.number().int(),
  acceptanceKopecks: z.number().int(),
  penaltyKopecks: z.number().int().nonnegative(),
  deductionKopecks: z.number().int().nonnegative(),
  financeOtherExpensesKopecks: z.number().int().nonnegative(),
  compensationKopecks: z.number().int().nonnegative(),
  acquiringKopecks: z.number().int(),
  financeExpensesKopecks: z.number().int(),
  cogsKopecks: nullableInteger,
  settlementProfitKopecks: nullableInteger,
  taxKopecks: nullableInteger,
  otherExpensesKopecks: nullableInteger,
  profitBeforeAdsAndLoyaltyKopecks: nullableInteger,
  advertisingSpendKopecks: nullableInteger,
  unattributedAdvertisingSpendKopecks: nullableInteger,
  profitBeforeLoyaltyKopecks: nullableInteger,
  cashbackAmountKopecks: nullableInteger,
  cashbackDiscountKopecks: nullableInteger,
  cashbackCommissionChangeKopecks: nullableInteger,
  loyaltyNetCostKopecks: nullableInteger,
  profitAfterLoyaltyKopecks: nullableInteger,
  netProfitKopecks: z.literal(null),
}).strict()

const metaSchema = z.object({
  state: z.enum(['ready', 'partial', 'future', 'empty', 'missing']),
  marketplaceAccountId: z.number().int().positive(),
  period: periodSchema,
  snapshot: snapshotSchema.nullable(),
  formulaVersion: z.literal('wb-abc-pnl-fullstats-loyalty-v1'),
  costLedgerRevision: z.number().int().nonnegative(),
  economicsRevision: z.number().int().nonnegative(),
  advertisingSource: z.enum(['finance_promotion', 'ads_fullstats']).nullable(),
  advertisingSnapshotChecksum: z.string().nullable(),
  advertisingEvidenceStatus: z.enum(['raw', 'aggregate_only', 'derived_legacy']).nullable(),
  blockerIds: z.array(z.string()),
}).strict()

const pageSchema = z.object({
  items: z.array(rowSchema),
  total: z.number().int().nonnegative(),
  limit: z.number().int().min(1).max(500),
  offset: z.number().int().nonnegative(),
  summary: summarySchema,
  meta: metaSchema,
  timestamp: utcDateTime,
}).strict()

export type CanonicalAbcPnlPage = z.infer<typeof pageSchema>
export type CanonicalAbcPnlRow = z.infer<typeof rowSchema>
export type CanonicalAbcPnlState = CanonicalAbcPnlPage['meta']['state']

export type CanonicalAbcPnlRollout = {
  organizationId: number
  marketplaceAccountId: number
}

export type CanonicalAbcPnlSurface = 'abc' | 'pnl'
export type CanonicalPnlMode = 'financial' | 'operational'

export function shouldUseCanonicalAbcPnl(
  rollout: CanonicalAbcPnlRollout | null,
  surface: CanonicalAbcPnlSurface,
  pnlMode: CanonicalPnlMode = 'financial',
) {
  return rollout !== null && (surface === 'abc' || pnlMode === 'financial')
}

export function canonicalPnlRowStatus(row: {
  sourceStatus?: string | null
  confidence?: string | null
  blockerIds?: string[] | null
}) {
  if (row.blockerIds?.length || row.confidence === 'blocked' || row.sourceStatus === 'partial') return 'частично'
  return row.sourceStatus ?? 'canonical'
}

export function canonicalAbcPnlEmptyMessage(
  surface: CanonicalAbcPnlSurface,
  state: CanonicalAbcPnlState | null | undefined,
) {
  if (state === 'future') {
    return surface === 'abc'
      ? 'Выбранный период находится в будущем. Canonical API не возвращает расчетные строки.'
      : 'Canonical API не рассчитывает финансовые строки для будущего периода.'
  }
  if (state === 'missing') {
    return surface === 'abc'
      ? 'Для выбранного аккаунта и периода еще нет canonical finance snapshot.'
      : 'Для выбранного аккаунта и периода нет canonical finance snapshot.'
  }
  if (state === 'empty') return 'Canonical snapshot готов, но финансовых операций за период нет.'
  return null
}

export type CanonicalPeriod = { fromIso: string; toIso: string }

export function resolveCanonicalAbcPnlRollout(
  organizationId: number | null | undefined,
  rawFlag = import.meta.env.VITE_CANONICAL_WB_ABC_PNL_ROLLOUT ?? '',
): CanonicalAbcPnlRollout | null {
  if (!Number.isSafeInteger(organizationId) || Number(organizationId) <= 0 || !rawFlag.trim()) return null
  const mappings = new Map<number, number>()
  for (const entry of rawFlag.split(',')) {
    const match = /^([1-9]\d*):([1-9]\d*)$/.exec(entry.trim())
    if (!match) return null
    const [, rawOrganizationId, rawMarketplaceAccountId] = match
    const candidateOrganizationId = Number(rawOrganizationId)
    const marketplaceAccountId = Number(rawMarketplaceAccountId)
    if (!Number.isSafeInteger(candidateOrganizationId) || !Number.isSafeInteger(marketplaceAccountId)) return null
    if (mappings.has(candidateOrganizationId)) return null
    mappings.set(candidateOrganizationId, marketplaceAccountId)
  }
  const marketplaceAccountId = mappings.get(organizationId as number)
  return marketplaceAccountId === undefined ? null : { organizationId: organizationId as number, marketplaceAccountId }
}

export function buildCanonicalAbcPnlPath(input: {
  marketplaceAccountId: number
  period: CanonicalPeriod
  limit: number
  offset: number
}) {
  const params = new URLSearchParams({
    marketplaceAccountId: String(input.marketplaceAccountId),
    dateFrom: input.period.fromIso,
    dateTo: input.period.toIso,
    limit: String(input.limit),
    offset: String(input.offset),
  })
  return `/api/v2/wb/reports/abc-pnl?${params.toString()}`
}

export function parseCanonicalAbcPnlPage(payload: unknown): CanonicalAbcPnlPage {
  const result = pageSchema.safeParse(payload)
  if (!result.success) {
    throw new ApiError('Invalid canonical ABC/P&L response', 502, 'INVALID_API_RESPONSE', result.error.flatten())
  }
  return result.data
}

type CanonicalRequest = (path: string, init?: RequestInit) => Promise<unknown>

function paginationIdentity(page: CanonicalAbcPnlPage) {
  return JSON.stringify({
    total: page.total,
    summary: page.summary,
    meta: page.meta,
  })
}

export async function fetchCanonicalAbcPnl(input: {
  accessToken: string
  marketplaceAccountId: number
  period: CanonicalPeriod
  signal?: AbortSignal
  pageSize?: number
  request?: CanonicalRequest
}): Promise<CanonicalAbcPnlPage> {
  const request = input.request ?? apiRequest
  const pageSize = Math.min(500, Math.max(1, Math.trunc(input.pageSize ?? 500)))
  const pages: CanonicalAbcPnlPage[] = []
  // Canonical finance groups rows by nmId, including one nullable unknown bucket.
  const seenNmIds = new Set<number | null>()
  let offset = 0
  let identity: string | null = null

  while (pages.length === 0 || offset < pages[0].total) {
    input.signal?.throwIfAborted()
    const path = buildCanonicalAbcPnlPath({
      marketplaceAccountId: input.marketplaceAccountId,
      period: input.period,
      limit: pageSize,
      offset,
    })
    const payload = await request(path, {
      signal: input.signal,
      headers: { Authorization: `Bearer ${input.accessToken}` },
    })
    input.signal?.throwIfAborted()
    const page = parseCanonicalAbcPnlPage(payload)
    const periodMatchesRequest = page.meta.period.dateFrom === input.period.fromIso
      && page.meta.period.dateTo === input.period.toIso
    if (
      page.offset !== offset
      || page.limit !== pageSize
      || page.meta.marketplaceAccountId !== input.marketplaceAccountId
      || !periodMatchesRequest
      || page.items.length > pageSize
    ) {
      throw new ApiError('Canonical ABC/P&L pagination drift', 409, 'CANONICAL_PAGINATION_DRIFT')
    }
    const currentIdentity = paginationIdentity(page)
    if (identity !== null && currentIdentity !== identity) {
      throw new ApiError('Canonical ABC/P&L pagination drift', 409, 'CANONICAL_PAGINATION_DRIFT')
    }
    identity = currentIdentity
    for (const item of page.items) {
      if (seenNmIds.has(item.nmId)) {
        throw new ApiError('Canonical ABC/P&L duplicate row', 409, 'CANONICAL_PAGINATION_DRIFT')
      }
      seenNmIds.add(item.nmId)
    }
    pages.push(page)
    if (page.items.length === 0) {
      if (offset < page.total) throw new ApiError('Canonical ABC/P&L pagination stalled', 409, 'CANONICAL_PAGINATION_DRIFT')
      break
    }
    offset += page.items.length
  }

  const first = pages[0]
  if (!first) throw new ApiError('Empty canonical ABC/P&L response', 502, 'INVALID_API_RESPONSE')
  const items = pages.flatMap((page) => page.items)
  if (items.length !== first.total) throw new ApiError('Canonical ABC/P&L pagination incomplete', 409, 'CANONICAL_PAGINATION_DRIFT')
  return { ...first, items, limit: pageSize, offset: 0 }
}

export type CanonicalCompatibilityMeta = {
  state: CanonicalAbcPnlState
  formulaVersion: CanonicalAbcPnlPage['meta']['formulaVersion']
  advertisingSource: CanonicalAbcPnlPage['meta']['advertisingSource']
  advertisingEvidenceStatus: CanonicalAbcPnlPage['meta']['advertisingEvidenceStatus']
  blockerIds: string[]
  period: CanonicalAbcPnlPage['meta']['period']
  snapshot: CanonicalAbcPnlPage['meta']['snapshot']
  advertisingSnapshotChecksum: string | null
  costLedgerRevision: number
  economicsRevision: number
}

function compatibilityMeta(page: CanonicalAbcPnlPage): CanonicalCompatibilityMeta {
  return {
    state: page.meta.state,
    formulaVersion: page.meta.formulaVersion,
    advertisingSource: page.meta.advertisingSource,
    advertisingEvidenceStatus: page.meta.advertisingEvidenceStatus,
    blockerIds: page.meta.blockerIds,
    period: page.meta.period,
    snapshot: page.meta.snapshot,
    advertisingSnapshotChecksum: page.meta.advertisingSnapshotChecksum,
    costLedgerRevision: page.meta.costLedgerRevision,
    economicsRevision: page.meta.economicsRevision,
  }
}

export function adaptCanonicalAbcReport(page: CanonicalAbcPnlPage) {
  return {
    rows: page.items.map((item) => ({
      sku: item.sellerArticle,
      nmId: item.nmId,
      cogsKopecks: item.cogsKopecks,
      salesComposite: { units: item.netUnits, kopecks: item.revenueKopecks, deltaPct: null },
      adSpendKopecks: item.advertisingSpendKopecks,
      profitAfterLoyaltyKopecks: item.profitAfterLoyaltyKopecks,
      salesClass: item.salesClass,
      abcCode: item.abcCode,
      costValueState: item.costValueState,
      costEvidenceStatus: item.costEvidenceStatus,
      economicsValueState: item.economicsValueState,
      economicsEvidenceStatus: item.economicsEvidenceStatus,
      blockerIds: item.blockerIds,
      canonicalSourceState: page.meta.state,
    })),
    filteredSummary: {
      salesKopecks: page.summary.revenueKopecks,
      salesCount: page.summary.netUnits,
      profitAfterLoyaltyKopecks: page.summary.profitAfterLoyaltyKopecks,
      attentionCount: page.items.filter((item) => item.blockerIds.length > 0).length,
    },
    sourceStatus: page.meta.state,
    blockerIds: page.meta.blockerIds,
    calculatedAt: page.timestamp,
    canonical: compatibilityMeta(page),
    canonicalSummary: page.summary,
  }
}

export function adaptCanonicalPnlReport(page: CanonicalAbcPnlPage) {
  return {
    meta: {
      title: 'Canonical WB ABC/P&L',
      generatedAt: page.timestamp,
      freshnessState: page.meta.state,
      sourceType: page.meta.advertisingSource,
      dateRange: { from: page.meta.period.dateFrom, to: page.meta.period.dateTo },
    },
    headline: page.meta.state === 'partial' ? 'Предварительный P&L: есть блокирующие допущения' : 'Canonical WB P&L',
    warning: page.meta.blockerIds.length > 0 ? page.meta.blockerIds.join(', ') : null,
    rows: page.items.map((item) => ({
      label: item.sellerArticle,
      articleId: item.sellerArticle,
      sku: item.sellerArticle,
      nmId: item.nmId,
      revenueKopecks: item.revenueKopecks,
      cogsKopecks: item.cogsKopecks,
      commissionKopecks: item.commissionKopecks,
      logisticsKopecks: item.logisticsKopecks,
      storageKopecks: item.storageKopecks,
      taxKopecks: item.taxKopecks,
      adSpendKopecks: item.advertisingSpendKopecks,
      overheadKopecks: null,
      returnsPenaltyKopecks: item.penaltyKopecks + item.deductionKopecks,
      netProfitKopecks: item.netProfitKopecks,
      profitAfterLoyaltyKopecks: item.profitAfterLoyaltyKopecks,
      marginPct: null,
      sourceStatus: page.meta.state,
      confidence: item.blockerIds.length > 0 ? 'blocked' : 'canonical',
      comment: item.blockerIds.join(', '),
      blockerIds: item.blockerIds,
    })),
    canonical: compatibilityMeta(page),
    canonicalSummary: page.summary,
  }
}
