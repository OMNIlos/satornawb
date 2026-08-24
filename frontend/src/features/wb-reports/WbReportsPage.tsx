import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  Columns3,
  Download,
  ExternalLink,
  RefreshCw,
  Search,
  X,
} from 'lucide-react'
import { formatRub } from '../../lib/formatRub'
import {
  fetchDigest,
  fetchDigestJob,
  fetchPnlReport,
  fetchReport,
  fetchReportExport,
  refreshReportSourcesJob,
  startReportJob,
} from './api'
import type {
  CompositeMetricValue,
  DigestAffectedItem,
  DigestProblemRow,
  DatePreset,
  DigestResponse,
  ReportGroupBy,
  ReportId,
  ReportResponse,
  TableColumn,
  TableRow,
  TableValue,
} from './types'
import '../../components/vella/VellaFoundation.css'

type ActiveReport = ReportId | 'digest'
type DigestMode = 'period' | 'now'
type Popover = 'period' | 'columns' | 'group' | 'notifications' | null
type ManagerFilter = 'all' | 'mine' | 'unassigned' | string
type ReportJobState = 'queued' | 'running' | 'waiting_1c' | 'waiting_baskets_detail' | 'waiting_daily_detail' | 'completed' | 'failed' | string
type ReportWithJob = ReportResponse & {
  reportJob?: {
    state?: ReportJobState | null
    stage?: string | null
    label?: string | null
    percent?: number | null
  } | null
}
type ReportJob = NonNullable<ReportWithJob['reportJob']>
const CURRENT_MANAGER_ID = 'manager-kotelnikova'
const backgroundReportIds = new Set<ReportId>(['abc', 'rnp', 'pnl', 'expenses', 'ads', 'stock', 'week-over-week'])

function isoDate(value: Date) {
  return value.toISOString().slice(0, 10)
}

function normalizeDateRange(input: { preset: DatePreset }): { preset: DatePreset; from: string; to: string } {
  const today = new Date()
  const days = input.preset === '1d' ? 1 : input.preset === '14d' ? 14 : input.preset === '30d' ? 30 : 7
  const from = new Date(today)
  from.setDate(today.getDate() - days + 1)
  return { preset: input.preset, from: isoDate(from), to: isoDate(today) }
}

const emptyChart = {
  title: 'Баланс за неделю',
  valueLabel: 'Заказы',
  compareLabel: 'Продажи',
  points: [],
}

const reportTabs: Array<{ id: ActiveReport | 'rules'; label: string; href: string }> = [
  { id: 'digest', label: 'Дайджест', href: '/wb/reports' },
  { id: 'abc', label: 'ABC', href: '/wb/reports/abc' },
  { id: 'rnp', label: 'РНП', href: '/wb/reports/rnp' },
  { id: 'pnl', label: 'P&L', href: '/wb/reports/pnl' },
  { id: 'expenses', label: 'Расходы', href: '/wb/reports/expenses' },
  { id: 'ads', label: 'Реклама', href: '/wb/reports/ads' },
  { id: 'stock', label: 'Остатки', href: '/wb/reports/stock' },
  { id: 'week-over-week', label: 'Неделя', href: '/wb/reports/week-over-week' },
  { id: 'rules', label: 'Правила', href: '/wb/reports/rules' },
]

const datePresets: Array<{ id: DatePreset; label: string }> = [
  { id: '1d', label: 'Сегодня' },
  { id: '7d', label: '7 дней' },
  { id: '14d', label: '14 дней' },
  { id: '30d', label: '30 дней' },
]

const groupOptions: Array<{ id: ReportGroupBy; label: string }> = [
  { id: 'sku', label: 'SKU' },
  { id: 'manager', label: 'Менеджер' },
  { id: 'brand', label: 'Бренд' },
  { id: 'category', label: 'Категория' },
  { id: 'status', label: 'Статус' },
]

function reportFromPath(pathname: string): ActiveReport {
  if (pathname.endsWith('/monitor')) return 'digest'
  if (pathname.endsWith('/abc')) return 'abc'
  if (pathname.endsWith('/rnp')) return 'rnp'
  if (pathname.endsWith('/pnl')) return 'pnl'
  if (pathname.endsWith('/expenses')) return 'expenses'
  if (pathname.endsWith('/ads')) return 'ads'
  if (pathname.endsWith('/stock')) return 'stock'
  if (pathname.endsWith('/week-over-week')) return 'week-over-week'
  return 'digest'
}

function HelpTip({ children }: { children: ReactNode }) {
  return (
    <span className="vella-tooltip-wrap">
      <span className="vella-help-dot" tabIndex={0}>?</span>
      <span className="vella-tooltip">{children}</span>
    </span>
  )
}

function toneClass(tone?: string) {
  if (tone === 'good') return 'good'
  if (tone === 'bad' || tone === 'warning') return 'warn'
  return ''
}

function isComposite(value: TableValue): value is CompositeMetricValue {
  return typeof value === 'object' && value !== null && ('units' in value || 'kopecks' in value || 'percent' in value)
}

