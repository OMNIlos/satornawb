import { ApiError, apiRequest, buildApiUrl } from '@/lib/api'
import { authorizationHeaders } from '@/features/auth/authApi'
import { sharedStatusRequest } from './sharedStatusRequest'
import { resolvePresetPeriodRange } from './presetPeriodAnchor'

function wbBasketNumber(volume: number) {
  const ranges = [
    [143, 1], [287, 2], [431, 3], [719, 4], [1007, 5], [1061, 6], [1115, 7], [1169, 8],
    [1313, 9], [1601, 10], [1655, 11], [1919, 12], [2045, 13], [2189, 14], [2405, 15], [2621, 16],
    [2837, 17], [3053, 18], [3269, 19], [3485, 20], [3701, 21], [3917, 22], [4133, 23], [4349, 24],
    [4565, 25], [4877, 26], [5189, 27], [5501, 28], [5813, 29], [6125, 30], [6437, 31], [6749, 32],
    [7061, 33], [12541, 44],
  ] as const
  return ranges.find(([limit]) => volume <= limit)?.[1] ?? 44
}

function wbProductPhotoUrl(nmId?: number | string | null) {
  const id = Number.parseInt(String(nmId ?? '').replace(/\D/g, ''), 10)
  if (!Number.isFinite(id) || id <= 0) return null
  const vol = Math.floor(id / 100000)
  const part = Math.floor(id / 1000)
  return `https://basket-${String(wbBasketNumber(vol)).padStart(2, '0')}.wbbasket.ru/vol${vol}/part${part}/${id}/images/c516x688/1.webp`
}

export type LiveRepricerSkuRow = {
  meta: {
    articleId: string
    nmId?: number | null
    name: string
    status: 'auto' | 'manual' | 'warmup' | 'liquidation'
    currentPriceKopecks: number
    basketsLast7d: number
    basketNorm: number
    warmupDaysLeft?: number | null
    managerId?: string | null
    managerName?: string
    assignmentSource?: 'manual' | 'xlsx' | 'none'
    subject?: string
    brand?: string | null
    imageUrl?: string | null
    photoUrl?: string | null
    chrtIds?: number[]
    activeStrategyId?: string | null
    activeStrategyName?: string
    activeTypedStrategyId?: string | null
    priceSource?: 'wb_cache' | 'local_override' | string
    localPriceOverrideActive?: boolean
  }
  strategy?: {
    id: string
    name: string
    typedStrategyId?: string | null
    type?: string
    description?: string
    color?: string
    assignedAt?: string | null
    assignmentSource?: 'manual' | 'xlsx' | 'none' | 'derived' | string
  status?: string
  config?: Record<string, unknown>
}
  settings: {
    wbCommissionPct: number
    minMarginKopecks?: number | null
    minMarginPct: number
    cogsKopecks: number
    logisticsKopecks: number
    otherExpensePerSaleKopecks?: number | null
    otherExpensePricePct?: number | null
    taxPct?: number | null
    maxMarginKopecks?: number | null
    maxMarginPct?: number | null
    pMinKopecks?: number | null
    pMaxKopecks?: number | null
    priceStepPct?: number | null
    priceStepMinutes?: number | null
    priceStepHours?: number | null
    rrpKopecks?: number | null
    allowNegativeMargin?: boolean
    automationEnabled?: boolean
    basketNormMode?: string
    basketNormManual?: number | null
    repricerMode?: string
    revenueComparisonDays?: number
    nightMedianEnabled?: boolean
    promoBoostEnabled?: boolean
    promoBoostPct?: number
    promoBoostHours?: number
    pickPackCostPercent?: number | null
    promoCostPercent?: number | null
    competeDiffType?: string | number | null
    competePriceType?: string | number | null
    competeDiffValue?: number | null
    ordersPlanQty?: number | null
    ordersPlanDays?: number | null
    ordersPlanType?: string | number | null
    normalStockQty?: number | null
    targetDiscountPct?: number | null
    minCompeteStock?: number | null
    useSpp?: boolean
    beautyPriceEnabled?: boolean
    beautyPriceMode?: string | number | null
    beautyPriceTemplate?: string | number | null
    beautyPriceMaxChangeKopecks?: number | null
    beautyPriceMaxChangePct?: number | null
    storageCostPerSaleKopecks?: number | null
    discountType?: string | number | null
    beautyPriceLevel?: string | number | null
    promoBoostType?: string | number | null
    useOutOfStock?: boolean
    targetTurnover?: number | null
    advertCostPercent?: number | null
    competeWalletType?: string | number | null
    stockFbs?: number | null
    stockFbm?: number | null
  }
  analytics?: {
    abcCode?: string
    promotionStatus?: 'yes' | 'no'
    promotionStatusText?: string | null
    promotionName?: string | null
    promotionId?: string | number | null
    wbStockUnits?: number | null
    stockState?: 'ok' | 'fallback' | 'no_data'
    buyoutPct?: number
    baskets?: number | null
    basketsState?: 'ok' | 'fallback' | 'no_data'
    ordersUnits?: number
    cancelledOrdersUnits?: number | null
    previousPeriod?: {
      baskets?: number | null
      ordersUnits?: number | null
      funnelOrderCount?: number | null
    } | null
    periodStatsState?: 'ok' | 'fallback' | 'no_data'
    salesUnits?: number | null
    returnsUnits?: number | null
    revenueKopecks?: number | null
    basePriceKopecks?: number
    sellerDiscountedPriceKopecks?: number
    buyerPriceNoWalletKopecks?: number | null
    buyerPriceWithWalletKopecks?: number | null
    accountedBuyerPriceKopecks?: number | null
    marginBaseKopecks?: number | null
    avgPriceWithSppKopecks?: number | null
    marginPct?: number | null
    marginKopecks?: number | null
    wbCommissionPct?: number | null
    baseWbCommissionPct?: number | null
    acquiringPct?: number | null
    commissionDisplayPct?: number | null
    commissionSource?: string | null
    commissionState?: 'ok' | 'fallback_hidden' | 'no_data' | string
    commissionReason?: string | null
    reportCommissionPct?: number | null
    sppPct?: number | null
    sppSource?: string | null
    sppObservedAt?: string | null
    periodSppPct?: number | null
    periodSppObservedAt?: string | null
    financeSppPct?: number | null
    liveSppPct?: number | null
    sppAccountingMode?: 'spp_only' | 'spp_plus_wallet' | string
    accountedWbWalletPct?: number | null
    accountedPlatformDiscountPct?: number | null
    walletPct?: number | null
    totalWbDiscountPct?: number | null
    wbWalletPct?: number | null
    sppState?: 'ok' | 'fallback' | 'no_data' | 'no_buyer_price'
    commissionKopecks?: number | null
    logisticsKopecks?: number | null
    storageKopecks?: number | null
    acceptanceKopecks?: number | null
    penaltyKopecks?: number | null
    deductionKopecks?: number | null
    payableKopecks?: number | null
    adSpendKopecks?: number | null
    adImpressions?: number | null
    adClicks?: number | null
    adCartAdds?: number | null
    adOrders?: number | null
    adRevenueKopecks?: number | null
    otherExpensesKopecks?: number | null
    taxKopecks?: number | null
    taxPct?: number | null
    expensesKopecks?: number | null
    acquiringKopecks?: number | null
    plannedMarginKopecks?: number | null
    plannedPeriodMarginKopecks?: number | null
    factNetProfitKopecks?: number | null
    netProfitKopecks?: number | null
    cogsTotalKopecks?: number | null
    discountPct?: number | null
    financeState?: 'ok' | 'fallback' | 'no_data'
  }
}

