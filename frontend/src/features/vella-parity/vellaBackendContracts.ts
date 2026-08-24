export type VellaSourceStatus =
  | 'confirmed'
  | 'stale'
  | 'partial'
  | 'blocked'
  | 'unknown'
  | 'manual_fallback'
  | 'disabled'

export type VellaFreshness = {
  source: string
  fetchedAt: string | null
  staleAfter: string | null
  isStale: boolean
  confidence: 'high' | 'medium' | 'low' | 'unknown'
}

export type VellaPermissionMatrix = {
  canViewFinance: boolean
  canExportFinance: boolean
  canExportReports: boolean
  canSendPrices: boolean
  canPublishXml: boolean
  canSendMessages: boolean
  canReplyReviews: boolean
  canManagePayments: boolean
  canAdminAccess: boolean
}

export type VellaActionAvailability = {
  enabled: boolean
  disabledReason: string | null
  requiresApproval: boolean
  prepareEndpoint: string | null
  commitEndpoint: string | null
}

export type VellaScreenStates = {
  loading: boolean
  empty: boolean
  error: string | null
  stale: boolean
  partial: boolean
  noAccess: boolean
  requiredFilters: string[]
  emptyReason: 'no_data' | 'required_parameters' | 'no_access' | 'source_blocked' | null
}

export type VellaExportHistoryItem = {
  id: string
  type: 'xlsx'
  status: 'queued' | 'running' | 'ready' | 'failed' | 'expired'
  requestedAt: string
  generatedAt: string | null
  sourceStatus: VellaSourceStatus
  schemaVersion: string | null
}

export type VellaEndpointEnvelope<TData> = {
  data: TData
  sourceStatus: VellaSourceStatus
  freshness: VellaFreshness
  blockerIds: string[]
  permissions: VellaPermissionMatrix
  actions: Record<string, VellaActionAvailability>
  states: VellaScreenStates
  exportHistory: VellaExportHistoryItem[]
}

export type VellaDependencyRef = {
  uiControl: string
  backendField: string
  sourceRef: string
  formulaRef: string | null
  blockerIds: string[]
}

export type ProductsTableRowPayload = {
  sku: string
  nmId: string
  title: string
  category: string
  brand: string
  managerId: string | null
  priceRub: number
  priceMinRub: number
  priceMaxRub: number
  strategyId: string | null
  stockQty: number
  basketsQty: number
  ordersQty: number
  statusFlags: string[]
  selected: boolean
}

export type ProductsTablePayload = {
  rows: ProductsTableRowPayload[]
  rowCount: number
  activeSavedViewId: string | null
  sortKey: string
  filters: Record<string, string | string[] | boolean>
}

export type SecondaryReportKind = 'digest' | 'sales' | 'rnp' | 'pnl' | 'expenses' | 'ads' | 'stock' | 'week' | 'quality'

export type ReportKpiPayload = {
  key: string
  label: string
  value: string
  delta: string | null
  sourceRef: string | null
  formulaRef: string | null
  blockerIds: string[]
}

export type ReportSummaryCardPayload = {
  key: string
  label: string
  value: string
  meta: string | null
  state: 'ok' | 'warning' | 'critical' | 'blocked' | 'info'
  targetRoute: string | null
  actionKey: string | null
  sourceRef: string | null
  formulaRef: string | null
  blockerIds: string[]
}

export type DigestReportPayload = {
  summary: ReportSummaryCardPayload[]
  kpis: ReportKpiPayload[]
  planFactRows: Array<Record<string, string | number | null>>
  actionQueue: QualityQueueIssuePayload[]
  qualityQueue: QualityQueueIssuePayload[]
  chartSeries: Array<Record<string, string | number | null>>
}

export type SalesReportPayload = {
  dateType: 'order_date' | 'sale_date' | 'report_generated_at'
  salesKpis: ReportKpiPayload[]
  chartSeries: Array<Record<string, string | number | null>>
  topMovers: Array<Record<string, string | number | null>>
  rows: Array<Record<string, string | number | null>>
  reportJobs: VellaExportHistoryItem[]
}

