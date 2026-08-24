import { getRnpReport, normalizeDateRange } from '../../../src/features/wb-reports/repository.js'
import type { DatePreset } from '../../../src/features/wb-reports/types.js'

export default function handler(
  request: { query?: { datePreset?: string } },
  response: { status: (code: number) => { json: (data: unknown) => void } },
) {
  const datePreset = (request.query?.datePreset ?? '7d') as DatePreset
  response.status(200).json(getRnpReport(normalizeDateRange({ preset: datePreset })))
}
