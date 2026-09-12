import { afterEach, beforeEach, expect, test, vi } from 'vitest'

type Kind = 'products' | 'strategies' | 'sync' | 'refresh'

beforeEach(() => vi.resetModules())
afterEach(() => vi.unstubAllGlobals())

async function loader(kind: Kind) {
  const api = await import('./liveParityData')
  return {
    products: (token: string) => api.loadLiveRepricerParityProducts(token),
    strategies: (token: string) => api.loadLiveRepricerStrategies(token),
    sync: (token: string) => api.loadLiveRepricerSyncStatus(token),
    refresh: (token: string) => api.refreshLiveRepricerSource(token, 'stocks'),
  }[kind]
}

function response(kind: Kind, owner: number) {
  const payload = kind === 'products'
    ? { items: [], total: owner, cache: { totalCached: owner } }
    : kind === 'strategies'
      ? { items: [{ id: String(owner), name: `Synthetic ${owner}` }] }
      : { state: 'completed', source: 'stocks', count: owner, runId: String(owner) }
  return new Response(JSON.stringify(payload), { headers: { 'content-type': 'application/json' } })
}

test.each<Kind>(['products', 'strategies', 'sync'])('%s cache cannot serve another access token', async (kind) => {
  const load = await loader(kind)
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(response(kind, 1))
    .mockResolvedValueOnce(response(kind, 2))
  vi.stubGlobal('fetch', fetchMock)
  const first = await load('synthetic-account-a')
  expect(await load('synthetic-account-a')).toEqual(first)
  const second = await load('synthetic-account-b')
  expect(second).not.toEqual(first)
  expect(await load('synthetic-account-b')).toEqual(second)
  expect(fetchMock).toHaveBeenCalledTimes(2)
})

test.each<Kind>(['products', 'strategies', 'sync', 'refresh'])('%s isolates concurrent sessions without losing same-session deduplication', async (kind) => {
  const load = await loader(kind)
  const pending: Array<() => void> = []
  const fetchMock = vi.fn((_url: unknown, init: RequestInit) => new Promise<Response>(resolve => {
    const owner = new Headers(init.headers).get('Authorization') === 'Bearer synthetic-account-a' ? 1 : 2
    pending.push(() => resolve(response(kind, owner)))
  }))
  vi.stubGlobal('fetch', fetchMock)
  const first = load('synthetic-account-a')
  const firstAgain = load('synthetic-account-a')
  const second = load('synthetic-account-b')
  const calls = [first, firstAgain, second]
  try {
    expect(fetchMock).toHaveBeenCalledTimes(2)
    pending[0]()
    const firstResult = await first
    const secondAgain = load('synthetic-account-b')
    calls.push(secondAgain)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    pending[1]()
    const secondResult = await second
    expect(secondResult).not.toEqual(firstResult)
    expect(await firstAgain).toEqual(firstResult)
    expect(await secondAgain).toEqual(secondResult)
  } finally {
    pending.forEach(resolve => resolve())
    await Promise.allSettled(calls)
  }
})

test.each([
  ['products', 'refresh', false], ['products', 'refresh', true],
  ['products', 'parity', false], ['products', 'parity', true],
  ['products', 'strategy', false], ['products', 'strategy', true],
  ['strategies', 'strategy', false], ['strategies', 'strategy', true],
] as const)('late A %s/%s completion preserves B cache (ready=%s)', async (kind, mutation, ready) => {
  const load = await loader(kind)
  const api = await import('./liveParityData')
  const pending: Array<() => void> = []
  const fetchMock = vi.fn((_url: unknown, init: RequestInit) => {
    if (init.method !== 'POST' && new Headers(init.headers).get('Authorization') === 'Bearer synthetic-account-a') {
      return Promise.resolve(response(kind, 1))
    }
    return new Promise<Response>(resolve => {
      pending.push(() => resolve(response(init.method === 'POST' ? 'refresh' : kind, 2)))
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  const change = mutation === 'refresh'
    ? api.refreshLiveRepricerSource('synthetic-account-a', 'stocks')
    : mutation === 'parity'
      ? api.refreshLiveRepricerParityProducts('synthetic-account-a', 0)
      : api.applyLiveRepricerStrategy('synthetic-account-a', [], 'synthetic', undefined, false)
  const second = load('synthetic-account-b')
  const calls = [change, second]
  try {
    if (ready) {
      pending[1]()
      await second
    }
    pending[0]()
    await change
    const secondAgain = load('synthetic-account-b')
    calls.push(secondAgain)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    pending[1]()
    expect(await secondAgain).toEqual(await second)
    expect(await load('synthetic-account-b')).toEqual(await second)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  } finally {
    pending.forEach(resolve => resolve())
    await Promise.allSettled(calls)
  }
})

test.each(['products', 'strategies'] as const)('%s reset invalidates its own session and rejects late publication', async (kind) => {
  const load = await loader(kind)
  const api = await import('./liveParityData')
  const reset = kind === 'products' ? api.resetLiveRepricerParityCache : api.resetLiveRepricerStrategiesCache
  const fetchMock = vi.fn(() => Promise.resolve(response(kind, 1)))
  vi.stubGlobal('fetch', fetchMock)
  await load('synthetic-account-a')
  reset('synthetic-account-a')
  const pending = load('synthetic-account-a')
  reset('synthetic-account-a')
  await pending
  await load('synthetic-account-a')
  expect(fetchMock).toHaveBeenCalledTimes(3)
  reset()
  await load('synthetic-account-a')
  expect(fetchMock).toHaveBeenCalledTimes(4)
})
