import { afterEach, expect, it, vi } from 'vitest'
import { syncProductsPeriod } from './productsSourceSync'
import { syncStatsSources } from './statsSourceSync'
import { resetLiveRepricerParityCache } from './liveParityData'

vi.mock('./statsSourceSync', async original => ({ ...await original<typeof import('./statsSourceSync')>(), syncStatsSources: vi.fn() }))
vi.mock('./liveParityData', () => ({ resetLiveRepricerParityCache: vi.fn() }))
afterEach(() => vi.resetAllMocks())
const period = { dateFrom: '2026-09-01', dateTo: '2026-09-07' }

it('uses the managed period job and reads the saved final batch even for a reused job', async () => {
  vi.mocked(syncStatsSources).mockImplementation(async (_token, _from, _to, _signal, progress) => {
    await progress({ state: 'running' })
    await progress({ state: 'completed', reused: true })
    return { state: 'completed' }
  })
  const read = vi.fn().mockResolvedValue(undefined)
  const status = vi.fn()
  await syncProductsPeriod('synthetic', period, new AbortController().signal, () => true, read, status)
  expect(syncStatsSources).toHaveBeenCalledTimes(1)
  expect(read).toHaveBeenCalledTimes(1)
  expect(resetLiveRepricerParityCache).toHaveBeenCalledWith('synthetic')
  expect(status.mock.calls.map(([job]) => job.state)).toEqual(['running', 'completed'])
})

it('never publishes an old period after navigation or cancellation', async () => {
  let current = true
  vi.mocked(syncStatsSources).mockImplementation(async (_token, _from, _to, _signal, progress) => {
    current = false
    await progress({ state: 'completed' })
    return { state: 'completed' }
  })
  const read = vi.fn()
  const status = vi.fn()
  await syncProductsPeriod('synthetic', period, new AbortController().signal, () => current, read, status)
  expect(read).not.toHaveBeenCalled()
  expect(status).not.toHaveBeenCalled()
  const controller = new AbortController(); controller.abort()
  await syncProductsPeriod('synthetic', period, controller.signal, () => true, read)
  expect(syncStatsSources).toHaveBeenCalledTimes(1)
})

it('propagates a provider failure without a repeat or clearing saved rows', async () => {
  vi.mocked(syncStatsSources).mockRejectedValue(new Error('WB HTTP 429'))
  const read = vi.fn()
  await expect(syncProductsPeriod('synthetic', period, new AbortController().signal, () => true, read)).rejects.toThrow('429')
  expect(syncStatsSources).toHaveBeenCalledTimes(1)
  expect(read).not.toHaveBeenCalled()
})
