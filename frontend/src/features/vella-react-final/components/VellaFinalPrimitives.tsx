import { Search } from 'lucide-react'
import type { ReactNode } from 'react'

function classes(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

export function VellaFinalMetrics({
  items,
}: {
  items: Array<{ label: string; value: ReactNode; delta?: string; tone?: 'up' | 'down' | 'neutral'; tip?: string }>
}) {
  return (
    <div className="stats vella-final-kpis">
      {items.map((item) => (
        <div className="stat" key={item.label}>
          <div className="stat-label">
            {item.label}
            {item.tip ? <span className="stat-tip" data-tip={item.tip} title={item.tip}>?</span> : null}
          </div>
          <div className="stat-val">{item.value}</div>
          {item.delta ? <div className={classes('stat-delta', item.tone)}>{item.delta}</div> : null}
        </div>
      ))}
    </div>
  )
}

export function SourceStrip({
  tone = 'partial',
  kicker,
  title,
  meta,
  chips,
  action,
}: {
  tone?: 'fresh' | 'partial' | 'warn'
  kicker: string
  title: string
  meta: string
  chips: string[]
  action?: ReactNode
}) {
  return (
    <div className="report-source-strip report-source-compact">
      <div className={classes('source-state-card', tone)}>
        <div>
          <div className="source-state-kicker">
            <span>{kicker}</span>
            {chips.map((chip) => <span className="source-state-chip" key={chip}>{chip}</span>)}
          </div>
          <div className="source-state-title">{title}</div>
          <div className="source-state-meta">{meta}</div>
        </div>
        {action ? <div className="toolbar-right">{action}</div> : null}
      </div>
    </div>
  )
}

export function FilterToolbar({
  searchPlaceholder,
  query,
  onQueryChange,
  filters,
  activeFilter,
  onFilterChange,
  right,
}: {
  searchPlaceholder: string
  query: string
  onQueryChange: (value: string) => void
  filters: string[]
  activeFilter: string
  onFilterChange: (filter: string) => void
  right?: ReactNode
}) {
  return (
    <div className="toolbar">
      <label className="search vella-final-search">
        <Search size={13} />
        <input value={query} placeholder={searchPlaceholder} onChange={(event) => onQueryChange(event.target.value)} />
      </label>
      <div className="chips" role="group" aria-label="Фильтры">
        {filters.map((filter) => (
          <button
            aria-pressed={filter === activeFilter}
            className={classes('chip', filter === activeFilter && 'active')}
            key={filter}
            type="button"
            onClick={() => onFilterChange(filter)}
          >
            {filter}
          </button>
        ))}
      </div>
      {right ? <div className="toolbar-right">{right}</div> : null}
    </div>
  )
}

export function FilterSummary({
  shown,
  total,
  label,
  onReset,
}: {
  shown: number
  total: number
  label: string
  onReset: () => void
}) {
  return (
    <div className="report-filter-summary" data-filter-summary>
      <span>Показано <b>{shown} из {total}</b> · фильтры: {label}</span>
      <button className="btn btn-ghost btn-sm" type="button" onClick={onReset}>Сбросить</button>
    </div>
  )
}

export type DataColumn<Row> = {
  key: string
  label: ReactNode
  render: (row: Row) => ReactNode
  numeric?: boolean
  sticky?: boolean
}

export function DataTable<Row extends { id: string }>({
  columns,
  rows,
  className,
  wrapperClassName,
  onRowClick,
}: {
  columns: Array<DataColumn<Row>>
  rows: Row[]
  className?: string
  wrapperClassName?: string
  onRowClick?: (row: Row) => void
}) {
  return (
    <div className={classes('report-table-wrap', wrapperClassName)}>
      <table className={classes('report-mid', className)}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th className={classes(column.numeric && 'num', column.sticky && 'report-sticky')} key={column.key}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              data-report-row
              key={row.id}
              onClick={() => onRowClick?.(row)}
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((column) => (
                <td
                  className={classes(column.numeric && 'num', column.sticky && 'report-sticky')}
                  data-sticky-column={column.sticky ? 'true' : undefined}
                  key={column.key}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 ? (
        <div className="empty show">
          <div className="empty-title">Нет строк по выбранным фильтрам</div>
          <div className="empty-desc">Сбросьте фильтр или строку поиска.</div>
        </div>
      ) : null}
    </div>
  )
}

export function Badge({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'new' | 'neutral'; children: ReactNode }) {
  return <span className={classes('report-tag', tone)}>{children}</span>
}

export function Drawer({
  open,
  title,
  meta,
  tag,
  children,
  footer,
  onClose,
}: {
  open: boolean
  title: string
  meta: string
  tag: string
  children: ReactNode
  footer?: ReactNode
  onClose: () => void
}) {
  return (
    <>
      <div className={classes('drawer-overlay', open && 'open')} aria-hidden={!open} onClick={onClose} />
      <aside className={classes('drawer finance-drawer', open && 'open')} data-drawer role="dialog" aria-modal="true" aria-hidden={!open}>
        <div className="drawer-header">
          <div className="drawer-info">
            <div className="drawer-title">{title}</div>
            <div className="drawer-meta"><span className="drawer-sku">{meta}</span><span className="report-tag fin">{tag}</span></div>
          </div>
          <button className="drawer-close" type="button" aria-label="Закрыть" onClick={onClose}>x</button>
        </div>
        <div className="drawer-body">{children}</div>
        {footer ? <div className="finance-drawer-actions">{footer}</div> : null}
      </aside>
    </>
  )
}
