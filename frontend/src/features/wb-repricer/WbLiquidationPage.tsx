import { useMemo, useState } from 'react'
import {
  Bell,
  Check,
  Columns3,
  Download,
  ExternalLink,
  Search,
  X,
} from 'lucide-react'
import { formatRub } from '../../lib/formatRub'
import '../../components/vella/VellaFoundation.css'
import { computePMinKopecks, marginStatusAt } from './pricing'
import { SKU_LIST } from './skuListFixtures'
import type { SkuSettingsResponse } from './schemas'

export interface LiquidationCandidate {
  articleId: string
  name: string
  currentPriceKopecks: number
  recommendedPriceKopecks: number
  pMinKopecks: number
  basketsLast7d: number
  basketNorm: number
  daysSinceLastSale: number
  marginStatus: 'negative' | 'thin' | 'ok'
  stockUnits: number
  stockValueKopecks: number
  reason: 'negative_margin' | 'low_baskets' | 'slow_stock'
}

export interface ActiveLiquidation {
  id: string
  articleId: string
  name: string
  startPriceKopecks: number
  currentPriceKopecks: number
  targetPriceKopecks: number
  pMinKopecks: number
  startedAt: string
  nextStepAt: string
  stepPct: number
  requiresNegativeMarginConfirm: boolean
  negativeMarginConfirmed: boolean
}

export interface LiquidationHistoryItem {
  id: string
  articleId: string
  title: string
  status: 'started' | 'stopped' | 'confirmed_negative' | 'completed'
  createdAt: string
  meta: string
}

export interface LiquidationData {
  candidates: LiquidationCandidate[]
  active: ActiveLiquidation[]
  history: LiquidationHistoryItem[]
}

type Tab = 'candidates' | 'active' | 'history'
type ColumnKey = 'selected' | 'sku' | 'reason' | 'baskets' | 'stock' | 'price' | 'target' | 'pmin'

const BASE_NOW = new Date('2026-05-08T12:00:00.000+05:00').getTime()

const columns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'selected', label: '' },
  { key: 'sku', label: 'SKU' },
  { key: 'reason', label: 'Причина' },
  { key: 'baskets', label: 'Корзины' },
  { key: 'stock', label: 'Остаток' },
  { key: 'price', label: 'Цена' },
  { key: 'target', label: 'Цель' },
  { key: 'pmin', label: 'P_min' },
]

function isoOffset(days: number, hours = 0) {
  return new Date(BASE_NOW + days * 86_400_000 + hours * 3_600_000).toISOString()
}

function pMin(row: SkuSettingsResponse, minMarginPct = row.settings.minMarginPct) {
  return computePMinKopecks(
    row.settings.cogsKopecks,
    row.settings.wbCommissionPct,
    row.settings.logisticsKopecks,
    minMarginPct,
  )
}

function marginStatus(row: SkuSettingsResponse) {
  return marginStatusAt(
    row.meta.currentPriceKopecks,
    row.settings.cogsKopecks,
    row.settings.wbCommissionPct,
    row.settings.logisticsKopecks,
  )
}

function buildCandidate(row: SkuSettingsResponse, index: number): LiquidationCandidate {
  const status = marginStatus(row)
  const lowBaskets = row.meta.basketsLast7d < row.meta.basketNorm * 0.25
  const pMinKopecks = pMin(row)
  const recommendedPriceKopecks = Math.round(pMin(row, 0) * (status === 'negative' ? 0.88 : 0.95))
  const stockUnits = row.analytics?.wbStockUnits ?? 24 + index * 7
  return {
    articleId: row.meta.articleId,
    name: row.meta.name,
    currentPriceKopecks: row.meta.currentPriceKopecks,
    recommendedPriceKopecks,
    pMinKopecks,
    basketsLast7d: row.meta.basketsLast7d,
    basketNorm: row.meta.basketNorm,
    daysSinceLastSale: 9 + (index * 5) % 31,
    marginStatus: status,
    stockUnits,
    stockValueKopecks: stockUnits * row.meta.currentPriceKopecks,
    reason: status === 'negative' ? 'negative_margin' : lowBaskets ? 'low_baskets' : 'slow_stock',
  }
}

