import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/features/auth/authContext'
import { apiData, ApiError } from '@/lib/api'
import { authorizationHeaders } from '@/features/auth/authApi'
import { credentialPath, readWbData, revokeWbCredential, saveWbCredential, shouldPollWbSync, startWbSync, syncPath, wbErrorMessage, type WbAccount, type WbCredential, type WbSync } from './api'

const selections = new Map<string, number>()
const selectionEvent = 'satorna:wb-account-selected'

export function useWbAccount() {
  const { accessToken, cabinetMe } = useAuth()
  const scope = cabinetMe ? `${cabinetMe.activeSession?.sessionId ?? cabinetMe.user.userId}:${cabinetMe.organization.organizationId}` : ''
  const [accounts, setAccounts] = useState<WbAccount[]>([])
  const [accountId, setAccountId] = useState<number | null>(null)
  const [loadedScope, setLoadedScope] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(null)
    if (!accessToken || !scope || !cabinetMe) { setLoading(false); return }
    setLoading(true)
    void readWbData<WbAccount[]>(accessToken, '/api/v1/cabinet/marketplace-accounts?provider=wb', controller.signal)
      .then((items) => {
        if (controller.signal.aborted) return
        const eligible = items.filter((account) => account.provider === 'wb')
        const remembered = selections.get(scope)
        const selected = eligible.find((account) => account.marketplaceAccountId === remembered)?.marketplaceAccountId
          ?? (eligible.length === 1 ? eligible[0].marketplaceAccountId : null)
        setAccounts(eligible); setAccountId(selected); setLoadedScope(scope)
      })
      .catch((failure) => { if (!controller.signal.aborted) setError(wbErrorMessage(failure)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [accessToken, scope, cabinetMe?.organization.organizationId, revision])
  useEffect(() => {
    const update = () => setAccountId(selections.get(scope) ?? null)
    window.addEventListener(selectionEvent, update)
    return () => window.removeEventListener(selectionEvent, update)
  }, [scope])
  return {
    accessToken, scope, accounts: loadedScope === scope ? accounts : [],
    accountId: loadedScope === scope ? accountId : null, loading, error,
    reload: () => setRevision((value) => value + 1),
    select: (id: number | null) => {
      if (id !== null && accounts.some((account) => account.marketplaceAccountId === id)) selections.set(scope, id)
      else selections.delete(scope)
      window.dispatchEvent(new Event(selectionEvent))
    },
  }
}

export function WbAccountSelect({ account, disabled = false }: { account: ReturnType<typeof useWbAccount>; disabled?: boolean }) {
  return <div className="profile-field">
    <label htmlFor="wb-live-account">Аккаунт Wildberries</label>
    <select id="wb-live-account" className="profile-input" disabled={disabled || account.loading} value={account.accountId ?? ''} onChange={(event) => account.select(event.target.value ? Number(event.target.value) : null)}>
      <option value="">{account.loading ? 'Загрузка аккаунтов…' : 'Выберите аккаунт'}</option>
      {account.accounts.map((item) => <option key={item.marketplaceAccountId} value={item.marketplaceAccountId}>{item.displayName || `WB · ${item.externalAccountId}`}</option>)}
    </select>
    {account.error ? <div role="alert" className="profile-token-feedback is-error">{account.error} <button type="button" className="btn btn-ghost btn-sm" onClick={account.reload}>Повторить чтение</button></div> : null}
    {!account.loading && !account.error && account.accounts.length === 0 ? <p>Аккаунт WB ещё не создан. Добавьте его в настройках подключения.</p> : null}
  </div>
}

export function useWbSync(accessToken: string | null, accountId: number | null, scope: string) {
  const [snapshot, setSnapshot] = useState<{ key: string; data: WbSync } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const key = `${scope}:${accountId}`
  useEffect(() => {
    setSnapshot(null); setError(null)
    if (!accessToken || !accountId) return
    let disposed = false
    let timeout: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined
    let failures = 0
    const poll = async () => {
      if (disposed || document.hidden) return
      const requestController = new AbortController()
      controller = requestController
      try {
        const data = await readWbData<WbSync>(accessToken, syncPath(accountId), requestController.signal)
        if (disposed || requestController.signal.aborted) return
        failures = 0; setSnapshot({ key, data }); setError(null)
        if (shouldPollWbSync(data)) timeout = setTimeout(poll, 15_000)
      } catch (failure) {
        if (disposed || requestController.signal.aborted) return
        setError(wbErrorMessage(failure))
        // Stop after three failed reads; the user can retry explicitly.
        if (++failures < 3) timeout = setTimeout(poll, 30_000)
      }
    }
    const visibility = () => {
      clearTimeout(timeout); controller?.abort()
      if (!document.hidden) void poll()
    }
    document.addEventListener('visibilitychange', visibility)
    void poll()
    return () => { disposed = true; clearTimeout(timeout); controller?.abort(); document.removeEventListener('visibilitychange', visibility) }
  }, [accessToken, accountId, key, revision])
  return { data: snapshot?.key === key ? snapshot.data : null, error, refresh: () => setRevision((value) => value + 1) }
}

const syncLabels: Record<string, string> = { idle: 'Загрузка ещё не запускалась', queued: 'Загрузка в очереди', running: 'Загрузка выполняется', partial: 'Доступна часть данных', completed: 'Загрузка завершена', failed: 'Ошибка загрузки' }
export function WbSyncStatus({ sync }: { sync: ReturnType<typeof useWbSync> }) {
  return <div className="profile-token-feedback" aria-live="polite">
    {sync.error ? <div role="alert">{sync.error}</div> : null}
    {sync.data ? <><b>{syncLabels[sync.data.state] ?? sync.data.state}</b>
      {sync.data.sources.map((source) => <div key={source.source}>{source.source}: {syncLabels[source.state] ?? source.state} · сохранено {source.processed.toLocaleString('ru-RU')}{source.updatedAt ? ` · ${new Date(source.updatedAt).toLocaleString('ru-RU')}` : ''}{source.errorCode ? ' · источник сообщил об ошибке' : ''}</div>)}
      {sync.data.state === 'partial' || sync.data.state === 'queued' || sync.data.state === 'running' ? <div>Товары отображаются по мере загрузки. Цены и история могут появиться позже с учётом ограничений WB.</div> : null}
    </> : !sync.error ? 'Читаем состояние загрузки…' : null}
    <button className="btn btn-ghost btn-sm" type="button" onClick={sync.refresh}>Обновить состояние</button>
  </div>
}

export function WbConnection() {
  const account = useWbAccount()
  const { accessToken, accountId, scope } = account
  const sync = useWbSync(accessToken, accountId, scope)
  const [credential, setCredential] = useState<WbCredential | null>(null)
  const [draft, setDraft] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const [unknown, setUnknown] = useState(false)
  const [adding, setAdding] = useState(false)
  const syncIntent = useRef<{ owner: string; id: string } | null>(null)
  const credentialOwner = useRef('')
  const current = useRef('')
  current.current = `${scope}:${accountId}`
  const key = current.current
  useEffect(() => {
    const controller = new AbortController()
    setCredential(null); setDraft(''); setError(null)
    if (!accessToken || !accountId) return
    void readWbData<WbCredential>(accessToken, credentialPath(accountId), controller.signal)
      .then((data) => { if (!controller.signal.aborted) { credentialOwner.current = key; setCredential(data); setUnknown(false) } })
      .catch((failure) => { if (!controller.signal.aborted) setError(wbErrorMessage(failure)) })
    return () => controller.abort()
  }, [accessToken, accountId, key, revision])
  useEffect(() => { setBusy(false); setUnknown(false); syncIntent.current = null }, [key])
  const activeCredential = credentialOwner.current === key ? credential : null
  useEffect(() => {
    if (!account.loading && !account.error && !accountId) setUnknown(false)
  }, [account.loading, account.error, accountId])
  async function write(action: 'save' | 'revoke' | 'sync') {
    if (!accessToken || !accountId || busy || unknown) return
    const owner = key
    setBusy(true); setError(null)
    try {
      if (action === 'sync') {
        if (syncIntent.current?.owner !== owner) syncIntent.current = { owner, id: crypto.randomUUID() }
        await startWbSync(accessToken, accountId, syncIntent.current.id)
        if (current.current === owner) syncIntent.current = null
      }
      else {
        const data = action === 'save' ? await saveWbCredential(accessToken, accountId, draft.trim()) : await revokeWbCredential(accessToken, accountId)
        if (current.current === owner) { credentialOwner.current = owner; setCredential(data); setDraft('') }
      }
      if (current.current === owner) sync.refresh()
    } catch (failure) {
      if (current.current === owner) { setError(wbErrorMessage(failure, true)); setUnknown(!(failure instanceof ApiError && failure.status < 500)); setDraft('') }
    } finally { if (current.current === owner) setBusy(false) }
  }
  async function createAccount() {
    if (!accessToken || !draft.trim() || busy || unknown) return
    const owner = key
    setBusy(true); setError(null)
    try {
      const result = await apiData<{ account: WbAccount; credential: WbCredential }>('/api/v1/cabinet/marketplace-accounts/connect/wb', { method: 'POST', headers: authorizationHeaders(accessToken), body: JSON.stringify({ wbToken: draft.trim(), ...(name.trim() ? { displayName: name.trim() } : {}) }) })
      if (current.current !== owner) return
      selections.set(scope, result.account.marketplaceAccountId)
      setName(''); setDraft(''); setAdding(false); account.reload()
    } catch (failure) { if (current.current === owner) { setError(wbErrorMessage(failure, true)); setUnknown(!(failure instanceof ApiError && failure.status < 500)); setDraft('') } }
    finally { if (current.current === owner) setBusy(false) }
  }
  return <div className="profile-token-card" data-wb-live="connection">
    <div className="profile-token-head"><div><div className="profile-card-title">WB token</div><div className="profile-helper-text">Подключение аккаунта Wildberries и загрузка данных.</div></div><span className="access-badge">{activeCredential?.status === 'active' ? 'ключ сохранён' : 'нет активного ключа'}</span></div>
    <WbAccountSelect account={account} disabled={busy} />
    {account.accounts.length > 0 ? <button className="btn btn-ghost btn-sm" type="button" disabled={busy} onClick={() => { setAdding((value) => !value); setDraft('') }}>{adding ? 'Отменить добавление' : 'Добавить аккаунт WB'}</button> : null}
    {!account.loading && !account.error && (account.accounts.length === 0 || adding) ? <div className="profile-token-actions"><input aria-label="Название аккаунта WB" className="profile-input" value={name} onChange={(event) => setName(event.target.value)} placeholder="Название аккаунта (необязательно)" /><input aria-label="WB Base token" className="profile-input" type="password" autoComplete="new-password" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ключ Wildberries" disabled={busy || unknown} /><button type="button" className="btn btn-primary btn-sm" disabled={!draft.trim() || busy || unknown} onClick={() => void createAccount()}>Проверить и сохранить подключение</button></div> : null}
    {accountId && !adding ? <><div className="profile-token-grid"><div className="profile-field"><label htmlFor="settingsProfileWbToken">WB Base token</label><input id="settingsProfileWbToken" className="profile-input" type="password" autoComplete="new-password" value={draft} onChange={(event) => setDraft(event.target.value)} disabled={busy || unknown} /></div><div className="profile-token-status"><b>{activeCredential?.status === 'active' ? 'Ключ сохранён' : activeCredential?.status === 'expired' ? 'Ключ истёк' : 'Добавьте ключ WB'}</b><p>Ключ хранится зашифрованным. Проверка доступа выполняется при загрузке; сохранение ключа не подтверждает доступ к каждому источнику.</p></div></div>
    <div className="profile-token-actions"><button className="btn btn-primary btn-sm" type="button" disabled={busy || unknown || !draft.trim()} onClick={() => void write('save')}>Сохранить ключ</button><button className="btn btn-default btn-sm" type="button" disabled={busy || unknown || activeCredential?.status !== 'active' || sync.data?.state === 'queued' || sync.data?.state === 'running'} onClick={() => void write('sync')}>Проверить доступ и загрузить</button><button className="btn btn-ghost btn-sm" type="button" disabled={busy || unknown || activeCredential?.status !== 'active'} onClick={() => void write('revoke')}>Удалить ключ</button></div><WbSyncStatus sync={sync} /></> : null}
    {busy ? <div role="status">Выполняем действие…</div> : null}
    {error ? <div className="profile-token-feedback is-error" role="alert">{error}</div> : null}
    {unknown || error ? <button className="btn btn-default btn-sm" type="button" onClick={() => { setRevision((value) => value + 1); account.reload(); sync.refresh() }}>Прочитать сохранённое состояние</button> : null}
  </div>
}
