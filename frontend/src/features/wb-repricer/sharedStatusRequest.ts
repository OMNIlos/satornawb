type Fetcher<T> = () => Promise<T>

type Entry = {
  at: number
  value: Promise<unknown>
}

const entries = new Map<string, Entry>()

/**
 * Collapse repeated status polls onto one request.
 *
 * Several components poll worker/status and sync/status on their own timers,
 * so a repricer page issued ~18 worker/status calls per minute.  Each one is a
 * round trip to the API, and together they saturated the browser's connection
 * pool - the products request queued behind them, which is why loading felt
 * slow and why switching period "worked every other time": the in-flight
 * products request was aborted by the next poll before it resolved.
 *
 * Callers within `ttlMs` of a previous call share its promise instead of
 * issuing another request.
 */
export function sharedStatusRequest<T>(key: string, ttlMs: number, fetcher: Fetcher<T>): Promise<T> {
  const now = Date.now()
  const existing = entries.get(key)
  if (existing && now - existing.at < ttlMs) {
    return existing.value as Promise<T>
  }
  const value = fetcher().catch((error) => {
    // A failed poll must not be cached, or one blip freezes the widget for the
    // whole TTL.
    if (entries.get(key)?.value === value) entries.delete(key)
    throw error
  })
  entries.set(key, { at: now, value })
  return value as Promise<T>
}

export function resetSharedStatusRequests() {
  entries.clear()
}
