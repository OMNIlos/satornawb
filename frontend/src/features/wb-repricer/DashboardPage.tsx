import { useEffect, useState } from 'react'

type View = 'dashboard' | 'sku-list' | 'sku-card' | 'templates' | 'liquidation' | 'algorithm' | 'help'

interface DashboardData {
  total: number
  counts: { auto: number; manual: number; warmup: number; liquidation: number }
  attention: { articleId: string; name: string; reason: string; detail: string }[]
  typeStats: { type: string; total: number; autoPct: number; avgMarginPct: number }[]
  lastSyncAt: string
}

const TYPE_LABELS: Record<string, string> = {
  F: 'Футболки',
  H: 'Худи',
  L: 'Лонгсливы',
}

const REASON_CONFIG: Record<string, { label: string; icon: string; color: string }> = {
  negative_margin: { label: 'Отрицательная маржа', icon: '!', color: 'text-red-600' },
  low_baskets: { label: 'Корзины ниже нормы', icon: '•', color: 'text-amber-600' },
}

function StatCard({
  value,
  label,
  sub,
  color,
  onClick,
}: {
  value: string | number
  label: string
  sub?: string
  color?: string
  onClick?: () => void
}) {
  return (
    <div
      className={`bg-card rounded-lg border border-border p-5 ${onClick ? 'cursor-pointer hover:border-indigo-300 transition-colors' : ''}`}
      onClick={onClick}
    >
      <div className={`text-3xl font-bold font-mono ${color ?? 'text-foreground'}`}>{value}</div>
      <div className="text-sm font-medium text-foreground mt-1">{label}</div>
      {sub && <div className="text-xs text-muted-foreground/70 mt-0.5">{sub}</div>}
    </div>
  )
}

