import { useEffect, useState } from 'react'
import { apiRequest } from '../../lib/api'

type WbWalletType = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10
type MarginCalcMode = 'from-discount' | 'from-forpay' | 'from-wallet'
type SppAccountingMode = 'spp_only' | 'spp_plus_wallet'
type BasketSignalMode = 'matrix' | 'thresholds'
type BasketNormMode = 'fallback_by_type' | 'auto_orders'
type PlanFactMetric = 'orders' | 'revenue' | 'margin'

interface AlgorithmSettings {
  targetMarginPct: number
  priceStepPct: number
  maxPriceChangeDailyPct: number
  syncIntervalHours: number
  syncIntervalMinutes: number
  fullSyncIntervalMinutes: number
  fullSyncPromotionsEnabled: boolean
  workerAutoApplyPricesEnabled: boolean
  sppAccountingMode: SppAccountingMode
  wbWalletType: WbWalletType
  marginCalcMode: MarginCalcMode
  storageCostPer60Days: number
  acquiringPct: number
  logisticsCoefficient: number
  localizationIndex: number
  nightMedianEnabled: boolean
  nightMedianMode: 'conservative' | 'aggressive'
  nightMedianGlobal: boolean
  nightMedianAutoEnableAllSkus: boolean
  nightMedianAutoApplyEnabled: boolean
  nightMedianCollectEnabled: boolean
  nightMedianWindowStartHour: number
  nightMedianWindowEndHour: number
  nightMedianApplyDeltaPct: number
  nightMedianTimezone: string
  minPriceSyncEnabled: boolean
  promoMarginThresholdPct: number
  priceJumpProtectionEnabled: boolean
  priceJumpStockValueMinPct: number
  priceJumpSppMinPct: number
  priceJumpStockQtyMinPct: number
  csvMaxCostDropPct: number
  csvMaxPriceDropPct: number
  discountStepEnabled: boolean
  discountStepPct: number
  priceRoundingEnabled: boolean
  basketSignalMode: BasketSignalMode
  cartHighBasketsThreshold: number
  cartLowBasketsThreshold: number
  cartComparisonDays: number
  warmupExitBaskets: number
  basketNormMode: BasketNormMode
  basketNormPeriodDays: number
  basketNormAutoMinOrders: number
  basketNormFallbackByGarment: {
    tshirt: number
    hoodie: number
    longsleeve: number
  }
  planFactMetric: PlanFactMetric
  planFactFactPeriodDays: number
  planFactIntervalHours: number
}

const PRICE_STEP_MAX_PCT = 50
const WORKER_INTERVAL_OPTIONS = [
  { value: 5, label: 'Каждые 5 минут' },
  { value: 15, label: 'Каждые 15 минут' },
  { value: 30, label: 'Каждые 30 минут' },
  { value: 60, label: 'Каждый час' },
  { value: 120, label: 'Каждые 2 часа' },
  { value: 240, label: 'Каждые 4 часа' },
  { value: 360, label: 'Каждые 6 часов' },
  { value: 720, label: 'Каждые 12 часов' },
]
const FULL_SYNC_INTERVAL_OPTIONS = [
  { value: 15, label: 'Каждые 15 минут' },
  { value: 30, label: 'Каждые 30 минут' },
  { value: 60, label: 'Каждый час' },
  { value: 120, label: 'Каждые 2 часа' },
  { value: 240, label: 'Каждые 4 часа' },
  { value: 360, label: 'Каждые 6 часов' },
  { value: 720, label: 'Каждые 12 часов' },
  { value: 1440, label: 'Раз в сутки' },
]

const DEFAULT_ALGORITHM_SETTINGS: AlgorithmSettings = {
  targetMarginPct: 25,
  priceStepPct: 6,
  maxPriceChangeDailyPct: 20,
  syncIntervalHours: 1,
  syncIntervalMinutes: 60,
  fullSyncIntervalMinutes: 60,
  fullSyncPromotionsEnabled: true,
  workerAutoApplyPricesEnabled: false,
  sppAccountingMode: 'spp_only',
  wbWalletType: 4,
  marginCalcMode: 'from-discount',
  storageCostPer60Days: 21,
  acquiringPct: 3.31,
  logisticsCoefficient: 1.0,
  localizationIndex: 1.0,
  nightMedianEnabled: true,
  nightMedianMode: 'conservative',
  nightMedianGlobal: true,
  nightMedianAutoEnableAllSkus: true,
  nightMedianAutoApplyEnabled: false,
  nightMedianCollectEnabled: true,
  nightMedianWindowStartHour: 23,
  nightMedianWindowEndHour: 6,
  nightMedianApplyDeltaPct: 8,
  nightMedianTimezone: 'МСК (UTC+3)',
  minPriceSyncEnabled: true,
  promoMarginThresholdPct: 10,
  priceJumpProtectionEnabled: true,
  priceJumpStockValueMinPct: -20,
  priceJumpSppMinPct: -40,
  priceJumpStockQtyMinPct: -15,
  csvMaxCostDropPct: 20,
  csvMaxPriceDropPct: 20,
  discountStepEnabled: false,
  discountStepPct: 1,
  priceRoundingEnabled: false,
  basketSignalMode: 'matrix',
  cartHighBasketsThreshold: 30,
  cartLowBasketsThreshold: 5,
  cartComparisonDays: 7,
  warmupExitBaskets: 40,
  basketNormMode: 'fallback_by_type',
  basketNormPeriodDays: 7,
  basketNormAutoMinOrders: 1,
  basketNormFallbackByGarment: {
    tshirt: 20,
    hoodie: 15,
    longsleeve: 10,
  },
  planFactMetric: 'orders',
  planFactFactPeriodDays: 7,
  planFactIntervalHours: 4,
}