function scalarValue(value: TableValue) {
  if (typeof value === 'number') return value
  if (typeof value === 'string') return value
  if (typeof value === 'boolean') return value ? 1 : 0
  if (Array.isArray(value)) return value.filter(Boolean).length
  if (isComposite(value)) return value.kopecks ?? value.units ?? value.percent ?? value.deltaPct ?? 0
  return 0
}

function formatCell(value: TableValue, column?: TableColumn) {
  if (value == null) return '—'
  if (isComposite(value)) {
    const primary = value.kopecks != null ? formatRub(value.kopecks) : value.percent != null ? `${value.percent.toFixed(1)}%` : `${value.units ?? 0} ${value.unitsLabel ?? 'шт'}`
    return (
      <span className="vella-metric-stack">
        <strong>{primary}</strong>
        {value.units != null && value.kopecks != null && <span>{value.units} {value.unitsLabel ?? 'шт'}</span>}
        {value.deltaLabel && <span className={value.deltaPct != null && value.deltaPct < 0 ? 'metric-down' : 'metric-up'}>{value.deltaLabel}</span>}
      </span>
    )
  }
  if (Array.isArray(value)) {
    if (value.some((item) => typeof item === 'object')) return `${value.length} SKU`
    return (
      <span className="vella-availability">
        {value.map((item, index) => <span className={item ? 'on' : 'off'} key={index} />)}
      </span>
    )
  }
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  if (column?.format === 'currency' && typeof value === 'number') return formatRub(value)
  if (column?.format === 'percent' && typeof value === 'number') return `${value.toFixed(1)}%`
  if (column?.format === 'number' && typeof value === 'number') return value.toLocaleString('ru-RU')
  if (column?.format === 'image' && typeof value === 'string') return <img className="vella-product-photo" src={value} alt="" />
  if (column?.format === 'wb-link') return <span className="vella-mono">{String(value)}</span>
  if (column?.format === 'abc') return <span className="vella-badge neutral">{String(value)}</span>
  if (column?.format === 'promotion') return value === 'yes' ? <span className="vella-badge warn">в акции</span> : <span className="vella-badge good">нет</span>
  if (column?.key === 'attributionLevel') {
    const label = value === 'exact_sku' ? 'точно к товару' : value === 'campaign_sku' ? 'по кампании и товару' : 'по кампании'
    const tone = value === 'exact_sku' ? 'good' : value === 'campaign_sku' ? 'warn' : 'neutral'
    return <span className={`vella-badge ${tone}`}>{label}</span>
  }
  if (column?.key === 'recommendation') {
    const label = value === 'draft_stop' ? 'кандидат · черновик' : value === 'review' ? 'на проверку' : 'в пределах порога'
    const tone = value === 'keep' ? 'good' : 'warn'
    return <span className={`vella-badge ${tone}`}>{label}</span>
  }
  return String(value)
}

function formatReportCell(row: TableRow, column: TableColumn) {
  if (column.key === 'sku' && (row.productName || row.photoUrl)) {
    const sku = row.sku == null ? '' : String(row.sku)
    const title = row.productName ? String(row.productName) : sku || 'Товар без названия'
    return (
      <span className="vella-product-cell">
        {typeof row.photoUrl === 'string' && row.photoUrl ? (
          <img className="vella-product-photo" src={row.photoUrl} alt="" />
        ) : (
          <span className="vella-product-photo vella-product-photo-empty">{title.slice(0, 2).toUpperCase()}</span>
        )}
        <span>
          <strong>{title}</strong>
          {sku && <small>Артикул: {sku}</small>}
          {row.nmId != null && <small>WB {String(row.nmId)}</small>}
        </span>
      </span>
    )
  }
  return formatCell(row[column.key], column)
}

function formatNullableRub(value: number | null | undefined) {
  return value == null ? '—' : formatRub(value)
}

function formatNullablePct(value: number | null | undefined) {
  return value == null ? '—' : `${value.toFixed(1)}%`
}

function planFactStatusLabel(status: string) {
  if (status === 'no_plan') return 'нет плана'
  if (status === 'no_fact') return 'нет факта'
  if (status === 'unallocated_costs') return 'не распределено'
  if (status === 'risk') return 'риск'
  if (status === 'watch') return 'внимание'
  return 'норма'
}

function isUserFacingKpi(label: string) {
  return !/источник|source|cache|fresh|partial|latest|local orders|seller portal|операционн/i.test(label)
}

function jobIsRefreshing(job: ReportJob | null | undefined) {
  const state = job?.state
  const stage = job?.stage
  return (
    state === 'queued'
    || state === 'running'
    || state === 'waiting_1c'
    || state === 'waiting_baskets_detail'
    || state === 'waiting_daily_detail'
    || stage === 'refreshing_sources'
    || stage === 'building_report'
  )
}

function reportIsRefreshing(report: ReportWithJob | null) {
  return jobIsRefreshing(report?.reportJob)
}

