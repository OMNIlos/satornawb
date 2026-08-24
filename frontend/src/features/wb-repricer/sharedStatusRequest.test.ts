import { beforeEach, describe, expect, it, vi } from 'vitest'
import { resetSharedStatusRequests, sharedStatusRequest } from './sharedStatusRequest'

describe('sharedStatusRequest', () => {
  beforeEach(() => resetSharedStatusRequests())

  it('collapses concurrent polls onto one request', async () => {
    const fetcher = vi.fn().mockResolvedValue({ ok: true })

    const [a, b, c] = await Promise.all([
      sharedStatusRequest('worker', 10_000, fetcher),
      sharedStatusRequest('worker', 10_000, fetcher),
      sharedStatusRequest('worker', 10_000, fetcher),
    ])

    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(a).toEqual({ ok: true })
    expect(b).toBe(a)
    expect(c).toBe(a)
  })

  it('keeps separate keys independent', async () => {
    const worker = vi.fn().mockResolvedValue('w')
    const sync = vi.fn().mockResolvedValue('s')

    await Promise.all([
      sharedStatusRequest('worker', 10_000, worker),
      sharedStatusRequest('sync', 10_000, sync),
    ])

    expect(worker).toHaveBeenCalledTimes(1)
    expect(sync).toHaveBeenCalledTimes(1)
  })

  it('refetches once the ttl has passed', async () => {
    vi.useFakeTimers()
    try {
      const fetcher = vi.fn().mockResolvedValue(1)
      await sharedStatusRequest('worker', 5_000, fetcher)
      vi.setSystemTime(Date.now() + 6_000)
      await sharedStatusRequest('worker', 5_000, fetcher)
      expect(fetcher).toHaveBeenCalledTimes(2)
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not cache a failure', async () => {
    const fetcher = vi.fn()
      .mockRejectedValueOnce(new Error('boom'))
      .mockResolvedValueOnce('recovered')

    await expect(sharedStatusRequest('worker', 10_000, fetcher)).rejects.toThrow('boom')
    await expect(sharedStatusRequest('worker', 10_000, fetcher)).resolves.toBe('recovered')
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
