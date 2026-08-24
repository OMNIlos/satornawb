import { describe, expect, it } from 'vitest'
import { lastClosedWbDay, resolvePresetPeriodRange } from './presetPeriodAnchor'

describe('preset period anchoring', () => {
  it('ends the window on the last closed WB day, not today', () => {
    // WB closes analytical windows at the end of the previous day.  Asking for
    // a range ending today returns an empty period, which is why every preset
    // button rendered zeros while an explicit range showed real numbers.
    const now = new Date('2026-08-24T07:00:00Z')
    expect(lastClosedWbDay(now)).toBe('2026-08-23')
  })

  it('keeps the requested number of days', () => {
    const now = new Date('2026-08-24T07:00:00Z')
    expect(resolvePresetPeriodRange(7, now)).toEqual({ dateFrom: '2026-08-17', dateTo: '2026-08-23' })
    expect(resolvePresetPeriodRange(1, now)).toEqual({ dateFrom: '2026-08-23', dateTo: '2026-08-23' })
    expect(resolvePresetPeriodRange(30, now)).toEqual({ dateFrom: '2026-07-25', dateTo: '2026-08-23' })
  })

  it('crosses month and year boundaries correctly', () => {
    expect(resolvePresetPeriodRange(7, new Date('2026-01-03T05:00:00Z')))
      .toEqual({ dateFrom: '2025-12-27', dateTo: '2026-01-02' })
  })

  it('uses UTC so the window matches the backend cache keys', () => {
    // 00:30 Moscow on the 24th is still the 23rd in UTC.
    expect(lastClosedWbDay(new Date('2026-08-23T21:30:00Z'))).toBe('2026-08-22')
  })
})
