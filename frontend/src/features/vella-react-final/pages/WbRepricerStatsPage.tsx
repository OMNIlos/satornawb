import { BarChart3, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { formatRub } from '../../../lib/formatRub'
import { Badge, DataTable, FilterSummary, FilterToolbar, VellaFinalMetrics, type DataColumn } from '../components/VellaFinalPrimitives'
import type { MetricWithDelta, RepricerStatsRow } from '../contracts/repricer'
import { repricerStatsRows } from '../data/demoRepricer'
import { VellaProductionShell } from '../shell/VellaProductionShell'

const filters = ['Все SKU', 'Можно пересчитать', 'Цена заблокирована', 'Источник не готов', 'Корзины растут', 'Корзины падают', 'OOS риск', 'В акции', 'В рекламе']

function metric(value: MetricWithDelta, formatter: (value: number) => string = (n) => n.toLocaleString('ru-RU')) {
  return (
    <>
      <b>{formatter(value.value)}</b>
      <span className={`vella-delta ${value.direction}`}>{value.deltaPct == null ? 'нет сравнения' : `${value.deltaPct > 0 ? '+' : ''}${value.deltaPct}%`}</span>
    </>
  )
}

function protectionBadge(status: RepricerStatsRow['priceProtectionStatus']) {
  if (status === 'can_recalculate') return <Badge tone="ok">можно пересчитать</Badge>
  if (status === 'price_blocked') return <Badge tone="bad">цена заблокирована</Badge>
  return <Badge tone="warn">проверить</Badge>
}

function sourceBadge(status: RepricerStatsRow['sourceStatus']) {
  if (status === 'ready') return <Badge tone="ok">источник готов</Badge>
  if (status === 'stale') return <Badge tone="warn">устарело</Badge>
  return <Badge tone="bad">источник не готов</Badge>
}

export function WbRepricerStatsPage() {
  const [filter, setFilter] = useState('Все SKU')
  const [query, setQuery] = useState('')
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return repricerStatsRows
      .filter((row) => {
        if (filter === 'Все SKU') return true
        if (filter === 'Можно пересчитать') return row.priceProtectionStatus === 'can_recalculate'
        if (filter === 'Цена заблокирована') return row.priceProtectionStatus === 'price_blocked'
        if (filter === 'Источник не готов') return row.sourceStatus !== 'ready'
        if (filter === 'Корзины растут') return row.flags.includes('cart_growth')
        if (filter === 'Корзины падают') return row.flags.includes('cart_drop')
        if (filter === 'OOS риск') return row.flags.includes('oos_risk')
        if (filter === 'В акции') return row.flags.includes('promo')
        if (filter === 'В рекламе') return row.flags.includes('ads')
        return true
      })
      .filter((row) => !q || `${row.sku} ${row.title} ${row.nmId} ${row.managerLabel ?? ''}`.toLowerCase().includes(q))
  }, [filter, query])

  const columns: Array<DataColumn<RepricerStatsRow>> = [
    {
      key: 'position',
      label: 'Позиция',
      sticky: true,
      render: (row) => (
        <span className="vella-product-mini">
          {row.imageUrl ? <img src={row.imageUrl} alt="" /> : <span className="vella-product-placeholder" />}
          <span><b>{row.sku}</b><span className="sub">{row.title} · nmId {row.nmId}</span></span>
        </span>
      ),
    },
    { key: 'manager', label: 'Менеджер', render: (row) => <span className="vella-manager">{row.managerLabel ?? 'не назначен'}</span> },
    { key: 'impressions', label: 'Показы', numeric: true, render: (row) => metric(row.impressions) },
    { key: 'clicks', label: 'Клики', numeric: true, render: (row) => metric(row.clicks) },
    { key: 'carts', label: <span title="Корзины — основной сигнал для репрайсера">Корзины</span>, numeric: true, render: (row) => metric(row.carts) },
    { key: 'orders', label: 'Заказы', numeric: true, render: (row) => metric(row.orders) },
    { key: 'cr', label: <span title="CR корзины → заказ">CR</span>, numeric: true, render: (row) => metric(row.conversionRatePct, (n) => `${n.toFixed(1)}%`) },
    { key: 'ads', label: 'Реклама', numeric: true, render: (row) => metric(row.adSpendKopecks, formatRub) },
    { key: 'median', label: <span title="Ночная медиана цены">Медиана цены</span>, numeric: true, render: (row) => metric(row.medianPriceKopecks, formatRub) },
    { key: 'protection', label: <span title="Price protection блокирует отправку цены при неготовых источниках">Защита цены</span>, render: (row) => protectionBadge(row.priceProtectionStatus) },
    { key: 'source', label: <span title="Готовность источников для пересчёта">Статус источников</span>, render: (row) => sourceBadge(row.sourceStatus) },
  ]

  return (
    <VellaProductionShell
      title="Диагностика цен"
      subtitle=""
      module="repricer"
      mobileTitle="Диагностика цен доступна в desktop-версии"
      mobileCopy="Сигналы корзин, защита цены, медиана и статусы источников рассчитаны на широкий экран."
      topbarActions={<><button className="vella-button" type="button"><RefreshCw size={16} /> Проверить цены</button><button className="vella-button" type="button"><BarChart3 size={16} /> 7 дней</button></>}
    >
      <VellaFinalMetrics items={[
        { label: 'SKU можно пересчитать', value: 1, delta: 'источники готовы', tone: 'up' },
        { label: 'Цена заблокирована', value: 1, delta: 'защита цены', tone: 'down', tip: 'Цена не отправляется при неготовых или устаревших источниках.' },
        { label: 'Корзины растут', value: 1, delta: 'основной сигнал', tone: 'up', tip: 'Корзины важнее продаж для реакции репрайсера.' },
        { label: 'Статус источников', value: 1, delta: 'источник не готов', tone: 'down', tip: 'Статус источников влияет на разрешение пересчёта.' },
      ]} />
      <FilterToolbar
        searchPlaceholder="SKU, nmId, товар или менеджер..."
        query={query}
        onQueryChange={setQuery}
        filters={filters}
        activeFilter={filter}
        onFilterChange={setFilter}
      />
      <FilterSummary shown={rows.length} total={repricerStatsRows.length} label={filter} onReset={() => { setFilter('Все SKU'); setQuery('') }} />
      <DataTable rows={rows} columns={columns} className="vella-final-repricer-table" wrapperClassName="vella-final-repricer-table-wrap" />
    </VellaProductionShell>
  )
}