export type LiveRepricerSkuListResponse = {
  items: LiveRepricerSkuRow[]
  total: number
  totalCached?: number
  itemsReturned?: number
  page?: number
  pageSize?: number
  /** Window the backend actually answered for; a preset is anchored on the last closed WB day. */
  dateFrom?: string
  dateTo?: string
  periodDays?: number
  summary?: LiveRepricerSkuListSummary
  cache?: {
    pagesCached: number
    totalCached: number
    nextOffset: number
    pageLimit: number
    latestFetchedAt?: string | null
    stocksFetchedAt?: string | null
    periodStatsFetchedAt?: string | null
    financeFetchedAt?: string | null
    financeCachedGoodsNmIds?: number | null
    financeMatchedNmIds?: number | null
    adsFetchedAt?: string | null
    adsCount?: number | null
    adsCampaignCount?: number | null
    adsDateFrom?: string | null
    adsDateTo?: string | null
    adsSource?: string | null
    adsSpendKopecks?: number | null
    adsImpressions?: number | null
    adsClicks?: number | null
    adsCartAdds?: number | null
    adsOrders?: number | null
    adsRevenueKopecks?: number | null
    adsLastStatus?: string | null
    adsLastError?: string | null
    adsLastFinishedAt?: string | null
    basketsFetchedAt?: string | null
    basketsRequestedNmIds?: number | null
    basketsMatchedNmIds?: number | null
    periodDays?: number
    dateFrom?: string | null
    dateTo?: string | null
    requestedRange?: { from?: string | null; to?: string | null } | null
    statsSourceRange?: { from?: string | null; to?: string | null } | null
    statsSourceStatus?: string | null
    statsRangeAdjusted?: boolean
    periodCacheSuffix?: string | null
    listPage?: number
    listItemsLimit?: number
    listTotalFiltered?: number
  }
  trace?: LiveRepricerLoadTrace
}

export type LiveRepricerLoadTrace = {
  kind?: string
  startedAt?: string | null
  totalMs?: number
  steps?: Array<{
    name: string
    durationMs?: number
    elapsedMs?: number
    meta?: Record<string, unknown>
  }>
}

export type LiveRepricerSkuListSummary = {
  revenueKopecks?: number
  marginKopecks?: number
  cogsKopecks?: number
  expensesKopecks?: number
  storageKopecks?: number
  acceptanceKopecks?: number
  unassignedStorageKopecks?: number
  unassignedAcceptanceKopecks?: number
  unassignedExpensesKopecks?: number
  ordersUnits?: number
  cancelledOrdersUnits?: number
  salesUnits?: number
  returnsUnits?: number
  adSpendKopecks?: number
  adImpressions?: number
  adClicks?: number
  adCartAdds?: number
  adOrders?: number
  adRevenueKopecks?: number
  adSkuCount?: number
  avgMarginPct?: number
  totalBaskets?: number
  inSale?: number
  promoSharePct?: number
  skuCount?: number
}

export type LiveRepricerStatsMetricPayload = {
  impressions?: number | null
  clicks?: number | null
  ctrPct?: number | null
  adCartAdds?: number | null
  adOrders?: number | null
  baskets?: number | null
  orders?: number | null
  cartToOrderCrPct?: number | null
  revenueKopecks?: number | null
  netProfitKopecks?: number | null
  marginPct?: number | null
  adSpendKopecks?: number | null
  adRevenueKopecks?: number | null
  drrPct?: number | null
  stockUnits?: number | null
  currentPriceKopecks?: number | null
  avgPriceWithSppKopecks?: number | null
  medianPriceKopecks?: number | null
  sppPct?: number | null
  commissionPct?: number | null
}

export type LiveRepricerStatsItem = {
  articleId: string
  nmId?: number | null
  name?: string | null
  brand?: string | null
  imageUrl?: string | null
  photoUrl?: string | null
  status?: string | null
  managerId?: string | null
  managerName?: string | null
  strategyId?: string | null
  strategyName?: string | null
  promotionStatus?: string | null
  promotionStatusText?: string | null
  decision?: {
    id?: string | null
    label?: string | null
    tone?: 'ok' | 'warn' | 'bad' | 'neutral' | string | null
    reasons?: string[]
  }
  flags?: string[]
  metrics?: LiveRepricerStatsMetricPayload
  priceProtection?: {
    status?: string | null
    blockerIds?: string[]
    message?: string | null
  }
  sources?: {
    status?: 'ready' | 'partial' | 'blocked' | string | null
    missing?: string[]
    fresh?: string[]
    states?: Record<string, unknown>
  }
}

export type LiveRepricerStatsSummary = {
  skuCount?: number
  canRecalculate?: number
  priceBlocked?: number
  sourceReady?: number
  sourcePartial?: number
  sourceBlocked?: number
  impressions?: number
  clicks?: number
  adCtrPct?: number | null
  baskets?: number
  orders?: number
  cartToOrderCrPct?: number | null
  adSpendKopecks?: number
  revenueKopecks?: number
  drrPct?: number | null
}

export type LiveRepricerStatsResponse = {
  items: LiveRepricerStatsItem[]
  total: number
  totalCached?: number
  itemsReturned?: number
  page?: number
  pageSize?: number
  periodDays?: number
  dateFrom?: string
  dateTo?: string
  summary?: LiveRepricerStatsSummary
  cache?: LiveRepricerSkuListResponse['cache'] & {
    statsPage?: number
    statsItemsLimit?: number
    statsTotalFiltered?: number
  }
}

export type LiveRepricerProductsQuery = {
  periodDays?: number
  dateFrom?: string
  dateTo?: string
  page?: number
  pageSize?: number
  q?: string
  status?: string
  brand?: string
  manager?: string
  topMode?: boolean
}

export type LiveRepricerStrategySnapshotItem = {
  id: string
  type: string
  name: string
  color: string
  description: string
  applied: number
  status: string
  badgeClass: string
  badgeText: string
  typedStrategyId?: string | null
  rules: Array<{ label: string; value: string }>
  missingData?: string[]
  disabled?: boolean
  config?: Record<string, unknown>
}

type LiveRepricerStrategyCatalogResponse = {
  items: LiveRepricerStrategySnapshotItem[]
  total: number
}

export type LiveRepricerSkuGroup = {
  groupId: string
  groupName: string
  articleIds: string[]
  planOrders: number
  createdAt?: string | null
  updatedAt?: string | null
}

type LiveRepricerSkuGroupsResponse = {
  items: LiveRepricerSkuGroup[]
  total: number
}

export type LiveRepricerProductsPayload = {
  total: number
  products: ReturnType<typeof mapLiveRepricerRowToParityProduct>[]
  summary?: LiveRepricerSkuListSummary
  cache?: LiveRepricerSkuListResponse['cache']
  trace?: LiveRepricerLoadTrace
}

export type LiveRepricerSkuSettingsPayload = LiveRepricerSkuRow & {
  cachedAt?: string | null
  auditEvents?: unknown[]
}

export type LiveRepricerSyncStatus = {
  state: 'idle' | 'running' | 'completed' | 'partial' | 'failed' | 'stale' | string
  running: boolean
  stale?: boolean
  runId?: string | null
  trigger?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  periodDays?: number | null
  dateFrom?: string | null
  dateTo?: string | null
  periodCacheSuffix?: string | null
  syncProfile?: string | null
  syncProfileLabel?: string | null
  windowKind?: string | null
  cadenceMinutes?: number | null
  basketsDailyDetail?: boolean | null
  estimatedRequests?: number | null
  estimatedSeconds?: number | null
  estimateExplanation?: string | null
  sources?: string[]
  tokenFingerprint?: string | null
  organizationId?: number | null
  actorUserId?: string | null
  diagnostics?: {
    userTokenPresent?: boolean
    organizationTokenPresent?: boolean
    cachedGoodsCount?: number | null
    cachedGoodsFetchedAt?: string | null
  }
  currentSource?: string | null
  updatedAt?: string | null
  steps?: Array<{
    source: string
    status: string
    count?: number
    error?: string
    reason?: string
    startedAt?: string
    finishedAt?: string
    campaignCount?: number
    progressPercent?: number
    progressCurrent?: number | null
    progressTotal?: number | null
    phase?: string
    message?: string
    request?: string
  }>
  syncPlan?: Array<{
    syncProfile: string
    syncProfileLabel?: string | null
    group?: 'onboarding' | 'periodic' | 'nightly' | string
    windowKind?: string | null
    cadenceMinutes?: number | null
    dateFrom?: string | null
    dateTo?: string | null
    periodDays?: number | null
    sources?: string[]
    basketsDailyDetail?: boolean | null
    estimatedRequests?: number | null
    estimatedSeconds?: number | null
    estimateExplanation?: string | null
    lastRunAt?: string | null
    nextRunAt?: string | null
    due?: boolean
    dueInSeconds?: number | null
    running?: boolean
    cacheReady?: boolean
    sourceReadiness?: Array<{
      source: string
      ready: boolean
      reason?: string | null
      count?: number | null
      dateFrom?: string | null
      dateTo?: string | null
      requiredDays?: number | null
      dailyAggregatesDays?: number | null
      dailyDetailStatus?: string | null
      dailyDetailError?: string | null
      dailyDetailDeferredAt?: string | null
      dailyDetailPausedAt?: string | null
      dailyDetailFailedAt?: string | null
      dailyDetailFetchedAt?: string | null
      dailyDetailPartialAt?: string | null
      dailyDetailPreservedAt?: string | null
      dailyDetailPreservedBy?: string | null
      dailyDetailRequestsCompleted?: number | string | null
      dailyDetailRequestsTotal?: number | string | null
      fetchedAt?: string | null
    }>
    state?: 'pending' | 'running' | 'completed' | 'partial' | 'scheduled' | 'due' | string
  }>
  error?: string | null
}

