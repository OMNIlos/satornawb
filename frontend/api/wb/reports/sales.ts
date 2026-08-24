import { getAbcReport, normalizeDateRange } from '../../../src/features/wb-reports/repository.js'
import type { DatePreset, ReportGroupBy } from '../../../src/features/wb-reports/types.js'

export default function handler(
  request: { query?: { datePreset?: string; groupBy?: string } },
  response: { status: (code: number) => { json: (data: unknown) => void } },
) {
  const datePreset = (request.query?.datePreset ?? '7d') as DatePreset
  const groupBy = (request.query?.groupBy ?? 'sku') as ReportGroupBy
  response.status(200).json(getAbcReport(normalizeDateRange({ preset: datePreset }), groupBy))
}
