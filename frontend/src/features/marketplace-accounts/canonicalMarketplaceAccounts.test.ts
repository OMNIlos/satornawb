import { describe, expect, it, vi } from 'vitest'
import { parseCanonicalMarketplaceAccounts, readCanonicalMarketplaceAccounts } from './canonicalMarketplaceAccounts'
const accounts = [{ marketplaceAccountId: 11, provider: 'wb', externalAccountId: '00011', displayName: null, status: 'disconnected' },
  { marketplaceAccountId: 12, provider: 'avito', externalAccountId: 'actual-avito', displayName: 'Synthetic Avito', status: 'active' }]
const json = (data: unknown) => new Response(JSON.stringify({ data }), { headers: { 'Content-Type': 'application/json' } })
describe('shared canonical marketplace metadata boundary', () => {
  it('discovers both providers through shared API, preserving status but granting no actions', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json(accounts))
    expect(await readCanonicalMarketplaceAccounts('synthetic', new AbortController().signal, undefined, fetcher)).toEqual(accounts)
    expect(fetcher.mock.calls[0][0]).toBe('/api/v2/cabinet/marketplace-accounts')
    expect(fetcher.mock.calls[0][1]).toMatchObject({ cache: 'no-store', credentials: 'omit', redirect: 'error' })
  })
  it('validates optional provider filter against response and does not invent or alias provider', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json([accounts[0]]))
    await expect(readCanonicalMarketplaceAccounts('synthetic', new AbortController().signal, 'avito', fetcher)).rejects.toThrow()
    expect(fetcher.mock.calls[0][0]).toBe('/api/v2/cabinet/marketplace-accounts?provider=avito')
    expect(() => parseCanonicalMarketplaceAccounts([{ ...accounts[0], provider: 'Avito' }])).toThrow()
  })
  it.each([[accounts[0], accounts[0]], [{ ...accounts[0], marketplaceAccountId: '11' }], [{ ...accounts[0], credentialRef: 'forbidden' }], { data: [] }])('rejects malformed, duplicate or secret-bearing account metadata', value => {
    expect(() => parseCanonicalMarketplaceAccounts(value)).toThrow()
  })
  it('cancels old identity reads even if transport returns late; a fresh provider list remains separate', async () => {
    let finish!: (response: Response) => void
    const fetcher = vi.fn<typeof fetch>().mockImplementationOnce(() => new Promise(resolve => { finish = resolve })).mockResolvedValueOnce(json([accounts[1]]))
    const controller = new AbortController(), old = readCanonicalMarketplaceAccounts('old-synthetic', controller.signal, undefined, fetcher)
    controller.abort()
    expect(await readCanonicalMarketplaceAccounts('new-synthetic', new AbortController().signal, undefined, fetcher)).toEqual([accounts[1]])
    finish(json(accounts)); await expect(old).rejects.toMatchObject({ name: 'AbortError' })
  })
  it('accepts an authoritative changed-provider response without carrying a client-invented provider forward', () => {
    expect(parseCanonicalMarketplaceAccounts([{ ...accounts[0], provider: 'avito' }])[0].provider).toBe('avito')
  })
  it('bounds response and never falls back after unavailable discovery', async () => {
    for (const response of [json({ oversized: 'x'.repeat(1_048_577) }), new Response('', { status: 503 })]) {
      const fetcher = vi.fn<typeof fetch>().mockResolvedValue(response)
      await expect(readCanonicalMarketplaceAccounts('synthetic', new AbortController().signal, undefined, fetcher)).rejects.toThrow()
      expect(fetcher).toHaveBeenCalledOnce()
    }
  })
})
