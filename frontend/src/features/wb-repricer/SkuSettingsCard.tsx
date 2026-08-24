import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ArrowLeft, ExternalLink } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  SkuSettingsFormSchema,
  SkuSettingsResponseSchema,
  type RepricerMode,
  type SkuSettingsForm,
  type SkuSettingsResponse,
  type SkuStatus,
} from './schemas'
import type { Scenario } from './fixtures'
import { computePMinKopecks, marginStatusAt } from './pricing'
import { formatRub } from '../../lib/formatRub'
import { cn } from '../../lib/utils'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ChangelogTable, useChangelog } from './ChangelogPage'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'success'; data: SkuSettingsResponse }

type SaveState =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'saved' }
  | { kind: 'saveError'; message: string }

export function SkuSettingsCard({ scenario, articleId }: { scenario: Scenario; articleId: string }) {
  const [load, setLoad] = useState<LoadState>({ kind: 'loading' })
  const [retryToken, setRetryToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoad({ kind: 'loading' })

    async function doFetch(retriesLeft: number): Promise<void> {
      try {
        const getHeaders: Record<string, string> = {}
        if (import.meta.env.DEV) getHeaders['x-scenario'] = scenario
        const res = await fetch(`/api/v1/wb-repricer/sku/${articleId}/settings`, {
          headers: { ...getHeaders },
          signal: controller.signal,
        })
        if (!res.ok) {
          const err = await res.json().catch(() => ({}))
          throw new Error(err?.error?.message ?? `HTTP ${res.status}`)
        }
        const json = await res.json()
        const parsed = SkuSettingsResponseSchema.parse(json)
        setLoad({ kind: 'success', data: parsed })
      } catch (err: unknown) {
        if (controller.signal.aborted) return
        if (retriesLeft > 0) {
          await new Promise((r) => setTimeout(r, 300))
          if (!controller.signal.aborted) return doFetch(retriesLeft - 1)
          return
        }
        const message = err instanceof Error ? err.message : 'Неизвестная ошибка'
        setLoad({ kind: 'error', message })
      }
    }

    void doFetch(1)
    return () => controller.abort()
  }, [scenario, articleId, retryToken])

  if (load.kind === 'loading') return <SkeletonCard />
  if (load.kind === 'error')
    return <ErrorCard message={load.message} onRetry={() => setRetryToken((n) => n + 1)} />
  return <LoadedCard scenario={scenario} articleId={articleId} data={load.data} />
}

// ─── LoadedCard ─────────────────────────────────────────────────────────────