function rowSearchText(row: TableRow) {
  return Object.values(row)
    .map((value) => {
      if (isComposite(value)) return `${value.units ?? ''} ${value.kopecks ?? ''} ${value.deltaLabel ?? ''}`
      if (Array.isArray(value)) {
        return value
          .map((item) => typeof item === 'object' ? `${item.sku} ${item.nmId ?? ''} ${item.warehouseName}` : String(item))
          .join(' ')
      }
      return String(value ?? '')
    })
    .join(' ')
    .toLowerCase()
}

function affectedItemsFor(row: DigestProblemRow): DigestAffectedItem[] {
  const value = row.affectedItems
  if (!Array.isArray(value)) return []
  return value.filter((item): item is DigestAffectedItem => typeof item === 'object' && item !== null && 'sku' in item)
}

function OosRiskSummary({
  row,
  onOpenStock,
}: {
  row: DigestProblemRow
  onOpenStock: () => void
}) {
  const items = affectedItemsFor(row)
  const visibleItems = items.slice(0, 8)
  const hiddenCount = Math.max(0, items.length - visibleItems.length)

  return (
    <div className="vella-oos-card">
      <button className="vella-plan-row" type="button" onClick={onOpenStock}>
        <span>{String(row.metric ?? 'Остатки')}</span>
        <strong>{String(row.title ?? `${items.length} SKU`)}</strong>
        <em>{String(row.details ?? 'Товары без доступного остатка')}</em>
      </button>
      {visibleItems.length > 0 && (
        <div className="vella-oos-table-wrap">
          <table className="vella-oos-table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Склад</th>
                <th className="num">Доступно</th>
                <th>Причина</th>
              </tr>
            </thead>
            <tbody>
              {visibleItems.map((item) => (
                <tr key={`${item.nmId ?? item.sku}-${item.warehouseName}`}>
                  <td>
                    <strong>{item.sku}</strong>
                    {item.nmId != null && <span>NM {item.nmId}</span>}
                  </td>
                  <td>{item.warehouseName}</td>
                  <td className="num">{item.availableUnits ?? 0}</td>
                  <td>{item.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {hiddenCount > 0 && (
            <button className="vella-oos-more" type="button" onClick={onOpenStock}>
              Еще {hiddenCount.toLocaleString('ru-RU')} SKU в отчете Остатки
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function ChartBars({ data }: { data: ReportResponse['chart'] | DigestResponse['charts'][number] }) {
  const points = data.points.slice(0, 7)
  const max = Math.max(...points.flatMap((point) => [point.value, point.compareValue ?? 0]), 1)
  return (
    <div className="vella-report-chart">
      <div className="vella-section-title">{data.title}</div>
      <div className="vella-chart-bars" aria-label={data.title}>
        {points.map((point) => (
          <div className="vella-chart-bar-row" key={point.label}>
            <span>{point.label}</span>
            <div
              className="vella-chart-track"
              title={[
                point.date,
                `заказы: ${point.value}`,
                `продажи: ${point.compareValue ?? 0}`,
                point.returnsUnits != null ? `возвраты: ${point.returnsUnits}` : null,
                point.buyoutPct != null ? `выкуп: ${point.buyoutPct}%` : null,
              ].filter(Boolean).join(' · ')}
            >
              <i style={{ width: `${Math.max(4, point.value / max * 100)}%` }} />
              {point.compareValue != null && <em style={{ width: `${Math.max(4, point.compareValue / max * 100)}%` }} />}
            </div>
          </div>
        ))}
      </div>
      <div className="vella-muted">{data.valueLabel}{data.compareLabel ? ` · ${data.compareLabel}` : ''}</div>
    </div>
  )
}

function ReportLoadingState() {
  return (
    <div className="vella-report-state" role="status" aria-live="polite">
      <div className="vella-report-state-spinner" />
      <div>
        <h2>Загружаем отчет</h2>
        <p>Собираем показатели за выбранный период. Экран обновится автоматически.</p>
      </div>
      <div className="vella-report-state-grid" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, index) => (
          <span className="vella-report-state-skeleton" key={index} />
        ))}
      </div>
    </div>
  )
}

function ReportEmptyState({
  title,
  text,
  action,
}: {
  title: string
  text: string
  action?: { label: string; onClick: () => void }
}) {
  return (
    <div className="vella-report-state empty" role="status">
      <div className="vella-report-state-icon">0</div>
      <div>
        <h2>{title}</h2>
        <p>{text}</p>
      </div>
      {action && (
        <button className="vella-button primary" type="button" onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  )
}

export function WbReportsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const activeReport = reportFromPath(location.pathname)
  const digestMode: DigestMode = location.pathname.endsWith('/monitor') || new URLSearchParams(location.search).get('mode') !== 'period' ? 'now' : 'period'
  const isInternalPreview = location.pathname.startsWith('/internal/vella-preview')
  const [datePreset, setDatePreset] = useState<DatePreset>('7d')
  const [groupBy, setGroupBy] = useState<ReportGroupBy>('sku')
  const [pnlSource, setPnlSource] = useState<'operational' | 'financial'>('operational')
  const [search, setSearch] = useState('')
  const [managerFilter, setManagerFilter] = useState<ManagerFilter>('all')
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [hiddenColumns, setHiddenColumns] = useState<Record<string, Set<string>>>({})
  const [popover, setPopover] = useState<Popover>(null)
  const [drawerRow, setDrawerRow] = useState<TableRow | null>(null)
  const [modal, setModal] = useState<'export' | 'blocked' | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [digestData, setDigestData] = useState<DigestResponse | null>(null)
  const [reportData, setReportData] = useState<ReportResponse | null>(null)
  const [exportData, setExportData] = useState<{ fileName: string; rows: number; emptySourceNote?: string } | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [sourceRefreshJob, setSourceRefreshJob] = useState<ReportJob | null>(null)
  const [refreshReloadKey, setRefreshReloadKey] = useState(0)

  const dateRange = useMemo(() => normalizeDateRange({ preset: datePreset }), [datePreset])
  const digest = activeReport === 'digest' ? digestData : null
  const showExportAction = activeReport !== 'digest' || digestMode === 'period'
  const report = activeReport === 'digest' ? null : reportData
  const reportJob = (report as ReportWithJob | null)?.reportJob ?? null
  const visibleJob = sourceRefreshJob ?? reportJob
  const refreshInProgress = jobIsRefreshing(visibleJob)

  useEffect(() => {
    let ignore = false
    let retryTimer: number | null = null
    setLoading(true)
    setLoadError(null)
    setExportData(null)
    setDigestData(null)
    setReportData(null)

    async function load() {
      if (activeReport === 'digest') {
        const payload = await fetchDigest(dateRange)
        if (!ignore) {
          setDigestData(payload)
          setReportData(null)
        }
        return
      }

      if (backgroundReportIds.has(activeReport)) {
        await startReportJob(activeReport, dateRange, groupBy)
      }
      const payload = activeReport === 'pnl'
        ? await fetchPnlReport(dateRange, pnlSource)
        : await fetchReport(activeReport, dateRange, groupBy)

      if (!ignore) {
        setReportData(payload)
        setDigestData(null)
        if (reportIsRefreshing(payload as ReportWithJob)) {
          retryTimer = window.setTimeout(() => void load(), 2500)
        }
      }
    }

    void load()
      .catch((error: unknown) => {
        if (!ignore) setLoadError(error instanceof Error ? error.message : 'Не удалось загрузить отчет')
      })
      .finally(() => {
        if (!ignore) setLoading(false)
      })
    return () => {
      ignore = true
      if (retryTimer !== null) window.clearTimeout(retryTimer)
    }
  }, [activeReport, dateRange, groupBy, pnlSource, refreshReloadKey])

  const rows = useMemo<TableRow[]>(() => {
    if (digest) return digest.problemRows as TableRow[]
    return report?.rows ?? []
  }, [digest, report])
  const columns = useMemo<TableColumn[]>(() => {
    if (report) return report.columns
    return [
      { key: 'photoUrl', label: 'Фото', format: 'image', sticky: true },
      { key: 'sku', label: 'SKU', sticky: true },
      { key: 'productStatus', label: 'Статус' },
      { key: 'brand', label: 'Бренд' },
      { key: 'manager', label: 'Менеджер' },
      { key: 'marginPct', label: 'Маржа', format: 'percent', align: 'right' },
      { key: 'drrSalesPct', label: 'ДРР', format: 'percent', align: 'right' },
      { key: 'netTotalKopecks', label: 'Предв. прибыль', format: 'currency', align: 'right' },
      { key: 'wbStockUnits', label: 'Остаток WB', format: 'number', align: 'right' },
    ]
  }, [report])
  const hiddenForReport = hiddenColumns[activeReport] ?? new Set<string>()
  const visibleColumns = columns.filter((column) => column.defaultVisible !== false && !hiddenForReport.has(column.key))
  const brands = useMemo(() => ['Все', ...Array.from(new Set(rows.map((row) => String(row.brand ?? '')).filter(Boolean)))], [rows])
  const [brand, setBrand] = useState('Все')

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    const filtered = rows
      .filter((row) => brand === 'Все' || row.brand === brand)
      .filter((row) => {
        if (managerFilter === 'all') return true
        if (managerFilter === 'mine') return row.managerId === CURRENT_MANAGER_ID
        if (managerFilter === 'unassigned') return !row.managerId
        return row.managerId === managerFilter
      })
      .filter((row) => !query || rowSearchText(row).includes(query))
    if (!sortKey) return filtered
    return [...filtered].sort((a, b) => {
      const left = scalarValue(a[sortKey])
      const right = scalarValue(b[sortKey])
      const result = typeof left === 'string' ? left.localeCompare(String(right), 'ru') : Number(left) - Number(right)
      return sortDirection === 'asc' ? result : -result
    })
  }, [brand, managerFilter, rows, search, sortDirection, sortKey])

  const kpis = (digest?.kpis ?? report?.kpis ?? []).filter((kpi) => isUserFacingKpi(kpi.label))
  const title = digest?.meta.title ?? report?.meta.title ?? 'Отчеты WB'
  const headline = digest && digestMode === 'now'
    ? 'Оперативный режим дайджеста: свежесть данных, сегодняшние KPI, последние пересчеты и очередь действий.'
    : digest?.headline ?? report?.headline ?? ''
  const reportLoaded = !loading && !loadError && (activeReport === 'digest' ? Boolean(digest) : Boolean(report))
  const hasRows = rows.length > 0
  const showNoDataState = reportLoaded && !hasRows
  const showReportContent = reportLoaded && !showNoDataState

  function pushToast(text: string) {
    setToast(text)
    window.setTimeout(() => setToast(null), 2400)
  }

  async function refreshCurrentReportSources() {
    if (refreshInProgress) return
    try {
      const job = await refreshReportSourcesJob(activeReport, dateRange, groupBy)
      setSourceRefreshJob(job as ReportJob)
      pushToast('Обновляем данные отчета')
    } catch (error) {
      pushToast(error instanceof Error ? error.message : 'Не удалось запустить обновление')
    }
  }

  useEffect(() => {
    if (!jobIsRefreshing(sourceRefreshJob)) return
    let cancelled = false
    let timer: number | null = null

    async function poll() {
      try {
        if (activeReport === 'digest') {
          const job = await fetchDigestJob(dateRange)
          if (cancelled) return
          setSourceRefreshJob(job as ReportJob)
          if (!jobIsRefreshing(job as ReportJob)) {
            setSourceRefreshJob(null)
            setRefreshReloadKey((value) => value + 1)
          }
          return
        }

        const payload = activeReport === 'pnl'
          ? await fetchPnlReport(dateRange, pnlSource)
          : await fetchReport(activeReport, dateRange, groupBy)
        if (cancelled) return
        setReportData(payload)
        const nextJob = (payload as ReportWithJob).reportJob ?? null
        setSourceRefreshJob(nextJob)
        if (!jobIsRefreshing(nextJob)) {
          setSourceRefreshJob(null)
          setRefreshReloadKey((value) => value + 1)
        }
      } catch (error) {
        if (!cancelled) pushToast(error instanceof Error ? error.message : 'Не удалось проверить прогресс')
      } finally {
        if (!cancelled && jobIsRefreshing(sourceRefreshJob)) {
          timer = window.setTimeout(() => void poll(), 2500)
        }
      }
    }

    timer = window.setTimeout(() => void poll(), 900)
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [activeReport, dateRange, groupBy, pnlSource, sourceRefreshJob])

  function toggleColumn(columnKey: string) {
    setHiddenColumns((current) => {
      const nextSet = new Set(current[activeReport] ?? [])
      if (nextSet.has(columnKey)) nextSet.delete(columnKey)
      else nextSet.add(columnKey)
      return { ...current, [activeReport]: nextSet }
    })
  }

  function toggleSort(columnKey: string) {
    if (sortKey === columnKey) {
      setSortDirection((current) => current === 'desc' ? 'asc' : 'desc')
      return
    }
    setSortKey(columnKey)
    setSortDirection('desc')
  }

  async function openExportModal() {
    setModal('export')
    setExportData(null)
    try {
      const payload = await fetchReportExport(activeReport === 'digest' ? 'digest' : activeReport)
      setExportData(payload)
    } catch (error) {
      setExportData({
        fileName: 'export-unavailable.xlsx',
        rows: 0,
        emptySourceNote: error instanceof Error ? error.message : 'Не удалось запросить экспорт',
      })
    }
  }

  function routeFor(href: string) {
    return isInternalPreview ? href.replace('/wb/reports', '/internal/vella-preview/reports') : href
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <img className="vella-brand-logo" src="/brand/satorna-logo-white.svg" alt="Satorna" />
          </div>
          <div className="vella-nav-label">WB</div>
          <button className="vella-nav-button vella-nav-parent" type="button" onClick={() => navigate(isInternalPreview ? '/internal/vella-preview/repricer' : '/wb/repricer')}>
            <span className="vella-nav-dot" />
            Репрайсер
          </button>
          <button className="vella-nav-button" type="button" onClick={() => navigate(isInternalPreview ? '/internal/vella-preview/sources' : '/wb/sources')}>
            <span className="vella-nav-dot" />
            Источники и загрузки
          </button>
          <div className="vella-nav-group">
            <button className="vella-nav-button active vella-nav-parent" type="button">
              <span className="vella-nav-dot" />
              Отчёты
            </button>
            {reportTabs.map((tab) => (
              <button
                className={`vella-nav-button ${tab.id === activeReport ? 'active' : ''}`}
                key={tab.id}
                type="button"
                onClick={() => navigate(routeFor(tab.href))}
              >
                <span className="vella-nav-dot" />
                {tab.label}
              </button>
            ))}
          </div>
          <div className="vella-nav-label">Авито</div>
          {['Чаты', 'Объявления', 'Кошельки'].map((item) => <button className="vella-nav-button" type="button" key={item} onClick={() => pushToast(`${item}: раздел появится в следующем модуле`)}><span className="vella-nav-dot" />{item}</button>)}
          <div className="vella-nav-label">Система</div>
          {['Уведомления', 'Настройки'].map((item) => <button className="vella-nav-button" type="button" key={item} onClick={() => pushToast(`${item}: раздел системы`) }><span className="vella-nav-dot" />{item}</button>)}
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> <b>{title}</b></div>
            <div className="vella-top-actions">
              {digest && digestMode === 'now' ? (
                <span className="vella-badge good">Сегодня · {digest.meta.freshnessState}</span>
              ) : (
                <div className="vella-position">
                  <button className="vella-button" type="button" onClick={() => setPopover(popover === 'period' ? null : 'period')}>
                    <CalendarDays size={16} /> {datePresets.find((item) => item.id === datePreset)?.label} <ChevronDown size={14} />
                  </button>
                  {popover === 'period' && (
                    <div className="vella-popover">
                      {datePresets.map((preset) => (
                        <button className="vella-popover-row" key={preset.id} type="button" onClick={() => {
                          setDatePreset(preset.id)
                          setPopover(null)
                          pushToast(`Период изменен: ${preset.label}`)
                        }}>
                          <Check size={14} opacity={datePreset === preset.id ? 1 : 0.15} /> {preset.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              <div className="vella-position">
                <button className="vella-icon-button" type="button" aria-label="Уведомления" onClick={() => setPopover(popover === 'notifications' ? null : 'notifications')}>
                  <Bell size={16} />
                </button>
                {popover === 'notifications' && (
                  <div className="vella-popover">
                    {(digest?.alerts ?? []).slice(0, 3).map((alert) => (
                      <button className="vella-popover-row" key={alert.id} type="button" onClick={() => pushToast(alert.title)}>
                        {alert.title}
                      </button>
                    ))}
                    {!digest && <button className="vella-popover-row" type="button" onClick={() => pushToast('Уведомления отчета открыты')}>Свежесть отчета проверена</button>}
                  </div>
                )}
              </div>
              <button className="vella-button" type="button" disabled={refreshInProgress} onClick={() => void refreshCurrentReportSources()}>
                <RefreshCw size={16} /> {refreshInProgress ? 'Обновляем' : 'Обновить данные'}
              </button>
              {showExportAction && (
                <button className="vella-button primary" type="button" onClick={() => void openExportModal()}>
                  <Download size={16} /> Экспорт
                </button>
              )}
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-tabs">
              {reportTabs.map((tab) => (
                <button className={`vella-tab ${tab.id === activeReport ? 'active' : ''}`} key={tab.id} type="button" onClick={() => navigate(routeFor(tab.href))}>
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="vella-report-head">
              <div>
                <h1>{title}</h1>
                <p>{headline}</p>
              </div>
              {digest && (
                <div className="vella-tabs" aria-label="Режим дайджеста">
                  <button className={`vella-tab ${digestMode === 'period' ? 'active' : ''}`} type="button" onClick={() => navigate(routeFor('/wb/reports?mode=period'))}>
                    Период
                  </button>
                  <button className={`vella-tab ${digestMode === 'now' ? 'active' : ''}`} type="button" onClick={() => navigate(routeFor('/wb/reports'))}>
                    Сейчас
                  </button>
                </div>
              )}
              {report?.warning && <button className="vella-badge warn" type="button" onClick={() => setModal('blocked')}>Есть блокер</button>}
            </div>

            {loading && <ReportLoadingState />}
            {loadError && (
              <ReportEmptyState
                title="Отчет не загрузился"
                text={loadError}
                action={{ label: 'Повторить', onClick: () => setRefreshReloadKey((value) => value + 1) }}
              />
            )}
            {showNoDataState && (
              <ReportEmptyState
                title="Данных за выбранный период пока нет"
                text="Попробуйте выбрать другой период или обновить данные."
                action={{ label: 'Обновить данные', onClick: () => void refreshCurrentReportSources() }}
              />
            )}
            {visibleJob && refreshInProgress && showReportContent && (
              <div className="vella-report-refresh-note" role="status" aria-live="polite">
                <RefreshCw size={16} />
                <span>Обновляем отчет. Можно продолжать работу с текущими данными.</span>
              </div>
            )}

            {showReportContent && (
              <>
                <div className="vella-kpis">
                  {kpis.slice(0, 4).map((kpi) => (
                    <div className="vella-kpi" key={kpi.id}>
                      <div className="vella-kpi-label">{kpi.label}{kpi.hint && <HelpTip>{kpi.hint}</HelpTip>}</div>
                      <div className="vella-kpi-value">{kpi.value}</div>
                      {kpi.delta && <div className={`vella-kpi-delta ${toneClass(kpi.delta.tone)}`}>{kpi.delta.label}</div>}
                    </div>
                  ))}
                </div>

            {digest && digestMode === 'period' && (
              <div className="vella-report-grid">
                <div className="vella-section">
                  <div className="vella-section-title">План-факт</div>
                  {digest.planFactRows.length === 0 && (
                    <button className="vella-plan-row" type="button" onClick={() => pushToast('План-факт ожидает решения по источнику планов')}>
                      <span>План не создан</span>
                      <strong>—</strong>
                      <em>после подтверждения заказчиков добавим создание плана</em>
                    </button>
                  )}
                  {digest.planFactRows.map((row) => (
                    <button className="vella-plan-row" key={row.ownerId} type="button" onClick={() => pushToast(`Открыт план-факт: ${row.name}`)}>
                      <span>{row.name}</span>
                      <strong>{formatNullableRub(row.factKopecks)}</strong>
                      <em>{formatNullablePct(row.completionPct)} · {planFactStatusLabel(row.status)}</em>
                    </button>
                  ))}
                </div>
                <div className="vella-section">
                  <div className="vella-section-title">Критичные события</div>
                  {digest.problemRows.slice(0, 4).map((row, index) => (
                    row.reason === 'oos_risk' ? (
                      <OosRiskSummary key={String(row.id ?? index)} row={row} onOpenStock={() => navigate(routeFor('/wb/reports/stock'))} />
                    ) : (
                      <button className="vella-plan-row" key={String(row.id ?? index)} type="button" onClick={() => navigate(routeFor('/wb/reports/abc'))}>
                        <span>{String(row.sku ?? row.title ?? 'Событие')}</span>
                        <strong>{String(row.metric ?? 'Проверка')}</strong>
                        <em>{String(row.recommendation ?? row.details ?? 'в работу')}</em>
                      </button>
                    )
                  ))}
                </div>
              </div>
            )}

            <ChartBars data={digest ? (digest.weeklyBalance ?? digest.charts[0] ?? emptyChart) : (report?.chart ?? emptyChart)} />

            {digest?.periodCards && digest.periodCards.length > 0 && (
              <div className="vella-report-grid">
                {digest.periodCards.map((card) => (
                  <div className="vella-section" key={card.id}>
                    <div className="vella-section-title">{card.label}</div>
                    <button className="vella-plan-row" type="button" onClick={() => pushToast(`${card.label}: ${card.ordersUnits} заказов`)}>
                      <span>Заказы, шт</span><strong>{card.ordersUnits.toLocaleString('ru-RU')}</strong><em>{formatRub(card.ordersKopecks)}</em>
                    </button>
                    <button className="vella-plan-row" type="button" onClick={() => pushToast(`${card.label}: продажи`)}>
                      <span>Продажи</span><strong>{card.salesUnits.toLocaleString('ru-RU')}</strong><em>выкуп {card.buyoutPct == null ? '—' : `${card.buyoutPct.toFixed(1)}%`}</em>
                    </button>
                    <button className="vella-plan-row" type="button" onClick={() => pushToast(`${card.label}: возвраты`)}>
                      <span>Возвраты</span><strong>{card.returnsUnits.toLocaleString('ru-RU')}</strong><em>выручка {formatRub(card.revenueKopecks)}</em>
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="vella-toolbar">
              <div className="vella-toolbar-left">
                <div className="vella-search-wrap">
                  <Search size={15} />
                  <input className="vella-search" placeholder="Поиск по таблице" value={search} onChange={(event) => setSearch(event.target.value)} />
                </div>
                <button
                  className={`vella-chip ${brand !== 'Все' ? 'active' : ''}`}
                  type="button"
                  onClick={() => setBrand(brands[(brands.indexOf(brand) + 1) % brands.length] ?? 'Все')}
                >
                  Бренды: {brand}
                </button>
                <select
                  className="vella-button"
                  aria-label="Ответственный менеджер"
                  value={managerFilter}
                  onChange={(event) => setManagerFilter(event.target.value)}
                >
                  <option value="all">Все менеджеры</option>
                  <option value="mine">Мои SKU</option>
                  <option value="unassigned">Без ответственного</option>
                  {Array.from(new Map(rows.map((row) => [String(row.managerId ?? ''), String(row.manager ?? '')])).entries())
                    .filter(([id, name]) => id && name)
                    .map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
                {(activeReport === 'abc' || activeReport === 'rnp') && (
                  <div className="vella-position">
                    <button className="vella-chip active" type="button" onClick={() => setPopover(popover === 'group' ? null : 'group')}>
                      Группировка: {groupOptions.find((item) => item.id === groupBy)?.label}
                    </button>
                    {popover === 'group' && (
                      <div className="vella-popover">
                        {groupOptions.map((option) => (
                          <button className="vella-popover-row" key={option.id} type="button" onClick={() => {
                            setGroupBy(option.id)
                            setPopover(null)
                          }}>
                            <Check size={14} opacity={groupBy === option.id ? 1 : 0.15} /> {option.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                {activeReport === 'pnl' && (
                  <button
                    className="vella-chip active"
                    type="button"
                    onClick={() => {
                      setPnlSource((current) => current === 'operational' ? 'financial' : 'operational')
                      setModal('blocked')
                    }}
                  >
                    Источник: {pnlSource === 'operational' ? 'оперативный' : 'финансовый'}
                  </button>
                )}
              </div>
              <div className="vella-toolbar-right">
                <div className="vella-position">
                  <button className="vella-button" type="button" onClick={() => setPopover(popover === 'columns' ? null : 'columns')}>
                    <Columns3 size={16} /> Колонки
                  </button>
                  {popover === 'columns' && (
                    <div className="vella-popover">
                      {columns.map((column) => (
                        <button className="vella-popover-row" key={column.key} type="button" onClick={() => toggleColumn(column.key)}>
                          <Check size={14} opacity={hiddenForReport.has(column.key) ? 0.15 : 1} /> {column.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="vella-panel">
              <div className="vella-table-wrap">
                <table className="vella-table">
                  <thead>
                    <tr>
                      {visibleColumns.map((column) => (
                        <th
                          className={`${column.sticky ? 'sticky ' : ''}sortable ${column.align === 'right' ? 'num' : ''}`}
                          key={column.key}
                          onClick={() => toggleSort(column.key)}
                        >
                          {column.label}{sortKey === column.key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ''}
                        </th>
                      ))}
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((row, index) => (
                      <tr key={`${row.sku ?? row.campaignId ?? index}`}>
                        {visibleColumns.map((column) => (
                          <td className={`${column.sticky ? 'sticky ' : ''}${column.align === 'right' ? 'num' : ''}`} key={column.key}>
                            {formatReportCell(row, column)}
                          </td>
                        ))}
                        <td>
                          <button className="vella-button" type="button" onClick={() => setDrawerRow(row)}>
                            <ExternalLink size={14} /> Детали
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredRows.length === 0 && <ReportEmptyState title="Нет строк по выбранным фильтрам" text="Измените поиск, бренд или менеджера, чтобы вернуть строки отчета." />}
              </div>
            </div>

            {digest && digestMode === 'now' && (
              <div className="vella-report-grid">
                <div className="vella-section">
                  <div className="vella-section-title">Критичные события</div>
                  {digest.problemRows.slice(0, 3).map((row, index) => (
                    row.reason === 'oos_risk' ? (
                      <OosRiskSummary key={String(row.id ?? index)} row={row} onOpenStock={() => navigate(routeFor('/wb/reports/stock'))} />
                    ) : (
                      <button className="vella-plan-row" key={String(row.id ?? index)} type="button" onClick={() => navigate(routeFor('/wb/reports/abc'))}>
                        <span>{String(row.metric ?? 'Событие')}</span>
                        <strong>{String(row.sku ?? row.campaignName ?? row.title ?? '—')}</strong>
                        <em>{String(row.recommendation ?? row.details ?? row.reason ?? 'проверить')}</em>
                      </button>
                    )
                  ))}
                  {digest.problemRows.length === 0 && (
                    <button className="vella-plan-row" type="button" onClick={() => pushToast('Критичных событий нет')}>
                      <span>Очередь пуста</span>
                      <strong>0</strong>
                      <em>за выбранный период</em>
                    </button>
                  )}
                </div>
                <div className="vella-section">
                  <div className="vella-section-title">Оперативный монитор</div>
                  <button className="vella-plan-row" type="button" onClick={() => pushToast('Свежесть источников отчета')}>
                    <span>Свежесть</span>
                    <strong>{digest.meta.freshnessState}</strong>
                    <em>{new Date(digest.meta.lastUpdatedAt).toLocaleString('ru-RU')}</em>
                  </button>
                </div>
              </div>
            )}
              </>
            )}
          </section>
        </main>
      </div>

      {drawerRow && (
        <>
          <div className="vella-drawer-overlay" onClick={() => setDrawerRow(null)} />
          <aside className="vella-drawer" aria-label="Детали строки отчета">
            <div className="vella-drawer-head">
              <div>
                <div className="vella-drawer-title">{String(drawerRow.sku ?? drawerRow.campaignName ?? 'Строка отчета')}</div>
                <div className="vella-muted">{title}</div>
              </div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setDrawerRow(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-drawer-body">
              <div className="vella-section">
                <div className="vella-section-title">Контекст</div>
                <p className="vella-muted">
                  Здесь будут комментарии, история решений и действия по выбранной строке отчета.
                </p>
              </div>
              <button className="vella-button primary" type="button" onClick={() => pushToast('Комментарий будет доступен в карточке строки')}>
                Добавить комментарий
              </button>
            </div>
          </aside>
        </>
      )}

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true">
          <div className="vella-modal">
            <div className="vella-modal-head">
              <div className="vella-modal-title">{modal === 'export' ? 'Экспорт отчета' : 'Блокер действия'}</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-modal-body">
              {modal === 'export'
                ? exportData
                  ? `Будет создан файл ${exportData.fileName}, строк: ${exportData.rows}. ${exportData.emptySourceNote ?? ''}`
                  : 'Готовим файл для выгрузки...'
                : report?.warning ?? 'Финальный источник пока не подтвержден, действие заблокировано до свежих данных.'}
            </div>
            <div className="vella-modal-foot">
              <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
              <button className="vella-button primary" type="button" onClick={() => {
                pushToast(modal === 'export' ? (exportData?.rows ? 'Экспорт поставлен в очередь' : 'Экспорт недоступен') : 'Блокер зафиксирован')
                setModal(null)
              }}>
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="vella-toast-stack"><div className="vella-toast">{toast}</div></div>}
    </div>
  )
}
