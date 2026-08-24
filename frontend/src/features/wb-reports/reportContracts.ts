import {
  AbcReportResponseSchema,
  AdsPerformanceResponseSchema,
  PnlReportResponseSchema,
  RnpReportResponseSchema,
  type AbcReportResponse,
  type AdsAttributionLevel,
  type AdsPerformanceResponse,
  type PnlReportResponse,
  type RnpReportResponse,
} from './schemas.js'
import type { DateRange, ReportGroupBy, ReportId, ReportResponse, TableRow, TableValue } from './types.js'
import type { SourceEvidence, SourceStatus } from '../wb-contracts/sourceState.js'

type ContractReportId = Extract<ReportId, 'abc' | 'ads' | 'pnl' | 'rnp'>
type PnlSource = 'operational' | 'financial'

type ReportContractContext = {
  dateRange: DateRange
  groupBy?: ReportGroupBy | 'campaign'
  pnlSource?: PnlSource
}

type ReportContractSidecar =
  | AbcReportResponse
  | AdsPerformanceResponse
  | PnlReportResponse
  | RnpReportResponse

const CALCULATED_AT = '2026-05-21T10:00:00.000Z'

const SOURCE_EVIDENCE: Record<string, SourceEvidence> = {
  operational: {
    sourceId: 'vella-mock-operational-reports',
    sourceType: 'mock',
    sourceName: 'Vella mock operational reports',
    lastSyncedAt: '2026-05-07T03:00:00.000Z',
    freshnessTtlMinutes: 1440,
    fieldsUsed: ['orders', 'sales', 'baskets', 'stock', 'ads'],
  },
  financial: {
    sourceId: 'one-c-finance-live',
    sourceType: 'one_c',
    sourceName: '1С · финансы и УУ',
    lastSyncedAt: '2026-05-07T04:10:00.000Z',
    freshnessTtlMinutes: 1440,
    fieldsUsed: ['storage', 'packaging', 'payroll', 'acquiring', 'services', 'externalLogistics', 'other', 'tax'],
  },
  ads: {
    sourceId: 'wb-ads-discovery-placeholder',
    sourceType: 'mock',
    sourceName: 'WB Ads source discovery placeholder',
    lastSyncedAt: null,
    freshnessTtlMinutes: null,
    fieldsUsed: ['campaign', 'adSpend', 'impressions', 'clicks', 'orders'],
  },
}

function numberValue(value: TableValue): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    if ('kopecks' in value && typeof value.kopecks === 'number') return value.kopecks
    if ('units' in value && typeof value.units === 'number') return value.units
    if ('percent' in value && typeof value.percent === 'number') return value.percent
  }
  return null
}

