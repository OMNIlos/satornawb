import { describe, expect, it } from 'vitest'
import type { ThresholdProfile } from './types'
import {
  abcLetterByRank,
  canRunPriceMutation,
  classifyBand,
  createThresholdPreview,
  FIXED_ABC_SHARE,
  isFixedAbcShare,
  validateThresholdShare,
  type ThresholdPreviewInputRow,
} from './thresholds'

const standardProfile: ThresholdProfile = {
  id: 'thr-standard',
  name: 'Стандартный профиль',
  preset: 'standard',
  version: 3,
  status: 'active',
  updatedAt: '2026-05-08T08:55:00+05:00',
  updatedBy: { id: 'user-maria', name: 'Мария', role: 'owner' },
  abc: {
    salesShare: { aPct: 20, bPct: 30, cPct: 50 },
    netProfitShare: { aPct: 20, bPct: 30, cPct: 50 },
  },
  qualityBands: {
    ctrPct: { goodMin: 10, averageMin: 6 },
    crPct: { goodMin: 4, averageMin: 2 },
    cartToOrderPct: { goodMin: 45, averageMin: 25 },
    buyoutPct: { goodMin: 80, averageMin: 60 },
    marginPct: { goodMin: 25, thinMin: 10, lossBelow: 0 },
    drrPct: { goodMax: 9, warnMin: 14 },
    roiPct: { goodMin: 250, warnBelow: 100 },
    daysToOos: { warnBelow: 7 },
    stockUnits: { criticalBelow: 12 },
    localizationPct: { badBelow: 60 },
  },
  automationMapping: {
    aaGood: 'raise_price',
    badCr: 'rnp',
    loss: 'liquidation',
    highDrr: 'stop_ads',
    oos: 'alert',
    cWeak: 'audit',
  },
}

const aggressiveProfile: ThresholdProfile = {
  ...standardProfile,
  id: 'thr-aggressive',
  name: 'Агрессивный профиль',
  preset: 'aggressive',
  version: 1,
  status: 'draft',
  abc: {
    salesShare: { aPct: 25, bPct: 35, cPct: 40 },
    netProfitShare: { aPct: 25, bPct: 35, cPct: 40 },
  },
  qualityBands: {
    ...standardProfile.qualityBands,
    crPct: { goodMin: 3.2, averageMin: 1.5 },
    marginPct: { goodMin: 20, thinMin: 7, lossBelow: -3 },
    drrPct: { goodMax: 11, warnMin: 18 },
    roiPct: { goodMin: 180, warnBelow: 70 },
    daysToOos: { warnBelow: 5 },
    stockUnits: { criticalBelow: 8 },
  },
}

const previewRows: ThresholdPreviewInputRow[] = [
  { sku: 'FBBT_42', salesRankPct: 22, netProfitRankPct: 22, marginPct: 22, crPct: 3.4, drrPct: 9, roiPct: 140, daysToOos: 30, stockUnits: 70 },
  { sku: 'HCBT_29', salesRankPct: 61, netProfitRankPct: 64, marginPct: -1, crPct: 1.8, drrPct: 20, roiPct: 55, daysToOos: 18, stockUnits: 42 },
]

describe('report thresholds', () => {
  it('validates that ABC shares add up to 100%', () => {
    expect(validateThresholdShare({ aPct: 20, bPct: 30, cPct: 50 })).toBe(true)
    expect(validateThresholdShare({ aPct: 25, bPct: 30, cPct: 50 })).toBe(false)
  })

  it('classifies boundary values into the expected bands', () => {
    expect(classifyBand(10, { goodMin: 10, averageMin: 6 })).toBe('good')
    expect(classifyBand(6, { goodMin: 10, averageMin: 6 })).toBe('average')
    expect(classifyBand(14, { goodMax: 9, warnMin: 14 })).toBe('bad')
    expect(classifyBand(7, { warnBelow: 7 })).toBe('bad')
  })

  it('calculates ABC letters independently for sales and net profit axes', () => {
    expect(FIXED_ABC_SHARE).toEqual({ aPct: 20, bPct: 30, cPct: 50 })
    expect(isFixedAbcShare(standardProfile.abc.salesShare)).toBe(true)
    expect(abcLetterByRank(20, standardProfile.abc.salesShare)).toBe('A')
    expect(abcLetterByRank(50, standardProfile.abc.salesShare)).toBe('B')
    expect(abcLetterByRank(51, standardProfile.abc.netProfitShare)).toBe('C')
  })

  it('builds a dry-run diff when a preset changes thresholds', () => {
    const preview = createThresholdPreview(previewRows, standardProfile, aggressiveProfile)

    expect(preview.affectedSkuCount).toBeGreaterThan(0)
    expect(preview.abcChanges).toBeGreaterThan(0)
    expect(preview.sampleRows[0]?.sku).toBe('FBBT_42')
    expect(preview.warnings[0]).toContain('не запускает')
  })

  it('keeps price mutation hard guards above threshold automation', () => {
    expect(canRunPriceMutation({ belowPMin: true, priceStepExceeded: false, dailyPriceLimitExceeded: false })).toBe(false)
    expect(canRunPriceMutation({ belowPMin: false, priceStepExceeded: true, dailyPriceLimitExceeded: false })).toBe(false)
    expect(canRunPriceMutation({ belowPMin: false, priceStepExceeded: false, dailyPriceLimitExceeded: false })).toBe(true)
  })
})
