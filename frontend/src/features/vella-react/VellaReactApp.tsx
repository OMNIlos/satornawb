import {
  Archive,
  BarChart3,
  Bell,
  CalendarDays,
  CheckCheck,
  ChevronDown,
  Columns3,
  Download,
  ExternalLink,
  LineChart,
  Search,
  Settings2,
  Star,
} from 'lucide-react'
import { type Dispatch, type SetStateAction, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
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
} from '@/components/vella-system/VellaSystem'
import { getNotifications } from '@/features/notifications/repository'
import type { NotificationEvent } from '@/features/notifications/types'
import './vella-react.css'

type RouteGroup = 'repricer' | 'reports' | 'notifications'
type RepricerTab = 'products' | 'algo' | 'templates' | 'history' | 'liq' | 'promos'
type ReportsTab = 'digest' | 'abc' | 'rnp' | 'pnl' | 'ads' | 'stock' | 'week' | 'report-rules'
type ModalKind = 'apply' | 'export' | 'strategy' | 'liquidation' | 'pmin' | 'saveView' | 'shortcuts' | 'blocked' | null
type Density = 'comfortable' | 'compact'

type SkuRow = {
  id: string
  sku: string
  article: string
  name: string
  status: 'auto' | 'manual' | 'new'
  abc: 'AA' | 'BA' | 'CC'
  promo: boolean
  price: number
  pMin: number
  margin: number
  baskets: number
  orders: number
  stock: number
  manager: 'МД' | 'АП' | 'СВ' | 'ИК'
  strategy: string
  liquidation: 'candidate' | 'active' | 'none'
  changed24h?: boolean
}

type AuditEvent = {
  id: number
  text: string
  at: string
  actor: string
  operation: string
  entity: string
  diff: string
  mode: 'manual' | 'auto' | 'system'
  reason: string
  scope: string
}

type SavedView = {
  id: string
  name: string
  scope: 'repricer'
  filters: {
    problemOnly?: boolean
    noPMin?: boolean
    lossMargin?: boolean
    changed24h?: boolean
    liquidation?: boolean
  }
  sort: { id: string; direction: 'asc' | 'desc' }
  columns: string[]
  period: string
  brand: string
  owner: string
  access: 'system' | 'personal' | 'team'
}

type WorkQueueItem = {
  id: string
  skuId: string
  owner: string
  status: 'требует решения' | 'ожидает данных' | 'заблокировано guardrail' | 'в работе'
  sla: string
  ageHours: number
  reasonToAct: string
  nextAction: string
  critical?: boolean
}

type RecommendationExplanation = {
  trigger: string
  freshness: string
  rule: string
  guardrail: string
}

type Toast = {
  id: number
  text: string
  variant: 'info' | 'success' | 'warn' | 'error'
}

const initialSkuRows: SkuRow[] = [
  { id: '1', sku: 'FBBT_42', article: '100043703', name: 'Футболка белая «Принт 42»', status: 'auto', abc: 'BA', promo: false, price: 2150, pMin: 1850, margin: 34, baskets: 16, orders: 20, stock: 81, manager: 'МД', strategy: 'Локомотив', liquidation: 'none', changed24h: true },
  { id: '2', sku: 'HCBT_17', article: '100018084', name: 'Худи чёрное «Принт 17»', status: 'manual', abc: 'BA', promo: false, price: 2100, pMin: 1850, margin: 37, baskets: 17, orders: 21, stock: 68, manager: 'АП', strategy: 'Ручной', liquidation: 'none', changed24h: true },
  { id: '3', sku: 'LBBT_33', article: '100021254', name: 'Лонгслив белый «Принт 33»', status: 'manual', abc: 'CC', promo: true, price: 1140, pMin: 1180, margin: -3, baskets: 4, orders: 3, stock: 31, manager: 'СВ', strategy: 'Неликвид', liquidation: 'candidate' },
  { id: '4', sku: 'FBCT_08', article: '100049409', name: 'Футболка чёрная «Принт 8»', status: 'auto', abc: 'BA', promo: true, price: 2090, pMin: 1720, margin: 34, baskets: 12, orders: 20, stock: 82, manager: 'ИК', strategy: 'Локомотив', liquidation: 'none' },
  { id: '5', sku: 'FBBT_29', article: '100055348', name: 'Футболка белая «Принт 29»', status: 'new', abc: 'CC', promo: true, price: 590, pMin: 0, margin: -8, baskets: 2, orders: 1, stock: 43, manager: 'МД', strategy: 'Запуск', liquidation: 'candidate' },
  { id: '6', sku: 'HBBT_51', article: '100062335', name: 'Худи белое «Принт 51»', status: 'auto', abc: 'BA', promo: false, price: 2100, pMin: 1780, margin: 37, baskets: 17, orders: 21, stock: 84, manager: 'АП', strategy: 'Локомотив', liquidation: 'none' },
]

