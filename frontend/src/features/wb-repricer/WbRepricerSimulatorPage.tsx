import { useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, Flame, Play, RefreshCw, Save, SlidersHorizontal, Zap } from 'lucide-react'
import { authorizationHeaders } from '@/features/auth/authApi'
import { useAuth } from '@/features/auth/authContext'
import { ApiError, apiRequest } from '@/lib/api'
import './WbRepricerSimulatorPage.css'

type SimulatorItem = {
  articleId: string
  nmId: number | null
  name: string
  status: 'auto' | 'liquidation' | string
  automationEnabled: boolean
  strategy: {
    id: string | null
    name: string | null
    type: string | null
    typedStrategyId: string | null
    assignmentSource: string | null
  }
  current: {
    sellerPriceKopecks: number | null
    buyerPriceKopecks: number | null
    sppPct: number | null
    baskets: number | null
    basketNorm: number | null
    ordersUnits: number | null
    salesUnits: number | null
    returnsUnits: number | null
    revenueKopecks: number | null
    buyoutPct: number | null
    stockUnits: number | null
    marginPct: number | null
    pMinKopecks: number | null
    pMaxKopecks: number | null
  }
  sourceState: Record<string, string | null>
  liquidation: { nextStepAt?: string; stepPct?: number; targetPriceKopecks?: number } | null
}

type SimulatorDashboard = {
  mode: {
    wbApiMode: string
    realPriceApplyEnabled: boolean
    localPriceApplyEnabled: boolean
    schedulerEnabled: boolean
    executeIntervalMinutes: number
    simulationAllowed: boolean
    inputOverridesAllowed?: boolean
    simulatorRunApplyAllowed?: boolean
    simulatorRunMode?: 'preview_only' | 'local_apply' | string
  }
  summary: {
    activeTotal: number
    strategyCount: number
    liquidationCount: number
  }
  worker: {
    beatTask: string
    orgTask: string
    intervalMinutes: number
    queue: string
    selectionRule: string
    priceApplyRule: string
  }
  items: SimulatorItem[]
}

type ExecuteItem = {
  articleId: string
  status: 'executed' | 'skipped' | 'blocked' | 'failed'
  skipReason?: string | null
  strategyId?: string | null
  frontendStrategyId?: string | null
  explanation?: string | null
  oldPriceKopecks?: number | null
  recommendedPriceKopecks?: number | null
  deltaKopecks?: number | null
  applyState?: string | null
  blockedReasons?: string[]
  blockerDetails?: Array<{
    code: string
    message?: string
    observedValue?: string | number | boolean | null
    threshold?: string | number | boolean | null
  }>
}

type ExecuteReport = {
  runId: string
  executedCount: number
  skippedCount: number
  blockedCount: number
  items: ExecuteItem[]
}

type SimulatorSaveResponse = { dashboard: SimulatorDashboard; item: SimulatorItem }

type FormState = {
  sellerPriceRub: string
  buyerPriceRub: string
  sppPct: string
  baskets: string
  basketNorm: string
  ordersUnits: string
  salesUnits: string
  returnsUnits: string
  revenueRub: string
  buyoutPct: string
  stockUnits: string
  strategyId: string
  makeLiquidationDue: boolean
}

const strategyOptions = [
  { id: '', label: 'Не менять' },
  { id: 'stockout_guard', label: 'Защита out of stock' },
  { id: 'turnover_control', label: 'Контроль оборачиваемости' },
  { id: 'plan_fact_daily', label: 'План-факт стандартный' },
  { id: 'plan_fact_period', label: 'План-факт на период' },
  { id: 'plan_fact_interval', label: 'План-факт интервальный' },
  { id: 'illiquid', label: 'Неликвид' },
  { id: 'optimal_price', label: 'Оптимальная цена' },
  { id: 'baskets_orders', label: 'Динамика корзин и заказов' },
  { id: 'metric_dynamics', label: 'Поддержание динамики показателя' },
  { id: 'schedule', label: 'Расписание — настройка в /wb/repricer', disabled: true },
  { id: 'plan_fact_group', label: 'План-факт группы — настройка в /wb/repricer', disabled: true },
  { id: 'cross_marketplace', label: 'Кроссмаркетплейс — выключено', disabled: true },
  { id: 'bundles', label: 'Комплекты — выключено', disabled: true },
]

