import { authorizationHeaders } from '@/features/auth/authApi'
import { apiRequest } from '@/lib/api'

export type ReportRulesPreset = 'standard' | 'conservative' | 'aggressive' | 'custom'
export type ReportRulesAction = 'raise_price' | 'lower_price' | 'rnp' | 'liquidation' | 'stop_ads' | 'alert' | 'audit'

export type ReportRulesConfig = {
  abc: {
    salesShare: { aPct: number; bPct: number; cPct: number }
    netProfitShare: { aPct: number; bPct: number; cPct: number }
  }
  qualityBands: {
    ctrPct: { goodMin: number; averageMin: number }
    crPct: { goodMin: number; averageMin: number }
    cartToOrderPct: { goodMin: number; averageMin: number }
    buyoutPct: { goodMin: number; averageMin: number }
    marginPct: { goodMin: number; thinMin: number; lossBelow: number }
    drrPct: { goodMax: number; warnMin: number }
    roiPct: { goodMin: number; warnBelow: number }
    daysToOos: { warnBelow: number }
    stockUnits: { criticalBelow: number }
    localizationPct: { badBelow: number }
  }
  automationMapping: Record<'aaGood' | 'badCr' | 'loss' | 'highDrr' | 'oos' | 'cWeak', ReportRulesAction>
}

export type ReportRulesProfile = {
  profileId: number | null
  organizationId: number
  version: number
  name: string
  preset: ReportRulesPreset
  config: ReportRulesConfig
  createdByUserId: string | null
  createdAt: string | null
  isActive: boolean
}

export type ReportRulesReadResponse = {
  profile: ReportRulesProfile
  presets: Record<'standard' | 'conservative' | 'aggressive', ReportRulesConfig>
  automationActions: ReportRulesAction[]
  canWrite: boolean
}

export type ReportRulesDraft = {
  expectedVersion: number
  name: string
  preset: ReportRulesPreset
  config: ReportRulesConfig
}

export type ReportRulesPreview = {
  affectedSkuCount: number
  statusChanges: number
  automationImpact: Record<string, number>
  sampleRows: Array<{ sku: string; before: { status: string }; after: { status: string; statusReasons: string[] } }>
  warnings: string[]
  availableReports: string[]
  previewToken: string
}

export type DigestPlan = {
  month: string
  company: { revenuePlanKopecks: number; marginPlanKopecks: number }
  managers: Array<{ id: string; name: string; revenuePlanKopecks: number; marginPlanKopecks: number }>
  updatedAt?: string
}

const headers = (accessToken: string) => authorizationHeaders(accessToken)

export const getReportRules = (accessToken: string) =>
  apiRequest<ReportRulesReadResponse>('/api/wb/reports/rules', { headers: headers(accessToken) })

export const getReportRulesHistory = (accessToken: string) =>
  apiRequest<{ items: ReportRulesProfile[] }>('/api/wb/reports/rules/history?limit=20', { headers: headers(accessToken) })

export const previewReportRules = (accessToken: string, draft: ReportRulesDraft) =>
  apiRequest<ReportRulesPreview>('/api/wb/reports/rules/preview', {
    method: 'POST', headers: headers(accessToken), body: JSON.stringify(draft),
  })

export const saveReportRules = (accessToken: string, draft: ReportRulesDraft & { previewToken: string }) =>
  apiRequest<{ profile: ReportRulesProfile }>('/api/wb/reports/rules', {
    method: 'PUT', headers: headers(accessToken), body: JSON.stringify(draft),
  })

export const getManagerPlan = (accessToken: string, month: string) =>
  apiRequest<DigestPlan>(`/api/wb/reports/digest/plan?month=${encodeURIComponent(month)}`, { headers: headers(accessToken) })

export const saveManagerPlan = (accessToken: string, plan: DigestPlan) =>
  apiRequest<DigestPlan>('/api/wb/reports/digest/plan', {
    method: 'POST', headers: headers(accessToken), body: JSON.stringify(plan),
  })
