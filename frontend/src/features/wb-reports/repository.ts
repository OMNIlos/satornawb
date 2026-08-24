import { formatRub } from '../../lib/formatRub.js'
import { assertReportContract } from './reportContracts.js'
import type {
  AbcCode,
  AdsCampaignRow,
  CompositeMetricValue,
  DatePreset,
  DateRange,
  DigestResponse,
  DigestProblemRow,
  ExportResponse,
  FinancialConfirmationStatus,
  FreshnessItem,
  FreshnessState,
  KpiTone,
  ManagerAssignmentSource,
  PlanFactRow,
  ReportAuditEvent,
  ReportAlert,
  ReportChartData,
  ReportGroupBy,
  ReportId,
  ReportKpi,
  ReportResponse,
  SkuComment,
  SkuAnalyticsSummary,
  SkuReportRow,
  StockDailySnapshot,
  StockWarehouseRow,
  TableColumn,
  TableRow,
  WeekOverWeekRow,
} from './types.js'

const LAST_OPERATIONAL_UPDATE = '2026-05-07T08:00:00.000+05:00'
const LAST_FINANCIAL_UPDATE = '2026-05-06T10:20:00.000+05:00'
const EMPTY_PROMO_FILE_NOTE = 'Файл исключений акции содержит только строку "Товар уже участвует в акции" и не даёт списка SKU.'
const ADS_DRAFT_STOP_DRR_THRESHOLD_PCT = 25
const ADS_DRAFT_STOP_MIN_SPEND_KOPECKS = 150000
const ADS_DRAFT_STOP_MIN_OBSERVATION_DAYS = 21

const DEFAULT_RANGE: DateRange = { preset: '7d', from: '2026-05-01', to: '2026-05-07' }
const UNASSIGNED_MANAGER_LABEL = 'Без ответственного'
const UNASSIGNED_MANAGER_ID = null

type ManagerUser = {
  id: string
  name: string
  active: boolean
  order: number
  monthlyPlanKopecks: number | null
}

export const MANAGERS: ManagerUser[] = [
  { id: 'manager-kotelnikova', name: 'Котельникова', active: true, order: 10, monthlyPlanKopecks: 24000000 },
  { id: 'manager-vorobieva', name: 'Воробьева', active: true, order: 20, monthlyPlanKopecks: 21000000 },
  { id: 'manager-dudina', name: 'Дудина', active: true, order: 30, monthlyPlanKopecks: 19000000 },
  { id: 'manager-svetlana', name: 'Светлана', active: true, order: 40, monthlyPlanKopecks: null },
  { id: 'manager-irina', name: 'Ирина', active: true, order: 50, monthlyPlanKopecks: 16000000 },
]

const MANAGER_BY_NAME = new Map(MANAGERS.map((manager) => [manager.name, manager]))
const MANAGER_ASSIGNMENT_OVERRIDES: Record<string, { managerId: string | null; source: ManagerAssignmentSource; assignedAt: string | null }> = {
  LBBT_03: { managerId: null, source: 'none', assignedAt: null },
  HBBT_08: { managerId: null, source: 'none', assignedAt: null },
  FBBT_14: { managerId: 'manager-irina', source: 'xlsx', assignedAt: '2026-05-07T18:40:00.000+05:00' },
}

type LocalizationBand = {
  min: number
  max: number
  territorialCoefficient: number
  salesDistributionCoefficient: number
}

const LOCALIZATION_BANDS: LocalizationBand[] = [
  { min: 95, max: 100, territorialCoefficient: 0.5, salesDistributionCoefficient: 0 },
  { min: 90, max: 94.99, territorialCoefficient: 0.6, salesDistributionCoefficient: 0 },
  { min: 85, max: 89.99, territorialCoefficient: 0.7, salesDistributionCoefficient: 0 },
  { min: 80, max: 84.99, territorialCoefficient: 0.8, salesDistributionCoefficient: 0 },
  { min: 75, max: 79.99, territorialCoefficient: 0.9, salesDistributionCoefficient: 0 },
  { min: 70, max: 74.99, territorialCoefficient: 1, salesDistributionCoefficient: 0 },
  { min: 65, max: 69.99, territorialCoefficient: 1, salesDistributionCoefficient: 0 },
  { min: 60, max: 64.99, territorialCoefficient: 1, salesDistributionCoefficient: 0 },
  { min: 55, max: 59.99, territorialCoefficient: 1.05, salesDistributionCoefficient: 2 },
  { min: 50, max: 54.99, territorialCoefficient: 1.1, salesDistributionCoefficient: 2.05 },
  { min: 45, max: 49.99, territorialCoefficient: 1.2, salesDistributionCoefficient: 2.05 },
  { min: 40, max: 44.99, territorialCoefficient: 1.3, salesDistributionCoefficient: 2.1 },
  { min: 35, max: 39.99, territorialCoefficient: 1.4, salesDistributionCoefficient: 2.1 },
  { min: 30, max: 34.99, territorialCoefficient: 1.5, salesDistributionCoefficient: 2.15 },
  { min: 25, max: 29.99, territorialCoefficient: 1.55, salesDistributionCoefficient: 2.2 },
  { min: 20, max: 24.99, territorialCoefficient: 1.6, salesDistributionCoefficient: 2.25 },
  { min: 15, max: 19.99, territorialCoefficient: 1.7, salesDistributionCoefficient: 2.3 },
  { min: 10, max: 14.99, territorialCoefficient: 1.75, salesDistributionCoefficient: 2.35 },
  { min: 5, max: 9.99, territorialCoefficient: 1.8, salesDistributionCoefficient: 2.45 },
  { min: 0, max: 4.99, territorialCoefficient: 2, salesDistributionCoefficient: 2.5 },
]

export function calculateLocalizationPct(localOrders: number, totalOrders: number): number {
  if (totalOrders <= 0) return 0
  return Number(Math.max(0, Math.min(100, (localOrders / totalOrders) * 100)).toFixed(2))
}

export function localizationCoefficients(localizationPct: number): LocalizationBand {
  const normalized = Math.max(0, Math.min(100, localizationPct))
  return LOCALIZATION_BANDS.find((band) => normalized >= band.min && normalized <= band.max) ?? LOCALIZATION_BANDS[LOCALIZATION_BANDS.length - 1]
}

function daysBack(days: number): DateRange {
  const to = new Date('2026-05-07T00:00:00.000Z')
  const from = new Date(to)
  from.setUTCDate(to.getUTCDate() - days + 1)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  return { preset: `${days}d` as DatePreset, from: iso(from), to: iso(to) }
}

