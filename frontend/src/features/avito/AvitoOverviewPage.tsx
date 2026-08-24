import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowRight,
  CalendarDays,
  CircleDollarSign,
  Download,
  ExternalLink,
  Eye,
  FileWarning,
  Heart,
  MessageSquare,
  PackageCheck,
  Phone,
  RefreshCw,
  Search,
  ShieldAlert,
  Star,
  Wallet,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { AvitoModuleTabs } from './AvitoShared'

type Severity = 'critical' | 'warning' | 'info'
type Source = 'account' | 'chat' | 'review' | 'listing' | 'wallet' | 'order'
type KpiState = 'ok' | 'warning' | 'critical' | 'unavailable'
type DashboardPeriod = 'today' | '7d' | '14d' | '30d' | 'custom'
type TopMetric = 'views' | 'contacts' | 'orders'
type Density = 'comfortable' | 'compact'
type QuickFilter = 'all' | 'safe' | 'stale' | 'risk'
type DrawerTab = 'reason' | 'data' | 'actions' | 'audit'

type Kpi = {
  id: string
  label: string
  value: string
  secondary: string
  state: KpiState
  tooltip: string
}

type DashboardMetric = {
  id: string
  label: string
  values: Record<DashboardPeriod, { value: string; previous: string; delta: string; detail: string }>
  source: string
  tone: 'blue' | 'green' | 'pink' | 'amber'
  points: number[]
}

type TopProduct = {
  id: string
  name: string
  brand: string
  views: string
  contacts: string
  orders: string
  url: string
}

type Blocker = {
  id: string
  severity: Severity
  source: Source
  account: string
  title: string
  reason: string
  freshness: string
  owner: string
  nextAction: string
  audit: string
  blocked: string[]
  stillWorks: string[]
}

const periodOptions: Array<{ value: DashboardPeriod; label: string }> = [
  { value: 'today', label: '1 день' },
  { value: '7d', label: '7 дней' },
  { value: '14d', label: '14 дней' },
  { value: '30d', label: '30 дней' },
]

const calendarWeeks = [
  ['20', '21', '22', '23', '24', '25', '26'],
  ['27', '28', '29', '30', '01', '02', '03'],
]

const dashboardMetrics: DashboardMetric[] = [
  {
    id: 'views',
    label: 'Просмотры',
    values: {
      today: { value: '1 460', previous: 'вчера: 1 902', delta: '-23.2%', detail: '0.89% в контакт · пик в 14:00' },
      '7d': { value: '10 842', previous: 'пред. 7 дней: 12 406', delta: '-12.6%', detail: '1.02% в контакт · 4 аккаунта растут' },
      '14d': { value: '21 980', previous: 'пред. 14 дней: 24 510', delta: '-10.3%', detail: '1.01% в контакт · 3 аккаунта просели' },
      '30d': { value: '43 618', previous: 'пред. 30 дней: 39 880', delta: '+9.4%', detail: '0.96% в контакт · топ-5 дают 50%' },
      custom: { value: '8 214', previous: '24.04—30.04: 8 960', delta: '-8.3%', detail: '25.04—01.05 · 0.98% в контакт' },
    },
    source: 'Статистика Авито · все аккаунты',
    tone: 'blue',
    points: [42, 46, 44, 30, 34, 45, 61, 74, 70, 84, 58, 26, 25, 25],
  },
  {
    id: 'contacts',
    label: 'Контакты',
    values: {
      today: { value: '13', previous: 'вчера: 38', delta: '-65.8%', detail: '3 заказа · 23.1% в заказ' },
      '7d': { value: '118', previous: 'пред. 7 дней: 104', delta: '+13.5%', detail: '27 заказов · 22.9% в заказ' },
      '14d': { value: '226', previous: 'пред. 14 дней: 208', delta: '+8.7%', detail: '52 заказа · 23.0% в заказ' },
      '30d': { value: '421', previous: 'пред. 30 дней: 388', delta: '+8.5%', detail: '93 заказа · 22.1% в заказ' },
      custom: { value: '84', previous: '24.04—30.04: 79', delta: '+6.3%', detail: '25.04—01.05 · 19 заказов' },
    },
    source: 'Чаты и звонки',
    tone: 'green',
    points: [35, 35, 12, 12, 36, 14, 39, 18, 42, 61, 34, 12, 12, 12],
  },
  {
    id: 'favorites',
    label: 'Избранное',
    values: {
      today: { value: '202', previous: 'вчера: 368', delta: '-45.1%', detail: '6 товаров дали 61% избранного' },
      '7d': { value: '1 484', previous: 'пред. 7 дней: 1 210', delta: '+22.6%', detail: '12 товаров перешли порог спроса' },
      '14d': { value: '2 910', previous: 'пред. 14 дней: 2 420', delta: '+20.2%', detail: 'избранное растёт быстрее контактов' },
      '30d': { value: '5 906', previous: 'пред. 30 дней: 4 982', delta: '+18.5%', detail: 'избранное растёт быстрее просмотров' },
      custom: { value: '1 118', previous: '24.04—30.04: 930', delta: '+20.2%', detail: '25.04—01.05 · спрос без рекламы' },
    },
    source: 'Статистика объявлений',
    tone: 'pink',
    points: [36, 42, 34, 39, 38, 62, 55, 58, 76, 45, 31, 31, 31, 31],
  },
  {
    id: 'spend',
    label: 'Расходы',
    values: {
      today: { value: '3 658 ₽', previous: 'вчера: 7 630 ₽', delta: '-52.1%', detail: '2.51 ₽ за просмотр' },
      '7d': { value: '31 420 ₽', previous: 'пред. 7 дней: 29 870 ₽', delta: '+5.2%', detail: '2.90 ₽ за просмотр · 2 кампании дорогие' },
      '14d': { value: '62 850 ₽', previous: 'пред. 14 дней: 57 400 ₽', delta: '+9.5%', detail: '2.86 ₽ за просмотр · лимит 74%' },
      '30d': { value: '126 900 ₽', previous: 'пред. 30 дней: 119 300 ₽', delta: '+6.4%', detail: '3.02 ₽ за просмотр · лимит 82%' },
      custom: { value: '24 770 ₽', previous: '24.04—30.04: 22 980 ₽', delta: '+7.8%', detail: '25.04—01.05 · лимит 68%' },
    },
    source: 'Продвижение и расходы',
    tone: 'amber',
    points: [28, 36, 29, 32, 35, 43, 50, 50, 72, 34, 38, 24, 24, 24],
  },
]

