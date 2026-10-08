import { afterEach, expect, it, vi } from 'vitest'
import { apiRequest } from '@/lib/api'
import { loadLatestReportCache } from './VellaHtmlParityPage'

vi.mock('@/lib/api', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api')>(), apiRequest: vi.fn() }))
afterEach(() => { vi.mocked(apiRequest).mockReset(); vi.unstubAllGlobals() })
const period = { fromIso: '2026-09-01', toIso: '2026-09-07' }

it('publishes saved data first and refreshes stale sources without clearing rows', async () => {
  vi.stubGlobal('document', { getElementById: () => null })
  const saved = { rows: [{ value: 1 }], cache: { fresh: false } }
  const latest = { rows: [{ value: 2 }], cache: { fresh: true } }
  vi.mocked(apiRequest).mockResolvedValueOnce(saved).mockResolvedValueOnce({ state: 'completed' }).mockResolvedValueOnce(latest)
  const onCached = vi.fn()
  const onJob = vi.fn()
  expect(await loadLatestReportCache('rnp', 'rnp', 'synthetic', 'sku', period, 'operational', { onCached, onJob })).toEqual(latest)
  expect(onCached).toHaveBeenCalledWith(saved)
  expect(onJob).not.toHaveBeenCalled() // Loading state must not hide the cached table.
  expect(apiRequest).toHaveBeenCalledTimes(3)
})

it('retains saved data when refresh fails and never retries automatically', async () => {
  vi.stubGlobal('document', { getElementById: () => null })
  const saved = { rows: [{ value: 1 }], cache: { fresh: false } }
  vi.mocked(apiRequest).mockResolvedValueOnce(saved).mockRejectedValueOnce(new Error('HTTP 429'))
  expect(await loadLatestReportCache('rnp', 'rnp', 'synthetic', 'sku', period)).toEqual(saved)
  expect(apiRequest).toHaveBeenCalledTimes(2)
})

it('does not start a collection for a fresh cache', async () => {
  vi.stubGlobal('document', { getElementById: () => null })
  const saved = { cache: { fresh: true } }
  vi.mocked(apiRequest).mockResolvedValueOnce(saved)
  expect(await loadLatestReportCache('rnp', 'rnp', 'synthetic', 'sku', period)).toEqual(saved)
  expect(apiRequest).toHaveBeenCalledTimes(1)
})

it('discards a late cache response after the selected period was cancelled', async () => {
  const controller = new AbortController()
  const onCached = vi.fn()
  vi.mocked(apiRequest).mockImplementationOnce(async () => {
    controller.abort()
    return { rows: [{ value: 1 }], cache: { fresh: false } }
  })
  await expect(loadLatestReportCache('rnp', 'rnp', 'synthetic', 'sku', period, 'operational', {
    signal: controller.signal, onCached,
  })).rejects.toMatchObject({ name: 'AbortError' })
  expect(onCached).not.toHaveBeenCalled()
  expect(apiRequest).toHaveBeenCalledTimes(1)
})

it('does not replace the selected dates with a report from a different period', async () => {
  const onCached = vi.fn()
  vi.mocked(apiRequest).mockResolvedValueOnce({ dateRange: { from: '2026-08-01', to: '2026-08-31' }, cache: { fresh: true } })
  await expect(loadLatestReportCache('rnp', 'rnp', 'synthetic', 'sku', period, 'operational', { onCached }))
    .rejects.toMatchObject({ status: 409 })
  expect(onCached).not.toHaveBeenCalled()
  expect(apiRequest).toHaveBeenCalledTimes(1)
})