function LoadedCard({ scenario, articleId, data }: { scenario: Scenario; articleId: string; data: SkuSettingsResponse }) {
  const [meta, setMeta] = useState(data.meta)
  const [form, setForm] = useState<SkuSettingsForm>(data.settings)
  const [priceOverride, setPriceOverride] = useState<number | null>(null)
  const [priceOverrideDraft, setPriceOverrideDraft] = useState('')
  const [priceEditorOpen, setPriceEditorOpen] = useState(false)

  useEffect(() => {
    if (scenario === 'validation') {
      setForm((f) => ({ ...f, pMaxKopecks: 30000 }))
    }
  }, [scenario])

  const [save, setSave] = useState<SaveState>({ kind: 'idle' })
  const [confirmLiquidation, setConfirmLiquidation] = useState(false)
  const [activeTab, setActiveTab] = useState<'settings' | 'history'>('settings')

  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    }
  }, [])

  const isWarmup = meta.status === 'warmup'
  const canSync = !isWarmup
  const disableAutomation = isWarmup

  const pMin = useMemo(
    () =>
      computePMinKopecks(
        form.cogsKopecks,
        form.wbCommissionPct,
        form.logisticsKopecks,
        form.allowNegativeMargin ? 0 : form.minMarginPct,
      ),
    [form],
  )

  const displayedPrice = priceOverride ?? meta.currentPriceKopecks
  const margin = useMemo(
    () => marginStatusAt(displayedPrice, form.cogsKopecks, form.wbCommissionPct, form.logisticsKopecks),
    [form, displayedPrice],
  )

  const parseResult = SkuSettingsFormSchema.safeParse(form)
  const pMaxInvalid = form.pMaxKopecks <= pMin
  const fieldErrors: Partial<Record<keyof SkuSettingsForm, string>> = {}
  if (!parseResult.success) {
    for (const issue of parseResult.error.issues) {
      const key = issue.path[0] as keyof SkuSettingsForm
      fieldErrors[key] = issue.message
    }
  }
  if (pMaxInvalid) fieldErrors.pMaxKopecks = 'P_max должен быть больше P_min'
  const hasErrors = Object.keys(fieldErrors).length > 0

  async function onSave() {
    if (hasErrors) return
    setSave({ kind: 'saving' })
    try {
      const putHeaders: Record<string, string> = { 'Content-Type': 'application/json' }
      if (import.meta.env.DEV) putHeaders['x-scenario'] = scenario
      const res = await fetch(`/api/v1/wb-repricer/sku/${articleId}/settings`, {
        method: 'PUT',
        headers: { ...putHeaders },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err?.error?.message ?? `HTTP ${res.status}`)
      }
      const json = SkuSettingsResponseSchema.parse(await res.json())
      setMeta(json.meta)
      setSave({ kind: 'saved' })
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
      toastTimerRef.current = setTimeout(() => setSave({ kind: 'idle' }), 3000)
    } catch (err) {
      setSave({
        kind: 'saveError',
        message: err instanceof Error ? err.message : 'Ошибка сохранения',
      })
    }
  }

  function toggleLiquidation(next: boolean) {
    if (next) { setConfirmLiquidation(true); return }
    setForm((f) => ({ ...f, allowNegativeMargin: false }))
  }

  function acceptLiquidation() {
    setForm((f) => ({ ...f, allowNegativeMargin: true }))
    setConfirmLiquidation(false)
  }

  function applyPriceOverride() {
    const kopecks = Math.round(Number(priceOverrideDraft) * 100)
    if (!Number.isFinite(kopecks) || kopecks <= 0) return
    setPriceOverride(kopecks)
    setPriceEditorOpen(false)
  }

  return (
    <>
      <div className="flex flex-col h-full overflow-hidden">

        {/* ── Identity bar ─────────────────────────────────────────── */}
        <div className="flex-shrink-0 flex items-center gap-3 px-5 py-2.5 border-b border-border">
          <BackButton />
          <div className="w-px h-4 bg-border" />
          <span className="font-mono text-sm font-semibold text-foreground" data-testid="article-id">
            {meta.articleId}
          </span>
          {meta.nmId && (
            <a
              href={`https://www.wildberries.ru/catalog/${meta.nmId}/detail.aspx`}
              target="_blank"
              rel="noopener noreferrer"
              title="Открыть на Wildberries"
              className="text-muted-foreground/50 hover:text-primary transition-colors"
            >
              <ExternalLink size={13} />
            </a>
          )}
          <StatusBadge status={meta.status} />
          <span className="text-sm font-medium text-foreground truncate">{meta.name}</span>
          {data.cachedAt && <PartialBadgePill cachedAt={data.cachedAt} />}
        </div>

        {/* ── Alert banners ─────────────────────────────────────────── */}
        {isWarmup && (
          <AlertBanner
            tone="info"
            testId="warmup-banner"
            title={`Собираем данные: осталось ${meta.warmupDaysLeft ?? 0} дней.`}
            body="Автоматика выключена до накопления статистики. Доступно только ручное управление ценой."
          />
        )}
        {/* ── Two-panel body ────────────────────────────────────────── */}
        <div className="flex flex-1 overflow-hidden">

          {/* LEFT: form + tabs */}
          <div className="flex flex-col flex-1 overflow-hidden border-r border-border">

            {/* Tabs */}
            <div className="flex-shrink-0 flex border-b border-border px-5">
              {(['settings', 'history'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    'px-4 py-2.5 text-sm font-medium transition-colors duration-150 border-b-2 -mb-px',
                    activeTab === tab
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}
                >
                  {tab === 'settings' ? 'Настройки' : 'История'}
                </button>
              ))}
            </div>

            {/* Scrollable form */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'settings' && (
                <SettingsContent
                  form={form}
                  fieldErrors={fieldErrors}
                  formDisabled={false}
                  onChange={setForm}
                  onToggleLiquidation={toggleLiquidation}
                />
              )}
              {activeTab === 'history' && <HistoryTab articleId={articleId} />}
            </div>

            {/* Sticky footer */}
            {activeTab === 'settings' && (
              <div className="flex-shrink-0 border-t border-border px-5 py-3 flex items-center justify-between gap-4 bg-background">
                <div className="text-xs text-muted-foreground" data-testid="last-saved">
                  {meta.lastSavedAt ? (
                    <>
                      Сохранено:{' '}
                      <span className="font-medium text-foreground">
                        {new Date(meta.lastSavedAt).toLocaleString('ru-RU', {
                          hour: '2-digit',
                          minute: '2-digit',
                          day: '2-digit',
                          month: '2-digit',
                        })}
                      </span>
                    </>
                  ) : (
                    'Настройки ещё не сохранялись'
                  )}
                </div>
                <div className="flex items-center gap-3" data-testid="save-status">
                  {save.kind === 'saved' && (
                    <span className="text-emerald-600 text-xs font-medium">✓ Сохранено</span>
                  )}
                  {save.kind === 'saveError' && save.message && (
                    <span className="text-red-600 text-xs">{save.message}</span>
                  )}
                  <button
                    type="button"
                    onClick={onSave}
                    disabled={save.kind === 'saving' || hasErrors}
                    className="inline-flex items-center gap-2 px-4 py-1.5 bg-primary text-primary-foreground font-medium rounded-md text-sm hover:opacity-90 disabled:bg-muted disabled:text-muted-foreground transition-all duration-150 cursor-pointer"
                    data-testid="button-save"
                  >
                    {save.kind === 'saving' ? (
                      <><Spinner /> Сохранение…</>
                    ) : (
                      'Сохранить'
                    )}
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* RIGHT: metrics sidebar */}
          <div className="w-72 xl:w-80 flex-shrink-0 overflow-y-auto flex flex-col divide-y divide-border bg-muted/[0.35]">

            {/* Price */}
            <div className="px-5 py-3.5">
              <SidebarLabel
                text="Текущая цена"
                tooltip={
                  <TooltipBody
                    what="Цена на WB прямо сейчас."
                    when="Меняется алгоритмом или вручную. Синхронизируется с WB каждый цикл."
                    depends="В алгоритме сравнивается с P_min и P_max."
                  />
                }
              />
              <div className="text-2xl font-bold font-mono mt-1" data-testid="current-price">
                {formatRub(priceOverride ?? meta.currentPriceKopecks)}
              </div>
              {priceOverride !== null && (
                <div className="text-xs text-amber-600 mt-0.5">Ручная замена · до след. цикла</div>
              )}
              {!priceEditorOpen ? (
                <div className="flex items-center gap-3 mt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setPriceOverrideDraft(((priceOverride ?? meta.currentPriceKopecks) / 100).toString())
                      setPriceEditorOpen(true)
                    }}
                    className="text-xs text-primary hover:underline cursor-pointer"
                    data-testid="button-price-edit"
                  >
                    Изменить вручную
                  </button>
                  <HelpTooltip
                    placement="bottom"
                    content={
                      <TooltipBody
                        what="Разовое переопределение текущей цены (без изменения COGS и границ)."
                        when="Для акции или быстрой реакции на рынок."
                        depends="Перезаписывает автоматику до следующего цикла."
                      />
                    }
                  />
                  {priceOverride !== null && (
                    <button
                      type="button"
                      onClick={() => { setPriceOverride(null); setPriceOverrideDraft('') }}
                      className="text-xs text-muted-foreground hover:underline cursor-pointer"
                      data-testid="button-price-revert"
                    >
                      Вернуть авто
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2 mt-2" data-testid="price-editor">
                  <input
                    type="number"
                    value={priceOverrideDraft}
                    onChange={(e) => setPriceOverrideDraft(e.target.value)}
                    className="w-24 border border-border rounded-md px-2 py-1 text-sm font-mono text-right focus:outline-none focus:ring-1 focus:ring-primary/40"
                    placeholder="₽"
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={applyPriceOverride}
                    className="px-2 py-1 bg-primary text-primary-foreground text-xs rounded-md hover:opacity-90 cursor-pointer"
                    data-testid="button-price-apply"
                  >
                    Применить
                  </button>
                  <button
                    type="button"
                    onClick={() => { setPriceEditorOpen(false); setPriceOverrideDraft('') }}
                    className="px-2 py-1 bg-muted text-foreground text-xs rounded-md hover:bg-muted/80 cursor-pointer"
                  >
                    Отмена
                  </button>
                </div>
              )}
            </div>

            {/* P_min + Margin */}
            <div className="px-5 py-3.5 space-y-2.5">
              <div>
                <SidebarLabel
                  text="P_min"
                  tooltip={
                    <TooltipBody
                      what="Минимальная цена, ниже которой продавать нельзя (сохраняет мин. маржу)."
                      when="Считается автоматически. Меняется через COGS / Логистику / Маржу."
                      depends="Синхронизируется с WB как min_price."
                    />
                  }
                />
                <div className="text-lg font-semibold font-mono mt-0.5" data-testid="derived-pmin">
                  {formatRub(pMin)}
                </div>
                <div className="text-xs mt-0.5" data-testid="pmin-sync">
                  {canSync ? (
                    <span className="text-emerald-600">✓ Синхронизировано с WB</span>
                  ) : (
                    <span className="text-muted-foreground">Не синхронизируется во время прогрева</span>
                  )}
                </div>
              </div>
              <div>
                <SidebarLabel
                  text="Маржа при текущей цене"
                  tooltip={
                    <TooltipBody
                      what="Фактическая маржа при цене WB прямо сейчас."
                      when="Мониторить во время акций WB — цена может опуститься."
                      depends="Считается от текущей цены, COGS, комиссии и логистики."
                    />
                  }
                />
                <MarginIndicator status={margin} price={displayedPrice} />
              </div>
            </div>

            {/* Baskets / Revenue mode signal */}
            {form.repricerMode === 'baskets' ? (
              <div className="px-5 py-3.5">
                <SidebarLabel
                  text="Корзины 7 дней"
                  tooltip={
                    <TooltipBody
                      what="Сколько раз товар добавили в корзину WB за 7 дней, и норма — ориентир для спроса."
                      when="Выше нормы → сигнал повысить цену. Ниже → снизить."
                      depends="Норму можно задать вручную. Источники: ручной → авто → fallback (прогрев)."
                    />
                  }
                />
                <BasketsRow
                  meta={meta}
                  basketNormMode={form.basketNormMode}
                  basketNormManual={form.basketNormManual}
                  onBasketNormChange={(mode, manual) =>
                    setForm((f) => ({ ...f, basketNormMode: mode, basketNormManual: manual }))
                  }
                />
              </div>
            ) : (
              <div className="px-5 py-3.5">
                <SidebarLabel
                  text="Сигнал: Выручка"
                  tooltip={
                    <TooltipBody
                      what="Режим 2: цена двигается по динамике выручки за выбранный период."
                      when="Выручка растёт → цена поднимается шагами. Падает → снижается."
                      depends="Период сравнения задаётся в настройках SKU."
                    />
                  }
                />
                <div className="mt-2 space-y-1.5">
                  <div className="text-sm font-medium text-foreground">
                    Период: {form.revenueComparisonDays} дн.
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Текущий период vs предыдущий
                  </div>
                  <div className="text-xs text-amber-700 dark:text-amber-400">
                    В акции не участвует
                  </div>
                </div>
              </div>
            )}

            {/* Automation */}
            <div className="px-5 py-3.5">
              <SidebarLabel
                text="Автоматика"
                tooltip={
                  <TooltipBody
                    what="Кто управляет ценой: система (auto) или менеджер (manual)."
                    when="Выключайте на время ручных корректировок или ценовых экспериментов."
                      depends="Не работает при warmup (< 30 дней)."
                  />
                }
              />
              <AutomationToggle
                value={form.automationEnabled && !disableAutomation}
                disabled={disableAutomation}
                onChange={(v) => setForm((f) => ({ ...f, automationEnabled: v }))}
              />
            </div>
          </div>
        </div>
      </div>

      {confirmLiquidation && (
        <LiquidationConfirm onAccept={acceptLiquidation} onCancel={() => setConfirmLiquidation(false)} />
      )}
    </>
  )
}

