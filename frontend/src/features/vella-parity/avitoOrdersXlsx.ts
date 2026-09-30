import { authorizationHeaders } from '@/features/auth/authApi'
import { buildApiUrl } from '@/lib/api'

export type AvitoOrdersPickingXlsxOptions = {
  accountId?: string
  kind?: 'picking' | 'returns'
}

type DownloadLink = {
  href: string
  download: string
  click: () => void
  remove?: () => void
}

type DownloadDeps = {
  createObjectUrl?: (blob: Blob) => string
  revokeObjectUrl?: (url: string) => void
  createLink?: () => DownloadLink
}

function filenameFromContentDisposition(value: string | null) {
  if (!value) return null
  const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].replace(/"/g, ''))
  const asciiMatch = value.match(/filename="?([^";]+)"?/i)
  return asciiMatch?.[1] ?? null
}

function buildPickingListPath(options: AvitoOrdersPickingXlsxOptions) {
  const path = options.kind === 'returns' ? 'returns-list.xlsx' : 'picking-list.xlsx'
  const params = new URLSearchParams()
  if (options.accountId) params.set('accountId', options.accountId)
  return `/api/v1/avito/orders/${path}${params.size ? `?${params.toString()}` : ''}`
}

export async function downloadAvitoOrdersPickingXlsx(
  accessToken: string,
  options: AvitoOrdersPickingXlsxOptions,
  deps: DownloadDeps = {},
) {
  const path = buildPickingListPath(options)
  const response = await fetch(buildApiUrl(path), {
    headers: authorizationHeaders(accessToken),
    credentials: 'include',
  })
  if (!response.ok) {
    throw new Error(`Не удалось скачать лист подбора Авито: ${response.status}`)
  }

  const blob = await response.blob()
  const filename = filenameFromContentDisposition(response.headers.get('content-disposition'))
    ?? `avito-${options.kind === 'returns' ? 'returns' : 'picking'}-list.xlsx`
  const createObjectUrl = deps.createObjectUrl ?? URL.createObjectURL.bind(URL)
  const revokeObjectUrl = deps.revokeObjectUrl ?? URL.revokeObjectURL.bind(URL)
  const createLink = deps.createLink ?? (() => document.createElement('a'))
  const url = createObjectUrl(blob)
  const link = createLink()
  link.href = url
  link.download = filename
  link.click()
  link.remove?.()
  revokeObjectUrl(url)
  return filename
}
