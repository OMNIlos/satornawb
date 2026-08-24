import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Clock3, Copy, Database, FileText, Moon, ReceiptText, RefreshCw, TerminalSquare, X } from 'lucide-react'
import { authorizationHeaders } from '@/features/auth/authApi'
import { useAuth } from '@/features/auth/authContext'
import { apiRequest } from '@/lib/api'
import { resetLiveRepricerParityCache } from './liveParityData'
import './WorkerOverlay.css'

type WorkerRunItem = {
  articleId?: string | null
  status?: string | null
  skipReason?: string | null
  frontendStrategyId?: string | null
  strategyId?: string | null
  explanation?: string | null
  applyState?: string | null
  draftId?: string | null
  oldPriceKopecks?: number | null
  recommendedPriceKopecks?: number | null
  deltaKopecks?: number | null
  blockedReasons?: string[]
  blockerDetails?: Array<{
    code?: string | null
    message?: string | null
    observedValue?: unknown
    threshold?: unknown
  }>
}

type WorkerRun = {
  runId: string | null
  trigger: string | null
  createdAt: string | null
  executedCount: number
  skippedCount: number
  blockedCount: number
  itemCount: number
  items: WorkerRunItem[]
}

type WbSyncStep = {
  source?: string | null
  key?: string | null
  label?: string | null
  status?: string | null
  state?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  progressPercent?: number | null
  progressCurrent?: number | null
  progressTotal?: number | null
  phase?: string | null
  message?: string | null
  request?: string | null
  count?: number | null
  rowsCount?: number | null
  error?: string | null
}

type WbSyncStatus = {
  state?: string | null
  running?: boolean | null
  stale?: boolean | null
  runId?: string | null
  trigger?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  periodDays?: number | null
  dateFrom?: string | null
  dateTo?: string | null
  currentSource?: string | null
  steps?: WbSyncStep[]
  error?: string | null
  updatedAt?: string | null
}

type WbSyncHistoryItem = {
  id?: string | null
  type?: string | null
  decision?: string | null
  reason?: string | null
  runId?: string | null
  state?: string | null
  trigger?: string | null
  observedAt?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  intervalMinutes?: number | null
  lastRunAt?: string | null
  nextRunAt?: string | null
  secondsUntilNextRun?: number | null
  periodDays?: number | null
  dateFrom?: string | null
  dateTo?: string | null
  sources?: string[]
  settings?: {
    fullSyncEnabled?: boolean | null
    fullSyncIntervalMinutes?: number | null
    envFullSyncIntervalMinutes?: number | null
    schedulerPollIntervalMinutes?: number | null
  } | null
  lastStatus?: {
    runId?: string | null
    state?: string | null
    trigger?: string | null
    startedAt?: string | null
    finishedAt?: string | null
  } | null
  steps?: WbSyncStep[]
  error?: string | null
}

type WorkerStatus = {
  organizationId: number
  mode: {
    wbApiMode: string
    realPriceApplyEnabled: boolean
    schedulerEnabled: boolean
    schedulerPollIntervalMinutes?: number
    executeIntervalMinutes: number
    fullSyncEnabled?: boolean
    fullSyncIntervalMinutes?: number
    fullSyncPromotionsEnabled?: boolean
    workerAutoApplyPricesEnabled?: boolean
  }
  timing: {
    serverNow: string
    lastSchedulerRunAt: string | null
    nextSchedulerPollAt?: string | null
    secondsUntilNextSchedulerPoll?: number | null
    nextRunAt: string | null
    secondsUntilNextRun: number | null
    lastFullSyncAt?: string | null
    nextFullSyncAt?: string | null
    secondsUntilNextFullSync?: number | null
  }
  runs: WorkerRun[]
  pendingApprovals: PendingPriceApproval[]
  sync?: WbSyncStatus | null
  syncHistory?: WbSyncHistoryItem[]
  nightMedian?: NightMedianDebug | null
}

type NightMedianDebug = {
  enabled?: boolean
  collectEnabled?: boolean
  autoAllSkus?: boolean
  phase?: string | null
  isWindowActive?: boolean | null
  activeStrategySkuCount?: number | null
  eligibleSkuCount?: number | null
  manualNightSkuCount?: number | null
  individualEnabledSkuCount?: number | null
  mode?: string | null
  windowLabel?: string | null
  timezone?: string | null
  applyDeltaPct?: number | string | null
  lastCollectedAt?: string | null
  activeWindowKey?: string | null
  latestWindowKey?: string | null
  latestWindowUpdatedAt?: string | null
  windowsCount?: number | null
  sampledSkuCount?: number | null
  appliedSkuCount?: number | null
  pendingSkuCount?: number | null
  eligibleItems?: Array<{
    articleId?: string | null
    strategyId?: string | null
    strategyName?: string | null
    assignmentSource?: string | null
    nightMedianEnabled?: boolean | null
  }>
  items?: Array<{
    articleId?: string | null
    nmId?: number | string | null
    samplesCount?: number | null
    medianBaskets?: number | null
    lastBaskets?: number | null
    lastAt?: string | null
    applied?: boolean | null
    appliedAt?: string | null
  }>
}

type PendingPriceApproval = {
  approvalId: string
  draftId?: string | null
  jobId?: string | null
  runId?: string | null
  trigger?: string | null
  articleId: string
  nmId?: number | null
  name?: string | null
  skuName?: string | null
  productName?: string | null
  status: string
  applyState?: string | null
  sourceStatus?: string | null
  wbMutationSent?: boolean | null
  wbUploadId?: number | null
  wbStatus?: number | null
  statusLabel?: string | null
  blockedReasons?: string[]
  notes?: string[]
  rowErrors?: Array<{ errorText?: string | null }>
  error?: string | null
  source?: string | null
  scenario?: string | null
  frontendStrategyId?: string | null
  strategyId?: string | null
  strategyName?: string | null
  oldPriceKopecks?: number | null
  recommendedPriceKopecks?: number | null
  deltaKopecks?: number | null
  explanation?: string | null
  createdAt?: string | null
  updatedAt?: string | null
}

type PriceApprovalDecisionResponse = {
  approval?: PendingPriceApproval | null
  job?: {
    state?: string | null
    wbUploadId?: number | null
    wbStatus?: number | null
    blockerIds?: string[]
    notes?: string[]
    rowErrors?: Array<{ errorText?: string | null }>
  } | null
}

type PriceApprovalBulkDecisionResponse = {
  results: Array<PriceApprovalDecisionResponse & {
    approvalId: string
    ok: boolean
    error?: string | null
  }>
}

type FinanceDiagnosticsPayload = {
  source: string
  state: string
  refreshed: boolean
  periodDays: number
  dateFrom: string
  dateTo: string
  fetchedAt?: string | null
  count: number
  rowsCount: number
  rawRowsStrippedFromCache: boolean
  diagnostics: {
    state?: string
    tax?: {
      taxPct?: number
      taxKopecks?: number
      taxIncludedInExpenses?: boolean
      note?: string
    }
    formula?: Record<string, unknown>
    totals?: Record<string, number>
    storageAcceptance?: {
      rawRowsAvailable?: boolean
      rawRowsCount?: number | null
      requestedFields?: string[]
      paidStorageFieldRequested?: boolean | null
      paidStorageRowsWithField?: number | null
      paidStorageNonzeroRows?: number | null
      paidStorageSum?: number | null
      paidStorageSumKopecks?: number | null
      paidStorageAggregateSumKopecks?: number | null
      paidStorageNonzeroSkuCount?: number | null
      paidStorageMissingNmRows?: number | null
      paidStorageMissingNmSumKopecks?: number | null
      paidAcceptanceFieldRequested?: boolean | null
      paidAcceptanceRowsWithField?: number | null
      paidAcceptanceNonzeroRows?: number | null
      paidAcceptanceSum?: number | null
      paidAcceptanceSumKopecks?: number | null
      paidAcceptanceAggregateSumKopecks?: number | null
      paidAcceptanceNonzeroSkuCount?: number | null
      paidAcceptanceMissingNmRows?: number | null
      paidAcceptanceMissingNmSumKopecks?: number | null
      source?: string
      note?: string
    }
    paidStorageNonzeroRows?: number | null
    paidStorageSum?: number | null
    paidAcceptanceNonzeroRows?: number | null
    paidAcceptanceSum?: number | null
    adjustmentRows?: Array<Record<string, unknown>>
    adjustmentRowsTotal?: number
    adjustmentRowsReturned?: number
    skuSummaries?: Array<Record<string, unknown>>
    skuSummariesTotal?: number
    skuSummariesReturned?: number
    marginBreakdown?: {
      formula?: string
      itemsReturned?: number
      itemsTotalFromBuiltRows?: number
      totals?: Record<string, number>
      unassignedComponentsReturned?: number
      unassignedComponents?: Array<{
        key?: string
        label?: string
        operation?: string
        amountKopecks?: number
        effectKopecks?: number
        source?: string
        note?: string | null
      }>
      items?: Array<{
        articleId?: string | null
        nmId?: number | string | null
        name?: string | null
        actualNetProfitKopecks?: number | null
        expectedNetProfitKopecks?: number | null
        deltaKopecks?: number | null
        components?: Array<{
          key?: string
          label?: string
          operation?: string
          amountKopecks?: number
          effectKopecks?: number
          source?: string
          note?: string | null
        }>
      }>
    }
    marginBreakdownError?: {
      statusCode?: number
      detail?: unknown
    }
  }
}

