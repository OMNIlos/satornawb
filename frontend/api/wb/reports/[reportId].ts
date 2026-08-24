import { getPnlReport, getReportById, normalizeDateRange } from '../../../src/features/wb-reports/repository.js'
import type { DatePreset, ReportGroupBy, ReportId } from '../../../src/features/wb-reports/types.js'

const REPORT_IDS = new Set<ReportId>(['abc', 'rnp', 'pnl', 'expenses', 'ads', 'stock', 'week-over-week'])

type QueryValue = string | string[] | undefined
type RequestLike = {
  query?: {
    reportId?: QueryValue
    preset?: QueryValue
    datePreset?: QueryValue
    from?: QueryValue
    to?: QueryValue
    groupBy?: QueryValue
    source?: QueryValue
  }
}
type ResponseLike = {
  status: (code: number) => { json: (data: unknown) => void }
}

function first(value: QueryValue): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default function handler(request: RequestLike, response: ResponseLike) {
  const reportId = first(request.query?.reportId) as ReportId | undefined
  if (!reportId || !REPORT_IDS.has(reportId)) {
    response.status(404).json({
      error: {
        code: 'REPORT_NOT_FOUND',
        message: `WB report "${reportId ?? 'unknown'}" is not available`,
      },
    })
    return
  }

  const dateRange = normalizeDateRange({
    preset: (first(request.query?.preset) ?? first(request.query?.datePreset) ?? '7d') as DatePreset,
    from: first(request.query?.from),
    to: first(request.query?.to),
  })

  if (reportId === 'pnl') {
    const source = first(request.query?.source) === 'financial' ? 'financial' : 'operational'
    response.status(200).json(getPnlReport(dateRange, source))
    return
  }

  response.status(200).json(getReportById(reportId, dateRange, (first(request.query?.groupBy) ?? 'sku') as ReportGroupBy))
}
