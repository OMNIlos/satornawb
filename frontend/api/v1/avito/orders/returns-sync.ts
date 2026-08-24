type HeaderValue = string | string[] | undefined

declare const process: {
  env: Record<string, string | undefined>
}

type RequestLike = {
  method?: string
  headers?: Record<string, HeaderValue>
}

type ResponseLike = {
  setHeader?: (name: string, value: string) => void
  status: (code: number) => {
    json?: (data: unknown) => void
    send?: (data: unknown) => void
    end?: () => void
  }
}

function headerValue(value: HeaderValue): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

function apiBaseUrl() {
  return String(process.env.VITE_API_BASE_URL || process.env.VELLA_API_BASE_URL || '').replace(/\/$/, '')
}

function send(response: ResponseLike, status: number, payload: unknown) {
  const target = response.status(status)
  if (target.json) {
    target.json(payload)
    return
  }
  if (target.send) {
    target.send(JSON.stringify(payload))
    return
  }
  target.end?.()
}

export default async function handler(request: RequestLike, response: ResponseLike) {
  response.setHeader?.('Access-Control-Allow-Origin', '*')
  response.setHeader?.('Access-Control-Allow-Methods', 'GET, OPTIONS')
  response.setHeader?.('Access-Control-Allow-Headers', 'Authorization, Content-Type')
  if (request.method === 'OPTIONS') {
    send(response, 204, null)
    return
  }
  if (request.method !== 'GET') {
    send(response, 405, { error: { code: 'METHOD_NOT_ALLOWED', message: 'Use GET' } })
    return
  }
  const baseUrl = apiBaseUrl()
  if (!baseUrl) {
    send(response, 502, {
      error: {
        code: 'API_BASE_URL_NOT_CONFIGURED',
        message: 'Frontend proxy cannot find VITE_API_BASE_URL or VELLA_API_BASE_URL',
      },
    })
    return
  }
  const authorization = headerValue(request.headers?.authorization || request.headers?.Authorization)
  const upstream = await fetch(`${baseUrl}/api/v1/avito/orders/returns-sync`, {
    method: 'GET',
    headers: authorization ? { Authorization: authorization } : {},
  })
  const text = await upstream.text()
  try {
    send(response, upstream.status, text ? JSON.parse(text) : {})
  } catch (_error) {
    send(response, upstream.status, text)
  }
}