type OneCCashFlowLogItem = {
  id: string
  receivedAt: string
  source?: string | null
  payload: Record<string, unknown>
  payloadKeys?: string[]
  clientHost?: string | null
  userAgent?: string | null
}

type OneCCashFlowLogsPayload = {
  total: number
  items: OneCCashFlowLogItem[]
}

const STATUS_REFRESH_MS = 15_000
const FINANCE_DIAGNOSTICS_LIMIT = 5000
const PRODUCTS_PERIOD_STORAGE_KEY = 'vella.products.analyticsPeriod'
const SUCCESSFUL_PRICE_APPLY_STATES = new Set(['accepted', 'local_applied', 'sent'])

const WORKER_REASON_LABELS: Record<string, string> = {
  auth_required: 'WB токен некорректный или истёк. Обновите токен в кабинете.',
  forbidden_scope: 'В WB токене нет роли записи цен. Нужен доступ Prices and discounts с правом записи.',
  WB_TOKEN_REQUIRED: 'WB токен не сохранён в кабинете организации.',
  'NO_ACCESS:price:send': 'У пользователя нет права price:send для отправки цен.',
  'WB-23': 'Не хватает свежих price/SPP/stock данных для безопасной отправки цены.',
  discovery_not_ready: 'Готовность WB price apply/SPP ещё не подтверждена.',
  margin_preview_blocked: 'Не удалось посчитать маржу: источник маржи заблокирован.',
  pmin_pmax_block: 'Цена не прошла проверку P_MIN/P_MAX.',
  source_stale_or_blocked: 'Критичные источники цены устарели или заблокированы.',
  source_stale_or_blocked_for_validation: 'Нельзя проверить цену: источник СПП/цены устарел или заблокирован.',
  spp_missing: 'Нет СПП по SKU, поэтому нельзя проверить цену покупателя и безопасно отправить цену в WB.',
  stock_oos: 'Остаток WB равен нулю, автоматическое изменение цены заблокировано.',
  cogs_missing: 'Не указана себестоимость SKU.',
  commission_missing: 'Не указана комиссия WB.',
  logistics_missing: 'Не указана логистика.',
  buyout_missing: 'Нет процента выкупа.',
  stock_missing: 'Нет актуального остатка WB.',
  wb_rate_limited: 'WB ограничил частоту запросов на изменение цен. Worker повторит позже.',
  wb_status_rate_limited: 'WB принял заявку на изменение цены, но временно ограничил проверку статуса. Цена может примениться после обработки WB.',
  rate_limited: 'WB ограничил частоту запросов. Нужно дождаться следующего окна.',
  manual_mode: 'Автоисполнение выключено: control plane стоит в ручном режиме.',
  warmup: 'SKU в прогреве, worker не меняет цену.',
  automation_disabled: 'Автоматизация выключена для этого SKU.',
  no_nm_id: 'У SKU нет nmId, цену нельзя отправить в WB.',
  no_strategy: 'Для SKU не назначена стратегия.',
  no_price_change: 'Стратегия не нашла изменения цены.',
  liquidation_not_due: 'Шаг ликвидации ещё не наступил.',
  night_median_collecting: 'Ночная медиана собирает корзины; цены ночью не меняются.',
  night_mode_disabled: 'Ночной режим выключен.',
  sku_not_found: 'SKU не найден в текущей WB-выборке.',
  wb_request_failed: 'WB отклонил запрос изменения цены.',
  wb_server_error: 'WB вернул серверную ошибку, retry возможен позже.',
  wb_sync_running: 'Идёт синхронизация WB-данных, расчёт цен пропущен до следующего тика.',
  execute_interval_not_due: 'Интервал стратегии ещё не наступил.',
  scheduler_disabled: 'Планировщик репрайсера выключен.',
  no_strategy_assignments: 'Нет SKU с назначенной стратегией.',
  no_cabinet_wb_token: 'В кабинете организации не найден WB token.',
}

const WORKER_STRATEGY_LABELS: Record<string, string> = {
  night_price_mode: 'ночная медиана',
  illiquid: 'ликвидация',
  baskets_orders: 'корзины+заказы',
  baskets_orders_4599: 'корзины+заказы',
  metric_dynamics: 'динамика выручки',
  revenue_dynamics_4600: 'динамика выручки',
}

function workerStrategyLabel(item: Pick<WorkerRunItem, 'frontendStrategyId' | 'strategyId'>) {
  const id = item.frontendStrategyId || item.strategyId || ''
  return WORKER_STRATEGY_LABELS[id] ?? (id || 'strategy')
}

function approvalProductName(item: PendingPriceApproval) {
  return item.productName || item.skuName || item.name || item.articleId || 'Товар'
}

function approvalProductMeta(item: PendingPriceApproval) {
  return [
    item.articleId ? `Артикул ${item.articleId}` : null,
    item.nmId ? `WB ${item.nmId}` : null,
    item.strategyName || workerStrategyLabel(item),
  ].filter(Boolean).join(' · ')
}

function approvalExplanation(item: PendingPriceApproval) {
  const explanation = item.explanation?.trim()
  if (explanation && !/approval_required|draft|worker|applyState/i.test(explanation)) {
    return explanation
  }
  const strategy = item.strategyName || workerStrategyLabel(item)
  return `Стратегия «${strategy}» пересчитала цену по текущим данным WB. Автоматическая отправка выключена, поэтому нужно решение менеджера.`
}

function workerItemStatusLabel(item: WorkerRunItem) {
  if (item.status === 'executed' && item.applyState === 'approval_required') return 'рассчитано, ждёт подтверждения'
  if (item.status === 'executed' && item.applyState === 'local_applied') return 'применено локально'
  if (item.status === 'executed' && item.applyState === 'accepted') return 'принято WB'
  if (item.status === 'executed') return 'рассчитано'
  if (item.status === 'blocked') return 'заблокировано'
  if (item.status === 'failed') return 'ошибка'
  if (item.status === 'skipped') return 'пропущено'
  return item.status ?? '—'
}

function describeWorkerReason(code: string | null | undefined) {
  if (!code) return ''
  return WORKER_REASON_LABELS[code] ?? code
}

function workerItemDetails(item: WorkerRunItem) {
  const reasons = [
    item.skipReason,
    ...(item.blockedReasons ?? []),
    ...(item.blockerDetails ?? []).map((detail) => detail.code),
  ]
    .filter((value): value is string => Boolean(value))
    .map(describeWorkerReason)
  const messages = (item.blockerDetails ?? [])
    .map((detail) => detail.message)
    .filter((value): value is string => Boolean(value))
  return Array.from(new Set([...reasons, ...messages])).filter(Boolean)
}

function formatCountdown(seconds: number | null | undefined) {
  if (seconds == null) return '—'
  const safeSeconds = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safeSeconds / 60)
  const rest = safeSeconds % 60
  return `${minutes}:${String(rest).padStart(2, '0')}`
}

