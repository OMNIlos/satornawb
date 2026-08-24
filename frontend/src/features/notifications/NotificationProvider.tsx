import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '@/features/auth/authContext'
import { fetchNotifications, markAllBackendNotificationsRead, markBackendNotificationRead } from './api.js'
import { NotificationContext, type NotificationContextValue } from './notificationContext.js'
import type { NotificationEvent } from './types.js'

export function NotificationProvider({ children }: { children: ReactNode }) {
  const { accessToken, isAuthenticated } = useAuth()
  const [items, setItems] = useState<NotificationEvent[]>([])
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    if (!accessToken || !isAuthenticated) {
      setItems([])
      setLoadError(false)
      return
    }
    let cancelled = false
    fetchNotifications(accessToken)
      .then((nextItems) => {
        if (!cancelled) {
          setItems(nextItems)
          setLoadError(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setItems([])
          setLoadError(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, isAuthenticated])

  const value = useMemo<NotificationContextValue>(
    () => ({
      items,
      loadError,
      markRead: (id: string) => {
        if (!accessToken) return
        void markBackendNotificationRead(accessToken, id)
          .then(setItems)
          .catch(() => setLoadError(true))
      },
      markAllRead: () => {
        if (!accessToken) return
        void markAllBackendNotificationsRead(accessToken)
          .then(setItems)
          .catch(() => setLoadError(true))
      },
    }),
    [accessToken, items, loadError],
  )

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}
