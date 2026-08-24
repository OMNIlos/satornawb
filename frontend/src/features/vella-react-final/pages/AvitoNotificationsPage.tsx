import { Bell, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { Badge, DataTable, FilterSummary, FilterToolbar, SourceStrip, VellaFinalMetrics, type DataColumn } from '../components/VellaFinalPrimitives'
import { VellaProductionShell } from '../shell/VellaProductionShell'

type AvitoEventRow = {
  id: string
  status: 'warn' | 'bad' | 'new' | 'ok'
  source: string
  account: string
  event: string
  freshness: string
  owner: string
  nextAction: string
  link: string
}

const eventRows: AvitoEventRow[] = [
  { id: 'avito-xml', status: 'warn', source: 'Объявления', account: 'Bless T · Москва', event: '5 активных объявлений отсутствуют в XML', freshness: 'устарело 2ч 14м', owner: 'Мария', nextAction: 'Открыть карточку', link: '/avito/listings' },
  { id: 'avito-wallet', status: 'warn', source: 'Кошельки', account: 'Anomie Studio', event: 'Баланс 320 ₽ ниже порога 1 000 ₽', freshness: '09:42', owner: 'Максим', nextAction: 'Кошельки позже', link: '/avito/wallets' },
  { id: 'avito-chat', status: 'new', source: 'Сообщения', account: 'Bless T', event: 'Чаты не обновлялись 18 минут', freshness: '18м назад', owner: 'Администратор', nextAction: 'Открыть сообщения', link: '/avito/chats' },
]

const filters = ['Все события', 'Требует действия', 'Объявления', 'Кошельки', 'Сообщения']

export function AvitoNotificationsPage() {
  const [filter, setFilter] = useState('Все события')
  const [query, setQuery] = useState('')
  const rows = eventRows
    .filter((row) => filter === 'Все события' || filter === 'Требует действия' && row.status !== 'ok' || row.source === filter)
    .filter((row) => !query.trim() || `${row.source} ${row.account} ${row.event}`.toLowerCase().includes(query.trim().toLowerCase()))

  const columns: Array<DataColumn<AvitoEventRow>> = [
    { key: 'status', label: 'Статус', render: (row) => <Badge tone={row.status}>{row.source}</Badge> },
    { key: 'source', label: 'Источник', render: (row) => row.source },
    { key: 'account', label: 'Аккаунт', render: (row) => row.account },
    { key: 'event', label: 'Событие', sticky: true, render: (row) => <><b>{row.event}</b><span className="sub">{row.link}</span></> },
    { key: 'freshness', label: 'Свежесть', render: (row) => row.freshness },
    { key: 'owner', label: 'Ответственный', render: (row) => row.owner },
    { key: 'action', label: 'Следующее действие', render: (row) => <button className="btn btn-default btn-sm" type="button">{row.nextAction}</button> },
  ]

  return (
    <VellaProductionShell
      title="Уведомления Авито"
      subtitle="Avito-specific event queue: аккаунты, отзывы, объявления, заказы и кошельки."
      mobileTitle="Уведомления Авито доступны в desktop-версии"
      mobileCopy="Правила очереди, события аккаунтов и контроль действий требуют широкого рабочего экрана."
      topbarActions={<><button className="vella-button" type="button"><RefreshCw size={16} /> Обновить</button><button className="vella-button" type="button"><Bell size={16} /> Правила</button></>}
    >
      <VellaFinalMetrics items={[
        { label: 'Событий', value: eventRows.length, delta: 'Авито очередь', tone: 'neutral' },
        { label: 'XML', value: '1 риск', delta: 'передавать все объявления', tone: 'down' },
        { label: 'Кошельки', value: 'ниже порога', delta: 'ручное действие', tone: 'down' },
        { label: 'Чаты', value: '18 мин', delta: 'задержка обновления', tone: 'neutral' },
      ]} />
      <SourceStrip
        tone="partial"
        kicker="Авито"
        chips={['events', 'wallets', 'listings', 'reviews']}
        title="События ведут к конкретному аккаунту, отзыву, объявлению, заказу или кошельку"
        meta="Это отдельная Avito-поверхность. Мобильный fallback и действия не должны ссылаться на WB digest или общие уведомления."
      />
      <FilterToolbar searchPlaceholder="Событие, аккаунт или источник..." query={query} onQueryChange={setQuery} filters={filters} activeFilter={filter} onFilterChange={setFilter} />
      <FilterSummary shown={rows.length} total={eventRows.length} label={filter} onReset={() => { setFilter('Все события'); setQuery('') }} />
      <DataTable rows={rows} columns={columns} />
    </VellaProductionShell>
  )
}