export type LiveRepricerReportSnapshotsStatus = {
  state: 'idle' | 'queued' | 'running' | 'completed' | 'partial' | 'failed' | string
  running?: boolean
  taskId?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  updatedAt?: string | null
  processed?: number | null
  total?: number | null
  failed?: number | null
  percent?: number | null
  dateFrom?: string | null
  dateTo?: string | null
  periodDays?: number | null
  stage?: string | null
  label?: string | null
  detail?: string | null
  error?: string | null
}

export type LiveRepricerCacheCoverageDay = {
  date: string
  state: 'complete' | 'partial' | 'missing' | string
  availableSources: string[]
  missingSources: string[]
  sourceFetchedAt?: Record<string, string>
}

export type LiveRepricerCacheCoverage = {
  dateFrom: string
  dateTo: string
  sources: string[]
  days: LiveRepricerCacheCoverageDay[]
  summary: {
    totalDays: number
    completeDays: number
    partialDays: number
    missingDays: number
  }
}

let liveProductsInFlight: Promise<LiveRepricerProductsPayload> | null = null
let liveProductsInFlightKey = ''
let liveProductsCachedAt = 0
let liveProductsCache: LiveRepricerProductsPayload | null = null
let liveProductsCachePeriodDays = 7
let liveProductsCacheKey = ''
let liveStrategiesInFlight: Promise<LiveRepricerStrategySnapshotItem[]> | null = null
let liveStrategiesCachedAt = 0
let liveStrategiesCache: LiveRepricerStrategySnapshotItem[] | null = null
const LIVE_PRODUCTS_CACHE_TTL_MS = 30_000
const DEFAULT_REPRICER_PERIOD_DAYS = 7

function sourcePriority(state: 'ok' | 'fallback' | 'no_data' | null | undefined) {
  if (state === 'ok') return 2
  if (state === 'fallback') return 1
  return 0
}

function parityProductDemandScore(product: ReturnType<typeof mapLiveRepricerRowToParityProduct>) {
  const orders = Number(product.ordersPeriod ?? 0)
  const baskets = Number(product.bsk ?? 0)
  const revenue = Number(product.revenue7d ?? 0)
  return orders * 1e9 + baskets * 1e6 + revenue
}

function compareParityProductsByDemand(left: ReturnType<typeof mapLiveRepricerRowToParityProduct>, right: ReturnType<typeof mapLiveRepricerRowToParityProduct>) {
  const scoreDiff = parityProductDemandScore(right) - parityProductDemandScore(left)
  if (scoreDiff !== 0) return scoreDiff > 0 ? 1 : -1

  const demandLeft = Number(left.ordersPeriod ?? 0) > 0 || Number(left.bsk ?? 0) > 0 ? 1 : 0
  const demandRight = Number(right.ordersPeriod ?? 0) > 0 || Number(right.bsk ?? 0) > 0 ? 1 : 0
  if (demandLeft !== demandRight) return demandRight - demandLeft

  const ordersDiff = Number(right.ordersPeriod ?? 0) - Number(left.ordersPeriod ?? 0)
  if (ordersDiff !== 0) return ordersDiff

  const financeDiff = sourcePriority(right.financeState) - sourcePriority(left.financeState)
  if (financeDiff !== 0) return financeDiff

  const periodDiff = sourcePriority(right.periodStatsState) - sourcePriority(left.periodStatsState)
  if (periodDiff !== 0) return periodDiff

  const basketsDiff = sourcePriority(right.basketsState) - sourcePriority(left.basketsState)
  if (basketsDiff !== 0) return basketsDiff

  const revenueDiff = Number(right.revenue7d ?? 0) - Number(left.revenue7d ?? 0)
  if (revenueDiff !== 0) return revenueDiff

  const basketsCountDiff = Number(right.bsk ?? 0) - Number(left.bsk ?? 0)
  if (basketsCountDiff !== 0) return basketsCountDiff

  const stockDiff = Number(right.stock ?? 0) - Number(left.stock ?? 0)
  if (stockDiff !== 0) return stockDiff

  return String(left.sku ?? '').localeCompare(String(right.sku ?? ''), 'ru', { numeric: true, sensitivity: 'base' })
}

function kopecksToRub(value: number | null | undefined) {
  return Math.round((value ?? 0) / 100)
}

function normalizeBuyerKopecks(value: number | null | undefined, sellerKopecks: number | null | undefined) {
  if (value == null) return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric <= 0) return null
  const seller = Number(sellerKopecks ?? 0)
  if (seller > 0 && numeric > seller * 5) {
    return Math.round(numeric / 100)
  }
  return Math.round(numeric)
}

function normalizeSppPct(value: number | null | undefined) {
  if (value == null) return null
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric < 0 || numeric > 100) return null
  return Number(numeric.toFixed(2))
}

function deriveSppPct(sellerKopecks: number | null | undefined, buyerKopecks: number | null | undefined) {
  const seller = Number(sellerKopecks ?? 0)
  const buyer = Number(buyerKopecks ?? 0)
  if (!Number.isFinite(seller) || !Number.isFinite(buyer) || seller <= 0 || buyer <= 0 || buyer > seller) return null
  return Number((((seller - buyer) / seller) * 100).toFixed(2))
}

function thumbType(articleId: string) {
  const first = articleId[0]?.toLowerCase() ?? 'f'
  const second = articleId[1]?.toLowerCase() ?? 'b'
  if ((first === 'f' || first === 'h' || first === 'l') && (second === 'b' || second === 'c')) return `${first}${second}`
  return 'fb'
}

function normalizeParityProductText(value: string | null | undefined) {
  return String(value ?? '').toLowerCase().replace(/ё/g, 'е')
}

function inferParityProductType(row: LiveRepricerSkuRow) {
  const haystack = [
    row.meta.subject,
    row.meta.name,
    row.meta.articleId,
  ].map(normalizeParityProductText).join(' ')

  if (/лонг|long\s*sleeve|longsleeve/.test(haystack)) return 'longsleeve'
  if (/худи|hoodie|толстов/.test(haystack)) return 'hoodie'
  if (/шорт|short/.test(haystack)) return 'shorts'
  if (/балак|balaclava/.test(haystack)) return 'balaclava'
  return 'shirt'
}

function inferParityProductColor(row: LiveRepricerSkuRow) {
  const haystack = [
    row.meta.subject,
    row.meta.name,
    row.meta.articleId,
  ].map(normalizeParityProductText).join(' ')

  if (/черн|black|\bbc|\bfc|\bhc|\blc/.test(haystack)) return 'black'
  if (/бел|white|\bwb|\bfb|\bhb|\blb/.test(haystack)) return 'white'
  return ''
}

function sparkBars(baskets: number, norm: number) {
  const ratio = baskets / Math.max(1, norm)
  if (ratio >= 1.2) return [1, 2, 2, 3, 3]
  if (ratio >= 0.9) return [1, 1, 2, 2, 3]
  if (ratio >= 0.5) return [0, 1, 1, 2, 2]
  return [0, 0, 1, 1, 1]
}

