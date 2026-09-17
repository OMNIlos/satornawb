import { apiRequest, ApiError } from '@/lib/api'
import { authorizationHeaders } from '@/features/auth/authApi'
import { resetLiveRepricerParityCache, type LiveRepricerPeriodRequest, type LiveRepricerSyncStatus } from './liveParityData'

export function missingPeriodSources(cache?: Record<string, unknown>) {
  return (['period-stats', 'finance', 'baskets'] as const).filter(source => {
    const key = source === 'period-stats' ? 'periodStats' : source
    return !cache?.[`${key}FetchedAt`] || ['partial', 'no_data'].includes(String(cache?.[`${key}CoverageState`]))
  })
}

export async function preparePeriod(token: string, period: LiveRepricerPeriodRequest,
  sources: string[], isCurrent: () => boolean, signal?: AbortSignal) {
  const options = { headers: authorizationHeaders(token), signal, cache: 'no-store' as const }
  const deadline = Date.now() + 10 * 60_000
  let runId: string | null | undefined
  let started = false
  while (Date.now() < deadline) {
    signal?.throwIfAborted()
    if (!isCurrent()) return false
    if (!started) {
      try {
        const run = await apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/run', {
          ...options, method: 'POST', body: JSON.stringify({ ...period, sources, mode: 'manual', force: false }),
        })
        if (!run?.runId) throw new Error('Сервер не подтвердил запуск загрузки периода')
        runId = run.runId
        started = true
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 409) throw error
      }
    }
    await new Promise(resolve => setTimeout(resolve, 3000))
    if (!isCurrent()) return false
    const status = await apiRequest<LiveRepricerSyncStatus>('/api/v1/wb-repricer/sync/status', options)
    if (!status) throw new Error('Не удалось получить статус загрузки периода')
    if (started && runId && status.runId !== runId) throw new Error('Загрузка периода была заменена. Обновите выбранный период.')
    if (started && !status.running) {
      resetLiveRepricerParityCache(token)
      if (status.state !== 'completed') throw new Error('WB вернул неполные данные периода. Проверьте статус загрузки; неизвестные показатели не рассчитаны.')
      return true
    }
  }
  throw new Error('Загрузка WB ещё не завершена. Проверьте статус загрузки и обновите список позже.')
}
