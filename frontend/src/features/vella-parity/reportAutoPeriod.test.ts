import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import ts from 'typescript'
import { describe, expect, it, vi } from 'vitest'

const source = readFileSync(new URL('./VellaHtmlParityPage.tsx', import.meta.url), 'utf8')
const compile = (text: string) => ts.transpileModule(text, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText

describe('automatic report period and refresh', () => {
  it.each(['from', 'to'])('applies the %s calendar boundary without an Apply/Update click', boundary => {
    const start = source.indexOf('  const commitCustomPeriod = ')
    const end = source.indexOf('\n  if (isAvitoTab)', start)
    const applied = vi.fn()
    const context = {
      customFromIso: '2026-09-09', customToIso: '2026-09-16', calendarBoundary: boundary,
      activeReportPeriodKey: 'abc', coverageLoading: false,
      setProductsPeriod: vi.fn(), setCustomFromIso: vi.fn(), setCustomToIso: vi.fn(),
      setCalendarBoundary: vi.fn(), setCalendarMonthIso: vi.fn(), setCalendarOpen: vi.fn(),
      productsPeriodDaysFromRange: (fromIso: string, toIso: string) => ({ days: 7, fromIso, toIso }),
      createProductsPeriodState: (_days: number, _mode: string, fromIso: string, toIso: string) => ({ fromIso, toIso }),
      applyAllWbReportPeriodStates: applied, monthStartIso: (x: string) => x,
      window: { showToast: vi.fn() }, document: { getElementById: () => null },
    }
    const choose = runInNewContext(`${compile(source.slice(start, end))}; chooseCoverageDate`, context)
    choose(boundary === 'from' ? '2026-09-01' : '2026-09-07', true)
    expect(applied).toHaveBeenCalledOnce()
    expect(applied).toHaveBeenCalledWith(boundary === 'from'
      ? { fromIso: '2026-09-01', toIso: '2026-09-16' }
      : { fromIso: '2026-09-07', toIso: '2026-09-07' })
  })

  it.each([false, undefined, true])('does not pin a partial ABC preview in memory (fresh=%s)', fresh => {
    const start = source.indexOf('function cacheAbcReport(')
    const end = source.indexOf('\nexport function installAbcLiveDataBridge', start)
    const memory = new Map([['period', { cachedAt: Date.now() }]])
    const store = runInNewContext(`${compile(source.slice(start, end))}; cacheAbcReport`, {
      abcReportMemoryCache: memory, ABC_REPORT_MEMORY_TTL_MS: 300_000, Date,
    })
    store('period', { cache: { fresh } }, [])
    expect(memory.has('period')).toBe(fresh === true)
  })

  it('publishes an immediately ready cached refresh and avoids forced recollection', async () => {
    const start = source.indexOf('  async function startRefresh()')
    const end = source.indexOf('\n  return (', start)
    const completed = vi.fn(), setJob = vi.fn(), request = vi.fn(async (_url: string, _options: object) => ({ state: 'completed' }))
    const run = runInNewContext(`${compile(source.slice(start, end))}; startRefresh`, {
      accessToken: 'synthetic', running: false, reportId: 'abc', period: {}, groupBy: 'sku', source: 'operational',
      backgroundReportJobStartPath: () => '/jobs', authorizationHeaders: () => ({}),
      apiRequest: request, describePnlReportJob: (x: unknown) => x, setJob, onCompleted: completed, ApiError: Error,
      refreshRequestRef: { current: null }, AbortController,
    })
    await run()
    expect(request.mock.calls[0][0]).toBe('/jobs')
    expect(completed).toHaveBeenCalledOnce()
    expect(setJob).toHaveBeenCalledWith({ state: 'completed' })
  })

  it('ignores a late refresh response after switching periods', async () => {
    const start = source.indexOf('  async function startRefresh()')
    const end = source.indexOf('\n  return (', start)
    const completed = vi.fn(), setJob = vi.fn()
    let finish!: (value: object) => void
    const response = new Promise(resolve => { finish = resolve })
    const ref = { current: null as AbortController | null }
    const run = runInNewContext(`${compile(source.slice(start, end))}; startRefresh`, {
      accessToken: 'synthetic', running: false, reportId: 'abc', period: {}, groupBy: 'sku', source: 'operational',
      backgroundReportJobStartPath: () => '/jobs', authorizationHeaders: () => ({}),
      apiRequest: () => response, describePnlReportJob: (x: unknown) => x,
      setJob, onCompleted: completed, ApiError: Error, refreshRequestRef: ref, AbortController,
    })
    const pending = run()
    ref.current?.abort()
    ref.current = null
    finish({ state: 'completed' })
    await pending
    expect(setJob).not.toHaveBeenCalled()
    expect(completed).not.toHaveBeenCalled()
  })
})