function createInitialData(): LiquidationData {
  const candidates = SKU_LIST
    .filter((row) => marginStatus(row) === 'negative' || row.meta.basketsLast7d < row.meta.basketNorm * 0.25 || row.meta.status === 'manual')
    .slice(0, 12)
    .map(buildCandidate)

  const active: ActiveLiquidation[] = [
    {
      id: 'liq-active-FBBT_55',
      articleId: 'FBBT_55',
      name: 'Футболка белая «Принт 55»',
      startPriceKopecks: 165000,
      currentPriceKopecks: 125000,
      targetPriceKopecks: 70000,
      pMinKopecks: 83334,
      startedAt: isoOffset(-3),
      nextStepAt: isoOffset(0, 10),
      stepPct: 5,
      requiresNegativeMarginConfirm: false,
      negativeMarginConfirmed: false,
    },
    {
      id: 'liq-active-HCBT_19',
      articleId: 'HCBT_19',
      name: 'Худи чёрное «Принт 19»',
      startPriceKopecks: 285000,
      currentPriceKopecks: 155000,
      targetPriceKopecks: 145000,
      pMinKopecks: 153334,
      startedAt: isoOffset(-5),
      nextStepAt: isoOffset(0, 2),
      stepPct: 5,
      requiresNegativeMarginConfirm: true,
      negativeMarginConfirmed: false,
    },
  ]

  return {
    candidates,
    active,
    history: [
      {
        id: 'hist-seed',
        articleId: 'LBBT_03',
        title: 'Кандидат добавлен в аудит',
        status: 'started',
        createdAt: isoOffset(-1),
        meta: 'Маржа ниже нуля, требуется решение по ликвидации.',
      },
    ],
  }
}

function reasonLabel(reason: LiquidationCandidate['reason']) {
  if (reason === 'negative_margin') return 'отрицательная маржа'
  if (reason === 'low_baskets') return 'низкие корзины'
  return 'зависший остаток'
}

function progressPct(item: ActiveLiquidation) {
  const range = item.startPriceKopecks - item.targetPriceKopecks
  if (range <= 0) return 100
  return Math.max(0, Math.min(100, Math.round((item.startPriceKopecks - item.currentPriceKopecks) / range * 100)))
}

