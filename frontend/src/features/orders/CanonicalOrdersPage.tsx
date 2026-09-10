import { useEffect, useState } from 'react'
import { z } from 'zod'
import { useAuth } from '@/features/auth/authContext'
import { readWbData } from '@/features/wb-live/api'
import { CanonicalOrdersSavedView } from './CanonicalOrdersSavedView'

const accountsSchema = z.array(z.object({ marketplaceAccountId: z.number().int().positive().max(2147483647),
  provider: z.enum(['wb', 'avito']), externalAccountId: z.string().min(1).max(1024), displayName: z.string().max(1024).nullable(), status: z.string().min(1).max(64),
}).strict()).max(1000)
export function parseCanonicalOrderAccounts(value: unknown) {
  const accounts = accountsSchema.parse(value)
  if (new Set(accounts.map(account => account.marketplaceAccountId)).size !== accounts.length) throw new Error('DUPLICATE_ACCOUNT')
  return accounts
}

export function CanonicalOrdersPage() {
  const { accessToken, cabinetMe } = useAuth()
  const session = `${cabinetMe?.activeSession?.sessionId}:${cabinetMe?.organization.organizationId}:${cabinetMe?.user.userId}`
  const [loaded, setLoaded] = useState<{ session: string; token: string; accounts: ReturnType<typeof parseCanonicalOrderAccounts> } | null>(null)
  const [chosen, setChosen] = useState<{ session: string; ids: number[] }>({ session: '', ids: [] })
  const [applied, setApplied] = useState<{ session: string; ids: number[] }>({ session: '', ids: [] })
  const [error, setError] = useState<string | null>(null), [loading, setLoading] = useState(true), [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setLoaded(null); setChosen({ session, ids: [] }); setApplied({ session, ids: [] }); setError(null)
    if (!accessToken || !cabinetMe) { setLoading(false); return }
    setLoading(true)
    void readWbData(accessToken, '/api/v2/cabinet/marketplace-accounts', controller.signal, parseCanonicalOrderAccounts)
      .then(accounts => { if (!controller.signal.aborted) setLoaded({ session, token: accessToken, accounts }) })
      .catch(() => { if (!controller.signal.aborted) setError('Аккаунты недоступны. Нужны активная сессия, cabinet:read и включённое каноническое обнаружение аккаунтов.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [session, accessToken, revision])
  const accounts = loaded?.session === session && loaded.token === accessToken ? loaded.accounts : []
  const selectedIds = chosen.session === session ? chosen.ids : []
  const accountIds = applied.session === session ? applied.ids.filter(id => accounts.some(account => account.marketplaceAccountId === id)) : []
  return <main className="min-h-screen bg-background text-foreground"><div className="mx-auto flex w-full max-w-7xl flex-col gap-5 p-6">
    <section className="rounded-lg border bg-card p-5 shadow-sm"><h2>Аккаунты WB и Avito</h2><p>Выберите точный состав аккаунтов сохранённого представления. Наличие аккаунта в списке не разрешает печать, отправку или другие действия.</p>
      {loading ? <p role="status">Читаем доступные аккаунты…</p> : null}{error ? <p role="alert">{error}</p> : null}
      {!loading && !error && accounts.length === 0 ? <p>Доступных аккаунтов пока нет.</p> : null}
      <fieldset disabled={loading}>{accounts.map(account => <label key={account.marketplaceAccountId} className="block"><input type="checkbox" checked={selectedIds.includes(account.marketplaceAccountId)} onChange={event => setChosen({ session,
        ids: event.target.checked ? [...selectedIds, account.marketplaceAccountId].sort((a, b) => a - b) : selectedIds.filter(id => id !== account.marketplaceAccountId) })} /> {account.provider.toUpperCase()} · {account.displayName || account.externalAccountId} · {account.status}</label>)}</fieldset>
      <div className="profile-token-actions"><button type="button" className="btn btn-default" disabled={loading || selectedIds.length === 0} onClick={() => setApplied({ session, ids: [...selectedIds] })}>Открыть сохранённое представление</button><button type="button" className="btn btn-default" disabled={loading} onClick={() => setRevision(value => value + 1)}>Перечитать аккаунты</button></div>
    </section>
    {accessToken && cabinetMe && accountIds.length > 0 ? <CanonicalOrdersSavedView key={`${session}:${accessToken}:${accountIds.join(',')}`} token={accessToken} scope={{ organizationId: cabinetMe.organization.organizationId, accountIds }} /> : <p>Выберите аккаунты и откройте сохранённое представление.</p>}
  </div></main>
}
