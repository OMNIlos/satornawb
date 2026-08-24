import { getPnlReport, normalizeDateRange } from '../../../src/features/wb-reports/repository.js'
import type { DatePreset } from '../../../src/features/wb-reports/types.js'

type QueryValue = string | string[] | undefined

function first(value: QueryValue): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default function handler(
  request: { query?: { preset?: QueryValue; datePreset?: QueryValue; from?: QueryValue; to?: QueryValue; source?: QueryValue } },
  response: { status: (code: number) => { json: (data: unknown) => void } },
) {
  const datePreset = (first(request.query?.preset) ?? first(request.query?.datePreset) ?? '7d') as DatePreset
  const source = first(request.query?.source) === 'financial' ? 'financial' : 'operational'
  response.status(200).json(getPnlReport(normalizeDateRange({
    preset: datePreset,
    from: first(request.query?.from),
    to: first(request.query?.to),
  }), source))
}
