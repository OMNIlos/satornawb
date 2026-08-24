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
import { CHANGELOG_ENTRIES } from './changelogFixtures'
import type { PriceChangeEntry } from './schemas'

type TriggerFilter = PriceChangeEntry['trigger'] | 'all'
type DirectionFilter = 'all' | 'up' | 'down'
type SourceFilter = PriceChangeEntry['source'] | 'all'
type ColumnKey = 'time' | 'sku' | 'oldPrice' | 'newPrice' | 'change' | 'trigger' | 'actor' | 'reason' | 'margin'

const triggerLabels: Record<PriceChangeEntry['trigger'], string> = {
  algorithm: 'Алгоритм',
  night_median_up: 'Медиана вверх',
  night_median_restore: 'Медиана возврат',
  manual: 'Вручную',
  liquidation: 'Ликвидация',
  warmup_end: 'Конец прогрева',
  wb_sync: 'WB sync',
}

const columns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'time', label: 'Время' },
  { key: 'sku', label: 'SKU' },
  { key: 'oldPrice', label: 'Было' },
  { key: 'newPrice', label: 'Стало' },
  { key: 'change', label: 'Δ%' },
  { key: 'trigger', label: 'Причина' },
  { key: 'actor', label: 'Кто' },
  { key: 'reason', label: 'Комментарий' },
  { key: 'margin', label: 'Маржа после' },
]

