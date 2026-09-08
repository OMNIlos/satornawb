import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const source = readFileSync(fileURLToPath(new URL('./VellaHtmlParityPage.tsx', import.meta.url)), 'utf8')

function functionSource(name: string) {
  const start = source.indexOf(`function ${name}`)
  const next = source.indexOf('\nfunction ', start + 10)
  return source.slice(start, next < 0 ? source.length : next)
}

describe('canonical ABC/P&L cutover wiring', () => {
  it('keeps legacy ABC as rollback and selects canonical by explicit rollout', () => {
    const bridge = functionSource('installAbcLiveDataBridge')
    expect(bridge).toContain('canonicalRollout')
    expect(bridge).toContain('fetchCanonicalAbcPnl')
    expect(bridge).toContain("loadLatestReportCache<AbcBackendReport>('abc'")
  })

  it('selects canonical only for financial P&L and keeps operational P&L unchanged', () => {
    const island = functionSource('PnlReportActiveIsland')
    expect(island).toContain('canonicalRollout')
    expect(island).toContain('fetchCanonicalAbcPnl')
    expect(island).toContain("shouldUseCanonicalAbcPnl(canonicalRollout, 'pnl', pnlMode)")
    expect(island).toContain("loadLatestReportCache<PnlBackendReport>('pnl'")
  })

  it('uses preliminary labels and never aliases canonical profit to final net profit', () => {
    expect(source).toContain('Прибыль после лояльности')
    expect(source).toContain('profitAfterLoyaltyKopecks')
    expect(source).toContain("abc: isCanonical ? (row.salesClass ? `${row.salesClass}·—` : '—')")
  })
})
