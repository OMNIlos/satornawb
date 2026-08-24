import { useMemo, useState } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  Bell,
  CheckCheck,
  Clock3,
  Download,
  ExternalLink,
  Filter,
  Info,
  Search,
  ShieldAlert,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import {
  DEFAULT_NOTIFICATION_FILTERS,
  NOTIFICATION_CATEGORY_LABELS,
  NOTIFICATION_SEVERITY_LABELS,
  filterNotifications,
  getNotificationManagers,
  getNotificationPeriodLabel,
  getNotificationReadLabel,
  getUnreadCount,
} from './repository.js'
import { useNotifications } from './notificationContext.js'
import type {
  NotificationCategory,
  NotificationEvent,
  NotificationFilters,
  NotificationPeriod,
  NotificationReadFilter,
  NotificationSeverity,
} from './types.js'

const categoryOptions: Array<NotificationCategory | 'all'> = ['all', 'reports', 'prices', 'orders', 'avito', 'ai', 'system']
const severityOptions: Array<NotificationSeverity | 'all'> = ['all', 'critical', 'warning', 'info']
const periodOptions: NotificationPeriod[] = ['1d', '7d', '14d', '30d']
const readOptions: NotificationReadFilter[] = ['all', 'unread', 'read']

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function severityClass(severity: NotificationSeverity) {
  if (severity === 'critical') return 'text-red-600 bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-900 dark:text-red-300'
  if (severity === 'warning') return 'text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900 dark:text-amber-300'
  return 'text-blue-700 bg-blue-50 border-blue-200 dark:bg-blue-950/30 dark:border-blue-900 dark:text-blue-300'
}

function freshnessClass(state: NonNullable<NotificationEvent['freshness']>['state']) {
  if (state === 'fresh') return 'text-emerald-700 bg-emerald-50 border-emerald-200 dark:bg-emerald-950/25 dark:border-emerald-900 dark:text-emerald-300'
  if (state === 'partial' || state === 'pending') return 'text-amber-700 bg-amber-50 border-amber-200 dark:bg-amber-950/25 dark:border-amber-900 dark:text-amber-300'
  return 'text-red-700 bg-red-50 border-red-200 dark:bg-red-950/25 dark:border-red-900 dark:text-red-300'
}

function freshnessLabel(state: NonNullable<NotificationEvent['freshness']>['state']) {
  if (state === 'fresh') return 'актуально'
  if (state === 'partial') return 'частично'
  if (state === 'pending') return 'ожидается'
  return 'устарело'
}

function SeverityIcon({ severity }: { severity: NotificationSeverity }) {
  if (severity === 'critical') return <ShieldAlert className="size-4" aria-hidden="true" />
  if (severity === 'warning') return <AlertTriangle className="size-4" aria-hidden="true" />
  return <Info className="size-4" aria-hidden="true" />
}

function setFilter<K extends keyof NotificationFilters>(
  filters: NotificationFilters,
  key: K,
  value: NotificationFilters[K],
) {
  return { ...filters, [key]: value }
}

