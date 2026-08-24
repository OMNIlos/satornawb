/**
 * Anchors preset periods ("1 день", "7 дней", …) on the last closed WB day.
 *
 * WB closes its analytical windows at the end of the previous day, and the
 * backend sync writes its period caches anchored there.  Sending a range that
 * ends today asks for a day WB has no closed figures for, so the whole period
 * comes back empty - every KPI tile rendered zeros while the very same period
 * requested with explicit dates returned real numbers.
 *
 * Dates are computed in UTC because the backend builds its cache keys in UTC.
 */

function toIsoDay(date: Date) {
  return date.toISOString().slice(0, 10)
}

/** The most recent day WB has closed figures for. */
export function lastClosedWbDay(now: Date = new Date()) {
  const day = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
  day.setUTCDate(day.getUTCDate() - 1)
  return toIsoDay(day)
}

/** Resolves a preset length into an explicit, fully closed date range. */
export function resolvePresetPeriodRange(periodDays: number, now: Date = new Date()) {
  const dateTo = lastClosedWbDay(now)
  const start = new Date(`${dateTo}T00:00:00Z`)
  start.setUTCDate(start.getUTCDate() - (Math.max(1, Math.trunc(periodDays)) - 1))
  return { dateFrom: toIsoDay(start), dateTo }
}