function rubFromKopecks(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return ''
  return String(Math.round(value / 100))
}

function kopecksFromRub(value: string) {
  const text = value.trim()
  if (!text) return null
  const normalized = Number(text.replace(/\s/g, '').replace(',', '.'))
  return Number.isFinite(normalized) ? Math.round(normalized * 100) : null
}

function numberOrNull(value: string) {
  if (!value.trim()) return null
  const normalized = Number(value.replace(',', '.'))
  return Number.isFinite(normalized) ? normalized : null
}

function intOrNull(value: string) {
  const parsed = numberOrNull(value)
  return parsed == null ? null : Math.max(0, Math.round(parsed))
}

function formatRubKopecks(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return `${Math.round(value / 100).toLocaleString('ru-RU')} ₽`
}

function apiErrorText(caught: unknown, fallback: string) {
  if (!(caught instanceof ApiError)) return fallback
  const details = caught.details as { issues?: Array<{ loc?: Array<string | number>; msg?: string }> } | undefined
  const issue = details?.issues?.[0]
  if (issue?.msg) {
    const loc = Array.isArray(issue.loc) ? issue.loc.join('.') : ''
    return `${caught.message}: ${loc ? `${loc}: ` : ''}${issue.msg}`
  }
  return caught.message
}

function formatNumber(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '—'
  return Math.round(value).toLocaleString('ru-RU')
}

function formFromItem(item: SimulatorItem | null): FormState {
  return {
    sellerPriceRub: rubFromKopecks(item?.current.sellerPriceKopecks),
    buyerPriceRub: rubFromKopecks(item?.current.buyerPriceKopecks),
    sppPct: item?.current.sppPct == null ? '' : String(item.current.sppPct),
    baskets: item?.current.baskets == null ? '' : String(item.current.baskets),
    basketNorm: item?.current.basketNorm == null ? '' : String(item.current.basketNorm),
    ordersUnits: item?.current.ordersUnits == null ? '' : String(item.current.ordersUnits),
    salesUnits: item?.current.salesUnits == null ? '' : String(item.current.salesUnits),
    returnsUnits: item?.current.returnsUnits == null ? '' : String(item.current.returnsUnits),
    revenueRub: rubFromKopecks(item?.current.revenueKopecks),
    buyoutPct: item?.current.buyoutPct == null ? '' : String(item.current.buyoutPct),
    stockUnits: item?.current.stockUnits == null ? '' : String(item.current.stockUnits),
    strategyId: '',
    makeLiquidationDue: false,
  }
}

function patchPayloadFromForm(form: FormState) {
  const payload = {
    sellerPriceKopecks: kopecksFromRub(form.sellerPriceRub),
    buyerPriceKopecks: kopecksFromRub(form.buyerPriceRub),
    sppPct: numberOrNull(form.sppPct),
    baskets: intOrNull(form.baskets),
    basketNorm: intOrNull(form.basketNorm),
    ordersUnits: intOrNull(form.ordersUnits),
    salesUnits: intOrNull(form.salesUnits),
    returnsUnits: intOrNull(form.returnsUnits),
    revenueKopecks: kopecksFromRub(form.revenueRub),
    buyoutPct: numberOrNull(form.buyoutPct),
    stockUnits: intOrNull(form.stockUnits),
    strategyId: form.strategyId || null,
    makeLiquidationDue: form.makeLiquidationDue,
  }
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => value != null))
}

function statusLabel(status: string) {
  if (status === 'liquidation') return 'Ликвидация'
  if (status === 'auto') return 'Стратегия'
  return status
}

function resultClass(status: ExecuteItem['status']) {
  if (status === 'executed') return 'ok'
  if (status === 'blocked' || status === 'failed') return 'bad'
  return 'muted'
}