const topProducts: TopProduct[] = [
  { id: '1', name: 'Худи yohji yamamoto pour homme', brand: 'Bless T', views: '7 692', contacts: '51', orders: '8', url: 'https://www.avito.ru/all?q=%D0%A5%D1%83%D0%B4%D0%B8+yohji+yamamoto+pour+homme' },
  { id: '2', name: 'Худи alpha industries', brand: 'Bless T', views: '6 330', contacts: '61', orders: '5', url: 'https://www.avito.ru/all?q=%D0%A5%D1%83%D0%B4%D0%B8+alpha+industries' },
  { id: '3', name: 'Футболка desotive 808 droland miller girl black', brand: 'Bless T', views: '3 345', contacts: '24', orders: '9', url: 'https://www.avito.ru/all?q=%D0%A4%D1%83%D1%82%D0%B1%D0%BE%D0%BB%D0%BA%D0%B0+desotive+808+droland+miller+girl+black' },
  { id: '4', name: 'Футболка y2k opium archive', brand: 'Bless T', views: '2 567', contacts: '33', orders: '3', url: 'https://www.avito.ru/all?q=%D0%A4%D1%83%D1%82%D0%B1%D0%BE%D0%BB%D0%BA%D0%B0+y2k+opium+archive' },
  { id: '5', name: 'Худи Рыночные отношения', brand: 'Bless T', views: '2 037', contacts: '18', orders: '7', url: 'https://www.avito.ru/all?q=%D0%A5%D1%83%D0%B4%D0%B8+%D0%A0%D1%8B%D0%BD%D0%BE%D1%87%D0%BD%D1%8B%D0%B5+%D0%BE%D1%82%D0%BD%D0%BE%D1%88%D0%B5%D0%BD%D0%B8%D1%8F' },
]

const blockerRoutes: Record<Source, string> = {
  account: '/avito/accounts',
  chat: '/avito/chats',
  review: '/avito/reviews',
  listing: '/avito/listings',
  wallet: '/avito/wallets',
  order: '/orders',
}

const hourlyViews = {
  today: [62, 74, 67, 18, 34, 26, 58, 74, 105, 128, 111, 143, 105, 138, 176, 109, 55, 0, 0, 0, 0, 0, 0, 0],
  yesterday: [106, 142, 70, 47, 33, 24, 22, 63, 118, 131, 111, 126, 144, 131, 146, 170, 105, 129, 104, 106, 151, 176, 178, 163],
  week: [92, 98, 47, 34, 31, 27, 58, 73, 113, 119, 157, 133, 169, 140, 165, 156, 117, 171, 145, 181, 160, 166, 219, 162],
}