export function WbLiquidationPage() {
  const [data, setData] = useState<LiquidationData>(() => createInitialData())
  const [tab, setTab] = useState<Tab>('candidates')
  const [query, setQuery] = useState('')
  const [onlyLoss, setOnlyLoss] = useState(false)
  const [onlyLowBaskets, setOnlyLowBaskets] = useState(false)
  const [selectedOnly, setSelectedOnly] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [hiddenColumns, setHiddenColumns] = useState<Set<ColumnKey>>(() => new Set())
  const [sortKey, setSortKey] = useState<ColumnKey>('stock')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [popover, setPopover] = useState<'columns' | 'notifications' | null>(null)
  const [drawerCandidate, setDrawerCandidate] = useState<LiquidationCandidate | null>(null)
  const [drawerActive, setDrawerActive] = useState<ActiveLiquidation | null>(null)
  const [modal, setModal] = useState<'start' | 'stop' | 'negative' | 'export' | null>(null)
  const [targetArticleId, setTargetArticleId] = useState<string | null>(null)
  const [allowNegative, setAllowNegative] = useState(true)
  const [toast, setToast] = useState<string | null>(null)

  const visibleColumns = columns.filter((column) => !hiddenColumns.has(column.key))
  const filteredCandidates = useMemo(() => {
    const q = query.trim().toLowerCase()
    return [...data.candidates]
      .filter((candidate) => !q || `${candidate.articleId} ${candidate.name} ${candidate.reason}`.toLowerCase().includes(q))
      .filter((candidate) => !onlyLoss || candidate.marginStatus === 'negative')
      .filter((candidate) => !onlyLowBaskets || candidate.basketsLast7d < candidate.basketNorm * 0.25)
      .filter((candidate) => !selectedOnly || selected.has(candidate.articleId))
      .sort((a, b) => {
        const values: Record<ColumnKey, [number | string, number | string]> = {
          selected: [Number(selected.has(a.articleId)), Number(selected.has(b.articleId))],
          sku: [a.articleId, b.articleId],
          reason: [a.reason, b.reason],
          baskets: [a.basketsLast7d / Math.max(a.basketNorm, 1), b.basketsLast7d / Math.max(b.basketNorm, 1)],
          stock: [a.stockValueKopecks, b.stockValueKopecks],
          price: [a.currentPriceKopecks, b.currentPriceKopecks],
          target: [a.recommendedPriceKopecks, b.recommendedPriceKopecks],
          pmin: [a.pMinKopecks, b.pMinKopecks],
        }
        const [left, right] = values[sortKey]
        const result = typeof left === 'string' ? left.localeCompare(String(right), 'ru') : left - Number(right)
        return sortDirection === 'asc' ? result : -result
      })
  }, [data.candidates, onlyLoss, onlyLowBaskets, query, selected, selectedOnly, sortDirection, sortKey])

  const stats = useMemo(() => {
    const selectedValue = data.candidates
      .filter((candidate) => selected.has(candidate.articleId))
      .reduce((sum, candidate) => sum + candidate.stockValueKopecks, 0)
    return {
      candidates: data.candidates.length,
      active: data.active.length,
      confirm: data.active.filter((item) => item.requiresNegativeMarginConfirm && !item.negativeMarginConfirmed).length,
      stockValue: data.candidates.reduce((sum, candidate) => sum + candidate.stockValueKopecks, 0),
      selectedValue,
    }
  }, [data.active, data.candidates, selected])

  function pushToast(text: string) {
    setToast(text)
    window.setTimeout(() => setToast(null), 2400)
  }

  function toggleSort(column: ColumnKey) {
    if (sortKey === column) {
      setSortDirection((current) => current === 'desc' ? 'asc' : 'desc')
      return
    }
    setSortKey(column)
    setSortDirection('desc')
  }

  function startSelected() {
    const picked = data.candidates.filter((candidate) => selected.has(candidate.articleId))
    const nextActive = picked.map((candidate): ActiveLiquidation => ({
      id: `liq-${candidate.articleId}-${Date.now()}`,
      articleId: candidate.articleId,
      name: candidate.name,
      startPriceKopecks: candidate.currentPriceKopecks,
      currentPriceKopecks: candidate.currentPriceKopecks,
      targetPriceKopecks: candidate.recommendedPriceKopecks,
      pMinKopecks: candidate.pMinKopecks,
      startedAt: new Date().toISOString(),
      nextStepAt: new Date(Date.now() + 24 * 3_600_000).toISOString(),
      stepPct: 5,
      requiresNegativeMarginConfirm: candidate.recommendedPriceKopecks < candidate.pMinKopecks && !allowNegative,
      negativeMarginConfirmed: allowNegative && candidate.recommendedPriceKopecks < candidate.pMinKopecks,
    }))
    setData((current) => ({
      candidates: current.candidates.filter((candidate) => !selected.has(candidate.articleId)),
      active: [...nextActive, ...current.active],
      history: [
        ...picked.map((candidate) => ({
          id: `hist-start-${candidate.articleId}-${Date.now()}`,
          articleId: candidate.articleId,
          title: 'Ликвидация запущена',
          status: 'started' as const,
          createdAt: new Date().toISOString(),
          meta: `${formatRub(candidate.currentPriceKopecks)} → ${formatRub(candidate.recommendedPriceKopecks)}${allowNegative ? ' · убыток разрешен' : ''}`,
        })),
        ...current.history,
      ],
    }))
    setSelected(new Set())
    setModal(null)
    setTab('active')
    pushToast(`Ликвидация запущена для ${picked.length} SKU`)
  }

  function stopActive(articleId: string) {
    const item = data.active.find((active) => active.articleId === articleId)
    if (!item) return
    setData((current) => ({
      ...current,
      active: current.active.filter((active) => active.articleId !== articleId),
      history: [{
        id: `hist-stop-${articleId}-${Date.now()}`,
        articleId,
        title: 'Ликвидация остановлена',
        status: 'stopped',
        createdAt: new Date().toISOString(),
        meta: `Цена зафиксирована на ${formatRub(item.currentPriceKopecks)}; следующий шаг отменен.`,
      }, ...current.history],
    }))
    setDrawerActive(null)
    setTargetArticleId(null)
    setModal(null)
    setTab('history')
    pushToast(`Ликвидация остановлена · ${articleId}`)
  }

  function confirmNegative(articleId: string) {
    setData((current) => ({
      ...current,
      active: current.active.map((item) => item.articleId === articleId ? {
        ...item,
        requiresNegativeMarginConfirm: false,
        negativeMarginConfirmed: true,
      } : item),
      history: [{
        id: `hist-confirm-${articleId}-${Date.now()}`,
        articleId,
        title: 'Отрицательная маржа подтверждена',
        status: 'confirmed_negative',
        createdAt: new Date().toISOString(),
        meta: 'Разрешение действует 24 часа в mock-state.',
      }, ...current.history],
    }))
    setModal(null)
    pushToast(`Отрицательная маржа подтверждена · ${articleId}`)
  }

  function renderCandidateCell(candidate: LiquidationCandidate, column: ColumnKey) {
    if (column === 'selected') {
      return (
        <input
          aria-label={`Выбрать ${candidate.articleId}`}
          type="checkbox"
          checked={selected.has(candidate.articleId)}
          onChange={() => setSelected((current) => {
            const next = new Set(current)
            if (next.has(candidate.articleId)) next.delete(candidate.articleId)
            else next.add(candidate.articleId)
            return next
          })}
        />
      )
    }
    if (column === 'sku') {
      return (
        <div>
          <div className="vella-mono">{candidate.articleId}</div>
          <div className="vella-muted">{candidate.name}</div>
        </div>
      )
    }
    if (column === 'reason') return <span className={`vella-badge ${candidate.reason === 'negative_margin' ? 'bad' : 'warn'}`}>{reasonLabel(candidate.reason)}</span>
    if (column === 'baskets') return `${candidate.basketsLast7d} / ${candidate.basketNorm}`
    if (column === 'stock') return `${candidate.stockUnits} шт · ${formatRub(candidate.stockValueKopecks)}`
    if (column === 'price') return formatRub(candidate.currentPriceKopecks)
    if (column === 'target') return <span className={candidate.recommendedPriceKopecks < candidate.pMinKopecks ? 'metric-down' : ''}>{formatRub(candidate.recommendedPriceKopecks)}</span>
    return formatRub(candidate.pMinKopecks)
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <div className="vella-brand-mark">S</div>
            <div>
              <div className="vella-brand-name">Satorna</div>
              <div className="vella-brand-sub">Liquidation</div>
            </div>
          </div>
          <div className="vella-nav-group">
            <div className="vella-nav-label">Ликвидация</div>
            {[
              ['Кандидаты', 'candidates'],
              ['В процессе', 'active'],
              ['История', 'history'],
            ].map(([label, value]) => (
              <button className={`vella-nav-button ${tab === value ? 'active' : ''}`} key={value} type="button" onClick={() => setTab(value as Tab)}>
                <span className="vella-nav-dot" />
                {label}
              </button>
            ))}
          </div>
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> <b>Ликвидация</b></div>
            <div className="vella-top-actions">
              <div className="vella-position">
                <button className="vella-icon-button" type="button" aria-label="Уведомления" onClick={() => setPopover(popover === 'notifications' ? null : 'notifications')}>
                  <Bell size={16} />
                </button>
                {popover === 'notifications' && (
                  <div className="vella-popover">
                    <button className="vella-popover-row" type="button" onClick={() => setTab('active')}>Требуют подтверждения: {stats.confirm}</button>
                    <button className="vella-popover-row" type="button" onClick={() => setOnlyLoss(true)}>Loss candidates: {data.candidates.filter((item) => item.marginStatus === 'negative').length}</button>
                  </div>
                )}
              </div>
              <button className="vella-button primary" type="button" onClick={() => setModal('export')}>
                <Download size={16} /> Экспорт
              </button>
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-report-head">
              <div>
                <h1>Ликвидация товаров</h1>
                <p>Плавное снижение цены для зависших SKU. Все write-actions здесь mock-only, но меняют видимое состояние и audit/history.</p>
              </div>
              {selected.size > 0 && <button className="vella-button primary" type="button" onClick={() => setModal('start')}>Начать ликвидацию ({selected.size})</button>}
            </div>

            <div className="vella-kpis">
              <div className="vella-kpi"><div className="vella-kpi-label">Кандидаты</div><div className="vella-kpi-value">{stats.candidates}</div><div className="vella-kpi-delta">{filteredCandidates.length} в фильтре</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">В процессе</div><div className="vella-kpi-value">{stats.active}</div><div className="vella-kpi-delta good">живой mock-state</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Требуют confirm</div><div className="vella-kpi-value">{stats.confirm}</div><div className="vella-kpi-delta warn">ниже P_min</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Остаток кандидатов</div><div className="vella-kpi-value">{formatRub(stats.stockValue)}</div><div className="vella-kpi-delta">{selected.size ? `выбрано ${formatRub(stats.selectedValue)}` : 'не выбрано'}</div></div>
            </div>

            <div className="vella-tabs">
              {[
                ['candidates', 'Кандидаты'],
                ['active', 'В процессе'],
                ['history', 'История'],
              ].map(([value, label]) => (
                <button className={`vella-tab ${tab === value ? 'active' : ''}`} key={value} type="button" onClick={() => setTab(value as Tab)}>{label}</button>
              ))}
            </div>

            {tab === 'candidates' && (
              <>
                <div className="vella-toolbar">
                  <div className="vella-toolbar-left">
                    <div className="vella-search-wrap">
                      <Search size={15} />
                      <input className="vella-search" placeholder="Поиск SKU или причины" value={query} onChange={(event) => setQuery(event.target.value)} />
                    </div>
                    <button className={`vella-chip ${onlyLoss ? 'active' : ''}`} type="button" onClick={() => setOnlyLoss((value) => !value)}>Только loss</button>
                    <button className={`vella-chip ${onlyLowBaskets ? 'active' : ''}`} type="button" onClick={() => setOnlyLowBaskets((value) => !value)}>Низкие корзины</button>
                    <button className={`vella-chip ${selectedOnly ? 'active' : ''}`} type="button" onClick={() => setSelectedOnly((value) => !value)}>Выбранные</button>
                  </div>
                  <div className="vella-toolbar-right">
                    <button className="vella-button" type="button" onClick={() => {
                      const allVisible = filteredCandidates.every((candidate) => selected.has(candidate.articleId))
                      setSelected((current) => {
                        const next = new Set(current)
                        for (const candidate of filteredCandidates) {
                          if (allVisible) next.delete(candidate.articleId)
                          else next.add(candidate.articleId)
                        }
                        return next
                      })
                    }}>Выбрать видимые</button>
                    <div className="vella-position">
                      <button className="vella-button" type="button" onClick={() => setPopover(popover === 'columns' ? null : 'columns')}>
                        <Columns3 size={16} /> Колонки
                      </button>
                      {popover === 'columns' && (
                        <div className="vella-popover">
                          {columns.filter((column) => column.key !== 'selected').map((column) => (
                            <button className="vella-popover-row" key={column.key} type="button" onClick={() => {
                              setHiddenColumns((current) => {
                                const next = new Set(current)
                                if (next.has(column.key)) next.delete(column.key)
                                else next.add(column.key)
                                return next
                              })
                            }}>
                              <Check size={14} opacity={hiddenColumns.has(column.key) ? 0.15 : 1} /> {column.label}
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
                      <thead><tr>{visibleColumns.map((column) => <th className={`${column.key === 'sku' ? 'sticky ' : ''}sortable`} key={column.key} onClick={() => column.key !== 'selected' && toggleSort(column.key)}>{column.label}{sortKey === column.key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ''}</th>)}<th>Действия</th></tr></thead>
                      <tbody>
                        {filteredCandidates.map((candidate) => (
                          <tr key={candidate.articleId}>
                            {visibleColumns.map((column) => <td className={column.key === 'sku' ? 'sticky' : ''} key={column.key}>{renderCandidateCell(candidate, column.key)}</td>)}
                            <td><button className="vella-button" type="button" onClick={() => setDrawerCandidate(candidate)}><ExternalLink size={14} /> Детали</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {filteredCandidates.length === 0 && <div className="vella-empty">Нет кандидатов под текущие фильтры.</div>}
                  </div>
                </div>
              </>
            )}

            {tab === 'active' && (
              <div className="vella-report-grid">
                {data.active.map((item) => (
                  <div className="vella-section" key={item.articleId}>
                    <div className="vella-section-title">{item.articleId} · {item.name}</div>
                    {item.requiresNegativeMarginConfirm && !item.negativeMarginConfirmed && <div className="vella-blocked-note">Достигнут P_min. Дальнейшее снижение требует подтверждения отрицательной маржи.</div>}
                    <div className="vella-price-grid">
                      <span>Старт</span><b>{formatRub(item.startPriceKopecks)}</b>
                      <span>Текущая</span><b>{formatRub(item.currentPriceKopecks)}</b>
                      <span>Цель</span><b>{formatRub(item.targetPriceKopecks)}</b>
                      <span>Следующий шаг</span><b>−{item.stepPct}%</b>
                    </div>
                    <div className="vella-liquid-progress"><i style={{ width: `${progressPct(item)}%` }} /></div>
                    <div className="vella-drawer-actions">
                      {item.requiresNegativeMarginConfirm && !item.negativeMarginConfirmed && (
                        <button className="vella-button" type="button" onClick={() => {
                          setTargetArticleId(item.articleId)
                          setModal('negative')
                        }}>Разрешить минус</button>
                      )}
                      <button className="vella-button" type="button" onClick={() => setDrawerActive(item)}>Детали</button>
                      <button className="vella-button primary" type="button" onClick={() => {
                        setTargetArticleId(item.articleId)
                        setModal('stop')
                      }}>Остановить</button>
                    </div>
                  </div>
                ))}
                {data.active.length === 0 && <div className="vella-empty">Активных ликвидаций нет.</div>}
              </div>
            )}

            {tab === 'history' && (
              <div className="vella-panel">
                <div className="vella-table-wrap">
                  <table className="vella-table">
                    <thead><tr><th>Событие</th><th>SKU</th><th>Статус</th><th>Комментарий</th><th>Время</th></tr></thead>
                    <tbody>{data.history.map((item) => <tr key={item.id}><td>{item.title}</td><td className="vella-mono">{item.articleId}</td><td><span className="vella-badge neutral">{item.status}</span></td><td>{item.meta}</td><td>{new Date(item.createdAt).toLocaleString('ru-RU')}</td></tr>)}</tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </main>
      </div>

      {(drawerCandidate || drawerActive) && (
        <>
          <div className="vella-drawer-overlay" onClick={() => {
            setDrawerCandidate(null)
            setDrawerActive(null)
          }} />
          <aside className="vella-drawer" aria-label="Детали ликвидации">
            <div className="vella-drawer-head">
              <div>
                <div className="vella-drawer-title">{drawerCandidate?.articleId ?? drawerActive?.articleId}</div>
                <div className="vella-muted">{drawerCandidate?.name ?? drawerActive?.name}</div>
              </div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => {
                setDrawerCandidate(null)
                setDrawerActive(null)
              }}><X size={16} /></button>
            </div>
            <div className="vella-drawer-body">
              {drawerCandidate && (
                <>
                  <div className="vella-section">
                    <div className="vella-section-title">Расчёт кандидата</div>
                    <div className="vella-price-grid">
                      <span>Причина</span><b>{reasonLabel(drawerCandidate.reason)}</b>
                      <span>Текущая цена</span><b>{formatRub(drawerCandidate.currentPriceKopecks)}</b>
                      <span>P_min</span><b>{formatRub(drawerCandidate.pMinKopecks)}</b>
                      <span>Цель ликвидации</span><b className={drawerCandidate.recommendedPriceKopecks < drawerCandidate.pMinKopecks ? 'metric-down' : ''}>{formatRub(drawerCandidate.recommendedPriceKopecks)}</b>
                    </div>
                  </div>
                  <button className="vella-button primary" type="button" onClick={() => {
                    setSelected((current) => new Set(current).add(drawerCandidate.articleId))
                    pushToast(`${drawerCandidate.articleId} выбран`)
                  }}>Выбрать SKU</button>
                </>
              )}
              {drawerActive && (
                <>
                  <div className="vella-section">
                    <div className="vella-section-title">Прогресс</div>
                    <div className="vella-price-grid">
                      <span>Старт</span><b>{formatRub(drawerActive.startPriceKopecks)}</b>
                      <span>Текущая</span><b>{formatRub(drawerActive.currentPriceKopecks)}</b>
                      <span>Цель</span><b>{formatRub(drawerActive.targetPriceKopecks)}</b>
                      <span>Подтверждение минуса</span><b>{drawerActive.negativeMarginConfirmed ? 'да' : 'нет'}</b>
                    </div>
                  </div>
                  <button className="vella-button primary" type="button" onClick={() => {
                    setTargetArticleId(drawerActive.articleId)
                    setModal('stop')
                  }}>Остановить</button>
                </>
              )}
            </div>
          </aside>
        </>
      )}

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true">
          <div className="vella-modal">
            <div className="vella-modal-head">
              <div className="vella-modal-title">{modal === 'start' ? 'Запустить ликвидацию' : modal === 'stop' ? 'Остановить ликвидацию' : modal === 'negative' ? 'Подтвердить отрицательную маржу' : 'Экспорт ликвидации'}</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}><X size={16} /></button>
            </div>
            <div className="vella-modal-body">
              {modal === 'start' && (
                <>
                  Выбрано {selected.size} SKU. Они перейдут во вкладку `В процессе`, а событие попадёт в историю.
                  <label className="vella-checkbox-line">
                    <input type="checkbox" checked={allowNegative} onChange={(event) => setAllowNegative(event.target.checked)} />
                    Разрешить снижение ниже P_min в этом mock-запуске
                  </label>
                </>
              )}
              {modal === 'stop' && `Остановить ${targetArticleId}? Цена останется в текущем mock-state, событие попадёт в историю.`}
              {modal === 'negative' && `Разрешить отрицательную маржу для ${targetArticleId} на 24 часа?`}
              {modal === 'export' && `Будет выгружено: кандидатов ${data.candidates.length}, активных ${data.active.length}, событий истории ${data.history.length}.`}
            </div>
            <div className="vella-modal-foot">
              <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
              <button className="vella-button primary" type="button" onClick={() => {
                if (modal === 'start') startSelected()
                else if (modal === 'stop' && targetArticleId) stopActive(targetArticleId)
                else if (modal === 'negative' && targetArticleId) confirmNegative(targetArticleId)
                else {
                  pushToast('Экспорт ликвидации поставлен в очередь')
                  setModal(null)
                }
              }}>Подтвердить</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="vella-toast-stack"><div className="vella-toast">{toast}</div></div>}
    </div>
  )
}
