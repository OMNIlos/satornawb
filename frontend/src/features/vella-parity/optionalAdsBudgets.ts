type BudgetRow = { campaignId?: string | number | null; budgetCashKopecks?: number | null; budgetNettingKopecks?: number | null; budgetTotalKopecks?: number | null }
type Kpi = { id?: string; value?: string | number | null; hint?: string | null }
export type BudgetPatch = {
  dateFrom: string; dateTo: string; rows: BudgetRow[]
  kpi?: Kpi | null
  budgetRefresh: { state?: string; error?: string; collected?: number; total?: number }
}

export function applyOptionalBudgets<T extends { rows?: BudgetRow[] | null; kpis?: Kpi[] | null }>(report: T, patch: BudgetPatch, from: string, to: string): T {
  if (patch.dateFrom !== from || patch.dateTo !== to) return report
  const byCampaign = new Map(patch.rows.map(row => [String(row.campaignId), row]))
  return {
    ...report,
    budgetRefresh: patch.budgetRefresh,
    rows: report.rows?.map(row => {
      const budget = byCampaign.get(String(row.campaignId))
      return budget ? { ...row, budgetCashKopecks: budget.budgetCashKopecks, budgetNettingKopecks: budget.budgetNettingKopecks, budgetTotalKopecks: budget.budgetTotalKopecks } : row
    }),
    kpis: report.kpis?.map(kpi => kpi.id === 'campaign_budget' && patch.kpi ? { ...kpi, value: patch.kpi.value, hint: patch.kpi.hint } : kpi),
  }
}
