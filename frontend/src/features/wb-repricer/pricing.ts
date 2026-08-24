// P_min = (COGS + logistics) / (1 - commission% - minMargin%) — подтверждено Марией 24.04.2026.
// Все значения в копейках (кроме процентов).
export function computePMinKopecks(
  cogsKopecks: number,
  commissionPct: number,
  logisticsKopecks: number,
  minMarginPct: number,
): number {
  const denom = 1 - (commissionPct + minMarginPct) / 100
  if (denom <= 0) return Number.POSITIVE_INFINITY
  return Math.ceil((cogsKopecks + logisticsKopecks) / denom)
}

export type MarginStatus = 'negative' | 'thin' | 'ok'

export function marginStatusAt(
  priceKopecks: number,
  cogsKopecks: number,
  commissionPct: number,
  logisticsKopecks: number,
): MarginStatus {
  const net = priceKopecks * (1 - commissionPct / 100) - logisticsKopecks - cogsKopecks
  const pct = (net / priceKopecks) * 100
  if (pct < 0) return 'negative'
  if (pct < 10) return 'thin'
  return 'ok'
}