function reasonLabel(reason: string) {
  const normalized = reason.toLowerCase()
  if (normalized === 'wb-23') return 'Не хватает свежих price/SPP/stock данных для безопасной отправки цены'
  if (normalized.includes('discovery_not_ready')) return 'Готовность WB price apply/SPP ещё не подтверждена'
  if (normalized.includes('margin_preview_blocked')) return 'Не удалось посчитать маржу: источник маржи заблокирован'
  if (normalized.includes('source_stale_or_blocked_for_validation')) return 'Нельзя проверить цену: источник СПП/цены устарел или заблокирован'
  if (normalized.includes('source_stale') || normalized.includes('source_stale_or_blocked')) return 'Критичные источники цены устарели или заблокированы'
  if (normalized.includes('spp_missing')) return 'Нет СПП по SKU, поэтому нельзя проверить цену покупателя и безопасно отправить цену в WB'
  if (normalized.includes('cogs_missing')) return 'Не указана себестоимость'
  if (normalized.includes('commission_missing')) return 'Не указана комиссия WB'
  if (normalized.includes('logistics_missing')) return 'Не указана логистика'
  if (normalized.includes('buyout_missing')) return 'Нет процента выкупа'
  if (normalized.includes('stock_missing')) return 'Нет остатка WB'
  if (normalized.includes('stock_oos')) return 'Остаток WB равен нулю'
  if (normalized.includes('candidate_buyer_price_below_p_min') || normalized.includes('candidate_below_min') || normalized.includes('below_min')) return 'Цена до СПП ниже P_MIN'
  if (normalized.includes('candidate_buyer_price_above_p_max') || normalized.includes('candidate_above_max') || normalized.includes('above_max')) return 'Цена до СПП выше P_MAX'
  if (normalized.includes('pmin_pmax') || normalized.includes('p_min') || normalized.includes('min_price')) return 'Не прошла проверка P_MIN/P_MAX'
  if (normalized.includes('negative_margin')) return 'После изменения маржа станет отрицательной'
  if (normalized.includes('per_update_step')) return 'Сработал лимит шага за одно изменение'
  if (normalized.includes('per_day_step')) return 'Сработал дневной лимит изменения цены'
  if (normalized.includes('step')) return 'Сработал лимит шага изменения цены'
  if (normalized.includes('daily') || normalized.includes('cooldown')) return 'Сработал лимит частоты изменения цены'
  if (normalized.includes('margin')) return 'Сработала защита маржи'
  if (normalized.includes('night_median_collecting')) return 'Ночная медиана собирает корзины; цены ночью не меняются'
  if (normalized.includes('night')) return 'Ночной режим сейчас не активен'
  if (normalized.includes('liquidation_not_due')) return 'Следующий шаг ликвидации ещё не наступил'
  if (normalized.includes('no_price_change')) return 'Цена не изменилась'
  if (normalized.includes('manual_mode')) return 'SKU в ручном режиме'
  if (normalized.includes('automation_disabled')) return 'Автоматизация для SKU выключена'
  return reason
}

function sortedReasons(reasons: string[]) {
  return [...reasons].sort((left, right) => {
    const leftGeneric = left.toLowerCase() === 'wb-23' ? 1 : 0
    const rightGeneric = right.toLowerCase() === 'wb-23' ? 1 : 0
    return leftGeneric - rightGeneric || left.localeCompare(right)
  })
}

function formatGuardValue(code: string, value: string | number | boolean | null | undefined) {
  if (value == null) return '—'
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  if (typeof value === 'string') return value
  if (!Number.isFinite(value)) return '—'
  const normalized = code.toLowerCase()
  if (normalized.includes('price') || normalized.includes('margin')) {
    if (Math.abs(value) >= 100) return formatRubKopecks(value)
  }
  if (normalized.includes('step') || normalized.includes('pct')) return `${Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}%`
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: 2 })
}

