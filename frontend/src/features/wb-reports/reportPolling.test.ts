import { describe, expect, it } from 'vitest'
import { retainReadyReportWhileRefreshing } from './reportPolling'

describe('report polling state', () => {
  it('keeps already rendered report data visible during a background refresh', () => {
    const readyState = { status: 'ready' as const, report: { rows: [{ sku: 'REAL_SKU' }] } }

    expect(retainReadyReportWhileRefreshing(readyState)).toBe(readyState)
  })

  it('shows loading before the first report response', () => {
    expect(retainReadyReportWhileRefreshing({ status: 'loading' as const })).toEqual({ status: 'loading' })
    expect(retainReadyReportWhileRefreshing({ status: 'error' as const, message: 'retry' })).toEqual({ status: 'loading' })
  })
})
