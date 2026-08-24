export type NotificationSeverity = 'critical' | 'warning' | 'info'
export type NotificationCategory = 'reports' | 'prices' | 'orders' | 'avito' | 'ai' | 'system'
export type NotificationReadFilter = 'all' | 'unread' | 'read'
export type NotificationPeriod = '1d' | '7d' | '14d' | '30d'

export interface NotificationFreshness {
  label: string
  state: 'fresh' | 'partial' | 'stale' | 'pending'
  updatedAt: string
}

export interface NotificationEvent {
  id: string
  title: string
  details: string
  severity: NotificationSeverity
  category: NotificationCategory
  source: string
  manager: string
  createdAt: string
  readAt: string | null
  entityType: 'sku' | 'report' | 'order' | 'account' | 'review' | 'system'
  entityId: string
  route?: string
  blockedActions: string[]
  freshness?: NotificationFreshness
  reportFile?: {
    id: string
    report: string
    period: string
    rows: number
    size: string
    format: 'XLS' | 'XLSX' | 'CSV' | 'PDF'
    fileName: string
    generatedAt: string
  }
}

export interface NotificationFilters {
  period: NotificationPeriod
  category: NotificationCategory | 'all'
  severity: NotificationSeverity | 'all'
  manager: string
  read: NotificationReadFilter
  query: string
}

export interface NotificationsResponse {
  items: NotificationEvent[]
}
