import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { apiRequest } from './api'
import { clearStoredAccessToken, readStoredAccessToken, storeAccessToken } from './authTokenStore'

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiRequest auth refresh', () => {
  beforeEach(() => {
    clearStoredAccessToken({ notify: false })
  })

  afterEach(() => {
    vi.restoreAllMocks()
    clearStoredAccessToken({ notify: false })
  })

  it('refreshes expired access token and retries original request', async () => {
    storeAccessToken('old-access', { notify: false })
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const path = new URL(url, 'http://localhost').pathname
      if (path === '/api/v1/auth/refresh') {
        return jsonResponse({
          data: { accessToken: 'new-access', expiresIn: 900, tokenType: 'bearer' },
          timestamp: '2026-06-15T00:00:00Z',
        })
      }
      if (path === '/api/example' && fetchMock.mock.calls.length === 1) {
        expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer old-access')
        return jsonResponse({ detail: 'INVALID_AUTH_TOKEN:TOKEN_EXPIRED' }, 401)
      }
      expect(path).toBe('/api/example')
      expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer new-access')
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest<{ ok: boolean }>('/api/example', {
      headers: { Authorization: 'Bearer old-access' },
    })).resolves.toEqual({ ok: true })

    expect(readStoredAccessToken()).toBe('new-access')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('does not refresh or clear auth for non-auth 401 responses', async () => {
    storeAccessToken('old-access', { notify: false })
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname
      expect(path).toBe('/api/wb-upstream')
      return jsonResponse({ detail: 'WB token is invalid' }, 401)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/api/wb-upstream', {
      headers: { Authorization: 'Bearer old-access' },
    })).rejects.toMatchObject({ status: 401, message: 'WB token is invalid' })

    expect(readStoredAccessToken()).toBe('old-access')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('clears the current access token when refresh cookie is terminally rejected', async () => {
    storeAccessToken('old-access', { notify: false })
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = new URL(String(input), 'http://localhost').pathname
      if (path === '/api/v1/auth/refresh') {
        return jsonResponse({ detail: 'REFRESH_TOKEN_REQUIRED' }, 401)
      }
      return jsonResponse({ detail: 'INVALID_AUTH_TOKEN:TOKEN_EXPIRED' }, 401)
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/api/example', {
      headers: { Authorization: 'Bearer old-access' },
    })).rejects.toMatchObject({ status: 401, message: 'INVALID_AUTH_TOKEN:TOKEN_EXPIRED' })

    expect(readStoredAccessToken()).toBeNull()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('deduplicates parallel access token refreshes', async () => {
    storeAccessToken('old-access', { notify: false })
    let refreshCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = new URL(String(input), 'http://localhost').pathname
      const authorization = new Headers(init?.headers).get('Authorization')

      if (path === '/api/v1/auth/refresh') {
        refreshCalls += 1
        await new Promise((resolve) => setTimeout(resolve, 10))
        return jsonResponse({
          data: { accessToken: 'new-access', expiresIn: 900, tokenType: 'bearer' },
          timestamp: '2026-06-15T00:00:00Z',
        })
      }

      if (authorization === 'Bearer old-access') {
        return jsonResponse({ detail: 'INVALID_AUTH_TOKEN:TOKEN_EXPIRED' }, 401)
      }

      expect(authorization).toBe('Bearer new-access')
      return jsonResponse({ ok: true, path })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(Promise.all([
      apiRequest<{ ok: boolean }>('/api/example-a', { headers: { Authorization: 'Bearer old-access' } }),
      apiRequest<{ ok: boolean }>('/api/example-b', { headers: { Authorization: 'Bearer old-access' } }),
    ])).resolves.toEqual([{ ok: true, path: '/api/example-a' }, { ok: true, path: '/api/example-b' }])

    expect(refreshCalls).toBe(1)
    expect(readStoredAccessToken()).toBe('new-access')
  })

  it('rejects a successful HTML response instead of treating it as empty JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<!doctype html><title>SPA fallback</title>', {
      status: 200,
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    })))

    await expect(apiRequest('/api/v2/wb/reports/abc-pnl')).rejects.toMatchObject({
      status: 502,
      code: 'INVALID_API_RESPONSE',
    })
  })

  it('accepts JSON-compatible media types and empty successful responses', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/problem+json; charset=utf-8' },
      }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiRequest('/api/problem-json')).resolves.toEqual({ ok: true })
    await expect(apiRequest('/api/no-content')).resolves.toBeNull()
  })
})
