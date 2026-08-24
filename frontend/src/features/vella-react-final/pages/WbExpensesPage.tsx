import { FileSpreadsheet, Plus, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { formatRub } from '../../../lib/formatRub'
import { Badge, DataTable, Drawer, FilterSummary, FilterToolbar, SourceStrip, VellaFinalMetrics, type DataColumn } from '../components/VellaFinalPrimitives'
import type { ExpenseDraftInput, ExpenseRow } from '../contracts/finance'
import { expenseRows, expenseSummaryMetrics } from '../data/demoFinance'
import { VellaProductionShell } from '../shell/VellaProductionShell'

const filters = ['Все', 'Берём', 'Исключено', 'P&L only', 'Требует сверки', 'Распределяется', 'Поступления', 'Выбытия']

function directionLabel(row: ExpenseRow) {
  return row.direction === 'inflow' ? 'Поступление' : 'Выбытие'
}

function periodLabel(row: ExpenseRow) {
  return `${row.periodFrom.slice(8, 10)}.${row.periodFrom.slice(5, 7)}–${row.periodTo.slice(8, 10)}.${row.periodTo.slice(5, 7)}.${row.periodTo.slice(0, 4)}`
}

function scopeLabel(row: ExpenseRow) {
  if (row.scope === 'exclude') return 'Исключено'
  if (row.scope === 'pnl_only_admin') return 'P&L only'
  if (row.scope === 'cashflow_reconciliation') return 'cashflow сверка'
  if (row.scope === 'period_allocated') return 'Распределяется'
  return 'Требует сверки'
}

function includeBadge(row: ExpenseRow) {
  if (!row.include) return <Badge tone="bad">исключено</Badge>
  if (row.scope === 'reconciliation_required') return <Badge tone="warn">берём после сверки</Badge>
  return <Badge tone="ok">берём</Badge>
}

function statusBadge(row: ExpenseRow) {
  if (row.status === 'ready_for_pnl') return <Badge tone="ok">готово</Badge>
  if (row.status === 'pnl_only') return <Badge tone="neutral">P&L only</Badge>
  if (row.status === 'excluded') return <Badge tone="bad">исключено</Badge>
  if (row.status === 'reconciliation_required') return <Badge tone="warn">сверка</Badge>
  return <Badge tone="warn">черновик</Badge>
}

function ExpensesControlStrip() {
  const unallocated = expenseRows.filter((row) => row.scope === 'reconciliation_required')
  const unallocatedAmount = unallocated.reduce((sum, row) => sum + (row.amountKopecks ?? 0), 0)

  return (
    <section className="vella-final-expense-control" aria-label="Контроль расходов">
      <div className="vella-final-control-head">
        <div>
          <div className="vella-final-control-kicker">Расходы не распределены</div>
          <b>Период закрывается только после правил по спорным статьям</b>
        </div>
        <Badge tone="warn">нужно правило Максима</Badge>
      </div>
      <div className="vella-final-control-grid">
        <div>
          <span>Сумма за период</span>
          <b>{formatRub(unallocatedAmount)}</b>
        </div>
        <div>
          <span>WB / Avito</span>
          <b>72% / 28%</b>
        </div>
        <div>
          <span>Anomi / Esseri</span>
          <b>61% / 39%</b>
        </div>
        <div>
          <span>Статус</span>
          <b>требует сверки</b>
        </div>
      </div>
    </section>
  )
}

const defaultExpenseDraft: ExpenseDraftInput = {
  ddsArticleName: '',
  direction: 'outflow',
  amountKopecks: 0,
  periodFrom: '2026-05-01',
  periodTo: '2026-05-31',
  sourceType: 'manual',
  scope: 'pnl_only_admin',
  allocationDriver: null,
  ownerUserId: 'maxim',
  comment: null,
}

function AddExpenseDraftForm({
  saved,
}: {
  saved: boolean
}) {
  return (
    <>
      <p className="vella-muted">Черновик не участвует в закрытии периода до проверки правила статьи ДДС.</p>
      {saved ? <div className="vella-final-draft-note">Черновик расхода сохранён в демо-слое. Backend endpoint ещё не подключён.</div> : null}
      <div className="vella-final-form-grid">
        <label>
          <span>Статья ДДС</span>
          <input defaultValue="Новая статья расхода" />
        </label>
        <label>
          <span>Направление</span>
          <select defaultValue={defaultExpenseDraft.direction}>
            <option value="outflow">Выбытие</option>
          </select>
        </label>
        <label>
          <span>Сумма</span>
          <input defaultValue="0 ₽" inputMode="decimal" />
        </label>
        <label>
          <span>Период</span>
          <input defaultValue="01.05.2026 — 31.05.2026" />
        </label>
        <label>
          <span>Источник</span>
          <select defaultValue={defaultExpenseDraft.sourceType}>
            <option value="manual">Ручной ввод</option>
            <option value="excel_fallback">Excel fallback</option>
            <option value="one_c">1С ДДС</option>
          </select>
        </label>
        <label>
          <span>Тип</span>
          <select defaultValue={defaultExpenseDraft.scope}>
            <option value="pnl_only_admin">P&L only</option>
            <option value="period_allocated">распределяется</option>
            <option value="reconciliation_required">требует сверки</option>
          </select>
        </label>
        <label>
          <span>Драйвер SKU</span>
          <select defaultValue="">
            <option value="">нет</option>
            <option value="orders">orders</option>
            <option value="units">units</option>
            <option value="production_units">production_units</option>
            <option value="shipments">shipments</option>
            <option value="revenue">revenue</option>
            <option value="manual">manual</option>
          </select>
        </label>
        <label>
          <span>Ответственный</span>
          <select defaultValue={defaultExpenseDraft.ownerUserId}>
            <option value="maxim">Максим</option>
            <option value="maria">Мария</option>
          </select>
        </label>
        <label className="wide">
          <span>Комментарий</span>
          <textarea placeholder="Что это за расход и как его учитывать" />
        </label>
      </div>
    </>
  )
}

export function WbExpensesPage() {
  const [filter, setFilter] = useState('Все')
  const [query, setQuery] = useState('')
  const [drawerRow, setDrawerRow] = useState<ExpenseRow | null>(null)
  const [addExpenseOpen, setAddExpenseOpen] = useState(false)
  const [draftSaved, setDraftSaved] = useState(false)

  const rows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return expenseRows
      .filter((row) => {
        if (filter === 'Все') return true
        if (filter === 'Берём') return row.include
        if (filter === 'Исключено') return row.scope === 'exclude'
        if (filter === 'P&L only') return row.scope === 'pnl_only_admin'
        if (filter === 'Требует сверки') return row.scope === 'reconciliation_required'
        if (filter === 'Распределяется') return row.scope === 'period_allocated'
        if (filter === 'Поступления') return row.direction === 'inflow'
        if (filter === 'Выбытия') return row.direction === 'outflow'
        return true
      })
      .filter((row) => !normalizedQuery || `${row.ddsArticleName} ${row.comment ?? ''} ${row.sourceLabel}`.toLowerCase().includes(normalizedQuery))
  }, [filter, query])

  const columns: Array<DataColumn<ExpenseRow>> = [
    { key: 'article', label: 'Статья ДДС', sticky: true, render: (row) => <><b>{row.ddsArticleName}</b><span className="sub">{row.comment}</span></> },
    { key: 'period', label: 'Период', render: periodLabel },
    { key: 'direction', label: 'Направление', render: directionLabel },
    { key: 'amount', label: 'Сумма', numeric: true, render: (row) => row.amountKopecks == null ? '—' : formatRub(row.amountKopecks) },
    { key: 'include', label: 'Брать', render: includeBadge },
    { key: 'scope', label: 'Тип', render: scopeLabel },
    { key: 'driver', label: 'Драйвер', render: (row) => row.allocationDriver ?? '—' },
    { key: 'pnl', label: 'P&L', render: (row) => row.entersCompanyPnl ? <b>да</b> : 'нет' },
    { key: 'sku', label: 'SKU', render: (row) => row.entersSkuPnl ? `${row.skuCoveragePct ?? 0}%` : <span className="subline">нет</span> },
    { key: 'status', label: 'Статус', render: statusBadge },
    { key: 'action', label: 'Действие', render: (row) => <button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(row)}>Правило</button> },
  ]

  return (
    <VellaProductionShell
      title="Расходы WB"
      subtitle="Классификация статей ДДС и качество распределения расходов. Это не готовый P&L и не SKU-выручка."
      mobileTitle="Расходы WB доступны в desktop-версии"
      mobileCopy="Статьи расходов, подтверждающий сотрудник и база распределения требуют широкого рабочего экрана."
      topbarActions={(
        <>
          <div className="vella-final-period-control" aria-label="Период">
            <button type="button">1 день</button>
            <button className="active" type="button">7 дней</button>
            <button type="button">14 дней</button>
            <button type="button">30 дней</button>
          </div>
          <button className="vella-button" type="button"><RefreshCw size={16} /> Проверить ДДС</button>
          <button className="vella-button" type="button"><FileSpreadsheet size={16} /> Экспорт</button>
        </>
      )}
    >
      <VellaFinalMetrics items={[
        { label: 'Все расходы', value: formatRub(expenseSummaryMetrics.totalExpensesKopecks), delta: 'без поступлений и исключённых', tone: 'up', tip: 'Сумма включённых расходных ДДС-строк за период: без поступлений покупателей и красных исключённых статей.' },
        { label: 'P&L учтено', value: formatRub(expenseSummaryMetrics.pnlOnlyKopecks), delta: 'P&L only · без SKU', tone: 'neutral', tip: 'Административные расходы не делятся на SKU, но попадают в общий P&L и план-факт месяца.' },
        { label: 'Чистая прибыль', value: formatRub(expenseSummaryMetrics.draftNetProfitKopecks), delta: 'черновой расчёт', tone: 'neutral', tip: 'Черновой расчёт по учтённым строкам, не закрытый P&L.' },
        { label: 'Требует сверки', value: formatRub(expenseSummaryMetrics.reconciliationRequiredKopecks), delta: 'поставщик без правила', tone: 'down', tip: 'Статьи ДДС, которые нельзя автоматически считать расходом SKU или P&L без ручного правила.' },
      ]} />
      <SourceStrip
        kicker="финансовый конвейер"
        chips={['1С ДДС', 'cashflow', 'проверка перед P&L']}
        title="ДДС → правила статей → P&L / сверка cashflow / SKU-драйверы"
        meta="ДДС — источник движения денег, а не готовая SKU-экономика. Административные расходы идут только в P&L; красные статьи исключены; поступления покупателей используются для сверки, не как SKU-выручка."
      />
      <ExpensesControlStrip />
      <FilterToolbar
        searchPlaceholder="Статья ДДС, тип, причина или ответственный..."
        query={query}
        onQueryChange={setQuery}
        filters={filters}
        activeFilter={filter}
        onFilterChange={setFilter}
        right={(
          <>
            <button className="btn btn-default btn-sm" type="button" onClick={() => { setDraftSaved(false); setAddExpenseOpen(true) }}><Plus size={14} />Добавить расход</button>
            <button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(expenseRows[0])}>Правило статьи ДДС</button>
            <button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(expenseRows[0])}>SKU-драйвер</button>
            <button className="btn btn-default btn-sm" type="button" onClick={() => setDrawerRow(expenseRows[4])}>Проверка строки ДДС</button>
          </>
        )}
      />
      <FilterSummary shown={rows.length} total={expenseRows.length} label={filter} onReset={() => { setFilter('Все'); setQuery('') }} />
      <DataTable rows={rows} columns={columns} className="vella-final-expenses-table" onRowClick={setDrawerRow} />
      <Drawer
        open={addExpenseOpen}
        title="Добавить расход"
        meta="ручной черновик"
        tag="черновик"
        onClose={() => setAddExpenseOpen(false)}
        footer={<><button className="btn btn-ghost btn-sm" type="button" onClick={() => setAddExpenseOpen(false)}>Отмена</button><button className="btn btn-default btn-sm" type="button" onClick={() => setDraftSaved(true)}>Сохранить черновик</button></>}
      >
        <AddExpenseDraftForm saved={draftSaved} />
      </Drawer>
      <Drawer
        open={Boolean(drawerRow)}
        title="Правило статьи ДДС"
        meta={drawerRow?.ddsArticleName ?? '1С · ДДС'}
        tag="финансы"
        onClose={() => setDrawerRow(null)}
        footer={<><button className="btn btn-ghost btn-sm" type="button" onClick={() => setDrawerRow(null)}>Отмена</button><button className="btn btn-default btn-sm" type="button">Сохранить черновик</button></>}
      >
        <p className="vella-muted">ДДС работает по cash-basis. Поступления покупателей используются только для сверки cashflow и не заменяют WB-выручку.</p>
        {drawerRow ? (
          <div className="vella-final-drawer-grid">
            <b>Тип</b><span>{scopeLabel(drawerRow)}</span>
            <b>P&L</b><span>{drawerRow.entersCompanyPnl ? 'входит' : 'не входит'}</span>
            <b>SKU</b><span>{drawerRow.entersSkuPnl ? 'входит после драйвера' : 'не входит'}</span>
            <b>Причина</b><span>{drawerRow.comment}</span>
          </div>
        ) : null}
      </Drawer>
    </VellaProductionShell>
  )
}
