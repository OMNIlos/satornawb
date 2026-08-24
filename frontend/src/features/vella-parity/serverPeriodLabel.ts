function formatDayMonth(iso: string) {
  const [year, month, day] = iso.split('-').map(Number)
  if (!year || !month || !day) return ''
  return `${String(day).padStart(2, '0')}.${String(month).padStart(2, '0')}`
}

/**
 * Label the window the backend actually answered for.
 *
 * A preset period is anchored on the last closed WB analytical day, so the
 * range behind the numbers can sit a day behind the one the picker assumed.
 * Labelling the picker's guess instead of the served window told the user the
 * KPIs covered days that are not in them.
 *
 * Returns null when the backend did not report a range, so the caller can keep
 * whatever label it already had.
 */
export function makeServerProductsPeriodLabel(
  dateFrom: string | undefined | null,
  dateTo: string | undefined | null,
  todayIso: string,
): string | null {
  if (!dateFrom || !dateTo) return null
  const fromLabel = formatDayMonth(dateFrom)
  const toLabel = dateTo === todayIso ? 'сегодня' : formatDayMonth(dateTo)
  if (!fromLabel || !toLabel) return null
  if (dateFrom === dateTo) return dateTo === todayIso ? 'сегодня' : fromLabel
  const days = Math.round((Date.parse(`${dateTo}T00:00:00Z`) - Date.parse(`${dateFrom}T00:00:00Z`)) / 86_400_000) + 1
  if (!Number.isFinite(days) || days < 1) return null
  return `с ${fromLabel} по ${toLabel} · ${days} дн`
}
