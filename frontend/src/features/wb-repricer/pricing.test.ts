import { describe, expect, test } from 'vitest'
import { computePMinKopecks, marginStatusAt } from './pricing'

describe('computePMinKopecks', () => {
  test('COGS 450₽ + commission 25% + logistics 50₽ + margin 15% → P_min ≈ 834₽', () => {
    // (45000 + 5000) / (1 - 0.40) = 50000 / 0.60 = 83333.33 → ceil 83334
    expect(computePMinKopecks(45000, 25, 5000, 15)).toBe(83334)
  })

  test('когда commission + margin >= 100% → Infinity (невозможно)', () => {
    expect(computePMinKopecks(45000, 60, 5000, 50)).toBe(Number.POSITIVE_INFINITY)
  })

  test('нулевая логистика работает', () => {
    // 45000 / (1 - 0.30) = 45000 / 0.70 = 64285.71 → 64286
    expect(computePMinKopecks(45000, 15, 0, 15)).toBe(64286)
  })
})

describe('marginStatusAt', () => {
  test('цена ниже P_min → negative', () => {
    expect(marginStatusAt(50000, 45000, 25, 5000)).toBe('negative')
  })

  test('цена немного выше P_min → thin (< 10%)', () => {
    // price 85000, net = 85000*0.75 - 5000 - 45000 = 63750 - 50000 = 13750. pct = 16.2% ≈ ok
    // need less: price 75000 → 75000*0.75 - 50000 = 56250 - 50000 = 6250. pct = 8.3% → thin
    expect(marginStatusAt(75000, 45000, 25, 5000)).toBe('thin')
  })

  test('цена заметно выше P_min → ok', () => {
    expect(marginStatusAt(129000, 45000, 25, 5000)).toBe('ok')
  })
})