function formatTime(iso: string) {
  return new Date(iso).toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function triggerClass(trigger: PriceChangeEntry['trigger']) {
  if (trigger === 'liquidation') return 'bad'
  if (trigger === 'manual') return 'warn'
  if (trigger === 'warmup_end') return 'good'
  if (trigger === 'wb_sync') return 'neutral'
  return 'neutral'
}

function searchText(entry: PriceChangeEntry) {
  return `${entry.articleId} ${entry.skuName} ${entry.trigger} ${triggerLabels[entry.trigger]} ${entry.actor.name} ${entry.reason ?? ''}`.toLowerCase()
}

export function WbRepricerChangelogPage() {
  const [query, setQuery] = useState('')
  const [trigger, setTrigger] = useState<TriggerFilter>('all')
  const [direction, setDirection] = useState<DirectionFilter>('all')
  const [source, setSource] = useState<SourceFilter>('all')
  const [withReasonOnly, setWithReasonOnly] = useState(false)
  const [hiddenColumns, setHiddenColumns] = useState<Set<ColumnKey>>(() => new Set())
  const [sortKey, setSortKey] = useState<ColumnKey>('time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [popover, setPopover] = useState<'trigger' | 'columns' | 'notifications' | null>(null)
  const [drawerEntry, setDrawerEntry] = useState<PriceChangeEntry | null>(null)
  const [modal, setModal] = useState<'export' | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const visibleColumns = columns.filter((column) => !hiddenColumns.has(column.key))
  const filteredEntries = useMemo(() => {
    const q = query.trim().toLowerCase()
    return [...CHANGELOG_ENTRIES]
      .filter((entry) => !q || searchText(entry).includes(q))
      .filter((entry) => trigger === 'all' || entry.trigger === trigger)
      .filter((entry) => source === 'all' || entry.source === source)
      .filter((entry) => !withReasonOnly || Boolean(entry.reason))
      .filter((entry) => direction === 'all' || (direction === 'up' ? entry.changePct > 0 : entry.changePct < 0))
      .sort((a, b) => {
        const values: Record<ColumnKey, [number | string, number | string]> = {
          time: [new Date(a.timestamp).getTime(), new Date(b.timestamp).getTime()],
          sku: [a.articleId, b.articleId],
          oldPrice: [a.oldPriceKopecks, b.oldPriceKopecks],
          newPrice: [a.newPriceKopecks, b.newPriceKopecks],
          change: [a.changePct, b.changePct],
          trigger: [a.trigger, b.trigger],
          actor: [a.actor.name, b.actor.name],
          reason: [a.reason ?? '', b.reason ?? ''],
          margin: [a.marginAfterPct, b.marginAfterPct],
        }
        const [left, right] = values[sortKey]
        const result = typeof left === 'string' ? left.localeCompare(String(right), 'ru') : left - Number(right)
        return sortDirection === 'asc' ? result : -result
      })
  }, [direction, query, sortDirection, sortKey, source, trigger, withReasonOnly])

  const stats = useMemo(() => {
    const up = CHANGELOG_ENTRIES.filter((entry) => entry.changePct > 0).length
    const down = CHANGELOG_ENTRIES.filter((entry) => entry.changePct < 0).length
    const manual = CHANGELOG_ENTRIES.filter((entry) => entry.trigger === 'manual').length
    const liquidation = CHANGELOG_ENTRIES.filter((entry) => entry.trigger === 'liquidation').length
    const withReason = CHANGELOG_ENTRIES.filter((entry) => entry.reason).length
    return { up, down, manual, liquidation, withReason }
  }, [])

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

  function renderCell(entry: PriceChangeEntry, key: ColumnKey) {
    if (key === 'time') return formatTime(entry.timestamp)
    if (key === 'sku') {
      return (
        <div>
          <div className="vella-mono">{entry.articleId}</div>
          <div className="vella-muted">{entry.skuName}</div>
        </div>
      )
    }
    if (key === 'oldPrice') return formatRub(entry.oldPriceKopecks)
    if (key === 'newPrice') return formatRub(entry.newPriceKopecks)
    if (key === 'change') {
      return <span className={entry.changePct >= 0 ? 'metric-up' : 'metric-down'}>{entry.changePct > 0 ? '+' : ''}{entry.changePct.toFixed(1)}%</span>
    }
    if (key === 'trigger') return <span className={`vella-badge ${triggerClass(entry.trigger)}`}>{triggerLabels[entry.trigger]}</span>
    if (key === 'actor') return <span>{entry.actor.name}</span>
    if (key === 'reason') return entry.reason ? <span>{entry.reason}</span> : <span className="vella-muted">Системное событие</span>
    return <span className={entry.marginAfterPct < 10 ? 'vella-warn-text' : 'metric-up'}>{entry.marginAfterPct.toFixed(1)}%</span>
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <div className="vella-brand-mark">S</div>
            <div>
              <div className="vella-brand-name">Satorna</div>
              <div className="vella-brand-sub">Price audit</div>
            </div>
          </div>
          <div className="vella-nav-group">
            <div className="vella-nav-label">Репрайсер</div>
            {['Все товары', 'Журнал', 'Ночная медиана', 'Ручные правки', 'Ликвидация'].map((item) => (
              <button
                className={`vella-nav-button ${item === 'Журнал' ? 'active' : ''}`}
                key={item}
                type="button"
                onClick={() => {
                  if (item === 'Ночная медиана') setTrigger('night_median_up')
                  if (item === 'Ручные правки') setTrigger('manual')
                  if (item === 'Ликвидация') setTrigger('liquidation')
                  pushToast(`Фильтр: ${item}`)
                }}
              >
                <span className="vella-nav-dot" />
                {item}
              </button>
            ))}
          </div>
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> <b>Журнал изменений</b></div>
            <div className="vella-top-actions">
              <div className="vella-position">
                <button className="vella-icon-button" type="button" aria-label="Уведомления" onClick={() => setPopover(popover === 'notifications' ? null : 'notifications')}>
                  <Bell size={16} />
                </button>
                {popover === 'notifications' && (
                  <div className="vella-popover">
                    <button className="vella-popover-row" type="button" onClick={() => setTrigger('manual')}>Ручных правок: {stats.manual}</button>
                    <button className="vella-popover-row" type="button" onClick={() => setTrigger('liquidation')}>Ликвидационных шагов: {stats.liquidation}</button>
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
                <h1>Журнал изменений цен</h1>
                <p>Журнал изменений репрайсера: алгоритм, ночная медиана, ручные изменения, ликвидация и выход из прогрева.</p>
              </div>
              <button className="vella-badge neutral" type="button" onClick={() => pushToast('Журнал работает на mock-событиях до API')}>
                {filteredEntries.length} событий
              </button>
            </div>

            <div className="vella-kpis">
              <div className="vella-kpi">
                <div className="vella-kpi-label">Всего событий</div>
                <div className="vella-kpi-value">{CHANGELOG_ENTRIES.length}</div>
                <div className="vella-kpi-delta">{filteredEntries.length} в фильтре</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Повышения</div>
                <div className="vella-kpi-value">{stats.up}</div>
                <div className="vella-kpi-delta good">ночь + алгоритм</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Снижения</div>
                <div className="vella-kpi-value">{stats.down}</div>
                <div className="vella-kpi-delta warn">РНП и ликвидация</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Ручные</div>
                <div className="vella-kpi-value">{stats.manual}</div>
                <div className="vella-kpi-delta">виден человек/action</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">С причиной</div>
                <div className="vella-kpi-value">{stats.withReason}</div>
                <div className="vella-kpi-delta">ручные и bulk</div>
              </div>
            </div>

            <div className="vella-toolbar">
              <div className="vella-toolbar-left">
                <div className="vella-search-wrap">
                  <Search size={15} />
                  <input className="vella-search" placeholder="Поиск SKU, товара, причины" value={query} onChange={(event) => setQuery(event.target.value)} />
                </div>
                <div className="vella-position">
                  <button className={`vella-chip ${trigger !== 'all' ? 'active' : ''}`} type="button" onClick={() => setPopover(popover === 'trigger' ? null : 'trigger')}>
                    Причина: {trigger === 'all' ? 'Все' : triggerLabels[trigger]}
                  </button>
                  {popover === 'trigger' && (
                    <div className="vella-popover">
                      {(['all', ...Object.keys(triggerLabels)] as TriggerFilter[]).map((item) => (
                        <button className="vella-popover-row" key={item} type="button" onClick={() => {
                          setTrigger(item)
                          setPopover(null)
                        }}>
                          <Check size={14} opacity={trigger === item ? 1 : 0.15} /> {item === 'all' ? 'Все' : triggerLabels[item]}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button className={`vella-chip ${direction !== 'all' ? 'active' : ''}`} type="button" onClick={() => setDirection((value) => value === 'all' ? 'up' : value === 'up' ? 'down' : 'all')}>
                  Направление: {direction === 'all' ? 'все' : direction === 'up' ? 'рост' : 'снижение'}
                </button>
                <button className={`vella-chip ${source !== 'all' ? 'active' : ''}`} type="button" onClick={() => setSource((value) => value === 'all' ? 'manager' : value === 'manager' ? 'bulk' : value === 'bulk' ? 'system' : 'all')}>
                  Источник: {source === 'all' ? 'все' : source === 'manager' ? 'менеджер' : source === 'bulk' ? 'bulk' : 'система'}
                </button>
                <button className={`vella-chip ${withReasonOnly ? 'active' : ''}`} type="button" onClick={() => setWithReasonOnly((value) => !value)}>
                  Только с комментарием
                </button>
              </div>
              <div className="vella-toolbar-right">
                <div className="vella-position">
                  <button className="vella-button" type="button" onClick={() => setPopover(popover === 'columns' ? null : 'columns')}>
                    <Columns3 size={16} /> Колонки
                  </button>
                  {popover === 'columns' && (
                    <div className="vella-popover">
                      {columns.map((column) => (
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
                  <thead>
                    <tr>
                      {visibleColumns.map((column) => (
                        <th className={`${column.key === 'sku' ? 'sticky ' : ''}sortable`} key={column.key} onClick={() => toggleSort(column.key)}>
                          {column.label}{sortKey === column.key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ''}
                        </th>
                      ))}
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredEntries.map((entry) => (
                      <tr key={entry.id}>
                        {visibleColumns.map((column) => (
                          <td className={column.key === 'sku' ? 'sticky' : ''} key={column.key}>{renderCell(entry, column.key)}</td>
                        ))}
                        <td>
                          <button className="vella-button" type="button" onClick={() => setDrawerEntry(entry)}>
                            <ExternalLink size={14} /> Детали
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredEntries.length === 0 && <div className="vella-empty">Нет событий под текущие фильтры.</div>}
              </div>
            </div>
          </section>
        </main>
      </div>

      {drawerEntry && (
        <>
          <div className="vella-drawer-overlay" onClick={() => setDrawerEntry(null)} />
          <aside className="vella-drawer" aria-label="Детали события">
            <div className="vella-drawer-head">
              <div>
                <div className="vella-drawer-title">{drawerEntry.articleId}</div>
                <div className="vella-muted">{triggerLabels[drawerEntry.trigger]} · {formatTime(drawerEntry.timestamp)}</div>
              </div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setDrawerEntry(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-drawer-body">
              <div className="vella-section">
                <div className="vella-section-title">Изменение</div>
                <div className="vella-price-grid">
                  <span>Было</span><b>{formatRub(drawerEntry.oldPriceKopecks)}</b>
                  <span>Стало</span><b>{formatRub(drawerEntry.newPriceKopecks)}</b>
                  <span>Динамика</span><b className={drawerEntry.changePct >= 0 ? 'metric-up' : 'metric-down'}>{drawerEntry.changePct > 0 ? '+' : ''}{drawerEntry.changePct.toFixed(1)}%</b>
                  <span>Маржа после</span><b>{drawerEntry.marginAfterPct.toFixed(1)}%</b>
                </div>
              </div>
              <div className="vella-section">
                <div className="vella-section-title">Audit context</div>
                <div className="vella-price-grid">
                  <span>Кто инициировал</span><b>{drawerEntry.actor.name}</b>
                  <span>Источник</span><b>{drawerEntry.source === 'manager' ? 'менеджер' : drawerEntry.source === 'bulk' ? 'bulk' : 'система'}</b>
                  <span>Scope</span><b>{drawerEntry.scope === 'bulk' ? 'массовое действие' : 'SKU'}</b>
                  <span>Причина</span><b>{drawerEntry.reason ?? 'Системное событие'}</b>
                </div>
              </div>
              <button className="vella-button primary" type="button" onClick={() => pushToast(`Открыт SKU ${drawerEntry.articleId} в mock-state`)}>
                Открыть SKU
              </button>
            </div>
          </aside>
        </>
      )}

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true">
          <div className="vella-modal">
            <div className="vella-modal-head">
              <div className="vella-modal-title">Экспорт журнала</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-modal-body">
              Будет выгружено {filteredEntries.length} событий с текущими фильтрами: причина, старая цена, новая цена, динамика и маржа после изменения.
            </div>
            <div className="vella-modal-foot">
              <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
              <button className="vella-button primary" type="button" onClick={() => {
                pushToast('Экспорт журнала поставлен в очередь')
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
