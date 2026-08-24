export type PeriodRequestSurface = 'products' | 'abc' | 'rnp' | 'pnl' | 'expenses' | 'ads' | 'stock' | 'week'

export function shouldLoadPeriodSurface(
  activeTab: string | null | undefined,
  surface: PeriodRequestSurface,
) {
  if (activeTab === surface) return true
  if (typeof window === 'undefined') return false

  const pathname = window.location.pathname.replace(/^\/internal\/vella-parity(?=\/|$)/, '').replace(/\/$/, '')
  const tab = new URLSearchParams(window.location.search).get('tab')
  if (tab === surface) return true

  if (surface === 'products') return pathname === '/wb/repricer' || /\/repricer\/sku\/[^/?#]+$/.test(pathname)
  if (surface === 'week') return pathname === '/wb/reports/week' || pathname === '/wb/reports/week-over-week'
  return pathname === `/wb/reports/${surface}`
}