function periodTrend(current: number | null | undefined, previous: number | null | undefined) {
  if (previous == null || !Number.isFinite(Number(previous))) return ''
  const currentValue = Number(current ?? 0)
  const previousValue = Number(previous)
  if (currentValue > previousValue) return 'up'
  if (currentValue < previousValue) return 'down'
  return 'flat'
}

function parityStatus(row: LiveRepricerSkuRow) {
  if (row.meta.status === 'liquidation') return 'illiquid'
  if (row.meta.status === 'manual') return 'manual'
  if (row.meta.status === 'warmup') return 'new'
  const marginPct = row.analytics?.marginPct ?? 0
  if (marginPct < 10 || row.meta.basketsLast7d < row.meta.basketNorm) return 'illiquid'
  return 'loko'
}

function parityAssignmentSource(row: LiveRepricerSkuRow) {
  return row.strategy?.assignmentSource ?? row.meta.assignmentSource ?? 'none'
}

function parityTemplate(row: LiveRepricerSkuRow) {
  const assignedStrategy = row.strategy?.id ?? row.meta.activeStrategyId
  const assignmentSource = parityAssignmentSource(row)
  if (assignmentSource === 'manual' || assignmentSource === 'xlsx') {
    return assignedStrategy ? String(assignedStrategy) : ''
  }
  return ''
}

function assignedStrategyName(row: LiveRepricerSkuRow) {
  const assignmentSource = parityAssignmentSource(row)
  if (assignmentSource !== 'manual' && assignmentSource !== 'xlsx') return ''
  return row.strategy?.name ?? row.meta.activeStrategyName ?? ''
}

function parityPMinRub(row: LiveRepricerSkuRow) {
  const commission = Number(row.settings.wbCommissionPct ?? 0)
  const minMargin = Number(row.settings.minMarginPct ?? 0)
  const denominator = 1 - (commission + minMargin) / 100
  if (denominator <= 0) return 0
  const numerator = Number(row.settings.cogsKopecks ?? 0) + Number(row.settings.logisticsKopecks ?? 0)
  return Math.round(numerator / denominator / 100)
}