function detailLine(detail: NonNullable<ExecuteItem['blockerDetails']>[number]) {
  const observed = formatGuardValue(detail.code, detail.observedValue)
  const threshold = formatGuardValue(detail.code, detail.threshold)
  if (observed !== '—' && threshold !== '—') return `${reasonLabel(detail.code)}: ${observed} / лимит ${threshold}`
  if (observed !== '—') return `${reasonLabel(detail.code)}: ${observed}`
  return reasonLabel(detail.code)
}

function primaryResultReason(item: ExecuteItem) {
  const blockers = item.blockedReasons ?? []
  const detailReasons = visibleBlockerDetails(item).map((detail) => reasonLabel(detail.code))
  if ((item.status === 'blocked' || item.status === 'failed') && blockers.length) {
    return Array.from(new Set([...detailReasons, ...sortedReasons(blockers).map(reasonLabel)])).join(' · ')
  }
  return item.skipReason ? reasonLabel(item.skipReason) : item.explanation || '—'
}

function strategyResultLabel(item: ExecuteItem) {
  const id = item.frontendStrategyId || item.strategyId || ''
  return strategyOptions.find((option) => option.id === id)?.label || id || 'стратегия не определена'
}

function secondaryResultReason(item: ExecuteItem) {
  const blockers = item.blockedReasons ?? []
  if ((item.status === 'blocked' || item.status === 'failed') && blockers.length && item.explanation) return item.explanation
  if (item.status === 'skipped' && item.explanation) return item.explanation
  if (item.applyState) return `apply: ${item.applyState}`
  return null
}