function toBoolean(raw: unknown, fallback: boolean): boolean {
  return typeof raw === 'boolean' ? raw : fallback
}

function toNumber(raw: unknown, fallback: number): number {
  const value = Number(raw)
  return Number.isFinite(value) ? value : fallback
}

function clampNumber(raw: unknown, fallback: number, min: number, max: number): number {
  const value = toNumber(raw, fallback)
  return Math.max(min, Math.min(max, value))
}

function toInt(raw: unknown, fallback: number): number {
  const value = Number(raw)
  if (!Number.isFinite(value)) return fallback
  return Math.trunc(value)
}

function toWalletType(raw: unknown): WbWalletType {
  const value = toInt(raw, DEFAULT_ALGORITHM_SETTINGS.wbWalletType)
  if ([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].includes(value)) {
    return value as WbWalletType
  }
  return DEFAULT_ALGORITHM_SETTINGS.wbWalletType
}

function toSppAccountingMode(raw: unknown): SppAccountingMode {
  return raw === 'spp_plus_wallet' ? 'spp_plus_wallet' : 'spp_only'
}

function toMarginMode(raw: unknown): MarginCalcMode {
  if (raw === 'from-forpay' || raw === 'from-wallet') return raw
  return 'from-discount'
}

function toNightMedianMode(raw: unknown): 'conservative' | 'aggressive' {
  return raw === 'aggressive' ? 'aggressive' : 'conservative'
}

function toBasketSignalMode(raw: unknown): BasketSignalMode {
  return raw === 'thresholds' ? 'thresholds' : 'matrix'
}

function toBasketNormMode(raw: unknown): BasketNormMode {
  return raw === 'auto' || raw === 'auto_orders' || raw === 'auto_orders_avg' ? 'auto_orders' : 'fallback_by_type'
}

function toPlanFactMetric(raw: unknown): PlanFactMetric {
  if (raw === 'revenue' || raw === 'margin') return raw
  return 'orders'
}

function toGarmentNorms(raw: unknown): AlgorithmSettings['basketNormFallbackByGarment'] {
  const value = typeof raw === 'object' && raw !== null ? raw as Record<string, unknown> : {}
  return {
    tshirt: toInt(value.tshirt, DEFAULT_ALGORITHM_SETTINGS.basketNormFallbackByGarment.tshirt),
    hoodie: toInt(value.hoodie, DEFAULT_ALGORITHM_SETTINGS.basketNormFallbackByGarment.hoodie),
    longsleeve: toInt(value.longsleeve, DEFAULT_ALGORITHM_SETTINGS.basketNormFallbackByGarment.longsleeve),
  }
}