export type QualityQueueIssuePayload = {
  id: string
  type: 'hidden_product' | 'card_issue' | 'storage_risk' | 'penalty' | 'kiz_marking' | 'return_join'
  severity: 'critical' | 'warning' | 'info'
  owner: string | null
  sku: string | null
  title: string
  sourceReport: string
  riskRub: number | null
  linkedIdentifiers: Record<string, string | null>
  action: string
  blockerIds: string[]
}

export type SecondaryReportCellPayload = {
  key: string
  value: string
  className: string | null
  sourceRef: string | null
  formulaRef: string | null
}

export type SecondaryReportRowPayload = {
  id: string
  sku: string | null
  report: SecondaryReportKind
  cells: SecondaryReportCellPayload[]
  status: string | null
  confidence: 'high' | 'medium' | 'low' | 'unknown'
  blockerIds: string[]
}

export type SecondaryReportPayload = {
  report: SecondaryReportKind
  rows: SecondaryReportRowPayload[]
  rowCount: number
  filters: Record<string, string | string[] | boolean>
}

export type AdsPerformanceCardPayload = {
  key: string
  label: string
  value: string
  meta: string | null
  state: 'ok' | 'warning' | 'critical' | 'blocked' | 'info'
  detail: string | null
  sourceRef: string | null
  formulaRef: string | null
  blockerIds: string[]
}

export type AdsReportPayload = SecondaryReportPayload & {
  kpis: ReportKpiPayload[]
  balanceSeries: Array<Record<string, string | number | null>>
  performanceCards: AdsPerformanceCardPayload[]
  attribution: {
    exactSkuPct: number | null
    campaignSkuPct: number | null
    campaignOnlyPct: number | null
    confidence: 'high' | 'medium' | 'low' | 'unknown'
  }
}

export type StockManagementCardPayload = {
  key: string
  label: string
  value: string
  chip: string | null
  state: 'ok' | 'warning' | 'critical' | 'blocked' | 'info'
  actionKey: string | null
  sourceRef: string | null
  formulaRef: string | null
  blockerIds: string[]
}

export type StockReportPayload = SecondaryReportPayload & {
  kpis: ReportKpiPayload[]
  managementCards: StockManagementCardPayload[]
  qualityQueue: QualityQueueIssuePayload[]
}

export type PnlDrilldownPayload = {
  key: string
  title: string
  value: string
  meta: string | null
  state: 'ok' | 'warning' | 'critical' | 'blocked' | 'info'
  actionLabel: string | null
  actionKey: string | null
  sourceRef: string | null
  formulaRef: string | null
  blockerIds: string[]
}

export type PnlReportPayload = SecondaryReportPayload & {
  kpis: ReportKpiPayload[]
  opCostAllocation: Array<Record<string, string | number | null>>
  drilldowns: PnlDrilldownPayload[]
}

export type NotificationEventPayload = {
  id: string
  category: string
  severity: 'critical' | 'warning' | 'info' | string
  manager: string | null
  source: string
  freshness: string | null
  timestamp: string
  read: boolean
  active: boolean
  title: string
  body: string
  detail: string | null
  entityId: string | null
  route: string | null
  blockerIds: string[]
}

export type NotificationDetailPayload = {
  eventId: string | null
  blockedActions: string[]
  reportFile: {
    report: string
    fileName: string
    format: string
    period: string
    rows: number
    size: string
    generatedAt: string
  } | null
  routeAction: VellaActionAvailability
}

export type NotificationWorkspacePayload = {
  context: 'all' | 'wb' | 'avito'
  avitoMode: 'events' | 'rules' | 'recipients' | 'channels' | 'history' | 'quiet'
  active: boolean
  title: string
  summary: string
}

export type NotificationsPayload = {
  events: NotificationEventPayload[]
  selected: NotificationDetailPayload
  workspace: NotificationWorkspacePayload
}