function formatRunTime(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function secondsUntilFromIso(targetIso: string | null | undefined, serverNowIso: string | null | undefined) {
  if (!targetIso || !serverNowIso) return null
  const targetMs = new Date(targetIso).getTime()
  const serverNowMs = new Date(serverNowIso).getTime()
  if (!Number.isFinite(targetMs) || !Number.isFinite(serverNowMs)) return null
  return Math.max(0, Math.floor((targetMs - serverNowMs) / 1000))
}

function runTone(run: WorkerRun | undefined) {
  if (!run) return 'muted'
  if (run.blockedCount > 0) return 'warn'
  if (run.executedCount > 0) return 'ok'
  return 'muted'
}

function formatKopecks(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${Math.round(value / 100).toLocaleString('ru-RU')} ₽`
}

function formatCount(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return Math.round(value).toLocaleString('ru-RU')
}

function syncStepProgressPercent(step: WbSyncStep) {
  const value = Number(step.progressPercent)
  if (!Number.isFinite(value)) return null
  return Math.max(0, Math.min(100, Math.round(value)))
}

function formatRequestFlag(value: boolean | null | undefined) {
  if (value == null) return '—'
  return value ? 'да' : 'нет'
}

function nightMedianPhaseLabel(phase: string | null | undefined) {
  if (phase === 'collecting') return 'идёт ночной сбор'
  if (phase === 'waiting_for_night') return 'ждёт 23:00 МСК'
  if (phase === 'no_samples_collected') return 'окно прошло без samples'
  if (phase === 'waiting_for_morning_or_applied') return 'ждёт утра / уже применено'
  if (phase === 'off') return 'выключена'
  return 'нет статуса'
}

function syncHistoryTitle(item: WbSyncHistoryItem) {
  if (item.type === 'scheduler_decision') {
    if (item.decision === 'due') return 'scheduler решил запускать'
    if (item.decision === 'not_due') return 'scheduler пропустил'
    if (item.reason === 'wb_sync_stale') return 'scheduler увидел stale'
    if (item.reason === 'wb_sync_running') return 'scheduler увидел running'
    return 'scheduler decision'
  }
  if (item.type === 'sync_started') return 'WB sync стартовал'
  if (item.type === 'sync_finished') return 'WB sync завершился'
  return item.type || 'WB sync event'
}

function syncHistoryTone(item: WbSyncHistoryItem) {
  if (item.error || item.state === 'failed' || item.state === 'partial') return 'warn'
  if (item.type === 'scheduler_decision' && item.decision === 'due') return 'warn'
  if (item.type === 'scheduler_decision') return 'muted'
  if (item.type === 'sync_finished') return 'ok'
  return 'muted'
}

function syncReasonLabel(reason: string | null | undefined) {
  if (reason === 'full_sync_interval_not_due') return 'интервал WB sync ещё не наступил'
  if (reason === 'full_sync_interval_due') return 'прошёл интервал WB sync'
  if (reason === 'no_previous_full_sync') return 'нет предыдущего завершённого WB sync'
  if (reason === 'wb_sync_running') return 'предыдущий WB sync ещё идёт'
  if (reason === 'wb_sync_stale') return 'предыдущий WB sync помечен stale, автозапуск заблокирован'
  return reason || '—'
}

function describePriceApprovalFailure(response: PriceApprovalDecisionResponse) {
  const approval = response.approval ?? null
  const job = response.job ?? null
  const state = job?.state || approval?.applyState || approval?.status || 'unknown'
  if (state === 'sent') return 'WB принял заявку на изменение цены. Статус применения уточним позже, цена обновится после обработки WB.'
  const blockers = job?.blockerIds?.length ? job.blockerIds : approval?.blockedReasons
  const notes = job?.notes?.length ? job.notes : approval?.notes
  const rowErrors = job?.rowErrors?.length ? job.rowErrors : approval?.rowErrors
  const details = [
    blockers?.filter(Boolean).map(describeWorkerReason).join(', '),
    notes?.filter(Boolean).join('; '),
    rowErrors?.map((row) => row.errorText).filter(Boolean).join('; '),
    approval?.error,
    job?.wbStatus || approval?.wbStatus ? `WB status ${job?.wbStatus ?? approval?.wbStatus}` : null,
    job?.wbUploadId || approval?.wbUploadId ? `uploadID ${job?.wbUploadId ?? approval?.wbUploadId}` : null,
  ].filter(Boolean)
  return `WB не принял изменение цены: ${state}${details.length ? ` · ${details.join(' · ')}` : ''}`
}

function financeDiagnosticsQuery(refresh: boolean) {
  const params = new URLSearchParams({ limit: String(FINANCE_DIAGNOSTICS_LIMIT) })
  try {
    const stored = JSON.parse(window.localStorage.getItem(PRODUCTS_PERIOD_STORAGE_KEY) ?? '{}') as {
      days?: number
      fromIso?: string
      toIso?: string
    }
    if (stored.days) params.set('periodDays', String(stored.days))
    if (stored.fromIso) params.set('dateFrom', stored.fromIso)
    if (stored.toIso) params.set('dateTo', stored.toIso)
  } catch {
    params.set('periodDays', '30')
  }
  if (!params.has('periodDays')) params.set('periodDays', '30')
  if (refresh) params.set('refresh', 'true')
  return params.toString()
}

export function WorkerOverlay() {
  const { accessToken } = useAuth()
  const location = useLocation()
  const [visible, setVisible] = useState(true)
  const [openPanel, setOpenPanel] = useState<'worker' | 'finance' | 'sync' | 'night' | 'cashFlow' | null>(null)
  const [status, setStatus] = useState<WorkerStatus | null>(null)
  const [financeDiagnostics, setFinanceDiagnostics] = useState<FinanceDiagnosticsPayload | null>(null)
  const [cashFlowLogs, setCashFlowLogs] = useState<OneCCashFlowLogsPayload | null>(null)
  const [fetchedAtMs, setFetchedAtMs] = useState(() => Date.now())
  const [nowMs, setNowMs] = useState(() => Date.now())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [financeLoading, setFinanceLoading] = useState(false)
  const [financeError, setFinanceError] = useState<string | null>(null)
  const [financeCopied, setFinanceCopied] = useState(false)
  const [cashFlowLoading, setCashFlowLoading] = useState(false)
  const [cashFlowError, setCashFlowError] = useState<string | null>(null)
  const [approvalBusy, setApprovalBusy] = useState<string | null>(null)
  const [approvalError, setApprovalError] = useState<string | null>(null)
  const [failedApproval, setFailedApproval] = useState<PendingPriceApproval | null>(null)

  const headers = useMemo(() => authorizationHeaders(accessToken ?? ''), [accessToken])

  const loadStatus = useCallback(async () => {
    setLoading(true)
    try {
      const payload = await apiRequest<WorkerStatus>('/api/v1/wb-repricer/worker/status?limit=8', {
        headers,
        cache: 'no-store',
      })
      if (payload) {
        setStatus(payload)
        setFetchedAtMs(Date.now())
        setError(null)
      }
    } catch {
      setError('worker status недоступен')
    } finally {
      setLoading(false)
    }
  }, [headers])

  const loadFinanceDiagnostics = useCallback(async (refresh = false) => {
    setFinanceLoading(true)
    try {
      const payload = await apiRequest<FinanceDiagnosticsPayload>(
        `/api/v1/wb-repricer/finance-diagnostics?${financeDiagnosticsQuery(refresh)}`,
        {
          headers,
          cache: 'no-store',
        },
      )
      if (payload) {
        setFinanceDiagnostics(payload)
        setFinanceError(null)
        if (refresh) {
          resetLiveRepricerParityCache()
          const productsRuntime = window as typeof window & {
            __vellaLoadLiveRepricerProducts?: () => void | Promise<unknown>
          }
          const reload = productsRuntime.__vellaLoadLiveRepricerProducts?.()
          void Promise.resolve(reload).finally(() => {
            window.dispatchEvent(new CustomEvent('vella:products-rows-updated'))
            window.dispatchEvent(new CustomEvent('vella:products-kpi-updated'))
          })
        }
      }
    } catch {
      setFinanceError('финансовый лог недоступен')
    } finally {
      setFinanceLoading(false)
    }
  }, [headers])

  const toggleFinancePanel = useCallback(() => {
    const shouldOpen = openPanel !== 'finance'
    setOpenPanel(shouldOpen ? 'finance' : null)
    if (shouldOpen && !financeDiagnostics) void loadFinanceDiagnostics(false)
  }, [financeDiagnostics, loadFinanceDiagnostics, openPanel])

  const copyFinanceDiagnostics = useCallback(async () => {
    if (!financeDiagnostics) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(financeDiagnostics, null, 2))
      setFinanceCopied(true)
      window.setTimeout(() => setFinanceCopied(false), 1400)
    } catch {
      setFinanceError('не удалось скопировать JSON')
    }
  }, [financeDiagnostics])

  const loadCashFlowLogs = useCallback(async () => {
    setCashFlowLoading(true)
    try {
      const payload = await apiRequest<OneCCashFlowLogsPayload>('/api/1c/cash-flow/logs?limit=50', {
        headers,
        cache: 'no-store',
      })
      if (payload) {
        setCashFlowLogs(payload)
        setCashFlowError(null)
      }
    } catch {
      setCashFlowError('логи 1С недоступны')
    } finally {
      setCashFlowLoading(false)
    }
  }, [headers])

  const toggleCashFlowPanel = useCallback(() => {
    const shouldOpen = openPanel !== 'cashFlow'
    setOpenPanel(shouldOpen ? 'cashFlow' : null)
    if (shouldOpen) void loadCashFlowLogs()
  }, [loadCashFlowLogs, openPanel])

  const closePendingApproval = useCallback((approvalId: string) => {
    setStatus((current) => current
      ? {
          ...current,
          pendingApprovals: (current.pendingApprovals ?? []).filter((item) => item.approvalId !== approvalId),
        }
      : current)
    setApprovalError(null)
    setFailedApproval(null)
  }, [])

  const decidePendingApproval = useCallback(async (approvalId: string, decision: 'approve' | 'reject') => {
    setApprovalBusy(`${decision}:${approvalId}`)
    setApprovalError(null)
    setFailedApproval(null)
    try {
      const response = await apiRequest<PriceApprovalDecisionResponse>(`/api/v1/wb-repricer/price-approvals/${encodeURIComponent(approvalId)}/${decision}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          reason: decision === 'approve' ? 'manager confirmed worker price change' : 'manager rejected worker price change',
        }),
        cache: 'no-store',
      })
      if (decision === 'approve') {
        const state = response?.job?.state ?? response?.approval?.applyState ?? response?.approval?.status
        if (!state || !SUCCESSFUL_PRICE_APPLY_STATES.has(state)) {
          setFailedApproval(response?.approval ?? null)
          setApprovalError(describePriceApprovalFailure(response ?? {}))
          void loadStatus()
          return
        }
      }
      closePendingApproval(approvalId)
      resetLiveRepricerParityCache()
      window.dispatchEvent(new CustomEvent('vella:products-rows-updated'))
      window.dispatchEvent(new CustomEvent('vella:products-kpi-updated'))
      if (decision === 'approve') void loadStatus()
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'не удалось обработать подтверждение цены'
      if (message.includes('PENDING_PRICE_APPROVAL_ALREADY_CLOSED')) {
        closePendingApproval(approvalId)
        void loadStatus()
        return
      }
      setApprovalError(message)
    } finally {
      setApprovalBusy(null)
    }
  }, [closePendingApproval, headers, loadStatus])

  useEffect(() => {
    if (!visible) return
    void loadStatus()
    const intervalId = window.setInterval(() => void loadStatus(), STATUS_REFRESH_MS)
    return () => window.clearInterval(intervalId)
  }, [loadStatus, visible])

  useEffect(() => {
    if (!visible) return
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(intervalId)
  }, [visible])

  if (!visible || !location.pathname.startsWith('/wb/repricer')) return null

  const latestRun = status?.runs?.[0]
  const pendingApprovals = status?.pendingApprovals ?? []
  const currentApproval = pendingApprovals.find((item) => item.status === 'pending') ?? null
  const approvalModal = currentApproval ?? (approvalError && failedApproval ? failedApproval : null)
  const approvalCanDecide = approvalModal?.status === 'pending'
  const pendingApprovalCount = pendingApprovals.filter((item) => item.status === 'pending').length
  const decideAllPendingApprovals = async (decision: 'approve' | 'reject') => {
    const targets = pendingApprovals.filter((item) => item.status === 'pending')
    if (!targets.length) return
    setApprovalBusy(`${decision}:all`)
    setApprovalError(null)
    setFailedApproval(null)
    try {
      const response = await apiRequest<PriceApprovalBulkDecisionResponse>('/api/v1/wb-repricer/price-approvals/bulk', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          approvalIds: targets.map((item) => item.approvalId),
          decision,
          reason: decision === 'approve' ? 'manager confirmed all worker price changes' : 'manager rejected all worker price changes',
        }),
        cache: 'no-store',
      })
      const results = response?.results ?? []
      if (!results.length) throw new Error('сервер не вернул результат обработки цен')
      const succeededIds = new Set(results.filter((item) => item.ok).map((item) => item.approvalId))
      setStatus((current) => current
        ? {
            ...current,
            pendingApprovals: (current.pendingApprovals ?? []).filter((item) => !succeededIds.has(item.approvalId)),
          }
        : current)
      if (succeededIds.size) {
        resetLiveRepricerParityCache()
        window.dispatchEvent(new CustomEvent('vella:products-rows-updated'))
        window.dispatchEvent(new CustomEvent('vella:products-kpi-updated'))
      }
      const failed = results.find((item) => !item.ok)
      if (failed) {
        setFailedApproval(failed.approval ?? targets.find((item) => item.approvalId === failed.approvalId) ?? null)
        setApprovalError(failed.approval || failed.job ? describePriceApprovalFailure(failed) : failed.error || 'не удалось обработать часть цен')
      }
      if (decision === 'approve' || failed) void loadStatus()
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'не удалось обработать подтверждения цен'
      setApprovalError(message.includes('PENDING_PRICE_APPROVAL_ALREADY_CLOSED') ? 'Часть цен уже обработана. Обновляем список.' : message)
      void loadStatus()
    } finally {
      setApprovalBusy(null)
    }
  }
  const baseSeconds = status?.timing?.secondsUntilNextRun ?? secondsUntilFromIso(
    status?.timing?.nextRunAt,
    status?.timing?.serverNow,
  )
  const elapsedSeconds = Math.floor((nowMs - fetchedAtMs) / 1000)
  const countdownSeconds = baseSeconds == null ? null : Math.max(0, baseSeconds - elapsedSeconds)
  const baseSyncSeconds = status?.timing?.secondsUntilNextFullSync ?? secondsUntilFromIso(
    status?.timing?.nextFullSyncAt,
    status?.timing?.serverNow,
  )
  const syncCountdownSeconds = baseSyncSeconds == null ? null : Math.max(0, baseSyncSeconds - elapsedSeconds)
  const schedulerEnabled = Boolean(status?.mode?.schedulerEnabled)
  const fullSyncEnabled = Boolean(status?.mode?.fullSyncEnabled)
  const syncStatus = status?.sync ?? null
  const syncCountdownLabel = !fullSyncEnabled
    ? 'off'
    : syncStatus?.running
      ? 'идёт'
      : formatCountdown(syncCountdownSeconds)
  const tone = runTone(latestRun)
  const financeTotals = financeDiagnostics?.diagnostics.totals
  const financeTax = financeDiagnostics?.diagnostics.tax
  const storageAcceptance = financeDiagnostics?.diagnostics.storageAcceptance
  const marginBreakdown = financeDiagnostics?.diagnostics.marginBreakdown
  const marginTotals = marginBreakdown?.totals
  const marginTotalsRows = marginTotals
    ? [
        { key: 'actualNetProfitKopecks', label: 'Маржа всего', value: marginTotals.actualNetProfitKopecks, tone: 'strong' },
        { key: 'revenue', label: 'Выручка', value: marginTotals.revenue, tone: 'plus' },
        { key: 'totalDeductions', label: 'Все вычеты', value: (marginTotals.cogs ?? 0) + (marginTotals.expensesKopecks ?? 0) },
        { key: 'cogs', label: 'Себестоимость', value: marginTotals.cogs },
        { key: 'expensesKopecks', label: 'Расходы без себеса', value: marginTotals.expensesKopecks },
        { key: 'commission', label: 'Комиссия WB', value: marginTotals.commission },
        { key: 'logistics', label: 'Логистика WB', value: marginTotals.logistics },
        { key: 'storage', label: 'Хранение WB', value: marginTotals.storage },
        { key: 'unassignedStorage', label: 'Хранение без SKU', value: marginTotals.unassignedStorage, tone: 'muted' },
        { key: 'acceptance', label: 'Приемка WB', value: marginTotals.acceptance },
        { key: 'unassignedAcceptance', label: 'Приемка без SKU', value: marginTotals.unassignedAcceptance, tone: 'muted' },
        { key: 'penalty', label: 'Штрафы WB net', value: marginTotals.penalty },
        { key: 'deduction', label: 'Удержания WB net', value: marginTotals.deduction },
        { key: 'acquiring', label: 'Эквайринг', value: marginTotals.acquiring },
        { key: 'ads', label: 'Реклама WB', value: marginTotals.ads },
        { key: 'otherExpenses', label: 'Прочие расходы', value: marginTotals.otherExpenses },
        { key: 'additionalPayment', label: 'Доплаты WB', value: marginTotals.additionalPayment, tone: 'plus' },
        { key: 'tax', label: 'Налог справочно', value: marginTotals.tax, tone: 'muted' },
      ]
    : []
  const financeMeta = financeDiagnostics
    ? `${financeDiagnostics.dateFrom} — ${financeDiagnostics.dateTo} · rows ${financeDiagnostics.rowsCount} · adj ${financeDiagnostics.diagnostics.adjustmentRowsReturned ?? 0}/${financeDiagnostics.diagnostics.adjustmentRowsTotal ?? 0}`
    : 'кеш Finance detailed'
  const syncSteps = syncStatus?.steps ?? []
  const syncHistory = status?.syncHistory ?? []
  const nightMedian = status?.nightMedian ?? null
  const nightItems = nightMedian?.items ?? []
  const nightEligibleItems = nightMedian?.eligibleItems ?? []
  const syncMeta = syncStatus
    ? `${syncStatus.state ?? 'sync'}${syncStatus.running ? ' · идет' : ''} · ${syncStatus.dateFrom ?? '—'} — ${syncStatus.dateTo ?? '—'}`
    : 'WB sync лог пока пуст'
  const priceUpdateLogs = (status?.runs ?? []).flatMap((run) => (
    run.items
      .filter((item) => item.recommendedPriceKopecks != null || item.applyState || item.draftId)
      .map((item) => ({ run, item }))
  )).slice(0, 30)

  return (
    <div className="worker-overlay">
      <div className="worker-overlay-bar">
        <div className="worker-overlay-main">
          <Clock3 size={15} />
          <span>worker</span>
          <b>{schedulerEnabled ? formatCountdown(countdownSeconds) : 'off'}</b>
          <span>WB sync</span>
          <b>{syncCountdownLabel}</b>
          {status?.mode?.realPriceApplyEnabled ? <em>real</em> : <em>safe</em>}
          <em>{status?.mode?.workerAutoApplyPricesEnabled ? 'auto apply' : 'approval'}</em>
          {pendingApprovalCount > 0 ? <em className="worker-overlay-approval-chip">{pendingApprovalCount} approval</em> : null}
        </div>

        <span className={`worker-overlay-run ${tone}`}>
          {latestRun ? `${latestRun.executedCount}/${latestRun.blockedCount}/${latestRun.skippedCount}` : 'нет запусков'}
        </span>

        <button
          type="button"
          className={`worker-overlay-icon ${openPanel === 'worker' ? 'active' : ''}`}
          onClick={() => setOpenPanel((current) => current === 'worker' ? null : 'worker')}
          title="Логи worker"
        >
          <TerminalSquare size={15} />
        </button>
        <button
          type="button"
          className={`worker-overlay-icon ${openPanel === 'finance' ? 'active' : ''}`}
          onClick={toggleFinancePanel}
          title="Логи Finance detailed"
        >
          <FileText size={15} />
        </button>
        <button
          type="button"
          className={`worker-overlay-icon ${openPanel === 'sync' ? 'active' : ''}`}
          onClick={() => setOpenPanel((current) => current === 'sync' ? null : 'sync')}
          title="Логи WB sync и обновлений цен"
        >
          <Database size={15} />
        </button>
        <button
          type="button"
          className={`worker-overlay-icon ${openPanel === 'night' ? 'active' : ''}`}
          onClick={() => setOpenPanel((current) => current === 'night' ? null : 'night')}
          title="Отладка ночной медианы"
        >
          <Moon size={15} />
        </button>
        <button
          type="button"
          className={`worker-overlay-icon ${openPanel === 'cashFlow' ? 'active' : ''}`}
          onClick={toggleCashFlowPanel}
          title="Логи 1С cash-flow"
        >
          <ReceiptText size={15} />
        </button>
        <button type="button" className="worker-overlay-icon" onClick={() => void loadStatus()} disabled={loading} title="Обновить">
          <RefreshCw size={15} />
        </button>
        <button type="button" className="worker-overlay-icon" onClick={() => setVisible(false)} title="Закрыть">
          <X size={15} />
        </button>
      </div>

      {openPanel === 'worker' ? (
        <div className="worker-overlay-panel">
          <div className="worker-overlay-panel-head">
            <b>Логи worker</b>
            <span>{error ?? `org ${status?.organizationId ?? '—'} · интервал ${status?.mode?.executeIntervalMinutes ?? '—'} мин`}</span>
          </div>
          <div className="worker-overlay-runs">
            {status?.runs.map((run, runIndex) => (
              <div className="worker-overlay-log" key={run.runId ?? run.createdAt ?? `run-${runIndex}`}>
                <div className="worker-overlay-log-top">
                  <b>{run.runId?.slice(0, 13) ?? 'run'}</b>
                  <span>{formatRunTime(run.createdAt)}</span>
                  <em className={runTone(run)}>{run.executedCount} calc · {run.blockedCount} block · {run.skippedCount} skip</em>
                </div>
                {run.items.length ? (
                  <div className="worker-overlay-log-items">
                    {run.items.map((item) => {
                      const details = workerItemDetails(item)
                      return (
                        <div key={`${run.runId}-${item.articleId}-${item.status}`}>
                          <b>{item.articleId ?? 'SKU'}</b>
                          <span>{workerItemStatusLabel(item)} · {workerStrategyLabel(item)}{item.applyState ? ` · ${item.applyState}` : ''}</span>
                          {item.recommendedPriceKopecks != null ? (
                            <small>{formatKopecks(item.oldPriceKopecks)} → {formatKopecks(item.recommendedPriceKopecks)}</small>
                          ) : null}
                          {item.explanation ? <small>{item.explanation}</small> : null}
                          {details.length ? <small className="worker-overlay-reason">{details.join(' · ')}</small> : null}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p>В этом запуске SKU не выбраны.</p>
                )}
              </div>
            ))}
            {!status?.runs.length ? <p>Запусков worker пока нет.</p> : null}
          </div>
        </div>
      ) : null}

      {openPanel === 'sync' ? (
        <div className="worker-overlay-panel worker-overlay-sync-panel">
          <div className="worker-overlay-panel-head">
            <div className="worker-overlay-panel-title">
              <b>WB sync и цены</b>
              <span>{error ?? syncMeta}</span>
            </div>
            <div className="worker-overlay-panel-actions">
              <button type="button" onClick={() => void loadStatus()} disabled={loading}>
                обновить
              </button>
            </div>
          </div>
          <div className="worker-overlay-runs">
            <div className="worker-overlay-sync-grid">
              <div>
                <span>проверка worker</span>
                <b>{status?.mode?.schedulerEnabled ? `${status.mode.schedulerPollIntervalMinutes ?? 5} мин` : 'выключен'}</b>
              </div>
              <div>
                <span>шаг стратегии</span>
                <b>{status?.mode?.schedulerEnabled ? `${status.mode.executeIntervalMinutes} мин` : 'выключен'}</b>
              </div>
              <div>
                <span>WB sync</span>
                <b>
                  {status?.mode?.fullSyncEnabled
                    ? `${status.mode.fullSyncIntervalMinutes ?? '—'} мин · ${status.mode.fullSyncPromotionsEnabled === false ? 'без акций' : 'с акциями'}`
                    : 'выключен'}
                </b>
              </div>
              <div>
                <span>отправка цен</span>
                <b>{status?.mode?.workerAutoApplyPricesEnabled ? 'авто в WB' : 'через попап'}</b>
              </div>
              <div>
                <span>следующая проверка</span>
                <b>{formatRunTime(status?.timing?.nextSchedulerPollAt ?? null)}</b>
              </div>
              <div>
                <span>следующий шаг стратегии</span>
                <b>{formatRunTime(status?.timing?.nextRunAt ?? null)}</b>
              </div>
              <div>
                <span>следующий WB sync</span>
                <b>{syncStatus?.running ? 'после завершения' : formatRunTime(status?.timing?.nextFullSyncAt ?? null)}</b>
              </div>
              <div>
                <span>последний sync</span>
                <b>{formatRunTime(status?.timing?.lastFullSyncAt ?? syncStatus?.finishedAt ?? syncStatus?.updatedAt ?? syncStatus?.startedAt ?? null)}</b>
              </div>
            </div>

            <div className="worker-overlay-log">
              <div className="worker-overlay-log-top">
                <b>{syncStatus?.runId?.slice(0, 13) ?? 'WB sync'}</b>
                <span>{syncStatus?.trigger ?? syncStatus?.currentSource ?? '—'}</span>
                <em className={syncStatus?.error ? 'warn' : syncStatus?.running ? 'muted' : 'ok'}>
                  {syncStatus?.state ?? 'нет данных'}
                </em>
              </div>
              {syncStatus?.error ? <p>{syncStatus.error}</p> : null}
              {syncSteps.length ? (
                <div className="worker-overlay-log-items">
                  {syncSteps.map((step, index) => {
                    const progressPercent = syncStepProgressPercent(step)
                    const hasProgress = progressPercent != null && (step.status === 'running' || step.progressTotal != null)
                    return (
                      <div key={`${step.source ?? step.key ?? index}-${index}`}>
                        <b>{step.label ?? step.source ?? step.key ?? `step ${index + 1}`}</b>
                        <span>{step.status ?? step.state ?? '—'} · {formatRunTime(step.finishedAt ?? step.startedAt ?? null)}</span>
                        {hasProgress ? (
                          <div className="worker-overlay-sync-progress">
                            <div className="worker-overlay-sync-progress-top">
                              <span>{step.message ?? step.phase ?? 'progress'}</span>
                              <b>{progressPercent}%</b>
                            </div>
                            <div className="worker-overlay-sync-progress-track">
                              <i style={{ width: `${progressPercent}%` }} />
                            </div>
                            <small>
                              {formatCount(step.progressCurrent)} / {formatCount(step.progressTotal)}
                              {step.request ? ` · ${step.request}` : ''}
                            </small>
                          </div>
                        ) : null}
                        <small>
                          rows {formatCount(step.rowsCount ?? step.count)}
                          {step.error ? ` · ${step.error}` : ''}
                        </small>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p>Шагов WB sync пока нет в статусе.</p>
              )}
            </div>

            <div className="worker-overlay-log">
              <div className="worker-overlay-log-top">
                <b>История WB sync</b>
                <span>последние 24 часа</span>
                <em className={syncHistory.length ? 'ok' : 'muted'}>{syncHistory.length}</em>
              </div>
              {syncHistory.length ? (
                <div className="worker-overlay-log-items worker-overlay-sync-history">
                  {syncHistory.map((item, index) => {
                    const happenedAt = item.observedAt ?? item.finishedAt ?? item.startedAt ?? null
                    const interval = item.intervalMinutes ?? item.settings?.fullSyncIntervalMinutes ?? null
                    const poll = item.settings?.schedulerPollIntervalMinutes ?? status?.mode?.schedulerPollIntervalMinutes ?? null
                    const envInterval = item.settings?.envFullSyncIntervalMinutes ?? null
                    const sources = item.sources?.length ? item.sources.join(', ') : null
                    return (
                      <div key={item.id ?? `${item.type}-${item.runId}-${index}`}>
                        <b>
                          {syncHistoryTitle(item)}
                          {item.runId ? ` · ${item.runId.slice(0, 13)}` : ''}
                        </b>
                        <span>
                          {formatRunTime(happenedAt)}
                          {' · '}
                          <em className={syncHistoryTone(item)}>{item.decision ?? item.state ?? item.trigger ?? 'event'}</em>
                          {' · '}
                          {syncReasonLabel(item.reason)}
                        </span>
                        <small>
                          настройка {interval != null ? `${interval} мин` : '—'}
                          {envInterval != null ? ` · env ${envInterval} мин` : ''}
                          {poll != null ? ` · проверка scheduler ${poll} мин` : ''}
                          {item.lastRunAt ? ` · прошлый ${formatRunTime(item.lastRunAt)}` : ''}
                          {item.nextRunAt ? ` · должен ${formatRunTime(item.nextRunAt)}` : ''}
                          {item.secondsUntilNextRun != null ? ` · через ${formatCountdown(item.secondsUntilNextRun)}` : ''}
                        </small>
                        {item.lastStatus ? (
                          <small>
                            last status: {item.lastStatus.state ?? '—'} · {item.lastStatus.trigger ?? '—'}
                            {item.lastStatus.runId ? ` · ${item.lastStatus.runId.slice(0, 13)}` : ''}
                            {item.lastStatus.finishedAt ? ` · finish ${formatRunTime(item.lastStatus.finishedAt)}` : ''}
                          </small>
                        ) : null}
                        {sources ? <small>sources: {sources}</small> : null}
                        {item.dateFrom || item.dateTo ? <small>period: {item.dateFrom ?? '—'} — {item.dateTo ?? '—'}</small> : null}
                        {item.error ? <small className="worker-overlay-reason">{item.error}</small> : null}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p>История WB sync за сутки пока пустая. Следующий scheduler tick или ручной запуск появится здесь.</p>
              )}
            </div>

            <div className="worker-overlay-log">
              <div className="worker-overlay-log-top">
                <b>Обновления цен</b>
                <span>последние worker runs</span>
                <em className={priceUpdateLogs.length ? 'ok' : 'muted'}>{priceUpdateLogs.length}</em>
              </div>
              {priceUpdateLogs.length ? (
                <div className="worker-overlay-log-items">
                  {priceUpdateLogs.map(({ run, item }, index) => {
                    const details = workerItemDetails(item)
                    return (
                      <div key={`${run.runId}-${item.articleId}-${index}`}>
                        <b>{item.articleId ?? 'SKU'}</b>
                        <span>
                          {workerItemStatusLabel(item)} · {workerStrategyLabel(item)}
                          {item.applyState ? ` · ${item.applyState}` : ''}
                          {item.draftId ? ` · ${item.draftId}` : ''}
                        </span>
                        <small>{formatRunTime(run.createdAt)} · {formatKopecks(item.oldPriceKopecks)} → {formatKopecks(item.recommendedPriceKopecks)}</small>
                        {item.explanation ? <small>{item.explanation}</small> : null}
                        {details.length ? <small className="worker-overlay-reason">{details.join(' · ')}</small> : null}
                      </div>
                    )
                  })}
                </div>
              ) : (
                <p>В последних worker-запусках нет попыток обновить цену.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {openPanel === 'cashFlow' ? (
        <div className="worker-overlay-panel worker-overlay-sync-panel">
          <div className="worker-overlay-panel-head">
            <div className="worker-overlay-panel-title">
              <b>1С cash-flow</b>
              <span>{cashFlowError ?? `${cashFlowLogs?.total ?? 0} событий · POST /api/1c/cash-flow`}</span>
            </div>
            <div className="worker-overlay-panel-actions">
              <button type="button" onClick={() => void loadCashFlowLogs()} disabled={cashFlowLoading}>
                обновить
              </button>
            </div>
          </div>
          <div className="worker-overlay-runs">
            {cashFlowLoading && !cashFlowLogs ? <p>Загружаем логи 1С…</p> : null}
            {cashFlowLogs?.items.length ? (
              cashFlowLogs.items.map((item) => (
                <div className="worker-overlay-log" key={item.id}>
                  <div className="worker-overlay-log-top">
                    <b>{item.id.slice(0, 13)}</b>
                    <span>{formatRunTime(item.receivedAt)}</span>
                    <em className="ok">1С</em>
                  </div>
                  <div className="worker-overlay-log-items">
                    <div>
                      <b>{item.payloadKeys?.join(', ') || 'payload'}</b>
                      <span>{item.clientHost ?? 'host —'}{item.userAgent ? ` · ${item.userAgent}` : ''}</span>
                      <pre className="worker-overlay-json">{JSON.stringify(item.payload, null, 2)}</pre>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <p>1С ещё не присылала cash-flow события.</p>
            )}
          </div>
        </div>
      ) : null}

      {openPanel === 'night' ? (
        <div className="worker-overlay-panel worker-overlay-sync-panel">
          <div className="worker-overlay-panel-head">
            <div className="worker-overlay-panel-title">
              <b>Ночная медиана</b>
              <span>
                {nightMedian
                  ? `${nightMedianPhaseLabel(nightMedian.phase)} · покрыто ${nightMedian.eligibleSkuCount ?? 0} SKU · samples ${nightMedian.sampledSkuCount ?? 0}`
                  : 'debug-лог пока пуст'}
              </span>
            </div>
            <div className="worker-overlay-panel-actions">
              <button type="button" onClick={() => void loadStatus()} disabled={loading}>
                обновить
              </button>
            </div>
          </div>
          <div className="worker-overlay-runs">
            <div className="worker-overlay-sync-grid">
              <div><span>режим</span><b>{nightMedian?.enabled ? 'включен' : 'выключен'}</b></div>
              <div><span>фаза</span><b>{nightMedianPhaseLabel(nightMedian?.phase)}</b></div>
              <div><span>сбор ночью</span><b>{nightMedian?.collectEnabled ? 'включен' : 'выключен'}</b></div>
              <div><span>SKU scope</span><b>{nightMedian?.autoAllSkus ? 'все активные' : 'только с галкой SKU'}</b></div>
              <div><span>активных стратегий</span><b>{formatCount(nightMedian?.activeStrategySkuCount)}</b></div>
              <div><span>попадает под режим</span><b>{formatCount(nightMedian?.eligibleSkuCount)}</b></div>
              <div><span>назначено руками</span><b>{formatCount(nightMedian?.manualNightSkuCount)}</b></div>
              <div><span>галка на SKU</span><b>{formatCount(nightMedian?.individualEnabledSkuCount)}</b></div>
              <div><span>окно</span><b>{nightMedian?.windowLabel ?? '23:00-06:00'}</b></div>
              <div><span>часовой пояс</span><b>{nightMedian?.timezone ?? 'МСК'}</b></div>
              <div><span>дельта</span><b>{nightMedian?.applyDeltaPct ?? '—'}%</b></div>
              <div><span>последний сбор</span><b>{formatRunTime(nightMedian?.lastCollectedAt ?? null)}</b></div>
              <div><span>обновлено окно</span><b>{formatRunTime(nightMedian?.latestWindowUpdatedAt ?? null)}</b></div>
              <div><span>окон в кеше</span><b>{formatCount(nightMedian?.windowsCount)}</b></div>
              <div><span>ожидают утра</span><b>{formatCount(nightMedian?.pendingSkuCount)}</b></div>
            </div>
            <div className="worker-overlay-log">
              <div className="worker-overlay-log-top">
                <b>Покрытие режима</b>
                <span>{nightMedian?.autoAllSkus ? 'глобальная галка активна' : 'только выбранные SKU'}</span>
                <em className={(nightMedian?.eligibleSkuCount ?? 0) > 0 ? 'ok' : 'muted'}>{nightMedian?.eligibleSkuCount ?? 0}</em>
              </div>
              {nightEligibleItems.length ? (
                <div className="worker-overlay-log-items">
                  {nightEligibleItems.map((item) => (
                    <div key={`${item.articleId}-${item.strategyId}`}>
                      <b>{item.articleId ?? 'SKU'}</b>
                      <span>{item.strategyName || item.strategyId || 'стратегия'} · {item.assignmentSource || 'source'}</span>
                      <small>{item.nightMedianEnabled ? 'галка SKU включена' : 'попадает по глобальному режиму'}</small>
                    </div>
                  ))}
                </div>
              ) : (
                <p>Нет SKU с активной стратегией, которые попадают под ночную медиану. Проверь назначение стратегии у товара.</p>
              )}
            </div>
            <div className="worker-overlay-log">
              <div className="worker-overlay-log-top">
                <b>{nightMedian?.latestWindowKey ?? 'night median'}</b>
                <span>samples и утреннее применение</span>
                <em className={nightItems.length ? 'ok' : 'muted'}>{nightItems.length}</em>
              </div>
              {nightItems.length ? (
                <div className="worker-overlay-log-items">
                  {nightItems.map((item) => (
                    <div key={`${item.articleId}-${item.lastAt ?? ''}`}>
                      <b>{item.articleId ?? 'SKU'}</b>
                      <span>
                        samples {formatCount(item.samplesCount)} · median {formatCount(item.medianBaskets)} · last {formatCount(item.lastBaskets)}
                      </span>
                      <small>
                        {formatRunTime(item.lastAt ?? null)}
                        {item.applied ? ` · применено ${formatRunTime(item.appliedAt ?? null)}` : ' · ждёт утренней коррекции'}
                      </small>
                    </div>
                  ))}
                </div>
              ) : (
                <p>
                  Пока нет ночных samples. Если окно уже прошло, значит ночью worker не собрал baskets snapshots для этих SKU.
                  После фикса ручная стратегия «Ночная медиана» тоже будет попадать в ночной сбор.
                </p>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {openPanel === 'finance' ? (
        <div className="worker-overlay-panel worker-overlay-finance-panel">
          <div className="worker-overlay-panel-head">
            <div className="worker-overlay-panel-title">
              <b>Финансы WB</b>
              <span>{financeError ?? financeMeta}</span>
            </div>
            <div className="worker-overlay-panel-actions">
              <button type="button" onClick={() => void loadFinanceDiagnostics(false)} disabled={financeLoading}>
                кеш
              </button>
              <button type="button" onClick={() => void loadFinanceDiagnostics(true)} disabled={financeLoading}>
                WB
              </button>
              <button type="button" onClick={copyFinanceDiagnostics} disabled={!financeDiagnostics}>
                <Copy size={13} />
                {financeCopied ? 'ok' : 'json'}
              </button>
            </div>
          </div>
          <div className="worker-overlay-runs">
            {financeLoading && !financeDiagnostics ? <p>Загружаем финансовый лог…</p> : null}
            {financeDiagnostics ? (
              <div className="worker-overlay-finance">
                <div className="worker-overlay-finance-grid">
                  <div>
                    <span>налог в расходах</span>
                    <b>{financeTax?.taxIncludedInExpenses ? 'да' : 'нет'}</b>
                  </div>
                  <div>
                    <span>налог справочно</span>
                    <b>{formatKopecks(financeTax?.taxKopecks)}</b>
                  </div>
                  <div>
                    <span>расходы без налога</span>
                    <b>{formatKopecks(financeTotals?.expensesWithoutTaxKopecks)}</b>
                  </div>
                  <div>
                    <span>paidStorage raw</span>
                    <b>
                      {formatCount(storageAcceptance?.paidStorageNonzeroRows)} rows
                      {' · '}{formatKopecks(storageAcceptance?.paidStorageSumKopecks ?? storageAcceptance?.paidStorageSum)}
                    </b>
                  </div>
                  <div>
                    <span>paidStorage без nmId</span>
                    <b>
                      {formatCount(storageAcceptance?.paidStorageMissingNmRows)} rows
                      {' · '}{formatKopecks(storageAcceptance?.paidStorageMissingNmSumKopecks)}
                    </b>
                  </div>
                  <div>
                    <span>paidAcceptance raw</span>
                    <b>
                      {formatCount(storageAcceptance?.paidAcceptanceNonzeroRows)} rows
                      {' · '}{formatKopecks(storageAcceptance?.paidAcceptanceSumKopecks ?? storageAcceptance?.paidAcceptanceSum)}
                    </b>
                  </div>
                  <div>
                    <span>paidAcceptance без nmId</span>
                    <b>
                      {formatCount(storageAcceptance?.paidAcceptanceMissingNmRows)} rows
                      {' · '}{formatKopecks(storageAcceptance?.paidAcceptanceMissingNmSumKopecks)}
                    </b>
                  </div>
                  <div>
                    <span>fields запроса</span>
                    <b>
                      storage {formatRequestFlag(storageAcceptance?.paidStorageFieldRequested)}
                      {' · '}acceptance {formatRequestFlag(storageAcceptance?.paidAcceptanceFieldRequested)}
                    </b>
                  </div>
                  <div>
                    <span>raw строки Finance</span>
                    <b>
                      {storageAcceptance?.rawRowsAvailable ? 'есть' : 'нет'}
                      {' · '}source {storageAcceptance?.source ?? '—'}
                    </b>
                  </div>
                  <div>
                    <span>если бы с налогом</span>
                    <b>{formatKopecks(financeTotals?.expensesIfTaxIncludedKopecks)}</b>
                  </div>
                  <div>
                    <span>возвраты штрафов</span>
                    <b>{formatKopecks(financeTotals?.penaltyReturnedKopecks)}</b>
                  </div>
                  <div>
                    <span>компенсации удержаний</span>
                    <b>{formatKopecks(financeTotals?.deductionCompensationKopecks)}</b>
                  </div>
                  <div>
                    <span>доплаты WB</span>
                    <b>{formatKopecks(financeTotals?.additionalPaymentKopecks)}</b>
                  </div>
                </div>
                <div className="worker-overlay-finance-formula">
                  expenses = commission + logistics + storage + acceptance + penalty + deduction + acquiring + ads + otherExpenses - additionalPayment
                </div>
                {marginBreakdown?.items?.length ? (
                  <div className="worker-overlay-margin-list">
                    <div className="worker-overlay-margin-head">
                      <b>Сборка маржи</b>
                      <span>
                        итого {formatKopecks(marginTotals?.actualNetProfitKopecks)}
                        {' · '}расходы {formatKopecks(marginTotals?.expensesKopecks)}
                        {' · '}прочие {formatKopecks(marginTotals?.otherExpenses)}
                        {' · '}{marginBreakdown.itemsReturned ?? 0}/{marginBreakdown.itemsTotalFromBuiltRows ?? 0} SKU
                      </span>
                    </div>
                    <div className="worker-overlay-margin-totals">
                      {marginTotalsRows.map((row) => (
                        <div className={`worker-overlay-margin-total ${row.tone ?? ''}`} key={row.key}>
                          <span>{row.label}</span>
                          <b>{formatKopecks(row.value)}</b>
                        </div>
                      ))}
                    </div>
                    {marginBreakdown.unassignedComponents?.length ? (
                      <div className="worker-overlay-margin-components worker-overlay-margin-unassigned">
                        {marginBreakdown.unassignedComponents.map((component) => (
                          <span key={component.key}>
                            <b>{component.operation}</b> {component.label}: {formatKopecks(component.amountKopecks)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {marginBreakdown.items.slice(0, 8).map((item, index) => (
                      <div className="worker-overlay-margin-row" key={`${item.articleId ?? item.nmId ?? index}`}>
                        <div className="worker-overlay-margin-row-top">
                          <b>{item.articleId ?? item.nmId ?? 'SKU'}</b>
                          <span>маржа {formatKopecks(item.actualNetProfitKopecks)} · delta {formatKopecks(item.deltaKopecks)}</span>
                        </div>
                        <div className="worker-overlay-margin-components">
                          {(item.components ?? []).map((component) => (
                            <span key={`${item.articleId}-${component.key}`}>
                              <b>{component.operation}</b> {component.label}: {formatKopecks(component.amountKopecks)}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : financeDiagnostics.diagnostics.marginBreakdownError ? (
                  <p>Сборка маржи недоступна: {String(financeDiagnostics.diagnostics.marginBreakdownError.detail ?? financeDiagnostics.diagnostics.marginBreakdownError.statusCode ?? 'ошибка')}</p>
                ) : null}
                <pre className="worker-overlay-finance-json">{JSON.stringify(financeDiagnostics, null, 2)}</pre>
              </div>
            ) : !financeLoading ? (
              <p>Финансовый лог пока пуст. Нажми WB, чтобы забрать свежий Finance detailed.</p>
            ) : null}
          </div>
        </div>
      ) : null}

      {approvalModal ? (
        <div className="worker-approval-backdrop" role="presentation">
          <section className="worker-approval-modal" role="dialog" aria-modal="true" aria-labelledby="worker-approval-title">
            <div className="worker-approval-head">
              <div className="worker-approval-mark"><AlertTriangle size={20} /></div>
              <div>
                <h2 id="worker-approval-title">{approvalCanDecide ? 'Нужно подтвердить изменение цены' : 'WB не принял изменение цены'}</h2>
                <p>
                  {approvalCanDecide
                    ? 'Репрайсер предлагает новую цену, но автоматическая отправка в WB выключена.'
                    : 'Цена не изменилась. Проверьте причину ниже и попробуйте позже.'}
                </p>
              </div>
            </div>
            <div className="worker-approval-product">
              <b>{approvalProductName(approvalModal)}</b>
              <span>{approvalProductMeta(approvalModal)}</span>
            </div>
            <div className="worker-approval-price">
              <span><small>Сейчас</small>{formatKopecks(approvalModal.oldPriceKopecks)}</span>
              <b>→</b>
              <strong><small>Предлагаем</small>{formatKopecks(approvalModal.recommendedPriceKopecks)}</strong>
              {approvalModal.deltaKopecks ? <em>{approvalModal.deltaKopecks > 0 ? '+' : ''}{formatKopecks(approvalModal.deltaKopecks)}</em> : null}
            </div>
            <div className="worker-approval-reason">
              <b>Что происходит</b>
              <span>{approvalExplanation(approvalModal)}</span>
              {approvalCanDecide ? (
                <small>
                  Нажмите «Отправить цену в WB», чтобы применить рекомендацию. Нажмите «Не менять цену», если цену нужно оставить как есть.
                </small>
              ) : null}
            </div>
            {approvalError ? <div className="worker-approval-error">{approvalError}</div> : null}
            <div className="worker-approval-actions">
              {approvalCanDecide ? (
                <>
                  {pendingApprovalCount > 1 ? (
                    <>
                      <button
                        type="button"
                        className="worker-approval-btn ghost"
                        onClick={() => void decideAllPendingApprovals('reject')}
                        disabled={approvalBusy !== null}
                      >
                        <X size={15} /> Отклонить все цены {pendingApprovalCount}
                      </button>
                      <button
                        type="button"
                        className="worker-approval-btn primary"
                        onClick={() => void decideAllPendingApprovals('approve')}
                        disabled={approvalBusy !== null}
                      >
                        <CheckCircle2 size={15} /> {approvalBusy === 'approve:all' ? 'Принимаем все…' : `Принять все цены ${pendingApprovalCount}`}
                      </button>
                    </>
                  ) : null}
                  <button
                    type="button"
                    className="worker-approval-btn ghost"
                    onClick={() => void decidePendingApproval(approvalModal.approvalId, 'reject')}
                    disabled={approvalBusy !== null}
                  >
                    <X size={15} /> Не менять цену
                  </button>
                  <button
                    type="button"
                    className="worker-approval-btn primary"
                    onClick={() => void decidePendingApproval(approvalModal.approvalId, 'approve')}
                    disabled={approvalBusy !== null}
                  >
                    <CheckCircle2 size={15} /> {approvalBusy?.startsWith('approve:') ? 'Отправляем…' : 'Отправить цену в WB'}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="worker-approval-btn ghost"
                  onClick={() => {
                    setApprovalError(null)
                    setFailedApproval(null)
                  }}
                >
                  <X size={15} /> Закрыть
                </button>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  )
}