function normalizeAlgorithmSettings(raw: unknown): AlgorithmSettings {
  const payload = (typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : null) ?? {}
  const legacySyncIntervalHours = toInt(payload.syncIntervalHours, DEFAULT_ALGORITHM_SETTINGS.syncIntervalHours)
  const syncIntervalMinutes = Math.max(
    5,
    toInt(payload.syncIntervalMinutes, legacySyncIntervalHours * 60),
  )
  const autoEnableAllSkus = toBoolean(
    payload.nightMedianAutoEnableAllSkus ?? payload.nightMedianGlobal,
    DEFAULT_ALGORITHM_SETTINGS.nightMedianAutoEnableAllSkus,
  )
  return {
    targetMarginPct: clampNumber(payload.targetMarginPct, DEFAULT_ALGORITHM_SETTINGS.targetMarginPct, 0, 90),
    priceStepPct: clampNumber(payload.priceStepPct, DEFAULT_ALGORITHM_SETTINGS.priceStepPct, 0, PRICE_STEP_MAX_PCT),
    maxPriceChangeDailyPct: toNumber(
      payload.maxPriceChangeDailyPct,
      DEFAULT_ALGORITHM_SETTINGS.maxPriceChangeDailyPct,
    ),
    syncIntervalHours: Math.max(1, Math.round(syncIntervalMinutes / 60)),
    syncIntervalMinutes,
    fullSyncIntervalMinutes: Math.max(
      15,
      toInt(payload.fullSyncIntervalMinutes, DEFAULT_ALGORITHM_SETTINGS.fullSyncIntervalMinutes),
    ),
    fullSyncPromotionsEnabled: toBoolean(
      payload.fullSyncPromotionsEnabled,
      DEFAULT_ALGORITHM_SETTINGS.fullSyncPromotionsEnabled,
    ),
    workerAutoApplyPricesEnabled: toBoolean(
      payload.workerAutoApplyPricesEnabled,
      DEFAULT_ALGORITHM_SETTINGS.workerAutoApplyPricesEnabled,
    ),
    sppAccountingMode: toSppAccountingMode(payload.sppAccountingMode),
    wbWalletType: toWalletType(payload.wbWalletType),
    marginCalcMode: toMarginMode(payload.marginCalcMode),
    storageCostPer60Days: toNumber(
      payload.storageCostPer60Days,
      DEFAULT_ALGORITHM_SETTINGS.storageCostPer60Days,
    ),
    acquiringPct: toNumber(payload.acquiringPct, DEFAULT_ALGORITHM_SETTINGS.acquiringPct),
    logisticsCoefficient: toNumber(payload.logisticsCoefficient, DEFAULT_ALGORITHM_SETTINGS.logisticsCoefficient),
    localizationIndex: toNumber(payload.localizationIndex, DEFAULT_ALGORITHM_SETTINGS.localizationIndex),
    nightMedianEnabled: toBoolean(payload.nightMedianEnabled, DEFAULT_ALGORITHM_SETTINGS.nightMedianEnabled),
    nightMedianMode: toNightMedianMode(payload.nightMedianMode),
    nightMedianGlobal: autoEnableAllSkus,
    nightMedianAutoEnableAllSkus: autoEnableAllSkus,
    nightMedianAutoApplyEnabled: toBoolean(payload.nightMedianAutoApplyEnabled, DEFAULT_ALGORITHM_SETTINGS.nightMedianAutoApplyEnabled),
    nightMedianCollectEnabled: toBoolean(payload.nightMedianCollectEnabled, DEFAULT_ALGORITHM_SETTINGS.nightMedianCollectEnabled),
    nightMedianWindowStartHour: clampNumber(payload.nightMedianWindowStartHour, DEFAULT_ALGORITHM_SETTINGS.nightMedianWindowStartHour, 0, 23),
    nightMedianWindowEndHour: clampNumber(payload.nightMedianWindowEndHour, DEFAULT_ALGORITHM_SETTINGS.nightMedianWindowEndHour, 0, 23),
    nightMedianApplyDeltaPct: clampNumber(payload.nightMedianApplyDeltaPct, DEFAULT_ALGORITHM_SETTINGS.nightMedianApplyDeltaPct, 0, 20),
    nightMedianTimezone: typeof payload.nightMedianTimezone === 'string' && payload.nightMedianTimezone.trim()
      ? payload.nightMedianTimezone
      : DEFAULT_ALGORITHM_SETTINGS.nightMedianTimezone,
    minPriceSyncEnabled: toBoolean(payload.minPriceSyncEnabled, DEFAULT_ALGORITHM_SETTINGS.minPriceSyncEnabled),
    promoMarginThresholdPct: toNumber(
      payload.promoMarginThresholdPct,
      DEFAULT_ALGORITHM_SETTINGS.promoMarginThresholdPct,
    ),
    priceJumpProtectionEnabled: toBoolean(
      payload.priceJumpProtectionEnabled,
      DEFAULT_ALGORITHM_SETTINGS.priceJumpProtectionEnabled,
    ),
    priceJumpStockValueMinPct: toNumber(
      payload.priceJumpStockValueMinPct,
      DEFAULT_ALGORITHM_SETTINGS.priceJumpStockValueMinPct,
    ),
    priceJumpSppMinPct: toNumber(payload.priceJumpSppMinPct, DEFAULT_ALGORITHM_SETTINGS.priceJumpSppMinPct),
    priceJumpStockQtyMinPct: toNumber(
      payload.priceJumpStockQtyMinPct,
      DEFAULT_ALGORITHM_SETTINGS.priceJumpStockQtyMinPct,
    ),
    csvMaxCostDropPct: toNumber(payload.csvMaxCostDropPct, DEFAULT_ALGORITHM_SETTINGS.csvMaxCostDropPct),
    csvMaxPriceDropPct: toNumber(payload.csvMaxPriceDropPct, DEFAULT_ALGORITHM_SETTINGS.csvMaxPriceDropPct),
    discountStepEnabled: toBoolean(payload.discountStepEnabled, DEFAULT_ALGORITHM_SETTINGS.discountStepEnabled),
    discountStepPct: toNumber(payload.discountStepPct, DEFAULT_ALGORITHM_SETTINGS.discountStepPct),
    priceRoundingEnabled: toBoolean(payload.priceRoundingEnabled, DEFAULT_ALGORITHM_SETTINGS.priceRoundingEnabled),
    basketSignalMode: toBasketSignalMode(payload.basketSignalMode),
    cartHighBasketsThreshold: toInt(payload.cartHighBasketsThreshold, DEFAULT_ALGORITHM_SETTINGS.cartHighBasketsThreshold),
    cartLowBasketsThreshold: toInt(payload.cartLowBasketsThreshold, DEFAULT_ALGORITHM_SETTINGS.cartLowBasketsThreshold),
    cartComparisonDays: toInt(payload.cartComparisonDays, DEFAULT_ALGORITHM_SETTINGS.cartComparisonDays),
    warmupExitBaskets: toInt(payload.warmupExitBaskets, DEFAULT_ALGORITHM_SETTINGS.warmupExitBaskets),
    basketNormMode: toBasketNormMode(payload.basketNormMode),
    basketNormPeriodDays: toInt(payload.basketNormPeriodDays, DEFAULT_ALGORITHM_SETTINGS.basketNormPeriodDays),
    basketNormAutoMinOrders: toInt(payload.basketNormAutoMinOrders, DEFAULT_ALGORITHM_SETTINGS.basketNormAutoMinOrders),
    basketNormFallbackByGarment: toGarmentNorms(payload.basketNormFallbackByGarment),
    planFactMetric: toPlanFactMetric(payload.planFactMetric),
    planFactFactPeriodDays: toInt(payload.planFactFactPeriodDays, DEFAULT_ALGORITHM_SETTINGS.planFactFactPeriodDays),
    planFactIntervalHours: toInt(payload.planFactIntervalHours, DEFAULT_ALGORITHM_SETTINGS.planFactIntervalHours),
  }
}

