import { useEffect, useState } from 'react'
import { formatRub } from '../../lib/formatRub'

interface Candidate {
  articleId: string
  name: string
  currentPriceKopecks: number
  basketsLast7d: number
  basketNorm: number
  daysSinceLastSale: number
  recommendedPriceKopecks: number
}

interface ActiveItem {
  articleId: string
  name: string
  startPriceKopecks: number
  currentPriceKopecks: number
  targetPriceKopecks: number
  startedAt: string
  nextStepAt: string
  stepPct: number
  requiresNegativeMarginConfirm: boolean
}

interface LiquidationData {
  candidates: Candidate[]
  active: ActiveItem[]
  history: unknown[]
}

type Tab = 'candidates' | 'active' | 'history'

function ProgressBar({ start, current, target }: { start: number; current: number; target: number }) {
  const range = start - target
  const done = start - current
  const pct = range > 0 ? Math.round((done / range) * 100) : 100
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-muted-foreground/70 w-20 text-right font-mono">{formatRub(start)}</span>
      <div className="flex-1 bg-muted rounded-full h-2 relative">
        <div
          className="bg-red-400 h-2 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-card border-2 border-red-500 rounded-full shadow"
          style={{ left: `calc(${pct}% - 6px)` }}
          title={`Текущая: ${formatRub(current)}`}
        />
      </div>
      <span className="text-xs text-muted-foreground/70 w-20 font-mono">{formatRub(target)}</span>
    </div>
  )
}

