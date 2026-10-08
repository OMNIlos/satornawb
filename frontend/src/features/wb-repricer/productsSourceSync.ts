import { resetLiveRepricerParityCache, type LiveRepricerPeriodRequest } from './liveParityData'
import { shouldReadStatsProgress, syncStatsSources, type StatsSourceJob } from './statsSourceSync'

// This page owns an isolated financial job. It reads existing non-financial
// sources without rebuilding other reports or starting a full-account sync.
export async function syncProductsPeriod(token: string, period: LiveRepricerPeriodRequest,
  signal: AbortSignal, isCurrent: () => boolean, readSaved: () => Promise<void>, onStatus: (job: StatsSourceJob) => void = () => {}) {
  if (!period.dateFrom || !period.dateTo || !isCurrent() || signal.aborted) return
  let lastRead = Date.now()
  await syncStatsSources(token, period.dateFrom, period.dateTo, signal, async job => {
    if (!isCurrent() || signal.aborted) return
    onStatus(job)
    if (shouldReadStatsProgress(job, lastRead)) {
      resetLiveRepricerParityCache(token)
      await readSaved()
      lastRead = Date.now()
    }
  }, isCurrent, 'repricer-finance')
}
