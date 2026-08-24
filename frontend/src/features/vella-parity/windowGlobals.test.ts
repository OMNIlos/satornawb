import { describe, expect, it } from 'vitest'
import { clearVellaWindowProperty } from './windowGlobals'

describe('Vella window globals', () => {
  it('clears legacy window handlers without throwing on non-configurable properties', () => {
    const target = {}
    Object.defineProperty(target, 'applyAvitoOverviewPeriod', {
      configurable: false,
      value: () => undefined,
      writable: true,
    })

    expect(() => clearVellaWindowProperty(target, 'applyAvitoOverviewPeriod')).not.toThrow()
    expect(target).toHaveProperty('applyAvitoOverviewPeriod')
  })
})
