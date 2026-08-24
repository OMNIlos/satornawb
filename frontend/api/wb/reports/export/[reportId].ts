import { getExportForRole } from '../../../../src/features/wb-reports/repository.js'
import type { ReportId } from '../../../../src/features/wb-reports/types.js'

const EXPORTABLE_REPORT_IDS = new Set<ReportId>(['digest', 'abc', 'rnp', 'pnl', 'expenses', 'ads', 'stock', 'week-over-week'])

type QueryValue = string | string[] | undefined
type RequestLike = { query?: { reportId?: QueryValue; role?: QueryValue } }
type ResponseLike = { status: (code: number) => { json: (data: unknown) => void } }

function first(value: QueryValue): string | undefined {
  return Array.isArray(value) ? value[0] : value
}

export default function handler(request: RequestLike, response: ResponseLike) {
  const reportId = first(request.query?.reportId) as ReportId | undefined
  if (!reportId) {
    response.status(404).json({
      error: {
        code: 'REPORT_EXPORT_NOT_FOUND',
        message: 'Report export id is required',
      },
    })
    return
  }

  if (!EXPORTABLE_REPORT_IDS.has(reportId)) {
    response.status(501).json({
      error: {
        code: 'REPORT_EXPORT_UNSUPPORTED',
        message: `Export for WB report "${reportId}" is not supported`,
      },
    })
    return
  }

  const exportInfo = getExportForRole(reportId, first(request.query?.role) ?? 'admin')
  if (!exportInfo.exportAllowed) {
    response.status(403).json({
      error: {
        code: 'REPORT_EXPORT_FORBIDDEN',
        message: exportInfo.blockedReason,
      },
      export: exportInfo,
    })
    return
  }

  response.status(200).json(exportInfo)
}