export const VELLA_BACKEND_SOURCE_DOC_REFS = {
  wbSourceRegistry: 'docs/handoffs/wb-backend-source-registry.md',
  wbFormulaCatalog: 'docs/handoffs/wb-backend-formula-catalog.md',
  wbReuseDependencyMap: 'docs/handoffs/wb-backend-reuse-dependency-map.md',
  openQuestions: 'docs/open-questions-current.md',
} as const

export const PRODUCTS_BACKEND_DEPENDENCY_MAP: VellaDependencyRef[] = [
  { uiControl: 'products.table.price', backendField: 'rows[].priceRub', sourceRef: 'wbSourceRegistry:prices', formulaRef: 'wbFormulaCatalog:p_min_p_max', blockerIds: ['WB-06', 'WB-22', 'WB-23'] },
  { uiControl: 'products.table.strategy', backendField: 'rows[].strategyId', sourceRef: 'wbReuseDependencyMap:pricing-engine', formulaRef: null, blockerIds: ['WB-14', 'WB-25'] },
  { uiControl: 'products.table.stock', backendField: 'rows[].stockQty', sourceRef: 'wbSourceRegistry:stocks-report', formulaRef: 'wbFormulaCatalog:oos_days', blockerIds: ['WB-01', 'WB-17', 'WB-23'] },
]

