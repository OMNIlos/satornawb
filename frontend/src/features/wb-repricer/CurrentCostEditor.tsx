import { useRef, useState } from 'react'
import { useAuth } from '@/features/auth/authContext'
import { authorizationHeaders } from '@/features/auth/authApi'
import { ApiError, apiData } from '@/lib/api'

type Cost = { amountKopecks: number | null; costVersionId: number | null; effectiveFrom: string | null }
type Context = { catalogSkuId: number; linkedProductCount: number; canWrite: boolean; currentCost: Cost }

export function parseCostRubles(raw: string): number {
  const value = raw.trim()
  if (!/^(?:\d+|\d{1,3}(?:[ \u00a0\u202f]\d{3})+)(?:[,.]\d{1,2})?$/.test(value)) throw new Error('Введите неотрицательную сумму, не больше двух знаков после запятой')
  const [whole, fraction = ''] = value.replace(/[ \u00a0\u202f]/g, '').split(/[,.]/)
  const amount = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'))
  if (amount > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error('Слишком большая сумма')
  return Number(amount)
}

export function CurrentCostEditor({ nmId, onSaved }: { nmId: number; onSaved: () => Promise<void> }) {
  const { accessToken } = useAuth()
  const [context, setContext] = useState<Context | null>(null)
  const [text, setText] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [sharedConfirmed, setSharedConfirmed] = useState(false)
  const command = useRef<{ amount: number; version: number | null; key: string } | null>(null)
  const format = (value: number | null) => value == null ? '' : `${Math.trunc(value / 100)},${String(value % 100).padStart(2, '0')}`
  const load = async (preserveInput = false) => {
    if (!accessToken || !nmId) return
    setBusy(true)
    try {
      const value = await apiData<Context>(`/api/v2/wb/products/${nmId}/current-cost`, { headers: authorizationHeaders(accessToken) })
      setContext(value)
      if (!preserveInput) setText(format(value.currentCost.amountKopecks))
      setMessage(preserveInput ? `Конфликт. Сейчас сохранено: ${format(value.currentCost.amountKopecks) || 'не указано'}. Ваш ввод сохранён; проверьте перед повтором.` : '')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Не удалось загрузить себестоимость') }
    finally { setBusy(false) }
  }
  const save = async () => {
    if (!context || !accessToken || busy || !context.canWrite) return
    try {
      const amount = parseCostRubles(text)
      if (context.linkedProductCount > 1 && !sharedConfirmed) throw new Error('Подтвердите изменение общей себестоимости связанных карточек')
      const version = context.currentCost.costVersionId
      if (!command.current || command.current.amount !== amount || command.current.version !== version) command.current = { amount, version, key: Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, '0')).join('') }
      setBusy(true)
      const saved = await apiData<Cost>(`/api/v2/catalog/skus/${context.catalogSkuId}/current-cost`, {
        method: 'POST', headers: authorizationHeaders(accessToken), body: JSON.stringify({ amountKopecks: amount, expectedCostVersionId: version, sourceReference: command.current.key }),
      })
      setContext({ ...context, currentCost: saved }); setText(format(saved.amountKopecks)); command.current = null
      setMessage(`Сохранено с ${saved.effectiveFrom ? new Date(saved.effectiveFrom).toLocaleString('ru-RU') : 'текущего момента'}. История не переписана. Обновляем расчёт…`)
      try { await onSaved(); setMessage(`Сохранено с ${new Date(saved.effectiveFrom!).toLocaleString('ru-RU')}. Прошлые периоды не изменены.`) }
      catch { setMessage('Стоимость сохранена. Расчёт не обновился — обновите список.') }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) { command.current = null; await load(true) }
      else setMessage(error instanceof Error ? error.message : 'Не удалось сохранить')
    } finally { setBusy(false) }
  }
  return <div style={{ minWidth: 150, maxWidth: 220 }} onClick={event => event.stopPropagation()}>
      <input aria-label={`Себестоимость ${nmId}, рублей за штуку`} inputMode="decimal" value={text}
        readOnly={!context || busy || !context.canWrite} aria-busy={busy}
        placeholder={busy ? '…' : '—'} title="Себестоимость одной единицы, ₽. Enter — сохранить, Escape — отменить."
        style={{ width: 105, minHeight: 34, padding: '6px 10px', border: '1px solid #2563eb', borderRadius: 6, background: '#eff6ff', color: '#1d4ed8', fontWeight: 600, outlineOffset: 2 }}
        onFocus={() => { if (!context && !busy) void load() }}
        onClick={() => { if (!context && !busy && message) void load() }}
        onChange={event => { setText(event.target.value); setMessage('Не сохранено') }}
        onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); if (!context && !busy) void load(); else void save() } if (event.key === 'Escape') { setText(format(context?.currentCost.amountKopecks ?? null)); setMessage('') } }} />
    {context && <>
      <button type="button" aria-label={`Сохранить себестоимость ${nmId}`} disabled={busy || !context.canWrite} onClick={() => void save()}>{busy ? '…' : '✓'}</button>
      {context.linkedProductCount > 1 && <label style={{ display: 'block' }}><input type="checkbox" checked={sharedConfirmed} onChange={event => setSharedConfirmed(event.target.checked)} />Общая для {context.linkedProductCount} карточек</label>}
    </>}
    <small role="status" style={{ display: 'block', whiteSpace: 'normal' }}>{message}</small>
  </div>
}