export function normalizeDateRange(params: Partial<DateRange> = {}): DateRange {
  if (params.preset === '1d') return daysBack(1)
  if (params.preset === '14d') return daysBack(14)
  if (params.preset === '30d') return daysBack(30)
  if (params.preset === 'custom' && params.from && params.to) return { preset: 'custom', from: params.from, to: params.to }
  return {
    preset: params.preset ?? DEFAULT_RANGE.preset,
    from: params.from ?? DEFAULT_RANGE.from,
    to: params.to ?? DEFAULT_RANGE.to,
  }
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`
}

function sum(values: number[]) {
  return values.reduce((acc, value) => acc + value, 0)
}

function avg(values: number[]) {
  return values.length ? sum(values) / values.length : 0
}

function daysInRange(dateRange: DateRange) {
  const from = new Date(`${dateRange.from}T00:00:00.000Z`)
  const to = new Date(`${dateRange.to}T00:00:00.000Z`)
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime()) || to < from) return 1
  return Math.floor((to.getTime() - from.getTime()) / 86_400_000) + 1
}

function daysInMonth(dateRange: DateRange) {
  const from = new Date(`${dateRange.from}T00:00:00.000Z`)
  return new Date(Date.UTC(from.getUTCFullYear(), from.getUTCMonth() + 1, 0)).getUTCDate()
}

function periodPlan(monthlyPlanKopecks: number | null, dateRange: DateRange) {
  if (monthlyPlanKopecks == null) return null
  const ratio = Math.min(1, daysInRange(dateRange) / daysInMonth(dateRange))
  return Math.round(monthlyPlanKopecks * ratio)
}

function assignmentFor(row: Pick<SkuReportRow, 'sku' | 'manager'>) {
  const override = MANAGER_ASSIGNMENT_OVERRIDES[row.sku]
  if (override) {
    const manager = override.managerId ? MANAGERS.find((item) => item.id === override.managerId) : null
    return {
      managerId: override.managerId,
      manager: manager?.name ?? UNASSIGNED_MANAGER_LABEL,
      assignmentSource: override.source,
      assignedAt: override.assignedAt,
    }
  }
  const manager = MANAGER_BY_NAME.get(row.manager)
  return {
    managerId: manager?.id ?? UNASSIGNED_MANAGER_ID,
    manager: manager?.name ?? UNASSIGNED_MANAGER_LABEL,
    assignmentSource: (manager ? 'manual' : 'none') as ManagerAssignmentSource,
    assignedAt: manager ? '2026-05-06T09:12:00.000+05:00' : null,
  }
}

function deltaTone(value: number, goodWhenPositive = true): KpiTone {
  if (value === 0) return 'neutral'
  return value > 0 === goodWhenPositive ? 'good' : 'bad'
}

function delta(value: number, suffix = '%', goodWhenPositive = true) {
  return {
    value,
    label: `${value > 0 ? '+' : ''}${value.toFixed(1)}${suffix}`,
    tone: deltaTone(value, goodWhenPositive),
  }
}

function composite(units: number, kopecks: number, deltaPct: number, unitsLabel = 'шт'): CompositeMetricValue {
  return {
    units,
    unitsLabel,
    kopecks,
    deltaPct,
    deltaLabel: `${deltaPct > 0 ? '+' : ''}${deltaPct.toFixed(1)}%`,
  }
}

function wbImage(nmId: number) {
  const label = String(nmId).slice(-4)
  const hue = nmId % 360
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 96">
    <rect width="80" height="96" fill="#f3f4f6"/>
    <path d="M22 32 L40 22 L58 32 L62 84 L18 84 Z" fill="#e5e7eb" stroke="#d1d5db" stroke-width="2"/>
    <circle cx="40" cy="52" r="12" fill="hsl(${hue} 70% 52%)"/>
    <text x="40" y="56" font-family="monospace" font-size="10" font-weight="700" fill="#fff" text-anchor="middle">${label}</text>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

function cogsByCategory(category: string) {
  if (category.toLowerCase().includes('худи')) return 82000
  if (category.toLowerCase().includes('лонгслив')) return 54000
  return 46700
}

function abcByRank(rank: number): AbcCode {
  const sales = rank <= 3 ? 'A' : rank <= 6 ? 'B' : 'C'
  const profit = [1, 2, 4].includes(rank) ? 'A' : [3, 5, 6].includes(rank) ? 'B' : 'C'
  return `${sales}${profit}` as AbcCode
}

const ABC_ROWS: SkuReportRow[] = [
  {
    sku: 'FBBT_42', nmId: 684820752, photoUrl: wbImage(684820752), productStatus: 'локомотив', manager: 'Котельникова', brand: 'Anomie Studio', category: 'Футболки',
    priceBeforeSppKopecks: 139000, priceWithSppKopecks: 93800, marginPct: 26.7, marginKopecks: 25052, marginDeltaPct: 3.4,
    impressions: 354770, clicks: 13793, ctrPct: 3.9, baskets: 2469, cartCrPct: 17.9, basketsDeltaPct: 8.2,
    ordersUnits: 632, ordersDeltaPct: 5.8, ordersKopecks: 276389900, salesUnits: 514, salesDeltaPct: 4.1, salesKopecks: 176089000,
    adSpendKopecks: 1481400, drrOrdersPct: 0.5, drrSalesPct: 0.8, netPerUnitKopecks: 25052, netTotalKopecks: 42840330,
    logisticsCostPct: 9.8, logisticsDeltaPct: -1.2, commissionCostPct: 5.0, commissionDeltaPct: -0.4, storageCostPct: 0.8, storageDeltaPct: 0.1,
    wbStockUnits: 987, wbStockKopecks: 137193000, promotionStatus: 'yes', abcCode: 'AA', buyoutPct: 57.2,
  },
  {
    sku: 'FCBT_17', nmId: 453200669, photoUrl: wbImage(453200669), productStatus: 'локомотив', manager: 'Котельникова', brand: 'Anomie Studio', category: 'Футболки',
    priceBeforeSppKopecks: 135000, priceWithSppKopecks: 91200, marginPct: 23.1, marginKopecks: 21060, marginDeltaPct: 1.8,
    impressions: 48367, clicks: 4387, ctrPct: 9.1, baskets: 812, cartCrPct: 18.5, basketsDeltaPct: 11.4,
    ordersUnits: 384, ordersDeltaPct: 6.9, ordersKopecks: 162353800, salesUnits: 341, salesDeltaPct: 2.7, salesKopecks: 161201800,
    adSpendKopecks: 1018600, drrOrdersPct: 0.6, drrSalesPct: 0.6, netPerUnitKopecks: 21060, netTotalKopecks: 37202390,
    logisticsCostPct: 10.1, logisticsDeltaPct: -0.8, commissionCostPct: 5.3, commissionDeltaPct: -0.2, storageCostPct: 0.7, storageDeltaPct: 0.0,
    wbStockUnits: 2281, wbStockKopecks: 317059000, promotionStatus: 'yes', abcCode: 'AA', buyoutPct: 59.0,
  },
  {
    sku: 'HCBT_19', nmId: 559938623, photoUrl: wbImage(559938623), productStatus: 'средний', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Худи',
    priceBeforeSppKopecks: 289000, priceWithSppKopecks: 193600, marginPct: 14.5, marginKopecks: 28072, marginDeltaPct: -4.6,
    impressions: 91475, clicks: 5099, ctrPct: 5.6, baskets: 719, cartCrPct: 14.1, basketsDeltaPct: -7.9,
    ordersUnits: 181, ordersDeltaPct: -9.2, ordersKopecks: 82287400, salesUnits: 132, salesDeltaPct: -12.4, salesKopecks: 83780630,
    adSpendKopecks: 1464500, drrOrdersPct: 1.8, drrSalesPct: 1.7, netPerUnitKopecks: 28072, netTotalKopecks: 18771570,
    logisticsCostPct: 18.2, logisticsDeltaPct: 3.9, commissionCostPct: 8.8, commissionDeltaPct: 1.6, storageCostPct: 1.9, storageDeltaPct: 0.6,
    wbStockUnits: 1864, wbStockKopecks: 259096000, promotionStatus: 'no', abcCode: 'AB', buyoutPct: 48.0,
  },
  {
    sku: 'FBBT_55', nmId: 486641252, photoUrl: wbImage(486641252), productStatus: 'новинка', manager: 'Дудина', brand: 'Esereal', category: 'Футболки',
    priceBeforeSppKopecks: 129000, priceWithSppKopecks: 98040, marginPct: 14.0, marginKopecks: 13770, marginDeltaPct: 2.1,
    impressions: 346350, clicks: 20701, ctrPct: 6.0, baskets: 2755, cartCrPct: 13.3, basketsDeltaPct: 21.5,
    ordersUnits: 520, ordersDeltaPct: 17.8, ordersKopecks: 82556100, salesUnits: 302, salesDeltaPct: 14.3, salesKopecks: 75622000,
    adSpendKopecks: 2026700, drrOrdersPct: 2.5, drrSalesPct: 2.7, netPerUnitKopecks: 13770, netTotalKopecks: 4158540,
    logisticsCostPct: 19.7, logisticsDeltaPct: 1.2, commissionCostPct: 21.7, commissionDeltaPct: 0.4, storageCostPct: 0.7, storageDeltaPct: 0.1,
    wbStockUnits: 412, wbStockKopecks: 53148000, promotionStatus: 'yes', abcCode: 'BA', buyoutPct: 53.2,
  },
  {
    sku: 'LBBT_03', nmId: 486612890, photoUrl: wbImage(486612890), productStatus: 'неликвид', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Лонгсливы',
    priceBeforeSppKopecks: 120000, priceWithSppKopecks: 80400, marginPct: 2.9, marginKopecks: 2309, marginDeltaPct: -6.1,
    impressions: 391323, clicks: 20399, ctrPct: 5.2, baskets: 2600, cartCrPct: 12.7, basketsDeltaPct: -3.1,
    ordersUnits: 86, ordersDeltaPct: -18.4, ordersKopecks: 116155700, salesUnits: 41, salesDeltaPct: -20.6, salesKopecks: 28400000,
    adSpendKopecks: 1039800, drrOrdersPct: 0.9, drrSalesPct: 3.7, netPerUnitKopecks: 2309, netTotalKopecks: 94669,
    logisticsCostPct: 23.9, logisticsDeltaPct: 5.4, commissionCostPct: 38.3, commissionDeltaPct: 2.9, storageCostPct: 2.1, storageDeltaPct: 0.8,
    wbStockUnits: 1060, wbStockKopecks: 127200000, promotionStatus: 'no', abcCode: 'CC', buyoutPct: 41.0,
  },
  {
    sku: 'HBBT_08', nmId: 622460434, photoUrl: wbImage(622460434), productStatus: 'хвост', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Худи',
    priceBeforeSppKopecks: 261000, priceWithSppKopecks: 174870, marginPct: 5.7, marginKopecks: 9899, marginDeltaPct: -2.8,
    impressions: 715832, clicks: 41458, ctrPct: 5.8, baskets: 4396, cartCrPct: 10.6, basketsDeltaPct: -11.7,
    ordersUnits: 83, ordersDeltaPct: -22.0, ordersKopecks: 276389900, salesUnits: 39, salesDeltaPct: -24.2, salesKopecks: 50100000,
    adSpendKopecks: 1481400, drrOrdersPct: 0.5, drrSalesPct: 3.0, netPerUnitKopecks: 9899, netTotalKopecks: 386061,
    logisticsCostPct: 46.8, logisticsDeltaPct: 7.3, commissionCostPct: 8.3, commissionDeltaPct: 0.9, storageCostPct: 2.2, storageDeltaPct: 0.6,
    wbStockUnits: 405, wbStockKopecks: 105705000, promotionStatus: 'yes', abcCode: 'BC', buyoutPct: 38.0,
  },
  {
    sku: 'FCBT_73', nmId: 322457049, photoUrl: wbImage(322457049), productStatus: 'средний', manager: 'Дудина', brand: 'Esereal', category: 'Футболки',
    priceBeforeSppKopecks: 142000, priceWithSppKopecks: 107920, marginPct: 18.5, marginKopecks: 19965, marginDeltaPct: 0.9,
    impressions: 389666, clicks: 28031, ctrPct: 7.2, baskets: 3366, cartCrPct: 12.0, basketsDeltaPct: 4.7,
    ordersUnits: 216, ordersDeltaPct: 3.2, ordersKopecks: 121642700, salesUnits: 143, salesDeltaPct: 1.1, salesKopecks: 141000000,
    adSpendKopecks: 1344200, drrOrdersPct: 1.1, drrSalesPct: 1.0, netPerUnitKopecks: 19965, netTotalKopecks: 2854995,
    logisticsCostPct: 14.4, logisticsDeltaPct: -0.3, commissionCostPct: 16.2, commissionDeltaPct: 0.2, storageCostPct: 0.9, storageDeltaPct: 0.1,
    wbStockUnits: 327, wbStockKopecks: 46434000, promotionStatus: 'no', abcCode: 'BB', buyoutPct: 55.0,
  },
]

const MORE_SKUS: Array<{
  sku: string
  nmId: number
  productStatus: SkuReportRow['productStatus']
  manager: string
  brand: string
  category: string
}> = [
  { sku: 'FBBT_91', nmId: 781240991, productStatus: 'хвост', manager: 'Котельникова', brand: 'Anomie Studio', category: 'Футболки' },
  { sku: 'FCBT_64', nmId: 781240964, productStatus: 'новинка', manager: 'Дудина', brand: 'Esereal', category: 'Футболки' },
  { sku: 'HBBT_27', nmId: 781240927, productStatus: 'локомотив', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Худи' },
  { sku: 'HCBT_31', nmId: 781240931, productStatus: 'средний', manager: 'Светлана', brand: 'Bless T', category: 'Худи' },
  { sku: 'LBBT_44', nmId: 781240944, productStatus: 'неликвид', manager: 'Светлана', brand: 'Bless T', category: 'Лонгсливы' },
  { sku: 'LCBT_12', nmId: 781240912, productStatus: 'средний', manager: 'Котельникова', brand: 'Anomie Studio', category: 'Лонгсливы' },
  { sku: 'FBBT_108', nmId: 781241108, productStatus: 'новинка', manager: 'Дудина', brand: 'Esereal', category: 'Футболки' },
  { sku: 'FCBT_06', nmId: 781240906, productStatus: 'хвост', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Футболки' },
  { sku: 'HBBT_88', nmId: 781240988, productStatus: 'локомотив', manager: 'Светлана', brand: 'Bless T', category: 'Худи' },
  { sku: 'HCBT_52', nmId: 781240952, productStatus: 'средний', manager: 'Котельникова', brand: 'Anomie Studio', category: 'Худи' },
  { sku: 'FBBT_14', nmId: 781240914, productStatus: 'неликвид', manager: 'Дудина', brand: 'Esereal', category: 'Футболки' },
  { sku: 'FCBT_39', nmId: 781240939, productStatus: 'средний', manager: 'Светлана', brand: 'Bless T', category: 'Футболки' },
  { sku: 'LBBT_76', nmId: 781240976, productStatus: 'хвост', manager: 'Воробьева', brand: 'Anomie Studio', category: 'Лонгсливы' },
  { sku: 'LCBT_58', nmId: 781240958, productStatus: 'новинка', manager: 'Котельникова', brand: 'Bless T', category: 'Лонгсливы' },
  { sku: 'FBBT_120', nmId: 781241120, productStatus: 'локомотив', manager: 'Дудина', brand: 'Esereal', category: 'Футболки' },
]

MORE_SKUS.forEach((item, index) => {
  const base = ABC_ROWS[index % ABC_ROWS.length]
  const factor = 0.42 + index * 0.045
  const marginShift = item.productStatus === 'неликвид' ? -9 : item.productStatus === 'новинка' ? -2 : item.productStatus === 'локомотив' ? 5 : -4
  const marginPct = Math.max(1.2, Math.min(34, base.marginPct + marginShift + (index % 3)))
  const priceWithSppKopecks = Math.round(base.priceWithSppKopecks * (0.86 + (index % 5) * 0.06))
  const marginKopecks = Math.round(priceWithSppKopecks * marginPct / 100)
  const ordersUnits = Math.max(2, Math.round(base.ordersUnits * factor))
  const salesUnits = Math.max(1, Math.round(base.salesUnits * factor * 0.86))
  const ordersKopecks = ordersUnits * priceWithSppKopecks
  const salesKopecks = salesUnits * priceWithSppKopecks
  const adSpendKopecks = Math.round(base.adSpendKopecks * (0.45 + (index % 6) * 0.16))
  ABC_ROWS.push({
    ...base,
    ...item,
    photoUrl: wbImage(item.nmId),
    priceBeforeSppKopecks: Math.round(priceWithSppKopecks * 1.42),
    priceWithSppKopecks,
    marginPct,
    marginKopecks,
    marginDeltaPct: Number((base.marginDeltaPct + (index % 5) - 2.4).toFixed(1)),
    impressions: Math.round(base.impressions * (0.5 + (index % 7) * 0.18)),
    clicks: Math.round(base.clicks * (0.46 + (index % 5) * 0.17)),
    ctrPct: Number(Math.max(1.1, base.ctrPct + (index % 4) - 1.5).toFixed(1)),
    baskets: Math.round(base.baskets * (0.35 + (index % 6) * 0.15)),
    cartCrPct: Number(Math.max(3.5, base.cartCrPct + (index % 5) - 2).toFixed(1)),
    basketsDeltaPct: Number((base.basketsDeltaPct + (index % 7) * 2.1 - 6).toFixed(1)),
    ordersUnits,
    ordersDeltaPct: Number((base.ordersDeltaPct + (index % 6) * 1.7 - 5).toFixed(1)),
    ordersKopecks,
    salesUnits,
    salesDeltaPct: Number((base.salesDeltaPct + (index % 6) * 1.5 - 5.5).toFixed(1)),
    salesKopecks,
    adSpendKopecks,
    drrOrdersPct: Number((adSpendKopecks / Math.max(ordersKopecks, 1) * 100).toFixed(1)),
    drrSalesPct: Number((adSpendKopecks / Math.max(salesKopecks, 1) * 100).toFixed(1)),
    netPerUnitKopecks: marginKopecks,
    netTotalKopecks: marginKopecks * salesUnits,
    logisticsCostPct: Number(Math.max(5, base.logisticsCostPct + (index % 8) * 1.8 - 4).toFixed(1)),
    logisticsDeltaPct: Number((base.logisticsDeltaPct + (index % 5) - 2).toFixed(1)),
    commissionCostPct: Number(Math.max(4, base.commissionCostPct + (index % 4) * 1.4).toFixed(1)),
    commissionDeltaPct: Number((base.commissionDeltaPct + (index % 4) - 1.2).toFixed(1)),
    storageCostPct: Number(Math.max(0.2, base.storageCostPct + (index % 5) * 0.25).toFixed(1)),
    storageDeltaPct: Number((base.storageDeltaPct + (index % 5) * 0.2).toFixed(1)),
    wbStockUnits: Math.max(0, Math.round(base.wbStockUnits * (0.25 + (index % 9) * 0.12))),
    wbStockKopecks: Math.max(0, Math.round(base.wbStockUnits * (0.25 + (index % 9) * 0.12)) * priceWithSppKopecks),
    promotionStatus: index % 3 === 0 ? 'yes' : 'no',
    abcCode: 'CC',
    buyoutPct: Number(Math.max(28, Math.min(72, base.buyoutPct + (index % 7) * 2 - 6)).toFixed(1)),
  })
})

ABC_ROWS.forEach((row, index) => {
  row.abcCode = abcByRank(index + 1)
  row.cogsKopecks = cogsByCategory(row.category)
  Object.assign(row, assignmentFor(row))
})

export const ABC_COLUMNS: TableColumn[] = [
  { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
  { key: 'sku', label: 'Наш артикул', sticky: true },
  { key: 'nmId', label: 'Артикул WB', format: 'wb-link', sticky: true },
  { key: 'abcCode', label: 'ABC', format: 'abc', align: 'center' },
  { key: 'productStatus', label: 'Статус' },
  { key: 'promotionStatus', label: 'Акция', format: 'promotion', align: 'center' },
  { key: 'manager', label: 'Менеджер' },
  { key: 'priceBeforeSppKopecks', label: 'Цена до СПП', format: 'currency', align: 'right' },
  { key: 'priceWithSppKopecks', label: 'Цена с СПП', format: 'currency', align: 'right' },
  { key: 'cogsKopecks', label: 'Себестоимость', format: 'currency', align: 'right' },
  { key: 'marginPct', label: 'Маржа %', format: 'percent', align: 'right' },
  { key: 'marginKopecks', label: 'Маржа руб', format: 'currency', align: 'right' },
  { key: 'marginDeltaPct', label: 'Дин. маржи', format: 'percent', align: 'right' },
  { key: 'impressions', label: 'Показы', format: 'number', align: 'right' },
  { key: 'clicks', label: 'Клики', format: 'number', align: 'right' },
  { key: 'ctrPct', label: 'CTR', format: 'percent', align: 'right' },
  { key: 'baskets', label: 'Корзины', format: 'number', align: 'right' },
  { key: 'cartCrPct', label: 'CR корзин', format: 'percent', align: 'right' },
  { key: 'basketsDeltaPct', label: 'Дин. корзин', format: 'percent', align: 'right' },
  { key: 'ordersUnits', label: 'Заказы шт', format: 'number', align: 'right' },
  { key: 'ordersDeltaPct', label: 'Дин. заказов', format: 'percent', align: 'right' },
  { key: 'ordersKopecks', label: 'Заказы руб', format: 'currency', align: 'right' },
  { key: 'ordersComposite', label: 'Заказы шт/руб/динамика', align: 'right' },
  { key: 'salesUnits', label: 'Продажи шт', format: 'number', align: 'right' },
  { key: 'salesDeltaPct', label: 'Дин. продаж', format: 'percent', align: 'right' },
  { key: 'salesKopecks', label: 'Продажи руб', format: 'currency', align: 'right' },
  { key: 'salesComposite', label: 'Продажи шт/руб/динамика', align: 'right' },
  { key: 'adSpendKopecks', label: 'Реклама', format: 'currency', align: 'right' },
  { key: 'drrOrdersPct', label: 'ДРР заказов', format: 'percent', align: 'right' },
  { key: 'drrSalesPct', label: 'ДРР продаж', format: 'percent', align: 'right' },
  { key: 'netPerUnitKopecks', label: 'Чистая/шт', format: 'currency', align: 'right' },
  { key: 'netTotalKopecks', label: 'Чистая/SKU', format: 'currency', align: 'right' },
  { key: 'logisticsCostPct', label: '% логистика', format: 'percent', align: 'right' },
  { key: 'logisticsDeltaPct', label: 'Дин. логистики', format: 'percent', align: 'right', defaultVisible: false },
  { key: 'commissionCostPct', label: '% комиссия', format: 'percent', align: 'right' },
  { key: 'commissionDeltaPct', label: 'Дин. комиссии', format: 'percent', align: 'right', defaultVisible: false },
  { key: 'storageCostPct', label: '% хранение', format: 'percent', align: 'right' },
  { key: 'storageDeltaPct', label: 'Дин. хранения', format: 'percent', align: 'right', defaultVisible: false },
  { key: 'wbStockUnits', label: 'Остаток WB шт', format: 'number', align: 'right' },
  { key: 'wbStockKopecks', label: 'Остаток WB руб', format: 'currency', align: 'right' },
]

const ALERTS: ReportAlert[] = [
  {
    id: 'abc-cc',
    alertType: 'abc_loss',
    severity: 'critical',
    entityType: 'sku',
    entityId: 'LBBT_03',
    title: 'LBBT_03 попал в CC',
    details: 'Слабые продажи и почти нулевая предварительная прибыль после рекламы, логистики и хранения.',
    createdAt: '2026-05-07T08:05:00.000+05:00',
    resolvedAt: null,
    route: '/wb/reports/abc',
  },
  {
    id: 'ads-drr',
    alertType: 'ads_drr',
    severity: 'warning',
    entityType: 'sku',
    entityId: 'FBBT_55',
    title: 'ДРР по FBBT_55 выше порога профиля',
    details: 'Рекламные расходы выше чистой прибыли за период.',
    createdAt: '2026-05-07T08:04:00.000+05:00',
    resolvedAt: null,
    route: '/wb/reports/ads',
  },
]

function planFactStatus(planKopecks: number | null, factKopecks: number | null, completionPct: number | null, unallocatedCostKopecks = 0): PlanFactRow['status'] {
  if (unallocatedCostKopecks > 0) return 'unallocated_costs'
  if (planKopecks == null) return 'no_plan'
  if (factKopecks == null) return 'no_fact'
  if ((completionPct ?? 0) >= 86) return 'ok'
  if ((completionPct ?? 0) >= 80) return 'watch'
  return 'risk'
}

function buildPlanFactRows(dateRange: DateRange): PlanFactRow[] {
  const adsRows = adsCampaignRows()
  const unallocatedCostKopecks = sum(adsRows.filter((row) => row.attributionLevel === 'campaign_only').map((row) => row.adSpendKopecks))
  const allFactKopecks = sum(ABC_ROWS.map((row) => row.netTotalKopecks))
  const companyMonthlyPlanKopecks = sum(MANAGERS.map((manager) => manager.monthlyPlanKopecks ?? 0))
  const companyPlanKopecks = periodPlan(companyMonthlyPlanKopecks, dateRange)
  const companyCompletionPct = companyPlanKopecks ? Number((allFactKopecks / companyPlanKopecks * 100).toFixed(1)) : null
  const remainingDays = Math.max(1, daysInMonth(dateRange) - daysInRange(dateRange))
  const companyRow: PlanFactRow = {
    owner: 'company',
    ownerId: 'company',
    name: 'Компания',
    planKopecks: companyPlanKopecks,
    factKopecks: allFactKopecks,
    completionPct: companyCompletionPct,
    forecastKopecks: Math.round(allFactKopecks / Math.max(daysInRange(dateRange), 1) * daysInMonth(dateRange)),
    deltaPct: companyCompletionPct == null ? null : Number((companyCompletionPct - 100).toFixed(1)),
    needPerDayKopecks: companyPlanKopecks == null ? null : Math.max(0, Math.round((companyPlanKopecks - allFactKopecks) / remainingDays)),
    status: planFactStatus(companyPlanKopecks, allFactKopecks, companyCompletionPct, unallocatedCostKopecks),
    factFreshness: 'preliminary',
    unallocatedCostKopecks,
  }
  const managerRows = MANAGERS
    .filter((manager) => manager.active)
    .sort((a, b) => a.order - b.order)
    .map<PlanFactRow>((manager) => {
      const rows = ABC_ROWS.filter((row) => row.managerId === manager.id)
      const factKopecks = rows.length ? sum(rows.map((row) => row.netTotalKopecks)) : null
      const planKopecks = periodPlan(manager.monthlyPlanKopecks, dateRange)
      const completionPct = planKopecks && factKopecks != null ? Number((factKopecks / planKopecks * 100).toFixed(1)) : null
      return {
        owner: 'manager',
        ownerId: manager.id,
        name: manager.name,
        planKopecks,
        factKopecks,
        completionPct,
        forecastKopecks: factKopecks == null ? null : Math.round(factKopecks / Math.max(daysInRange(dateRange), 1) * daysInMonth(dateRange)),
        deltaPct: completionPct == null ? null : Number((completionPct - 100).toFixed(1)),
        needPerDayKopecks: planKopecks == null || factKopecks == null ? null : Math.max(0, Math.round((planKopecks - factKopecks) / remainingDays)),
        status: planFactStatus(planKopecks, factKopecks, completionPct),
        factFreshness: manager.id === 'manager-irina' ? 'stale' : 'preliminary',
      }
    })
  return [companyRow, ...managerRows]
}

const SKU_COMMENTS: SkuComment[] = []

const REPORT_AUDIT_EVENTS: ReportAuditEvent[] = [
  { id: 'audit-001', sku: 'FBBT_42', actor: 'system', actorType: 'system', createdAt: '2026-05-08T08:15:00+05:00', text: 'Автоматически пересчитаны ABC, РНП и складской риск за период.' },
  { id: 'audit-002', sku: 'LBBT_03', actor: 'Ирина', actorType: 'manager', createdAt: '2026-05-08T08:46:00+05:00', text: 'Менеджер оставил комментарий по низкому CR и высокой логистике.' },
]

function adsCampaignRows(): AdsCampaignRow[] {
  return ABC_ROWS.slice(0, 12).map((row, index) => {
    const campaignType: AdsCampaignRow['campaignType'] = index % 4 === 0 ? 'search' : index % 4 === 1 ? 'catalog' : index % 4 === 2 ? 'shelf' : 'media'
    const campaignName = index % 4 === 3 ? 'Весенняя распродажа' : `${row.category} · ${row.sku}`
    const attributionLevel: AdsCampaignRow['attributionLevel'] = index % 6 === 0 ? 'campaign_only' : index % 3 === 0 ? 'campaign_sku' : 'exact_sku'
    const attributionSource: AdsCampaignRow['attributionSource'] =
      attributionLevel === 'exact_sku' ? 'wb_ads_nm'
        : attributionLevel === 'campaign_sku' ? (index % 2 === 0 ? 'campaign_product_list' : 'manual_mapping')
          : 'campaign_name_match'
    const attributionConfidencePct = attributionLevel === 'exact_sku' ? 96 : attributionLevel === 'campaign_sku' ? 78 : 48
    const observationDays = index % 4 === 1 ? 14 : 21 + (index % 5) * 3
    const hasOosInPeriod = index % 7 === 2
    const isNewSku = row.productStatus === 'новинка'
    const isPromoOrLiquidation = row.promotionStatus === 'yes' || row.productStatus === 'ликвидация'
    const adSpendMultiplier = row.productStatus === 'хвост' || row.productStatus === 'неликвид' ? 8.5 : 0.74 + index * 0.03
    const adSpendKopecks = Math.round(row.adSpendKopecks * adSpendMultiplier)
    const drrPct = Number((adSpendKopecks / Math.max(row.salesKopecks, 1) * 100).toFixed(1))
    const minSpendMet = adSpendKopecks >= ADS_DRAFT_STOP_MIN_SPEND_KOPECKS
    const attributionAllowed = attributionLevel !== 'campaign_only'
    const stopAllowed =
      observationDays >= ADS_DRAFT_STOP_MIN_OBSERVATION_DAYS
      && drrPct >= ADS_DRAFT_STOP_DRR_THRESHOLD_PCT
      && minSpendMet
      && !hasOosInPeriod
      && !isNewSku
      && !isPromoOrLiquidation
      && attributionAllowed
    const shouldReview = !stopAllowed && (drrPct >= 14 || !attributionAllowed || hasOosInPeriod)
    const recommendation: AdsCampaignRow['recommendation'] = stopAllowed ? 'draft_stop' : shouldReview ? 'review' : 'keep'
    const recommendationReason = stopAllowed
      ? `Статус правила: кандидат · черновик. Период ${observationDays} дн., ДРР ${drrPct}%, расход ${formatRub(adSpendKopecks)}, атрибуция ${attributionConfidencePct}%.`
      : shouldReview
        ? `Статус правила: на проверку. ${[
            drrPct >= 14 ? `ДРР ${drrPct}%` : '',
            !attributionAllowed ? 'нет SKU-точной атрибуции' : '',
            hasOosInPeriod ? 'были дни OOS' : '',
            observationDays < ADS_DRAFT_STOP_MIN_OBSERVATION_DAYS ? `история ${observationDays} дн.` : '',
            isNewSku ? 'новинка' : '',
            isPromoOrLiquidation ? 'акция/ликвидация' : '',
          ].filter(Boolean).join(', ')}`
        : 'В пределах порогов профиля: ДРР и воронка в допустимом диапазоне.'
    return {
      campaignId: `rk-${String(8400 + index).padStart(5, '0')}`,
      campaignName,
      campaignType,
      attributionLevel,
      attributionSource,
      attributionConfidencePct,
      photoUrl: row.photoUrl,
      productName: `${row.category.slice(0, -1)} ${row.sku}`,
      category: row.category,
      managerId: row.managerId ?? null,
      manager: row.manager,
      sku: row.sku,
      nmId: row.nmId,
      observationDays,
      impressions: row.impressions,
      clicks: row.clicks,
      ctrPct: row.ctrPct,
      baskets: row.baskets,
      orders: composite(row.ordersUnits, row.ordersKopecks, row.ordersDeltaPct),
      sales: composite(row.salesUnits, row.salesKopecks, row.salesDeltaPct),
      adSpendKopecks,
      drrPct,
      minSpendMet,
      hasOosInPeriod,
      isNewSku,
      isPromoOrLiquidation,
      recommendation,
      recommendationStatus: recommendation === 'keep' ? 'confirmed' : 'draft',
      recommendationReason,
    }
  })
}

function stockWarehouseReportRows(): StockWarehouseRow[] {
  const warehouses = ['Коледино', 'Электросталь', 'Краснодар', 'Казань', 'Екатеринбург', 'Санкт-Петербург']
  const clusters = ['Центр', 'Центр', 'Юг', 'Поволжье', 'Урал', 'СЗФО']
  return ABC_ROWS.slice(0, 15).map((row, index) => {
    const wbStockUnits = Math.max(0, Math.round(row.wbStockUnits / (8 + index % 5)))
    const fromClientUnits = index % 4 === 0 ? 6 + index : index % 3
    const toClientUnits = index % 5 === 0 ? 3 + index : index % 2
    const availableUnits = wbStockUnits + fromClientUnits
    const ordersPerDay = Number(Math.max(0.2, row.ordersUnits / 7 / (4 + index % 3)).toFixed(1))
    const daysToOos = Math.round(availableUnits / Math.max(ordersPerDay, 0.2))
    const totalClusterOrders = Math.max(1, Math.round(row.ordersUnits / (4 + index % 3)))
    const localOrders = Math.max(0, Math.round(totalClusterOrders * Math.max(0.04, Math.min(0.98, 0.92 - (index % 8) * 0.06))))
    const localizationPct = calculateLocalizationPct(localOrders, totalClusterOrders)
    const coefficients = localizationCoefficients(localizationPct)
    const ktrIndex = coefficients.territorialCoefficient
    const decision: StockWarehouseRow['decision'] = daysToOos < 7 ? 'дозагрузить' : daysToOos > 60 ? 'держать' : 'норма'
    return {
      sku: row.sku,
      nmId: row.nmId,
      photoUrl: row.photoUrl,
      productName: row.category,
      warehouseName: warehouses[index % warehouses.length],
      clusterName: clusters[index % clusters.length],
      wbStockUnits,
      fromClientUnits,
      toClientUnits,
      availableUnits,
      ordersPerDay,
      daysToOos,
      ktrIndex,
      localizationPct,
      salesDistributionCoefficient: coefficients.salesDistributionCoefficient,
      logisticsPerUnitKopecks: 5800 + (index % 8) * 900,
      decision,
      decisionStatus: 'draft',
    }
  })
}

function rangeDates(dateRange: DateRange): string[] {
  const from = new Date(`${dateRange.from}T00:00:00.000Z`)
  const to = new Date(`${dateRange.to}T00:00:00.000Z`)
  const dates: string[] = []
  for (const day = new Date(from); day <= to; day.setUTCDate(day.getUTCDate() + 1)) {
    dates.push(day.toISOString().slice(0, 10))
  }
  return dates
}

export function getStockDailySnapshots(dateRange: DateRange = DEFAULT_RANGE): StockDailySnapshot[] {
  const dates = rangeDates(dateRange).slice(-30)
  return stockWarehouseReportRows().flatMap((row, rowIndex) => dates.map((snapshotDate, dayIndex) => {
    const plannedOutage = rowIndex % 5 === 0 && dayIndex > 2 && dayIndex < 6
    const availableUnits = plannedOutage ? 0 : row.availableUnits
    return {
      snapshotDate,
      sku: row.sku,
      nmId: row.nmId,
      warehouseName: row.warehouseName,
      clusterName: row.clusterName,
      wbStockUnits: plannedOutage ? 0 : row.wbStockUnits,
      fromClientUnits: plannedOutage ? 0 : row.fromClientUnits,
      toClientUnits: row.toClientUnits,
      availableUnits,
      wasOutOfStock: availableUnits <= 0,
      source: 'wb_stocks_report',
      sourceUpdatedAt: `${snapshotDate}T08:00:00.000+05:00`,
    }
  }))
}

function stockHistoryForSku(snapshots: StockDailySnapshot[], sku: string, dateRange: DateRange) {
  const dates = rangeDates(dateRange).slice(-7)
  return dates.map((date) => {
    const daySnapshots = snapshots.filter((snapshot) => snapshot.sku === sku && snapshot.snapshotDate === date)
    if (daySnapshots.length === 0) return null
    return daySnapshots.some((snapshot) => snapshot.availableUnits > 0)
  })
}

function weekOverWeekRows(dateRange: DateRange = DEFAULT_RANGE): WeekOverWeekRow[] {
  const snapshots = getStockDailySnapshots(dateRange)
  return ABC_ROWS.slice(0, 14).map((row, index) => {
    const stockAvailability7d = stockHistoryForSku(snapshots, row.sku, dateRange)
    const knownDays = stockAvailability7d.filter((item): item is boolean => item !== null)
    const stockOutDays = knownDays.filter((item) => !item).length
    const wasOutOfStock = stockOutDays > 0
    const coveragePct = stockAvailability7d.length === 0 ? 0 : Math.round((knownDays.length / stockAvailability7d.length) * 100)
    return {
      sku: row.sku,
      photoUrl: row.photoUrl,
      productName: row.category,
      productStatus: row.productStatus,
      abcCode: row.abcCode,
      orders: composite(row.ordersUnits, row.ordersKopecks, row.ordersDeltaPct),
      sales: composite(row.salesUnits, row.salesKopecks, row.salesDeltaPct),
      baskets: { units: row.baskets, unitsLabel: 'корз.', deltaPct: row.basketsDeltaPct, deltaLabel: `${row.basketsDeltaPct > 0 ? '+' : ''}${row.basketsDeltaPct.toFixed(1)}%` },
      marginPct: { percent: row.marginPct, deltaPct: row.marginDeltaPct, deltaLabel: `${row.marginDeltaPct > 0 ? '+' : ''}${row.marginDeltaPct.toFixed(1)} п.п.` },
      profit: { kopecks: row.netTotalKopecks, deltaPct: row.marginDeltaPct + index % 4 - 1.5, deltaLabel: `${row.marginDeltaPct > 0 ? '+' : ''}${row.marginDeltaPct.toFixed(1)}%` },
      wasOutOfStock,
      stockAvailability7d: stockAvailability7d.map(Boolean),
      stockOutDays,
      stockSnapshotCoveragePct: coveragePct,
      stockSnapshotSource: 'daily snapshots 08:00',
      conclusion: wasOutOfStock ? `${stockOutDays} дн. ОС, сравнение продаж искажено` : row.marginDeltaPct < 0 ? 'маржа ниже предыдущего периода' : 'в пределах порогов периода',
    }
  })
}

function freshnessMessage(state: FreshnessState, label: string) {
  if (state === 'fresh') return `${label} обновлены`
  if (state === 'partial') return `${label} частично обновлены: часть источников WB догружается`
  if (state === 'pending_financial') return `${label} ждёт еженедельный финансовый отчёт WB`
  return `${label} устарели`
}

function freshness(id: string, label: string, state: FreshnessState, sourceType: FreshnessItem['sourceType'], updatedAt = LAST_OPERATIONAL_UPDATE): FreshnessItem {
  return { id, label, state, sourceType, updatedAt, message: freshnessMessage(state, label) }
}

function baseMeta(id: ReportId, title: string, description: string, sourceType: 'operational' | 'financial' = 'operational', freshnessState: FreshnessState = 'fresh') {
  return {
    id,
    title,
    description,
    sourceType,
    freshnessState,
    lastUpdatedAt: sourceType === 'financial' ? LAST_FINANCIAL_UPDATE : LAST_OPERATIONAL_UPDATE,
  }
}

function kpis(rows: SkuReportRow[]): ReportKpi[] {
  const revenue = sum(rows.map((row) => row.ordersKopecks))
  const sales = sum(rows.map((row) => row.salesKopecks))
  const profit = sum(rows.map((row) => row.netTotalKopecks))
  const adSpend = sum(rows.map((row) => row.adSpendKopecks))
  const baskets = sum(rows.map((row) => row.baskets))
  const orders = sum(rows.map((row) => row.ordersUnits))
  const marginPct = profit / Math.max(sales, 1) * 100
  const promoPct = rows.filter((row) => row.promotionStatus === 'yes').length / rows.length * 100

  return [
    { id: 'revenue', label: 'Заказы руб', value: formatRub(revenue), delta: delta(5.8) },
    { id: 'orders', label: 'Заказы шт', value: orders.toLocaleString('ru-RU'), delta: delta(2.9) },
    { id: 'sales', label: 'Продажи руб', value: formatRub(sales), delta: delta(4.1) },
    { id: 'profit', label: 'Предв. прибыль', value: formatRub(profit), hint: 'Черновой показатель: P&L к закрытию ждёт WB-12/WB-13/WB-24.', delta: delta(-1.8) },
    { id: 'margin', label: 'Маржа', value: formatPercent(marginPct), delta: delta(-0.7, ' п.п.') },
    { id: 'baskets', label: 'Корзины', value: baskets.toLocaleString('ru-RU'), delta: delta(6.4) },
    { id: 'promo', label: 'В акциях', value: formatPercent(promoPct), hint: EMPTY_PROMO_FILE_NOTE },
    { id: 'ads', label: 'Реклама', value: formatRub(adSpend), delta: delta(9.7, '%', false) },
  ]
}

function chartFromRows(title: string, valueLabel: string, rows: SkuReportRow[], key: keyof SkuReportRow): ReportChartData {
  return {
    title,
    valueLabel,
    xAxisLabel: 'SKU',
    yAxisLabel: valueLabel,
    points: rows.slice(0, 7).map((row) => ({
      label: row.sku,
      value: Number(row[key] ?? 0),
      compareValue: Number(row[key] ?? 0) * 0.92,
    })),
  }
}

function aggregateRows(rows: SkuReportRow[], groupBy: ReportGroupBy): TableRow[] {
  if (groupBy === 'sku') {
    return rows.map((row) => ({
      ...row,
      ordersComposite: composite(row.ordersUnits, row.ordersKopecks, row.ordersDeltaPct),
      salesComposite: composite(row.salesUnits, row.salesKopecks, row.salesDeltaPct),
    }))
  }
  const grouped = new Map<string, SkuReportRow[]>()
  for (const row of rows) {
    const key = groupBy === 'manager' ? (row.managerId ?? 'unassigned') : groupBy === 'brand' ? row.brand : groupBy === 'category' ? row.category : groupBy === 'status' ? row.productStatus : 'WB'
    grouped.set(key, [...(grouped.get(key) ?? []), row])
  }
  return Array.from(grouped.entries()).map(([key, items]) => ({
    managerId: groupBy === 'manager' ? (items[0]?.managerId ?? null) : undefined,
    manager: groupBy === 'manager' ? (items[0]?.manager ?? UNASSIGNED_MANAGER_LABEL) : undefined,
    sku: groupBy === 'manager' ? (items[0]?.manager ?? UNASSIGNED_MANAGER_LABEL) : key,
    productStatus: groupBy,
    cogsKopecks: sum(items.map((item) => item.cogsKopecks ?? 0)),
    ordersKopecks: sum(items.map((item) => item.ordersKopecks)),
    ordersUnits: sum(items.map((item) => item.ordersUnits)),
    salesKopecks: sum(items.map((item) => item.salesKopecks)),
    salesUnits: sum(items.map((item) => item.salesUnits)),
    ordersComposite: composite(
      sum(items.map((item) => item.ordersUnits)),
      sum(items.map((item) => item.ordersKopecks)),
      avg(items.map((item) => item.ordersDeltaPct)),
    ),
    salesComposite: composite(
      sum(items.map((item) => item.salesUnits)),
      sum(items.map((item) => item.salesKopecks)),
      avg(items.map((item) => item.salesDeltaPct)),
    ),
    baskets: sum(items.map((item) => item.baskets)),
    adSpendKopecks: sum(items.map((item) => item.adSpendKopecks)),
    netTotalKopecks: sum(items.map((item) => item.netTotalKopecks)),
    marginPct: avg(items.map((item) => item.marginPct)),
    wbStockUnits: sum(items.map((item) => item.wbStockUnits)),
  }))
}

export function getAbcReport(dateRange: DateRange = DEFAULT_RANGE, groupBy: ReportGroupBy = 'sku'): ReportResponse {
  const rows = [...ABC_ROWS].sort((a, b) => b.netTotalKopecks - a.netTotalKopecks)
  const report: ReportResponse = {
    meta: baseMeta('abc', 'ABC-анализ', 'Главный SKU-отчёт Марии: продажи, предварительная прибыль, реклама, остатки и акция в одной таблице.'),
    headline: 'ABC считается двумя буквами: первая по продажам, вторая по предварительной прибыли; финальная прибыль ждёт WB-12/WB-13/WB-24.',
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange, groupBy },
    kpis: kpis(rows),
    chart: chartFromRows('Предварительная прибыль по SKU', 'Предв. прибыль, руб', rows, 'netTotalKopecks'),
    columns: groupBy === 'sku' ? ABC_COLUMNS : [
      { key: 'sku', label: 'Группа', sticky: true },
      { key: 'cogsKopecks', label: 'Себестоимость', format: 'currency', align: 'right' },
      { key: 'ordersUnits', label: 'Заказы шт', format: 'number', align: 'right' },
      { key: 'ordersComposite', label: 'Заказы шт/руб/динамика', align: 'right' },
      { key: 'ordersKopecks', label: 'Заказы руб', format: 'currency', align: 'right' },
      { key: 'salesUnits', label: 'Продажи шт', format: 'number', align: 'right' },
      { key: 'salesComposite', label: 'Продажи шт/руб/динамика', align: 'right' },
      { key: 'salesKopecks', label: 'Продажи руб', format: 'currency', align: 'right' },
      { key: 'netTotalKopecks', label: 'Предв. прибыль', format: 'currency', align: 'right' },
      { key: 'marginPct', label: 'Маржа', format: 'percent', align: 'right' },
      { key: 'baskets', label: 'Корзины', format: 'number', align: 'right' },
      { key: 'adSpendKopecks', label: 'Реклама', format: 'currency', align: 'right' },
      { key: 'wbStockUnits', label: 'Остаток WB', format: 'number', align: 'right' },
    ],
    rows: aggregateRows(rows, groupBy),
  }
  assertReportContract('abc', report, { dateRange, groupBy })
  return report
}

export function getDigestReport(dateRange: DateRange = DEFAULT_RANGE): DigestResponse {
  const oosRows = ABC_ROWS.filter((row) => row.wbStockUnits <= 0).slice(0, 8)
  const oosProblemRow: DigestProblemRow | null = oosRows.length > 0 ? {
    id: 'oos-risk',
    kind: 'oos_risk',
    title: `${oosRows.length} SKU с риском OOS`,
    details: `Товары, у которых нулевой доступный остаток: ${oosRows.map((row) => row.sku).slice(0, 5).join(', ')}${oosRows.length > 5 ? '...' : ''}`,
    metric: 'Остатки',
    reason: 'oos_risk',
    recommendation: 'Проверить поставку и остатки WB',
    skuCount: oosRows.length,
    affectedItems: oosRows.map((row) => ({
      sku: row.sku,
      nmId: row.nmId,
      warehouseName: 'Все склады WB',
      availableUnits: 0,
      wbStockUnits: row.wbStockUnits,
      fromClientUnits: 0,
      toClientUnits: null,
      reason: 'Доступный остаток 0 шт',
    })),
  } : null
  const problemRows: DigestProblemRow[] = [
    ...(oosProblemRow ? [oosProblemRow] : []),
    ...ABC_ROWS.filter((row) => row.abcCode.includes('C') || row.marginPct < 8 || row.drrSalesPct > 2.5),
  ]
  const planFactRows = buildPlanFactRows(dateRange)
  const digestKpis = kpis(ABC_ROWS)
  const digestSales = digestKpis.find((item) => item.id === 'sales')
  const digestOrders = digestKpis.find((item) => item.id === 'orders')
  const digestProfit = digestKpis.find((item) => item.id === 'profit')
  const digestMargin = digestKpis.find((item) => item.id === 'margin')
  const digestBaskets = digestKpis.find((item) => item.id === 'baskets')
  const digestPromo = digestKpis.find((item) => item.id === 'promo')
  const digestAds = digestKpis.find((item) => item.id === 'ads')
  return {
    meta: baseMeta('digest', 'WB-витрина', 'Единый экран с ключевыми показателями из ABC, P&L, РНП, рекламы и остатков.'),
    headline: 'Период: предварительная прибыль, реклама, логистика и хвостовые SKU показаны относительно порогов профиля.',
    dateRange,
    kpis: [
      { id: 'orders_qty', label: 'Заказы, шт', value: digestOrders?.value ?? '0', hint: 'Количество заказанных товаров за выбранный период. Если воронка WB недоступна, берём поток заказов WB Statistics.' },
      { id: 'sales_revenue', label: 'Выкупили на сумму', value: digestSales?.value ?? formatRub(0), hint: 'Сумма выкупленных товаров за выбранный период. Если воронка WB недоступна, берём сумму продаж из WB Statistics.' },
      { id: 'margin_profit', label: 'Марж. прибыль', value: digestProfit?.value ?? formatRub(0), hint: 'Предварительная прибыль после удержаний WB. Формула: seller payout - комиссии WB - логистика - штрафы - приемка - хранение. Себестоимость, реклама, налоги и прочие расходы здесь не вычтены.' },
      { id: 'oos_risk', label: 'OOS риск', value: `${oosRows.length} SKU`, hint: 'Товары с нулевым доступным остатком: остаток WB + возвраты от клиента = 0. Такие позиции могут перестать продаваться, пока не появится доступный остаток.' },
      ...(digestMargin ? [digestMargin] : []),
      ...(digestBaskets ? [digestBaskets] : []),
      ...(digestPromo ? [digestPromo] : []),
      ...(digestAds ? [digestAds] : []),
    ],
    planFactRows,
    freshness: [
      freshness('abc', 'ABC / Воронка', 'fresh', 'operational'),
      freshness('ads', 'Реклама', 'fresh', 'operational'),
      freshness('stock', 'Остатки WB', 'fresh', 'operational'),
      freshness('pnl', 'P&L', 'pending_financial', 'financial', LAST_FINANCIAL_UPDATE),
    ],
    alerts: ALERTS,
    charts: [
      {
        title: 'План-факт маржинальной прибыли',
        valueLabel: 'Факт, руб',
        compareLabel: 'План, руб',
        xAxisLabel: 'Ответственный',
        yAxisLabel: 'Предварительная прибыль',
        points: planFactRows.map((row) => ({
          label: row.name,
          value: row.factKopecks ?? 0,
          compareValue: row.planKopecks ?? 0,
        })),
      },
      chartFromRows('Предварительная прибыль по SKU', 'Предв. прибыль, руб', ABC_ROWS, 'netTotalKopecks'),
    ],
    problemRows,
    quickLinks: [
      { title: 'ABC-анализ', description: 'Основная таблица Марии по SKU.', href: '/wb/reports/abc' },
      { title: 'РНП', description: 'Неделя-к-неделе по воронке и рекламе.', href: '/wb/reports/rnp' },
      { title: 'Реклама', description: 'Расходы, ДРР и ROI по SKU.', href: '/wb/reports/ads' },
      { title: 'Остатки WB', description: 'Склады, рубли и риск out of stock.', href: '/wb/reports/stock' },
    ],
  }
}

export function getRnpReport(dateRange: DateRange = DEFAULT_RANGE, groupBy: ReportGroupBy = 'sku'): ReportResponse {
  const columns: TableColumn[] = [
    { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
    { key: 'sku', label: 'Артикул', sticky: true },
    { key: 'productStatus', label: 'Тег' },
    { key: 'manager', label: 'Менеджер' },
    { key: 'activeRule', label: 'Правило репрайсера' },
    { key: 'impressions', label: 'Показы', format: 'number', align: 'right' },
    { key: 'impressionsDeltaPct', label: 'Дин. показов', format: 'percent', align: 'right' },
    { key: 'clicks', label: 'Клики', format: 'number', align: 'right' },
    { key: 'clicksDeltaPct', label: 'Дин. кликов', format: 'percent', align: 'right' },
    { key: 'ctrPct', label: 'CTR', format: 'percent', align: 'right' },
    { key: 'baskets', label: 'Корзины', format: 'number', align: 'right' },
    { key: 'basketsDeltaPct', label: 'Дин. корзин', format: 'percent', align: 'right' },
    { key: 'cartCrPct', label: 'CR корзин', format: 'percent', align: 'right' },
    { key: 'ordersKopecks', label: 'Заказы руб', format: 'currency', align: 'right' },
    { key: 'ordersUnits', label: 'Заказы шт', format: 'number', align: 'right' },
    { key: 'ordersComposite', label: 'Заказы шт/руб/динамика', align: 'right' },
    { key: 'salesComposite', label: 'Продажи шт/руб/динамика', align: 'right' },
    { key: 'buyoutPct', label: '% выкупа', format: 'percent', align: 'right' },
    { key: 'adSpendKopecks', label: 'Реклама', format: 'currency', align: 'right' },
    { key: 'adSpendDeltaPct', label: 'Дин. рекламы', format: 'percent', align: 'right' },
    { key: 'drrOrdersPct', label: 'ДРР', format: 'percent', align: 'right' },
    { key: 'netTotalKopecks', label: 'Маржа', format: 'currency', align: 'right' },
  ]
  const rules = ['Динамика корзин', 'Ночная медиана', 'Консервативный', 'Запуск новинки']
  const rows = ABC_ROWS.map((row, index) => ({
    ...row,
    activeRule: rules[index % rules.length],
    impressionsDeltaPct: Number((row.basketsDeltaPct * 0.6).toFixed(1)),
    clicksDeltaPct: Number((row.ordersDeltaPct * 0.8).toFixed(1)),
    ordersComposite: composite(row.ordersUnits, row.ordersKopecks, row.ordersDeltaPct),
    salesComposite: composite(row.salesUnits, row.salesKopecks, row.salesDeltaPct),
    adSpendDeltaPct: Number((row.drrSalesPct > 2.5 ? 12.4 : -3.1).toFixed(1)),
  }))
  const groupColumns: TableColumn[] = [
    { key: 'sku', label: 'Группа', sticky: true },
    { key: 'ordersComposite', label: 'Заказы шт/руб/динамика', align: 'right' },
    { key: 'salesComposite', label: 'Продажи шт/руб/динамика', align: 'right' },
    { key: 'baskets', label: 'Корзины', format: 'number', align: 'right' },
    { key: 'adSpendKopecks', label: 'Реклама', format: 'currency', align: 'right' },
    { key: 'netTotalKopecks', label: 'Маржа', format: 'currency', align: 'right' },
    { key: 'marginPct', label: 'Маржа %', format: 'percent', align: 'right' },
  ]
  const report: ReportResponse = {
    meta: baseMeta('rnp', 'РНП', 'Рука на пульсе без ручного Google Sheets: воронка, реклама, маржа и ROI по SKU.'),
    headline: 'РНП показывает строки ниже порогов выбранного профиля за выбранный период.',
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange, groupBy },
    kpis: kpis(ABC_ROWS),
    chart: chartFromRows('Воронка: показы → корзины', 'Корзины', ABC_ROWS, 'baskets'),
    columns: groupBy === 'sku' ? columns : groupColumns,
    rows: groupBy === 'sku' ? rows : aggregateRows(rows, groupBy),
  }
  assertReportContract('rnp', report, { dateRange, groupBy })
  return report
}

export function getAdsReport(dateRange: DateRange = DEFAULT_RANGE): ReportResponse {
  const rows = adsCampaignRows()
  const report: ReportResponse = {
    meta: baseMeta('ads', 'Реклама', 'SKU-first отчёт по рекламным расходам, ДРР и эффективности кампаний.'),
    headline: 'Строка начинается с позиции, рекламная кампания показана рядом как источник расхода.',
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange },
    kpis: kpis(ABC_ROWS),
    chart: {
      title: 'Рекламные расходы по РК',
      valueLabel: 'Расход, руб',
      points: rows.slice(0, 7).map((row) => ({
        label: row.campaignName,
        value: row.adSpendKopecks,
        compareValue: row.adSpendKopecks * 0.88,
      })),
    },
    columns: [
      { key: 'photoUrl', label: 'Фото позиции', format: 'image' },
      { key: 'sku', label: 'Позиция', sticky: true },
      { key: 'nmId', label: 'WB', format: 'wb-link' },
      { key: 'campaignName', label: 'РК' },
      { key: 'campaignType', label: 'Тип РК' },
      { key: 'attributionLevel', label: 'Атрибуция' },
      { key: 'attributionConfidencePct', label: 'Уверенность', format: 'percent', align: 'right' },
      { key: 'manager', label: 'Менеджер' },
      { key: 'observationDays', label: 'Дней', format: 'number', align: 'right' },
      { key: 'impressions', label: 'Показы', format: 'number', align: 'right' },
      { key: 'clicks', label: 'Клики', format: 'number', align: 'right' },
      { key: 'ctrPct', label: 'CTR', format: 'percent', align: 'right' },
      { key: 'baskets', label: 'Корзины', format: 'number', align: 'right' },
      { key: 'orders', label: 'Заказы шт/руб/динамика', align: 'right' },
      { key: 'sales', label: 'Продажи шт/руб/динамика', align: 'right' },
      { key: 'adSpendKopecks', label: 'Расход', format: 'currency', align: 'right' },
      { key: 'drrPct', label: 'ДРР', format: 'percent', align: 'right' },
      { key: 'recommendation', label: 'Статус правила' },
      { key: 'recommendationReason', label: 'Основание' },
    ],
    rows: rows as unknown as TableRow[],
  }
  assertReportContract('ads', report, { dateRange, groupBy: 'campaign' })
  return report
}

export function getStockReport(dateRange: DateRange = DEFAULT_RANGE): ReportResponse {
  const rows = stockWarehouseReportRows()
  return {
    meta: baseMeta('stock', 'Остатки WB', 'Остатки по складам WB, кластерам, КТР и доступному остатку.'),
    headline: 'Доступный остаток = остаток WB + от клиента; к клиенту показывается отдельно и не прибавляется.',
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange },
    kpis: [
      ...kpis(ABC_ROWS).slice(0, 3),
      { id: 'avg-ktr', label: 'Средний КТР', value: avg(rows.map((row) => row.ktrIndex)).toFixed(2), delta: delta(-0.3, '', false) },
      { id: 'available-stock', label: 'Доступно', value: rows.reduce((acc, row) => acc + row.availableUnits, 0).toLocaleString('ru-RU'), hint: 'остаток WB + от клиента; к клиенту не прибавляется' },
    ],
    chart: {
      title: 'Доступный остаток по складам',
      valueLabel: 'Доступно, шт',
      points: rows.slice(0, 7).map((row) => ({
        label: `${row.sku} · ${row.warehouseName}`,
        value: row.availableUnits,
        compareValue: row.wbStockUnits,
      })),
    },
    columns: [
      { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
      { key: 'sku', label: 'Позиция', sticky: true },
      { key: 'nmId', label: 'WB', format: 'wb-link' },
      { key: 'warehouseName', label: 'Склад WB' },
      { key: 'clusterName', label: 'Кластер' },
      { key: 'wbStockUnits', label: 'Остаток WB', format: 'number', align: 'right' },
      { key: 'fromClientUnits', label: 'От клиента', format: 'number', align: 'right' },
      { key: 'toClientUnits', label: 'К клиенту', format: 'number', align: 'right' },
      { key: 'availableUnits', label: 'Доступно', format: 'number', align: 'right' },
      { key: 'ordersPerDay', label: 'Заказы/день', format: 'number', align: 'right' },
      { key: 'daysToOos', label: 'Дней до OOS', format: 'number', align: 'right' },
      { key: 'ktrIndex', label: 'КТР', format: 'number', align: 'right' },
      { key: 'localizationPct', label: 'Локализация', format: 'percent', align: 'right' },
      { key: 'salesDistributionCoefficient', label: 'Коэф. продаж', format: 'number', align: 'right' },
      { key: 'logisticsPerUnitKopecks', label: 'Логистика/шт', format: 'currency', align: 'right' },
      { key: 'decision', label: 'Решение' },
      { key: 'decisionStatus', label: 'Статус правила' },
    ],
    rows: rows as unknown as TableRow[],
  }
}

export function getWeekOverWeekReport(dateRange: DateRange = DEFAULT_RANGE): ReportResponse {
  const rows = weekOverWeekRows(dateRange)
  return {
    meta: baseMeta('week-over-week', 'Неделя к неделе', 'Сравнение ключевых показателей по SKU с предыдущим периодом.'),
    headline: 'Физическое значение показывается вместе с процентной динамикой; остатки читаются через признак "был ОС".',
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange },
    kpis: kpis(ABC_ROWS),
    chart: {
      title: 'WoW: цены, маржа, прибыль, продажи, заказы, корзины',
      valueLabel: 'Динамика, %',
      compareLabel: 'Предыдущий период',
      points: rows.slice(0, 7).map((row) => ({
        label: row.sku,
        value: row.orders.deltaPct ?? 0,
        compareValue: row.sales.deltaPct ?? 0,
      })),
    },
    columns: [
      { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
      { key: 'sku', label: 'Позиция', sticky: true },
      { key: 'abcCode', label: 'ABC', format: 'abc', align: 'center' },
      { key: 'productStatus', label: 'Статус' },
      { key: 'orders', label: 'Заказы значение/динамика', align: 'right' },
      { key: 'sales', label: 'Продажи значение/динамика', align: 'right' },
      { key: 'baskets', label: 'Корзины значение/динамика', align: 'right' },
      { key: 'marginPct', label: 'Маржа значение/динамика', align: 'right' },
      { key: 'profit', label: 'Прибыль значение/динамика', align: 'right' },
      { key: 'wasOutOfStock', label: 'Был ОС' },
      { key: 'stockAvailability7d', label: 'Наличие 7 дней' },
      { key: 'stockOutDays', label: 'Дней ОС', format: 'number', align: 'right' },
      { key: 'stockSnapshotCoveragePct', label: 'Покрытие истории', format: 'percent', align: 'right' },
      { key: 'conclusion', label: 'Статус правила' },
    ],
    rows: rows as unknown as TableRow[],
  }
}

export function getPnlReport(dateRange: DateRange = DEFAULT_RANGE, source: 'operational' | 'financial' = 'operational'): ReportResponse {
  const pending = source === 'financial'
  const financialConfirmationStatus: FinancialConfirmationStatus = pending ? 'pending_financial' : 'operational'
  const report: ReportResponse = {
    meta: baseMeta('pnl', 'P&L', 'P&L показывает выручку, себестоимость, комиссии, логистику, налоги и предварительную прибыль за выбранный период.', 'financial', pending ? 'pending_financial' : 'partial'),
    headline: 'Налоговая база = выручка покупателя до вычета комиссии и логистики.',
    warning: pending ? 'Финансовый отчёт WB за выбранный период ещё не финальный.' : undefined,
    financialConfirmationStatus,
    comments: SKU_COMMENTS,
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange },
    kpis: kpis(ABC_ROWS),
    chart: chartFromRows('Маржа по SKU', 'Маржа, %', ABC_ROWS, 'marginPct'),
    columns: [
      { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
      { key: 'sku', label: 'Артикул', sticky: true },
      { key: 'nmId', label: 'WB', format: 'wb-link', sticky: true },
      { key: 'priceWithSppKopecks', label: 'Цена с СПП', format: 'currency', align: 'right' },
      { key: 'salesKopecks', label: 'Продажи', format: 'currency', align: 'right' },
      { key: 'taxBaseKopecks', label: 'Налоговая база', format: 'currency', align: 'right' },
      { key: 'cogsKopecks', label: 'Себестоимость', format: 'currency', align: 'right' },
      { key: 'netTotalKopecks', label: 'Предв. прибыль', format: 'currency', align: 'right' },
      { key: 'netPerUnitKopecks', label: 'Чистая/шт', format: 'currency', align: 'right' },
      { key: 'marginPct', label: 'Маржа', format: 'percent', align: 'right' },
      { key: 'logisticsCostPct', label: '% логистика', format: 'percent', align: 'right' },
      { key: 'commissionCostPct', label: '% комиссия', format: 'percent', align: 'right' },
      { key: 'storageCostPct', label: '% хранение', format: 'percent', align: 'right' },
      { key: 'adSpendKopecks', label: 'Реклама', format: 'currency', align: 'right' },
    ],
    rows: ABC_ROWS.map((row) => ({
      ...row,
      taxBaseKopecks: row.ordersKopecks,
      cogsKopecks: Math.max(0, row.salesKopecks - row.netTotalKopecks - row.adSpendKopecks),
    })),
  }
  assertReportContract('pnl', report, { dateRange, groupBy: 'sku', pnlSource: source })
  return report
}

export function getExpensesReport(dateRange: DateRange = DEFAULT_RANGE): ReportResponse {
  const rows = [
    {
      id: 'storage-overhead',
      category: 'Хранение',
      amountKopecks: 4_860_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: 'stock-days · fallback выручка',
      allocationCoverageLabel: '82% SKU',
      approvalStatusLabel: 'требует маппинга',
      owner: 'Максим · finance_admin',
      pending: '2 статьи склада не сопоставлены · проверить маппинг',
      comment: 'Общая строка периода раскладывается на SKU по stock-days.',
    },
    {
      id: 'packaging-consumables',
      category: 'Упаковка',
      amountKopecks: 6_120_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: 'штуки / заказы',
      allocationCoverageLabel: '100% SKU',
      approvalStatusLabel: 'готово к P&L',
      owner: 'Мария · finance_editor',
      pending: 'Проверить выборочно 12 SKU перед закрытием',
      comment: 'Прямые и общие строки распределены по отгруженным штукам.',
    },
    {
      id: 'payroll-shifts',
      category: 'ФОТ / смены',
      amountKopecks: 9_650_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: 'произведённые штуки',
      allocationCoverageLabel: '74% SKU',
      approvalStatusLabel: 'требует маппинга',
      owner: 'Мария · finance_editor',
      pending: 'Назначить SKU без производственного разреза',
      comment: 'План-факт использует агрегат без детализации для менеджеров.',
    },
    {
      id: 'acquiring',
      category: 'Эквайринг',
      amountKopecks: 1_890_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: '% от выручки',
      allocationCoverageLabel: '100% SKU',
      approvalStatusLabel: 'готово к P&L',
      owner: 'Максим · finance_admin',
      pending: 'Ставка действует до изменения правила',
      comment: 'Переменный расход привязан к рублю выручки.',
    },
    {
      id: 'services',
      category: 'Сервисы',
      amountKopecks: 2_280_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: 'выручка',
      allocationCoverageLabel: '100% SKU',
      approvalStatusLabel: 'готово к P&L',
      owner: 'Максим · finance_admin',
      pending: 'Оставить правило по выручке на май',
      comment: 'Сервисные расходы распределяются по доле выручки SKU.',
    },
    {
      id: 'external-logistics',
      category: 'Внешняя логистика',
      amountKopecks: 5_690_000,
      sourceLabel: '1С · финансы и УУ',
      allocationBaseLabel: 'отправления / заказы',
      allocationCoverageLabel: '91% SKU',
      approvalStatusLabel: 'требует маппинга',
      owner: 'Мария · finance_editor',
      pending: 'Связать 43 отправления с SKU',
      comment: 'Не смешиваем с логистикой WB без отдельного правила.',
    },
    {
      id: 'tax-vat',
      category: 'Налоги / НДС',
      amountKopecks: null,
      sourceLabel: '1С · налоговый слой',
      allocationBaseLabel: 'база и ставка не заданы',
      allocationCoverageLabel: '0% SKU',
      approvalStatusLabel: 'нужна ставка',
      owner: 'Максим · finance_admin',
      pending: 'Заполнить базу, ставку, режим и округление',
      comment: 'Сумма null: не ставим 0 и не считаем примерную ставку.',
    },
    {
      id: 'other-opex',
      category: 'Прочее',
      amountKopecks: 740_000,
      sourceLabel: 'Excel fallback',
      allocationBaseLabel: 'ручное правило',
      allocationCoverageLabel: '0% SKU',
      approvalStatusLabel: 'не распределено',
      owner: 'Максим · finance_admin',
      pending: 'Добавить комментарий и правило перед P&L',
      comment: 'Fallback-строка остаётся вне P&L к закрытию периода без правила.',
    },
  ]
  const readyKopecks = rows
    .filter((row) => row.approvalStatusLabel === 'готово к P&L')
    .reduce((acc, row) => acc + (row.amountKopecks ?? 0), 0)
  const totalKopecks = rows.reduce((acc, row) => acc + (row.amountKopecks ?? 0), 0)
  const unallocatedKopecks = rows
    .filter((row) => row.approvalStatusLabel !== 'готово к P&L')
    .reduce((acc, row) => acc + (row.amountKopecks ?? 0), 0)

  return {
    meta: baseMeta('expenses', 'Расходы', 'Live-слой 1С для расходов: источник, маппинг, распределение по SKU, проверка и попадание в P&L.', 'financial', 'partial'),
    headline: 'Расходы привязываются к SKU. Общие строки периода распределяются по драйверу и остаются вне P&L к закрытию периода без правила.',
    warning: 'P&L остаётся предварительным, пока не заполнены налоговая база/ставка и строки без драйвера распределения.',
    financialConfirmationStatus: 'pending_financial',
    comments: [],
    auditEvents: REPORT_AUDIT_EVENTS,
    filters: { dateRange },
    kpis: [
      { id: 'expense-rows', label: 'Статей в таблице', value: String(rows.length), hint: '1С-слой: хранение, налоги и основные OPEX-статьи.' },
      { id: 'total', label: 'Сумма периода', value: formatRub(totalKopecks), delta: delta(6.4) },
      { id: 'ready', label: 'Готово к P&L', value: `${Math.round((readyKopecks / Math.max(totalKopecks, 1)) * 100)}%`, hint: 'Строки с источником, драйвером и SKU-покрытием.' },
      { id: 'unallocated', label: 'Не распределено', value: formatRub(unallocatedKopecks), hint: 'Не участвует в P&L к закрытию без драйвера или ручного правила.', delta: { value: -1, label: 'налог + прочее', tone: 'warning' } },
      { id: 'source-errors', label: 'Ошибки источников', value: '2', hint: 'Ошибки 1С/маппинга требуют действия.' },
    ],
    chart: {
      title: 'Статус расходных источников',
      valueLabel: 'Строки',
      points: [
        { label: 'Готово к P&L', value: rows.filter((row) => row.approvalStatusLabel === 'готово к P&L').length },
        { label: 'Требует маппинга', value: rows.filter((row) => row.approvalStatusLabel === 'требует маппинга').length },
        { label: 'Нужна ставка', value: rows.filter((row) => row.approvalStatusLabel === 'нужна ставка').length },
      ],
    },
    columns: [
      { key: 'category', label: 'Статья', sticky: true },
      { key: 'periodLabel', label: 'Период' },
      { key: 'amountKopecks', label: 'Сумма', format: 'currency', align: 'right' },
      { key: 'sourceLabel', label: 'Источник' },
      { key: 'allocationBaseLabel', label: 'База распределения' },
      { key: 'allocationCoverageLabel', label: 'Покрытие SKU' },
      { key: 'approvalStatusLabel', label: 'Статус' },
      { key: 'owner', label: 'Ответственный' },
      { key: 'pending', label: 'Действие' },
    ],
    rows: rows.map((row) => ({
      ...row,
      periodLabel: `${dateRange.from} — ${dateRange.to}`,
    })),
  }
}

export function getReportById(id: ReportId, dateRange: DateRange = DEFAULT_RANGE, groupBy: ReportGroupBy = 'sku'): ReportResponse {
  if (id === 'abc') return getAbcReport(dateRange, groupBy)
  if (id === 'rnp') return getRnpReport(dateRange, groupBy)
  if (id === 'expenses') return getExpensesReport(dateRange)
  if (id === 'ads') return getAdsReport(dateRange)
  if (id === 'stock') return getStockReport(dateRange)
  if (id === 'week-over-week') return getWeekOverWeekReport(dateRange)
  return getPnlReport(dateRange)
}

export function getAlerts() {
  return { items: ALERTS }
}

export function getExport(reportId: ReportId): ExportResponse {
  const rows = reportId === 'digest' ? ABC_ROWS.length : getReportById(reportId).rows.length
  const financeOnlyReports = new Set<ReportId>(['pnl', 'expenses'])
  const allowedRoles: ExportResponse['allowedRoles'] = financeOnlyReports.has(reportId)
    ? ['finance', 'admin']
    : reportId === 'ads'
      ? ['ads', 'finance', 'admin']
      : ['owner', 'admin', 'finance']
  return {
    fileName: `wb-${reportId}-${DEFAULT_RANGE.from}-${DEFAULT_RANGE.to}.xlsx`,
    rows,
    exportAllowed: true,
    allowedRoles,
    emptySourceNote: reportId === 'abc' ? EMPTY_PROMO_FILE_NOTE : undefined,
  }
}

export function getExportForRole(reportId: ReportId, role: string): ExportResponse {
  const exportInfo = getExport(reportId)
  if (exportInfo.allowedRoles.includes(role as ExportResponse['allowedRoles'][number])) return exportInfo
  return {
    ...exportInfo,
    exportAllowed: false,
    blockedReason: reportId === 'pnl' || reportId === 'expenses'
      ? 'Финансовый экспорт доступен только роли финансы или администратор до закрытия WB-24.'
      : 'Экспорт недоступен для текущей роли.',
  }
}

export function getSkuAnalyticsSummary(sku: string): SkuAnalyticsSummary | undefined {
  const row = ABC_ROWS.find((item) => item.sku === sku)
  if (!row) return undefined
  return {
    abcCode: row.abcCode,
    productStatus: row.productStatus,
    promotionStatus: row.promotionStatus,
    wbStockUnits: row.wbStockUnits,
    buyoutPct: row.buyoutPct,
    baskets: row.baskets,
    ordersUnits: row.ordersUnits,
    avgPriceWithSppKopecks: row.priceWithSppKopecks,
    marginPct: row.marginPct,
    marginKopecks: row.marginKopecks,
    wbCommissionPct: row.commissionCostPct,
  }
}