function visibleBlockerDetails(item: ExecuteItem) {
  const details = item.blockerDetails ?? []
  const seen = new Set<string>()
  return details.filter((detail) => {
    const key = `${detail.code}:${String(detail.observedValue)}:${String(detail.threshold)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

export function WbRepricerSimulatorPage() {
  const { accessToken } = useAuth()
  const [dashboard, setDashboard] = useState<SimulatorDashboard | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(() => formFromItem(null))
  const [lastReport, setLastReport] = useState<ExecuteReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const headers = useMemo(() => authorizationHeaders(accessToken ?? ''), [accessToken])
  const items = dashboard?.items ?? []
  const selected = items.find((item) => item.articleId === selectedId) ?? items[0] ?? null
  const realApplyEnabled = Boolean(dashboard?.mode.realPriceApplyEnabled)
  const simulatorRunApplyAllowed = dashboard?.mode.simulatorRunApplyAllowed ?? !realApplyEnabled

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const payload = await apiRequest<SimulatorDashboard>('/api/v1/wb-repricer/simulator?periodDays=30', { headers, cache: 'no-store' })
      if (!payload) throw new ApiError('Empty simulator response', 204)
      setDashboard(payload)
      const nextSelected = selectedId && payload.items.some((item) => item.articleId === selectedId)
        ? selectedId
        : payload.items[0]?.articleId ?? null
      setSelectedId(nextSelected)
      setForm(formFromItem(payload.items.find((item) => item.articleId === nextSelected) ?? payload.items[0] ?? null))
    } catch (caught) {
      setError(apiErrorText(caught, 'Не удалось загрузить симулятор.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function selectItem(item: SimulatorItem) {
    setSelectedId(item.articleId)
    setForm(formFromItem(item))
    setLastReport(null)
  }

  function updateForm(key: keyof FormState, value: string | boolean) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  async function saveSimulationInputs(item: SimulatorItem) {
    const response = await apiRequest<SimulatorSaveResponse>(
      `/api/v1/wb-repricer/simulator/sku/${encodeURIComponent(item.articleId)}?periodDays=30`,
      { method: 'PUT', headers, body: JSON.stringify(patchPayloadFromForm(form)) },
    )
    if (!response) throw new ApiError('Empty simulator save response', 204)
    setDashboard(response.dashboard)
    setSelectedId(response.item.articleId)
    setForm(formFromItem(response.item))
    return response
  }

  async function saveSimulation() {
    if (!selected) return
    setSaving(true)
    setError(null)
    try {
      await saveSimulationInputs(selected)
    } catch (caught) {
      setError(apiErrorText(caught, 'Не удалось сохранить входные данные.'))
    } finally {
      setSaving(false)
    }
  }

  async function runEngine(articleIds: string[], preview = false) {
    setRunning(true)
    setError(null)
    try {
      const selectedInputs = selected && articleIds.length === 1
        ? patchPayloadFromForm(form)
        : undefined
      if (preview) {
        const report = await apiRequest<ExecuteReport>('/api/v1/wb-repricer/strategies/preview', {
          method: 'POST',
          headers,
          body: JSON.stringify({ articleIds, scenario: 'complete', force: true, periodDays: 30, inputs: selectedInputs }),
        })
        if (!report) throw new ApiError('Empty preview response', 204)
        setLastReport(report)
      } else {
        const response = await apiRequest<{ report: ExecuteReport; dashboard: SimulatorDashboard }>('/api/v1/wb-repricer/simulator/run', {
          method: 'POST',
          headers,
          body: JSON.stringify({ articleIds, scenario: 'complete', applyPrices: simulatorRunApplyAllowed, force: true, periodDays: 30, inputs: selectedInputs }),
        })
        if (!response) throw new ApiError('Empty simulator run response', 204)
        setLastReport(response.report)
        setDashboard(response.dashboard)
        const refreshedSelected = selectedId
          ? response.dashboard.items.find((item) => item.articleId === selectedId)
          : null
        if (refreshedSelected && !selectedInputs) setForm(formFromItem(refreshedSelected))
      }
    } catch (caught) {
      setError(apiErrorText(caught, 'Engine не вернул результат.'))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="repricer-sim-page">
      <aside className="repricer-sim-rail">
        <div className="repricer-sim-brand">Satorna</div>
        <a href="/wb/repricer">Все товары</a>
        <a href="/wb/templates">Стратегии</a>
        <a href="/wb/repricer/changelog">История</a>
        <a href="/wb/repricer/simulator" className="active">Симулятор</a>
      </aside>

      <main className="repricer-sim-main">
        <header className="repricer-sim-topbar">
          <div>
            <h1>Симулятор WB-товаров</h1>
            <div className="repricer-sim-subtitle">Активные стратегии и ликвидации · тестовые входы WB · реальный repricer engine</div>
          </div>
          <div className="repricer-sim-actions">
            <button type="button" className="sim-btn secondary" onClick={() => void load()} disabled={loading}>
              <RefreshCw size={16} /> Обновить
            </button>
            <button type="button" className="sim-btn primary" onClick={() => void runEngine([], false)} disabled={running || !items.length}>
              <Play size={16} /> {realApplyEnabled ? 'Проверить все' : 'Запустить все'}
            </button>
          </div>
        </header>

        {error ? <div className="repricer-sim-alert"><AlertTriangle size={16} />{error}</div> : null}
        {dashboard?.mode.realPriceApplyEnabled ? (
          <div className="repricer-sim-mode-note">
            <AlertTriangle size={16} />
            <div>
              <b>Real apply включен</b>
              <span>Симулятор сохраняет входы WB, а запуск здесь работает как preview. Реальную отправку цены делает worker или запуск со страницы товаров.</span>
            </div>
          </div>
        ) : null}

        <section className="repricer-sim-kpis">
          <div><span>Активно</span><b>{dashboard?.summary.activeTotal ?? '—'}</b></div>
          <div><span>В стратегиях</span><b>{dashboard?.summary.strategyCount ?? '—'}</b></div>
          <div><span>В ликвидации</span><b>{dashboard?.summary.liquidationCount ?? '—'}</b></div>
          <div><span>Цикл worker</span><b>{dashboard ? `${dashboard.mode.executeIntervalMinutes} мин` : '—'}</b></div>
          <div><span>WB apply</span><b>{dashboard?.mode.realPriceApplyEnabled ? 'real' : 'off'}</b></div>
          <div><span>Симулятор</span><b>{dashboard ? (simulatorRunApplyAllowed ? 'apply' : 'preview') : '—'}</b></div>
        </section>

        <div className="repricer-sim-grid">
          <section className="repricer-sim-panel">
            <div className="repricer-sim-panel-head">
              <div><Activity size={17} /> Товары в работе</div>
              <span>{loading ? 'загрузка' : `${items.length} SKU`}</span>
            </div>
            <div className="repricer-sim-list">
              {items.map((item) => (
                <button
                  type="button"
                  key={item.articleId}
                  className={`repricer-sim-item ${selected?.articleId === item.articleId ? 'active' : ''}`}
                  onClick={() => selectItem(item)}
                >
                  <div>
                    <b>{item.articleId}</b>
                    <span>{item.name}</span>
                  </div>
                  <div className="repricer-sim-item-right">
                    <span className={item.status === 'liquidation' ? 'sim-pill warn' : 'sim-pill ok'}>
                      {item.status === 'liquidation' ? <Flame size={12} /> : <Zap size={12} />}
                      {statusLabel(item.status)}
                    </span>
                    <strong>{formatRubKopecks(item.current.sellerPriceKopecks)}</strong>
                  </div>
                </button>
              ))}
              {!loading && !items.length ? <div className="repricer-sim-empty">Нет SKU с явно назначенной стратегией или активной ликвидацией.</div> : null}
            </div>
          </section>

          <section className="repricer-sim-panel repricer-sim-editor">
            <div className="repricer-sim-panel-head">
              <div><SlidersHorizontal size={17} /> Входные WB-сигналы</div>
              {selected ? <span>{selected.strategy.name || '—'}</span> : null}
            </div>

            {selected ? (
              <>
                <div className="repricer-sim-current">
                  <div><span>Цена</span><b>{formatRubKopecks(selected.current.sellerPriceKopecks)}</b></div>
                  <div><span>P_MIN</span><b>{formatRubKopecks(selected.current.pMinKopecks)}</b></div>
                  <div><span>P_MAX</span><b>{formatRubKopecks(selected.current.pMaxKopecks)}</b></div>
                  <div><span>Корзины</span><b>{formatNumber(selected.current.baskets)}</b></div>
                  <div><span>Остаток</span><b>{formatNumber(selected.current.stockUnits)}</b></div>
                </div>

                <div className="repricer-sim-form">
                  <label>Цена селлера, ₽<input value={form.sellerPriceRub} onChange={(event) => updateForm('sellerPriceRub', event.target.value)} /></label>
                  <label>Цена покупателя, ₽<input value={form.buyerPriceRub} onChange={(event) => updateForm('buyerPriceRub', event.target.value)} /></label>
                  <label>СПП, %<input value={form.sppPct} onChange={(event) => updateForm('sppPct', event.target.value)} /></label>
                  <label>Корзины<input value={form.baskets} onChange={(event) => updateForm('baskets', event.target.value)} /></label>
                  <label>Норма корзин<input value={form.basketNorm} onChange={(event) => updateForm('basketNorm', event.target.value)} /></label>
                  <label>Заказы<input value={form.ordersUnits} onChange={(event) => updateForm('ordersUnits', event.target.value)} /></label>
                  <label>Продажи<input value={form.salesUnits} onChange={(event) => updateForm('salesUnits', event.target.value)} /></label>
                  <label>Возвраты<input value={form.returnsUnits} onChange={(event) => updateForm('returnsUnits', event.target.value)} /></label>
                  <label>Выручка, ₽<input value={form.revenueRub} onChange={(event) => updateForm('revenueRub', event.target.value)} /></label>
                  <label>Выкуп, %<input value={form.buyoutPct} onChange={(event) => updateForm('buyoutPct', event.target.value)} /></label>
                  <label>Остаток WB<input value={form.stockUnits} onChange={(event) => updateForm('stockUnits', event.target.value)} /></label>
                  <label>Стратегия<select value={form.strategyId} onChange={(event) => updateForm('strategyId', event.target.value)}>{strategyOptions.map((option) => <option key={option.id} value={option.id} disabled={option.disabled}>{option.label}</option>)}</select></label>
                </div>

                {selected.status === 'liquidation' ? (
                  <label className="repricer-sim-check">
                    <input type="checkbox" checked={form.makeLiquidationDue} onChange={(event) => updateForm('makeLiquidationDue', event.target.checked)} />
                    Сделать следующий шаг ликвидации доступным сейчас
                  </label>
                ) : null}

                <div className="repricer-sim-actions bottom">
                  <button type="button" className="sim-btn secondary" onClick={() => void runEngine([selected.articleId], true)} disabled={running}>
                    <CheckCircle2 size={16} /> Preview
                  </button>
                  <button type="button" className="sim-btn secondary" onClick={() => void saveSimulation()} disabled={saving}>
                    <Save size={16} /> Сохранить входы
                  </button>
                  <button type="button" className="sim-btn primary" onClick={() => void runEngine([selected.articleId], false)} disabled={running}>
                    <Play size={16} /> {running ? 'Запускаю' : (realApplyEnabled ? 'Проверить SKU' : 'Запустить SKU')}
                  </button>
                </div>
              </>
            ) : (
              <div className="repricer-sim-empty">Выберите SKU из списка.</div>
            )}
          </section>

          <section className="repricer-sim-panel">
            <div className="repricer-sim-panel-head">
              <div><Activity size={17} /> Последний запуск</div>
              {lastReport ? <span>{lastReport.runId.slice(0, 12)}</span> : null}
            </div>
            {lastReport ? (
              <div className="repricer-sim-report">
                <div className="repricer-sim-report-kpis">
                  <div><span>executed</span><b>{lastReport.executedCount}</b></div>
                  <div><span>skipped</span><b>{lastReport.skippedCount}</b></div>
                  <div><span>blocked</span><b>{lastReport.blockedCount}</b></div>
                </div>
                {lastReport.items.map((item) => (
                  <div className="repricer-sim-result" key={`${lastReport.runId}-${item.articleId}`}>
                    <div>
                      <b>{item.articleId}</b>
                      <span className="sim-result-strategy">{strategyResultLabel(item)}</span>
                      <span className={item.status === 'blocked' || item.status === 'failed' ? 'sim-result-primary bad' : 'sim-result-primary'}>
                        {primaryResultReason(item)}
                      </span>
                      {secondaryResultReason(item) ? <span className="sim-result-secondary">{secondaryResultReason(item)}</span> : null}
                      {visibleBlockerDetails(item).length ? (
                        <div className="sim-result-details">
                          {visibleBlockerDetails(item).map((detail) => (
                            <span key={`${detail.code}-${String(detail.observedValue)}-${String(detail.threshold)}`}>{detailLine(detail)}</span>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    <div>
                      <span className={`sim-pill ${resultClass(item.status)}`}>{item.status}</span>
                      <strong>{formatRubKopecks(item.oldPriceKopecks)} → {formatRubKopecks(item.recommendedPriceKopecks)}</strong>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="repricer-sim-empty">Запусков на этой странице ещё не было.</div>
            )}
          </section>

          <section className="repricer-sim-panel">
            <div className="repricer-sim-panel-head">
              <div><Activity size={17} /> Worker</div>
              <span>{dashboard?.mode.schedulerEnabled ? 'enabled' : 'disabled'}</span>
            </div>
            <div className="repricer-sim-worker">
              <div><span>Beat task</span><b>{dashboard?.worker.beatTask ?? '—'}</b></div>
              <div><span>Org task</span><b>{dashboard?.worker.orgTask ?? '—'}</b></div>
              <div><span>Queue</span><b>{dashboard?.worker.queue ?? '—'}</b></div>
              <div><span>Отбор SKU</span><b>{dashboard?.worker.selectionRule ?? '—'}</b></div>
              <div><span>Применение цены</span><b>{dashboard?.worker.priceApplyRule ?? '—'}</b></div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
