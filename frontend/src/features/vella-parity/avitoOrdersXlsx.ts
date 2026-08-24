import { authorizationHeaders } from '@/features/auth/authApi'
import { buildApiUrl } from '@/lib/api'

export type AvitoOrdersPickingXlsxOptions = {
  dateFrom: string
  periodDays: number
  status?: string
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
  const todayIso = new Date().toISOString().slice(0, 10)
  const fallback = new Date(Date.now() - (Math.max(1, options.periodDays) - 1) * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  const normalizedDateFrom = /^\d{4}-\d{2}-\d{2}$/.test(options.dateFrom) && options.dateFrom <= todayIso ? options.dateFrom : fallback
  const params = new URLSearchParams({
    dateFrom: normalizedDateFrom,
    periodDays: String(options.periodDays),
  })
  if (options.status && options.status !== 'all') params.set('status', options.status)
  return `/api/v1/avito/orders/picking-list.xlsx?${params.toString()}`
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
    ?? `avito-picking-list-${options.dateFrom}.xlsx`
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