export function NotificationsPage() {
  const navigate = useNavigate()
  const { items, loadError, markRead, markAllRead } = useNotifications()
  const [filters, setFilters] = useState<NotificationFilters>(DEFAULT_NOTIFICATION_FILTERS)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [exportMessage, setExportMessage] = useState<string | null>(null)

  const filteredItems = useMemo(() => filterNotifications(items, filters), [items, filters])
  const unreadCount = useMemo(() => getUnreadCount(items), [items])
  const criticalCount = useMemo(() => items.filter((item) => !item.readAt && item.severity === 'critical').length, [items])
  const managers = useMemo(() => getNotificationManagers(items), [items])
  const lastDigestAt = useMemo(() => {
    const latest = items.reduce<string | null>((current, item) => {
      if (!current) return item.createdAt
      return new Date(item.createdAt).getTime() > new Date(current).getTime() ? item.createdAt : current
    }, null)
    return latest ? new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(latest)) : '—'
  }, [items])
  const selected = useMemo(
    () => filteredItems.find((item) => item.id === selectedId) ?? filteredItems[0] ?? items[0],
    [filteredItems, items, selectedId],
  )

  function selectItem(item: NotificationEvent) {
    setSelectedId(item.id)
  }

  function openRoute(item: NotificationEvent) {
    if (item.route) navigate(item.route)
  }

  function downloadReport(item: NotificationEvent) {
    if (!item.reportFile) return
    const file = item.reportFile
    const rows = [
      ['Отчёт', file.report],
      ['Период', file.period],
      ['Строк', String(file.rows)],
      ['Сформирован', file.generatedAt],
      [],
      ['SKU', 'Кампания', 'ДРР', 'Заказы', 'Рекомендация'],
      ['FBBT_42', 'Футболка белая Принт 42', '9.1%', '34', 'оставить'],
      ['HCBT_17', 'Худи чёрное Принт 17', '7.8%', '18', 'оставить'],
      ['LBBT_33', 'Лонгслив белый Принт 33', '25.0%', '3', 'стоп реклама'],
    ]
    const html = `
      <html><head><meta charset="utf-8"></head><body>
        <table>${rows.map((row) => `<tr>${row.map((cell) => `<td>${String(cell ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')}</td>`).join('')}</tr>`).join('')}</table>
      </body></html>`
    const blob = new Blob(['\ufeff' + html], { type: 'application/vnd.ms-excel;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.fileName
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
    markRead(item.id)
    setExportMessage(`Скачан сохранённый отчёт: ${file.fileName}`)
  }

  function handleRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, item: NotificationEvent) {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    selectItem(item)
  }

  return (
    <div className="flex min-h-full flex-col bg-background">
      <section className="border-b bg-card px-4 py-4 md:px-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start">
          <div className="min-w-0 flex-1">
            <h1 className="text-[22px] font-bold tracking-normal text-foreground">Центр уведомлений</h1>
            <p className="mt-1 max-w-4xl text-sm leading-5 text-muted-foreground">
              Единый журнал алертов, отчётов и операционных событий. Колокольчик сверху показывает свежие и критичные события.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" className="h-8 gap-2" onClick={markAllRead}>
              <CheckCheck className="size-3.5" />
              Прочитать всё
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-2"
              title="Сформировать выгрузку по текущим фильтрам"
              onClick={() => setExportMessage(`Экспорт уведомлений поставлен в очередь: ${filteredItems.length} событий`)}
            >
              <Download className="size-3.5" />
              Экспорт
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-3 px-4 py-4 md:grid-cols-4 md:px-6">
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>Новые</span>
            <Bell className="size-4" />
          </div>
          <div className="mt-2 text-2xl font-bold">{unreadCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>Критичные</span>
            <ShieldAlert className="size-4 text-red-500" />
          </div>
          <div className="mt-2 text-2xl font-bold text-red-600">{criticalCount}</div>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>За период</span>
            <Filter className="size-4" />
          </div>
          <div className="mt-2 text-2xl font-bold">{filteredItems.length}</div>
        </div>
        <div className="rounded-lg border bg-card p-3">
          <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
            <span>Последний дайджест</span>
            <Clock3 className="size-4" />
          </div>
          <div className="mt-2 text-2xl font-bold">{lastDigestAt}</div>
        </div>
      </section>

      {exportMessage && (
        <div className="mx-4 mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900 md:mx-6 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">
          {exportMessage}
        </div>
      )}

      {loadError && (
        <div className="mx-4 mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 md:mx-6 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
          Уведомления временно недоступны. Показываем последний сохранённый снимок.
        </div>
      )}

      <section className="grid min-h-0 flex-1 gap-4 px-4 pb-5 lg:grid-cols-[minmax(0,1fr)_360px] md:px-6">
        <div className="min-w-0 overflow-hidden rounded-lg border bg-card">
          <div className="flex flex-wrap items-center gap-2 border-b p-3">
            <div className="relative min-w-[240px] flex-1 sm:max-w-[360px]">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={filters.query}
                onChange={(event) => setFilters((current) => setFilter(current, 'query', event.target.value))}
                className="h-8 pl-8"
                placeholder="SKU, менеджер, раздел, текст..."
              />
            </div>
            <select
              className="h-8 rounded-md border bg-background px-2 text-sm"
              value={filters.period}
              onChange={(event) => setFilters((current) => setFilter(current, 'period', event.target.value as NotificationPeriod))}
              aria-label="Период уведомлений"
            >
              {periodOptions.map((period) => <option key={period} value={period}>{getNotificationPeriodLabel(period)}</option>)}
            </select>
            <select
              className="h-8 rounded-md border bg-background px-2 text-sm"
              value={filters.manager}
              onChange={(event) => setFilters((current) => setFilter(current, 'manager', event.target.value))}
              aria-label="Менеджер"
            >
              <option value="all">Все менеджеры</option>
              {managers.map((manager) => <option key={manager} value={manager}>{manager}</option>)}
            </select>
            <select
              className="h-8 rounded-md border bg-background px-2 text-sm"
              value={filters.read}
              onChange={(event) => setFilters((current) => setFilter(current, 'read', event.target.value as NotificationReadFilter))}
              aria-label="Статус прочтения"
            >
              {readOptions.map((read) => <option key={read} value={read}>{getNotificationReadLabel(read)}</option>)}
            </select>
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => setFilters(DEFAULT_NOTIFICATION_FILTERS)}
            >
              Сбросить
            </Button>
          </div>

          <div className="flex gap-2 overflow-x-auto border-b px-3 py-2">
            {categoryOptions.map((category) => (
              <button
                key={category}
                type="button"
                className={cn(
                  'h-7 shrink-0 rounded-full border px-3 text-xs font-semibold',
                  filters.category === category ? 'border-primary/30 bg-primary/10 text-primary' : 'border-border bg-background text-muted-foreground hover:text-foreground',
                )}
                onClick={() => setFilters((current) => setFilter(current, 'category', category))}
              >
                {category === 'all' ? 'Все категории' : NOTIFICATION_CATEGORY_LABELS[category]}
              </button>
            ))}
            {severityOptions.map((severity) => (
              <button
                key={severity}
                type="button"
                className={cn(
                  'h-7 shrink-0 rounded-full border px-3 text-xs font-semibold',
                  filters.severity === severity ? 'border-primary/30 bg-primary/10 text-primary' : 'border-border bg-background text-muted-foreground hover:text-foreground',
                )}
                onClick={() => setFilters((current) => setFilter(current, 'severity', severity))}
              >
                {severity === 'all' ? 'Все важности' : NOTIFICATION_SEVERITY_LABELS[severity]}
              </button>
            ))}
          </div>

          {filteredItems.length === 0 ? (
            <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 p-6 text-center">
              <Bell className="size-8 text-muted-foreground" />
              <div>
                <div className="font-semibold">Нет уведомлений по выбранным фильтрам</div>
                <div className="mt-1 text-sm text-muted-foreground">Сбросьте фильтры или расширьте период.</div>
              </div>
              <Button variant="outline" size="sm" onClick={() => setFilters(DEFAULT_NOTIFICATION_FILTERS)}>Сбросить фильтры</Button>
            </div>
          ) : (
            <>
              <div className="hidden overflow-x-auto md:block">
                <table className="w-full min-w-[880px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b bg-muted/40 text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                      <th className="px-3 py-2 font-semibold">Событие</th>
                      <th className="px-3 py-2 font-semibold">Категория</th>
                      <th className="px-3 py-2 font-semibold">Менеджер</th>
                      <th className="px-3 py-2 font-semibold">Раздел</th>
                      <th className="px-3 py-2 font-semibold">Время</th>
                      <th className="px-3 py-2 text-right font-semibold">Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => {
                      const active = selected?.id === item.id
                      return (
                        <tr
                          key={item.id}
                          className={cn('cursor-pointer border-b hover:bg-muted/35', active && 'bg-muted/50')}
                          tabIndex={0}
                          role="button"
                          aria-selected={active}
                          onClick={() => selectItem(item)}
                          onKeyDown={(event) => handleRowKeyDown(event, item)}
                        >
                          <td className="px-3 py-3">
                            <div className="flex items-start gap-2">
                              <span className={cn('mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-md border', severityClass(item.severity))}>
                                <SeverityIcon severity={item.severity} />
                              </span>
                              <div className="min-w-0">
                                <div className="font-semibold text-foreground">{item.title}</div>
                                <div className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{item.details}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3">{NOTIFICATION_CATEGORY_LABELS[item.category]}</td>
                          <td className="px-3 py-3">{item.manager}</td>
                          <td className="px-3 py-3">
                            <div className="font-medium">{item.source}</div>
                            {item.freshness && (
                              <div className="mt-1 text-xs text-muted-foreground">{item.freshness.label}</div>
                            )}
                          </td>
                          <td className="whitespace-nowrap px-3 py-3">{formatDateTime(item.createdAt)}</td>
                          <td className="px-3 py-3 text-right">
                            <span className={cn('inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold', item.readAt ? 'bg-muted text-muted-foreground' : 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/25 dark:text-red-300')}>
                              {item.readAt ? 'прочитано' : 'новое'}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="divide-y md:hidden">
                {filteredItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="w-full p-3 text-left hover:bg-muted/40"
                    onClick={() => selectItem(item)}
                  >
                    <div className="flex items-start gap-2">
                      <span className={cn('inline-flex size-6 shrink-0 items-center justify-center rounded-md border', severityClass(item.severity))}>
                        <SeverityIcon severity={item.severity} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="font-semibold">{item.title}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{NOTIFICATION_CATEGORY_LABELS[item.category]} · {item.manager} · {formatDateTime(item.createdAt)}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <aside className="min-w-0 rounded-lg border bg-card">
          {selected ? (
            <div className="flex h-full min-h-[420px] flex-col">
              <div className="border-b p-4">
                <div className={cn('mb-3 inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-semibold', severityClass(selected.severity))}>
                  <SeverityIcon severity={selected.severity} />
                  {NOTIFICATION_SEVERITY_LABELS[selected.severity]}
                </div>
                <h2 className="text-base font-bold leading-6">{selected.title}</h2>
                <p className="mt-2 text-sm leading-5 text-muted-foreground">{selected.details}</p>
              </div>
              <div className="flex-1 space-y-4 overflow-auto p-4">
                <DetailBlock title="Контекст">
                  <div className="grid gap-2 text-sm">
                    <div className="flex justify-between gap-3"><span className="text-muted-foreground">Категория</span><span className="font-medium">{NOTIFICATION_CATEGORY_LABELS[selected.category]}</span></div>
                    <div className="flex justify-between gap-3"><span className="text-muted-foreground">Менеджер</span><span className="font-medium">{selected.manager}</span></div>
                    <div className="flex justify-between gap-3"><span className="text-muted-foreground">Сущность</span><span className="font-mono text-xs font-semibold">{selected.entityId}</span></div>
                    <div className="flex justify-between gap-3"><span className="text-muted-foreground">Создано</span><span className="font-medium">{formatDateTime(selected.createdAt)}</span></div>
                  </div>
                </DetailBlock>

                <DetailBlock title="Источник и свежесть">
                  <div className="text-sm font-medium">{selected.source}</div>
                  {selected.freshness ? (
                    <div className={cn('mt-2 rounded-md border px-3 py-2 text-xs', freshnessClass(selected.freshness.state))}>
                      {selected.freshness.label}: {freshnessLabel(selected.freshness.state)} · {formatDateTime(selected.freshness.updatedAt)}
                    </div>
                  ) : (
                    <div className="mt-1 text-sm text-muted-foreground">Данных о свежести пока нет.</div>
                  )}
                </DetailBlock>

                {selected.reportFile && (
                  <DetailBlock title="Файл отчёта">
                    <div className="space-y-3">
                      <div>
                        <div className="font-semibold">{selected.reportFile.report}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{selected.reportFile.fileName}</div>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full border bg-background px-2 py-1">{selected.reportFile.format}</span>
                        <span className="rounded-full border bg-background px-2 py-1">{selected.reportFile.period}</span>
                        <span className="rounded-full border bg-background px-2 py-1">{selected.reportFile.rows.toLocaleString('ru-RU')} строк</span>
                        <span className="rounded-full border bg-background px-2 py-1">{selected.reportFile.size}</span>
                        <span className="rounded-full border bg-background px-2 py-1">{selected.reportFile.generatedAt}</span>
                      </div>
                      <Button size="sm" className="h-8 gap-2" onClick={() => downloadReport(selected)}>
                        <Download className="size-3.5" />
                        Скачать ещё раз
                      </Button>
                    </div>
                  </DetailBlock>
                )}

                <DetailBlock title="Что заблокировано">
                  {selected.blockedActions.length > 0 ? (
                    <ul className="space-y-1 text-sm">
                      {selected.blockedActions.map((action) => <li key={action}>• {action}</li>)}
                    </ul>
                  ) : (
                    <div className="text-sm text-muted-foreground">Нет заблокированных действий.</div>
                  )}
                </DetailBlock>
              </div>
              <div className="flex flex-wrap gap-2 border-t p-4">
                <Button size="sm" className="h-8 gap-2" onClick={() => markRead(selected.id)} disabled={Boolean(selected.readAt)}>
                  <CheckCheck className="size-3.5" />
                  Пометить прочитанным
                </Button>
                {selected.route && (
                  <Button size="sm" variant="outline" className="h-8 gap-2" onClick={() => openRoute(selected)}>
                    <ExternalLink className="size-3.5" />
                    Открыть модуль
                  </Button>
                )}
                {selected.reportFile && (
                  <Button size="sm" variant="outline" className="h-8 gap-2" onClick={() => downloadReport(selected)}>
                    <Download className="size-3.5" />
                    Скачать отчёт
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex min-h-[420px] items-center justify-center p-6 text-center text-sm text-muted-foreground">
              Выберите уведомление, чтобы увидеть детали.
            </div>
          )}
        </aside>
      </section>
    </div>
  )
}

function DetailBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <div className="rounded-lg border bg-background/60 p-3">{children}</div>
    </section>
  )
}
