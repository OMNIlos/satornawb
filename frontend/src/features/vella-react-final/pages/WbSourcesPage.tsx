import { Download, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge, DataTable, Drawer, FilterSummary, FilterToolbar, VellaFinalMetrics, type DataColumn } from '../components/VellaFinalPrimitives'
import type { SourceRow } from '../contracts/sources'
import { sourceRows } from '../data/demoSources'
import { VellaProductionShell } from '../shell/VellaProductionShell'

const filters = ['Все источники', 'Требует действия', 'Свежее', 'Устарело', '1С', 'Ручная загрузка', 'Есть ошибка', 'P&L', 'РНП/ABC', 'Репрайсер', 'Реклама', 'Ответственный']

const surfaceLabels: Record<SourceRow['dependentSurfaces'][number], string> = {
  abc: 'ABC',
  ads: 'Реклама',
  expenses: 'Расходы',
  plans: 'Планы',
  pnl: 'P&L',
  repricer: 'Репрайсер',
  rnp: 'РНП',
}

function statusLabel(row: SourceRow) {
  if (row.status === 'synced') return <Badge tone="ok">свежее</Badge>
  if (row.status === 'stale') return <Badge tone="warn">устарело</Badge>
  if (row.status === 'mapping_required') return <Badge tone="warn">требует правил</Badge>
  if (row.status === 'not_connected') return <Badge tone="bad">не подключено</Badge>
  return <Badge tone="neutral">{row.status}</Badge>
}

export function WbSourcesPage() {
  const [filter, setFilter] = useState('Все источники')
  const [query, setQuery] = useState('')
  const [drawerRow, setDrawerRow] = useState<SourceRow | null>(null)

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return sourceRows
      .filter((row) => {
        if (filter === 'Все источники') return true
        if (filter === 'Требует действия') return ['mapping_required', 'not_connected', 'error'].includes(row.status)
        if (filter === 'Свежее') return row.status === 'synced'
        if (filter === 'Устарело') return row.status === 'stale'
        if (filter === '1С') return row.sourceType === 'one_c'
        if (filter === 'Ручная загрузка') return row.sourceType === 'excel_fallback'
        if (filter === 'Есть ошибка') return row.status === 'error'
        if (filter === 'P&L') return row.dependentSurfaces.includes('pnl')
        if (filter === 'РНП/ABC') return row.dependentSurfaces.includes('rnp') || row.dependentSurfaces.includes('abc')
        if (filter === 'Репрайсер') return row.dependentSurfaces.includes('repricer')
        if (filter === 'Реклама') return row.dependentSurfaces.includes('ads')
        if (filter === 'Ответственный') return Boolean(row.ownerUserId)
        return true
      })
      .filter((row) => !q || `${row.name} ${row.pulls.join(' ')} ${row.qualityLabel}`.toLowerCase().includes(q))
  }, [filter, query])

  const columns: Array<DataColumn<SourceRow>> = [
    { key: 'source', label: 'Источник', sticky: true, render: (row) => <><b>{row.name}</b><span className="sub">{row.id}</span></> },
    { key: 'pulls', label: 'Что тянем', render: (row) => row.pulls.join(' · ') },
    { key: 'period', label: 'Период', render: (row) => row.periodLabel },
    { key: 'sync', label: 'Последняя синхронизация', render: (row) => row.lastSyncAt ? new Date(row.lastSyncAt).toLocaleString('ru-RU') : 'ещё нет' },
    { key: 'quality', label: 'Качество данных', render: (row) => <>{statusLabel(row)}<span className="sub">{row.qualityLabel}</span></> },
    { key: 'depends', label: 'Зависит', render: (row) => <span className="vella-final-badge-list">{row.dependentSurfaces.map((surface) => <Badge tone="neutral" key={surface}>{surfaceLabels[surface]}</Badge>)}</span> },
    { key: 'owner', label: 'Ответственный', render: (row) => row.ownerLabel },
    { key: 'action', label: 'Действие', render: (row) => <button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(row)}>{row.action === 'connect' ? 'Подключить' : row.action === 'map' ? 'Правила' : row.action === 'upload' ? 'Загрузить' : 'Открыть'}</button> },
  ]

  return (
    <VellaProductionShell
      title="Источники и загрузки"
      subtitle="Готовность источников, правила ДДС и переходы в зависимые отчёты."
      module="standalone"
      mobileTitle="Источники и загрузки доступны в desktop-версии"
      mobileCopy="Статусы свежести, открытые уточнения и зависимости отчётов требуют широкого рабочего экрана."
      topbarActions={<><button className="vella-button" type="button"><RefreshCw size={16} /> Проверить свежесть</button><button className="vella-button" type="button"><Download size={16} /> Шаблон Excel</button></>}
    >
      <VellaFinalMetrics items={[
        { label: 'Источников под контролем', value: sourceRows.length, delta: 'WB + 1С + fallback', tone: 'up' },
        { label: '1С ДДС live', value: 'требует правил', delta: 'красные статьи исключены', tone: 'down', tip: 'Статус подключения к отчёту 1С «Движение денежных средств» и маппингу статей.' },
        { label: 'Fallback-загрузки', value: 'Excel', delta: 'аварийный импорт', tone: 'neutral' },
        { label: 'Зависимые отчёты', value: 'P&L / РНП / ABC', delta: 'переходы из строк', tone: 'neutral' },
      ]} />
      <FilterToolbar
        searchPlaceholder="Источник, отчёт или действие..."
        query={query}
        onQueryChange={setQuery}
        filters={filters}
        activeFilter={filter}
        onFilterChange={setFilter}
        right={<><button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(sourceRows[0])}>Подключение 1С</button><button className="btn btn-default btn-sm" type="button">Расходы</button><button className="btn btn-default btn-sm" type="button">Шаблон Excel</button></>}
      />
      <FilterSummary shown={rows.length} total={sourceRows.length} label={filter} onReset={() => { setFilter('Все источники'); setQuery('') }} />
      <DataTable rows={rows} columns={columns} className="vella-final-sources-table" wrapperClassName="vella-final-sources-table-wrap" onRowClick={setDrawerRow} />
      <Drawer open={Boolean(drawerRow)} title="Подключение 1С" meta={drawerRow?.name ?? 'источник'} tag="источники" onClose={() => setDrawerRow(null)}>
        <p className="vella-muted">Сервисный слой должен отдавать статус подключения, последнюю синхронизацию, качество данных и зависимые поверхности. Страница не выполняет реальные действия до подключения источника.</p>
      </Drawer>
    </VellaProductionShell>
  )
}