// ─── SettingsContent ─────────────────────────────────────────────────────────

function RepricerModeSelector({
  value,
  disabled,
  onChange,
}: {
  value: RepricerMode
  disabled: boolean
  onChange: (mode: RepricerMode) => void
}) {
  const modes: { key: RepricerMode; label: string; hint: string }[] = [
    {
      key: 'baskets',
      label: 'Режим 1: Корзины',
      hint: 'Цена двигается по добавлениям в корзину. Корзины↑ → +3%, Корзины↓ → −3%.',
    },
    {
      key: 'revenue',
      label: 'Режим 2: Динамика выручки',
      hint: 'Цена двигается по динамике выручки за период. Выручка↑ → +5%, Выручка↓ → −5%.',
    },
  ]
  return (
    <div className="flex flex-col gap-2">
      {modes.map((m) => (
        <label
          key={m.key}
          className={cn(
            'flex items-start gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors',
            value === m.key ? 'border-primary bg-primary/5' : 'border-border hover:bg-muted/30',
            disabled && 'pointer-events-none opacity-50',
          )}
        >
          <input
            type="radio"
            name="repricerMode"
            value={m.key}
            checked={value === m.key}
            disabled={disabled}
            onChange={() => onChange(m.key)}
            className="mt-0.5 text-primary cursor-pointer"
          />
          <div>
            <div className="text-sm font-medium text-foreground">{m.label}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{m.hint}</div>
          </div>
        </label>
      ))}
    </div>
  )
}