function Section({
  title,
  hint,
  children,
}: {
  title: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="bg-card rounded-lg border border-border mb-4">
      <div className="px-5 py-3 border-b border-border/60">
        <div className="font-semibold text-sm text-foreground">{title}</div>
        {hint && <div className="text-xs text-muted-foreground/70 mt-0.5">{hint}</div>}
      </div>
      <div className="px-5 py-4 space-y-4">{children}</div>
    </div>
  )
}

function FieldRow({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-4">
      <div className="flex-1">
        <div className="text-sm font-medium text-foreground">{label}</div>
        {hint && <div className="text-xs text-muted-foreground/70 mt-0.5">{hint}</div>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  )
}

function Toggle({
  value,
  onChange,
  disabled = false,
}: {
  value: boolean
  onChange: (v: boolean) => void
  disabled?: boolean
}) {
  return (
    <label className="inline-flex cursor-pointer">
      <span className="relative inline-block w-10 h-5">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={value}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        <span
          className={`absolute inset-0 rounded-full transition-colors ${
            value ? 'bg-emerald-500' : 'bg-muted'
          }`}
        />
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 bg-card rounded-full shadow transition-transform ${
            value ? 'translate-x-5' : ''
          }`}
        />
      </span>
    </label>
  )
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step,
  suffix,
  warning,
  error,
  disabled = false,
}: {
  value: number
  onChange: (v: number) => void
  min?: number
  max?: number
  step?: number
  suffix?: string
  warning?: string
  error?: string
  disabled?: boolean
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step ?? 1}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          className={`w-24 border rounded px-2 py-1.5 text-sm font-mono text-right focus:outline-none ${
            error
              ? 'border-red-400 focus:border-red-500'
              : warning
                ? 'border-amber-400 focus:border-amber-500'
                : 'border-border focus:border-primary'
          }`}
        />
        {suffix && <span className="text-sm text-muted-foreground">{suffix}</span>}
      </div>
      {error && <div className="text-xs text-red-600 mt-1">{error}</div>}
      {warning && !error && <div className="text-xs text-amber-600 mt-1">{warning}</div>}
    </div>
  )
}

export function AlgorithmSettingsPage() {
  const [settings, setSettings] = useState<AlgorithmSettings>(DEFAULT_ALGORITHM_SETTINGS)
  const [original, setOriginal] = useState<AlgorithmSettings | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [confirmModal, setConfirmModal] = useState(false)
  const [fetchLoading, setFetchLoading] = useState(false)
  const [fetchError, setFetchError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    setFetchLoading(true)
    setFetchError(false)

    apiRequest('/api/v1/wb-repricer/algorithm', { signal: controller.signal })
      .then((data) => {
        if (controller.signal.aborted) return
        const normalized = normalizeAlgorithmSettings(data)
        setSettings(normalized)
        setOriginal(normalized)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setFetchError(true)
        console.error('Failed to load algorithm settings', err)
      })
      .finally(() => {
        if (!controller.signal.aborted) setFetchLoading(false)
      })

    return () => controller.abort()
  }, [])

  let priceStepError: string | undefined
  let priceStepWarning: string | undefined
  if (settings.priceStepPct >= 40) priceStepWarning = 'Осторожно: очень резкий шаг цены'
  else if (settings.priceStepPct >= 20) priceStepWarning = 'Высокий шаг лучше сначала проверить в симуляторе'

  const isDirty = original && JSON.stringify(settings) !== JSON.stringify(original)
  const disabled = fetchLoading || saving

  async function handleSave() {
    setConfirmModal(false)
    setSaving(true)
    setSaveError(null)

    try {
      const data = await apiRequest('/api/v1/wb-repricer/algorithm', {
        method: 'PUT',
        body: JSON.stringify(settings),
      })
      const normalized = normalizeAlgorithmSettings(data)
      setSettings(normalized)
      setOriginal(normalized)
      setSaved(true)
      setTimeout(() => setSaved(false), 4000)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Unable to save algorithm settings')
    } finally {
      setSaving(false)
    }
  }

  function update<K extends keyof AlgorithmSettings>(key: K, value: AlgorithmSettings[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  function updateWorkerInterval(minutes: number) {
    setSettings((prev) => ({
      ...prev,
      syncIntervalMinutes: minutes,
      syncIntervalHours: Math.max(1, Math.round(minutes / 60)),
    }))
    setSaved(false)
  }

  function updateNightMedianAutoEnableAllSkus(value: boolean) {
    setSettings((prev) => ({
      ...prev,
      nightMedianAutoEnableAllSkus: value,
      nightMedianGlobal: value,
    }))
    setSaved(false)
  }

  if (fetchLoading) {
    return (
      <div className="p-6 space-y-4 max-w-2xl animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-16 rounded-lg bg-muted" />
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="p-8 flex flex-col items-center gap-3 text-center">
        <div className="text-sm font-medium text-red-600 dark:text-red-400">
          Не удалось загрузить настройки алгоритма
        </div>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="text-xs text-primary hover:underline"
        >
          Обновить страницу
        </button>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Настройки алгоритма репрайсера</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Базовые параметры цикла, защита от скачков цен и режим ночного повышения
        </p>
      </div>

      {confirmModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg shadow-lg max-w-sm w-full">
            <div className="px-5 py-4 border-b border-border font-semibold text-foreground">
              Применить изменения?
            </div>
            <div className="px-5 py-3 text-sm text-muted-foreground">
              Изменённые настройки повлияют на все активные артикулы после следующего цикла синхронизации.
            </div>
            <div className="px-5 py-3 border-t border-border flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmModal(false)}
                className="px-4 py-2 border border-border text-foreground rounded text-sm hover:bg-muted/40"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={handleSave}
                className="px-4 py-2 bg-primary text-white rounded text-sm hover:bg-primary/90 font-medium"
                disabled={saving}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      <Section title="Базовые параметры" hint="Основные настройки цикла репрайсера">
        <FieldRow
          label="Целевая маржа"
          hint="Используется в расчетах P_min для SKU без ручного P_min."
        >
          <NumberInput
            value={settings.targetMarginPct}
            onChange={(v) => update('targetMarginPct', v)}
            min={0}
            max={90}
            suffix="%"
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow
          label="Макс. % изменения за один цикл"
          hint="Ограничение одного изменения цены в одном запуске."
        >
          <NumberInput
            value={settings.priceStepPct}
            onChange={(v) => update('priceStepPct', v)}
            min={1}
            max={PRICE_STEP_MAX_PCT}
            suffix="%"
            warning={priceStepWarning}
            error={priceStepError}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow
          label="Макс. % изменения цены в день"
          hint="Суммарный лимит изменения цены в сутки."
        >
          <NumberInput
            value={settings.maxPriceChangeDailyPct}
            onChange={(v) => update('maxPriceChangeDailyPct', v)}
            min={settings.priceStepPct}
            max={50}
            suffix="%"
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Время шага по умолчанию" hint="Как часто воркер может запускать новый шаг стратегии">
          <select
            value={settings.syncIntervalMinutes}
            onChange={(e) => updateWorkerInterval(Number(e.target.value))}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            {WORKER_INTERVAL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow label="Полный синк WB" hint="Как часто фоновый синк обновляет товары, остатки, заказы, корзины и финансы">
          <select
            value={settings.fullSyncIntervalMinutes}
            onChange={(e) => update('fullSyncIntervalMinutes', Number(e.target.value))}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            {FULL_SYNC_INTERVAL_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </FieldRow>

        <FieldRow
          label="Синхронизировать акции WB"
          hint="Если выключено, полный WB sync пропускает источник акций и не ждёт календарь промо."
        >
          <Toggle
            value={settings.fullSyncPromotionsEnabled}
            onChange={(v) => update('fullSyncPromotionsEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow
          label="Автоматически отправлять цены в WB"
          hint="Если выключено, worker создает заявку и показывает попап подтверждения перед отправкой цены."
        >
          <Toggle
            value={settings.workerAutoApplyPricesEnabled}
            onChange={(v) => update('workerAutoApplyPricesEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Округление цены" hint="Округлять кандидата до красивых цен перед guard-проверкой.">
          <Toggle
            value={settings.priceRoundingEnabled}
            onChange={(v) => update('priceRoundingEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow
          label="Учет СПП и WB кошелька"
          hint="Какая покупательская цена используется в стратегиях и P_min."
        >
          <select
            value={settings.sppAccountingMode}
            onChange={(e) => update('sppAccountingMode', e.target.value as SppAccountingMode)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value="spp_only">Учитывать СПП</option>
            <option value="spp_plus_wallet">Учитывать СПП и WB кошелек</option>
          </select>
        </FieldRow>

        <FieldRow label="Тип учитываемого WB кошелька" hint="Используется только в режиме СПП + WB кошелек">
          <select
            value={settings.wbWalletType}
            onChange={(e) => update('wbWalletType', Number(e.target.value) as WbWalletType)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value={0}>Не учитывать</option>
            <option value={1}>Кошелёк 1%</option>
            <option value={2}>Кошелёк 2%</option>
            <option value={3}>Кошелёк 3%</option>
            <option value={4}>Кошелёк 4%</option>
            <option value={5}>Кошелёк 5%</option>
            <option value={6}>Кошелёк 6%</option>
            <option value={7}>Кошелёк 7%</option>
            <option value={8}>Кошелёк 8%</option>
            <option value={9}>Кошелёк 9%</option>
            <option value={10}>Кошелёк 10%</option>
          </select>
        </FieldRow>

        <FieldRow
          label="Режим расчёта маржинальности"
          hint="Способ расчёта базы маржи для отчётности"
        >
          <select
            value={settings.marginCalcMode}
            onChange={(e) => update('marginCalcMode', e.target.value as MarginCalcMode)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value="from-discount">От цены со скидкой</option>
            <option value="from-forpay">По ForPay</option>
            <option value="from-wallet">По цене с кошельком</option>
          </select>
        </FieldRow>
      </Section>

      <Section title="План-факт и норма" hint="Как считать норму спроса и факт для план-факт стратегий">
        <FieldRow label="Источник нормы спроса">
          <select
            value={settings.basketNormMode}
            onChange={(e) => update('basketNormMode', e.target.value as BasketNormMode)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value="fallback_by_type">План по типу товара</option>
            <option value="auto_orders">Авто по WB orders</option>
          </select>
        </FieldRow>

        <FieldRow label="Период нормы">
          <NumberInput value={settings.basketNormPeriodDays} onChange={(v) => update('basketNormPeriodDays', Math.round(v))} min={1} max={90} suffix="дней" disabled={disabled} />
        </FieldRow>

        <FieldRow label="Минимум авто-нормы">
          <NumberInput value={settings.basketNormAutoMinOrders} onChange={(v) => update('basketNormAutoMinOrders', Math.round(v))} min={0} max={1000} suffix="заказов" disabled={disabled} />
        </FieldRow>

        <FieldRow label="План по типам товара">
          <div className="grid grid-cols-3 gap-3">
            <NumberInput value={settings.basketNormFallbackByGarment.tshirt} onChange={(v) => update('basketNormFallbackByGarment', { ...settings.basketNormFallbackByGarment, tshirt: Math.round(v) })} min={1} max={1000} suffix="футболка" disabled={disabled} />
            <NumberInput value={settings.basketNormFallbackByGarment.hoodie} onChange={(v) => update('basketNormFallbackByGarment', { ...settings.basketNormFallbackByGarment, hoodie: Math.round(v) })} min={1} max={1000} suffix="худи" disabled={disabled} />
            <NumberInput value={settings.basketNormFallbackByGarment.longsleeve} onChange={(v) => update('basketNormFallbackByGarment', { ...settings.basketNormFallbackByGarment, longsleeve: Math.round(v) })} min={1} max={1000} suffix="лонгслив" disabled={disabled} />
          </div>
        </FieldRow>

        <FieldRow label="Метрика план-факта на период">
          <select
            value={settings.planFactMetric}
            onChange={(e) => update('planFactMetric', e.target.value as PlanFactMetric)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value="orders">Заказы</option>
            <option value="revenue">Выручка</option>
            <option value="margin">Маржа</option>
          </select>
        </FieldRow>

        <FieldRow label="Период факта по умолчанию">
          <NumberInput value={settings.planFactFactPeriodDays} onChange={(v) => update('planFactFactPeriodDays', Math.round(v))} min={1} max={90} suffix="дней" disabled={disabled} />
        </FieldRow>

        <FieldRow label="Интервал план-факта">
          <NumberInput value={settings.planFactIntervalHours} onChange={(v) => update('planFactIntervalHours', Math.round(v))} min={1} max={24} suffix="часов" disabled={disabled} />
        </FieldRow>
      </Section>

      <Section title="Сигнал корзин" hint="Как стратегия baskets_orders принимает решение">
        <FieldRow label="Режим работы">
          <select
            value={settings.basketSignalMode}
            onChange={(e) => update('basketSignalMode', e.target.value as BasketSignalMode)}
            disabled={disabled}
            className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
          >
            <option value="matrix">Матрица корзины + заказы</option>
            <option value="thresholds">Пороги корзин</option>
          </select>
        </FieldRow>

        <FieldRow label="Повысить цену если корзин за период ≥">
          <NumberInput value={settings.cartHighBasketsThreshold} onChange={(v) => update('cartHighBasketsThreshold', Math.round(v))} min={0} max={100000} suffix="шт" disabled={disabled} />
        </FieldRow>

        <FieldRow label="Снизить цену если корзин за период ≤">
          <NumberInput value={settings.cartLowBasketsThreshold} onChange={(v) => update('cartLowBasketsThreshold', Math.round(v))} min={0} max={100000} suffix="шт" disabled={disabled} />
        </FieldRow>

        <FieldRow label="База сравнения">
          <NumberInput value={settings.cartComparisonDays} onChange={(v) => update('cartComparisonDays', Math.round(v))} min={1} max={90} suffix="дней" disabled={disabled} />
        </FieldRow>

        <FieldRow label="Минимум корзин для запуска новинки">
          <NumberInput value={settings.warmupExitBaskets} onChange={(v) => update('warmupExitBaskets', Math.round(v))} min={0} max={100000} suffix="шт" disabled={disabled} />
        </FieldRow>
      </Section>

      <Section title="Формула P_min">
        <FieldRow label="Хранение WB" hint="Расходы на хранение за 60 дней, ₽">
          <NumberInput
            value={settings.storageCostPer60Days}
            onChange={(v) => update('storageCostPer60Days', v)}
            min={0}
            max={500}
            step={0.5}
            suffix="₽ / 60 дн."
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Эквайринг" hint="Комиссия платёжной системы">
          <NumberInput
            value={settings.acquiringPct}
            onChange={(v) => update('acquiringPct', v)}
            min={0}
            max={10}
            step={0.01}
            suffix="%"
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Коэффициент склада">
          <NumberInput
            value={settings.logisticsCoefficient}
            onChange={(v) => update('logisticsCoefficient', v)}
            min={0.5}
            max={3}
            step={0.1}
            suffix="×"
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Индекс локализации">
          <NumberInput
            value={settings.localizationIndex}
            onChange={(v) => update('localizationIndex', v)}
            min={0.5}
            max={1}
            step={0.05}
            suffix="×"
            disabled={disabled}
          />
        </FieldRow>
      </Section>

      <Section title="Защита при загрузке CSV">
        <FieldRow
          label="Макс. снижение себестоимости"
          hint="Если загрузка ниже порога — отклоняем изменение"
        >
          <NumberInput
            value={settings.csvMaxCostDropPct}
            onChange={(v) => update('csvMaxCostDropPct', v)}
            min={5}
            max={100}
            suffix="%"
            warning={settings.csvMaxCostDropPct > 25 ? 'Высокий порог безопасности' : undefined}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Макс. снижение min price" hint="Пороги по себестоимости цены">
          <NumberInput
            value={settings.csvMaxPriceDropPct}
            onChange={(v) => update('csvMaxPriceDropPct', v)}
            min={5}
            max={100}
            suffix="%"
            warning={settings.csvMaxPriceDropPct > 25 ? 'Высокий порог безопасности' : undefined}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Шаг изменения скидки">
          <Toggle
            value={settings.discountStepEnabled}
            onChange={(v) => update('discountStepEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        {settings.discountStepEnabled && (
          <FieldRow label="Размер шага скидки">
            <NumberInput
              value={settings.discountStepPct}
              onChange={(v) => update('discountStepPct', v)}
              min={1}
              max={10}
              suffix="п.п."
              disabled={disabled}
            />
          </FieldRow>
        )}
      </Section>

      <Section title="Защита от скачков цен">
        <FieldRow label="Включена" hint="Отключение может привести к неустойчивым ценовым колебаниям">
          <Toggle
            value={settings.priceJumpProtectionEnabled}
            onChange={(v) => update('priceJumpProtectionEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        {settings.priceJumpProtectionEnabled && (
          <>
            <FieldRow label="Порог падения стоимости стока, %">
              <NumberInput
                value={settings.priceJumpStockValueMinPct}
                onChange={(v) => update('priceJumpStockValueMinPct', v)}
                min={-100}
                max={0}
                suffix="%"
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Порог падения СПП, %">
              <NumberInput
                value={settings.priceJumpSppMinPct}
                onChange={(v) => update('priceJumpSppMinPct', v)}
                min={-100}
                max={0}
                suffix="%"
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Порог падения остатков, %">
              <NumberInput
                value={settings.priceJumpStockQtyMinPct}
                onChange={(v) => update('priceJumpStockQtyMinPct', v)}
                min={-100}
                max={0}
                suffix="%"
                disabled={disabled}
              />
            </FieldRow>
          </>
        )}
      </Section>

      <Section title="Ночная медиана (23:00–04:00 МСК)">
        <FieldRow label="Включена">
          <Toggle
            value={settings.nightMedianEnabled}
            onChange={(v) => update('nightMedianEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        {settings.nightMedianEnabled && (
          <>
            <FieldRow label="Режим">
              <div className="flex gap-3">
                {(['conservative', 'aggressive'] as const).map((mode) => (
                  <label key={mode} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="nightMedianMode"
                      value={mode}
                      checked={settings.nightMedianMode === mode}
                      disabled={disabled}
                      onChange={() => update('nightMedianMode', mode)}
                      className="text-primary"
                    />
                    <span className="text-sm text-foreground">
                      {mode === 'conservative' ? 'Консервативный' : 'Агрессивный'}
                    </span>
                  </label>
                ))}
              </div>
            </FieldRow>

            <FieldRow
              label="Автоматически включать у всех товаров"
              hint="Если включено, ночная медиана применяется ко всем товарам с активной стратегией, даже если у SKU она не включалась отдельно."
            >
              <Toggle
                value={settings.nightMedianAutoEnableAllSkus}
                onChange={updateNightMedianAutoEnableAllSkus}
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Авто применение цен" hint="Если выключено, worker покажет попап подтверждения перед отправкой в WB.">
              <Toggle
                value={settings.nightMedianAutoApplyEnabled}
                onChange={(v) => update('nightMedianAutoApplyEnabled', v)}
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Собирать данные ночью" hint="Накопление медианы в ночном окне.">
              <Toggle
                value={settings.nightMedianCollectEnabled}
                onChange={(v) => update('nightMedianCollectEnabled', v)}
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Ночное окно">
              <div className="flex items-center gap-2">
                <NumberInput
                  value={settings.nightMedianWindowStartHour}
                  onChange={(v) => update('nightMedianWindowStartHour', Math.round(v))}
                  min={0}
                  max={23}
                  suffix="с"
                  disabled={disabled}
                />
                <NumberInput
                  value={settings.nightMedianWindowEndHour}
                  onChange={(v) => update('nightMedianWindowEndHour', Math.round(v))}
                  min={0}
                  max={23}
                  suffix="до"
                  disabled={disabled}
                />
              </div>
            </FieldRow>

            <FieldRow label="Дельта применения медианы">
              <NumberInput
                value={settings.nightMedianApplyDeltaPct}
                onChange={(v) => update('nightMedianApplyDeltaPct', v)}
                min={0}
                max={20}
                suffix="%"
                disabled={disabled}
              />
            </FieldRow>

            <FieldRow label="Часовой пояс">
              <select
                value={settings.nightMedianTimezone}
                onChange={(e) => update('nightMedianTimezone', e.target.value)}
                disabled={disabled}
                className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none"
              >
                <option value="МСК (UTC+3)">МСК (UTC+3)</option>
                <option value="Asia/Yekaterinburg">Екатеринбург (UTC+5)</option>
                <option value="UTC">UTC</option>
              </select>
            </FieldRow>
          </>
        )}
      </Section>

      <Section title="Защита от акций" hint="Синхронизация min_price с WB">
        <FieldRow label="Синхронизировать min_price">
          <Toggle
            value={settings.minPriceSyncEnabled}
            onChange={(v) => update('minPriceSyncEnabled', v)}
            disabled={disabled}
          />
        </FieldRow>

        <FieldRow label="Минимальная маржа для акций">
          <NumberInput
            value={settings.promoMarginThresholdPct}
            onChange={(v) => update('promoMarginThresholdPct', v)}
            min={0}
            max={50}
            suffix="%"
            disabled={disabled}
          />
        </FieldRow>
      </Section>

      <div className="flex items-center justify-between mt-6">
        <div className="text-xs text-muted-foreground/70">
          {saved && <span className="text-emerald-600 font-medium">✓ Настройки сохранены</span>}
          {saveError && <span className="text-red-600">{saveError}</span>}
          {!saved && !saveError && isDirty && <span className="text-amber-600">Есть несохранённые изменения</span>}
        </div>
        <button
          type="button"
          onClick={() => (isDirty ? setConfirmModal(true) : undefined)}
          disabled={saving || disabled || !!priceStepError || !isDirty}
          className="px-5 py-2 bg-primary text-white rounded font-medium text-sm hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground/70"
        >
          {saving ? 'Сохранение…' : 'Сохранить настройки'}
        </button>
      </div>
    </div>
  )
}
