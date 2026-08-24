export type DdsArticleScope =
  | 'exclude'
  | 'pnl_only_admin'
  | 'period_allocated'
  | 'reconciliation_required'
  | 'cashflow_reconciliation'

export type DdsArticleRule = {
  articleName: string
  direction: 'inflow' | 'outflow'
  include: boolean
  scope: DdsArticleScope
  allocationDriver: null | 'orders' | 'units' | 'production_units' | 'shipments' | 'revenue' | 'manual'
  entersSkuPnl: boolean
  entersCompanyPnl: boolean
  reason: string
}

export type ExpenseRow = {
  id: string
  ddsArticleName: string
  direction: 'inflow' | 'outflow'
  include: boolean
  scope: DdsArticleScope
  periodFrom: string
  periodTo: string
  amountKopecks: number | null
  sourceId: string
  sourceLabel: string
  allocationDriver: DdsArticleRule['allocationDriver']
  skuCoveragePct: number | null
  planFactBase: 'monthly_plan_completion' | null
  status:
    | 'ready_for_pnl'
    | 'mapping_required'
    | 'rate_required'
    | 'unallocated'
    | 'pnl_only'
    | 'excluded'
    | 'reconciliation_required'
    | 'source_error'
    | 'draft'
  entersSkuPnl: boolean
  entersCompanyPnl: boolean
  comment: string | null
}

export type ExpenseDraftInput = {
  ddsArticleName: string
  direction: 'outflow'
  amountKopecks: number
  periodFrom: string
  periodTo: string
  sourceType: 'manual' | 'excel_fallback' | 'one_c'
  scope: 'pnl_only_admin' | 'period_allocated' | 'reconciliation_required'
  allocationDriver: DdsArticleRule['allocationDriver']
  ownerUserId: string
  comment: string | null
}

export type ExpenseSummaryMetrics = {
  totalExpensesKopecks: number
  pnlOnlyKopecks: number
  draftNetProfitKopecks: number
  reconciliationRequiredKopecks: number
}

export function validateExpenseRowContract(row: ExpenseRow) {
  if (row.scope === 'exclude') {
    return !row.entersSkuPnl && !row.entersCompanyPnl
  }
  if (row.scope === 'cashflow_reconciliation') {
    return !row.entersSkuPnl && !row.entersCompanyPnl
  }
  if (row.scope === 'pnl_only_admin') {
    return !row.entersSkuPnl
      && row.entersCompanyPnl
      && row.skuCoveragePct === null
      && row.planFactBase === 'monthly_plan_completion'
  }
  return true
}
