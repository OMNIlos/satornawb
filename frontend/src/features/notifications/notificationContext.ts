import { createContext, useContext } from 'react'
import type { NotificationEvent } from './types.js'

export interface NotificationContextValue {
  items: NotificationEvent[]
  loadError: boolean
  markRead: (id: string) => void
  markAllRead: () => void
}

export const NotificationContext = createContext<NotificationContextValue | null>(null)

export function useNotifications() {
  const value = useContext(NotificationContext)
  if (!value) throw new Error('useNotifications must be used inside NotificationProvider')
  return value
}
