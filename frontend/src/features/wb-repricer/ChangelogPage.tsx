import { Fragment, useEffect, useState } from 'react'
import { ChangelogResponseSchema, PriceChangeTrigger, type PriceChangeEntry } from './schemas'
import { formatRub } from '../../lib/formatRub'

// ── Конфиг триггеров ─────────────────────────────────────────────────────

const TRIGGER_META: Record<
  PriceChangeEntry['trigger'],
  { label: string; cls: string }
> = {
  algorithm:            { label: 'Алгоритм',    cls: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300' },
  night_median_up:      { label: '🌙 Медиана ↑', cls: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300' },
  night_median_restore: { label: '☀️ Медиана →', cls: 'bg-slate-100 text-slate-700 dark:bg-slate-700/40 dark:text-slate-300' },
  manual:               { label: 'Вручную',      cls: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' },
  liquidation:          { label: 'Ликвидация',   cls: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300' },
  warmup_end:           { label: 'Прогрев ✓',    cls: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' },
  wb_sync:              { label: 'WB sync',       cls: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300' },
}

export function TriggerBadge({ trigger }: { trigger: PriceChangeEntry['trigger'] }) {
  const cfg = TRIGGER_META[trigger]
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium rounded whitespace-nowrap ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

// ── Форматирование ───────────────────────────────────────────────────────

function fmtTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function fmtDate(iso: string) {
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date(today.getTime() - 86400_000)
  if (d.toDateString() === today.toDateString()) return 'Сегодня'
  if (d.toDateString() === yesterday.toDateString()) return 'Вчера'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function changeCls(pct: number) {
  if (pct > 0) return 'text-emerald-600 dark:text-emerald-400'
  if (pct < 0) return 'text-red-600 dark:text-red-400'
  return 'text-muted-foreground'
}

function marginCls(pct: number) {
  if (pct < 0) return 'text-red-600 dark:text-red-400'
  if (pct < 10) return 'text-amber-600'
  return 'text-emerald-600 dark:text-emerald-400'
}

// ── Таблица (переиспользуется в SkuSettingsCard) ─────────────────────────

type ChangelogTableProps = {
  items: PriceChangeEntry[]
  showSku?: boolean
  onSkuClick?: (articleId: string) => void
}

export function ChangelogTable({ items, showSku = true, onSkuClick }: ChangelogTableProps) {
  if (items.length === 0) {
    return (
      <div className="py-16 text-center text-muted-foreground text-sm">
        Изменений за выбранный период нет
      </div>
    )
  }

  let lastDate = ''

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-xs text-muted-foreground text-left">
            <th className="pb-2 pr-4 font-medium w-28">Время</th>
            {showSku && <th className="pb-2 pr-4 font-medium">Товар</th>}
            <th className="pb-2 pr-4 font-medium text-right">Было</th>
            <th className="pb-2 pr-4 font-medium text-right">Стало</th>
            <th className="pb-2 pr-4 font-medium text-right">Δ%</th>
            <th className="pb-2 pr-4 font-medium">Причина</th>
            <th className="pb-2 font-medium text-right">Маржа</th>
          </tr>
        </thead>
        <tbody>
          {items.map((entry) => {
            const dateLabel = fmtDate(entry.timestamp)
            const showDateRow = dateLabel !== lastDate
            if (showDateRow) lastDate = dateLabel

            return (
              <Fragment key={entry.id}>
                {showDateRow && (
                  <tr>
                    <td
                      colSpan={showSku ? 7 : 6}
                      className="pt-4 pb-1 text-xs font-semibold text-muted-foreground uppercase tracking-wide"
                    >
                      {dateLabel}
                    </td>
                  </tr>
                )}
                <tr
                  className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">
                    {fmtTime(entry.timestamp)}
                  </td>
                  {showSku && (
                    <td className="py-2 pr-4 max-w-[220px]">
                      {onSkuClick ? (
                        <button
                          type="button"
                          onClick={() => onSkuClick(entry.articleId)}
                          className="text-left hover:text-indigo-600 hover:underline"
                        >
                          <span className="font-mono text-xs text-muted-foreground block">{entry.articleId}</span>
                          <span className="truncate block">{entry.skuName}</span>
                        </button>
                      ) : (
                        <>
                          <span className="font-mono text-xs text-muted-foreground block">{entry.articleId}</span>
                          <span className="truncate block">{entry.skuName}</span>
                        </>
                      )}
                    </td>
                  )}
                  <td className="py-2 pr-4 font-mono text-right text-muted-foreground">
                    {formatRub(entry.oldPriceKopecks)}
                  </td>
                  <td className="py-2 pr-4 font-mono font-semibold text-right text-foreground">
                    {formatRub(entry.newPriceKopecks)}
                  </td>
                  <td className={`py-2 pr-4 font-mono text-right font-medium ${changeCls(entry.changePct)}`}>
                    {entry.changePct > 0 ? '+' : ''}{entry.changePct.toFixed(1)}%
                  </td>
                  <td className="py-2 pr-4">
                    <TriggerBadge trigger={entry.trigger} />
                  </td>
                  <td className={`py-2 font-mono text-right font-medium ${marginCls(entry.marginAfterPct)}`}>
                    {entry.marginAfterPct.toFixed(1)}%
                  </td>
                </tr>
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Хук загрузки ─────────────────────────────────────────────────────────

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'success'; items: PriceChangeEntry[]; total: number }

type ChangelogParams = {
  articleId?: string
  triggers: PriceChangeEntry['trigger'][]
  periodMs: number
}

// periodMs вместо fromMs — иначе Date.now() в каждом рендере создаёт новую зависимость
// и useEffect бесконечно перезапускается, отменяя fetch до завершения.
export function useChangelog({ articleId, triggers, periodMs }: ChangelogParams) {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })
  const triggersKey = triggers.join(',')

  useEffect(() => {
    const controller = new AbortController()
    setState({ kind: 'loading' })

    async function doFetch(retriesLeft: number): Promise<void> {
      try {
        const fromMs = Date.now() - periodMs
        const url = new URL(
          articleId
            ? `/api/v1/wb-repricer/sku/${articleId}/changelog`
            : '/api/v1/wb-repricer/changelog',
          window.location.origin,
        )
        url.searchParams.set('from', new Date(fromMs).toISOString())
        url.searchParams.set('limit', '200')
        for (const tr of triggersKey.split(',').filter(Boolean)) url.searchParams.append('trigger', tr)

        const res = await fetch(url.toString(), { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        const parsed = ChangelogResponseSchema.parse(json)
        setState({ kind: 'success', items: parsed.items, total: parsed.total })
      } catch (err: unknown) {
        if (controller.signal.aborted) return
        if (retriesLeft > 0) {
          await new Promise((r) => setTimeout(r, 300))
          if (!controller.signal.aborted) return doFetch(retriesLeft - 1)
          return
        }
        setState({ kind: 'error', message: err instanceof Error ? err.message : 'Ошибка' })
      }
    }

    void doFetch(1)
    return () => controller.abort()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [articleId, triggersKey, periodMs])

  return state
}

// ── Фильтры ──────────────────────────────────────────────────────────────

const ALL_TRIGGERS = PriceChangeTrigger.options

const PERIOD_PRESETS = [
  { label: '24 ч', ms: 24 * 3600_000 },
  { label: '7 дней', ms: 7 * 86400_000 },
  { label: '30 дней', ms: 30 * 86400_000 },
]

// ── Страница ─────────────────────────────────────────────────────────────

export function ChangelogPage({ onOpenSku }: { onOpenSku?: (articleId: string) => void }) {
  const [periodMs, setPeriodMs] = useState(24 * 3600_000)
  const [activeTriggers, setActiveTriggers] = useState<PriceChangeEntry['trigger'][]>([])
  const [skuSearch, setSkuSearch] = useState('')

  const triggerFilter = activeTriggers.length ? activeTriggers : ALL_TRIGGERS

  const state = useChangelog({ triggers: triggerFilter, periodMs })

  const items =
    state.kind === 'success'
      ? state.items.filter(
          (e) =>
            !skuSearch ||
            e.articleId.toLowerCase().includes(skuSearch.toLowerCase()) ||
            e.skuName.toLowerCase().includes(skuSearch.toLowerCase()),
        )
      : []

  function toggleTrigger(tr: PriceChangeEntry['trigger']) {
    setActiveTriggers((prev) =>
      prev.includes(tr) ? prev.filter((t) => t !== tr) : [...prev, tr],
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-foreground">Журнал изменений</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Все изменения цен алгоритмом, WB sync, ночной медианой и вручную
        </p>
      </div>

      {/* Фильтры */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        {/* Период */}
        <div className="inline-flex rounded-md border border-border overflow-hidden">
          {PERIOD_PRESETS.map((p) => (
            <button
              key={p.ms}
              type="button"
              onClick={() => setPeriodMs(p.ms)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                periodMs === p.ms
                  ? 'bg-indigo-600 text-white'
                  : 'bg-card text-muted-foreground hover:bg-muted/40'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Триггеры */}
        <div className="flex flex-wrap gap-1.5">
          {ALL_TRIGGERS.map((tr) => {
            const active = activeTriggers.length === 0 || activeTriggers.includes(tr)
            return (
              <button
                key={tr}
                type="button"
                onClick={() => toggleTrigger(tr)}
                className={`transition-opacity ${active ? 'opacity-100' : 'opacity-40'}`}
              >
                <TriggerBadge trigger={tr} />
              </button>
            )
          })}
          {activeTriggers.length > 0 && (
            <button
              type="button"
              onClick={() => setActiveTriggers([])}
              className="text-xs text-muted-foreground hover:underline px-1"
            >
              сбросить
            </button>
          )}
        </div>

        {/* Поиск по SKU */}
        <input
          type="search"
          placeholder="Поиск по артикулу или названию"
          value={skuSearch}
          onChange={(e) => setSkuSearch(e.target.value)}
          className="ml-auto w-64 px-3 py-1.5 text-sm border border-border rounded-md bg-card text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      {/* Счётчик */}
      {state.kind === 'success' && (
        <p className="text-xs text-muted-foreground mb-3">
          Найдено: {items.length} из {state.total} записей
        </p>
      )}

      {/* Контент */}
      <div className="bg-card border border-border rounded-lg px-6 py-4">
        {state.kind === 'loading' && (
          <div className="py-12 text-center text-muted-foreground text-sm animate-pulse">
            Загружаем журнал…
          </div>
        )}
        {state.kind === 'error' && (
          <div className="py-12 text-center text-red-600 text-sm">{state.message}</div>
        )}
        {state.kind === 'success' && (
          <ChangelogTable items={items} showSku onSkuClick={onOpenSku} />
        )}
      </div>
    </div>
  )
}
