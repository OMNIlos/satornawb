import { getDigestReport, normalizeDateRange } from '../../../src/features/wb-reports/repository.js'
import type { DatePreset } from '../../../src/features/wb-reports/types.js'

type QueryValue = string | string[] | undefined
type RequestLike = {
  query?: {
    preset?: QueryValue
    datePreset?: QueryValue
    from?: QueryValue
    to?: QueryValue
  }
}

function first(value: QueryValue): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default function handler(request: RequestLike, response: { status: (code: number) => { json: (data: unknown) => void } }) {
  const dateRange = normalizeDateRange({
    preset: (first(request.query?.preset) ?? first(request.query?.datePreset) ?? '7d') as DatePreset,
    from: first(request.query?.from),
    to: first(request.query?.to),
  })
  response.status(200).json(getDigestReport(dateRange))
}
