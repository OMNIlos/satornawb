import { createContext, useContext } from 'react'
import type { CurrentUserProfile, SessionInfo } from '@/features/settings/types'
import type { CabinetMeView } from './authApi'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'
export type SessionsStatus = 'idle' | 'loading' | 'ready' | 'error'

export type AuthContextValue = {
  status: AuthStatus
  isAuthenticated: boolean
  accessToken: string | null
  profile: CurrentUserProfile | null
  cabinetMe: CabinetMeView | null
  sessions: SessionInfo[]
  sessionsStatus: SessionsStatus
  login: (payload: { email: string; password: string }) => Promise<void>
  register: (payload: {
    email: string
    password: string
    fullName: string
    companyName: string
    wbToken?: string
  }) => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<void>
  refreshSessions: () => Promise<void>
  revokeSession: (sessionId: string) => Promise<void>
  revokeOtherSessions: () => Promise<number>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