export function mapLiveRepricerRowToParityProduct(row: LiveRepricerSkuRow, index: number) {
  const basketsState = row.analytics?.basketsState ?? 'no_data'
  const periodStatsState = row.analytics?.periodStatsState ?? 'no_data'
  const stockState = row.analytics?.stockState ?? 'no_data'
  const baskets = basketsState === 'no_data' ? 0 : row.analytics?.baskets ?? row.meta.basketsLast7d ?? 0
  const basketNorm = row.meta.basketNorm ?? Math.max(1, baskets)
  const currentPrice = kopecksToRub(row.meta.currentPriceKopecks)
  const basePrice = kopecksToRub(row.analytics?.basePriceKopecks ?? row.meta.currentPriceKopecks)
  const accountedPlatformDiscountPct = row.analytics?.accountedPlatformDiscountPct ?? null
  const buyerPriceNoWalletKopecks = normalizeBuyerKopecks(row.analytics?.buyerPriceNoWalletKopecks, row.meta.currentPriceKopecks)
  const avgPriceWithSppKopecks = normalizeBuyerKopecks(row.analytics?.avgPriceWithSppKopecks, row.meta.currentPriceKopecks)
  const buyerPriceWithWalletKopecks = normalizeBuyerKopecks(row.analytics?.buyerPriceWithWalletKopecks, row.meta.currentPriceKopecks)
  const accountedBuyerPriceKopecks = normalizeBuyerKopecks(row.analytics?.accountedBuyerPriceKopecks, row.meta.currentPriceKopecks)
  const priceWithSpp = buyerPriceNoWalletKopecks != null ? kopecksToRub(buyerPriceNoWalletKopecks) : null
  const avgPriceSpp = avgPriceWithSppKopecks != null ? kopecksToRub(avgPriceWithSppKopecks) : null
  const accountedBuyerPriceRub = accountedBuyerPriceKopecks != null
    ? kopecksToRub(accountedBuyerPriceKopecks)
    : null
  const buyerPriceWithWalletRub = buyerPriceWithWalletKopecks != null
    ? kopecksToRub(buyerPriceWithWalletKopecks)
    : null
  const priceWithWallet = accountedBuyerPriceRub ?? buyerPriceWithWalletRub
  const directSppPrice = priceWithSpp
  const financeState = row.analytics?.financeState ?? 'no_data'
  const hasFinance = financeState === 'ok' || financeState === 'fallback'
  const stock = stockState === 'no_data' ? 0 : row.analytics?.wbStockUnits ?? Math.max(0, baskets * 2)
  const ordersPeriod = periodStatsState === 'no_data' ? 0 : row.analytics?.ordersUnits ?? Math.max(0, baskets - 2)
  const previousBaskets = row.analytics?.previousPeriod?.baskets
  const previousOrders = row.analytics?.previousPeriod?.ordersUnits ?? row.analytics?.previousPeriod?.funnelOrderCount
  const marginRub = row.analytics?.marginKopecks != null ? kopecksToRub(row.analytics.marginKopecks) : null
  const managerName = row.meta.managerName || 'Без ответственного'
  const commissionSource = row.analytics?.commissionSource ?? null
  const commissionIsFallbackSource = !commissionSource
    || commissionSource.startsWith('fallback.')
    || commissionSource === 'settings.globalCommissionPct'
  const commissionState = row.analytics?.commissionState ?? (commissionIsFallbackSource ? 'fallback_hidden' : 'ok')
  const commissionDisplayPct = commissionState === 'ok' && row.analytics?.commissionDisplayPct != null
    ? row.analytics.commissionDisplayPct
    : null
  const commissionPct = commissionDisplayPct != null ? Number(commissionDisplayPct.toFixed(1)) : null
  const sppPct = normalizeSppPct(row.analytics?.sppPct)
    ?? deriveSppPct(row.meta.currentPriceKopecks, buyerPriceNoWalletKopecks)
  const commissionRub = hasFinance && row.analytics?.commissionKopecks != null
    ? kopecksToRub(row.analytics.commissionKopecks)
    : null
  const logisticsRub = hasFinance && row.analytics?.logisticsKopecks != null
    ? kopecksToRub(row.analytics.logisticsKopecks)
    : null
  const storageRub = hasFinance && row.analytics?.storageKopecks != null
    ? kopecksToRub(row.analytics.storageKopecks)
    : null
  const adSpendRub = hasFinance && row.analytics?.adSpendKopecks != null
    ? kopecksToRub(row.analytics.adSpendKopecks)
    : null
  const adRevenueRub = hasFinance && row.analytics?.adRevenueKopecks != null
    ? kopecksToRub(row.analytics.adRevenueKopecks)
    : null
  const cogsTotalRub = hasFinance && row.analytics?.cogsTotalKopecks != null
    ? kopecksToRub(row.analytics.cogsTotalKopecks)
    : null
  const expensesRub = hasFinance && row.analytics?.expensesKopecks != null
    ? kopecksToRub(row.analytics.expensesKopecks)
    : null
  const financeNetProfitRub = hasFinance && row.analytics?.netProfitKopecks != null
    ? kopecksToRub(row.analytics.netProfitKopecks)
    : null
  const plannedPeriodMarginRub = row.analytics?.plannedPeriodMarginKopecks != null
    ? kopecksToRub(row.analytics.plannedPeriodMarginKopecks)
    : null
  const financeRevenueRub = kopecksToRub(row.analytics?.revenueKopecks ?? 0)
  const revenue7d = hasFinance ? financeRevenueRub : 0
  const storagePerSku = storageRub
  const netPerUnit = marginRub
  const netSku = financeNetProfitRub != null
    ? financeNetProfitRub
    : plannedPeriodMarginRub != null
      ? plannedPeriodMarginRub
    : marginRub != null && ordersPeriod > 0
      ? marginRub * ordersPeriod
      : null
  const calculatedPminRub = parityPMinRub(row)
  const pminRub = row.settings.pMinKopecks != null && row.settings.pMinKopecks > 0
    ? kopecksToRub(row.settings.pMinKopecks)
    : calculatedPminRub
  const pmaxRub = kopecksToRub(row.settings.pMaxKopecks ?? Math.max(row.analytics?.basePriceKopecks ?? 0, row.meta.currentPriceKopecks))
  const walletPct = row.analytics?.accountedWbWalletPct ?? row.analytics?.walletPct ?? row.analytics?.wbWalletPct ?? 0
  const sppMultiplier = Math.max(0, 1 - (sppPct ?? 0) / 100)
  const finalMultiplier = Math.max(0, 1 - ((sppPct ?? 0) + walletPct) / 100)
  const productType = inferParityProductType(row)
  const productColor = inferParityProductColor(row)
  const rawPromotionLabel = String(row.analytics?.promotionStatusText || row.analytics?.promotionName || '').trim()
  const promotionLabel = /^Участвует:/i.test(rawPromotionLabel) ? String(row.analytics?.promotionName || '').trim() : rawPromotionLabel
  const noPromotionReason = /^Не участвует:/i.test(rawPromotionLabel) ? rawPromotionLabel : ''
  const promotionFallbackLabel = row.analytics?.promotionId != null ? `Акция ${row.analytics.promotionId}` : ''
  const displayPromotionLabel = promotionLabel && promotionLabel !== 'В акции' ? promotionLabel : promotionFallbackLabel
  const wbPhotoUrl = wbProductPhotoUrl(row.meta.nmId)
  const backendPhotoUrl = row.meta.imageUrl || row.meta.photoUrl || null
  const photoUrl = backendPhotoUrl && !/\/\/basket-\d+\.wbbasket\.ru\//i.test(backendPhotoUrl)
    ? backendPhotoUrl
    : wbPhotoUrl || backendPhotoUrl

  return {
    sel: index < 2,
    sku: row.meta.articleId,
    photoUrl,
    imageUrl: photoUrl,
    size: row.meta.subject || 'WB SKU',
    t: thumbType(row.meta.articleId),
    type: productType,
    color: productColor,
    name: row.meta.name,
    status: parityStatus(row),
    sub: row.meta.status === 'warmup' && row.meta.warmupDaysLeft ? `ещё ${row.meta.warmupDaysLeft} дн` : '',
    price: currentPrice,
    prevPrice: basePrice,
    pmin: pminRub,
    financeState,
    financeLabel: hasFinance ? null : 'нет данных',
    basketsState,
    periodStatsState,
    stockState,
    mg: row.analytics?.marginPct != null ? Math.round(row.analytics.marginPct) : null,
    mgRub: marginRub,
    bsk: baskets,
    previousBaskets,
    previousOrdersPeriod: previousOrders,
    bskTrend: periodTrend(baskets, previousBaskets),
    bskBars: sparkBars(baskets, basketNorm),
    stock,
    stockCls: stock === 0 ? 'zero' : stock <= 5 ? 'crit' : stock <= 20 ? 'low' : '',
    stockRub: stock * currentPrice,
    dl: basketNorm,
    dlCls: baskets >= basketNorm ? 't-ok' : baskets <= Math.max(2, Math.floor(basketNorm * 0.5)) ? 't-hot' : 't-warn',
    tpl: parityTemplate(row),
    strategyName: assignedStrategyName(row),
    strategyColor: row.strategy?.color ?? '',
    strategyDescription: row.strategy?.description ?? '',
    strategyAssignmentSource: parityAssignmentSource(row),
    nmId: row.meta.nmId ?? 0,
    abc: row.analytics?.abcCode ?? 'CC',
    abcCode: row.analytics?.abcCode ?? 'CC',
    promoActive: row.analytics?.promotionStatus === 'yes',
    promoPrice: row.analytics?.promotionStatus === 'yes' ? currentPrice : 0,
    promotionStatusText: displayPromotionLabel || promotionLabel || null,
    promotionName: displayPromotionLabel || promotionLabel || null,
    promotionId: row.analytics?.promotionId ?? null,
    promoState: row.analytics?.promotionStatus === 'yes' ? (displayPromotionLabel || promotionLabel || 'да') : (noPromotionReason || 'нет'),
    avgPriceSpp,
    priceWithSpp,
    priceWithWallet,
    spp: sppPct != null ? Number(sppPct.toFixed(2)) : null,
    pureSpp: sppPct != null ? Number(sppPct.toFixed(2)) : null,
    sppSource: row.analytics?.sppSource ?? null,
    sppObservedAt: row.analytics?.sppObservedAt ?? null,
    periodSppPct: row.analytics?.periodSppPct ?? null,
    periodSppObservedAt: row.analytics?.periodSppObservedAt ?? null,
    financeSppPct: row.analytics?.financeSppPct ?? null,
    liveSppPct: row.analytics?.liveSppPct ?? null,
    sppState: row.analytics?.sppState ?? (sppPct != null ? 'ok' : 'no_data'),
    sppAccountingMode: row.analytics?.sppAccountingMode ?? 'spp_only',
    accountedWbWalletPct: row.analytics?.accountedWbWalletPct ?? null,
    accountedPlatformDiscountPct,
    accountedBuyerPrice: accountedBuyerPriceRub,
    commissionPct,
    baseWbCommissionPct: row.analytics?.baseWbCommissionPct ?? null,
    commissionSource,
    commissionState,
    commissionReason: row.analytics?.commissionReason ?? null,
    commissionRub,
    ordersPeriod,
    ordersTrend: periodTrend(ordersPeriod, previousOrders),
    cancelledOrdersUnits: row.analytics?.cancelledOrdersUnits ?? 0,
    salesUnits: row.analytics?.salesUnits ?? 0,
    returnsUnits: row.analytics?.returnsUnits ?? 0,
    buyout: row.analytics?.buyoutPct ?? null,
    views: null,
    views7d: null,
    cr: null,
    adSpend: adSpendRub,
    adSpend7d: adSpendRub,
    adImpressions: row.analytics?.adImpressions ?? null,
    adClicks: row.analytics?.adClicks ?? null,
    adCartAdds: row.analytics?.adCartAdds ?? null,
    adOrders: row.analytics?.adOrders ?? null,
    adRevenue: adRevenueRub,
    revenue7d,
    cogsTotal: cogsTotalRub,
    expenses: expensesRub,
    drr: null,
    adRoi: null,
    cogs: kopecksToRub(row.settings.cogsKopecks),
    logistics: logisticsRub,
    storagePerSku,
    storage: storageRub,
    taxes: row.analytics?.taxPct ?? 6,
    stockMin: 5,
    daysToOos: ordersPeriod > 0 ? Math.round(stock / Math.max(1, ordersPeriod / 7)) : 0,
    orders7d: ordersPeriod,
    revenue: revenue7d,
    netPerUnit,
    netSku,
    wbWallet: row.analytics?.accountedWbWalletPct ?? row.analytics?.walletPct ?? row.analytics?.wbWalletPct ?? null,
    totalWbDiscountPct: accountedPlatformDiscountPct ?? row.analytics?.totalWbDiscountPct ?? null,
    buyerPriceNoWallet: buyerPriceNoWalletKopecks != null ? kopecksToRub(buyerPriceNoWalletKopecks) : null,
    buyerPriceWithWallet: buyerPriceWithWalletRub,
    priceFinal: directSppPrice ?? priceWithWallet,
    adsDataAvailable: adSpendRub != null || row.analytics?.adImpressions != null || row.analytics?.adClicks != null,
    demandTimeseriesAvailable: false,
    priceHistoryAvailable: false,
    pminHistoryAvailable: false,
    impactForecastAvailable: false,
    rrp: row.settings.rrpKopecks != null && row.settings.rrpKopecks > 0
      ? kopecksToRub(row.settings.rrpKopecks)
      : Math.max(basePrice, currentPrice),
    pminBeforeSpp: pminRub,
    pmaxBeforeSpp: pmaxRub,
    pminAfterSpp: Math.round(pminRub * sppMultiplier),
    pmaxAfterSpp: Math.round(pmaxRub * sppMultiplier),
    pminFinal: Math.round(pminRub * finalMultiplier),
    pmaxFinal: Math.round(pmaxRub * finalMultiplier),
    promoBoost: Boolean(row.settings.promoBoostEnabled),
    promoBoostPct: Number(row.settings.promoBoostPct ?? 25),
    promoBoostHours: Number(row.settings.promoBoostHours ?? 48),
    targetMarginPct: Number(row.settings.minMarginPct ?? 0),
    priceStepPct: row.settings.priceStepPct == null ? null : Number(row.settings.priceStepPct),
    priceStepMinutes: row.settings.priceStepMinutes == null
      ? (row.settings.priceStepHours == null ? null : Number(row.settings.priceStepHours) * 60)
      : Number(row.settings.priceStepMinutes),
    priceStepHours: row.settings.priceStepHours == null ? 1 : Number(row.settings.priceStepHours),
    nightMedianEnabled: Boolean(row.settings.nightMedianEnabled),
    settings: row.settings,
    priceRaw: currentPrice,
    avgPriceSppRaw: avgPriceSpp,
    priceWithWalletRaw: priceWithWallet,
    managerId: row.meta.managerId ?? null,
    managerName,
    manager: managerName,
    assignmentSource: row.meta.assignmentSource ?? 'none',
    brand: (row.meta.brand || 'wb').toLowerCase(),
    chrtIds: row.meta.chrtIds ?? [],
  }
}

