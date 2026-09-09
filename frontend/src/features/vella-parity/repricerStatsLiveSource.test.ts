import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('./VellaHtmlParityPage.tsx', import.meta.url), 'utf8')
const legacySource = readFileSync(new URL('../wb-repricer/WbRepricerStatsPage.tsx', import.meta.url), 'utf8')

describe('Repricer stats live source', () => {
  it('loads the repricer stats tab from the backend stats endpoint', () => {
    expect(source).toContain('loadLiveRepricerStats')
    expect(source).toContain('window.__vellaLoadLiveRepricerStats')
    // Route-driven loading is exercised by repricerStatsPageBrowser.test.ts.
    expect(source).toContain('renderLiveRepricerStats(payload)')
    expect(source).toContain('repricerStatsBody')
    expect(source).toContain("protectedLiveTabs = new Set(['repricer-stats'")
    expect(source).toContain('REPRICER_STATS_PAGE_SIZE')
    expect(source).toContain('#tab-repricer-stats,')
    expect(source).toContain("type ReportPeriodKey = 'digest' | 'repricer-stats'")
    expect(source).toContain("'repricer-stats', 'report-rules'")
    expect(source).toContain("readReportPeriodState('repricer-stats')")
    // Scoped period events are exercised through the actual React page as well.
    expect(source).toContain('applyRepricerStatsCachePeriod(payload)')
    expect(source).toContain('payload.cache?.statsRangeAdjusted')
    expect(source).toContain("applyReportPeriodState('repricer-stats', next")
    expect(source).toContain('report-decision-reason')
    expect(source).toContain('repricerStatsHasAssignedManager')
    expect(source).not.toContain('report-strategy-cell')
    expect(source).not.toContain('pageSize: 150')
  })

  it('keeps the legacy repricer stats screen off static SKU fixtures', () => {
    expect(legacySource).toContain('loadLiveRepricerStats')
    expect(legacySource).not.toContain('const statsRows')
    expect(legacySource).not.toContain("FBBT_42")
  })
})