export function LiquidationPage({ onOpenCard }: { onOpenCard: (articleId: string) => void }) {
  const [data, setData] = useState<LiquidationData | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('candidates')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmModal, setConfirmModal] = useState(false)
  const [autoApproveNegative, setAutoApproveNegative] = useState(true)
  const [stopModal, setStopModal] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/wb-repricer/liquidation', { signal: controller.signal })
      .then((r) => r.json())
      .then((d: LiquidationData) => {
        setData(d)
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        showToast('Ошибка загрузки данных ликвидации')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  async function startLiquidation() {
    setConfirmModal(false)
    try {
      await fetch('/api/v1/wb-repricer/liquidation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ articleIds: Array.from(selected) }),
      })
      showToast(`Ликвидация запущена для ${selected.size} артикулов`)
      setSelected(new Set())
      // Reload
      const res = await fetch('/api/v1/wb-repricer/liquidation')
      setData(await res.json())
    } catch {
      showToast('Ошибка: не удалось запустить ликвидацию')
    }
  }

  async function stopLiquidation(articleId: string) {
    setStopModal(null)
    try {
      await fetch(`/api/v1/wb-repricer/liquidation/${articleId}/stop`, { method: 'POST' })
      showToast(`Ликвидация остановлена · ${articleId}`)
      const res = await fetch('/api/v1/wb-repricer/liquidation')
      setData(await res.json())
    } catch {
      showToast('Ошибка: не удалось остановить ликвидацию')
    }
  }

  async function confirmNegative(articleId: string) {
    try {
      await fetch(`/api/v1/wb-repricer/liquidation/${articleId}/confirm-negative`, { method: 'POST' })
      showToast(`Отрицательная маржа подтверждена на 24ч · ${articleId}`)
      const res = await fetch('/api/v1/wb-repricer/liquidation')
      setData(await res.json())
    } catch {
      showToast('Ошибка: не удалось подтвердить отрицательную маржу')
    }
  }

  if (loading || !data) {
    return (
      <div className="p-6 space-y-3 animate-pulse">
        <div className="h-10 rounded-lg bg-muted w-1/2" />
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-14 rounded-lg bg-muted" />
        ))}
      </div>
    )
  }

  const tabCounts = {
    candidates: data.candidates.length,
    active: data.active.length,
    history: (data.history as unknown[]).length,
  }

  return (
    <div className="flex flex-col h-full">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-foreground text-background text-sm px-4 py-2 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      {/* Stop modal */}
      {stopModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg shadow-lg max-w-sm w-full">
            <div className="px-5 py-4 border-b border-border font-semibold text-foreground">
              Остановить ликвидацию?
            </div>
            <div className="px-5 py-3 text-sm text-muted-foreground">
              Алгоритм прекратит снижение. Цена вернётся к P_min артикула.
            </div>
            <div className="px-5 py-3 border-t border-border flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setStopModal(null)}
                className="px-4 py-2 border border-border text-foreground rounded text-sm hover:bg-muted/40"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={() => stopLiquidation(stopModal)}
                className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 font-medium"
              >
                Остановить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm start modal */}
      {confirmModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg shadow-lg max-w-md w-full">
            <div className="px-6 py-4 border-b border-border">
              <div className="font-semibold text-foreground">Запустить ликвидацию?</div>
            </div>
            <div className="px-6 py-4 text-sm text-muted-foreground space-y-2">
              <p>
                Выбрано <strong>{selected.size} артикула</strong>. Алгоритм будет ступенчато
                снижать цену до рекомендуемой цены ликвидации.
              </p>
              <div className="bg-muted/40 rounded p-3 space-y-1">
                {data.candidates
                  .filter((c) => selected.has(c.articleId))
                  .map((c) => (
                    <div key={c.articleId} className="flex items-center justify-between text-xs">
                      <span className="font-mono text-primary">{c.articleId}</span>
                      <span className="text-muted-foreground">
                        {formatRub(c.currentPriceKopecks)} → {formatRub(c.recommendedPriceKopecks)}
                      </span>
                    </div>
                  ))}
              </div>
              <label className="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoApproveNegative}
                  onChange={(e) => setAutoApproveNegative(e.target.checked)}
                  className="mt-0.5"
                />
                <span className="text-sm text-foreground">
                  Разрешить снижение ниже P_min автоматически
                  <span className="block text-xs text-muted-foreground/70 mt-0.5">
                    Снятие галочки: алгоритм остановится на P_min и запросит подтверждение
                  </span>
                </span>
              </label>
            </div>
            <div className="px-6 py-4 border-t border-border flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmModal(false)}
                className="px-4 py-2 border border-border text-foreground rounded text-sm hover:bg-muted/40"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={startLiquidation}
                className="px-4 py-2 bg-red-500 text-white rounded text-sm hover:bg-red-600 font-medium"
              >
                Запустить ликвидацию
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Heading + Tabs */}
      <div className="px-6 pt-4 bg-card border-b border-border">
        <h1 className="text-xl font-semibold text-foreground mb-1">Ликвидация товаров</h1>
        <p className="text-sm text-muted-foreground mb-3">
          Управляемое снижение цены до точки продаж для застоявшихся SKU
        </p>
      </div>
      <div className="px-6 pt-4 bg-card border-b border-border flex items-end gap-0" role="tablist" aria-label="Этапы ликвидации">
        {(['candidates', 'active', 'history'] as Tab[]).map((t) => {
          const labels: Record<Tab, string> = {
            candidates: 'Кандидаты',
            active: 'В процессе',
            history: 'Завершена',
          }
          return (
            <button
              key={t}
              type="button"
              role="tab"
              aria-selected={tab === t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm border-b-2 transition-colors ${
                tab === t
                  ? 'border-primary text-primary font-medium'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {labels[t]}
              {tabCounts[t] > 0 && (
                <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${
                  tab === t ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'
                }`}>
                  {tabCounts[t]}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto p-6">
        {/* ── Кандидаты ── */}
        {tab === 'candidates' && (
          <>
            {data.candidates.length === 0 ? (
              <div className="text-center py-12 text-sm text-muted-foreground/70">
                Кандидатов на ликвидацию нет. Алгоритм ищет артикулы с низким спросом каждый цикл.
              </div>
            ) : (
              <>
                <div className="mb-4 text-sm text-muted-foreground">
                  Алгоритм выявил {data.candidates.length} артикулов с застойным спросом. Выберите
                  нужные и запустите ликвидацию.
                </div>
                <table className="w-full text-left border-collapse bg-card rounded-lg border border-border overflow-hidden">
                  <thead className="bg-muted/40">
                    <tr className="border-b border-border">
                      <th className="px-4 py-2 w-8">
                        <input
                          type="checkbox"
                          checked={selected.size === data.candidates.length && data.candidates.length > 0}
                          onChange={() =>
                            setSelected(
                              selected.size === data.candidates.length
                                ? new Set()
                                : new Set(data.candidates.map((c) => c.articleId)),
                            )
                          }
                          className="rounded"
                        />
                      </th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Артикул</th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Название</th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Дней без продаж</th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Корзины</th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Тек. цена</th>
                      <th className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Рек. цена ликвид.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.candidates.map((c) => (
                      <tr key={c.articleId} className={`border-b border-border/60 ${selected.has(c.articleId) ? 'bg-red-500/10' : 'hover:bg-muted/40'}`}>
                        <td className="px-4 py-2.5">
                          <input
                            type="checkbox"
                            checked={selected.has(c.articleId)}
                            onChange={() =>
                              setSelected((prev) => {
                                const next = new Set(prev)
                                next.has(c.articleId) ? next.delete(c.articleId) : next.add(c.articleId)
                                return next
                              })
                            }
                            className="rounded"
                          />
                        </td>
                        <td className="px-3 py-2.5">
                          <button
                            type="button"
                            onClick={() => onOpenCard(c.articleId)}
                            className="font-mono text-sm text-primary hover:underline font-semibold"
                          >
                            {c.articleId}
                          </button>
                        </td>
                        <td className="px-3 py-2.5 text-sm text-foreground max-w-xs truncate">{c.name}</td>
                        <td className="px-3 py-2.5 text-right">
                          <span className={`text-sm font-semibold font-mono ${c.daysSinceLastSale > 21 ? 'text-red-600' : 'text-amber-600'}`}>
                            {c.daysSinceLastSale}
                          </span>
                        </td>
                        <td className="px-3 py-2.5 text-right text-sm font-mono text-red-500">
                          {c.basketsLast7d}/{c.basketNorm}
                        </td>
                        <td className="px-3 py-2.5 text-right text-sm font-mono font-semibold">
                          {formatRub(c.currentPriceKopecks)}
                        </td>
                        <td className="px-3 py-2.5 text-right text-sm font-mono text-red-600 font-semibold">
                          → {formatRub(c.recommendedPriceKopecks)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {selected.size > 0 && (
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Выбрано: {selected.size}</span>
                    <button
                      type="button"
                      onClick={() => setConfirmModal(true)}
                      className="px-5 py-2 bg-red-500 text-white rounded font-medium text-sm hover:bg-red-600"
                    >
                      Начать ликвидацию ({selected.size}) →
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ── В процессе ── */}
        {tab === 'active' && (
          <>
            {data.active.length === 0 ? (
              <div className="text-center py-12 text-sm text-muted-foreground/70">
                Нет активных ликвидаций. Перейдите на вкладку «Кандидаты» чтобы запустить.
              </div>
            ) : (
              <div className="space-y-4 max-w-2xl">
                {data.active.map((item) => {
                  const daysRunning = Math.round(
                    (Date.now() - new Date(item.startedAt).getTime()) / 86400000,
                  )
                  const hoursUntilNext = Math.round(
                    (new Date(item.nextStepAt).getTime() - Date.now()) / 3600000,
                  )
                  return (
                    <div
                      key={item.articleId}
                      className={`bg-card rounded-lg border p-5 ${item.requiresNegativeMarginConfirm ? 'border-amber-300' : 'border-border'}`}
                    >
                      {item.requiresNegativeMarginConfirm && (
                        <div className="mb-3 p-3 bg-amber-500/10 border border-amber-500/30 rounded text-sm text-amber-700 dark:text-amber-300 flex items-start gap-2">
                          <span className="text-base flex-shrink-0">⚠️</span>
                          <div>
                            <div className="font-semibold">Достигнут P_min — продолжить?</div>
                            <div className="text-xs mt-0.5">
                              Дальнейшее снижение будет ниже себестоимости.
                            </div>
                            <div className="mt-2 flex gap-2">
                              <button
                                type="button"
                                onClick={() => confirmNegative(item.articleId)}
                                className="px-3 py-1 bg-amber-600 text-white text-xs rounded hover:bg-amber-700"
                              >
                                Разрешить продолжить
                              </button>
                              <button
                                type="button"
                                onClick={() => setStopModal(item.articleId)}
                                className="px-3 py-1 border border-border text-muted-foreground text-xs rounded hover:bg-muted/40"
                              >
                                Остановить
                              </button>
                            </div>
                          </div>
                        </div>
                      )}

                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <button
                            type="button"
                            onClick={() => onOpenCard(item.articleId)}
                            className="font-mono text-sm text-primary hover:underline font-semibold"
                          >
                            {item.articleId}
                          </button>
                          <div className="text-sm text-foreground mt-0.5">{item.name}</div>
                          <div className="text-xs text-muted-foreground/70 mt-0.5">
                            Запущена {daysRunning} дн. назад · Текущая: {formatRub(item.currentPriceKopecks)} · Следующий шаг через {hoursUntilNext}ч (−{item.stepPct}%)
                          </div>
                        </div>
                        {!item.requiresNegativeMarginConfirm && (
                          <button
                            type="button"
                            onClick={() => setStopModal(item.articleId)}
                            className="text-xs px-3 py-1.5 border border-border text-muted-foreground rounded hover:bg-muted/40 flex-shrink-0"
                          >
                            Остановить
                          </button>
                        )}
                      </div>

                      <ProgressBar
                        start={item.startPriceKopecks}
                        current={item.currentPriceKopecks}
                        target={item.targetPriceKopecks}
                      />
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}

        {/* ── История ── */}
        {tab === 'history' && (
          <div className="text-center py-12 text-sm text-muted-foreground/70">
            История завершённых ликвидаций пуста — данные появятся после первых распродаж.
          </div>
        )}
      </div>
    </div>
  )
}
