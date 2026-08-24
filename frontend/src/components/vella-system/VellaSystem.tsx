import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import {
  ChevronDown,
  Check,
  Info,
  LayoutDashboard,
  X,
} from 'lucide-react'
import { type ReactNode } from 'react'
import './tokens.css'

type Variant = 'primary' | 'default' | 'ghost' | 'danger'
type BadgeVariant = 'success' | 'warning' | 'danger' | 'neutral' | 'brand'
type ToastVariant = 'info' | 'success' | 'warn' | 'error'

function classNames(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

export type VellaNavItem = {
  id: string
  label: string
  icon?: ReactNode
  count?: string | number
  active?: boolean
  onClick?: () => void
}

export type VellaNavGroup = {
  label: string
  items: VellaNavItem[]
}

export function VellaShell({
  groups,
  breadcrumb,
  title,
  subtitle,
  topbarActions,
  tabs,
  children,
}: {
  groups: VellaNavGroup[]
  breadcrumb: ReactNode
  title?: string
  subtitle?: string
  topbarActions?: ReactNode
  tabs?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="vella-system">
      <div className="vs-shell">
        <aside className="vs-sidebar">
          <div className="vs-logo">
            <div className="vs-logo-mark">S</div>
            <div>
              <div className="vs-logo-name">SATORNA</div>
              <div className="vs-logo-sub">WB workspace</div>
            </div>
          </div>
          <nav className="vs-nav-scroll" aria-label="Vella navigation">
            {groups.map((group) => (
              <div className="vs-nav-group" key={group.label}>
                <div className="vs-nav-label">{group.label}</div>
                {group.items.map((item) => (
                  <button
                    className={classNames('vs-nav-item', item.active && 'active')}
                    key={item.id}
                    type="button"
                    onClick={item.onClick}
                  >
                    <span className="vs-nav-icon">{item.icon ?? <LayoutDashboard size={16} />}</span>
                    <span className="vs-nav-text">{item.label}</span>
                    {item.count ? <span className="vs-nav-count">{item.count}</span> : null}
                  </button>
                ))}
              </div>
            ))}
          </nav>
        </aside>
        <main className="vs-main">
          <div className="vs-topbar">
            <div className="vs-breadcrumb">{breadcrumb}</div>
            <div className="vs-top-actions">{topbarActions}</div>
          </div>
          <section className="vs-content">
            {tabs}
            {title ? (
              <header>
                <h1 className="vs-page-title">{title}</h1>
                {subtitle ? <p className="vs-page-copy">{subtitle}</p> : null}
              </header>
            ) : null}
            {children}
          </section>
        </main>
      </div>
    </div>
  )
}

export function VellaButton({
  variant = 'default',
  loading,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  loading?: boolean
}) {
  return (
    <button className={classNames('vs-btn', variant, loading && 'loading', className)} type="button" {...props}>
      {loading ? <span className="vs-mono">...</span> : null}
      {children}
    </button>
  )
}

export function VellaIconButton({
  variant = 'default',
  label,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  label: string
}) {
  return (
    <button aria-label={label} className={classNames('vs-icon-btn', variant, className)} type="button" {...props}>
      {children}
    </button>
  )
}

export function VellaInput({
  icon,
  error,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  icon?: ReactNode
  error?: boolean
}) {
  return (
    <label className={classNames('vs-input-wrap', error && 'error', className)}>
      {icon}
      <input className="vs-input" {...props} />
    </label>
  )
}

export function VellaSelect({
  value,
  options,
  onChange,
  placeholder,
  disabled,
}: {
  value: string
  options: Array<{ value: string; label: string; disabled?: boolean }>
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
}) {
  const selected = options.find((option) => option.value === value)

  return (
    <VellaDropdown
      align="start"
      contentClassName="vs-select-content"
      trigger={(
        <button className="vs-select-trigger" disabled={disabled} type="button">
          <span>{selected?.label ?? placeholder ?? 'Выберите'}</span>
          <ChevronDown size={14} />
        </button>
      )}
    >
      {options.map((option) => (
        <DropdownMenuPrimitive.Item
          className="vs-select-option"
          disabled={option.disabled}
          key={option.value}
          onSelect={() => onChange(option.value)}
        >
          <span className="vs-select-check">{option.value === value ? <Check size={15} /> : null}</span>
          <span>{option.label}</span>
        </DropdownMenuPrimitive.Item>
      ))}
    </VellaDropdown>
  )
}

export function VellaChip({
  active,
  tone,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean
  tone?: 'brand' | 'warn'
}) {
  return (
    <button className={classNames('vs-chip', active && 'active', tone, className)} type="button" {...props}>
      {children}
    </button>
  )
}

export function VellaBadge({ variant, children }: { variant: BadgeVariant; children: ReactNode }) {
  return <span className={classNames('vs-badge', variant)}>{children}</span>
}

export function VellaTabs({
  items,
  activeId,
  onChange,
}: {
  items: Array<{ id: string; label: string; count?: string | number; icon?: ReactNode }>
  activeId: string
  onChange: (id: string) => void
}) {
  return (
    <div className="vs-subtabs" role="tablist">
      {items.map((item) => (
        <button
          aria-selected={item.id === activeId}
          className={classNames('vs-subtab', item.id === activeId && 'active')}
          key={item.id}
          role="tab"
          type="button"
          onClick={() => onChange(item.id)}
        >
          {item.icon}
          {item.label}
          {item.count ? <span className="vs-subtab-count">{item.count}</span> : null}
        </button>
      ))}
    </div>
  )
}

export function VellaMetricStrip({
  items,
}: {
  items: Array<{ label: string; value: ReactNode; meta: string; metaTone?: 'good' | 'bad'; tip?: string }>
}) {
  return (
    <div className="vs-kpi-strip">
      {items.map((item) => (
        <div className="vs-kpi" key={item.label}>
          <div className="vs-kpi-label">
            {item.label}
            {item.tip ? <VellaTooltip content={item.tip}><span className="vs-help-dot">i</span></VellaTooltip> : null}
          </div>
          <div className="vs-kpi-value">{item.value}</div>
          <div className={classNames('vs-kpi-meta', item.metaTone)}>{item.meta}</div>
        </div>
      ))}
    </div>
  )
}

export function VellaToolbar({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <div className="vs-toolbar">
      <div className="vs-toolbar-left">{left}</div>
      {right ? <div className="vs-toolbar-right">{right}</div> : null}
    </div>
  )
}

export function VellaCheckbox({
  checked,
  indeterminate,
  label,
  onClick,
}: {
  checked?: boolean
  indeterminate?: boolean
  label: string
  onClick?: () => void
}) {
  return (
    <button
      aria-label={label}
      aria-checked={indeterminate ? 'mixed' : Boolean(checked)}
      className={classNames('vs-checkbox', checked && 'checked', indeterminate && 'indeterminate')}
      role="checkbox"
      type="button"
      onClick={onClick}
    >
      {checked ? <Check size={12} /> : indeterminate ? '-' : null}
    </button>
  )
}

export type VellaTableColumn<Row> = {
  id: string
  label: string
  render: (row: Row) => ReactNode
  sortable?: boolean
  numeric?: boolean
  hidden?: boolean
}

export function VellaTable<Row extends { id: string }>({
  rows,
  columns,
  selectedIds,
  sortId,
  sortDirection,
  empty,
  onSort,
  onToggleRow,
}: {
  rows: Row[]
  columns: Array<VellaTableColumn<Row>>
  selectedIds?: Set<string>
  sortId?: string
  sortDirection?: 'asc' | 'desc'
  empty?: ReactNode
  onSort?: (id: string) => void
  onToggleRow?: (id: string) => void
}) {
  const visibleColumns = columns.filter((column) => !column.hidden)

  return (
    <div className="vs-table-wrap">
      {rows.length ? (
        <table className="vs-table">
          <thead>
            <tr>
              {onToggleRow ? <th style={{ width: 42 }}> </th> : null}
              {visibleColumns.map((column) => (
                <th key={column.id} style={{ textAlign: column.numeric ? 'right' : 'left' }}>
                  {column.sortable ? (
                    <button className="vs-dropdown-item" type="button" onClick={() => onSort?.(column.id)}>
                      <span>{column.label}</span>
                      <span className={classNames('vs-sort', sortId === column.id && 'active')}>
                        {sortId === column.id ? (sortDirection === 'asc' ? '↑' : '↓') : '↕'}
                      </span>
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr className={selectedIds?.has(row.id) ? 'selected' : undefined} key={row.id}>
                {onToggleRow ? (
                  <td>
                    <VellaCheckbox checked={selectedIds?.has(row.id)} label="Выбрать строку" onClick={() => onToggleRow(row.id)} />
                  </td>
                ) : null}
                {visibleColumns.map((column) => (
                  <td key={column.id} style={{ textAlign: column.numeric ? 'right' : 'left' }}>
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="vs-empty">{empty ?? <div><div className="vs-empty-title">Нет данных</div><div>Измените фильтры или период.</div></div>}</div>
      )}
    </div>
  )
}

export function VellaDropdown({
  trigger,
  children,
  open,
  onOpenChange,
  align = 'end',
  contentClassName,
}: {
  trigger: ReactNode
  children: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
  align?: 'start' | 'center' | 'end'
  contentClassName?: string
}) {
  return (
    <DropdownMenuPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DropdownMenuPrimitive.Trigger asChild>{trigger}</DropdownMenuPrimitive.Trigger>
      <DropdownMenuPrimitive.Portal>
        <DropdownMenuPrimitive.Content align={align} className={classNames('vs-dropdown-content', contentClassName)} sideOffset={6}>
          {children}
        </DropdownMenuPrimitive.Content>
      </DropdownMenuPrimitive.Portal>
    </DropdownMenuPrimitive.Root>
  )
}

export function VellaDropdownItem({
  children,
  checked,
  onSelect,
}: {
  children: ReactNode
  checked?: boolean
  onSelect?: () => void
}) {
  return (
    <DropdownMenuPrimitive.Item className="vs-dropdown-item" onSelect={onSelect}>
      <span>{children}</span>
      {checked ? <Check size={14} /> : null}
    </DropdownMenuPrimitive.Item>
  )
}

export function VellaPopover({
  trigger,
  children,
  open,
  onOpenChange,
  align = 'end',
}: {
  trigger: ReactNode
  children: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
  align?: 'start' | 'center' | 'end'
}) {
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <PopoverPrimitive.Trigger asChild>{trigger}</PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content align={align} className="vs-popover-content" sideOffset={6}>
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}

export function VellaTooltip({ children, content }: { children: ReactNode; content: ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={180}>
      <TooltipPrimitive.Root>
        <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
        <TooltipPrimitive.Portal>
          <TooltipPrimitive.Content className="vs-tooltip-content" sideOffset={8}>
            {content}
          </TooltipPrimitive.Content>
        </TooltipPrimitive.Portal>
      </TooltipPrimitive.Root>
    </TooltipPrimitive.Provider>
  )
}

export function VellaModal({
  open,
  title,
  description,
  children,
  footer,
  onOpenChange,
}: {
  open: boolean
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  onOpenChange: (open: boolean) => void
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="vs-modal-overlay" onClick={() => onOpenChange(false)} />
        <DialogPrimitive.Content className="vs-modal-content">
          <div className="vs-modal-head">
            <div>
              <DialogPrimitive.Title className="vs-modal-title">{title}</DialogPrimitive.Title>
              {description ? <DialogPrimitive.Description className="vs-modal-desc">{description}</DialogPrimitive.Description> : null}
            </div>
            <DialogPrimitive.Close asChild>
              <VellaIconButton label="Закрыть">
                <X size={15} />
              </VellaIconButton>
            </DialogPrimitive.Close>
          </div>
          <div className="vs-modal-body">{children}</div>
          {footer ? <div className="vs-modal-foot">{footer}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function VellaDrawer({
  open,
  title,
  subtitle,
  tabs,
  activeTab,
  onTabChange,
  children,
  footer,
  onOpenChange,
}: {
  open: boolean
  title: string
  subtitle?: ReactNode
  tabs?: Array<{ id: string; label: string }>
  activeTab?: string
  onTabChange?: (id: string) => void
  children: ReactNode
  footer?: ReactNode
  onOpenChange: (open: boolean) => void
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="vs-drawer-overlay" onClick={() => onOpenChange(false)} />
        <DialogPrimitive.Content className="vs-drawer-content">
          <div className="vs-drawer-head">
            <div>
              <DialogPrimitive.Title className="vs-drawer-title">{title}</DialogPrimitive.Title>
              {subtitle ? <div className="vs-modal-desc">{subtitle}</div> : null}
            </div>
            <DialogPrimitive.Close asChild>
              <VellaIconButton label="Закрыть">
                <X size={15} />
              </VellaIconButton>
            </DialogPrimitive.Close>
          </div>
          {tabs ? (
            <div className="vs-drawer-tabs">
              {tabs.map((tab) => (
                <button
                  className={classNames('vs-drawer-tab', tab.id === activeTab && 'active')}
                  key={tab.id}
                  type="button"
                  onClick={() => onTabChange?.(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : null}
          <div className="vs-drawer-body">{children}</div>
          {footer ? <div className="vs-drawer-foot">{footer}</div> : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function VellaBulkBar({
  count,
  children,
  onClose,
}: {
  count: number
  children: ReactNode
  onClose: () => void
}) {
  if (!count) return null
  return (
    <div className="vs-bulk-bar">
      <div className="vs-bulk-count">{count} выделено</div>
      {children}
      <button aria-label="Закрыть панель действий" className="vs-bulk-btn" type="button" onClick={onClose}>
        <X size={14} />
      </button>
    </div>
  )
}

export function VellaBulkButton({
  children,
  onClick,
}: {
  children: ReactNode
  onClick?: () => void
}) {
  return (
    <button className="vs-bulk-btn" type="button" onClick={onClick}>
      {children}
    </button>
  )
}

export function VellaToastStack({ items }: { items: Array<{ id: number; text: string; variant: ToastVariant }> }) {
  return (
    <div className="vs-toast-stack">
      {items.map((toast) => (
        <div className={classNames('vs-toast', toast.variant)} key={toast.id}>
          <Info size={15} />
          <span>{toast.text}</span>
        </div>
      ))}
    </div>
  )
}

export function VellaCalendar({ selectedDay, onSelectDay }: { selectedDay: number; onSelectDay: (day: number) => void }) {
  const days = Array.from({ length: 31 }, (_, index) => index + 1)
  const weekdays = ['ПН', 'ВТ', 'СР', 'ЧТ', 'ПТ', 'СБ', 'ВС']

  return (
    <div className="vs-calendar">
      <div className="vs-calendar-head">
        <span>Апрель — Май 2026</span>
        <span className="vs-row">
          <VellaIconButton label="Предыдущий месяц">‹</VellaIconButton>
          <VellaIconButton label="Следующий месяц">›</VellaIconButton>
        </span>
      </div>
      <div className="vs-calendar-grid">
        {weekdays.map((weekday) => <div className="vs-calendar-weekday" key={weekday}>{weekday}</div>)}
        {days.map((day) => (
          <button
            className={classNames('vs-calendar-day', selectedDay === day && 'active')}
            key={day}
            type="button"
            onClick={() => onSelectDay(day)}
          >
            {day}
          </button>
        ))}
      </div>
    </div>
  )
}

export function VellaInlineEdit({
  value,
  editing,
  onEdit,
  onChange,
  onSave,
}: {
  value: string
  editing: boolean
  onEdit: () => void
  onChange: (value: string) => void
  onSave: () => void
}) {
  if (editing) {
    return (
      <span className="vs-inline-edit">
        <input autoFocus value={value} onChange={(event) => onChange(event.target.value)} onKeyDown={(event) => {
          if (event.key === 'Enter') onSave()
        }} />
        <VellaIconButton label="Сохранить" onClick={onSave}>
          <Check size={14} />
        </VellaIconButton>
      </span>
    )
  }

  return (
    <button className="vs-btn ghost" type="button" onClick={onEdit}>
      {value}
    </button>
  )
}
