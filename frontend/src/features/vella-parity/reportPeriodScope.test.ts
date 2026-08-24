import { describe, expect, it } from 'vitest'
import { shouldLoadPeriodSurface } from './reportPeriodScope'

describe('shouldLoadPeriodSurface', () => {
  it('allows only the active report to load a changed period', () => {
    expect(shouldLoadPeriodSurface('pnl', 'pnl')).toBe(true)
    expect(shouldLoadPeriodSurface('pnl', 'rnp')).toBe(false)
    expect(shouldLoadPeriodSurface('pnl', 'ads')).toBe(false)
    expect(shouldLoadPeriodSurface('pnl', 'stock')).toBe(false)
    expect(shouldLoadPeriodSurface('pnl', 'products')).toBe(false)
  })
})
