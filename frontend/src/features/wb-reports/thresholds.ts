import type { AbcCode, AbcLetter, ThresholdBand, ThresholdPreview, ThresholdProfile, ThresholdShare } from './types'

export type ThresholdBandLevel = 'good' | 'average' | 'bad'

export const FIXED_ABC_SHARE: ThresholdShare = { aPct: 20, bPct: 30, cPct: 50 }

export interface ThresholdPreviewInputRow {
  sku: string
  salesRankPct: number
  netProfitRankPct: number
  marginPct: number
  crPct: number
  drrPct: number
  roiPct: number
  daysToOos: number
  stockUnits: number
}

interface ClassifiedThresholdRow {
  abcCode: AbcCode
  status: string
  action: string
  reason: string
}

export interface PriceMutationGuards {
  belowPMin: boolean
  priceStepExceeded: boolean
  dailyPriceLimitExceeded: boolean
}

export function validateThresholdShare(share: ThresholdShare): boolean {
  return Number((share.aPct + share.bPct + share.cPct).toFixed(2)) === 100
}

export function isFixedAbcShare(share: ThresholdShare): boolean {
  return share.aPct === FIXED_ABC_SHARE.aPct && share.bPct === FIXED_ABC_SHARE.bPct && share.cPct === FIXED_ABC_SHARE.cPct
}

export function classifyBand(value: number, band: ThresholdBand): ThresholdBandLevel {
  if (band.goodMax !== undefined && value <= band.goodMax) return 'good'
  if (band.warnMin !== undefined && value >= band.warnMin) return 'bad'
  if (band.goodMin !== undefined && value >= band.goodMin) return 'good'
  if (band.averageMin !== undefined && value >= band.averageMin) return 'average'
  if (band.warnBelow !== undefined && value <= band.warnBelow) return 'bad'
  if (band.criticalBelow !== undefined && value < band.criticalBelow) return 'bad'
  if (band.badBelow !== undefined && value < band.badBelow) return 'bad'
  return 'bad'
}

export function abcLetterByRank(rankPct: number, share: ThresholdShare): AbcLetter {
  if (rankPct <= share.aPct) return 'A'
  if (rankPct <= share.aPct + share.bPct) return 'B'
  return 'C'
}

export function canRunPriceMutation(guards: PriceMutationGuards): boolean {
  return !guards.belowPMin && !guards.priceStepExceeded && !guards.dailyPriceLimitExceeded
}

function classifyThresholdRow(row: ThresholdPreviewInputRow, profile: ThresholdProfile): ClassifiedThresholdRow {
  const salesLetter = abcLetterByRank(row.salesRankPct, profile.abc.salesShare)
  const profitLetter = abcLetterByRank(row.netProfitRankPct, profile.abc.netProfitShare)
  const abcCode = `${salesLetter}${profitLetter}` as AbcCode
  const marginBand = profile.qualityBands.marginPct

  if (row.marginPct < (marginBand.lossBelow ?? 0)) {
    return { abcCode, status: 'loss', action: 'liquidation', reason: 'Маржа ниже loss-порога' }
  }
  if (
    row.drrPct >= (profile.qualityBands.drrPct.warnMin ?? Number.POSITIVE_INFINITY) &&
    row.roiPct < (profile.qualityBands.roiPct.warnBelow ?? Number.NEGATIVE_INFINITY)
  ) {
    return { abcCode, status: 'выше порога ДРР', action: 'stop_ads', reason: 'ДРР выше warn-порога и ROI ниже warn-порога' }
  }
  if (
    row.daysToOos <= (profile.qualityBands.daysToOos.warnBelow ?? 0) ||
    row.stockUnits < (profile.qualityBands.stockUnits.criticalBelow ?? 0)
  ) {
    return { abcCode, status: 'OOS риск', action: 'alert', reason: 'Остаток ниже OOS-порога' }
  }
  if (row.crPct < (profile.qualityBands.crPct.averageMin ?? 0)) {
    return { abcCode, status: 'неликвид', action: 'rnp', reason: 'CR ниже среднего порога' }
  }
  if (abcCode === 'AA' && row.marginPct >= (marginBand.goodMin ?? Number.POSITIVE_INFINITY)) {
    return { abcCode, status: 'локомотив', action: 'raise_price', reason: 'AA и маржа выше good-порога' }
  }
  if (abcCode.includes('C') || row.marginPct < (marginBand.thinMin ?? 0)) {
    return { abcCode, status: 'неликвид', action: 'audit', reason: 'C-класс или тонкая маржа' }
  }
  return { abcCode, status: 'средний', action: 'audit', reason: 'Порогов автоматики не достиг' }
}

export function createThresholdPreview(
  rows: ThresholdPreviewInputRow[],
  oldProfile: ThresholdProfile,
  nextProfile: ThresholdProfile,
): ThresholdPreview {
  let abcChanges = 0
  let statusChanges = 0
  const automationImpact = { rnp: 0, liquidation: 0, alerts: 0, stopAds: 0 }
  const sampleRows: ThresholdPreview['sampleRows'] = []

  rows.forEach((row) => {
    const before = classifyThresholdRow(row, oldProfile)
    const after = classifyThresholdRow(row, nextProfile)
    const changed = before.abcCode !== after.abcCode || before.status !== after.status || before.action !== after.action

    if (before.abcCode !== after.abcCode) abcChanges += 1
    if (before.status !== after.status) statusChanges += 1
    if (after.action === 'rnp') automationImpact.rnp += 1
    if (after.action === 'liquidation') automationImpact.liquidation += 1
    if (after.action === 'alert') automationImpact.alerts += 1
    if (after.action === 'stop_ads') automationImpact.stopAds += 1

    if (changed && sampleRows.length < 20) {
      sampleRows.push({ sku: row.sku, before, after, reason: after.reason })
    }
  })

  return {
    affectedSkuCount: rows.filter((row) => {
      const before = classifyThresholdRow(row, oldProfile)
      const after = classifyThresholdRow(row, nextProfile)
      return before.abcCode !== after.abcCode || before.status !== after.status || before.action !== after.action
    }).length,
    abcChanges,
    statusChanges,
    automationImpact,
    sampleRows,
    warnings: ['Сохранение профиля не запускает мгновенное массовое изменение цен'],
  }
}
