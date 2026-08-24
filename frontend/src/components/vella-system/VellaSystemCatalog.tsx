import {
  Archive,
  BarChart3,
  Bell,
  CalendarDays,
  ChevronDown,
  Columns3,
  Download,
  LineChart,
  Percent,
  Search,
  Settings2,
  SlidersHorizontal,
  Star,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import {
  VellaBadge,
  VellaBulkBar,
  VellaBulkButton,
  VellaButton,
  VellaCalendar,
  VellaChip,
  VellaDrawer,
  VellaDropdown,
  VellaDropdownItem,
  VellaIconButton,
  VellaInlineEdit,
  VellaInput,
  VellaMetricStrip,
  VellaModal,
  VellaPopover,
  VellaSelect,
  VellaShell,
  VellaTable,
  VellaTabs,
  VellaToastStack,
  VellaToolbar,
  VellaTooltip,
  type VellaNavGroup,
  type VellaTableColumn,
} from './VellaSystem'

type Row = {
  id: string
  sku: string
  article: string
  status: 'auto' | 'manual' | 'new'
  price: number
  margin: number
  baskets: number
  manager: string
  abc: string
}

const rows: Row[] = [
  { id: '1', sku: 'FBBT_42', article: '100043703', status: 'auto', price: 2150, margin: 34, baskets: 16, manager: 'МД', abc: 'BA' },
  { id: '2', sku: 'HCBT_17', article: '100018084', status: 'manual', price: 2100, margin: 37, baskets: 17, manager: 'АП', abc: 'BA' },
  { id: '3', sku: 'LBBT_33', article: '100021254', status: 'new', price: 2050, margin: 39, baskets: 28, manager: 'СВ', abc: 'AA' },
]

const navGroups: VellaNavGroup[] = [
  {
    label: 'WB',
    items: [
      { id: 'repricer', label: 'Репрайсер', icon: <LineChart size={16} />, active: true },
      { id: 'reports', label: 'Отчёты', icon: <BarChart3 size={16} /> },
      { id: 'reviews', label: 'Отзывы WB', icon: <Star size={16} />, count: 'скоро' },
    ],
  },
  {
    label: 'Система',
    items: [
      { id: 'notifications', label: 'Уведомления', icon: <Bell size={16} />, count: 7 },
      { id: 'settings', label: 'Настройки', icon: <Settings2 size={16} /> },
    ],
  },
]

const tabs = [
  { id: 'products', label: 'Все товары', count: '1 482' },
  { id: 'templates', label: 'Стратегии', count: 5 },
  { id: 'history', label: 'История' },
  { id: 'liq', label: 'Ликвидация', count: 8 },
  { id: 'promos', label: 'Акции WB', count: '2!' },
]

const kpis = [
  { label: 'Выручка за период', value: '633 288 ₽', meta: '↑ +12.4% к прошлому периоду', metaTone: 'good' as const, tip: 'Сумма заказов по выбранному периоду.' },
  { label: 'Средняя маржа %', value: '26.8%', meta: '↑ +2.1 пп к прошлому периоду', metaTone: 'good' as const, tip: 'После СПП, комиссии, логистики и хранения.' },
  { label: 'Маржа ₽', value: '161 589 ₽', meta: 'после СПП, комиссии и хранения' },
  { label: 'SKU в продаже', value: '1 478', meta: '33 склада WB' },
]

export function VellaSystemCatalog() {
  const [activeTab, setActiveTab] = useState('products')
  const [search, setSearch] = useState('')
  const [manager, setManager] = useState('all')
  const [onlyProblems, setOnlyProblems] = useState(false)
  const [selectedDay, setSelectedDay] = useState(25)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set(['1', '2']))
  const [sort, setSort] = useState<{ id: string; direction: 'asc' | 'desc' }>({ id: 'price', direction: 'desc' })
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(() => new Set())
  const [modalOpen, setModalOpen] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [drawerTab, setDrawerTab] = useState('overview')
  const [inlineEditing, setInlineEditing] = useState(false)
  const [inlinePrice, setInlinePrice] = useState('2 150 ₽')
  const [toasts, setToasts] = useState<Array<{ id: number; text: string; variant: 'info' | 'success' | 'warn' | 'error' }>>([
    { id: 1, text: 'XLSX будет сформирован по текущим фильтрам', variant: 'info' },
  ])

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...rows]
      .filter((row) => manager === 'all' || row.manager === manager)
      .filter((row) => !onlyProblems || row.margin < 36)
      .filter((row) => !query || `${row.sku} ${row.article} ${row.manager}`.toLowerCase().includes(query))
      .sort((a, b) => {
        const left = a[sort.id as keyof Row]
        const right = b[sort.id as keyof Row]
        const result = typeof left === 'number' && typeof right === 'number'
          ? left - right
          : String(left).localeCompare(String(right), 'ru')
        return sort.direction === 'asc' ? result : -result
      })
  }, [manager, onlyProblems, search, sort])

  const columns: Array<VellaTableColumn<Row>> = [
    {
      id: 'sku',
      label: 'Фото / Артикул',
      sortable: true,
      render: (row) => (
        <button className="vs-btn ghost" type="button" onClick={() => setDrawerOpen(true)}>
          <span className="vs-sku">{row.sku}</span>
        </button>
      ),
    },
    { id: 'article', label: 'WB-Арт.', sortable: true, render: (row) => <span className="vs-sku">{row.article}</span> },
    {
      id: 'status',
      label: 'Статус товара',
      render: (row) => <VellaBadge variant={row.status === 'auto' ? 'success' : row.status === 'new' ? 'brand' : 'neutral'}>{row.status === 'auto' ? 'локомотив' : row.status === 'new' ? 'новинка' : 'ручной'}</VellaBadge>,
    },
    { id: 'abc', label: 'ABC', render: (row) => <VellaBadge variant="success">{row.abc}</VellaBadge> },
    {
      id: 'price',
      label: 'Цена до СПП',
      sortable: true,
      numeric: true,
      hidden: hiddenColumns.has('price'),
      render: (row) => row.id === '1'
        ? <VellaInlineEdit editing={inlineEditing} value={inlinePrice} onEdit={() => setInlineEditing(true)} onChange={setInlinePrice} onSave={() => {
          setInlineEditing(false)
          pushToast('Цена сохранена в mock state', 'success')
        }} />
        : <b>{row.price.toLocaleString('ru-RU')} ₽</b>,
    },
    {
      id: 'margin',
      label: 'Маржа',
      sortable: true,
      numeric: true,
      hidden: hiddenColumns.has('margin'),
      render: (row) => <span style={{ color: row.margin < 36 ? 'var(--red-mid)' : 'var(--green-mid)', fontWeight: 700 }}>+{row.margin}%</span>,
    },
    {
      id: 'baskets',
      label: 'Корзины',
      sortable: true,
      numeric: true,
      hidden: hiddenColumns.has('baskets'),
      render: (row) => <span>{row.baskets} ↑</span>,
    },
    { id: 'manager', label: 'Менеджер', hidden: hiddenColumns.has('manager'), render: (row) => row.manager },
  ]

  function pushToast(text: string, variant: 'info' | 'success' | 'warn' | 'error' = 'info') {
    setToasts((current) => [...current.slice(-2), { id: Date.now(), text, variant }])
  }

  function toggleSelected(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleColumn(id: string) {
    setHiddenColumns((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleSort(id: string) {
    setSort((current) => ({
      id,
      direction: current.id === id && current.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  const topbarActions = (
    <>
      <VellaPopover
        trigger={<VellaButton><CalendarDays size={15} /> 25.04 — 01.05 <ChevronDown size={14} /></VellaButton>}
      >
        <VellaCalendar selectedDay={selectedDay} onSelectDay={(day) => {
          setSelectedDay(day)
          pushToast(`Выбран день календаря: ${day}`, 'info')
        }} />
      </VellaPopover>
      <VellaTooltip content="Уведомления закрываются по Escape и клику вне popover">
        <VellaIconButton label="Уведомления" onClick={() => pushToast('Открыта проверка уведомлений', 'info')}>
          <Bell size={16} />
        </VellaIconButton>
      </VellaTooltip>
      <VellaDropdown trigger={<VellaButton variant="primary"><Download size={15} /> Экспорт <ChevronDown size={14} /></VellaButton>}>
        <VellaDropdownItem onSelect={() => pushToast('Экспорт XLSX запущен', 'success')}>Excel</VellaDropdownItem>
        <VellaDropdownItem onSelect={() => pushToast('Экспорт PDF запущен', 'success')}>PDF</VellaDropdownItem>
      </VellaDropdown>
    </>
  )

  return (
    <VellaShell
      breadcrumb={<><span>WB</span><span>/</span><b>Vella System</b></>}
      groups={navGroups}
      subtitle="Каталог primitives и состояний для 1:1 переноса HTML Vella в React."
      tabs={<VellaTabs activeId={activeTab} items={tabs} onChange={(id) => {
        setActiveTab(id)
        pushToast(`Открыта вкладка: ${tabs.find((tab) => tab.id === id)?.label}`, 'info')
      }} />}
      title="Design System Catalog"
      topbarActions={topbarActions}
    >
      <section className="vs-section" id="tokens">
        <h2>Tokens</h2>
        <div className="vs-swatch-row">
          {[
            ['brand', '#2563EB'],
            ['sidebar', '#0F172A'],
            ['bg', '#F8FAFC'],
            ['gray-900', '#030712'],
            ['green', '#059669'],
            ['red', '#DC2626'],
            ['amber', '#F59E0B'],
            ['purple', '#5B21B6'],
          ].map(([name, value]) => (
            <div className="vs-swatch" key={name} style={{ background: value }}>
              {name}
            </div>
          ))}
        </div>
      </section>

      <section className="vs-section" id="buttons">
        <h2>Buttons, chips, inputs</h2>
        <div className="vs-card">
          <div className="vs-row" style={{ flexWrap: 'wrap' }}>
            <VellaButton>Default</VellaButton>
            <VellaButton variant="primary">Primary</VellaButton>
            <VellaButton variant="ghost">Ghost</VellaButton>
            <VellaButton variant="danger">Danger</VellaButton>
            <VellaButton loading>Loading</VellaButton>
            <VellaButton disabled>Disabled</VellaButton>
            <VellaIconButton label="Колонки"><Columns3 size={15} /></VellaIconButton>
            <VellaChip active>Все 25</VellaChip>
            <VellaChip tone="brand">Новинки 2</VellaChip>
            <VellaChip tone="warn">Неликвид 0</VellaChip>
          </div>
          <div className="vs-divider" />
          <div className="vs-row" style={{ flexWrap: 'wrap' }}>
            <VellaInput icon={<Search size={15} />} placeholder="Артикул или название..." value={search} onChange={(event) => setSearch(event.target.value)} />
            <VellaInput error placeholder="Ошибка ввода" defaultValue="неверное значение" />
            <VellaSelect
              options={[
                { value: 'all', label: 'Все менеджеры' },
                { value: 'МД', label: 'Мария Д.' },
                { value: 'АП', label: 'Анна П.' },
                { value: 'СВ', label: 'Светлана В.' },
              ]}
              value={manager}
              onChange={setManager}
            />
          </div>
        </div>
      </section>

      <section className="vs-section" id="kpi">
        <h2>KPI strip</h2>
        <VellaMetricStrip items={kpis} />
      </section>

      <section className="vs-section" id="toolbar">
        <h2>Toolbar and table</h2>
        <VellaToolbar
          left={(
            <>
              <VellaInput icon={<Search size={15} />} placeholder="SKU или рекламная кампания" value={search} onChange={(event) => setSearch(event.target.value)} />
              <VellaChip active={!onlyProblems} onClick={() => setOnlyProblems(false)}>Все SKU</VellaChip>
              <VellaChip active={onlyProblems} onClick={() => setOnlyProblems(true)}>Проблемные</VellaChip>
              <VellaTooltip content="Фильтр меняет видимые строки в таблице">
                <span className="vs-help-dot">?</span>
              </VellaTooltip>
            </>
          )}
          right={(
            <>
              <VellaDropdown trigger={<VellaButton><SlidersHorizontal size={15} /> Сортировка</VellaButton>}>
                {['sku', 'price', 'margin', 'baskets'].map((id) => (
                  <VellaDropdownItem checked={sort.id === id} key={id} onSelect={() => toggleSort(id)}>{id}</VellaDropdownItem>
                ))}
              </VellaDropdown>
              <VellaDropdown trigger={<VellaButton><Columns3 size={15} /> Колонки</VellaButton>}>
                {['price', 'margin', 'baskets', 'manager'].map((id) => (
                  <VellaDropdownItem checked={!hiddenColumns.has(id)} key={id} onSelect={() => toggleColumn(id)}>{id}</VellaDropdownItem>
                ))}
              </VellaDropdown>
              <VellaButton variant="primary" onClick={() => setModalOpen(true)}>Применить цены · 47</VellaButton>
            </>
          )}
        />
        <VellaTable
          columns={columns}
          empty={<div><div className="vs-empty-title">Нет SKU под текущие фильтры</div><div>Сбросьте поиск или фильтр проблемных SKU.</div></div>}
          rows={filteredRows}
          selectedIds={selectedIds}
          sortDirection={sort.direction}
          sortId={sort.id}
          onSort={toggleSort}
          onToggleRow={toggleSelected}
        />
      </section>

      <section className="vs-section" id="overlays">
        <h2>Overlays</h2>
        <div className="vs-section-grid">
          <div className="vs-card">
            <h3>Modal / Drawer</h3>
            <p className="vs-page-copy">Открываются, закрываются по Escape и клику вне слоя.</p>
            <div className="vs-row" style={{ marginTop: 12 }}>
              <VellaButton onClick={() => setModalOpen(true)}>Открыть modal</VellaButton>
              <VellaButton onClick={() => setDrawerOpen(true)}>Открыть drawer</VellaButton>
            </div>
          </div>
          <div className="vs-card">
            <h3>Tooltip / Popover / Dropdown</h3>
            <div className="vs-row" style={{ marginTop: 12 }}>
              <VellaTooltip content="Тултип использует Vella visual contract">
                <VellaButton>Tooltip</VellaButton>
              </VellaTooltip>
              <VellaPopover trigger={<VellaButton>Popover</VellaButton>}>
                <div style={{ display: 'grid', gap: 8 }}>
                  <b>Popover state</b>
                  <span>Клик снаружи закрывает слой.</span>
                </div>
              </VellaPopover>
            </div>
          </div>
        </div>
      </section>

      <section className="vs-section" id="empty">
        <h2>Empty / blocked / fallback</h2>
        <div className="vs-table-wrap">
          <div className="vs-empty">
            <div>
              <div className="vs-empty-title">Источник WB временно недоступен</div>
              <div>Показываем fallback-состояние и сохраняем последний выбранный период.</div>
              <div className="vs-row" style={{ justifyContent: 'center', marginTop: 12 }}>
                <VellaButton>Повторить</VellaButton>
                <VellaButton variant="ghost">Открыть журнал</VellaButton>
              </div>
            </div>
          </div>
        </div>
      </section>

      <VellaBulkBar count={selectedIds.size} onClose={() => setSelectedIds(new Set())}>
        <VellaBulkButton onClick={() => pushToast('Стратегия применена к выделенным SKU', 'success')}>
          <Settings2 size={14} /> Применить стратегию
        </VellaBulkButton>
        <VellaBulkButton onClick={() => pushToast('P_min изменён для выделенных SKU', 'success')}>— Задать P_min</VellaBulkButton>
        <VellaBulkButton onClick={() => pushToast('Ликвидация запущена в mock state', 'warn')}>
          <Archive size={14} /> Ликвидировать
        </VellaBulkButton>
      </VellaBulkBar>

      <VellaModal
        description="Mock action меняет visible state и добавляет toast."
        footer={(
          <>
            <VellaButton variant="ghost" onClick={() => setModalOpen(false)}>Отмена</VellaButton>
            <VellaButton variant="primary" onClick={() => {
              setModalOpen(false)
              pushToast('Цены применены в mock state', 'success')
            }}>Применить</VellaButton>
          </>
        )}
        open={modalOpen}
        title="Применить цены"
        onOpenChange={setModalOpen}
      >
        <div className="vs-row" style={{ alignItems: 'flex-start' }}>
          <Percent size={18} />
          <div>
            <b>Будет изменено 47 SKU</b>
            <p className="vs-page-copy">2 SKU требуют подтверждения P_min. В production этот action пойдёт через backend, здесь меняется mock state.</p>
          </div>
        </div>
      </VellaModal>

      <VellaDrawer
        activeTab={drawerTab}
        footer={(
          <>
            <VellaButton variant="ghost" onClick={() => setDrawerOpen(false)}>Закрыть</VellaButton>
            <VellaButton variant="primary" onClick={() => pushToast('SKU сохранён', 'success')}>Сохранить</VellaButton>
          </>
        )}
        open={drawerOpen}
        subtitle={<span className="vs-sku">FBBT_42</span>}
        tabs={[{ id: 'overview', label: 'Обзор' }, { id: 'rules', label: 'Правила' }, { id: 'misc', label: 'Прочее' }]}
        title="Карточка SKU"
        onOpenChange={setDrawerOpen}
        onTabChange={setDrawerTab}
      >
        {drawerTab === 'overview' ? (
          <div style={{ display: 'grid', gap: 12 }}>
            <VellaMetricStrip items={[
              { label: 'Цена', value: '2 150 ₽', meta: 'без изм.' },
              { label: 'Маржа', value: '+34%', meta: '+730 ₽', metaTone: 'good' },
              { label: 'Корзины', value: '16', meta: 'активный спрос' },
              { label: 'Остаток', value: '81%', meta: 'выкуп' },
            ]} />
            <div className="vs-card">История расчёта, комментарии и действия SKU живут внутри единого drawer primitive.</div>
          </div>
        ) : drawerTab === 'rules' ? (
          <div className="vs-card">Автоматика, P_min, ночная медиана и ограничения стратегии.</div>
        ) : (
          <div className="vs-card">Прочее: заказы, остатки, комментарии, audit trail.</div>
        )}
      </VellaDrawer>

      <VellaToastStack items={toasts} />
    </VellaShell>
  )
}
