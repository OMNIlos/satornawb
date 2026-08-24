import { apiData } from '@/lib/api'
import {
  clearStoredAccessToken,
  readStoredAccessToken,
  storeAccessToken,
  AUTH_ACCESS_TOKEN_CLEARED_EVENT,
  AUTH_ACCESS_TOKEN_REFRESHED_EVENT,
} from '@/lib/authTokenStore'
import type { CurrentUserProfile, MarketplaceScope, SessionInfo } from '@/features/settings/types'

export type PermissionProfile =
  | 'viewer'
  | 'settings_editor'
  | 'price_sender'
  | 'finance_viewer'
  | 'admin'
  | 'custom'

export type TeamUserView = {
  userId: string
  organizationId: number
  email: string
  fullName: string
  permissionProfile: PermissionProfile
  permissions: string[]
  isActive: boolean
  createdAt: string
}

export type SessionView = {
  sessionId: string
  userId: string
  issuedAt: string
  expiresAt: string
  lastSeenAt: string
  revokedAt: string | null
  revokedReason: string | null
  userAgent: string | null
  ipAddress: string | null
}

export type UserPreferencesView = {
  userId: string
  notificationSettings: Record<string, unknown>
  exportSettings: Record<string, unknown>
  timezone: string
  updatedAt: string
}

export type OrganizationView = {
  organizationId: number
  slug: string
  name: string
  createdAt: string
}

export type CabinetMeView = {
  organization: OrganizationView
  user: TeamUserView
  activeSession: SessionView | null
  preferences: UserPreferencesView
}

type LoginResponse = {
  accessToken: string
  expiresIn: number
  tokenType: string
}

type RegisterResponse = LoginResponse & {
  organization: OrganizationView
  user: TeamUserView
}

const PROFILE_LABELS: Record<PermissionProfile, string> = {
  viewer: 'Только просмотр',
  settings_editor: 'Редактор настроек',
  price_sender: 'Отправка цен',
  finance_viewer: 'Финансы',
  admin: 'Администратор',
  custom: 'Индивидуальный профиль',
}

const PROFILE_ROLE: Record<PermissionProfile, CurrentUserProfile['role']> = {
  viewer: 'viewer',
  settings_editor: 'manager',
  price_sender: 'manager',
  finance_viewer: 'finance',
  admin: 'admin',
  custom: 'manager',
}

function hasPermission(permissions: string[], permission: string) {
  return permissions.includes(permission)
}

function deriveMarketplaceScopes(permissions: string[]): MarketplaceScope[] {
  const wbModules = ['Репрайсер', 'Отчеты']
  if (hasPermission(permissions, 'finance:read')) wbModules.push('P&L')
  if (hasPermission(permissions, 'reviews:read')) wbModules.push('Отзывы')
  if (hasPermission(permissions, 'settings:read')) wbModules.push('Настройки')

  const wbDangerousPermissions: MarketplaceScope['dangerousPermissions'] = []
  if (hasPermission(permissions, 'finance:read')) wbDangerousPermissions.push('finance_view')
  if (hasPermission(permissions, 'price:send')) wbDangerousPermissions.push('price_send')
  if (hasPermission(permissions, 'reviews:send') || hasPermission(permissions, 'reviews:write')) {
    wbDangerousPermissions.push('review_send')
  }

  return [
    {
      marketplace: 'wb',
      status: hasPermission(permissions, 'settings:write') || hasPermission(permissions, 'price:send') ? 'full' : 'limited',
      modules: wbModules,
      accountIds: ['wb-primary'],
      dangerousPermissions: wbDangerousPermissions,
      blockers: [],
    },
    {
      marketplace: 'avito',
      status: hasPermission(permissions, 'integrations:write') ? 'limited' : 'view_only',
      modules: hasPermission(permissions, 'integrations:read') ? ['Интеграции', 'Уведомления'] : ['Интеграции'],
      accountIds: [],
      dangerousPermissions: [],
      blockers: ['Аккаунты Avito подключаются отдельным модулем'],
    },
  ]
}

function initialsFromName(fullName: string) {
  const parts = fullName.split(/\s+/).map((part) => part.trim()).filter(Boolean)
  if (parts.length === 0) return 'OG'
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('')
}

function shortNameFromFullName(fullName: string) {
  return fullName.split(/\s+/)[0] || fullName
}

function formatSessionDate(iso: string) {
  return new Intl.DateTimeFormat('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

export function mapCabinetMeToProfile(me: CabinetMeView): CurrentUserProfile {
  const permissions = me.user.permissions ?? []
  const roleLabel = PROFILE_LABELS[me.user.permissionProfile] ?? me.user.permissionProfile

  return {
    id: me.user.userId,
    name: me.user.fullName,
    shortName: shortNameFromFullName(me.user.fullName),
    initials: initialsFromName(me.user.fullName),
    email: me.user.email,
    telegram: '',
    role: PROFILE_ROLE[me.user.permissionProfile] ?? 'manager',
    roleLabel,
    workspace: me.organization.name,
    position: `Профиль доступа: ${roleLabel}`,
    scopes: deriveMarketplaceScopes(permissions),
    unreadApprovals: 0,
  }
}

export function mapSessionsToSessionInfo(sessions: SessionView[], currentSessionId: string | null): SessionInfo[] {
  return sessions.map((session) => ({
    id: session.sessionId,
    device: session.userAgent || 'Неизвестное устройство',
    location: session.ipAddress ? `IP ${session.ipAddress}` : 'Источник не определен',
    ip: session.ipAddress || '-',
    lastActiveAt: session.revokedAt ? `отозвана ${formatSessionDate(session.revokedAt)}` : formatSessionDate(session.lastSeenAt),
    current: session.sessionId === currentSessionId,
    status: session.revokedAt ? 'revoked' : 'active',
  }))
}

export {
  AUTH_ACCESS_TOKEN_CLEARED_EVENT,
  AUTH_ACCESS_TOKEN_REFRESHED_EVENT,
  clearStoredAccessToken,
  readStoredAccessToken,
  storeAccessToken,
}

export function authorizationHeaders(accessToken: string) {
  return { Authorization: `Bearer ${accessToken}` }
}

export async function loginWithPassword(payload: { email: string; password: string }) {
  return apiData<LoginResponse>('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) })
}

export async function registerWithPassword(payload: {
  email: string
  password: string
  fullName: string
  companyName: string
  wbToken?: string
}) {
  return apiData<RegisterResponse>('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) })
}

export async function refreshAccessToken() {
  return apiData<LoginResponse>('/api/v1/auth/refresh', { method: 'POST' })
}

export async function logoutCurrentSession(accessToken: string) {
  return apiData<{ status: string }>('/api/v1/auth/logout', { method: 'POST', headers: authorizationHeaders(accessToken) })
}

export async function fetchCabinetMe(accessToken: string) {
  return apiData<CabinetMeView>('/api/v1/cabinet/me', { headers: authorizationHeaders(accessToken) })
}

export async function fetchSessions(accessToken: string) {
  return apiData<SessionView[]>('/api/v1/cabinet/sessions', { headers: authorizationHeaders(accessToken) })
}

export async function revokeSession(accessToken: string, sessionId: string) {
  return apiData<SessionView>(`/api/v1/cabinet/sessions/${sessionId}/revoke`, {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
  })
}

export async function revokeOtherSessions(accessToken: string) {
  return apiData<{ revokedCount: number }>('/api/v1/cabinet/sessions/revoke-others', {
    method: 'POST',
    headers: authorizationHeaders(accessToken),
  })
}