const hourlyOrders = {
  today: [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  yesterday: [0, 1, 0, 0, 0, 0, 0, 0, 0, 2, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 2, 2, 1, 0],
  week: [1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 5, 0, 1, 1, 1, 1, 0, 0, 0],
}

const kpis: Kpi[] = [
  {
    id: 'accounts',
    label: 'Аккаунты',
    value: '12/15',
    secondary: '3 требуют обновления',
    state: 'warning',
    tooltip: 'Готовность считается по авторизации, тарифу, автозагрузке, чатам, статистике и кошельку.',
  },
  {
    id: 'chats',
    label: 'Непрочитанные чаты',
    value: '46',
    secondary: '8 новых',
    state: 'warning',
    tooltip: 'Показывает только диалоги в доступных аккаунтах. Отправка с overview недоступна.',
  },
  {
    id: 'bot',
    label: 'Черновики бота',
    value: '19',
    secondary: '5 на проверке',
    state: 'warning',
    tooltip: 'Бот готовит черновики. Внешняя отправка требует согласования на экране чата.',
  },
  {
    id: 'reviews',
    label: 'Отзывы без ответа',
    value: '14',
    secondary: '3 с рейтингом <=3',
    state: 'critical',
    tooltip: 'Черновики ответов для отзывов. Ответы и удаление недоступны без отдельного согласования.',
  },
  {
    id: 'wallets',
    label: 'Низкий баланс',
    value: '4',
    secondary: 'мин. 320 ₽',
    state: 'critical',
    tooltip: 'Точные суммы видны финансам, владельцу и админу. Автопополнение не включается без проверки интеграции.',
  },
  {
    id: 'xml',
    label: 'XML/объявления',
    value: '7',
    secondary: '2 устарели, 5 на проверке',
    state: 'critical',
    tooltip: 'Публикация неполного XML-фида заблокирована. Защита от случайного снятия объявлений включена.',
  },
  {
    id: 'orders',
    label: 'Заказы/возвраты',
    value: '11',
    secondary: '6 без маппинга',
    state: 'warning',
    tooltip: 'Заказы доступны как чтение и очередь производства. QR-возвраты требуют отдельной проверки интеграции.',
  },
]

const blockers: Blocker[] = [
  {
    id: 'xml-missing',
    severity: 'critical',
    source: 'listing',
    account: 'Bless T · Москва',
    title: '5 активных объявлений отсутствуют в XML',
    reason: 'Количество объявлений в фиде не совпадает с активным реестром. Публикация заблокирована до проверки.',
    freshness: 'устарело 2ч 14м',
    owner: 'Мария',
    nextAction: 'Открыть проверку',
    audit: '09:41 · защита XML остановила синхронизацию',
    blocked: ['публикация XML', 'применение цен', 'массовая привязка фото'],
    stillWorks: ['таблица на чтение', 'редактирование черновика', 'экспорт расхождений'],
  },
  {
    id: 'wallet-low',
    severity: 'critical',
    source: 'wallet',
    account: 'Anomie Studio · Скидки',
    title: 'Баланс 320 ₽ ниже порога 1 000 ₽',
    reason: 'Баланс обновлен, но пополнение через интеграцию не подтверждено. Создана ручная задача для финансов.',
    freshness: '09:42',
    owner: 'Максим',
    nextAction: 'Открыть кошелёк',
    audit: '09:42 · предупреждение о низком балансе',
    blocked: ['автопополнение', 'платеж'],
    stillWorks: ['ручная задача', 'журнал баланса', 'изменение порога с аудитом'],
  },
  {
    id: 'messenger-stale',
    severity: 'warning',
    source: 'chat',
    account: 'Bless T · Уличная одежда',
    title: 'Чаты не обновлялись 18 минут',
    reason: 'Включен резервный опрос. Быстрая доставка событий недоступна до проверки тарифа и прав доступа.',
    freshness: '18м назад',
    owner: 'Администратор',
    nextAction: 'Проверить синхронизацию',
    audit: '09:24 · задержка обновления чатов',
    blocked: ['отправка ботом в реальном времени'],
    stillWorks: ['чтение кэша чатов', 'ручное обновление', 'шаблоны'],
  },
  {
    id: 'reviews-negative',
    severity: 'warning',
    source: 'review',
    account: 'Anomie Studio · Москва',
    title: '3 негативных отзыва без ответа',
    reason: 'Черновики ответов готовы, но один черновик заблокирован правилом “обещание доставки”.',
    freshness: '09:38',
    owner: 'Мария',
    nextAction: 'Открыть отзывы',
    audit: '09:39 · проверка черновика ответа',
    blocked: ['публикация ответа'],
    stillWorks: ['редактирование черновика', 'запрос согласования', 'назначение ответственного'],
  },
  {
    id: 'orders-mapping',
    severity: 'info',
    source: 'order',
    account: 'Bless T · Заказы',
    title: '6 заказов требуют сопоставление артикула',
    reason: 'Артикул продавца не совпал с форматом `[Тип][Цвет]BT_[Номер]`.',
    freshness: '09:35',
    owner: 'Производство',
    nextAction: 'Открыть заказы',
    audit: '09:35 · синхронизация заказов требует проверки',
    blocked: ['массовый экспорт затронутых строк'],
    stillWorks: ['ручной маппинг', 'просмотр заказа', 'печать остальных строк'],
  },
]

const sourceLabels: Record<Source, string> = {
  account: 'Аккаунты',
  chat: 'Чаты',
  review: 'Отзывы',
  listing: 'Объявления',
  wallet: 'Кошельки',
  order: 'Заказы',
}

const severityLabels: Record<Severity, string> = {
  critical: 'Блокировка',
  warning: 'Проверка',
  info: 'Событие',
}

const severityStyles: Record<Severity, string> = {
  critical: 'border-red-200 bg-red-50 text-red-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
}

const kpiStyles: Record<KpiState, string> = {
  ok: 'text-emerald-700',
  warning: 'text-amber-700',
  critical: 'text-red-700',
  unavailable: 'text-slate-500',
}

const metricToneStyles: Record<DashboardMetric['tone'], { accent: string; bg: string; border: string; stroke: string }> = {
  blue: { accent: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-100', stroke: '#2563EB' },
  green: { accent: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-100', stroke: '#059669' },
  pink: { accent: 'text-pink-700', bg: 'bg-pink-50', border: 'border-pink-100', stroke: '#DB2777' },
  amber: { accent: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-100', stroke: '#D97706' },
}

function sourceIcon(source: Source) {
  if (source === 'chat') return MessageSquare
  if (source === 'review') return Star
  if (source === 'listing') return FileWarning
  if (source === 'wallet') return Wallet
  if (source === 'order') return PackageCheck
  return ShieldAlert
}

function polyline(points: number[], width: number, height: number) {
  const max = Math.max(...points)
  const min = Math.min(...points)
  const range = Math.max(max - min, 1)
  return points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width
      const y = height - ((point - min) / range) * height
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

function scaledY(point: number, height: number, min: number, max: number) {
  const range = Math.max(max - min, 1)
  return height - ((point - min) / range) * height
}

function scaledPolyline(points: number[], width: number, height: number, min: number, max: number) {
  return points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width
      return `${x.toFixed(1)},${scaledY(point, height, min, max).toFixed(1)}`
    })
    .join(' ')
}

function scaledArea(points: number[], width: number, height: number, min: number, max: number) {
  return `0,${height} ${scaledPolyline(points, width, height, min, max)} ${width},${height}`
}

function metricIcon(id: string) {
  if (id === 'views') return Eye
  if (id === 'contacts') return Phone
  if (id === 'favorites') return Heart
  return CircleDollarSign
}

function Sparkline({ points, stroke }: { points: number[]; stroke: string }) {
  return (
    <svg className="mt-1.5 h-5 w-full" viewBox="0 0 160 28" preserveAspectRatio="none" aria-hidden="true">
      <polyline
        fill="none"
        points={polyline(points, 160, 23)}
        stroke={stroke}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function PeriodControl({ value, onChange, compact = false }: { value: DashboardPeriod; onChange: (value: DashboardPeriod) => void; compact?: boolean }) {
  const [calendarOpen, setCalendarOpen] = useState(false)
  const [rangeStart, setRangeStart] = useState('25')
  const [rangeEnd, setRangeEnd] = useState('01')
  return (
    <div className="relative inline-flex shrink-0 items-center gap-1 rounded-[10px] border border-slate-200 bg-slate-50 p-1">
      {periodOptions.map((option) => (
        <button
          key={option.value}
          className={cn(
            'rounded-lg font-semibold transition hover:bg-white hover:text-slate-900',
            compact ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-[12.5px]',
            value === option.value ? 'bg-blue-600 text-white shadow-[0_6px_16px_rgba(37,99,235,0.24)] hover:bg-blue-700 hover:text-white' : 'text-slate-500',
          )}
          type="button"
          onClick={() => onChange(option.value)}
          aria-pressed={value === option.value}
        >
          {option.label}
        </button>
      ))}
      <button
        className={cn(
          'inline-flex items-center gap-1.5 rounded-lg font-semibold transition hover:bg-white hover:text-slate-900',
          compact ? 'h-7 px-2.5 text-xs' : 'h-8 px-3 text-[12.5px]',
          value === 'custom' ? 'bg-blue-600 text-white shadow-[0_6px_16px_rgba(37,99,235,0.24)] hover:bg-blue-700 hover:text-white' : 'text-slate-500',
        )}
        type="button"
        onClick={() => setCalendarOpen((open) => !open)}
        aria-expanded={calendarOpen}
      >
        <CalendarDays className="size-3.5" />
        {value === 'custom' ? '25.04 — 01.05' : 'Свой'}
      </button>
      {calendarOpen && (
        <div className="absolute right-0 top-[calc(100%+6px)] z-30 w-[286px] rounded-xl border border-slate-200 bg-white p-3 text-xs shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="font-bold text-slate-950">Период аналитики</div>
              <div className="mt-0.5 text-[11px] text-slate-500">25 апреля — 1 мая 2026</div>
            </div>
            <span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-bold text-blue-700">7 дней</span>
          </div>
          <div className="mb-2 grid grid-cols-7 text-center text-[10px] font-bold uppercase text-slate-400">
            {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((day) => <span key={day}>{day}</span>)}
          </div>
          <div className="grid gap-1">
            {calendarWeeks.map((week) => (
              <div className="grid grid-cols-7 gap-1" key={week.join('-')}>
                {week.map((day) => {
                  const active = day === rangeStart || day === rangeEnd
                  const inRange = ['25', '26', '27', '28', '29', '30', '01'].includes(day)
                  return (
                    <button
                      key={day}
                      className={cn(
                        'h-8 rounded-lg text-xs font-bold transition',
                        active ? 'bg-blue-600 text-white' : inRange ? 'bg-blue-50 text-blue-700 hover:bg-blue-100' : 'text-slate-500 hover:bg-slate-50',
                      )}
                      type="button"
                      onClick={() => {
                        if (day > '24' || day === '01') setRangeEnd(day)
                        else setRangeStart(day)
                      }}
                    >
                      {day}
                    </button>
                  )
                })}
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between gap-2">
            <button className="h-8 rounded-lg border border-slate-200 px-3 font-semibold text-slate-600 hover:bg-slate-50" type="button" onClick={() => setCalendarOpen(false)}>
              Отмена
            </button>
            <button
              className="h-8 rounded-lg bg-blue-600 px-3 font-semibold text-white hover:bg-blue-700"
              type="button"
              onClick={() => {
                onChange('custom')
                setCalendarOpen(false)
              }}
            >
              Применить
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function DashboardMetricCard({ metric, period, active, onSelect }: { metric: DashboardMetric; period: DashboardPeriod; active: boolean; onSelect: () => void }) {
  const tone = metricToneStyles[metric.tone]
  const Icon = metricIcon(metric.id)
  const current = metric.values[period]
  return (
    <button
      className={cn(
        'rounded-lg border bg-white p-3 text-left shadow-sm transition hover:border-blue-200 hover:bg-blue-50/30',
        active ? 'border-blue-300 ring-2 ring-blue-100' : tone.border,
      )}
      type="button"
      onClick={onSelect}
      aria-pressed={active}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={cn('inline-flex size-6 items-center justify-center rounded-md', tone.bg, tone.accent)}>
            <Icon className="size-3.5" />
          </span>
          <div>
            <div className="text-[11px] font-bold text-slate-700">{metric.label}</div>
            <div className="mt-0.5 text-[11px] text-slate-400">{metric.source}</div>
          </div>
        </div>
        <span className={cn('rounded-full px-2 py-0.5 text-[11px] font-bold', current.delta.startsWith('+') ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600')}>{current.delta}</span>
      </div>
      <div className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] items-end gap-2">
        <div>
          <div className="text-[22px] font-extrabold leading-none text-slate-950">{current.value}</div>
          <div className="mt-1 text-xs text-slate-500">{current.previous}</div>
        </div>
        <span className={cn('rounded-lg px-2 py-0.5 text-[11px] font-bold', tone.bg, tone.accent)}>
          свежие
        </span>
      </div>
      <Sparkline points={metric.points} stroke={tone.stroke} />
      <div className="mt-1 truncate text-[11px] font-medium text-slate-500">
        {current.detail}
      </div>
    </button>
  )
}

function scaleSeries(points: number[], range: DashboardPeriod) {
  const factor = range === 'today' ? 1 : range === '7d' ? 5.8 : range === '14d' ? 10.8 : range === 'custom' ? 6.4 : 22
  return points.map((point, index) => Math.round(point * factor + (range === '30d' ? (index % 5) * 14 : 0)))
}

function xAxisLabels(range: DashboardPeriod) {
  if (range === 'today') return ['00:00', '06:00', '12:00', '18:00', '23:00']
  if (range === '7d') return ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
  if (range === '14d') return ['18.04', '21.04', '24.04', '27.04', '30.04', '01.05']
  if (range === 'custom') return ['25.04', '26.04', '27.04', '28.04', '29.04', '30.04', '01.05']
  return ['01.04', '07.04', '14.04', '21.04', '30.04']
}

function activeXAxisLabel(range: DashboardPeriod, index: number) {
  if (range === 'today') return `${String(index).padStart(2, '0')}:00`
  const labels = xAxisLabels(range)
  return labels[Math.min(labels.length - 1, Math.round((index / 23) * (labels.length - 1)))]
}

function LineChart({
  title,
  primary,
  secondary,
  tertiary,
  periodSummaries,
}: {
  title: string
  primary: number[]
  secondary: number[]
  tertiary: number[]
  periodSummaries: Record<DashboardPeriod, string>
}) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const [range, setRange] = useState<DashboardPeriod>('today')
  const seriesLabels =
    range === 'today'
      ? ['Сегодня', 'Вчера', 'Неделю назад']
      : range === '7d'
        ? ['Текущие 7', 'Пред. 7', 'Неделя ранее']
        : range === '14d'
          ? ['Текущие 14', 'Пред. 14', 'Двумя нед. ранее']
          : range === 'custom'
            ? ['25.04—01.05', 'Пред. период', 'Неделей ранее']
            : ['Текущие 30', 'Пред. 30', 'Месяц ранее']
  const visiblePrimary = useMemo(() => scaleSeries(primary, range), [primary, range])
  const visibleSecondary = useMemo(() => scaleSeries(secondary, range), [secondary, range])
  const visibleTertiary = useMemo(() => scaleSeries(tertiary, range), [tertiary, range])
  const allPoints = [...visiblePrimary, ...visibleSecondary, ...visibleTertiary]
  const max = Math.max(...allPoints)
  const min = Math.min(...allPoints)
  const chartWidth = 960
  const chartHeight = 190
  const activeX = activeIndex === null ? null : (activeIndex / Math.max(primary.length - 1, 1)) * chartWidth
  const activeLabel = activeIndex === null ? null : activeXAxisLabel(range, activeIndex)
  const tooltipLeft = activeIndex === null ? '50%' : `clamp(96px, ${(activeIndex / Math.max(primary.length - 1, 1)) * 100}%, calc(100% - 96px))`
  const chartId = title.includes('заказ') ? 'orders' : 'views'
  const summaryLabel = periodSummaries[range]

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-950">{title}</h2>
          <p className="mt-1 text-xs text-slate-500">
            {range === 'today' ? 'Почасовая динамика' : range === 'custom' ? 'Выбранный календарный диапазон' : 'Динамика по дням выбранного периода'}
          </p>
        </div>
        <PeriodControl value={range} onChange={setRange} compact />
      </div>
      <div className="relative">
      <svg className="h-[244px] w-full overflow-visible" viewBox="0 0 960 244" preserveAspectRatio="none" role="img" aria-label={title} onMouseLeave={() => setActiveIndex(null)}>
        <defs>
          <linearGradient id={`${chartId}-primary-fill`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2563EB" stopOpacity="0.22" />
            <stop offset="70%" stopColor="#2563EB" stopOpacity="0.05" />
            <stop offset="100%" stopColor="#2563EB" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={`${chartId}-secondary-fill`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#DB2777" stopOpacity="0.14" />
            <stop offset="100%" stopColor="#DB2777" stopOpacity="0" />
          </linearGradient>
          <linearGradient id={`${chartId}-tertiary-fill`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#16A34A" stopOpacity="0.10" />
            <stop offset="100%" stopColor="#16A34A" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((line) => (
          <line key={line} x1="0" x2="960" y1={line * 50 + 10} y2={line * 50 + 10} stroke="#E5E7EB" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        ))}
        {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((line) => (
          <line key={line} x1={line * 120} x2={line * 120} y1="10" y2="210" stroke="#F1F5F9" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        ))}
        <polygon fill={`url(#${chartId}-tertiary-fill)`} points={scaledArea(visibleTertiary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        <polygon fill={`url(#${chartId}-secondary-fill)`} points={scaledArea(visibleSecondary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        <polygon fill={`url(#${chartId}-primary-fill)`} points={scaledArea(visiblePrimary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        <polyline fill="none" stroke="#2563EB" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.25" vectorEffect="non-scaling-stroke" points={scaledPolyline(visiblePrimary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        <polyline fill="none" stroke="#DB2777" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" vectorEffect="non-scaling-stroke" points={scaledPolyline(visibleSecondary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        <polyline fill="none" stroke="#16A34A" strokeDasharray="6 6" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" vectorEffect="non-scaling-stroke" points={scaledPolyline(visibleTertiary, chartWidth, chartHeight, min, max)} transform="translate(0 10)" />
        {visiblePrimary.map((_, index) => (
          <rect
            key={index}
            x={(index / visiblePrimary.length) * chartWidth}
            y="10"
            width={chartWidth / visiblePrimary.length}
            height="200"
            fill="transparent"
            className="cursor-crosshair hover:fill-blue-500/5"
            onMouseEnter={() => setActiveIndex(index)}
            onMouseMove={() => setActiveIndex(index)}
          />
        ))}
        {activeIndex !== null && activeX !== null && (
          <>
            <line x1={activeX} x2={activeX} y1="10" y2="210" stroke="#94A3B8" strokeDasharray="4 4" />
            <circle cx={activeX} cy={scaledY(visiblePrimary[activeIndex], chartHeight, min, max) + 10} r="5" fill="#2563EB" stroke="#fff" strokeWidth="2" />
            <circle cx={activeX} cy={scaledY(visibleSecondary[activeIndex], chartHeight, min, max) + 10} r="4" fill="#DB2777" stroke="#fff" strokeWidth="2" />
            <circle cx={activeX} cy={scaledY(visibleTertiary[activeIndex], chartHeight, min, max) + 10} r="4" fill="#16A34A" stroke="#fff" strokeWidth="2" />
          </>
        )}
      </svg>
      {activeIndex !== null && (
        <div
          className="pointer-events-none absolute top-4 z-20 w-48 -translate-x-1/2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg"
          style={{ left: tooltipLeft }}
        >
          <div className="border-b border-slate-100 pb-2 font-bold text-slate-950">{activeLabel}</div>
          {[
            ['bg-blue-600', seriesLabels[0], visiblePrimary[activeIndex]],
            ['bg-pink-600', seriesLabels[1], visibleSecondary[activeIndex]],
            ['bg-emerald-600', seriesLabels[2], visibleTertiary[activeIndex]],
          ].map(([color, label, value]) => (
            <div className="mt-2 flex items-center gap-2" key={label}>
              <span className={cn('size-2.5 rounded-full', color as string)} aria-hidden="true" />
              <span className="min-w-0 flex-1 text-slate-600">{label}</span>
              <b className="font-bold text-slate-950">{value}</b>
            </div>
          ))}
        </div>
      )}
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          {xAxisLabels(range).map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
        <div className="text-center text-[11px] font-semibold text-slate-700">{summaryLabel}</div>
      </div>
    </section>
  )
}

function StatusPill({ severity }: { severity: Severity }) {
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-1 text-[11px] font-semibold', severityStyles[severity])}>
      {severityLabels[severity]}
    </span>
  )
}

function AccountBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm">
      <span className="size-2 rounded-full bg-blue-500" aria-hidden="true" />
      {name}
    </span>
  )
}

export function AvitoOverviewPage() {
  const navigate = useNavigate()
  const [severityFilter, setSeverityFilter] = useState<Severity | 'all'>('all')
  const [sourceFilter, setSourceFilter] = useState<Source | 'all'>('all')
  const [dashboardPeriod, setDashboardPeriod] = useState<DashboardPeriod>('today')
  const [activeMetricId, setActiveMetricId] = useState('views')
  const [topMetric, setTopMetric] = useState<TopMetric>('views')
  const [density, setDensity] = useState<Density>('comfortable')
  const [quickFilter, setQuickFilter] = useState<QuickFilter>('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Blocker | null>(null)
  const [drawerTab, setDrawerTab] = useState<DrawerTab>('reason')

  const filteredBlockers = useMemo(
    () =>
      blockers.filter((item) => {
        const normalizedQuery = query.trim().toLowerCase()
        const queryMatches =
          !normalizedQuery ||
          [item.account, item.title, item.reason, item.owner, item.nextAction, sourceLabels[item.source], severityLabels[item.severity]]
            .join(' ')
            .toLowerCase()
            .includes(normalizedQuery)
        const severityMatches = severityFilter === 'all' || item.severity === severityFilter
        const sourceMatches = sourceFilter === 'all' || item.source === sourceFilter
        const quickMatches =
          quickFilter === 'all' ||
          (quickFilter === 'safe' && item.severity === 'info') ||
          (quickFilter === 'stale' && item.freshness.toLowerCase().includes('устарело')) ||
          (quickFilter === 'risk' && item.severity !== 'info')
        return queryMatches && severityMatches && sourceMatches && quickMatches
      }),
    [severityFilter, sourceFilter, quickFilter, query],
  )

  const rowPadding = density === 'compact' ? 'px-3 py-1.5' : 'px-3 py-2.5'

  const topMetricLabels: Record<TopMetric, { label: string; short: string }> = {
    views: { label: 'просм.', short: 'Просм.' },
    contacts: { label: 'контактов', short: 'Контакты' },
    orders: { label: 'заказов', short: 'Заказы' },
  }

  const sortedTopProducts = useMemo(
    () =>
      [...topProducts].sort((a, b) => {
        const left = Number(a[topMetric].replace(/\s/g, ''))
        const right = Number(b[topMetric].replace(/\s/g, ''))
        return right - left
      }),
    [topMetric],
  )

  function openKpi(kpi: Kpi) {
    if (kpi.id === 'chats' || kpi.id === 'bot') {
      setSourceFilter('chat')
      setSeverityFilter('all')
      setQuickFilter('all')
    } else if (kpi.id === 'reviews') {
      setSourceFilter('review')
      setSeverityFilter('all')
      setQuickFilter('risk')
    } else if (kpi.id === 'wallets') {
      setSourceFilter('wallet')
      setSeverityFilter('critical')
      setQuickFilter('risk')
    } else if (kpi.id === 'xml') {
      setSourceFilter('listing')
      setSeverityFilter('critical')
      setQuickFilter('stale')
    } else if (kpi.id === 'orders') {
      setSourceFilter('order')
      setSeverityFilter('all')
      setQuickFilter('all')
    } else {
      setSourceFilter('all')
      setSeverityFilter('warning')
      setQuickFilter('risk')
    }
  }

  function openBlocker(item: Blocker) {
    setSelected(item)
    setDrawerTab('reason')
  }

  function openBlockerRoute(item: Blocker) {
    navigate(blockerRoutes[item.source])
  }

  return (
    <div className="min-h-full overflow-auto bg-slate-50 text-slate-900">
      <section className="space-y-4 px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-extrabold text-slate-950">Обзор Авито</h1>
              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-bold text-emerald-700">12 из 15 аккаунтов готовы</span>
              <span className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-700">Требуется обновление · 2 события</span>
            </div>
            <p className="mt-1 text-sm text-slate-500">Операционный обзор по аккаунтам, чатам, объявлениям, кошелькам и заказам. Внешние действия выполняются только в целевых модулях.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <PeriodControl value={dashboardPeriod} onChange={setDashboardPeriod} />
            <Button variant="outline" size="sm" className="gap-2" title="Обновляет только безопасные источники чтения">
              <RefreshCw className="size-3.5" />
              Обновить
            </Button>
            <Button variant="outline" size="sm" className="gap-2" title="Экспортирует сводку статусов без платежных данных">
              <Download className="size-3.5" />
              Экспорт
            </Button>
          </div>
        </div>
        <AvitoModuleTabs />

        <div className="grid gap-2 md:grid-cols-4 xl:grid-cols-7">
          {kpis.map((kpi) => (
            <button
              key={kpi.id}
              className={cn(
                'min-w-[142px] rounded-lg border border-slate-200 bg-white px-3 py-2 text-left shadow-sm hover:bg-slate-50',
                (kpi.id === 'wallets' && sourceFilter === 'wallet') ||
                (kpi.id === 'xml' && sourceFilter === 'listing') ||
                (kpi.id === 'reviews' && sourceFilter === 'review') ||
                (kpi.id === 'orders' && sourceFilter === 'order') ||
                ((kpi.id === 'chats' || kpi.id === 'bot') && sourceFilter === 'chat')
                  ? 'border-blue-300 ring-2 ring-blue-100'
                  : '',
              )}
              title={kpi.tooltip}
              type="button"
              onClick={() => openKpi(kpi)}
            >
              <span className="block text-[11px] font-semibold text-slate-500">{kpi.label}</span>
              <span className={cn('mt-1 block text-2xl font-extrabold leading-none', kpiStyles[kpi.state])}>{kpi.value}</span>
              <span className={cn('mt-1 block truncate text-[11.5px] font-medium', kpi.state === 'critical' ? 'text-red-600' : kpi.state === 'warning' ? 'text-amber-700' : 'text-slate-400')}>
                {kpi.secondary}
              </span>
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="rounded-md bg-slate-50 px-2 py-1 font-semibold">Период: {dashboardPeriod === 'custom' ? '25.04 — 01.05' : periodOptions.find((item) => item.value === dashboardPeriod)?.label}</span>
          <span className="rounded-md bg-red-50 px-2 py-1 font-semibold text-red-700">Внешние действия под защитой</span>
          <span className="rounded-md bg-amber-50 px-2 py-1 font-semibold text-amber-700">Обновлено: только что</span>
          <span className="rounded-md bg-blue-50 px-2 py-1 font-semibold text-blue-700">
            {dashboardPeriod === 'today' ? '12 из 15 аккаунтов' : dashboardPeriod === '7d' ? '14 из 15 аккаунтов' : dashboardPeriod === '14d' ? '15 аккаунтов · 1 устаревший период' : dashboardPeriod === 'custom' ? '25.04—01.05 · все аккаунты' : '15 аккаунтов · 2 устаревших периода'}
          </span>
        </div>

        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
          {dashboardMetrics.map((metric) => (
            <DashboardMetricCard
              key={metric.id}
              metric={metric}
              period={dashboardPeriod}
              active={activeMetricId === metric.id}
              onSelect={() => {
                setActiveMetricId(metric.id)
                if (metric.id === 'views') setTopMetric('views')
                if (metric.id === 'contacts') setTopMetric('contacts')
                if (metric.id === 'spend') setSourceFilter('wallet')
              }}
            />
          ))}
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.95fr)]">
          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-950">Воронка конверсии</h2>
              <span className="rounded-full bg-blue-50 px-2 py-1 text-[11px] font-semibold text-blue-700">0.89% в контакт</span>
            </div>
            {[
              ['Просмотры → Контакты', '0.89%', '1 460 просм.', '13 конт.', 0.089, 'bg-cyan-500'],
              ['Контакты → Заказы', '23.1%', '13 конт.', '3 заказа', 0.231, 'bg-emerald-500'],
              ['Заказы → Выкупы', '166.7%', '3 заказа', '5 выкупов', 1, 'bg-orange-500'],
            ].map(([label, value, left, right, width, color]) => (
              <div className="mb-4 last:mb-0" key={label}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-medium text-slate-600">{label}</span>
                  <span className="font-bold text-slate-950">{value}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className={cn('h-full rounded-full', color as string)} style={{ width: `${Number(width) * 100}%` }} />
                </div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
                  <span>{left}</span>
                  <span>{right}</span>
                </div>
              </div>
            ))}
            <div className="mt-5 border-t border-slate-100 pt-4">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="font-bold text-slate-800">Цель на месяц</span>
                <span className="font-bold text-amber-700">21%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full w-[21%] rounded-full bg-amber-400" />
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-slate-400">
                <span>206 / 1 000 заказов</span>
                <span>Осталось: 794</span>
              </div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-950">Топ-5 товаров</h2>
              <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-0.5">
                {(['views', 'contacts', 'orders'] as const).map((metric) => (
                  <button
                    key={metric}
                    className={cn(
                      'h-6 rounded-full px-2 text-[11px] font-semibold transition',
                      topMetric === metric ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-800',
                    )}
                    type="button"
                    onClick={() => setTopMetric(metric)}
                    aria-pressed={topMetric === metric}
                  >
                    {topMetricLabels[metric].short}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              {sortedTopProducts.map((product, index) => (
                <a
                  className="grid grid-cols-[28px_minmax(0,1fr)_92px_24px] items-center gap-3 rounded-lg bg-slate-50 px-3 py-2 transition hover:bg-blue-50 hover:shadow-sm"
                  href={product.url}
                  key={product.id}
                  rel="noreferrer"
                  target="_blank"
                  title="Открыть страницу товара на Авито"
                >
                  <span className="inline-flex size-6 items-center justify-center rounded-md bg-slate-200 text-xs font-bold text-slate-600">{index + 1}</span>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-slate-900">{product.name}</div>
                    <div className="text-[11px] text-slate-500">{product.brand} · {product.contacts} контактов · {product.orders} заказов</div>
                  </div>
                  <div className="text-right">
                    <div className="font-bold text-slate-950">{product[topMetric]}</div>
                    <div className="text-[11px] text-slate-400">{topMetricLabels[topMetric].label}</div>
                  </div>
                  <ExternalLink className="size-4 text-slate-400" />
                </a>
              ))}
            </div>
            <div className="mt-3 text-right text-[11px] text-slate-400">За последние 30 дней</div>
          </section>
        </div>

        <div className="grid gap-4">
          <LineChart
            title="Динамика просмотров"
            primary={hourlyViews.today}
            secondary={hourlyViews.yesterday}
            tertiary={hourlyViews.week}
            periodSummaries={{
              today: 'Пик сегодня: 176',
              '7d': 'Пик недели: Пт · 1 248',
              '14d': 'Пик периода: 30.04 · 1 380',
              '30d': 'Пик месяца: 21.04 · 1 620',
              custom: 'Пик диапазона: 29.04 · 1 104',
            }}
          />
          <LineChart
            title="Динамика заказов с доставкой"
            primary={hourlyOrders.today}
            secondary={hourlyOrders.yesterday}
            tertiary={hourlyOrders.week}
            periodSummaries={{
              today: 'Сегодня: 3 заказа · 3 535 ₽',
              '7d': 'За 7 дней: 27 заказов · 31 420 ₽',
              '14d': 'За 14 дней: 54 заказа · 62 840 ₽',
              '30d': 'За 30 дней: 116 заказов · 138 600 ₽',
              custom: '25.04 — 01.05: 19 заказов · 24 770 ₽',
            }}
          />
        </div>
      </section>

      <section className="flex shrink-0 items-center gap-2 overflow-x-auto border-y border-slate-200 bg-white px-5 py-3">
        <label className="flex min-w-[280px] shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[13px] text-slate-400 focus-within:border-blue-600">
          <Search className="size-3.5" />
          <input
            className="w-full border-0 bg-transparent p-0 text-[13px] text-slate-800 outline-none"
            placeholder="Поиск по аккаунту, объявлению, заказу"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <div className="flex min-w-0 shrink items-center gap-1 overflow-x-auto">
          {(['all', 'critical', 'warning', 'info'] as const).map((value) => (
                <button
                  key={value}
                  className={cn(
                'inline-flex h-[30px] shrink-0 items-center gap-1 rounded-full border px-3 text-[12.5px] font-medium',
                severityFilter === value ? 'border-slate-900 bg-slate-900 text-white' : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50 hover:text-slate-700',
                  )}
                  type="button"
                  onClick={() => setSeverityFilter(value)}
                >
              {value === 'all' ? 'Все' : severityLabels[value]}
              <span className="text-[11px] opacity-70">{value === 'all' ? blockers.length : blockers.filter((item) => item.severity === value).length}</span>
                </button>
              ))}
            </div>
        <div className="ml-auto flex shrink-0 items-center gap-2">
          <span className="whitespace-nowrap text-xs text-slate-400">Показано {filteredBlockers.length} из {blockers.length}</span>
          <Button variant="outline" size="sm" className="h-[30px] gap-1.5 rounded-lg px-3 text-[13px] font-medium" title="Обновляет только безопасные источники чтения">
            <RefreshCw className="size-3.5" />
            Обновить
          </Button>
          <Button variant="outline" size="sm" className="h-[30px] gap-1.5 rounded-lg px-3 text-[13px] font-medium" title="Экспортирует сводку статусов без платежных данных">
            <Download className="size-3.5" />
            Экспорт
          </Button>
        </div>
      </section>

      <section className="grid shrink-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3 bg-slate-50 px-5 pt-3">
        <div className="flex min-w-0 items-center gap-2 overflow-x-auto">
          {[
            ['all', 'Все источники'],
            ['chat', 'Чаты'],
            ['review', 'Отзывы'],
            ['listing', 'Объявления'],
            ['wallet', 'Кошельки'],
            ['order', 'Заказы'],
          ].map(([value, label]) => (
            <button
              key={value}
              className={cn(
                'inline-flex h-[30px] shrink-0 items-center gap-1.5 rounded-full border px-3 text-xs font-semibold',
                sourceFilter === value ? 'border-slate-900 bg-slate-900 text-white shadow-sm' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900',
              )}
              type="button"
              onClick={() => setSourceFilter(value as Source | 'all')}
            >
              {label}
              <span className="text-[10.5px] opacity-70">{value === 'all' ? blockers.length : blockers.filter((item) => item.source === value).length}</span>
            </button>
          ))}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="min-w-[230px] text-right text-[11.5px] leading-[1.35] text-slate-500">
            <b className="font-bold text-slate-800">обновлено 09:42</b> · 2 аккаунта требуют обновления
          </div>
          <div className="inline-flex items-center gap-0.5 rounded-lg border border-slate-200 bg-white p-0.5">
            {([
              ['comfortable', 'Обычная'],
              ['compact', 'Плотная'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                className={cn(
                  'h-6 rounded-md px-2 text-[11.5px] font-semibold transition',
                  density === value ? 'bg-slate-900 text-white' : 'text-slate-500 hover:text-slate-800',
                )}
                type="button"
                onClick={() => setDensity(value)}
                aria-pressed={density === value}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 px-5 py-3 text-xs text-slate-600">
        <b>Фильтры:</b>
        {([
          ['safe', 'Безопасные'],
          ['stale', 'Устаревшие'],
          ['risk', 'Риски'],
        ] as const).map(([value, label]) => (
          <button
            key={value}
            className={cn(
              'h-7 rounded-full border px-3 font-semibold transition',
              quickFilter === value ? 'border-blue-200 bg-blue-600 text-white shadow-sm' : 'border-slate-200 bg-blue-50 text-blue-700 hover:bg-blue-100',
            )}
            type="button"
            onClick={() => setQuickFilter(value)}
            aria-pressed={quickFilter === value}
          >
            {label}
          </button>
        ))}
        <button
          className="h-7 rounded-full border border-transparent px-3 text-slate-600 hover:bg-slate-100"
          type="button"
          onClick={() => {
            setQuickFilter('all')
            setSeverityFilter('all')
            setSourceFilter('all')
            setQuery('')
          }}
        >
          Сбросить
        </button>
        <span className="ml-auto whitespace-nowrap text-amber-800">
          Требуется обновление: внешние действия на целевых экранах будут заблокированы при устаревшем состоянии.
        </span>
      </div>

      <div className="overflow-auto px-5 pb-4">
        <table className={cn('w-full min-w-[1380px] border-separate border-spacing-0 overflow-hidden rounded-lg border border-slate-200 bg-white text-[13px] shadow-sm', density === 'compact' && 'text-xs')}>
          <thead className="sticky top-0 z-10 bg-slate-50">
            <tr>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Приоритет</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Источник</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Аккаунт</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Событие</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Свежесть</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Ответственный</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Действия</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Аудит</th>
              <th className="border-b border-slate-200 px-3 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-[0.05em] text-slate-500">Доступно</th>
            </tr>
          </thead>
          <tbody>
            {filteredBlockers.map((item) => {
              const Icon = sourceIcon(item.source)
              const active = selected?.id === item.id
              return (
                <tr key={item.id} className={cn('cursor-pointer hover:bg-slate-50', active && 'bg-blue-50')} onClick={() => openBlocker(item)}>
                  <td className={cn('border-b border-slate-100', rowPadding)}><StatusPill severity={item.severity} /></td>
                  <td className={cn('border-b border-slate-100', rowPadding)}>
                    <span className="inline-flex items-center gap-2 font-semibold text-slate-700">
                      <Icon className="size-4 text-slate-500" />
                      {sourceLabels[item.source]}
                    </span>
                  </td>
                  <td className={cn('border-b border-slate-100', rowPadding)}><AccountBadge name={item.account} /></td>
                  <td className={cn('max-w-[390px] border-b border-slate-100', rowPadding)}>
                    <span className="block text-left font-semibold text-blue-700">{item.title}</span>
                    <div className="mt-1 line-clamp-1 text-xs text-slate-500">{item.reason}</div>
                  </td>
                  <td className={cn('border-b border-slate-100 font-mono text-[11.5px] font-semibold text-slate-600', rowPadding)}>{item.freshness}</td>
                  <td className={cn('border-b border-slate-100 font-semibold text-slate-700', rowPadding)}>{item.owner}</td>
                  <td className={cn('border-b border-slate-100', rowPadding)}>
                    <button
                      className="inline-flex h-[30px] items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 text-[13px] font-medium text-blue-700 hover:border-slate-300 hover:bg-slate-50"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        openBlockerRoute(item)
                      }}
                    >
                      {item.nextAction}
                      <ArrowRight className="size-3" />
                    </button>
                  </td>
                  <td className={cn('border-b border-slate-100 text-xs text-slate-500', rowPadding)}>{item.audit}</td>
                  <td className={cn('border-b border-slate-100', rowPadding)}>
                    <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700">{item.stillWorks.length} безопасно</span>
                  </td>
                </tr>
              )
            })}
            {filteredBlockers.length === 0 && (
              <tr>
                <td className="px-4 py-10 text-center text-sm text-slate-500" colSpan={9}>
                  По текущим переключателям ничего не найдено. Сбросьте фильтры или измените поиск.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && (
        <>
          <button className="fixed inset-0 z-40 bg-slate-950/20" type="button" aria-label="Закрыть детали" onClick={() => setSelected(null)} />
          <aside className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[620px] flex-col border-l border-slate-200 bg-white shadow-2xl">
            <div className="flex min-h-[62px] items-center justify-between border-b border-slate-200 px-4 py-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <StatusPill severity={selected.severity} />
                  <AccountBadge name={selected.account} />
                </div>
                <h2 className="mt-2 truncate text-base font-bold text-slate-950">{selected.title}</h2>
              </div>
              <button className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50" type="button" onClick={() => setSelected(null)} aria-label="Закрыть">
                <X className="size-4" />
              </button>
            </div>
            <div className="flex border-b border-slate-200 px-4">
              {([
                ['reason', 'Причина'],
                ['data', 'Данные'],
                ['actions', 'Действия'],
                ['audit', 'Аудит'],
              ] as const).map(([tab, label]) => (
                <button
                  key={tab}
                  className={cn('h-10 border-b-2 px-3 text-sm font-semibold', drawerTab === tab ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-800')}
                  type="button"
                  onClick={() => setDrawerTab(tab)}
                  aria-pressed={drawerTab === tab}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex-1 space-y-3 overflow-auto p-4">
              {drawerTab === 'reason' && (
                <section className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                  <h3 className="text-sm font-bold text-slate-950">Причина статуса</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{selected.reason}</p>
                  <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <div className="font-semibold text-slate-500">Свежесть</div>
                      <div className="mt-1 font-mono text-slate-800">{selected.freshness}</div>
                    </div>
                    <div className="rounded-lg border border-slate-200 bg-white p-2">
                      <div className="font-semibold text-slate-500">Ответственный</div>
                      <div className="mt-1 font-semibold text-slate-800">{selected.owner}</div>
                    </div>
                  </div>
                </section>
              )}

              {drawerTab === 'data' && (
                <>
                  <section className="rounded-lg border border-slate-200 bg-white p-3">
                    <h3 className="text-sm font-bold text-slate-950">Что заблокировано</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selected.blocked.map((item) => (
                        <span key={item} className="rounded-full border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">{item}</span>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-lg border border-slate-200 bg-white p-3">
                    <h3 className="text-sm font-bold text-slate-950">Что остается доступным</h3>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selected.stillWorks.map((item) => (
                        <span key={item} className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">{item}</span>
                      ))}
                    </div>
                  </section>
                </>
              )}

              {drawerTab === 'actions' && (
                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <h3 className="text-sm font-bold text-slate-950">Следующее безопасное действие</h3>
                  <button className="mt-3 inline-flex h-8 items-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white hover:bg-blue-700" type="button" onClick={() => openBlockerRoute(selected)}>
                    {selected.nextAction}
                    <ArrowRight className="size-3.5" />
                  </button>
                  <p className="mt-2 text-xs text-slate-500">Отправка, публикация, платежи и удаление здесь не выполняются.</p>
                </section>
              )}

              {drawerTab === 'audit' && (
                <section className="rounded-lg border border-slate-200 bg-white p-3">
                  <h3 className="text-sm font-bold text-slate-950">Аудит и источник</h3>
                  <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-700">{selected.audit}</div>
                  <p className="mt-2 text-xs text-slate-500">Каждая внешняя операция в целевом модуле должна иметь отдельную запись согласования и аудита.</p>
                </section>
              )}
            </div>
          </aside>
        </>
      )}
    </div>
  )
}
