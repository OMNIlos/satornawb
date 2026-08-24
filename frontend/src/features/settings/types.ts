export type AccessRole = 'owner' | 'admin' | 'ecom' | 'manager' | 'finance' | 'ads' | 'production' | 'reviews' | 'viewer'

export type Marketplace = 'wb' | 'avito'

export type AccessStatus = 'full' | 'limited' | 'view_only' | 'blocked'

export type DangerousPermission =
  | 'finance_view'
  | 'price_send'
  | 'xml_publish'
  | 'message_send'
  | 'review_send'
  | 'wallet_topup'
  | 'role_admin'
  | 'token_admin'

export type SettingsMutationResult =
  | { status: 'success'; message: string; auditEventId: string }
  | { status: 'approval_required'; message: string; approvalId: string; auditEventId: string }
  | { status: 'blocked'; message: string; blockedReason: string; auditEventId: string }

export type MarketplaceScope = {
  marketplace: Marketplace
  status: AccessStatus
  modules: string[]
  accountIds: string[]
  dangerousPermissions: DangerousPermission[]
  blockers: string[]
}

export type CurrentUserProfile = {
  id: string
  name: string
  shortName: string
  initials: string
  email: string
  telegram: string
  role: AccessRole
  roleLabel: string
  workspace: string
  position: string
  scopes: MarketplaceScope[]
  unreadApprovals: number
}

export type UserAccessProfile = {
  id: string
  name: string
  initials: string
  email: string
  role: AccessRole
  roleLabel: string
  status: 'active' | 'invited' | 'blocked'
  scopes: MarketplaceScope[]
  lastActiveAt: string
}

export type AccountCapability = {
  id: string
  marketplace: Marketplace
  accountName: string
  owner: string
  status: 'ready' | 'partial' | 'blocked' | 'missing_access'
  tariff: string
  health: string
  capabilities: Array<{
    key: string
    label: string
    status: 'ready' | 'blocked' | 'unknown'
    reason: string
  }>
  nextAction: string
  updatedAt: string
}

export type NotificationRoute = {
  id: string
  event: string
  marketplace: Marketplace | 'system'
  priority: 'critical' | 'warning' | 'info'
  recipients: string[]
  channels: Array<'telegram' | 'email' | 'center'>
  workingHours: string
  status: 'active' | 'needs_setup' | 'paused'
}

export type SessionInfo = {
  id: string
  device: string
  location: string
  ip: string
  lastActiveAt: string
  current: boolean
  status: 'active' | 'revoked'
}

export type SettingsAuditEvent = {
  id: string
  createdAt: string
  actor: string
  action: string
  marketplace: Marketplace | 'system'
  target: string
  result: 'success' | 'blocked' | 'approval_required'
  summary: string
}