export async function loadLiveRepricerSkuSettings(accessToken: string, articleId: string, signal?: AbortSignal) {
  return apiRequest<LiveRepricerSkuSettingsPayload>(`/api/v1/wb-repricer/sku/${encodeURIComponent(articleId)}/settings`, {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
}

export async function updateLiveRepricerSkuSettings(
  accessToken: string,
  articleId: string,
  settingsPatch: Record<string, unknown>,
  signal?: AbortSignal,
) {
  const payload = await apiRequest<LiveRepricerSkuSettingsPayload>(`/api/v1/wb-repricer/sku/${encodeURIComponent(articleId)}/settings`, {
    method: 'PUT',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify(settingsPatch),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

export async function updateLiveRepricerSkuManager(
  accessToken: string,
  articleId: string,
  managerUserId: string | null,
  reason: string,
  signal?: AbortSignal,
) {
  const payload = await apiRequest<LiveRepricerSkuSettingsPayload>(`/api/v1/wb-repricer/sku/${encodeURIComponent(articleId)}/manager-simple`, {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({ managerUserId, reason }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

export async function loadLiveRepricerParityProducts(
  accessToken: string,
  signal?: AbortSignal,
  periodDaysOrQuery: number | LiveRepricerProductsQuery = DEFAULT_REPRICER_PERIOD_DAYS,
  force = false,
) {
  const query = typeof periodDaysOrQuery === 'number' ? { periodDays: periodDaysOrQuery } : periodDaysOrQuery
  const period = normalizeLiveRepricerPeriod(query)
  const periodDays = period.periodDays
  const page = Math.max(1, query.page ?? 1)
  const pageSize = Math.max(25, Math.min(500, query.pageSize ?? 150))
  const params = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
    topMode: query.topMode === false ? 'false' : 'true',
  })
  appendLiveRepricerPeriodParams(params, period)
  if (query.q?.trim()) params.set('q', query.q.trim())
  if (query.status && query.status !== 'all') params.set('status', query.status)
  if (query.brand && query.brand !== 'all') params.set('brand', query.brand)
  if (query.manager && query.manager !== 'all') params.set('manager', query.manager)
  const cacheKey = params.toString()
  const now = Date.now()
  if (
    !force
    && liveProductsCache
    && liveProductsCachePeriodDays === periodDays
    && liveProductsCacheKey === cacheKey
    && now - liveProductsCachedAt <= LIVE_PRODUCTS_CACHE_TTL_MS
  ) {
    return liveProductsCache
  }
  if (!force && liveProductsInFlight && liveProductsInFlightKey === cacheKey) {
    return liveProductsInFlight
  }

  liveProductsInFlightKey = cacheKey
  liveProductsInFlight = apiRequest<LiveRepricerSkuListResponse>(`/api/v1/wb-repricer/sku?${params.toString()}`, {
    headers: authorizationHeaders(accessToken),
    cache: 'no-store',
    signal,
  }).then((resolvedPayload) => {
    if (!resolvedPayload) return { total: 0, products: [] }
    const rows = Array.isArray(resolvedPayload.items) ? resolvedPayload.items : []
    const products = rows.map(mapLiveRepricerRowToParityProduct)
    if (query.topMode !== false) products.sort(compareParityProductsByDemand)
    const total = Number(resolvedPayload.total ?? rows.length)
    const cache = resolvedPayload.cache
      ? {
          ...resolvedPayload.cache,
          listTotalFiltered: total,
          listPage: page,
          listItemsLimit: pageSize,
          totalCached: Number(resolvedPayload.totalCached ?? resolvedPayload.cache.totalCached ?? total),
        }
      : undefined
    const mapped = {
      total,
      products,
      summary: resolvedPayload.summary,
      cache,
      trace: resolvedPayload.trace,
      // The backend anchors a preset period on the last closed WB day, so the
      // window it answered for can differ from the one the picker assumed.
      // Carry it through and let the UI label the numbers it is showing.
      dateFrom: resolvedPayload.dateFrom,
      dateTo: resolvedPayload.dateTo,
      periodDays: resolvedPayload.periodDays,
    }
    liveProductsCachedAt = Date.now()
    liveProductsCachePeriodDays = periodDays
    liveProductsCacheKey = cacheKey
    liveProductsCache = mapped
    return mapped
  }).finally(() => {
    liveProductsInFlight = null
    liveProductsInFlightKey = ''
  })

  if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
  return liveProductsInFlight
}

export async function loadLiveRepricerStats(
  accessToken: string,
  signal?: AbortSignal,
  query: LiveRepricerProductsQuery = {},
) {
  const period = normalizeLiveRepricerPeriod(query)
  const page = Math.max(1, query.page ?? 1)
  const pageSize = Math.max(25, Math.min(500, query.pageSize ?? 150))
  const params = new URLSearchParams({
    page: String(page),
    pageSize: String(pageSize),
    topMode: query.topMode === false ? 'false' : 'true',
  })
  appendLiveRepricerPeriodParams(params, period)
  if (query.q?.trim()) params.set('q', query.q.trim())
  if (query.status && query.status !== 'all') params.set('status', query.status)
  if (query.brand && query.brand !== 'all') params.set('brand', query.brand)
  if (query.manager && query.manager !== 'all') params.set('manager', query.manager)
  const payload = await apiRequest<LiveRepricerStatsResponse>(`/api/v1/wb-repricer/stats?${params.toString()}`, {
    headers: authorizationHeaders(accessToken),
    cache: 'no-store',
    signal,
  })
  if (!payload) return { items: [], total: 0, page, pageSize, periodDays: period.periodDays } satisfies LiveRepricerStatsResponse
  return payload
}

export function resetLiveRepricerParityCache() {
  liveProductsInFlight = null
  liveProductsInFlightKey = ''
  liveProductsCachedAt = 0
  liveProductsCache = null
}

export function resetLiveRepricerStrategiesCache() {
  liveStrategiesInFlight = null
  liveStrategiesCachedAt = 0
  liveStrategiesCache = null
}

export async function refreshLiveRepricerParityProducts(
  accessToken: string,
  offset: number,
  signal?: AbortSignal,
  period: number | LiveRepricerPeriodRequest = DEFAULT_REPRICER_PERIOD_DAYS,
) {
  const params = new URLSearchParams({ limit: '100', offset: String(Math.max(0, offset)) })
  if (offset === 0) params.set('all', 'true')
  const payload = await apiRequest<LiveRepricerSkuListResponse>(`/api/v1/wb-repricer/sku/refresh?${params.toString()}`, {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
  if (!payload) return { total: 0, products: [], cache: undefined }
  resetLiveRepricerParityCache()
  const loaded = await loadLiveRepricerParityProducts(accessToken, signal, period, true)
  return payload.cache ? { ...loaded, cache: payload.cache } : loaded
}

export async function loadLiveRepricerSyncStatus(accessToken: string, _signal?: AbortSignal) {
  // The shared poll is not tied to one caller's lifetime, so an individual
  // abort signal no longer applies - callers just drop the resolved value.
  return sharedStatusRequest('sync-status', 10_000, () =>
    apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/status', {
      headers: authorizationHeaders(accessToken),
      cache: 'no-store',
    }),
  )
}

export async function loadLiveRepricerReportSnapshotsStatus(accessToken: string, signal?: AbortSignal) {
  return apiRequest<LiveRepricerReportSnapshotsStatus>('/api/v1/wb-repricer/report-snapshots/status', {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
}

export async function startLiveRepricerReportSnapshotsMaterialize(accessToken: string, signal?: AbortSignal) {
  return apiRequest<LiveRepricerReportSnapshotsStatus>('/api/v1/wb-repricer/report-snapshots/materialize', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
}

export async function loadLiveRepricerCacheCoverage(
  accessToken: string,
  range: Pick<LiveRepricerPeriodRequest, 'dateFrom' | 'dateTo'>,
  signal?: AbortSignal,
) {
  const params = new URLSearchParams()
  params.set('dateFrom', range.dateFrom || '')
  params.set('dateTo', range.dateTo || '')
  return apiRequest<LiveRepricerCacheCoverage>(`/api/v1/wb-repricer/cache/coverage?${params.toString()}`, {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
}

export async function refreshLiveRepricerAllSources(
  accessToken: string,
  signal?: AbortSignal,
  periodInput: number | LiveRepricerPeriodRequest = DEFAULT_REPRICER_PERIOD_DAYS,
  sources?: string[],
) {
  void periodInput
  void sources
  const payload = await apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/run', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({
      scenario: 'complete',
      mode: 'onboarding',
      force: true,
    }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

export async function startLiveRepricerColdFullSync(
  accessToken: string,
  signal?: AbortSignal,
) {
  const payload = await apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/run', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({
      scenario: 'complete',
      mode: 'onboarding',
      force: true,
    }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

export async function retryLiveRepricerSyncStep(
  accessToken: string,
  source: 'stocks' | 'baskets',
  signal?: AbortSignal,
) {
  const payload = await apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/retry-step', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({
      source,
      scenario: 'complete',
    }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

export async function loadLiveRepricerStrategies(accessToken: string, signal?: AbortSignal, force = false) {
  const now = Date.now()
  if (!force && liveStrategiesCache && now - liveStrategiesCachedAt <= LIVE_PRODUCTS_CACHE_TTL_MS) {
    return liveStrategiesCache
  }
  if (!force && liveStrategiesInFlight) {
    return liveStrategiesInFlight
  }

  liveStrategiesInFlight = apiRequest<LiveRepricerStrategyCatalogResponse>('/api/v1/wb-repricer/strategies/catalog', {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  }).then((payload) => {
    const items = Array.isArray(payload?.items) ? payload.items : []
    liveStrategiesCache = items
    liveStrategiesCachedAt = Date.now()
    return items
  }).finally(() => {
    liveStrategiesInFlight = null
  })

  if (signal?.aborted) throw new DOMException('Request aborted', 'AbortError')
  return liveStrategiesInFlight
}

export async function loadLiveRepricerSkuGroups(accessToken: string, signal?: AbortSignal) {
  const payload = await apiRequest<LiveRepricerSkuGroupsResponse>('/api/v1/wb-repricer/sku-groups', {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
  return Array.isArray(payload?.items) ? payload.items : []
}

export async function upsertLiveRepricerSkuGroup(
  accessToken: string,
  payload: {
    groupId?: string | null
    groupName?: string | null
    articleIds: string[]
    planOrders?: number | null
    mode?: 'add' | 'replace'
  },
  signal?: AbortSignal,
) {
  return apiRequest<LiveRepricerSkuGroup>('/api/v1/wb-repricer/sku-groups', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify(payload),
    signal,
    cache: 'no-store',
  })
}

export type LiveRepricerExecutionSkuResult = {
  articleId: string
  status: 'executed' | 'skipped' | 'blocked' | 'failed'
  skipReason?: string | null
  explanation?: string | null
  oldPriceKopecks?: number | null
  recommendedPriceKopecks?: number | null
  deltaKopecks?: number | null
  blockedReasons?: string[]
  draftId?: string | null
  jobId?: string | null
  applyState?: string | null
}

export type LiveRepricerExecutionReport = {
  runId: string
  executedCount: number
  skippedCount: number
  blockedCount: number
  items: LiveRepricerExecutionSkuResult[]
}

export type LiveRepricerStrategyApplyResponse = {
  strategy: { id: string; name: string; typedStrategyId?: string | null }
  assignedCount: number
  unassignedCount?: number
  items: Array<{ articleId: string; strategyId: string; strategyName: string }>
  execution?: LiveRepricerExecutionReport
}

export type LiveWbPromotion = {
  id: string
  name: string
  type: 'auto' | 'flash' | 'special' | string
  status: 'active' | 'upcoming' | 'ended' | string
  startDate?: string | null
  endDate?: string | null
  daysUntilEnd?: number | null
  daysUntilStart?: number | null
  eligibleSkuCount?: number | null
  participatingSkuCount?: number | null
  participationPct?: number | null
  excelLoaded?: boolean
  excelStatus?: 'missing' | 'partial' | 'loaded' | 'error' | 'parsed' | string
  excelFileName?: string | null
  excelLoadedAt?: string | null
  thresholdRowsParsed?: number | null
  thresholdRowsTotal?: number | null
  excelErrorText?: string | null
}

export type LivePromotionsBulkUploadResult = {
  matched: Array<{ filename: string; promotionId: string; promotionName?: string; rowsParsed: number; status: string; errorText?: string | null }>
  unmatched: Array<{ filename: string; normalizedFilename: string; rowsParsed: number }>
  errors: Array<{ filename: string; promotionId: string; promotionName?: string; rowsParsed: number; status: string; errorText?: string | null }>
  matchedCount: number
  unmatchedCount: number
  errorCount: number
}

export type LiveRepricerNomenclatureUploadResult = {
  source: string
  filename: string
  fileHash: string
  rowsTotal: number
  rowsParsed: number
  appliedCount: number
  unmatchedCount: number
  errorCount: number
  importedAt: string
  applied: Array<{ articleId: string; nmId?: number | null; strategyId?: string | null; settings?: Record<string, unknown>; strategyApplied?: boolean }>
  unmatched: Array<Record<string, unknown>>
  errors: Array<Record<string, unknown>>
}

export async function downloadLiveRepricerNomenclatureXlsx(accessToken: string, signal?: AbortSignal) {
  const response = await fetch(buildApiUrl('/api/v1/wb-repricer/sku/export-xlsx'), {
    method: 'GET',
    headers: {
      ...authorizationHeaders(accessToken),
      Accept: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    },
    credentials: 'include',
    cache: 'no-store',
    signal,
  })
  if (!response.ok) {
    let message = response.statusText || `Request failed: ${response.status}`
    try {
      const payload = await response.clone().json() as { detail?: string | { message?: string; code?: string }; error?: { message?: string } }
      if (payload.error?.message) message = payload.error.message
      else if (typeof payload.detail === 'string') message = payload.detail
      else if (payload.detail && typeof payload.detail === 'object') message = payload.detail.message || payload.detail.code || message
    } catch {
      // Binary endpoint errors are still surfaced by status text when the body is not JSON.
    }
    throw new ApiError(message, response.status)
  }
  return {
    blob: await response.blob(),
    filename: filenameFromContentDisposition(response.headers.get('content-disposition')) || `REPRICER_WB_NOMENCLATURE_${new Date().toISOString().slice(0, 10)}.xlsx`,
  }
}

function filenameFromContentDisposition(value: string | null) {
  if (!value) return null
  const utfMatch = /filename\*=UTF-8''([^;]+)/i.exec(value)
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].replace(/"/g, ''))
  const match = /filename="?([^";]+)"?/i.exec(value)
  return match?.[1] ?? null
}

export async function uploadLiveRepricerNomenclatureXlsx(accessToken: string, file: File, signal?: AbortSignal) {
  const body = new FormData()
  body.append('file', file)
  const payload = await apiRequest<LiveRepricerNomenclatureUploadResult>('/api/v1/wb-repricer/sku/import-xlsx', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body,
    signal,
    cache: 'no-store',
  })
  if (!payload) throw new ApiError('Empty repricer nomenclature upload response', 204)
  resetLiveRepricerParityCache()
  resetLiveRepricerStrategiesCache()
  return payload
}

export async function applyLiveRepricerStrategy(
  accessToken: string,
  articleIds: string[],
  strategyName: string,
  signal?: AbortSignal,
  executeAfterAssign = true,
  config?: Record<string, unknown> | null,
) {
  const payload = await apiRequest<LiveRepricerStrategyApplyResponse>('/api/v1/wb-repricer/strategy-assignments/bulk', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({ articleIds, strategyName, executeAfterAssign, config }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  resetLiveRepricerStrategiesCache()
  return payload
}

export async function loadLiveWbPromotions(accessToken: string, signal?: AbortSignal) {
  const payload = await apiRequest<LiveWbPromotion[]>('/api/v1/wb-repricer/promotions', {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
  return Array.isArray(payload) ? payload : []
}

export async function uploadLiveWbPromotionExcel(accessToken: string, promotionId: string, file: File, signal?: AbortSignal) {
  const body = new FormData()
  body.append('file', file)
  const payload = await apiRequest<LiveWbPromotion>(`/api/v1/wb-repricer/promotions/${promotionId}/upload-excel`, {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body,
    signal,
    cache: 'no-store',
  })
  if (!payload) throw new ApiError('Empty promotions upload response', 204)
  return payload
}

export async function uploadLiveWbPromotionsExcelBulk(accessToken: string, files: File[], signal?: AbortSignal) {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))
  const payload = await apiRequest<LivePromotionsBulkUploadResult>('/api/v1/wb-repricer/promotions/upload-excel', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body,
    signal,
    cache: 'no-store',
  })
  if (!payload) throw new ApiError('Empty promotions bulk upload response', 204)
  return payload
}

export async function previewLiveRepricerStrategies(
  accessToken: string,
  articleIds: string[],
  signal?: AbortSignal,
  force = false,
) {
  return apiRequest<LiveRepricerExecutionReport>('/api/v1/wb-repricer/strategies/preview', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({ articleIds, scenario: 'complete', force }),
    signal,
    cache: 'no-store',
  })
}

export async function executeLiveRepricerStrategies(
  accessToken: string,
  articleIds: string[],
  signal?: AbortSignal,
  options?: {
    applyPrices?: boolean
    simulateLocalPrice?: boolean
    force?: boolean
  },
) {
  const payload = await apiRequest<LiveRepricerExecutionReport>('/api/v1/wb-repricer/strategies/execute', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({
      articleIds,
      scenario: 'complete',
      createDrafts: true,
      autoApprove: true,
      applyPrices: options?.applyPrices ?? true,
      simulateLocalPrice: options?.simulateLocalPrice ?? false,
      force: options?.force ?? false,
    }),
    signal,
    cache: 'no-store',
  })
  resetLiveRepricerParityCache()
  return payload
}

type LiveRepricerSourceRefreshResult = {
  source: string
  count: number
  requestedNmIds?: number
  matchedNmIds?: number
  cachedGoodsNmIds?: number
  matchedCachedGoodsNmIds?: number
  partial?: boolean
  warning?: string
}

const refreshSourceInFlight = new Map<string, Promise<LiveRepricerSourceRefreshResult | null>>()

export async function refreshLiveRepricerSource(
  accessToken: string,
  source: 'content' | 'promotions' | 'stocks' | 'period-stats' | 'finance' | 'ads' | 'baskets',
  signal?: AbortSignal,
  periodInput: number | LiveRepricerPeriodRequest = DEFAULT_REPRICER_PERIOD_DAYS,
) {
  const period = normalizeLiveRepricerPeriod(periodInput)
  const periodParams = new URLSearchParams()
  appendLiveRepricerPeriodParams(periodParams, period)
  const refreshPeriodParams = new URLSearchParams()
  refreshPeriodParams.set('period_days', String(period.periodDays))
  if (period.dateFrom) refreshPeriodParams.set('dateFrom', period.dateFrom)
  if (period.dateTo) refreshPeriodParams.set('dateTo', period.dateTo)
  const flightKey = `${source}:${periodParams.toString()}`
  const existing = refreshSourceInFlight.get(flightKey)
  if (existing) return existing

  const endpoint = source === 'content'
    ? '/api/v1/wb-repricer/sku/refresh-content'
    : source === 'promotions'
      ? '/api/v1/wb-repricer/sku/refresh-promotions'
      : source === 'stocks'
      ? '/api/v1/wb-repricer/sku/refresh-stocks'
      : source === 'period-stats'
        ? `/api/v1/wb-repricer/sku/refresh-period-stats?${refreshPeriodParams.toString()}`
        : source === 'baskets'
          ? `/api/v1/wb-repricer/sku/refresh-baskets?${refreshPeriodParams.toString()}`
          : source === 'ads'
            ? `/api/v1/wb-repricer/sku/refresh-ads?${refreshPeriodParams.toString()}`
            : `/api/v1/wb-repricer/sku/refresh-finance?${refreshPeriodParams.toString()}`
  const request = apiRequest<LiveRepricerSourceRefreshResult>(endpoint, {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  }).then((payload) => {
    resetLiveRepricerParityCache()
    return payload
  }).finally(() => {
    refreshSourceInFlight.delete(flightKey)
  })

  refreshSourceInFlight.set(flightKey, request)
  return request
}
export type LiveRepricerPeriodRequest = {
  periodDays?: number
  dateFrom?: string
  dateTo?: string
}

export type LiveBasketsDetailStatus = {
  runId: string
  state: 'queued' | 'running' | 'completed' | 'failed'
  cached: boolean
  dateFrom: string
  dateTo: string
  periodDays: number
  requestsCompleted: number
  requestsTotal: number
  progressPercent: number
  updatedAt: string
  phase?: string | null
  day?: string | null
  dayIndex?: number | null
  daysTotal?: number | null
  batch?: number | null
  batchesTotal?: number | null
  error?: string | null
  failedChunks?: Array<{ date?: string | null; chunkIndex?: number | null; error?: string | null }>
  warning?: string | null
  finishedAt?: string | null
}

export async function startLiveBasketsDetail(
  accessToken: string,
  range: Pick<LiveRepricerPeriodRequest, 'dateFrom' | 'dateTo'> & { force?: boolean },
  signal?: AbortSignal,
) {
  const payload = await apiRequest<LiveBasketsDetailStatus>('/api/v1/wb-repricer/baskets/detail/start', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
    body: JSON.stringify({ dateFrom: range.dateFrom, dateTo: range.dateTo, scenario: 'complete', force: Boolean(range.force) }),
    signal,
    cache: 'no-store',
  })
  if (!payload) throw new ApiError('Empty baskets detail start response', 204)
  return payload
}

export async function loadLiveBasketsDetailStatus(accessToken: string, runId: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ runId })
  const payload = await apiRequest<LiveBasketsDetailStatus>(`/api/v1/wb-repricer/baskets/detail/status?${params.toString()}`, {
    headers: authorizationHeaders(accessToken),
    signal,
    cache: 'no-store',
  })
  if (!payload) throw new ApiError('Empty baskets detail status response', 204)
  return payload
}

function normalizeLiveRepricerPeriod(period: number | LiveRepricerPeriodRequest = DEFAULT_REPRICER_PERIOD_DAYS): Required<LiveRepricerPeriodRequest> {
  const input = typeof period === 'number' ? { periodDays: period } : period
  const periodDays = input.periodDays ?? DEFAULT_REPRICER_PERIOD_DAYS
  if (input.dateFrom && input.dateTo) {
    return { periodDays, dateFrom: input.dateFrom, dateTo: input.dateTo }
  }
  // A preset carries only a length.  Resolving it here - against the last day
  // WB has closed - keeps the request off today, which has no closed figures
  // and made every preset come back empty.
  const preset = resolvePresetPeriodRange(periodDays)
  return {
    periodDays,
    dateFrom: input.dateFrom || preset.dateFrom,
    dateTo: input.dateTo || preset.dateTo,
  }
}

function appendLiveRepricerPeriodParams(params: URLSearchParams, period: LiveRepricerPeriodRequest) {
  params.set('periodDays', String(period.periodDays ?? DEFAULT_REPRICER_PERIOD_DAYS))
  if (period.dateFrom) params.set('dateFrom', period.dateFrom)
  if (period.dateTo) params.set('dateTo', period.dateTo)
}
