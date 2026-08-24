export type MetricWithDelta = {
  value: number
  deltaPct: number | null
  direction: 'up' | 'down' | 'flat' | 'unknown'
}

export type RepricerStatsRow = {
  id: string
  sku: string
  nmId: string
  title: string
  imageUrl: string | null
  managerId: string | null
  managerLabel: string | null
  impressions: MetricWithDelta
  clicks: MetricWithDelta
  carts: MetricWithDelta
  orders: MetricWithDelta
  conversionRatePct: MetricWithDelta
  adSpendKopecks: MetricWithDelta
  medianPriceKopecks: MetricWithDelta
  priceProtectionStatus: 'can_recalculate' | 'price_blocked' | 'needs_review'
  sourceStatus: 'ready' | 'source_not_ready' | 'stale' | 'error'
  flags: Array<'cart_growth' | 'cart_drop' | 'oos_risk' | 'promo' | 'ads'>
}
