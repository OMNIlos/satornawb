import { describe, expect, it } from 'vitest'
import { makeServerProductsPeriodLabel } from './serverPeriodLabel'

describe('makeServerProductsPeriodLabel', () => {
  it('labels the window the backend actually answered for', () => {
    // Preset "7 дней" clicked on 19.08: the backend anchors on the last closed
    // WB day, so the numbers cover 12.08-18.08, not 13.08-сегодня.
    expect(makeServerProductsPeriodLabel('2026-08-12', '2026-08-18', '2026-08-19')).toBe('с 12.08 по 18.08 · 7 дн')
  })

  it('still says сегодня when the window really does reach today', () => {
    expect(makeServerProductsPeriodLabel('2026-08-13', '2026-08-19', '2026-08-19')).toBe('с 13.08 по сегодня · 7 дн')
  })

  it('collapses a single day', () => {
    expect(makeServerProductsPeriodLabel('2026-08-18', '2026-08-18', '2026-08-19')).toBe('18.08')
    expect(makeServerProductsPeriodLabel('2026-08-19', '2026-08-19', '2026-08-19')).toBe('сегодня')
  })

  it('returns null when the backend did not report a range', () => {
    expect(makeServerProductsPeriodLabel(undefined, undefined, '2026-08-19')).toBeNull()
    expect(makeServerProductsPeriodLabel('2026-08-12', undefined, '2026-08-19')).toBeNull()
  })
})
