import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Bell,
  CalendarDays,
  Check,
  ChevronDown,
  Columns3,
  Download,
  ExternalLink,
  Search,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import './VellaFoundation.css'

type Status = 'ok' | 'new' | 'problem'
type ColumnKey = 'brand' | 'price' | 'margin' | 'baskets' | 'stock' | 'manager'
type SortKey = 'sku' | 'price' | 'margin' | 'baskets' | 'stock'

type SkuRow = {
  id: string
  sku: string
  name: string
  brand: string
  status: Status
  abc: string
  price: number
  margin: number
  baskets: number
  stock: number
  manager: string
  comment: string
}

type Toast = {
  id: number
  text: string
}

const rows: SkuRow[] = [
  {
    id: '1',
    sku: 'FBBT_42',
    name: 'Футболка Base белая, принт 42',
    brand: 'Огни Base',
    status: 'problem',
    abc: 'A / fast',
    price: 1290,
    margin: 24,
    baskets: 38,
    stock: 44,
    manager: 'Мария',
    comment: 'Высокие корзины, маржа ниже целевой.',
  },
  {
    id: '2',
    sku: 'HCBT_18',
    name: 'Худи черное, принт 18',
    brand: 'Огни Street',
    status: 'new',
    abc: 'B / test',
    price: 3190,
    margin: 37,
    baskets: 11,
    stock: 18,
    manager: 'Антон',
    comment: 'Новинка, идет первичный сбор сигналов.',
  },
  {
    id: '3',
    sku: 'FCBT_77',
    name: 'Футболка черная, принт 77',
    brand: 'Огни Base',
    status: 'ok',
    abc: 'A / stable',
    price: 1390,
    margin: 31,
    baskets: 24,
    stock: 67,
    manager: 'Мария',
    comment: 'Цена в коридоре, остатки достаточные.',
  },
  {
    id: '4',
    sku: 'HBBT_91',
    name: 'Худи белое, принт 91',
    brand: 'Огни Street',
    status: 'problem',
    abc: 'C / slow',
    price: 2990,
    margin: 18,
    baskets: 4,
    stock: 93,
    manager: 'Ирина',
    comment: 'Кандидат на ликвидацию после проверки рекламы.',
  },
]

const columns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'brand', label: 'Бренд' },
  { key: 'price', label: 'Цена' },
  { key: 'margin', label: 'Маржа' },
  { key: 'baskets', label: 'Корзины' },
  { key: 'stock', label: 'Остаток' },
  { key: 'manager', label: 'Ответственный' },
]

const tabs = ['Мониторинг', 'ABC', 'P&L', 'Правила']
const drawerTabs = ['Обзор', 'Правила', 'Комментарии']
const navGroups: Array<{ group: string; items: string[] }> = [
  { group: 'WB', items: ['Репрайсер', 'Отчеты WB', 'Ликвидация', 'Отзывы'] },
  { group: 'Авито', items: ['Чаты', 'Объявления', 'Кошельки'] },
  { group: 'Система', items: ['Уведомления', 'Настройки'] },
]

function formatRub(value: number) {
  return new Intl.NumberFormat('ru-RU').format(value) + ' ₽'
}

function HelpTip({ children }: { children: ReactNode }) {
  return (
    <span className="vella-tooltip-wrap">
      <span className="vella-help-dot" tabIndex={0}>?</span>
      <span className="vella-tooltip">{children}</span>
    </span>
  )
}

function statusBadge(status: Status) {
  if (status === 'problem') return <span className="vella-badge bad">Проблемный SKU</span>
  if (status === 'new') return <span className="vella-badge warn">Новинка</span>
  return <span className="vella-badge good">В норме</span>
}

