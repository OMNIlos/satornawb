import { afterEach, expect, test, vi } from 'vitest'
import { missingPeriodSources, preparePeriod } from './preparePeriod'

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals() })
test('only missing exact-period sources are requested', () => {
  expect(missingPeriodSources({ financeFetchedAt: 'now', periodStatsFetchedAt: 'now', basketsCoverageState: 'no_data' })).toEqual(['baskets'])
  expect(missingPeriodSources({ financeFetchedAt: 'now', periodStatsFetchedAt: 'now', basketsFetchedAt: 'now', basketsCoverageState: 'ok' })).toEqual([])
})
test('uses selected dates without onboarding or force; waits for its run', async () => {
  vi.useFakeTimers()
  const response = (data: unknown) => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } })
  const fetch = vi.fn().mockResolvedValueOnce(response({ runId: 'r', running: true }))
    .mockResolvedValueOnce(response({ runId: 'r', running: false, state: 'completed' }))
  vi.stubGlobal('fetch', fetch)
  const result = preparePeriod('fake', { dateFrom: '2026-09-01', dateTo: '2026-09-04', periodDays: 4 }, ['baskets'], () => true)
  await vi.advanceTimersByTimeAsync(3000)
  expect(await result).toBe(true)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ dateFrom: '2026-09-01', dateTo: '2026-09-04', periodDays: 4, sources: ['baskets'], mode: 'manual', force: false })
})
test('a superseded view never starts another request', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  expect(await preparePeriod('fake', { periodDays: 7 }, ['finance'], () => false)).toBe(false)
  expect(fetch).not.toHaveBeenCalled()
})

test.each(['partial', 'failed'])('does not claim success for %s data', async state => {
  vi.useFakeTimers()
  const response = (data: unknown) => new Response(JSON.stringify(data), { headers: { 'content-type': 'application/json' } })
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response({ runId: 'r', running: true }))
    .mockResolvedValueOnce(response({ runId: 'r', running: false, state })))
  const assertion = expect(preparePeriod('fake', { periodDays: 3 }, ['finance'], () => true)).rejects.toThrow('неполные данные')
  await vi.advanceTimersByTimeAsync(3000)
  await assertion
})

test('does not apply completion after the user changes the period', async () => {
  vi.useFakeTimers()
  let current = true
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ runId: 'r', running: true }), { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch)
  const result = preparePeriod('fake', { periodDays: 3 }, ['finance'], () => current)
  await vi.advanceTimersByTimeAsync(1)
  current = false
  await vi.advanceTimersByTimeAsync(3000)
  expect(await result).toBe(false)
  expect(fetch).toHaveBeenCalledTimes(1)
})