const builtInSavedViews: SavedView[] = [
  { id: 'all', name: 'Все', scope: 'repricer', filters: {}, sort: { id: 'price', direction: 'desc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
  { id: 'problem', name: 'Проблемные SKU', scope: 'repricer', filters: { problemOnly: true }, sort: { id: 'margin', direction: 'asc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
  { id: 'no-pmin', name: 'Без P_min', scope: 'repricer', filters: { noPMin: true }, sort: { id: 'sku', direction: 'asc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
  { id: 'loss', name: 'Loss margin', scope: 'repricer', filters: { lossMargin: true }, sort: { id: 'margin', direction: 'asc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
  { id: 'changed', name: 'Изменения 24ч', scope: 'repricer', filters: { changed24h: true }, sort: { id: 'price', direction: 'desc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
  { id: 'liq', name: 'Неликвид', scope: 'repricer', filters: { liquidation: true }, sort: { id: 'baskets', direction: 'asc' }, columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'], period: '25.04 — 01.05', brand: 'Все', owner: 'system', access: 'system' },
]

const workQueue: WorkQueueItem[] = [
  { id: 'w1', skuId: '3', owner: 'Светлана В.', status: 'требует решения', sla: 'SLA 2ч', ageHours: 18, reasonToAct: 'Loss margin и низкие корзины', nextAction: 'Проверить P_min перед ликвидацией', critical: true },
  { id: 'w2', skuId: '5', owner: 'Мария Д.', status: 'заблокировано guardrail', sla: 'SLA 4ч', ageHours: 9, reasonToAct: 'P_min отсутствует', nextAction: 'Заполнить P_min и подтвердить маржу', critical: true },
  { id: 'w3', skuId: '2', owner: 'Анна П.', status: 'в работе', sla: 'SLA 24ч', ageHours: 3, reasonToAct: 'Ручной режим после скачка цены', nextAction: 'Вернуть в стратегию после проверки' },
  { id: 'w4', skuId: '1', owner: 'Мария Д.', status: 'ожидает данных', sla: 'SLA 24ч', ageHours: 6, reasonToAct: 'Изменения 24ч требуют сверки WB', nextAction: 'Дождаться обновления корзин' },
]

const reportRows = [
  { id: 'r1', sku: 'FBBT_42', metric: 'Реклама WB', value: '9.1% ДРР', recommendation: 'оставить', manager: 'МД', profit: '41 585 ₽' },
  { id: 'r2', sku: 'HCBT_17', metric: 'Остатки WB', value: '42 шт', recommendation: 'пополнить', manager: 'АП', profit: '18 420 ₽' },
  { id: 'r3', sku: 'LBBT_33', metric: 'Неделя-к-неделе', value: '−18% заказов', recommendation: 'в ликвидацию', manager: 'СВ', profit: '−240 ₽' },
  { id: 'r4', sku: 'FBCT_08', metric: 'ABC', value: 'BC', recommendation: 'снизить ДРР', manager: 'ИК', profit: '1 260 ₽' },
]

const repricerTabs: Array<{ id: RepricerTab; label: string; count?: string | number }> = [
  { id: 'products', label: 'Все товары', count: '1 482' },
  { id: 'templates', label: 'Стратегии', count: 5 },
  { id: 'history', label: 'История' },
  { id: 'liq', label: 'Ликвидация', count: 8 },
  { id: 'promos', label: 'Акции WB', count: '2!' },
  { id: 'algo', label: 'Правила' },
]

const reportsTabs: Array<{ id: ReportsTab; label: string; count?: string | number }> = [
  { id: 'digest', label: 'Дайджест' },
  { id: 'abc', label: 'ABC' },
  { id: 'rnp', label: 'РНП' },
  { id: 'pnl', label: 'P&L' },
  { id: 'ads', label: 'Реклама' },
  { id: 'stock', label: 'Остатки' },
  { id: 'week', label: 'Неделя' },
  { id: 'report-rules', label: 'Правила' },
]

function routeFromPath(pathname: string): { group: RouteGroup; repricerTab: RepricerTab; reportsTab: ReportsTab } {
  if (pathname.includes('/notifications')) return { group: 'notifications', repricerTab: 'products', reportsTab: 'digest' }
  if (pathname.includes('/reports')) {
    if (pathname.includes('/ads')) return { group: 'reports', repricerTab: 'products', reportsTab: 'ads' }
    if (pathname.includes('/stock')) return { group: 'reports', repricerTab: 'products', reportsTab: 'stock' }
    if (pathname.includes('/week-over-week')) return { group: 'reports', repricerTab: 'products', reportsTab: 'week' }
    if (pathname.includes('/abc')) return { group: 'reports', repricerTab: 'products', reportsTab: 'abc' }
    if (pathname.includes('/rnp')) return { group: 'reports', repricerTab: 'products', reportsTab: 'rnp' }
    if (pathname.includes('/pnl')) return { group: 'reports', repricerTab: 'products', reportsTab: 'pnl' }
    if (pathname.includes('/rules')) return { group: 'reports', repricerTab: 'products', reportsTab: 'report-rules' }
    return { group: 'reports', repricerTab: 'products', reportsTab: 'digest' }
  }
  if (pathname.includes('/liquidation')) return { group: 'repricer', repricerTab: 'liq', reportsTab: 'digest' }
  if (pathname.includes('/promos') || pathname.includes('/promotions')) return { group: 'repricer', repricerTab: 'promos', reportsTab: 'digest' }
  if (pathname.includes('/changelog')) return { group: 'repricer', repricerTab: 'history', reportsTab: 'digest' }
  return { group: 'repricer', repricerTab: 'products', reportsTab: 'digest' }
}

function rub(value: number) {
  return value.toLocaleString('ru-RU') + ' ₽'
}

function nowLabel() {
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date())
}

export function VellaReactApp() {
  const location = useLocation()
  const navigate = useNavigate()
  const route = routeFromPath(location.pathname)
  const digestMode: 'period' | 'now' = location.pathname.includes('/reports/monitor') || new URLSearchParams(location.search).get('mode') !== 'period' ? 'now' : 'period'
  const [activeGroup, setActiveGroup] = useState<RouteGroup>(route.group)
  const [repricerTab, setRepricerTab] = useState<RepricerTab>(route.repricerTab)
  const [reportsTab, setReportsTab] = useState<ReportsTab>(route.reportsTab)
  const [skuRows, setSkuRows] = useState(initialSkuRows)
  const [search, setSearch] = useState('')
  const [manager, setManager] = useState('all')
  const [problemOnly, setProblemOnly] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set(['1', '2', '3']))
  const [sort, setSort] = useState<{ id: string; direction: 'asc' | 'desc' }>({ id: 'price', direction: 'desc' })
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(() => new Set())
  const [savedViews, setSavedViews] = useState<SavedView[]>(builtInSavedViews)
  const [activeSavedViewId, setActiveSavedViewId] = useState('all')
  const [saveViewName, setSaveViewName] = useState('Рабочий сегмент')
  const [worklistFilter, setWorklistFilter] = useState<'all' | 'critical' | 'mine' | 'blocked'>('all')
  const [density, setDensityState] = useState<Density>(() => {
    if (typeof window === 'undefined') return 'comfortable'
    return window.localStorage.getItem('vella-density') === 'compact' ? 'compact' : 'comfortable'
  })
  const [drawerSkuId, setDrawerSkuId] = useState<string | null>(null)
  const [drawerTab, setDrawerTab] = useState('overview')
  const [modal, setModal] = useState<ModalKind>(null)
  const [calendarDay, setCalendarDay] = useState(25)
  const [editingPriceId, setEditingPriceId] = useState<string | null>(null)
  const [editingPrice, setEditingPrice] = useState('')
  const [notifications, setNotifications] = useState<NotificationEvent[]>(() => getNotifications().items)
  const [selectedNotificationId, setSelectedNotificationId] = useState<string | null>(null)
  const [notificationQuery, setNotificationQuery] = useState('')
  const [audit, setAudit] = useState<AuditEvent[]>([
    { id: 1, text: 'Мария Д. применила стратегию «Локомотив» к 3 SKU', at: '08:32', actor: 'Мария Д.', operation: 'strategy.apply', entity: '3 SKU', diff: 'manual → auto', mode: 'manual', reason: 'корзины выше нормы', scope: 'selected rows' },
    { id: 2, text: 'Система сформировала Excel-отчёт по рекламе', at: '08:16', actor: 'system', operation: 'report.export', entity: 'Реклама WB', diff: 'draft → ready', mode: 'system', reason: 'scheduled report', scope: 'period 25.04—01.05' },
  ])
  const [toasts, setToasts] = useState<Toast[]>([])
  const activeSavedView = savedViews.find((view) => view.id === activeSavedViewId) ?? savedViews[0]
  const selectedRows = skuRows.filter((row) => selectedIds.has(row.id))

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === '?') {
        event.preventDefault()
        setModal('shortcuts')
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        document.querySelector<HTMLInputElement>('[data-vella-search="repricer"]')?.focus()
      }
      if (event.altKey && /^[1-6]$/.test(event.key)) {
        event.preventDefault()
        const view = savedViews[Number(event.key) - 1]
        if (view) {
          setActiveSavedViewId(view.id)
          setProblemOnly(Boolean(view.filters.problemOnly || view.filters.lossMargin || view.filters.liquidation))
          setSort(view.sort)
          setHiddenColumns(new Set(['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'].filter((column) => !view.columns.includes(column))))
        }
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [savedViews])

  function pushToast(text: string, variant: Toast['variant'] = 'info') {
    setToasts((current) => [...current.slice(-3), { id: Date.now(), text, variant }])
  }

  function pushAudit(text: string, event?: Partial<AuditEvent>) {
    setAudit((current) => [{
      id: Date.now(),
      text,
      at: nowLabel(),
      actor: event?.actor ?? 'Мария Д.',
      operation: event?.operation ?? 'manual.action',
      entity: event?.entity ?? `${selectedIds.size || 1} SKU`,
      diff: event?.diff ?? 'old→new',
      mode: event?.mode ?? 'manual',
      reason: event?.reason ?? 'ручное действие менеджера',
      scope: event?.scope ?? 'current selection',
    }, ...current].slice(0, 12))
  }

  function setDensity(mode: Density) {
    setDensityState(mode)
    window.localStorage.setItem('vella-density', mode)
    pushToast(`Плотность таблицы: ${mode === 'compact' ? 'Компактно' : 'Комфортно'}`, 'info')
  }

  function applySavedView(id: string) {
    const view = savedViews.find((item) => item.id === id)
    if (!view) return
    setActiveSavedViewId(id)
    setProblemOnly(Boolean(view.filters.problemOnly || view.filters.lossMargin || view.filters.liquidation))
    setSort(view.sort)
    setHiddenColumns(new Set(['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'].filter((column) => !view.columns.includes(column))))
    pushToast(`Открыт saved view: ${view.name}`, 'info')
  }

  function saveCurrentView() {
    const view: SavedView = {
      id: `custom-${Date.now()}`,
      name: saveViewName.trim() || 'Рабочий сегмент',
      scope: 'repricer',
      filters: { problemOnly },
      sort,
      columns: ['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'].filter((column) => !hiddenColumns.has(column)),
      period: '25.04 — 01.05',
      brand: 'Все',
      owner: 'Мария Д.',
      access: 'personal',
    }
    setSavedViews((current) => [...current, view])
    setActiveSavedViewId(view.id)
    setModal(null)
    pushAudit(`Мария Д. сохранила SavedView «${view.name}»`, { operation: 'savedView.create', entity: view.name, diff: 'none → saved', reason: 'сохранить текущие фильтры', scope: view.scope })
    pushToast(`SavedView добавлен: ${view.name}`, 'success')
  }

  function applyPMinPreview() {
    setSkuRows((current) => current.map((row) => selectedIds.has(row.id) ? { ...row, pMin: Math.max(row.pMin, row.price - 180) } : row))
    pushAudit(`P_min обновлён для ${selectedIds.size} SKU`, { operation: 'pmin.bulk_update', diff: 'current → preview new', reason: 'bulk preview confirmed' })
    setModal(null)
    pushToast('P_min применён после preview', 'success')
  }

  function setRouteGroup(group: RouteGroup) {
    setActiveGroup(group)
    if (group === 'repricer') navigate('/internal/vella-react/repricer')
    if (group === 'reports') navigate('/internal/vella-react/reports')
    if (group === 'notifications') navigate('/internal/vella-react/notifications')
  }

  function setRouteRepricerTab(tab: RepricerTab) {
    setActiveGroup('repricer')
    setRepricerTab(tab)
    if (tab === 'liq') navigate('/internal/vella-react/repricer/liquidation')
    else if (tab === 'promos') navigate('/internal/vella-react/repricer/promos')
    else if (tab === 'history') navigate('/internal/vella-react/repricer/changelog')
    else navigate('/internal/vella-react/repricer')
  }

  function setRouteReportsTab(tab: ReportsTab) {
    setActiveGroup('reports')
    setReportsTab(tab)
    if (tab === 'digest') {
      navigate('/internal/vella-react/reports')
      return
    }
    const path = tab === 'week' ? 'week-over-week' : tab === 'report-rules' ? 'rules' : tab
    navigate(`/internal/vella-react/reports/${path}`)
  }

  const navGroups: VellaNavGroup[] = [
    {
      label: 'WB',
      items: [
        { id: 'repricer', label: 'Репрайсер', icon: <LineChart size={16} />, active: activeGroup === 'repricer', onClick: () => setRouteGroup('repricer') },
        { id: 'reports', label: 'Отчёты', icon: <BarChart3 size={16} />, active: activeGroup === 'reports', onClick: () => setRouteGroup('reports') },
        { id: 'reviews', label: 'Отзывы WB', icon: <Star size={16} />, count: 'скоро', onClick: () => pushToast('Отзывы WB будут перенесены после текущего HTML scope', 'info') },
      ],
    },
    {
      label: 'Система',
      items: [
        { id: 'notifications', label: 'Уведомления', icon: <Bell size={16} />, count: notifications.filter((item) => !item.readAt).length, active: activeGroup === 'notifications', onClick: () => setRouteGroup('notifications') },
        { id: 'settings', label: 'Настройки', icon: <Settings2 size={16} />, onClick: () => setModal('blocked') },
      ],
    },
  ]

  const visibleRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...skuRows]
      .filter((row) => manager === 'all' || row.manager === manager)
      .filter((row) => !problemOnly || row.margin < 0 || row.liquidation !== 'none')
      .filter((row) => !activeSavedView.filters.noPMin || row.pMin === 0)
      .filter((row) => !activeSavedView.filters.lossMargin || row.margin < 0)
      .filter((row) => !activeSavedView.filters.changed24h || row.changed24h)
      .filter((row) => !activeSavedView.filters.liquidation || row.liquidation !== 'none')
      .filter((row) => !query || `${row.sku} ${row.article} ${row.name}`.toLowerCase().includes(query))
      .sort((a, b) => {
        const left = a[sort.id as keyof SkuRow]
        const right = b[sort.id as keyof SkuRow]
        const result = typeof left === 'number' && typeof right === 'number'
          ? left - right
          : String(left).localeCompare(String(right), 'ru')
        return sort.direction === 'asc' ? result : -result
      })
  }, [activeSavedView, manager, problemOnly, search, skuRows, sort])

  const selectedSku = skuRows.find((row) => row.id === drawerSkuId) ?? null

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
    setSort((current) => ({ id, direction: current.id === id && current.direction === 'desc' ? 'asc' : 'desc' }))
  }

  function savePrice() {
    if (!editingPriceId) return
    const numeric = Number(editingPrice.replace(/[^\d]/g, ''))
    if (!numeric) {
      pushToast('Введите корректную цену', 'error')
      return
    }
    const sku = skuRows.find((row) => row.id === editingPriceId)?.sku
    setSkuRows((current) => current.map((row) => row.id === editingPriceId ? { ...row, price: numeric } : row))
    setEditingPriceId(null)
    pushAudit(`Мария Д. вручную изменила цену ${sku} на ${rub(numeric)}`)
    pushToast(`Цена ${sku} сохранена`, 'success')
  }

  function applyPrices() {
    setSkuRows((current) => current.map((row) => selectedIds.has(row.id) ? { ...row, price: Math.round(row.price * 1.03) } : row))
    pushAudit(`Применены цены к ${selectedIds.size} SKU`, { operation: 'price.bulk_apply', diff: 'current → +3%', reason: 'preview confirmed' })
    setModal(null)
    pushToast(`Применены цены: ${selectedIds.size} SKU`, 'success')
  }

  function applyStrategy() {
    setSkuRows((current) => current.map((row) => selectedIds.has(row.id) ? { ...row, strategy: 'Локомотив', status: 'auto' } : row))
    pushAudit(`Стратегия «Локомотив» применена к ${selectedIds.size} SKU`, { operation: 'strategy.bulk_apply', diff: 'mixed → Локомотив', reason: 'manual review passed' })
    setModal(null)
    pushToast('Стратегия применена после preview', 'success')
  }

  function startLiquidation() {
    setSkuRows((current) => current.map((row) => selectedIds.has(row.id) ? { ...row, liquidation: 'active', status: 'manual' } : row))
    pushAudit(`Запущена ликвидация для ${selectedIds.size} SKU`, { operation: 'liquidation.start', diff: 'candidate → active', reason: 'projected floor accepted' })
    setSelectedIds(new Set())
    setModal(null)
    pushToast('Ликвидация запущена в mock state', 'warn')
  }

  function downloadReport(item?: NotificationEvent) {
    const fileName = item?.reportFile?.fileName ?? `vella-report-${Date.now()}.xls`
    const rows = [
      ['Отчёт', item?.reportFile?.report ?? 'Сводный отчёт WB'],
      ['Период', item?.reportFile?.period ?? '25.04—01.05'],
      ['Строк', String(item?.reportFile?.rows ?? reportRows.length)],
      [],
      ['SKU', 'Метрика', 'Значение', 'Рекомендация'],
      ...reportRows.map((row) => [row.sku, row.metric, row.value, row.recommendation]),
    ]
    const html = `<html><head><meta charset="utf-8"></head><body><table>${rows.map((row) => `<tr>${row.map((cell) => `<td>${String(cell).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</td>`).join('')}</tr>`).join('')}</table></body></html>`
    const blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName.replace(/\.xlsx$/i, '.xls')
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    if (item) setNotifications((current) => current.map((notification) => notification.id === item.id ? { ...notification, readAt: notification.readAt ?? new Date().toISOString() } : notification))
    pushAudit(`Скачан сформированный отчёт ${fileName}`)
    pushToast(`Скачан отчёт: ${fileName}`, 'success')
  }

  const reportsWithPeriod = ['abc', 'rnp', 'pnl', 'ads', 'stock', 'week'].includes(reportsTab)
  const showContextPeriod = (activeGroup === 'repricer' && repricerTab === 'products') || (activeGroup === 'reports' && (reportsWithPeriod || (reportsTab === 'digest' && digestMode === 'period')))
  const showContextExport = (activeGroup === 'repricer' && repricerTab === 'products') || showContextPeriod
  const showContextLiveStatus = activeGroup === 'reports' && reportsTab === 'digest' && digestMode === 'now'
  const contextControls = (
    <div className="vr-subtabs-context">
      {showContextLiveStatus ? <VellaBadge variant="success">Сегодня · обновлено {nowLabel()}</VellaBadge> : null}
      {showContextPeriod ? (
        <VellaPopover trigger={<VellaButton><CalendarDays size={15} /> 25.04 — 01.05 <ChevronDown size={14} /></VellaButton>}>
          <VellaCalendar selectedDay={calendarDay} onSelectDay={(day) => {
            setCalendarDay(day)
            pushToast(`Период обновлён: ${day}.04—01.05`, 'info')
          }} />
        </VellaPopover>
      ) : null}
      {showContextExport ? (
        <VellaDropdown trigger={<VellaButton><Download size={15} /> Экспорт <ChevronDown size={14} /></VellaButton>}>
          <VellaDropdownItem onSelect={() => downloadReport()}>Экспорт XLSX</VellaDropdownItem>
          {activeGroup === 'repricer' && repricerTab === 'products' ? <VellaDropdownItem onSelect={() => setModal('export')}>Импорт XLSX для цен</VellaDropdownItem> : null}
          {activeGroup === 'reports' ? <VellaDropdownItem onSelect={() => setModal('export')}>Настроить выгрузку</VellaDropdownItem> : null}
        </VellaDropdown>
      ) : null}
    </div>
  )

  const topbarActions = (
    <>
      <VellaPopover trigger={<VellaIconButton label="Уведомления"><Bell size={16} /></VellaIconButton>}>
        <div className="vr-popover-list">
          {notifications.slice(0, 5).map((item) => (
            <button className="vr-popover-row" key={item.id} type="button" onClick={() => {
              setRouteGroup('notifications')
              setSelectedNotificationId(item.id)
            }}>
              <b>{item.title}</b>
              <span>{item.details}</span>
            </button>
          ))}
        </div>
      </VellaPopover>
    </>
  )

  const tabsList = activeGroup === 'reports'
    ? <VellaTabs activeId={reportsTab} items={reportsTabs} onChange={(id) => setRouteReportsTab(id as ReportsTab)} />
    : activeGroup === 'repricer'
      ? <VellaTabs activeId={repricerTab} items={repricerTabs} onChange={(id) => setRouteRepricerTab(id as RepricerTab)} />
      : <VellaTabs activeId="notifications" items={[{ id: 'notifications', label: 'Уведомления', count: notifications.filter((item) => !item.readAt).length + ' новых' }]} onChange={() => undefined} />
  const tabs = (
    <div className="vr-subtabs-row">
      <div className="vr-subtabs-scroll">{tabsList}</div>
      {showContextLiveStatus || showContextPeriod || showContextExport ? contextControls : null}
    </div>
  )

  const pageTitle = activeGroup === 'reports'
    ? reportsTabs.find((tab) => tab.id === reportsTab)?.label ?? 'Отчёты'
    : activeGroup === 'notifications'
      ? 'Уведомления'
      : repricerTabs.find((tab) => tab.id === repricerTab)?.label ?? 'Репрайсер'

  return (
    <VellaShell
      breadcrumb={<><span>WB</span><span>/</span><b>{pageTitle}</b></>}
      groups={navGroups}
      subtitle={activeGroup === 'repricer' ? 'React runtime без iframe: корзины, P_min, маржа, автоматика и ручные действия меняют mock state.' : undefined}
      tabs={tabs}
      title={pageTitle}
      topbarActions={topbarActions}
    >
      {activeGroup === 'repricer' && (
        <RepricerContent
          audit={audit}
          drawerTab={drawerTab}
          editingPrice={editingPrice}
          editingPriceId={editingPriceId}
          hiddenColumns={hiddenColumns}
          density={density}
          activeSavedViewId={activeSavedViewId}
          savedViews={savedViews}
          worklistFilter={worklistFilter}
          problemOnly={problemOnly}
          repricerTab={repricerTab}
          rows={visibleRows}
          selectedIds={selectedIds}
          selectedSku={selectedSku}
          sort={sort}
          manager={manager}
          search={search}
          applySavedView={applySavedView}
          setDrawerSkuId={setDrawerSkuId}
          setDrawerTab={setDrawerTab}
          setEditingPrice={setEditingPrice}
          setEditingPriceId={setEditingPriceId}
          setManager={setManager}
          setModal={setModal}
          setProblemOnly={setProblemOnly}
          setSearch={setSearch}
          setDensity={setDensity}
          setWorklistFilter={setWorklistFilter}
          setSelectedIds={setSelectedIds}
          toggleColumn={toggleColumn}
          toggleSelected={toggleSelected}
          toggleSort={toggleSort}
          savePrice={savePrice}
        />
      )}
      {activeGroup === 'reports' && (
        <ReportsContent
          audit={audit}
          digestMode={digestMode}
          reportsTab={reportsTab}
          setModal={setModal}
          downloadReport={downloadReport}
          pushToast={pushToast}
        />
      )}
      {activeGroup === 'notifications' && (
        <NotificationsContent
          notifications={notifications}
          query={notificationQuery}
          selectedId={selectedNotificationId}
          setNotifications={setNotifications}
          setQuery={setNotificationQuery}
          setSelectedId={setSelectedNotificationId}
          downloadReport={downloadReport}
          openRoute={(routePath) => {
            if (routePath.includes('/reports')) setRouteGroup('reports')
            else setRouteGroup('repricer')
          }}
        />
      )}

      <VellaBulkBar count={selectedIds.size} onClose={() => setSelectedIds(new Set())}>
        <VellaBulkButton onClick={() => setModal('strategy')}><Settings2 size={14} /> Применить стратегию</VellaBulkButton>
        <VellaBulkButton onClick={() => setModal('pmin')}>— Задать P_min</VellaBulkButton>
        <VellaBulkButton onClick={() => setModal('liquidation')}><Archive size={14} /> Ликвидировать</VellaBulkButton>
      </VellaBulkBar>

      <VellaModal
        description={modal === 'apply' ? 'Цены применятся к выбранным SKU в mock state.' : modal === 'export' ? 'Файл будет скачан без обращения к backend.' : 'Действие будет записано в audit/history.'}
        footer={<ModalFooter modal={modal} onCancel={() => setModal(null)} onConfirm={() => {
          if (modal === 'apply') applyPrices()
          else if (modal === 'pmin') applyPMinPreview()
          else if (modal === 'liquidation') startLiquidation()
          else if (modal === 'strategy') applyStrategy()
          else if (modal === 'saveView') saveCurrentView()
          else if (modal === 'export') {
            setModal(null)
            downloadReport()
          } else {
            setModal(null)
            pushAudit('Mock-действие выполнено')
            pushToast('Действие выполнено', 'success')
          }
        }} />}
        open={Boolean(modal)}
        title={modal === 'apply' ? 'Применить цены' : modal === 'pmin' ? 'Preview: задать P_min' : modal === 'liquidation' ? 'Preview: ликвидировать SKU' : modal === 'saveView' ? 'Сохранить SavedView' : modal === 'shortcuts' ? 'Горячие клавиши' : modal === 'export' ? 'Экспорт отчёта' : modal === 'strategy' ? 'Preview: применить стратегию' : 'Действие недоступно'}
        onOpenChange={(open) => setModal(open ? modal : null)}
      >
        <ModalBody
          modal={modal}
          saveViewName={saveViewName}
          selectedRows={selectedRows}
          setSaveViewName={setSaveViewName}
        />
      </VellaModal>

      <VellaToastStack items={toasts} />
    </VellaShell>
  )
}

function ModalFooter({ modal, onCancel, onConfirm }: { modal: ModalKind; onCancel: () => void; onConfirm: () => void }) {
  return (
    <>
      <VellaButton variant="ghost" onClick={onCancel}>Отмена</VellaButton>
      <VellaButton variant={modal === 'liquidation' ? 'danger' : 'primary'} onClick={onConfirm}>
        {modal === 'shortcuts' ? 'Понятно' : modal === 'saveView' ? 'Сохранить/Клонировать' : modal === 'export' ? 'Скачать' : modal === 'liquidation' ? 'Запустить' : 'Подтвердить'}
      </VellaButton>
    </>
  )
}

function ModalBody({ modal, selectedRows, saveViewName, setSaveViewName }: { modal: ModalKind; selectedRows: SkuRow[]; saveViewName: string; setSaveViewName: (value: string) => void }) {
  if (modal === 'shortcuts') {
    return (
      <div className="vr-shortcut-grid">
        <kbd>Cmd/Ctrl+K</kbd><span>Фокус на поиск SKU</span>
        <kbd>?</kbd><span>Открыть это окно</span>
        <kbd>Enter</kbd><span>Сохранить inline edit или подтвердить focused action</span>
        <kbd>Space</kbd><span>Выбрать строку в таблице</span>
        <kbd>Esc</kbd><span>Закрыть modal / drawer / popover</span>
        <kbd>Alt+1...6</kbd><span>Переключить saved view</span>
      </div>
    )
  }
  if (modal === 'saveView') {
    return (
      <div className="vr-modal-stack">
        <VellaInput value={saveViewName} onChange={(event) => setSaveViewName(event.target.value)} />
        <div className="vr-preview-note">SavedView сохранит: name, scope, filters, sort, columns, period, brand, owner, access. Сейчас это frontend-only без persistence после reload.</div>
      </div>
    )
  }
  if (modal === 'pmin') {
    return <BulkPreviewTable rows={selectedRows} mode="pmin" />
  }
  if (modal === 'strategy') {
    return <BulkPreviewTable rows={selectedRows} mode="strategy" />
  }
  if (modal === 'liquidation') {
    return <BulkPreviewTable rows={selectedRows} mode="liquidation" />
  }
  return (
    <div className="vr-modal-copy">
      {modal === 'blocked'
        ? 'Этот раздел пока остаётся вне HTML baseline. Для финального переноса нужен отдельный approved screen.'
        : `Выбрано SKU: ${selectedRows.length || 1}. После подтверждения UI изменится сразу, без backend.`}
    </div>
  )
}

function BulkPreviewTable({ rows, mode }: { rows: SkuRow[]; mode: 'pmin' | 'strategy' | 'liquidation' }) {
  const previewRows = rows.length ? rows : initialSkuRows.slice(0, 1)
  return (
    <div className="vr-modal-stack">
      <div className="vr-preview-note">
        {mode === 'pmin' ? 'BulkActionPreview: текущий/new P_min, цена, маржа до/после и blocker до применения.' : mode === 'strategy' ? 'BulkActionPreview: affected count, rule conflicts и manual review перед применением стратегии.' : 'BulkActionPreview: price → projected floor, P_min, прогноз маржи и reason.'}
      </div>
      <div className="vr-preview-table-wrap">
        <table className="vr-preview-table">
          <thead>
            <tr><th>SKU</th><th>Сейчас</th><th>После</th><th>Маржа</th><th>Blocker / reason</th></tr>
          </thead>
          <tbody>
            {previewRows.map((row) => {
              const nextPmin = Math.max(row.pMin, row.price - 180)
              const projectedFloor = Math.max(row.pMin || row.price - 220, Math.round(row.price * 0.82))
              return (
                <tr key={row.id}>
                  <td><span className="vs-sku">{row.sku}</span></td>
                  <td>{mode === 'liquidation' ? rub(row.price) : mode === 'strategy' ? row.strategy : rub(row.pMin)}</td>
                  <td>{mode === 'liquidation' ? rub(projectedFloor) : mode === 'strategy' ? 'Локомотив' : rub(nextPmin)}</td>
                  <td><span className={row.margin < 0 ? 'vr-bad' : 'vr-good'}>{row.margin}% → {mode === 'liquidation' ? Math.max(-12, row.margin - 8) : row.margin + 2}%</span></td>
                  <td>{row.pMin === 0 ? 'нет P_min' : row.margin < 0 ? 'manual review' : 'ok'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function RepricerContent(props: {
  audit: AuditEvent[]
  drawerTab: string
  editingPrice: string
  editingPriceId: string | null
  hiddenColumns: Set<string>
  density: Density
  activeSavedViewId: string
  savedViews: SavedView[]
  worklistFilter: 'all' | 'critical' | 'mine' | 'blocked'
  problemOnly: boolean
  repricerTab: RepricerTab
  rows: SkuRow[]
  selectedIds: Set<string>
  selectedSku: SkuRow | null
  sort: { id: string; direction: 'asc' | 'desc' }
  manager: string
  search: string
  applySavedView: (id: string) => void
  setDrawerSkuId: (id: string | null) => void
  setDrawerTab: (id: string) => void
  setEditingPrice: (value: string) => void
  setEditingPriceId: (id: string | null) => void
  setManager: (value: string) => void
  setModal: (value: ModalKind) => void
  setProblemOnly: (value: boolean) => void
  setSearch: (value: string) => void
  setDensity: (value: Density) => void
  setWorklistFilter: (value: 'all' | 'critical' | 'mine' | 'blocked') => void
  setSelectedIds: (value: Set<string>) => void
  toggleColumn: (id: string) => void
  toggleSelected: (id: string) => void
  toggleSort: (id: string) => void
  savePrice: () => void
}) {
  const kpis = [
    { label: 'SKU в продаже', value: '1 478', meta: `${props.rows.length} в текущем фильтре`, metaTone: 'good' as const, tip: 'Количество SKU зависит от выбранных фильтров.' },
    { label: 'Автоматика', value: String(props.rows.filter((row) => row.status === 'auto').length), meta: 'можно переключать по строкам' },
    { label: 'Ниже P_min', value: String(props.rows.filter((row) => row.price < row.pMin).length), meta: 'требуют подтверждения', metaTone: 'bad' as const },
    { label: 'Корзины 7д', value: String(props.rows.reduce((sum, row) => sum + row.baskets, 0)), meta: 'главный сигнал WB', metaTone: 'good' as const },
  ]

  if (props.repricerTab !== 'products') {
    return <SecondaryRepricerTab tab={props.repricerTab} audit={props.audit} rows={props.rows} setModal={props.setModal} />
  }

  const columns: Array<VellaTableColumn<SkuRow>> = [
    { id: 'sku', label: 'Фото / Артикул', sortable: true, render: (row) => <button className="vr-sku-cell" type="button" onClick={() => props.setDrawerSkuId(row.id)}><span className="vs-sku">{row.sku}</span><span>{row.name}</span></button> },
    { id: 'article', label: 'WB-Арт.', sortable: true, render: (row) => <span className="vs-sku">{row.article}</span> },
    { id: 'status', label: 'Статус товара', render: (row) => <VellaBadge variant={row.status === 'auto' ? 'success' : row.status === 'new' ? 'brand' : 'neutral'}>{row.status === 'auto' ? 'локомотив' : row.status === 'new' ? 'новинка' : 'ручной'}</VellaBadge> },
    { id: 'abc', label: 'ABC', render: (row) => <VellaBadge variant={row.abc === 'CC' ? 'warning' : 'success'}>{row.abc}</VellaBadge> },
    { id: 'promo', label: 'Акция', render: (row) => row.promo ? <VellaBadge variant="warning">да</VellaBadge> : <span>нет</span> },
    { id: 'price', label: 'Цена до СПП', sortable: true, numeric: true, hidden: props.hiddenColumns.has('price'), render: (row) => props.editingPriceId === row.id ? <VellaInlineEdit editing value={props.editingPrice} onChange={props.setEditingPrice} onEdit={() => undefined} onSave={props.savePrice} /> : <button className="vr-price-btn" type="button" onClick={() => { props.setEditingPriceId(row.id); props.setEditingPrice(rub(row.price)) }}><b>{rub(row.price)}</b><span>без изм.</span></button> },
    { id: 'pmin', label: 'P_min', numeric: true, hidden: props.hiddenColumns.has('pmin'), render: (row) => rub(row.pMin) },
    { id: 'margin', label: 'Маржа', sortable: true, numeric: true, hidden: props.hiddenColumns.has('margin'), render: (row) => <span className={row.margin < 0 ? 'vr-bad' : 'vr-good'}>{row.margin > 0 ? '+' : ''}{row.margin}%</span> },
    { id: 'baskets', label: 'Корзины', sortable: true, numeric: true, hidden: props.hiddenColumns.has('baskets'), render: (row) => `${row.baskets} ↑` },
    { id: 'orders', label: 'Заказы', numeric: true, hidden: props.hiddenColumns.has('orders'), render: (row) => `${row.orders} ↑` },
    { id: 'stock', label: 'Остаток WB', numeric: true, hidden: props.hiddenColumns.has('stock'), render: (row) => `${row.stock}%` },
  ]

  return (
    <>
      <VellaMetricStrip items={kpis} />
      <SavedViewsPanel
        activeId={props.activeSavedViewId}
        rows={props.rows}
        savedViews={props.savedViews}
        onApply={props.applySavedView}
        onSave={() => props.setModal('saveView')}
      />
      <VellaToolbar
        left={<>
          <VellaInput data-vella-search="repricer" icon={<Search size={15} />} placeholder="Артикул или название..." value={props.search} onChange={(event) => props.setSearch(event.target.value)} />
          <VellaChip active={!props.problemOnly} onClick={() => props.setProblemOnly(false)}>Все 25</VellaChip>
          <VellaChip active={props.problemOnly} onClick={() => props.setProblemOnly(true)}>Проблемные SKU</VellaChip>
          <VellaTooltip content="Все фильтры меняют строки таблицы в mock state"><span className="vs-help-dot">?</span></VellaTooltip>
        </>}
        right={<>
          <VellaSelect value={props.manager} options={[{ value: 'all', label: 'Все менеджеры' }, { value: 'МД', label: 'Мария Д.' }, { value: 'АП', label: 'Анна П.' }, { value: 'СВ', label: 'Светлана В.' }, { value: 'ИК', label: 'Ирина К.' }]} onChange={props.setManager} />
          <VellaDropdown trigger={<VellaButton><Columns3 size={15} /> Колонки</VellaButton>}>
            {['price', 'pmin', 'margin', 'baskets', 'orders', 'stock'].map((id) => <VellaDropdownItem checked={!props.hiddenColumns.has(id)} key={id} onSelect={() => props.toggleColumn(id)}>{id}</VellaDropdownItem>)}
          </VellaDropdown>
          <div className="vr-density-toggle" aria-label="Плотность таблицы">
            <button className={props.density === 'comfortable' ? 'active' : ''} type="button" onClick={() => props.setDensity('comfortable')}>Комфортно</button>
            <button className={props.density === 'compact' ? 'active' : ''} type="button" onClick={() => props.setDensity('compact')}>Компактно</button>
          </div>
          <VellaButton variant="primary" onClick={() => props.setModal('apply')}>Применить цены · 47</VellaButton>
        </>}
      />
      <div className="vr-advanced-filter">
        <b>Фильтры:</b>
        <VellaChip tone="brand">Футболка</VellaChip>
        <VellaChip tone="brand">Худи</VellaChip>
        <VellaChip tone="brand">Белый</VellaChip>
        <VellaChip onClick={() => props.setProblemOnly(!props.problemOnly)}>Loss / ниже P_min</VellaChip>
        <VellaButton variant="ghost" onClick={() => { props.setSearch(''); props.setProblemOnly(false) }}>Сбросить</VellaButton>
      </div>
      <WorklistPanel filter={props.worklistFilter} rows={props.rows} onFilter={props.setWorklistFilter} onOpenSku={props.setDrawerSkuId} />
      <div className={`vr-table-density ${props.density}`}>
        <VellaTable rows={props.rows} columns={columns} selectedIds={props.selectedIds} sortId={props.sort.id} sortDirection={props.sort.direction} onSort={props.toggleSort} onToggleRow={props.toggleSelected} />
      </div>
      <SkuDrawer audit={props.audit} sku={props.selectedSku} tab={props.drawerTab} onTab={props.setDrawerTab} onClose={() => props.setDrawerSkuId(null)} />
    </>
  )
}

function SavedViewsPanel({ savedViews, activeId, rows, onApply, onSave }: { savedViews: SavedView[]; activeId: string; rows: SkuRow[]; onApply: (id: string) => void; onSave: () => void }) {
  const activeView = savedViews.find((view) => view.id === activeId) ?? savedViews[0]
  return (
    <div className="vr-saved-views-panel">
      <div className="vr-saved-views-left" aria-label="Сохранённые рабочие представления">
        {savedViews.map((view) => (
          <button className={view.id === activeId ? 'active' : ''} key={view.id} type="button" onClick={() => onApply(view.id)}>
            <span>{view.name}</span>
            <span className="vr-saved-view-count">{view.id === activeId ? rows.length : '·'}</span>
          </button>
        ))}
      </div>
      <div className="vr-saved-views-side">
        <span><b>{activeView.owner}</b> · {activeView.access} · {activeView.period} · бренд: {activeView.brand}</span>
        <VellaButton onClick={onSave}>Сохранить как сегмент</VellaButton>
      </div>
    </div>
  )
}

function WorklistPanel({ rows, filter, onFilter, onOpenSku }: { rows: SkuRow[]; filter: 'all' | 'critical' | 'mine' | 'blocked'; onFilter: (value: 'all' | 'critical' | 'mine' | 'blocked') => void; onOpenSku: (id: string) => void }) {
  const items = workQueue
    .filter((item) => rows.some((row) => row.id === item.skuId))
    .filter((item) => filter === 'all' || (filter === 'critical' && item.critical) || (filter === 'mine' && item.owner === 'Мария Д.') || (filter === 'blocked' && item.status === 'заблокировано guardrail'))
  return (
    <div className="vr-worklist">
      <div className="vr-worklist-head">
        <b>Problem SKU worklist</b>
        <div className="vr-worklist-filters">
          {[
            ['all', 'Все'],
            ['critical', 'Критично'],
            ['mine', 'Мои'],
            ['blocked', 'Заблокировано'],
          ].map(([id, label]) => <button className={filter === id ? 'active' : ''} key={id} type="button" onClick={() => onFilter(id as typeof filter)}>{label}</button>)}
        </div>
      </div>
      <div className="vr-worklist-grid">
        {items.map((item) => {
          const row = initialSkuRows.find((sku) => sku.id === item.skuId)
          return (
            <button className="vr-worklist-card" key={item.id} type="button" onClick={() => onOpenSku(item.skuId)}>
              <span className="vs-sku">{row?.sku}</span>
              <b>{item.status}</b>
              <span>{item.owner} · {item.sla} · {item.ageHours}ч</span>
              <span>{item.reasonToAct}</span>
              <em>{item.nextAction}</em>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function SecondaryRepricerTab({ tab, audit, rows, setModal }: { tab: RepricerTab; audit: AuditEvent[]; rows: SkuRow[]; setModal: (value: ModalKind) => void }) {
  if (tab === 'templates') {
    return <div className="vr-card-grid">{['Агрессивный', 'Консервативный', 'Запуск новинки', 'Ночная медиана', 'Ликвидация'].map((name) => <div className="vr-card" key={name}><h3>{name}</h3><p>Готовый набор правил. Применяется массово к выбранным SKU.</p><VellaBadge variant="success">активный</VellaBadge><VellaButton onClick={() => setModal('strategy')}>Настроить</VellaButton></div>)}</div>
  }
  if (tab === 'history') {
    return <div className="vr-list-card">{audit.map((item) => <div className="vr-history-row" key={item.id}><b>{item.at}</b><span>{item.text}</span></div>)}</div>
  }
  if (tab === 'liq') {
    return <div className="vr-card-grid">{rows.filter((row) => row.liquidation !== 'none').map((row) => <div className="vr-card" key={row.id}><h3>{row.sku}</h3><p>{row.name}</p><VellaBadge variant={row.liquidation === 'active' ? 'warning' : 'neutral'}>{row.liquidation === 'active' ? 'в процессе' : 'кандидат'}</VellaBadge><VellaButton variant="danger" onClick={() => setModal('liquidation')}>Запустить</VellaButton></div>)}</div>
  }
  if (tab === 'promos') {
    return <div className="vr-card-grid"><div className="vr-card"><h3>Весенняя распродажа</h3><p>47 SKU, 23 участвуют, 2 требуют P_min confirm.</p><VellaButton onClick={() => setModal('apply')}>Проверить цены</VellaButton></div><div className="vr-card"><h3>Флеш-акция выходного дня</h3><p>XLS пороги не загружены, автоприменение заблокировано.</p><VellaBadge variant="danger">нужен XLS</VellaBadge></div></div>
  }
  return <div className="vr-card"><h3>Правила репрайсера</h3><p>Корзины как главный сигнал, P_min/P_max, ночная медиана, защита акций WB.</p><VellaButton onClick={() => setModal('strategy')}>Сохранить правила</VellaButton></div>
}

function SkuDrawer({ sku, tab, audit, onTab, onClose }: { sku: SkuRow | null; tab: string; audit: AuditEvent[]; onTab: (id: string) => void; onClose: () => void }) {
  const explanation: RecommendationExplanation = {
    trigger: sku?.margin && sku.margin < 0 ? 'Маржа ниже 0% и P_min требует ручного подтверждения.' : 'Корзины выше порога, цена может двигаться по стратегии.',
    freshness: 'WB корзины обновлены сегодня 08:46, цены WB: 08.05 08:21.',
    rule: `Стратегия: ${sku?.strategy ?? 'не выбрана'}. Корзины как главный сигнал, P_min как нижняя граница.`,
    guardrail: sku?.pMin === 0 ? 'Guardrail блокирует автоматику: P_min не задан.' : 'Guardrail активен: не снижать ниже P_min и себестоимости.',
  }
  return (
    <VellaDrawer
      activeTab={tab}
      footer={<><VellaButton variant="ghost" onClick={onClose}>Закрыть</VellaButton><VellaButton variant="primary">Сохранить</VellaButton></>}
      open={Boolean(sku)}
      subtitle={sku ? <span className="vs-sku">{sku.article}</span> : undefined}
      tabs={[{ id: 'overview', label: 'Обзор' }, { id: 'rules', label: 'Правила' }, { id: 'misc', label: 'Прочее' }]}
      title={sku?.sku ?? 'SKU'}
      onOpenChange={(open) => { if (!open) onClose() }}
      onTabChange={onTab}
    >
      {sku ? <div className="vr-drawer-stack">{tab === 'overview' ? <><VellaMetricStrip items={[{ label: 'Цена', value: rub(sku.price), meta: 'без изм.' }, { label: 'P_min', value: sku.pMin ? rub(sku.pMin) : 'не задан', meta: 'нижняя граница' }, { label: 'Маржа', value: `${sku.margin}%`, meta: '+730 ₽' }, { label: 'Корзины', value: sku.baskets, meta: 'за 7 дней' }]} /><div className="vr-card">Расчёт цены, история корзин и комментарии SKU.</div></> : tab === 'rules' ? <RecommendationExplanationCard explanation={explanation} /> : <AuditTrail events={audit} sku={sku} />}</div> : null}
    </VellaDrawer>
  )
}

function RecommendationExplanationCard({ explanation }: { explanation: RecommendationExplanation }) {
  return (
    <div className="vr-explanation-grid">
      <div><b>Trigger</b><span>{explanation.trigger}</span></div>
      <div><b>Freshness</b><span>{explanation.freshness}</span></div>
      <div><b>Rule</b><span>{explanation.rule}</span></div>
      <div><b>Guardrail</b><span>{explanation.guardrail}</span></div>
    </div>
  )
}

function AuditTrail({ events, sku }: { events: AuditEvent[]; sku: SkuRow }) {
  return (
    <div className="vr-list-card">
      {events.map((event) => (
        <div className="vr-audit-row" key={event.id}>
          <div><b>{event.mode === 'manual' ? event.actor : event.mode}</b><span>{event.at} · {event.operation} · {sku.sku}</span></div>
          <p>{event.text}</p>
          <span className="audit-diff">{event.entity} · {event.diff}</span>
          <span className="audit-scope">{event.scope} · {event.reason}</span>
        </div>
      ))}
    </div>
  )
}

function ReportsContent({ reportsTab, audit, digestMode, setModal, downloadReport, pushToast }: { reportsTab: ReportsTab; audit: AuditEvent[]; digestMode: 'period' | 'now'; setModal: (value: ModalKind) => void; downloadReport: () => void; pushToast: (text: string, variant?: Toast['variant']) => void }) {
  const columns: Array<VellaTableColumn<typeof reportRows[number]>> = [
    { id: 'sku', label: 'Позиция', sortable: true, render: (row) => <span className="vs-sku">{row.sku}</span> },
    { id: 'metric', label: 'Метрика', render: (row) => row.metric },
    { id: 'value', label: 'Значение', render: (row) => row.value },
    { id: 'manager', label: 'Менеджер', render: (row) => row.manager },
    { id: 'profit', label: 'Чистая прибыль', numeric: true, render: (row) => row.profit },
    { id: 'recommendation', label: 'Рекомендация', render: (row) => <VellaBadge variant={row.recommendation.includes('стоп') || row.recommendation.includes('ликвидацию') ? 'warning' : 'success'}>{row.recommendation}</VellaBadge> },
  ]
  return (
    <>
      <VellaMetricStrip items={[
        { label: reportsTab === 'ads' ? 'Расход рекламы' : 'Заказы руб', value: reportsTab === 'ads' ? '18 940 ₽' : '13 389 944 ₽', meta: '+6.4% к периоду', metaTone: 'good' },
        { label: reportsTab === 'stock' ? 'Доступно WB' : 'Заказы шт', value: reportsTab === 'stock' ? '4 291' : '4 299', meta: '+2.9%' },
        { label: 'Чистая прибыль', value: '1 271 443 ₽', meta: '−1.8%', metaTone: 'bad' },
        { label: 'Кандидаты на действие', value: '2', meta: '21+ дн. и ДРР ≥ 25%', metaTone: 'bad' },
      ]} />
      {reportsTab === 'digest' ? (
        <div className="vr-row-wrap" aria-label="Режим дайджеста">
          <VellaChip active={digestMode === 'period'}>Период</VellaChip>
          <VellaChip active={digestMode === 'now'}>Сейчас</VellaChip>
        </div>
      ) : null}
      <div className="vr-report-grid">
        <div className="vr-card"><h3>{reportsTab === 'digest' && digestMode === 'now' ? 'Критичные события' : 'План-факт'}</h3><p>{reportsTab === 'digest' && digestMode === 'now' ? 'Цена, акции, РНП, остатки и маржа сразу ведут в нужный раздел.' : 'План, факт и прогноз по текущему периоду.'}</p><VellaBadge variant={reportsTab === 'digest' && digestMode === 'now' ? 'warning' : 'brand'}>{reportsTab === 'digest' && digestMode === 'now' ? 'в работу' : 'план-факт'}</VellaBadge></div>
        <div className="vr-card"><h3>{reportsTab === 'digest' && digestMode === 'now' ? 'Оперативный монитор' : 'Требует внимания'}</h3><div className="vr-bars"><span style={{ width: '83%' }} /><span style={{ width: '58%' }} /><span style={{ width: '44%' }} /></div></div>
      </div>
      <VellaToolbar
        left={<><VellaInput icon={<Search size={15} />} placeholder="Поиск по таблице" /><VellaChip active>Бренды: Все</VellaChip><VellaChip onClick={() => pushToast('Комментарий сохранён в mock state', 'success')}>Комментарии</VellaChip></>}
        right={reportsTab === 'digest' && digestMode === 'now' ? null : <><VellaButton onClick={() => setModal('export')}><Download size={15} /> Экспорт</VellaButton><VellaButton variant="primary" onClick={downloadReport}>Скачать XLS</VellaButton></>}
      />
      <VellaTable rows={reportRows} columns={columns} />
      <div className="vr-list-card">{audit.slice(0, 4).map((item) => <div className="vr-history-row" key={item.id}><b>{item.at}</b><span>{item.text}</span></div>)}</div>
    </>
  )
}

function NotificationsContent({ notifications, query, selectedId, setNotifications, setQuery, setSelectedId, downloadReport, openRoute }: { notifications: NotificationEvent[]; query: string; selectedId: string | null; setNotifications: Dispatch<SetStateAction<NotificationEvent[]>>; setQuery: (value: string) => void; setSelectedId: (value: string) => void; downloadReport: (item?: NotificationEvent) => void; openRoute: (routePath: string) => void }) {
  const filtered = notifications.filter((item) => !query.trim() || `${item.title} ${item.details} ${item.manager} ${item.source}`.toLowerCase().includes(query.toLowerCase()))
  const selected = filtered.find((item) => item.id === selectedId) ?? filtered[0]
  function markAllRead() {
    setNotifications((current) => current.map((item) => ({ ...item, readAt: item.readAt ?? new Date().toISOString() })))
  }
  return (
    <>
      <VellaMetricStrip items={[
        { label: 'Новые', value: notifications.filter((item) => !item.readAt).length, meta: 'требуют просмотра' },
        { label: 'Критичные', value: notifications.filter((item) => item.severity === 'critical' && !item.readAt).length, meta: 'SLA, P_min, источники', metaTone: 'bad' },
        { label: 'За период', value: filtered.length, meta: 'последние 7 дн.' },
        { label: 'Последний дайджест', value: '08:15', meta: 'Сводный дайджест WB', metaTone: 'good' },
      ]} />
      <VellaToolbar
        left={<><VellaInput icon={<Search size={15} />} placeholder="SKU, менеджер, раздел, текст..." value={query} onChange={(event) => setQuery(event.target.value)} /><VellaChip active>Все категории</VellaChip><VellaChip>Отчёты</VellaChip><VellaChip>Цены</VellaChip></>}
        right={<><VellaButton onClick={markAllRead}><CheckCheck size={15} /> Прочитать все</VellaButton><VellaButton><Download size={15} /> Экспорт</VellaButton></>}
      />
      <div className="vr-notifications">
        <VellaTable
          rows={filtered}
          columns={[
            { id: 'title', label: 'Событие', render: (item) => <button className="vr-notification-title" type="button" onClick={() => setSelectedId(item.id)}><b>{item.title}</b><span>{item.details}</span></button> },
            { id: 'category', label: 'Категория', render: (item) => <VellaBadge variant={item.category === 'reports' ? 'brand' : 'neutral'}>{item.category}</VellaBadge> },
            { id: 'manager', label: 'Менеджер', render: (item) => item.manager },
            { id: 'source', label: 'Источник', render: (item) => item.source },
            { id: 'status', label: 'Статус', render: (item) => <VellaBadge variant={item.readAt ? 'neutral' : 'brand'}>{item.readAt ? 'прочитано' : 'новое'}</VellaBadge> },
          ]}
        />
        <aside className="vr-notification-detail">
          {selected ? <>
            <h3>{selected.title}</h3>
            <p>{selected.details}</p>
            <div className="vr-kv"><span>Менеджер</span><b>{selected.manager}</b></div>
            <div className="vr-kv"><span>Сущность</span><b>{selected.entityId}</b></div>
            {selected.reportFile ? <div className="vr-report-file"><b>Файл отчёта</b><span>{selected.reportFile.fileName}</span><span>{selected.reportFile.period} · {selected.reportFile.rows.toLocaleString('ru-RU')} строк</span><VellaButton variant="primary" onClick={() => downloadReport(selected)}><Download size={15} /> Скачать ещё раз</VellaButton></div> : null}
            <div className="vr-row-wrap"><VellaButton onClick={() => setNotifications((current) => current.map((item) => item.id === selected.id ? { ...item, readAt: item.readAt ?? new Date().toISOString() } : item))}>Пометить прочитанным</VellaButton>{selected.route ? <VellaButton variant="ghost" onClick={() => openRoute(selected.route ?? '')}><ExternalLink size={15} /> Открыть модуль</VellaButton> : null}</div>
          </> : <p>Выберите уведомление.</p>}
        </aside>
      </div>
    </>
  )
}