export const SECONDARY_REPORT_BACKEND_DEPENDENCY_MAP: VellaDependencyRef[] = [
  { uiControl: 'reports.common.sourceCompact', backendField: 'sourceStatus + freshness + blockerIds + states + exportHistory[]', sourceRef: 'wbReuseDependencyMap:source-registry-state', formulaRef: null, blockerIds: ['WB-23', 'WB-24'] },
  { uiControl: 'reports.digest.summary', backendField: 'data.summary[]', sourceRef: 'wbSourceRegistry:sales-finance-stock-ads-quality', formulaRef: 'wbFormulaCatalog:management_digest', blockerIds: ['WB-02', 'WB-12', 'WB-13', 'WB-14A', 'WB-23', 'WB-24'] },
  { uiControl: 'reports.digest.kpis', backendField: 'data.kpis[]', sourceRef: 'wbSourceRegistry:sales-finance-stock-ads-quality', formulaRef: 'wbFormulaCatalog:management_digest', blockerIds: ['WB-02', 'WB-12', 'WB-13', 'WB-23', 'WB-24'] },
  { uiControl: 'reports.digest.actionQueue', backendField: 'data.actionQueue[]', sourceRef: 'wbReuseDependencyMap:event-stream', formulaRef: null, blockerIds: ['WB-17', 'WB-18', 'WB-24'] },
  { uiControl: 'reports.sales.dynamics', backendField: 'data.chartSeries[]', sourceRef: 'wbSourceRegistry:sales-export-jobs', formulaRef: 'wbFormulaCatalog:sales_dynamics', blockerIds: ['WB-03', 'WB-23'] },
  { uiControl: 'reports.sales.exportHistory', backendField: 'exportHistory[]', sourceRef: 'wbSourceRegistry:async-excel-reports', formulaRef: null, blockerIds: ['WB-03', 'WB-23'] },
  { uiControl: 'reports.rnp.table', backendField: 'rows[].cells', sourceRef: 'wbSourceRegistry:analytics-sales-orders-ads', formulaRef: 'wbFormulaCatalog:rnp_thresholds', blockerIds: ['WB-09', 'WB-19', 'WB-23'] },
  { uiControl: 'reports.pnl.table', backendField: 'rows[].cells', sourceRef: 'wbSourceRegistry:finance-reports', formulaRef: 'wbFormulaCatalog:profit_margin_allocation', blockerIds: ['WB-02', 'WB-11', 'WB-12', 'WB-24'] },
  { uiControl: 'reports.pnl.drilldowns', backendField: 'data.drilldowns[]', sourceRef: 'wbSourceRegistry:finance-reports', formulaRef: 'wbFormulaCatalog:profit_margin_allocation', blockerIds: ['WB-02', 'WB-11', 'WB-12', 'WB-13', 'WB-24'] },
  { uiControl: 'reports.pnl.opCostAllocation', backendField: 'data.opCostAllocation[]', sourceRef: 'wbSourceRegistry:finance-reports', formulaRef: 'wbFormulaCatalog:opex_allocation', blockerIds: ['WB-12', 'WB-13', 'WB-24'] },
  { uiControl: 'reports.expenses.table', backendField: 'rows[] + import.preview + import.commit', sourceRef: 'wbSourceRegistry:manual-expenses', formulaRef: 'wbFormulaCatalog:opex_allocation', blockerIds: ['WB-12', 'WB-13', 'WB-24'] },
  { uiControl: 'sources.status.registry', backendField: 'sourceStatus + freshness + blockerIds + evidenceRefs', sourceRef: 'wbReuseDependencyMap:source-registry-state', formulaRef: null, blockerIds: ['WB-02', 'WB-03', 'WB-06', 'WB-12', 'WB-13', 'WB-22', 'WB-23', 'WB-24'] },
  { uiControl: 'reports.quality.embedded', backendField: 'data.actionQueue[]', sourceRef: 'wbSourceRegistry:hidden-card-penalty-kiz', formulaRef: null, blockerIds: ['WB-17', 'WB-18', 'WB-24'] },
  { uiControl: 'reports.ads.balance', backendField: 'data.balanceSeries[]', sourceRef: 'wbSourceRegistry:ads-attribution', formulaRef: 'wbFormulaCatalog:drr_romi', blockerIds: ['WB-02', 'WB-11', 'WB-20', 'WB-23'] },
  { uiControl: 'reports.ads.performance', backendField: 'data.performanceCards[] + data.attribution', sourceRef: 'wbSourceRegistry:ads-attribution', formulaRef: 'wbFormulaCatalog:drr_romi', blockerIds: ['WB-02', 'WB-11', 'WB-20', 'WB-23'] },
  { uiControl: 'reports.ads.table', backendField: 'rows[].cells', sourceRef: 'wbSourceRegistry:ads-attribution', formulaRef: 'wbFormulaCatalog:drr_romi', blockerIds: ['WB-02', 'WB-20', 'WB-23'] },
  { uiControl: 'reports.stock.management', backendField: 'data.managementCards[]', sourceRef: 'wbSourceRegistry:stocks-report', formulaRef: 'wbFormulaCatalog:warehouse_oos', blockerIds: ['WB-01', 'WB-17', 'WB-18', 'WB-23'] },
  { uiControl: 'reports.stock.table', backendField: 'rows[].cells', sourceRef: 'wbSourceRegistry:stocks-report', formulaRef: 'wbFormulaCatalog:warehouse_oos', blockerIds: ['WB-01', 'WB-17', 'WB-18', 'WB-23'] },
  { uiControl: 'reports.week.table', backendField: 'rows[].cells', sourceRef: 'wbSourceRegistry:period-comparison', formulaRef: 'wbFormulaCatalog:week_over_week', blockerIds: ['WB-21', 'WB-23'] },
]

export const REPORTS_BACKEND_DEPENDENCY_MAP = SECONDARY_REPORT_BACKEND_DEPENDENCY_MAP

export const NOTIFICATIONS_BACKEND_DEPENDENCY_MAP: VellaDependencyRef[] = [
  { uiControl: 'notifications.table.row', backendField: 'events[]', sourceRef: 'wbReuseDependencyMap:event-stream', formulaRef: null, blockerIds: [] },
  { uiControl: 'notifications.detail.action', backendField: 'selected.routeAction', sourceRef: 'wbReuseDependencyMap:permission-matrix', formulaRef: null, blockerIds: ['WB-24', 'AV-14'] },
  { uiControl: 'notifications.avito.workspace', backendField: 'workspace', sourceRef: 'wbReuseDependencyMap:avito-capability-events', formulaRef: null, blockerIds: ['AV-02', 'AV-06', 'AV-07', 'AV-09'] },
]
