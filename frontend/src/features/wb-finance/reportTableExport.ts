import { ApiError, buildApiUrl } from '@/lib/api'
import { canonicalPnlRowStatus, type CanonicalCompatibilityMeta, type CanonicalPeriod } from './canonicalAbcPnl'

export const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
export const PNL_TABLE_EXPORT_HEADERS = ['Товар', 'Категория', 'Выручка', 'Себестоимость', 'Комиссия', 'Логистика', 'Хранение', 'Реклама', 'Налог', 'До внутренних расходов', 'Финальная маржа', 'Статус', 'Комментарий']
type Cell = string | number | null
export type ReportTableExportPayload = {
  reportKind: 'abc' | 'pnl'
  marketplaceAccountId: number
  dateFrom: string
  dateTo: string
  headers: string[]
  rows: Cell[][]
  source: ReturnType<typeof reportTableSource>
}

export function reportTableSource(meta: CanonicalCompatibilityMeta | null | undefined, accountId: number, period: CanonicalPeriod, filterDescription: string) {
  if (!meta?.snapshot || !['ready', 'partial', 'empty'].includes(meta.state)
    || meta.period.temporalState === 'future' || meta.marketplaceAccountId !== accountId
    || meta.period.dateFrom !== period.fromIso || meta.period.dateTo !== period.toIso) {
    throw new Error('Экспорт недоступен: нужен загруженный canonical-отчёт выбранного аккаунта и периода.')
  }
  return {
    state: meta.state as 'ready' | 'partial' | 'empty',
    formulaVersion: meta.formulaVersion,
    financeFormulaVersion: meta.snapshot.formulaVersion,
    financeSnapshotChecksum: meta.snapshot.snapshotChecksum,
    financeObservedAt: meta.snapshot.lastObservedAt,
    advertisingSnapshotChecksum: meta.advertisingSnapshotChecksum,
    costLedgerRevision: meta.costLedgerRevision,
    economicsRevision: meta.economicsRevision,
    blockerIds: meta.blockerIds,
    filterDescription,
  }
}

type PnlRow = {
  articleId?: string | null; sku?: string | null; productName?: string | null; label?: string | null
  category?: string | null; nmId?: number | string | null; comment?: string | null
  revenueKopecks?: number | null; cogsKopecks?: number | null; commissionKopecks?: number | null
  logisticsKopecks?: number | null; storageKopecks?: number | null; adSpendKopecks?: number | null
  taxKopecks?: number | null; profitBeforeInternalExpensesKopecks?: number | null; marginPct?: number | null
  sourceStatus?: string | null; confidence?: string | null; blockerIds?: string[] | null
}

export function filterPnlTableRows<T extends PnlRow>(rows: T[], query: string, manager: string): T[] {
  const needle = query.trim().toLocaleLowerCase('ru-RU')
  // The P&L DTO has no manager assignment; its rows are unassigned.
  return rows.filter(row => (manager === 'all' || manager === 'unassigned')
    && (!needle || [row.articleId, row.sku, row.productName, row.label, row.category, row.nmId, row.comment]
      .join(' ').toLocaleLowerCase('ru-RU').includes(needle)))
}

const rubles = (value: number | null | undefined) => value == null ? null : value / 100

export function buildPnlTableRows(rows: PnlRow[]): Cell[][] {
  return rows.map(row => {
    const article = row.articleId ?? row.sku
    return [
      [row.productName || row.label || row.category || 'Товар без названия', article ? `Артикул: ${article}` : null, row.nmId ? `WB ${row.nmId}` : null].filter(Boolean).join('\n'),
      row.category ?? null,
      ...[row.revenueKopecks, row.cogsKopecks, row.commissionKopecks, row.logisticsKopecks, row.storageKopecks, row.adSpendKopecks, row.taxKopecks, row.profitBeforeInternalExpensesKopecks].map(rubles),
      row.marginPct ?? null, canonicalPnlRowStatus(row), row.comment ?? '',
    ]
  })
}

type AbcRawRow = { sku?: string | null; nmId?: number | string | null; cogsPerUnitKopecks?: number | null; adSpendKopecks?: number | null; profitBeforeInternalExpensesKopecks?: number | null; blockerIds?: string[] | null }
type AbcDisplayRow = Record<string, unknown>
export function buildAbcTableRows(rawRows: AbcRawRow[], displayRows: AbcDisplayRow[], snapshot: { count: number; rows: Array<{ row: AbcDisplayRow; originalIndex: number }> }, columns: string[]): Cell[][] {
  const seen = new Set<number>()
  if (snapshot.count !== snapshot.rows.length || rawRows.length !== displayRows.length) throw new Error('Таблица обновилась. Повторите экспорт.')
  return snapshot.rows.map(({ row, originalIndex }) => {
    const raw = rawRows[originalIndex]
    if (!Number.isInteger(originalIndex) || !raw || row !== displayRows[originalIndex] || seen.has(originalIndex)
      || String(raw.sku ?? '—') !== String(row.sku) || String(raw.nmId ?? '—') !== String(row.wb)) throw new Error('Таблица обновилась. Повторите экспорт.')
    seen.add(originalIndex)
    // Only these fields exist in the canonical ABC adapter. Unsupported metrics remain blank.
    const cells: Record<string, Cell> = {
      position: [row.sku, row.name].filter(Boolean).join('\n'), wb: raw.nmId ?? null,
      status: String(row.status ?? ''), abc: String(row.abc ?? ''), action: String(row.action ?? ''),
      cogs: rubles(raw.cogsPerUnitKopecks), sales: String(row.sales ?? ''),
      ads: raw.adSpendKopecks == null ? null : String(row.ads ?? ''), net: rubles(raw.profitBeforeInternalExpensesKopecks),
      comment: raw.blockerIds?.length ? raw.blockerIds.join(' · ') : 'canonical',
    }
    return columns.map(column => cells[column] ?? null)
  })
}

export async function downloadReportTableXlsx({ accessToken, payload, signal }: { accessToken: string; payload: ReportTableExportPayload; signal?: AbortSignal }): Promise<Blob> {
  signal?.throwIfAborted()
  if (!accessToken || payload.rows.length > 10000 || !payload.headers.length || payload.headers.length > 32
    || payload.headers.some(header => !header.length || header.length > 128)
    || payload.rows.some(row => row.length !== payload.headers.length || row.some(cell => cell !== null
      && (typeof cell === 'number' ? !Number.isFinite(cell) : typeof cell !== 'string' || cell.length > 4096)))) {
    throw new Error('Экспорт недоступен: превышен размер таблицы или найдены некорректные ячейки.')
  }
  const body = JSON.stringify(payload)
  if (new TextEncoder().encode(body).byteLength > 5 * 1024 * 1024) throw new Error('Экспорт превышает 5 МиБ. Уточните фильтры.')
  const response = await fetch(buildApiUrl('/api/v2/wb/reports/table.xlsx'), {
    method: 'POST', headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json', Accept: XLSX_MIME },
    credentials: 'include', body, signal,
  })
  signal?.throwIfAborted()
  if (!response.ok) throw new ApiError(`Не удалось выгрузить XLSX (HTTP ${response.status}).`, response.status)
  if (response.headers.get('content-type') !== XLSX_MIME) throw new ApiError('Сервер вернул некорректный формат выгрузки.', 502, 'INVALID_API_RESPONSE')
  const blob = await response.blob()
  signal?.throwIfAborted()
  return blob
}
