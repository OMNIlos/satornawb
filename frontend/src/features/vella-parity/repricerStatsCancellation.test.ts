import { afterEach, expect, it, vi } from 'vitest'
import { installRepricerStatsLiveBridge } from './VellaHtmlParityPage'

afterEach(() => vi.unstubAllGlobals())

it.each(['reload', 'dispose', 'later-page'] as const)('cancels obsolete statistics transport on %s', async action => {
  vi.stubGlobal('window', {
    __vellaReportPeriods: { 'repricer-stats': { days: 7, mode: 'custom', fromIso: '2026-09-01', toIso: '2026-09-07' } },
  })
  vi.stubGlobal('document', { getElementById: () => null, querySelector: () => null })
  const pending: { signal: AbortSignal | null | undefined; finish: () => void }[] = []
  vi.stubGlobal('fetch', vi.fn((_path: string, init?: RequestInit) => new Promise<Response>((resolve, reject) => {
    const index = pending.length
    pending.push({ signal: init?.signal, finish: () => resolve(new Response(JSON.stringify({
      items: [], total: action === 'later-page' && index === 0 ? 501 : 0,
      page: index + 1, pageSize: 500,
    }), { headers: { 'content-type': 'application/json' } })) })
    init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
  })))
  const dispose = installRepricerStatsLiveBridge('synthetic-cancellation')
  const load = window.__vellaLoadLiveRepricerStats!
  const promises = [load()]
  try {
    expect(pending).toHaveLength(1)
    if (action === 'later-page') {
      pending[0]!.finish()
      await vi.waitFor(() => expect(pending).toHaveLength(2))
    }
    const obsolete = pending.at(-1)!
    if (action === 'reload') promises.push(load())
    else dispose()
    expect(obsolete.signal?.aborted).toBe(true)
    if (action === 'reload') expect(pending[1]!.signal?.aborted).toBe(false)
    else {
      expect(await load()).toBeNull()
      expect(window.__vellaLoadLiveRepricerStats).toBeUndefined()
    }
  } finally {
    dispose()
    pending.forEach(request => request.finish())
    await Promise.allSettled(promises)
  }
})