// Таблица шагов для режима 2 (из Excel Марии, апрель 2026)
const REVENUE_STEPS = [
  { from: '< 75%', action: 'Снижаем', step: '−5%', min: '30 ₽' },
  { from: '75–85%', action: 'Снижаем', step: '−4%', min: '20 ₽' },
  { from: '85–95%', action: 'Снижаем', step: '−3%', min: '10 ₽' },
  { from: '95–105%', action: 'Держим', step: '—', min: '—' },
  { from: '105–115%', action: 'Повышаем', step: '+3%', min: '10 ₽' },
  { from: '115–125%', action: 'Повышаем', step: '+4%', min: '20 ₽' },
  { from: '> 125%', action: 'Повышаем', step: '+5%', min: '30 ₽' },
]

function RevenueModeSettings({
  form,
  disabled,
  onChange,
}: {
  form: SkuSettingsForm
  disabled: boolean
  onChange: (updater: (f: SkuSettingsForm) => SkuSettingsForm) => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <div className="text-sm font-medium text-foreground">Период сравнения</div>
          <div className="text-xs text-muted-foreground mt-0.5">
            Текущий период vs предыдущий. Уточняется с Марией.
          </div>
        </div>
        <select
          value={form.revenueComparisonDays}
          disabled={disabled}
          onChange={(e) =>
            onChange((f) => ({ ...f, revenueComparisonDays: Number(e.target.value) }))
          }
          className="border border-border rounded px-2 py-1.5 text-sm bg-card focus:border-primary focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed"
        >
          <option value={1}>1 день</option>
          <option value={3}>3 дня</option>
          <option value={7}>7 дней (рекомендовано)</option>
          <option value={14}>14 дней</option>
        </select>
      </div>

      <div>
        <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
          Таблица шагов
        </div>
        <div className="rounded-md border border-border overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-muted/40">
                <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Динамика</th>
                <th className="px-3 py-1.5 text-left font-medium text-muted-foreground">Действие</th>
                <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Шаг</th>
                <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Мин.</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {REVENUE_STEPS.map((s) => (
                <tr key={s.from} className={s.action === 'Держим' ? 'bg-muted/20' : ''}>
                  <td className="px-3 py-1.5 font-mono text-foreground">{s.from}</td>
                  <td
                    className={cn(
                      'px-3 py-1.5',
                      s.action === 'Повышаем'
                        ? 'text-emerald-700 dark:text-emerald-400'
                        : s.action === 'Снижаем'
                          ? 'text-red-600 dark:text-red-400'
                          : 'text-muted-foreground',
                    )}
                  >
                    {s.action}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono font-medium text-foreground">
                    {s.step}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-muted-foreground">
                    {s.min}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-2 text-xs text-muted-foreground space-y-0.5">
          <div>Нет заказов за период → −3%/день</div>
          <div>Потолок роста: не более +5% от базовой цены</div>
          <div className="text-amber-700 dark:text-amber-400">В акции WB: не участвовать</div>
        </div>
      </div>
    </div>
  )
}

function SettingsContent({
  form,
  fieldErrors,
  formDisabled,
  onChange,
  onToggleLiquidation,
}: {
  form: SkuSettingsForm
  fieldErrors: Partial<Record<keyof SkuSettingsForm, string>>
  formDisabled: boolean
  onChange: (updater: (f: SkuSettingsForm) => SkuSettingsForm) => void
  onToggleLiquidation: (v: boolean) => void
}) {
  return (
    <div className="px-5 py-4 space-y-5">
      {/* Режим ценообразования */}
      <section>
        <SectionTitle
          title="Режим ценообразования"
          tooltip={
            <TooltipBody
              what="Какой сигнал использует алгоритм для движения цены."
              when="Выбирайте Режим 1 для новых товаров (быстро реагирует на спрос). Режим 2 — для стабильных SKU с историей выручки."
              depends="Оба режима работают в коридоре P_min–P_max."
            />
          }
        />
        <div className="mt-3">
          <RepricerModeSelector
            value={form.repricerMode}
            disabled={formDisabled}
            onChange={(mode) => onChange((f) => ({ ...f, repricerMode: mode }))}
          />
        </div>
        {form.repricerMode === 'revenue' && (
          <div className="mt-4">
            <RevenueModeSettings form={form} disabled={formDisabled} onChange={onChange} />
          </div>
        )}
      </section>

      {/* Экономика */}
      <section>
        <SectionTitle
          title="Экономика"
          tooltip={
            <TooltipBody
              what="Параметры, по которым считается P_min — минимальная цена без убытка."
              when="Меняйте при смене поставщика, пересчёте затрат или изменении комиссии WB."
              depends="COGS + Логистика + Комиссия + Мин. маржа → P_min ниже."
            />
          }
        />
        <div className="mt-3 grid grid-cols-2 gap-x-5 gap-y-3">
          <NumberField
            label="Себестоимость"
            hint="Стоимость производства 1 шт."
            tooltip={
              <TooltipBody
                what="Себестоимость производства одной единицы."
                when="Меняется при смене поставщика или пересчёте затрат."
                depends="P_min = Себес + Логистика/выкуп + Комиссия WB + Хранение 21₽ + НДС 20% + целевая маржа."
              />
            }
            value={form.cogsKopecks / 100}
            onChange={(v) => onChange((f) => ({ ...f, cogsKopecks: Math.round(v * 100) }))}
            suffix="₽"
            step={1}
            error={fieldErrors.cogsKopecks}
            disabled={formDisabled}
            testId="field-cogs"
          />
          <NumberField
            label="Комиссия WB"
            hint="В процентах от продажи"
            tooltip={
              <TooltipBody
                what="Процент WB с каждой продажи."
                when="WB может менять, обновляйте при смене категории или тарифа."
                depends="Уменьшает net-выручку → повышает P_min."
              />
            }
            value={form.wbCommissionPct}
            onChange={(v) => onChange((f) => ({ ...f, wbCommissionPct: v }))}
            suffix="%"
            error={fieldErrors.wbCommissionPct}
            disabled={formDisabled}
            testId="field-commission"
          />
          <NumberField
            label="Логистика WB"
            hint="Доставка WB → покупатель"
            tooltip={
              <TooltipBody
                what="Стоимость доставки WB → покупатель."
                when="Зависит от склада и зоны; обновляйте при смене FBS-склада."
                depends="Входит в P_min."
              />
            }
            value={form.logisticsKopecks / 100}
            onChange={(v) => onChange((f) => ({ ...f, logisticsKopecks: Math.round(v * 100) }))}
            suffix="₽"
            step={1}
            error={fieldErrors.logisticsKopecks}
            disabled={formDisabled}
            testId="field-logistics"
          />
          <NumberField
            label="Целевая маржа"
            hint="Минимальная прибыль при которой продаём"
            tooltip={
              <TooltipBody
                what="Минимальная маржа, с которой вы готовы продавать."
                when="Стратегическое решение: глубже → больше продаж и риска."
                depends="Определяет P_min. Акционная цена тоже проверяется по этому порогу."
              />
            }
            value={form.minMarginPct}
            onChange={(v) => onChange((f) => ({ ...f, minMarginPct: v }))}
            suffix="%"
            error={fieldErrors.minMarginPct}
            disabled={formDisabled}
            testId="field-margin"
          />
        </div>
      </section>

      {/* Границы и режимы */}
      <section>
        <SectionTitle
          title="Границы и режимы"
          tooltip={
            <TooltipBody
              what="Верхняя граница цены и специальные режимы."
              when="P_max ограничивает алгоритм сверху; режим ликвидации разрешает работу в минус."
              depends="Автоматика двигает цену между P_min и P_max по сигналу корзин."
            />
          }
        />
        <div className="mt-3 space-y-3">
          <div className="max-w-xs">
            <NumberField
              label="Максимальная цена"
              hint="Алгоритм не поднимет выше"
              tooltip={
                <TooltipBody
                  what="Максимальная цена, выше которой автоматика не поднимет."
                  when="Выше P_max — теряем конкурентоспособность. Ниже — оставляем деньги на столе."
                  depends="Потолок для автоматического роста по корзинам. По умолчанию: базовая цена × 1.05."
                />
              }
              value={form.pMaxKopecks / 100}
              onChange={(v) => onChange((f) => ({ ...f, pMaxKopecks: Math.round(v * 100) }))}
              suffix="₽"
              step={1}
              error={fieldErrors.pMaxKopecks}
              disabled={formDisabled}
              testId="field-pmax"
            />
          </div>

          <label
            className={cn(
              'flex items-start gap-3 rounded-lg border px-4 py-3 cursor-pointer transition-colors',
              form.allowNegativeMargin
                ? 'border-red-300 bg-red-500/5'
                : 'border-border hover:bg-muted/30',
              formDisabled && 'pointer-events-none opacity-50',
            )}
          >
            <input
              type="checkbox"
              className="mt-0.5 cursor-pointer"
              checked={form.allowNegativeMargin}
              disabled={formDisabled}
              onChange={(e) => onToggleLiquidation(e.target.checked)}
              data-testid="toggle-liquidation"
            />
            <div>
              <div className={cn('text-sm font-medium flex items-center gap-1.5', form.allowNegativeMargin && 'text-red-600')}>
                Разрешить отрицательную маржу
                <HelpTooltip
                  content={
                    <TooltipBody
                      what="Режим ликвидации. Цена может опускаться ниже P_min."
                      when="Товар нужно распродать любой ценой — смена коллекции, замороженные остатки."
                      depends="Снижает P_min до 0 в расчётах. Работает до остановки вручную."
                    />
                  }
                />
              </div>
              <div className={cn('text-xs mt-0.5', form.allowNegativeMargin ? 'text-red-600' : 'text-muted-foreground')}>
                Режим ликвидации. Цена может опускаться ниже точки безубыточности.
              </div>
            </div>
          </label>
        </div>
      </section>
    </div>
  )
}

// ─── Back button ─────────────────────────────────────────────────────────────

function BackButton() {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      onClick={() => navigate(-1)}
      className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
    >
      <ArrowLeft size={14} />
      <span>Товары</span>
    </button>
  )
}

// ─── Sidebar label ────────────────────────────────────────────────────────────

function SidebarLabel({ text, tooltip }: { text: string; tooltip: ReactNode }) {
  return (
    <div className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
      {text}
      <HelpTooltip content={tooltip} placement="bottom" />
    </div>
  )
}

// ─── AutomationToggle ─────────────────────────────────────────────────────────

function AutomationToggle({
  value,
  disabled,
  onChange,
}: {
  value: boolean
  disabled: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className={cn('inline-flex items-center gap-2 mt-2', disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer')}>
      <span className="relative inline-block w-8 h-4">
        <input
          type="checkbox"
          className="peer sr-only"
          checked={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
          data-testid="toggle-automation"
        />
        <span
          className={cn(
            'absolute inset-0 rounded-full transition-colors',
            disabled ? 'bg-muted' : value ? 'bg-emerald-500' : 'bg-muted',
          )}
        />
        <span
          className={cn(
            'absolute top-0.5 left-0.5 w-3 h-3 bg-white rounded-full shadow transition-transform',
            value ? 'translate-x-4' : '',
          )}
        />
      </span>
      <span className="text-sm text-foreground">{value ? 'Авто' : 'Ручной'}</span>
    </label>
  )
}

// ─── BasketsRow ──────────────────────────────────────────────────────────────

function BasketsRow({
  meta,
  basketNormMode,
  basketNormManual,
  onBasketNormChange,
}: {
  meta: SkuSettingsResponse['meta']
  basketNormMode: 'auto' | 'manual'
  basketNormManual: number | null
  onBasketNormChange: (mode: 'auto' | 'manual', manual: number | null) => void
}) {
  const [editing, setEditing] = useState(false)
  const displayedNorm = basketNormMode === 'manual' && basketNormManual !== null ? basketNormManual : meta.basketNorm
  const [draft, setDraft] = useState(String(displayedNorm))
  const source: 'manual' | 'auto' | 'fallback' = basketNormMode === 'manual' ? 'manual' : meta.basketNormSource

  function applyManual() {
    const n = Math.max(0, Math.round(Number(draft)))
    if (!Number.isFinite(n)) return
    onBasketNormChange('manual', n)
    setEditing(false)
  }

  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            'text-lg font-bold font-mono',
            meta.basketsLast7d >= displayedNorm ? 'text-emerald-600' : 'text-amber-600',
          )}
          data-testid="baskets-count"
        >
          {meta.basketsLast7d}
        </span>
        <span className="text-sm text-muted-foreground">/ {displayedNorm} норма</span>
        <BasketNormBadge source={source} />
      </div>

      {!editing && (
        <button
          type="button"
          onClick={() => { setDraft(String(displayedNorm)); setEditing(true) }}
          className="text-xs text-primary hover:underline cursor-pointer"
          data-testid="button-basket-norm-edit"
        >
          Изменить норму
        </button>
      )}

      {editing && (
        <div className="flex items-center gap-1.5" data-testid="basket-norm-editor">
          <input
            type="number"
            min={0}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applyManual()
              if (e.key === 'Escape') setEditing(false)
            }}
            className="w-16 border border-border rounded px-1.5 py-0.5 text-xs font-mono text-right focus:outline-none focus:ring-1 focus:ring-primary/40"
            autoFocus
            data-testid="input-basket-norm"
          />
          <button
            type="button"
            onClick={applyManual}
            className="px-1.5 py-0.5 bg-primary text-primary-foreground rounded text-[11px] hover:opacity-90 cursor-pointer"
            data-testid="button-basket-norm-apply"
          >
            Применить
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="text-[11px] text-muted-foreground hover:underline cursor-pointer"
          >
            Отмена
          </button>
          {basketNormMode === 'manual' && (
            <button
              type="button"
              onClick={() => { onBasketNormChange('auto', null); setEditing(false) }}
              className="text-[11px] text-muted-foreground hover:underline cursor-pointer"
              data-testid="button-basket-norm-revert"
            >
              Авто
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function BasketNormBadge({ source }: { source: 'manual' | 'auto' | 'fallback' }) {
  const map = {
    manual: { label: 'вручную', cls: 'bg-primary/10 text-primary' },
    auto: { label: 'авто', cls: 'bg-emerald-500/10 text-emerald-700' },
    fallback: { label: 'прогрев', cls: 'bg-amber-500/10 text-amber-700' },
  } as const
  const { label, cls } = map[source]
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-px text-[10px] font-medium ${cls}`}
      data-testid={`basket-norm-source-${source}`}
    >
      {label}
    </span>
  )
}

// ─── Tooltip ─────────────────────────────────────────────────────────────────

function HelpTooltip({ content, placement = 'top' }: { content: ReactNode; placement?: 'top' | 'bottom' }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="Подсказка"
          className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-muted text-muted-foreground hover:bg-muted/80 focus:outline-none text-[9px] font-bold cursor-help"
        >
          ?
        </button>
      </TooltipTrigger>
      <TooltipContent
        side={placement}
        sideOffset={6}
        collisionPadding={12}
        className="w-72 max-w-[calc(100vw-2rem)] bg-popover text-popover-foreground border border-border shadow-lg px-3 py-2.5 text-xs leading-relaxed whitespace-normal"
      >
        {content}
      </TooltipContent>
    </Tooltip>
  )
}

function TooltipBody({ what, when, depends }: { what: string; when: string; depends: string }) {
  return (
    <span className="block space-y-1.5">
      <span className="block"><span className="font-semibold text-muted-foreground">Что:</span> {what}</span>
      <span className="block"><span className="font-semibold text-muted-foreground">Когда менять:</span> {when}</span>
      <span className="block"><span className="font-semibold text-muted-foreground">Связь:</span> {depends}</span>
    </span>
  )
}

function SectionTitle({ title, tooltip }: { title: string; tooltip: ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-sm font-semibold text-foreground">{title}</span>
      <HelpTooltip content={tooltip} />
    </div>
  )
}

// ─── Status badges & banners ──────────────────────────────────────────────────

function StatusBadge({ status }: { status: SkuStatus }) {
  const config: Record<SkuStatus, { label: string; className: string; tooltip: ReactNode }> = {
    auto: {
      label: 'авто',
      className: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
      tooltip: <TooltipBody what="Автоматика активна — цены меняются по алгоритму корзин." when="Включается после warmup." depends="Можно переключить на manual тумблером." />,
    },
    manual: {
      label: 'ручной',
      className: 'bg-muted text-foreground border-border',
      tooltip: <TooltipBody what="Автоматика отключена — цена меняется только вручную." when="Выбирайте для ручных экспериментов с ценой." depends="Включить обратно — тумблером «Автоматика»." />,
    },
    warmup: {
      label: 'прогрев',
      className: 'bg-blue-500/10 text-blue-700 border-blue-500/20',
      tooltip: <TooltipBody what="SKU < 30 дней в системе — собираем данные." when="Выходит автоматически, когда накоплено 30 дней статистики." depends="Автоматика недоступна до окончания warmup." />,
    },
    liquidation: {
      label: 'ликвидация',
      className: 'bg-red-600/10 text-red-800 border-red-600/30 dark:text-red-400',
      tooltip: <TooltipBody what="Активен режим ликвидации — цена планомерно снижается." when="Запускается вручную из раздела Ликвидация." depends="Цель — распродать остаток, маржа может быть отрицательной." />,
    },
  }
  const { label, className, tooltip } = config[status]
  return (
    <span className="inline-flex items-center gap-1">
      <span
        className={`inline-flex items-center px-1.5 py-px text-[11px] font-medium rounded border ${className}`}
        data-testid={`status-${status}`}
      >
        {label}
      </span>
      <HelpTooltip content={tooltip} placement="bottom" />
    </span>
  )
}

function MarginIndicator({ status, price }: { status: 'negative' | 'thin' | 'ok'; price: number }) {
  const cfg = {
    negative: { label: 'Отрицательная', className: 'text-red-600' },
    thin: { label: 'Тонкая (< 10%)', className: 'text-amber-600' },
    ok: { label: 'Достаточная', className: 'text-emerald-600' },
  }[status]
  return (
    <div className={cn('text-sm font-semibold mt-0.5', cfg.className)} data-testid="margin-status">
      {cfg.label}{' '}
      <span className="text-xs font-normal text-muted-foreground">при {formatRub(price)}</span>
    </div>
  )
}

function PartialBadgePill({ cachedAt }: { cachedAt: string }) {
  const time = new Date(cachedAt)
  const mins = Math.round((Date.now() - time.getTime()) / 60000)
  return (
    <span
      className="ml-auto text-xs text-amber-700 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-md"
      data-testid="partial-badge"
    >
      Кэш {mins} мин назад
    </span>
  )
}

function AlertBanner({ tone, testId, title, body }: { tone: 'info' | 'error'; testId?: string; title: string; body: string }) {
  const cls = tone === 'error'
    ? 'bg-red-500/5 border-b border-red-500/20 text-red-800'
    : 'bg-blue-500/5 border-b border-blue-500/20 text-blue-800'
  return (
    <div className={`flex-shrink-0 px-5 py-2.5 text-sm ${cls}`} data-testid={testId}>
      <span className="font-medium">{title}</span>
      <span className="ml-2 opacity-75 text-xs">{body}</span>
    </div>
  )
}

// ─── NumberField ─────────────────────────────────────────────────────────────

function NumberField({
  label,
  hint,
  tooltip,
  value,
  onChange,
  suffix,
  step,
  error,
  disabled,
  testId,
}: {
  label: string
  hint?: string
  tooltip?: ReactNode
  value: number
  onChange: (v: number) => void
  suffix?: string
  step?: number
  error?: string
  disabled?: boolean
  testId?: string
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground font-semibold inline-flex items-center gap-1">
        <span>{label}</span>
        {tooltip && <HelpTooltip content={tooltip} />}
      </div>
      <div className="mt-1 flex items-center gap-2">
        <input
          type="number"
          value={value}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
          disabled={disabled}
          data-testid={testId}
          className={cn(
            'w-full border rounded-md px-2.5 py-1.5 text-sm font-mono',
            'transition-[border-color,box-shadow] duration-150',
            'shadow-[inset_0_1px_2px_rgba(0,0,0,0.04)]',
            'focus:outline-none focus:ring-1',
            disabled && 'bg-muted cursor-not-allowed opacity-60',
            error
              ? 'border-red-400 focus:ring-red-300'
              : 'border-border focus:border-primary/40 focus:ring-primary/20 focus:shadow-[inset_0_1px_2px_rgba(0,0,0,0.04),0_0_0_3px_hsl(var(--primary)/0.08)]',
          )}
        />
        {suffix && <span className="text-xs text-muted-foreground font-medium flex-shrink-0">{suffix}</span>}
      </div>
      {hint && !error && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
      {error && (
        <div className="text-xs text-red-600 mt-1" data-testid={`${testId}-error`}>
          {error}
        </div>
      )}
    </div>
  )
}

// ─── Skeleton / Error ─────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="flex flex-col h-full overflow-hidden animate-pulse" data-testid="skeleton">
      <div className="flex-shrink-0 flex items-center gap-3 px-5 py-3 border-b border-border">
        <div className="h-4 w-16 bg-muted rounded" />
        <div className="h-4 w-24 bg-muted rounded" />
        <div className="h-4 w-48 bg-muted rounded" />
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 p-6 space-y-6 border-r border-border">
          <div className="grid grid-cols-2 gap-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i}>
                <div className="h-3 w-24 bg-muted rounded" />
                <div className="mt-2 h-9 bg-muted rounded-md" />
              </div>
            ))}
          </div>
        </div>
        <div className="w-72 p-5 space-y-6">
          <div className="h-3 w-20 bg-muted rounded" />
          <div className="h-8 w-28 bg-muted rounded" />
          <div className="h-3 w-20 bg-muted rounded" />
          <div className="h-6 w-24 bg-muted rounded" />
        </div>
      </div>
    </div>
  )
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col h-full overflow-hidden" data-testid="error-card">
      <div className="px-6 py-4 bg-red-500/5 border-b border-red-500/20">
        <div className="text-sm font-medium text-red-800">Не удалось загрузить настройки SKU</div>
        <div className="text-xs text-red-600 mt-1">{message}</div>
      </div>
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="text-center space-y-4">
          <p className="text-sm text-muted-foreground">Проверьте соединение и попробуйте снова.</p>
          <button
            type="button"
            onClick={onRetry}
            className="px-4 py-2 bg-red-500 text-white font-medium rounded-md text-sm hover:bg-red-600 cursor-pointer"
            data-testid="button-retry"
          >
            Повторить
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── LiquidationConfirm ───────────────────────────────────────────────────────

function LiquidationConfirm({ onAccept, onCancel }: { onAccept: () => void; onCancel: () => void }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      data-testid="liquidation-modal"
    >
      <div className="bg-card rounded-lg shadow-lg max-w-md w-full border border-border">
        <div className="px-6 py-4 border-b border-border">
          <div className="text-base font-semibold text-foreground">Включить режим ликвидации?</div>
        </div>
        <div className="px-6 py-4 text-sm text-foreground space-y-2">
          <p>
            В этом режиме маржа может быть <strong>отрицательной</strong>. Цена товара сможет уходить ниже точки безубыточности.
          </p>
          <p className="text-xs text-muted-foreground">
            Режим работает до тех пор, пока вы не отключите его вручную.
          </p>
        </div>
        <div className="px-6 py-4 border-t border-border flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 border border-border rounded-md text-sm hover:bg-muted/40 cursor-pointer"
            data-testid="button-liquidation-cancel"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="px-4 py-2 bg-red-500 text-white font-medium rounded-md text-sm hover:bg-red-600 cursor-pointer"
            data-testid="button-liquidation-accept"
          >
            Включить
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Spinner ──────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  )
}

// ─── HistoryTab ───────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { label: '7 дней', ms: 7 * 86400_000 },
  { label: '30 дней', ms: 30 * 86400_000 },
] as const

function HistoryTab({ articleId }: { articleId: string }) {
  const [periodMs, setPeriodMs] = useState(7 * 86400_000)
  const state = useChangelog({ articleId, triggers: [], periodMs })

  return (
    <div className="p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs text-muted-foreground">Период:</span>
        <div className="inline-flex rounded-md border border-border overflow-hidden">
          {PERIOD_OPTIONS.map((p) => (
            <button
              key={p.ms}
              type="button"
              onClick={() => setPeriodMs(p.ms)}
              className={cn(
                'px-3 py-1 text-xs font-medium transition-colors cursor-pointer',
                periodMs === p.ms
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-muted-foreground hover:bg-muted/40',
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {state.kind === 'loading' && <div className="py-8 text-center text-muted-foreground text-sm animate-pulse">Загружаем историю…</div>}
      {state.kind === 'error' && <div className="py-8 text-center text-red-600 text-sm">{state.message}</div>}
      {state.kind === 'success' && <ChangelogTable items={state.items} showSku={false} />}
    </div>
  )
}