function stringValue(value: TableValue): string | null {
  if (typeof value === 'string' && value.trim()) return value
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

function rowsSum(rows: TableRow[], key: string): number | null {
  const values = rows.map((row) => numberValue(row[key])).filter((value): value is number => value !== null)
  if (values.length === 0) return null
  return values.reduce((acc, value) => acc + value, 0)
}

function rowsAvg(rows: TableRow[], key: string): number | null {
  const values = rows.map((row) => numberValue(row[key])).filter((value): value is number => value !== null)
  if (values.length === 0) return null
  return Number((values.reduce((acc, value) => acc + value, 0) / values.length).toFixed(1))
}

function sourceBase(context: ReportContractContext, sourceStatus: SourceStatus, blockerIds: string[], sourceEvidence: SourceEvidence[]) {
  return {
    sourceStatus,
    confidence: sourceStatus === 'fresh' ? 'high' as const : sourceStatus === 'blocked' ? 'blocked' as const : 'low' as const,
    blockerIds,
    sourceEvidence,
    calculatedAt: CALCULATED_AT,
    period: { dateFrom: context.dateRange.from, dateTo: context.dateRange.to },
  }
}

function buildPnlContract(report: ReportResponse, context: ReportContractContext): PnlReportResponse {
  const isFinancial = context.pnlSource === 'financial'
  const blockerIds = ['WB-12', 'WB-13', 'WB-23', 'WB-24']
  const sourceStatus: SourceStatus = isFinancial ? 'blocked' : 'partial'
  const confidence = isFinancial ? 'blocked' as const : 'low' as const
  return {
    ...sourceBase(context, sourceStatus, blockerIds, [SOURCE_EVIDENCE.operational, SOURCE_EVIDENCE.financial, SOURCE_EVIDENCE.ads]),
    confidence,
    reportState: isFinancial ? 'blocked' : 'preliminary',
    groupBy: context.groupBy ?? 'sku',
    totals: {
      revenueKopecks: rowsSum(report.rows, 'salesKopecks'),
      netProfitKopecks: null,
      marginPct: null,
      sourceStatus,
      confidence,
    },
    rows: report.rows.map((row, index) => ({
      rowId: stringValue(row.sku) ?? `pnl-row-${index}`,
      label: stringValue(row.sku) ?? stringValue(row.productStatus) ?? `Строка ${index + 1}`,
      brandId: stringValue(row.brand),
      managerId: stringValue(row.managerId),
      skuId: stringValue(row.sku),
      revenueKopecks: numberValue(row.salesKopecks),
      cogsKopecks: numberValue(row.cogsKopecks),
      commissionKopecks: null,
      logisticsKopecks: null,
      storageKopecks: null,
      adSpendKopecks: numberValue(row.adSpendKopecks),
      taxKopecks: null,
      overheadKopecks: null,
      netProfitKopecks: null,
      marginPct: null,
      sourceStatus,
      confidence,
    })),
    fieldMapping: [
      { metricId: 'revenue', metricLabel: 'Выручка', sourceId: SOURCE_EVIDENCE.operational.sourceId, sourceField: 'salesKopecks', formula: 'sales by selected period', fallback: null, blockerIds: [] },
      { metricId: 'ad_spend', metricLabel: 'Реклама', sourceId: SOURCE_EVIDENCE.ads.sourceId, sourceField: 'adSpendKopecks', formula: 'ads spend by selected period', fallback: null, blockerIds: ['WB-02'] },
      { metricId: 'storage', metricLabel: 'Хранение', sourceId: SOURCE_EVIDENCE.financial.sourceId, sourceField: 'storage', formula: 'amount * sku stock-days / period stock-days; fallback revenue share', fallback: 'Excel fallback', blockerIds: ['WB-12'] },
      { metricId: 'tax', metricLabel: 'Налог/НДС', sourceId: SOURCE_EVIDENCE.financial.sourceId, sourceField: 'tax', formula: 'requires configured tax base, rate, regime and rounding', fallback: null, blockerIds: ['WB-13'] },
      { metricId: 'opex_visibility', metricLabel: 'Расходы и доступы', sourceId: SOURCE_EVIDENCE.financial.sourceId, sourceField: 'opex', formula: '1С expense rows with SKU allocation coverage and finance/admin visibility', fallback: 'finance/admin only', blockerIds: ['WB-24'] },
    ],
    manualCosts: [
      { costId: 'storage', label: 'Хранение WB', amountKopecks: null, allocationBase: 'stock_days', sourceStatus: 'partial', blockerIds: ['WB-12'] },
      { costId: 'tax', label: 'Налог/НДС', amountKopecks: null, allocationBase: 'unknown', sourceStatus: 'blocked', blockerIds: ['WB-13'] },
      { costId: 'opex', label: 'Операционные расходы', amountKopecks: null, allocationBase: 'sku', sourceStatus: 'partial', blockerIds: ['WB-12', 'WB-24'] },
    ],
    dayAllocation: {
      allocationDateField: 'saleDate',
      expenseDateField: null,
      rule: 'Preliminary: expenses are allocated to SKU; rows without driver or tax rule stay out of P&L closeout',
      sourceStatus: 'partial',
      blockerIds: ['WB-23'],
    },
  }
}

function adsAttributionLevel(row: TableRow): AdsAttributionLevel {
  const value = stringValue(row.attributionLevel)
  if (value === 'exact_sku' || value === 'campaign_sku' || value === 'campaign_only' || value === 'unknown') return value
  return 'unknown'
}

function confidenceFromAttribution(level: AdsAttributionLevel) {
  if (level === 'exact_sku') return 'high' as const
  if (level === 'campaign_sku') return 'medium' as const
  return 'low' as const
}

function buildAdsContract(report: ReportResponse, context: ReportContractContext): AdsPerformanceResponse {
  const groupBy = context.groupBy ?? 'campaign'
  const rows = report.rows
    .filter((row) => groupBy !== 'sku' || adsAttributionLevel(row) !== 'campaign_only')
    .map((row, index) => {
      const level = adsAttributionLevel(row)
      return {
        rowId: stringValue(row.campaignId) ?? stringValue(row.sku) ?? `ads-row-${index}`,
        campaignId: stringValue(row.campaignId),
        skuId: level === 'campaign_only' ? null : stringValue(row.sku),
        brandId: stringValue(row.brand),
        managerId: stringValue(row.managerId),
        adSpendKopecks: numberValue(row.adSpendKopecks),
        impressions: numberValue(row.impressions),
        clicks: numberValue(row.clicks),
        cartAdds: numberValue(row.baskets),
        ordersCount: numberValue(row.orders),
        ordersKopecks: null,
        drrPct: numberValue(row.drrPct),
        romiPct: null,
        roiPct: null,
        attributionLevel: level,
        confidence: confidenceFromAttribution(level),
      }
    })

  return {
    ...sourceBase(context, 'partial', ['WB-02', 'WB-23'], [SOURCE_EVIDENCE.ads]),
    groupBy,
    totals: {
      adSpendKopecks: rows.reduce((acc, row) => acc + (row.adSpendKopecks ?? 0), 0),
      impressions: rows.reduce((acc, row) => acc + (row.impressions ?? 0), 0),
      clicks: rows.reduce((acc, row) => acc + (row.clicks ?? 0), 0),
      cartAdds: rows.reduce((acc, row) => acc + (row.cartAdds ?? 0), 0),
      ordersCount: rows.reduce((acc, row) => acc + (row.ordersCount ?? 0), 0),
      ordersKopecks: null,
      drrPct: rowsAvg(report.rows, 'drrPct'),
      romiPct: null,
      roiPct: null,
    },
    rows,
    attributionPolicy: {
      allowedSkuLevels: ['exact_sku', 'campaign_sku'],
      campaignOnlyCanAllocateToSkuPnl: false,
      notes: ['campaign_only remains campaign-level and is not allocated into exact SKU P&L'],
    },
  }
}

function buildRnpContract(report: ReportResponse, context: ReportContractContext): RnpReportResponse {
  return {
    ...sourceBase(context, 'partial', ['WB-02', 'WB-11', 'WB-23'], [SOURCE_EVIDENCE.operational, SOURCE_EVIDENCE.ads]),
    groupBy: context.groupBy ?? 'sku',
    rows: report.rows.map((row, index) => ({
      rowId: stringValue(row.sku) ?? `rnp-row-${index}`,
      label: stringValue(row.sku) ?? `Строка ${index + 1}`,
      skuId: context.groupBy === 'sku' || !context.groupBy ? stringValue(row.sku) : null,
      brandId: stringValue(row.brand),
      managerId: stringValue(row.managerId),
      adSpendKopecks: numberValue(row.adSpendKopecks),
      drrPct: numberValue(row.drrOrdersPct),
      roiPct: null,
      marginPct: numberValue(row.marginPct),
      sourceStatus: 'partial',
      confidence: 'low',
    })),
    adSpendKopecks: rowsSum(report.rows, 'adSpendKopecks'),
    drrPct: rowsAvg(report.rows, 'drrOrdersPct'),
    formulaNotes: ['DRR/ROI/margin formulas await Мария/Максим confirmation; ads source is still discovery-level'],
    adsSourceStatus: 'partial',
  }
}

function buildAbcContract(report: ReportResponse, context: ReportContractContext): AbcReportResponse {
  const locomotiveCount = report.rows.filter((row) => stringValue(row.productStatus) === 'локомотив').length
  return {
    ...sourceBase(context, 'partial', ['WB-12', 'WB-13', 'WB-19A', 'WB-23', 'WB-24'], [SOURCE_EVIDENCE.operational, SOURCE_EVIDENCE.ads]),
    filteredSummary: {
      filterHash: `${context.groupBy ?? 'sku'}:${context.dateRange.from}:${context.dateRange.to}:${report.rows.length}`,
      skuCount: report.rows.length,
      locomotiveCount,
      ordersCount: rowsSum(report.rows, 'ordersUnits'),
      ordersKopecks: rowsSum(report.rows, 'ordersKopecks'),
      profitKopecks: null,
      marginPct: null,
      adSpendKopecks: rowsSum(report.rows, 'adSpendKopecks'),
      sourceStatus: 'partial',
      confidence: 'blocked',
    },
    rows: report.rows,
  }
}

export function buildReportContractSidecar(reportId: 'abc', report: ReportResponse, context: ReportContractContext): AbcReportResponse
export function buildReportContractSidecar(reportId: 'ads', report: ReportResponse, context: ReportContractContext): AdsPerformanceResponse
export function buildReportContractSidecar(reportId: 'pnl', report: ReportResponse, context: ReportContractContext): PnlReportResponse
export function buildReportContractSidecar(reportId: 'rnp', report: ReportResponse, context: ReportContractContext): RnpReportResponse
export function buildReportContractSidecar(reportId: ContractReportId, report: ReportResponse, context: ReportContractContext): ReportContractSidecar
export function buildReportContractSidecar(reportId: ContractReportId, report: ReportResponse, context: ReportContractContext): ReportContractSidecar {
  if (reportId === 'pnl') return buildPnlContract(report, context)
  if (reportId === 'ads') return buildAdsContract(report, context)
  if (reportId === 'rnp') return buildRnpContract(report, context)
  return buildAbcContract(report, context)
}

export function assertReportContract(reportId: ContractReportId, report: ReportResponse, context: ReportContractContext): ReportContractSidecar {
  const sidecar = buildReportContractSidecar(reportId, report, context)
  if (reportId === 'pnl') return PnlReportResponseSchema.parse(sidecar)
  if (reportId === 'ads') return AdsPerformanceResponseSchema.parse(sidecar)
  if (reportId === 'rnp') return RnpReportResponseSchema.parse(sidecar)
  return AbcReportResponseSchema.parse(sidecar)
}