export function VellaFoundationWorkbench() {
  const [activeNav, setActiveNav] = useState('Отчеты WB')
  const [activeTab, setActiveTab] = useState(tabs[0])
  const [brand, setBrand] = useState('Все')
  const [onlyNew, setOnlyNew] = useState(false)
  const [onlyProblems, setOnlyProblems] = useState(false)
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; direction: 'asc' | 'desc' }>({ key: 'baskets', direction: 'desc' })
  const [visibleColumns, setVisibleColumns] = useState<Set<ColumnKey>>(() => new Set(columns.map((column) => column.key)))
  const [openPopover, setOpenPopover] = useState<'period' | 'columns' | 'notifications' | null>(null)
  const [drawerRow, setDrawerRow] = useState<SkuRow | null>(null)
  const [drawerTab, setDrawerTab] = useState(drawerTabs[0])
  const [modal, setModal] = useState<'export' | 'rule' | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastTimersRef = useRef<number[]>([])

  useEffect(() => {
    return () => {
      toastTimersRef.current.forEach((timer) => window.clearTimeout(timer))
      toastTimersRef.current = []
    }
  }, [])

  useEffect(() => {
    if (!drawerRow && !modal) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setDrawerRow(null)
      setModal(null)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [drawerRow, modal])

  const brands = useMemo(() => ['Все', ...Array.from(new Set(rows.map((row) => row.brand)))], [])
  const problemCount = rows.filter((row) => row.status === 'problem').length
  const newCount = rows.filter((row) => row.status === 'new').length

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...rows]
      .filter((row) => brand === 'Все' || row.brand === brand)
      .filter((row) => !onlyNew || row.status === 'new')
      .filter((row) => !onlyProblems || row.status === 'problem')
      .filter((row) => !query || `${row.sku} ${row.name} ${row.brand} ${row.manager}`.toLowerCase().includes(query))
      .sort((a, b) => {
        const left = a[sort.key]
        const right = b[sort.key]
        const result = typeof left === 'string' ? left.localeCompare(String(right), 'ru') : Number(left) - Number(right)
        return sort.direction === 'asc' ? result : -result
      })
  }, [brand, onlyNew, onlyProblems, search, sort])

  const kpis = useMemo(() => {
    const revenue = filteredRows.reduce((sum, row) => sum + row.price * Math.max(row.baskets, 1), 0)
    const avgMargin = Math.round(filteredRows.reduce((sum, row) => sum + row.margin, 0) / Math.max(filteredRows.length, 1))
    const baskets = filteredRows.reduce((sum, row) => sum + row.baskets, 0)
    const stock = filteredRows.reduce((sum, row) => sum + row.stock, 0)
    return [
      ['Выручка прогноза', formatRub(revenue), '+8% к прошлой неделе', 'Считается по текущему фильтру и корзинам.'],
      ['Средняя маржа', `${avgMargin}%`, avgMargin < 25 ? 'ниже цели' : 'в целевом коридоре', 'Моковый расчет маржи после комиссий и логистики.'],
      ['Корзины', String(baskets), `${problemCount} SKU требуют внимания`, 'Основной сигнал репрайсера для Огней.'],
      ['Остаток', `${stock} шт`, `${newCount} новинок`, 'Сумма остатков по видимым строкам.'],
    ]
  }, [filteredRows, newCount, problemCount])

  function pushToast(text: string) {
    const id = Date.now()
    setToasts((items) => [...items, { id, text }].slice(-3))
    const timer = window.setTimeout(() => {
      setToasts((items) => items.filter((item) => item.id !== id))
      toastTimersRef.current = toastTimersRef.current.filter((item) => item !== timer)
    }, 2800)
    toastTimersRef.current.push(timer)
  }

  function toggleColumn(key: ColumnKey) {
    setVisibleColumns((current) => {
      const next = new Set(current)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  function toggleSort(key: SortKey) {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  function sortMark(key: SortKey) {
    if (sort.key !== key) return ''
    return sort.direction === 'asc' ? ' ↑' : ' ↓'
  }

  function sortAria(key: SortKey): 'none' | 'ascending' | 'descending' {
    if (sort.key !== key) return 'none'
    return sort.direction === 'asc' ? 'ascending' : 'descending'
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <div className="vella-brand-mark">V</div>
            <div>
              <div className="vella-brand-name">Vella</div>
              <div className="vella-brand-sub">React foundation</div>
            </div>
          </div>

          {navGroups.map(({ group, items }) => (
            <div className="vella-nav-group" key={group}>
              <div className="vella-nav-label">{group}</div>
              {items.map((item) => (
                <button
                  className={`vella-nav-button ${activeNav === item ? 'active' : ''}`}
                  key={item}
                  type="button"
                  onClick={() => {
                    setActiveNav(item)
                    pushToast(`Открыт раздел: ${item}`)
                  }}
                >
                  <span className="vella-nav-dot" />
                  {item}
                </button>
              ))}
            </div>
          ))}
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">
              WB <span>/</span> <b>{activeNav}</b>
            </div>
            <div className="vella-top-actions">
              <div className="vella-position">
                <button
                  className="vella-button"
                  type="button"
                  onClick={() => setOpenPopover(openPopover === 'period' ? null : 'period')}
                >
                  <CalendarDays size={16} /> 7 дней <ChevronDown size={14} />
                </button>
                {openPopover === 'period' && (
                  <div className="vella-popover">
                    {['Сегодня', '7 дней', '30 дней', 'Текущий месяц'].map((period) => (
                      <button
                        className="vella-popover-row"
                        key={period}
                        type="button"
                        onClick={() => {
                          setOpenPopover(null)
                          pushToast(`Период изменен: ${period}`)
                        }}
                      >
                        <Check size={14} /> {period}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <div className="vella-position">
                <button
                  className="vella-icon-button"
                  type="button"
                  aria-label="Уведомления"
                  onClick={() => setOpenPopover(openPopover === 'notifications' ? null : 'notifications')}
                >
                  <Bell size={16} />
                </button>
                {openPopover === 'notifications' && (
                  <div className="vella-popover">
                    <button className="vella-popover-row" type="button" onClick={() => pushToast('Уведомление отмечено как прочитанное')}>
                      2 SKU вышли ниже минимальной маржи
                    </button>
                    <button className="vella-popover-row" type="button" onClick={() => pushToast('Открыт моковый центр уведомлений')}>
                      Ночной расчет медианы завершен
                    </button>
                  </div>
                )}
              </div>
              <button className="vella-button primary" type="button" onClick={() => setModal('export')}>
                <Download size={16} /> Экспорт
              </button>
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-tabs">
              {tabs.map((tab) => (
                <button
                  className={`vella-tab ${activeTab === tab ? 'active' : ''}`}
                  key={tab}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab)
                    pushToast(`Активна вкладка: ${tab}`)
                  }}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="vella-kpis">
              {kpis.map(([label, value, delta, tip], index) => (
                <div className="vella-kpi" key={label}>
                  <div className="vella-kpi-label">
                    {label} <HelpTip>{tip}</HelpTip>
                  </div>
                  <div className="vella-kpi-value">{value}</div>
                  <div className={`vella-kpi-delta ${index === 0 || index === 3 ? 'good' : index === 1 ? 'warn' : ''}`}>
                    {delta}
                  </div>
                </div>
              ))}
            </div>

            <div className="vella-toolbar">
              <div className="vella-toolbar-left">
                <div className="vella-search-wrap">
                  <Search size={15} />
                  <input
                    className="vella-search"
                    placeholder="Поиск по SKU, бренду, менеджеру"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                  />
                </div>
                <button
                  className={`vella-chip ${brand !== 'Все' ? 'active' : ''}`}
                  type="button"
                  onClick={() => {
                    const currentIndex = brands.indexOf(brand)
                    setBrand(brands[(currentIndex + 1) % brands.length])
                  }}
                >
                  Бренды: {brand}
                </button>
                <button className={`vella-chip ${onlyNew ? 'active' : ''}`} type="button" onClick={() => setOnlyNew((value) => !value)}>
                  Новинки <span className="vella-chip-count">{newCount}</span>
                </button>
                <button className={`vella-chip ${onlyProblems ? 'active' : ''}`} type="button" onClick={() => setOnlyProblems((value) => !value)}>
                  Проблемные SKU <span className="vella-chip-count">{problemCount}</span>
                </button>
              </div>
              <div className="vella-toolbar-right">
                <button className="vella-button" type="button" onClick={() => setModal('rule')}>
                  <SlidersHorizontal size={16} /> Правило
                </button>
                <div className="vella-position">
                  <button
                    className="vella-button"
                    type="button"
                    onClick={() => setOpenPopover(openPopover === 'columns' ? null : 'columns')}
                  >
                    <Columns3 size={16} /> Колонки
                  </button>
                  {openPopover === 'columns' && (
                    <div className="vella-popover">
                      {columns.map((column) => (
                        <button className="vella-popover-row" key={column.key} type="button" onClick={() => toggleColumn(column.key)}>
                          <Check size={14} opacity={visibleColumns.has(column.key) ? 1 : 0.15} />
                          {column.label}
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
                      <th aria-sort={sortAria('sku')} className="sticky"><button className="sortable" type="button" onClick={() => toggleSort('sku')}>SKU{sortMark('sku')}</button></th>
                      {visibleColumns.has('brand') && <th>Бренд</th>}
                      <th>Статус</th>
                      <th>ABC</th>
                      {visibleColumns.has('price') && <th aria-sort={sortAria('price')}><button className="sortable" type="button" onClick={() => toggleSort('price')}>Цена{sortMark('price')}</button></th>}
                      {visibleColumns.has('margin') && <th aria-sort={sortAria('margin')}><button className="sortable" type="button" onClick={() => toggleSort('margin')}>Маржа{sortMark('margin')}</button></th>}
                      {visibleColumns.has('baskets') && <th aria-sort={sortAria('baskets')}><button className="sortable" type="button" onClick={() => toggleSort('baskets')}>Корзины{sortMark('baskets')}</button></th>}
                      {visibleColumns.has('stock') && <th aria-sort={sortAria('stock')}><button className="sortable" type="button" onClick={() => toggleSort('stock')}>Остаток{sortMark('stock')}</button></th>}
                      {visibleColumns.has('manager') && <th>Ответственный</th>}
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredRows.map((row) => (
                      <tr key={row.id}>
                        <td className="sticky">
                          <div className="vella-sku">
                            <div className="vella-thumb">{row.sku.slice(0, 2)}</div>
                            <div>
                              <div className="vella-mono">{row.sku}</div>
                              <div className="vella-muted">{row.name}</div>
                            </div>
                          </div>
                        </td>
                        {visibleColumns.has('brand') && <td>{row.brand}</td>}
                        <td>{statusBadge(row.status)}</td>
                        <td>{row.abc}</td>
                        {visibleColumns.has('price') && <td>{formatRub(row.price)}</td>}
                        {visibleColumns.has('margin') && <td>{row.margin}%</td>}
                        {visibleColumns.has('baskets') && <td>{row.baskets}</td>}
                        {visibleColumns.has('stock') && <td>{row.stock} шт</td>}
                        {visibleColumns.has('manager') && <td>{row.manager}</td>}
                        <td>
                          <button
                            className="vella-button"
                            type="button"
                            onClick={() => {
                              setDrawerRow(row)
                              setDrawerTab(drawerTabs[0])
                            }}
                          >
                            <ExternalLink size={14} /> Подробнее
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredRows.length === 0 && (
                  <div className="vella-empty">
                    По текущим фильтрам SKU не найдено. Измените бренд, поиск или быстрые фильтры.
                  </div>
                )}
              </div>
            </div>
          </section>
        </main>
      </div>

      {drawerRow && (
        <>
          <div className="vella-drawer-overlay" tabIndex={0} onClick={() => setDrawerRow(null)} onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === 'Escape') setDrawerRow(null)
          }} />
          <aside className="vella-drawer" aria-label="Карточка SKU">
            <div className="vella-drawer-head">
              <div>
                <div className="vella-drawer-title">{drawerRow.sku}</div>
                <div className="vella-muted">{drawerRow.name}</div>
              </div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setDrawerRow(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-drawer-tabs">
              {drawerTabs.map((tab) => (
                <button
                  className={`vella-drawer-tab ${drawerTab === tab ? 'active' : ''}`}
                  key={tab}
                  type="button"
                  onClick={() => setDrawerTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="vella-drawer-body">
              <div className="vella-section">
                <div className="vella-section-title">{drawerTab}</div>
                {drawerTab === 'Обзор' && (
                  <p className="vella-muted">
                    {drawerRow.comment} Текущая цена {formatRub(drawerRow.price)}, маржа {drawerRow.margin}%, корзины {drawerRow.baskets}.
                  </p>
                )}
                {drawerTab === 'Правила' && (
                  <p className="vella-muted">
                    Коридор цены активен. Следующее действие: проверить `min_price`, затем применить мягкое снижение при сохранении проблемного статуса.
                  </p>
                )}
                {drawerTab === 'Комментарии' && (
                  <p className="vella-muted">
                    Последний ручной комментарий: ответственный {drawerRow.manager} проверяет рекламные расходы перед изменением цены.
                  </p>
                )}
              </div>
              <button
                className="vella-button primary"
                type="button"
                onClick={() => pushToast(`Моковое правило применено для ${drawerRow.sku}`)}
              >
                Применить моковое действие
              </button>
            </div>
          </aside>
        </>
      )}

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true" tabIndex={0} onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === 'Escape') setModal(null)
        }}>
          <div className="vella-modal">
            <div className="vella-modal-head">
              <div className="vella-modal-title">{modal === 'export' ? 'Экспорт отчета' : 'Создание правила'}</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}>
                <X size={16} />
              </button>
            </div>
            <div className="vella-modal-body">
              {modal === 'export'
                ? 'Здесь зафиксирован будущий UX: пользователь выбирает формат, период и состав колонок. Сейчас действие работает на моковых данных и показывает подтверждение.'
                : 'Форма правила будет связана с API на следующем этапе. В Phase 1 она уже открывается, закрывается и подтверждает выбранный сценарий.'}
            </div>
            <div className="vella-modal-foot">
              <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
              <button
                className="vella-button primary"
                type="button"
                onClick={() => {
                  pushToast(modal === 'export' ? 'Экспорт поставлен в очередь' : 'Правило сохранено в моковом состоянии')
                  setModal(null)
                }}
              >
                Подтвердить
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="vella-toast-stack">
        {toasts.map((toast) => (
          <div className="vella-toast" key={toast.id}>{toast.text}</div>
        ))}
      </div>
    </div>
  )
}