export function DashboardPage({ onNavigate }: { onNavigate: (view: View, articleId?: string) => void }) {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<Date>(new Date())

  function load() {
    setLoading(true)
    setError(false)
    fetch('/api/v1/wb-repricer/dashboard')
      .then((r) => r.json())
      .then((d: DashboardData) => {
        setData(d)
        setUpdatedAt(new Date())
        setLoading(false)
      })
      .catch(() => {
        setError(true)
        setLoading(false)
      })
  }

  useEffect(() => { load() }, [])

  if (loading) {
    return (
      <div className="p-8 flex items-center gap-2 text-sm text-muted-foreground/70">
        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Загрузка дашборда…
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-8 flex flex-col items-center gap-3 text-center">
        <div className="text-sm font-medium text-red-600 dark:text-red-400">Не удалось загрузить дашборд</div>
        <div className="text-xs text-muted-foreground">Проверьте подключение к WB API</div>
        <button
          type="button"
          onClick={load}
          className="text-xs text-primary hover:underline mt-1"
        >
          Повторить
        </button>
      </div>
    )
  }

  const problemCount = data.attention.length
  const syncMinsAgo = Math.round((Date.now() - new Date(data.lastSyncAt).getTime()) / 60000)

  const groupedAttention = data.attention.reduce<Record<string, typeof data.attention>>((acc, item) => {
    acc[item.reason] = acc[item.reason] ?? []
    acc[item.reason].push(item)
    return acc
  }, {})

  return (
    <div className="p-6 max-w-5xl">
      {/* Шапка с временем */}
      <div className="flex items-center justify-between mb-5">
        <div className="text-xs text-muted-foreground/70">
          Данные на {updatedAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
        </div>
        <button
          type="button"
          onClick={load}
          className="text-xs text-indigo-600 hover:underline flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Обновить
        </button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <StatCard value={data.total} label="Артикулов в системе" sub="всего загружено" />
        <StatCard
          value={data.counts.auto}
          label="На автоматике"
          sub={`${Math.round((data.counts.auto / data.total) * 100)}% от всех`}
          color="text-emerald-600"
          onClick={() => onNavigate('sku-list')}
        />
        <StatCard
          value={problemCount || '✓'}
          label={problemCount ? 'Требуют внимания' : 'Всё в порядке'}
          sub={problemCount ? 'кликните для перехода' : 'проблем не обнаружено'}
          color={problemCount ? 'text-red-600' : 'text-emerald-600'}
          onClick={problemCount ? () => onNavigate('sku-list') : undefined}
        />
        <StatCard
          value={`${syncMinsAgo}м`}
          label="Последняя синхронизация"
          sub="с WB API"
          color={syncMinsAgo > 60 ? 'text-amber-600' : 'text-foreground'}
        />
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Распределение по статусам */}
        <div className="bg-card rounded-lg border border-border p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Статусы артикулов</h3>
          <div className="space-y-3">
            {([
              { key: 'auto', label: 'Автоматика', color: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400' },
              { key: 'manual', label: 'Ручной режим', color: 'bg-muted-foreground/60', text: 'text-muted-foreground' },
              { key: 'warmup', label: 'Прогрев', color: 'bg-blue-400', text: 'text-blue-600 dark:text-blue-400' },
              { key: 'liquidation', label: 'Ликвидация', color: 'bg-red-400', text: 'text-red-600 dark:text-red-400' },
            ] as const).map(({ key, label, color, text }) => {
              const count = data.counts[key]
              const pct = data.total > 0 ? Math.round((count / data.total) * 100) : 0
              return (
                <div key={key} className="flex items-center gap-3">
                  <div className="w-24 text-xs text-muted-foreground">{label}</div>
                  <div className="flex-1 bg-muted rounded-full h-2">
                    <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
                  </div>
                  <div className={`text-sm font-semibold w-8 text-right font-mono ${text}`}>{count}</div>
                  <div className="text-xs text-muted-foreground/70 w-8">{pct}%</div>
                </div>
              )
            })}
          </div>

          {/* По типам */}
          <h3 className="text-sm font-semibold text-foreground mt-5 mb-3">По типам товара</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted-foreground/70">
                <th className="text-left font-medium pb-1">Тип</th>
                <th className="text-right font-medium pb-1">Кол-во</th>
                <th className="text-right font-medium pb-1">Авто</th>
                <th className="text-right font-medium pb-1">Маржа</th>
              </tr>
            </thead>
            <tbody>
              {data.typeStats.map((t) => (
                <tr key={t.type} className="border-t border-border/60">
                  <td className="py-1.5 text-foreground font-medium">{TYPE_LABELS[t.type] ?? t.type}</td>
                  <td className="py-1.5 text-right font-mono">{t.total}</td>
                  <td className="py-1.5 text-right font-mono text-emerald-600">{t.autoPct}%</td>
                  <td className={`py-1.5 text-right font-mono font-semibold ${t.avgMarginPct >= 15 ? 'text-emerald-600' : t.avgMarginPct >= 10 ? 'text-amber-600' : 'text-red-600'}`}>
                    {t.avgMarginPct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Требуют внимания */}
        <div className="bg-card rounded-lg border border-border p-5">
          <h3 className="text-sm font-semibold text-foreground mb-4">Требуют внимания</h3>

          {data.attention.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 text-center">
              <div className="text-2xl mb-2">✓</div>
              <div className="text-sm font-medium text-emerald-600 dark:text-emerald-400">Все артикулы в норме</div>
              <div className="text-xs text-muted-foreground/70 mt-1">Проблем не обнаружено</div>
            </div>
          ) : (
            <div className="space-y-4">
              {Object.entries(groupedAttention).map(([reason, items]) => {
                const cfg = REASON_CONFIG[reason] ?? { label: reason, icon: '⚠️', color: 'text-muted-foreground' }
                return (
                  <div key={reason}>
                    <div className={`text-xs font-semibold uppercase tracking-wide mb-1.5 flex items-center gap-1 ${cfg.color}`}>
                      <span>{cfg.icon}</span>
                      <span>{cfg.label} ({items.length})</span>
                    </div>
                    <div className="space-y-1">
                      {items.map((item) => (
                        <button
                          key={item.articleId}
                          type="button"
                          onClick={() => onNavigate('sku-card', item.articleId)}
                          className="w-full flex items-center justify-between text-left py-1 px-2 rounded hover:bg-muted/40 group"
                        >
                          <span className="flex items-center gap-2 min-w-0">
                            <span className="font-mono text-xs text-indigo-600 font-semibold flex-shrink-0">
                              {item.articleId}
                            </span>
                            <span className="text-xs text-muted-foreground truncate">{item.name}</span>
                          </span>
                          <span className={`text-xs font-mono flex-shrink-0 ml-2 ${cfg.color}`}>
                            {item.detail}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
