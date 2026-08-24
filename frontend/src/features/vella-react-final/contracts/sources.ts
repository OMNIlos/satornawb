export type SourceStatus =
  | 'not_connected'
  | 'checking_connection'
  | 'synced'
  | 'error'
  | 'mapping_required'
  | 'stale'
  | 'draft'

export type SourceRow = {
  id: string
  name: string
  sourceType: 'one_c' | 'wb_api' | 'excel_fallback' | 'manual' | 'derived'
  pulls: string[]
  periodLabel: string
  lastSyncAt: string | null
  status: SourceStatus
  qualityLabel: string
  dependentSurfaces: Array<'pnl' | 'rnp' | 'abc' | 'repricer' | 'ads' | 'plans' | 'expenses'>
  ownerUserId: string | null
  ownerLabel: string
  action: 'connect' | 'map' | 'review' | 'open_report' | 'upload'
}
