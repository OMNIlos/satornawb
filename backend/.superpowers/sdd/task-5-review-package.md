# Review Package Task 5 Final Re-review
Repo: D:\ogni-frontend\frontend
Base: 78278bd
Head: 179d922

## Commits
179d922 fix: show unavailable pnl cache miss metrics
e2bbbfe fix: avoid zero metrics on source cache miss
e13ca3e feat: show report source cache miss state

## Stat
 .../features/vella-parity/VellaHtmlParityPage.tsx  | 186 +++++++++++++++++----
 .../vella-parity/reportSourceCacheMiss.test.ts     |  31 ++++
 2 files changed, 185 insertions(+), 32 deletions(-)

## Diff
diff --git a/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx b/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx
index c0211fa..e7499b4 100644
--- a/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx
+++ b/frontend/src/features/vella-parity/VellaHtmlParityPage.tsx
@@ -6245,38 +6245,47 @@ function rnpReasonText(row: RnpBackendRow) {
     if (reason === 'ads_source_partial') return 'реклама частичная'
     if (reason === 'partial_source') return 'источник частичный'
     if (reason === 'weak_order') return 'слабый заказ'
     if (reason === 'missing_ads_row') return 'нет рекламной строки'
     return reason
   })
   return Array.from(new Set(labels)).join(', ')
 }
 
 function RnpKpiStripIsland({ replacementKey, state = { status: 'loading' } as RnpLiveState }: { replacementKey: string; state?: RnpLiveState }) {
+  const report = state.status === 'ready' ? state.report : null
   const rows = state.status === 'ready' ? getRnpRows(state.report) : []
   const statuses = rows.map(rnpBusinessStatus)
   const belowRows = statuses.filter((status) => status.tags.includes('below-threshold')).length
   const reviewRows = statuses.filter((status) => status.tags.includes('review')).length
   const rnpPct = rows.length > 0 ? belowRows / rows.length * 100 : null
   const salesDeltas = rows.map(rnpRowSalesDelta).map(asAdsNumber).filter((value): value is number => value != null)
   const salesWow = salesDeltas.length > 0 ? salesDeltas.reduce((sum, value) => sum + value, 0) / salesDeltas.length : null
   const activeWarehouseSet = rnpActiveWarehouseKeys(rows)
   const activeWarehouses = activeWarehouseSet.size > 0 ? activeWarehouseSet.size : rows.length > 0 ? 33 : null
   const sourceReviewCount = state.status === 'ready' && (state.report.adsSourceStatus !== 'fresh' || state.report.meta?.freshnessState !== 'fresh') ? 1 : 0
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const cards = state.status === 'error'
     ? [
         { label: 'РНП', value: 'нет данных', delta: state.message, deltaClass: 'down', tip: 'Агрегированный сигнал по SKU и сегментам ниже порогов выбранного профиля.', stroke: '#EF4444', points: '2,18 12,16 22,17 32,15 42,14' },
         { label: 'Продажи WoW', value: 'нет данных', delta: 'backend error', deltaClass: 'neutral', tip: 'Изменение продаж неделя к неделе.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
         { label: 'Ниже порога', value: 'нет данных', delta: 'нет строк', deltaClass: 'neutral', tip: 'SKU, которые попали ниже порога выбранного профиля.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
         { label: 'Активные склады', value: 'нет данных', delta: 'источник недоступен', deltaClass: 'neutral', tip: 'Количество складов, участвующих в live-срезе.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
       ]
-    : [
+    : sourceCacheMiss
+      ? [
+          { label: 'РНП', value: reportSourceCacheMissMetricValue(report, '0%'), delta: 'source cache недоступен', deltaClass: 'neutral', tip: 'Агрегированный сигнал по SKU и сегментам ниже порогов выбранного профиля.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
+          { label: 'Продажи WoW', value: reportSourceCacheMissMetricValue(report, '0%'), delta: 'source cache недоступен', deltaClass: 'neutral', tip: 'Изменение продаж неделя к неделе.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
+          { label: 'Ниже порога', value: reportSourceCacheMissMetricValue(report, '0 SKU'), delta: 'нет строк источника', deltaClass: 'neutral', tip: 'SKU, которые попали ниже порога выбранного профиля.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
+          { label: 'Активные склады', value: 'нет данных', delta: 'source cache недоступен', deltaClass: 'neutral', tip: 'Количество складов, участвующих в live-срезе.', stroke: '#94A3B8', points: '2,15 12,15 22,15 32,15 42,15' },
+        ]
+      : [
         { label: 'РНП', value: state.status === 'loading' ? 'загрузка' : `${(rnpPct ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}%`, delta: state.status === 'loading' ? 'считаем сигнал' : `${belowRows > 0 ? '↓' : '→'} ${belowRows > 0 ? 'ниже порога' : 'в норме'}`, deltaClass: belowRows > 0 ? 'down' : 'up', tip: 'Агрегированный сигнал по SKU и сегментам ниже порогов выбранного профиля.', stroke: '#2563EB', points: '2,18 10,15 18,16 28,11 36,10 42,7' },
         { label: 'Продажи WoW', value: state.status === 'loading' ? 'загрузка' : rnpSignedPct(salesWow), delta: state.status === 'loading' ? 'ждем продажи' : `по ${salesDeltas.length.toLocaleString('ru-RU')} SKU`, deltaClass: (salesWow ?? 0) >= 0 ? 'up' : 'down', tip: 'Изменение продаж неделя к неделе.', stroke: '#10B981', points: '2,17 10,16 18,14 28,12 36,10 42,8' },
         { label: 'Ниже порога', value: state.status === 'loading' ? 'загрузка' : `${belowRows.toLocaleString('ru-RU')} SKU`, delta: state.status === 'loading' ? 'проверяем профиль' : reviewRows > 0 ? `↑ +${reviewRows.toLocaleString('ru-RU')} к проверке` : 'без новых рисков', deltaClass: reviewRows > 0 ? 'down' : 'up', tip: 'SKU, которые попали ниже порога выбранного профиля.', stroke: '#F59E0B', points: '2,18 10,16 18,14 28,13 36,10 42,8' },
         { label: 'Активные склады', value: state.status === 'loading' ? 'загрузка' : formatAdsInteger(activeWarehouses), delta: state.status === 'loading' ? 'собираем срез' : sourceReviewCount > 0 ? `${sourceReviewCount} требует проверки` : 'источники в норме', deltaClass: sourceReviewCount > 0 ? 'neutral' : 'up', tip: 'Количество складов, участвующих в live-срезе.', stroke: '#94A3B8', points: '2,12 10,12 18,12 28,11 36,11 42,10' },
       ]
   return (
     <div
       key={replacementKey}
       className="stats"
       data-vella-island="rnp-kpi-strip"
@@ -6672,20 +6681,40 @@ function currentStockReportPath(period = readProductsPeriodState()) {
 
 function backgroundReportJobPath(reportPath: string, reportId: 'abc' | 'rnp' | 'pnl' | 'expenses' | 'ads' | 'stock' | 'week-over-week') {
   return reportPath.replace(`/api/wb/reports/${reportId}?`, `/api/wb/reports/${reportId}/jobs?`)
 }
 
 function backgroundReportIsRefreshing(report: unknown) {
   const job = (report as { reportJob?: { state?: string } } | null)?.reportJob
   return job?.state === 'queued' || job?.state === 'running' || job?.state === 'waiting_1c'
 }
 
+export function reportHasSourceCacheMiss(report: unknown) {
+  const cache = (report as { cache?: { status?: string } } | null)?.cache
+  return cache?.status === 'source_cache_miss'
+}
+
+export function reportSourceCacheMissMessage(report: unknown) {
+  const cache = (report as { cache?: { missingSources?: unknown } } | null)?.cache
+  if (!reportHasSourceCacheMiss(report)) return 'Данные отчёта собираются'
+  const missing = Array.isArray(cache?.missingSources)
+    ? cache.missingSources.map(String).filter(Boolean)
+    : []
+  return missing.length
+    ? `Нет source cache для: ${missing.join(', ')}. Запустите WB sync или дождитесь расписания.`
+    : 'Нет source cache для выбранного периода. Запустите WB sync или дождитесь расписания.'
+}
+
+export function reportSourceCacheMissMetricValue(report: unknown, fallback: string) {
+  return reportHasSourceCacheMiss(report) ? 'нет данных' : fallback
+}
+
 function removeLegacyReportTableFallbacks(tabId: 'rnp' | 'pnl' | 'ads' | 'stock' | 'week') {
   const root = document.getElementById(`tab-${tabId}`)
   if (!root) return
   const liveBindings: Record<typeof tabId, string> = {
     rnp: 'backend-rnp',
     pnl: 'backend-pnl',
     ads: 'backend-ads',
     stock: 'backend-stock',
     'week': 'backend-week-over-week',
   }
@@ -7020,71 +7049,84 @@ function getPnlRows(report: PnlBackendReport) {
 }
 
 function getPnlCashFlowRows(report: PnlBackendReport | null) {
   const rows = report?.cashFlow?.data?.rows
   return Array.isArray(rows) ? rows : []
 }
 
 function PnlLiveSourceStripIsland({ replacementKey, state }: { replacementKey: string; state: PnlLiveState }) {
   const isReady = state.status === 'ready'
   const report = isReady ? state.report : null
+  const sourceTitle = reportHasSourceCacheMiss(report)
+    ? reportSourceCacheMissMessage(report)
+    : report?.headline || report?.meta?.title || 'P&L получен с бэкенда'
   const job = state.status === 'ready' ? null : state.job ?? null
   const rowCount = report ? getPnlRows(report).length : 0
   const chips = isReady
     ? [
         report?.meta?.sourceType ?? 'backend',
         report?.meta?.freshnessState ?? 'live',
         report?.financialConfirmationStatus ?? 'status unknown',
       ]
     : state.status === 'loading'
       ? ['backend', job?.state ?? 'loading']
       : ['backend', job?.state === 'failed' ? 'failed' : 'error']
   const card: SourceStateCard = {
     className: state.status === 'error' || job?.workerDelayed ? 'source-state-card stale' : rowCount > 0 ? 'source-state-card fresh' : 'source-state-card partial',
     kicker: 'live P&L',
     chips,
     title: state.status === 'error'
       ? job?.state === 'failed' ? 'Фоновая сборка P&L завершилась с ошибкой' : 'Бэкенд P&L не ответил, мок-фоллбэк отключен'
       : state.status === 'loading'
         ? job?.label ?? 'Запускаем сборку P&L'
-        : report?.headline || report?.meta?.title || 'P&L получен с бэкенда',
+        : sourceTitle,
     meta: state.status === 'error'
       ? state.message
       : state.status === 'loading'
         ? job?.workerDelayed
           ? 'Задача больше 30 секунд ждёт worker. Проверьте Celery worker и очередь.'
           : job?.percent !== null && job?.percent !== undefined
             ? `Прогресс: ${job.percent}%`
             : job?.state === 'queued'
               ? 'Задача поставлена в очередь и ожидает worker'
               : currentPnlReportPath()
         : report?.warning || `Строк: ${rowCount}; период: ${report?.meta?.dateRange?.from ?? 'не указан'} - ${report?.meta?.dateRange?.to ?? 'не указан'}`,
   }
   return <ReportSourceStripIsland replacementKey={replacementKey} islandName="pnl-source-state-strip" cards={[card]} />
 }
 
 function PnlLiveWorkbenchIsland({ replacementKey, state }: { replacementKey: string; state: PnlLiveState }) {
   const report = state.status === 'ready' ? state.report : {}
   const rows = getPnlRows(report)
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const revenue = getPnlKpiValue(report, 'revenue') ?? formatPnlKopecks(sumPnlRows(rows, 'revenueKopecks'))
   const netProfit = getPnlKpiValue(report, 'net_profit') ?? formatPnlKopecks(sumPnlRows(rows, 'netProfitKopecks'))
   const margin = getPnlKpiValue(report, 'margin_pct') ?? formatPnlPercent(rows.length ? sumPnlRows(rows, 'netProfitKopecks') / Math.max(sumPnlRows(rows, 'revenueKopecks'), 1) * 100 : null)
   const flowItems = state.status === 'error'
     ? [
         ['Выручка', 'нет данных', 'pnl-flow-item'],
         ['Себестоимость', 'нет данных', 'pnl-flow-item cost'],
         ['Комиссия', 'нет данных', 'pnl-flow-item cost'],
         ['Логистика', 'нет данных', 'pnl-flow-item cost'],
         ['Хранение/штрафы', 'нет данных', 'pnl-flow-item cost'],
         ['Прибыль / маржа', 'нет данных', 'pnl-flow-item profit'],
       ]
-    : [
+    : sourceCacheMiss
+      ? [
+          ['Выручка', reportSourceCacheMissMetricValue(report, '0 ₽'), 'pnl-flow-item'],
+          ['Себестоимость', 'нет данных', 'pnl-flow-item cost'],
+          ['Комиссия', 'нет данных', 'pnl-flow-item cost'],
+          ['Логистика', 'нет данных', 'pnl-flow-item cost'],
+          ['Хранение/штрафы', 'нет данных', 'pnl-flow-item cost'],
+          ['Прибыль / маржа', 'нет данных', 'pnl-flow-item profit'],
+        ]
+      : [
         ['Выручка', state.status === 'loading' ? 'загрузка' : revenue, 'pnl-flow-item'],
         ['Себестоимость', state.status === 'loading' ? 'загрузка' : formatPnlKopecks(sumPnlRows(rows, 'cogsKopecks')), 'pnl-flow-item cost'],
         ['Комиссия', state.status === 'loading' ? 'загрузка' : formatPnlKopecks(sumPnlRows(rows, 'commissionKopecks')), 'pnl-flow-item cost'],
         ['Логистика', state.status === 'loading' ? 'загрузка' : formatPnlKopecks(sumPnlRows(rows, 'logisticsKopecks')), 'pnl-flow-item cost'],
         ['Хранение/штрафы', state.status === 'loading' ? 'загрузка' : formatPnlKopecks(sumPnlRows(rows, 'storageKopecks') + sumPnlRows(rows, 'returnsPenaltyKopecks')), 'pnl-flow-item cost'],
         ['Прибыль / маржа', state.status === 'loading' ? 'загрузка' : `${netProfit} · ${margin}`, 'pnl-flow-item profit'],
       ]
   return (
     <div
       key={replacementKey}
@@ -7100,34 +7142,41 @@ function PnlLiveWorkbenchIsland({ replacementKey, state }: { replacementKey: str
           </div>
         ))}
       </div>
     </div>
   )
 }
 
 function PnlLiveStatusGridIsland({ replacementKey, state }: { replacementKey: string; state: PnlLiveState }) {
   const report = state.status === 'ready' ? state.report : null
   const rows = report ? getPnlRows(report) : []
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const job = state.status === 'ready' ? null : state.job ?? null
   const cards = state.status === 'error'
     ? [
         ['Статус', job?.state === 'failed' ? 'failed' : 'ошибка бэка', 'pnl-status-card warn'],
         ['Фоллбэк', 'отключён', 'pnl-status-card good'],
         ['Детали', state.message, 'pnl-status-card'],
       ]
     : state.status === 'loading'
       ? [
           ['Статус', job?.state === 'queued' ? 'queued · в очереди' : job?.state === 'running' ? 'running · выполняется' : job?.state === 'waiting_1c' ? 'waiting_1c · ждём 1С' : 'запуск', job?.workerDelayed ? 'pnl-status-card warn' : 'pnl-status-card'],
           ['Этап', job?.label ?? 'Запускаем задачу', 'pnl-status-card'],
           ['Прогресс', job?.percent !== null && job?.percent !== undefined ? `${job.percent}%` : 'ожидание', 'pnl-status-card'],
         ]
-    : [
+    : sourceCacheMiss
+      ? [
+          ['Статус', 'source cache недоступен', 'pnl-status-card warn'],
+          ['Строки', reportSourceCacheMissMetricValue(report, 'Строки: 0'), 'pnl-status-card'],
+          ['Обновлено', 'нет данных', 'pnl-status-card'],
+        ]
+      : [
         ['Статус', report?.financialConfirmationStatus ?? 'получено', 'pnl-status-card good'],
         ['Строки', `${rows.length}`, 'pnl-status-card'],
         ['Обновлено', report?.meta?.generatedAt ?? 'не указано', 'pnl-status-card'],
       ]
   return (
     <div
       key={replacementKey}
       className="pnl-status-grid"
       data-vella-island="pnl-live-status-grid"
       data-vella-island-status="explicit-jsx"
@@ -7138,36 +7187,44 @@ function PnlLiveStatusGridIsland({ replacementKey, state }: { replacementKey: st
           <b>{value}</b>
         </div>
       ))}
     </div>
   )
 }
 
 function PnlLiveCostPanelIsland({ replacementKey, state }: { replacementKey: string; state: PnlLiveState }) {
   const report = state.status === 'ready' ? state.report : null
   const rows = report ? getPnlRows(report) : []
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const cashFlow = report?.cashFlow ?? null
   const cashFlowRows = getPnlCashFlowRows(report)
   const operationalExpenseRows = cashFlowRows
     .filter((row) => row.type === 'expense' && row.operationalExpense === true)
     .slice()
     .sort((left, right) => (asPnlNumber(right.amountKopecks) ?? 0) - (asPnlNumber(left.amountKopecks) ?? 0))
   const operationalExpenseTotal = cashFlow?.data?.totals?.operationalExpenseKopecks
     ?? operationalExpenseRows.reduce((sum, row) => sum + (asPnlNumber(row.amountKopecks) ?? 0), 0)
   const cashFlowReady = cashFlow?.status === 'ready'
   const cashFlowStatus = cashFlowReady
     ? `1С готово · ${operationalExpenseRows.length} статей`
     : cashFlow?.job_id
       ? `${cashFlow.status ?? 'pending'} · ${cashFlow.job_id}`
       : 'job ещё не создан'
   const cashFlowWaiting = cashFlow?.status === 'pending' || cashFlow?.status === 'processing'
-  const items = state.status === 'ready'
+  const items = sourceCacheMiss
+    ? [
+        ['Реклама', reportSourceCacheMissMetricValue(report, '0 ₽')],
+        ['Налог', 'нет данных'],
+        ['Опер. расходы', 'нет данных'],
+        ['1С cash-flow', 'source cache недоступен'],
+      ]
+    : state.status === 'ready'
     ? (cashFlowReady
         ? operationalExpenseRows.length > 0
           ? [
               ['Итого операционных', formatPnlKopecks(operationalExpenseTotal)],
               ...operationalExpenseRows.map((row) => [row.article || 'Статья 1С', formatPnlKopecks(row.amountKopecks)]),
             ]
           : [['Опер. расходы 1С', 'нет отмеченных статей']]
         : cashFlowWaiting
           ? [
               ['Статус', cashFlow?.status === 'processing' ? '1С забрала задачу' : 'ждем 1С'],
@@ -7178,31 +7235,35 @@ function PnlLiveCostPanelIsland({ replacementKey, state }: { replacementKey: str
             ['Реклама', formatPnlKopecks(sumPnlRows(rows, 'adSpendKopecks'))],
             ['Налог', formatPnlKopecks(sumPnlRows(rows, 'taxKopecks'))],
             ['Опер. расходы', formatPnlKopecks(sumPnlRows(rows, 'overheadKopecks'))],
             ['1С cash-flow', cashFlowStatus],
           ])
     : [
         ['Статус', state.status === 'loading' ? 'создаем job и ждем 1С' : 'ошибка бэка'],
         ['Источник', '1С cash-flow'],
         ['Опер. расходы', state.status === 'loading' ? 'загрузка' : 'нет данных'],
       ]
-  const panelTitle = cashFlowReady || cashFlowWaiting || state.status === 'loading'
-    ? 'Опер. расходы из 1С'
-    : 'Расходы из P&L API'
-  const panelTag = state.status === 'error'
-    ? 'нет фоллбэка'
-    : cashFlowReady
+  const panelTitle = sourceCacheMiss
+    ? 'Расходы из P&L API'
+    : cashFlowReady || cashFlowWaiting || state.status === 'loading'
+      ? 'Опер. расходы из 1С'
+      : 'Расходы из P&L API'
+  const panelTag = sourceCacheMiss
+    ? 'source cache недоступен'
+    : state.status === 'error'
+      ? 'нет фоллбэка'
+      : cashFlowReady
       ? cashFlowStatus
       : cashFlowWaiting || state.status === 'loading'
         ? 'ждем 1С'
         : 'backend'
-  const panelTagClass = state.status === 'error'
+  const panelTagClass = sourceCacheMiss || state.status === 'error'
     ? 'report-tag warn'
     : cashFlowReady
       ? 'report-tag good'
       : cashFlowWaiting || state.status === 'loading'
         ? 'report-tag fin'
         : 'report-tag fin'
   return (
     <div
       key={replacementKey}
       className="pnl-op-cost-panel"
@@ -7518,28 +7579,36 @@ function ExpensesStatsIsland({ replacementKey, state }: { replacementKey: string
   const rows = getExpensesRows(report)
   const total = report ? expensesTotalKopecks(report) : null
   const pnlTotal = rows.filter(expenseRowIsPnlReady).reduce((sum, row) => sum + (asPnlNumber(row.amountKopecks) ?? 0), 0)
   const reviewTotal = rows.filter(expenseRowNeedsReview).reduce((sum, row) => sum + (asPnlNumber(row.amountKopecks) ?? 0), 0)
   const skuDriverRows = rows.filter((row) => {
     const base = `${row.allocationBaseLabel ?? row.driver ?? ''}`.toLowerCase()
     return base.includes('sku') || base.includes('драйвер')
   }).length
   const waiting = state.status === 'loading'
   const error = state.status === 'error'
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const cards = error
     ? [
         { label: 'Все расходы', value: 'ошибка', delta: 'данные с моков не показываем', deltaClass: 'down', tip: 'Показываем только реальный ответ backend.', stroke: '#F59E0B', points: '0,8 6,10 12,12 18,13 24,13 30,15 36,16 44,18' },
         { label: 'P&L учтено', value: '—', delta: state.job?.state ?? 'job не завершен', deltaClass: 'neutral', tip: 'Расходы, готовые к учёту в P&L.', stroke: '#64748B', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
         { label: 'Чистая прибыль', value: '—', delta: 'ждем реальный backend', deltaClass: 'neutral', tip: 'Чистая прибыль требует P&L-расчёта.', stroke: '#64748B', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
         { label: 'Требует сверки', value: '—', delta: state.message, deltaClass: 'down', tip: 'Строки, по которым нужен ответ backend.', stroke: '#F59E0B', points: '0,8 6,10 12,12 18,13 24,13 30,15 36,16 44,18' },
       ]
-    : [
+    : sourceCacheMiss
+      ? [
+          { label: 'Все расходы', value: reportSourceCacheMissMetricValue(report, '0 ₽'), delta: 'source cache недоступен', deltaClass: 'neutral', tip: 'Рабочие выбытия из отчёта 1С «Движение денежных средств».', stroke: '#94A3B8', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
+          { label: 'P&L учтено', value: 'нет данных', delta: 'нет строк source cache', deltaClass: 'neutral', tip: 'Расходы, которые уже можно учитывать в общем P&L выбранного периода.', stroke: '#94A3B8', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
+          { label: 'Чистая прибыль', value: 'нет данных', delta: 'требуется source cache', deltaClass: 'neutral', tip: 'Финальная чистая прибыль считается в P&L, здесь показываем связь расходов с P&L.', stroke: '#94A3B8', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
+          { label: 'Требует сверки', value: 'нет данных', delta: 'нет строк source cache', deltaClass: 'neutral', tip: 'Строки, по которым нужно подтвердить правило или драйвер перед закрытием периода.', stroke: '#94A3B8', points: '0,13 6,13 12,12 18,12 24,11 30,11 36,10 44,10' },
+        ]
+      : [
         { label: 'Все расходы', value: waiting ? 'загрузка' : formatPnlKopecks(total), delta: waiting ? 'создаем job и ждем 1С' : `${rows.length} статей ДДС`, deltaClass: 'up', tip: 'Рабочие выбытия из отчёта 1С «Движение денежных средств».', stroke: '#2563EB', points: '0,16 6,14 12,15 18,12 24,10 30,11 36,8 44,7' },
         { label: 'P&L учтено', value: waiting ? 'загрузка' : formatPnlKopecks(pnlTotal), delta: waiting ? '1С cash-flow' : skuDriverRows > 0 ? `${skuDriverRows} со SKU-драйвером` : 'без SKU-драйвера', deltaClass: 'neutral', tip: 'Расходы, которые уже можно учитывать в общем P&L выбранного периода.', stroke: '#10B981', points: '0,18 6,16 12,14 18,13 24,12 30,9 36,9 44,5' },
         { label: 'Чистая прибыль', value: waiting ? 'загрузка' : getPnlKpiValue(pnlReport ?? {}, 'net_profit') ?? expensesKpiValue(report, 'net_profit') ?? 'P&L недоступен', delta: waiting ? 'после ответа 1С' : pnlReport ? 'из P&L за период' : 'откройте P&L', deltaClass: 'up', tip: 'Финальная чистая прибыль считается в P&L, здесь показываем связь расходов с P&L.', stroke: '#10B981', points: '0,16 6,13 12,14 18,11 24,10 30,8 36,7 44,5' },
         { label: 'Требует сверки', value: waiting ? 'загрузка' : formatPnlKopecks(reviewTotal), delta: waiting ? state.job?.state ?? 'waiting_1c' : reviewTotal > 0 ? 'есть строки на проверке' : 'нет блокеров', deltaClass: reviewTotal > 0 ? 'down' : 'neutral', tip: 'Строки, по которым нужно подтвердить правило или драйвер перед закрытием периода.', stroke: '#F59E0B', points: '0,8 6,10 12,12 18,13 24,13 30,15 36,16 44,18' },
       ]
   return (
     <div key={replacementKey} className="stats" data-vella-island="expenses-stats" data-vella-island-status="explicit-jsx">
       {cards.map((card) => (
         <div className="stat" key={card.label}>
           <div className="stat-label">
@@ -7549,34 +7618,37 @@ function ExpensesStatsIsland({ replacementKey, state }: { replacementKey: string
           <div className={`stat-delta ${card.deltaClass}`}>{card.delta}</div>
           <ExpenseStatSpark stroke={card.stroke} points={card.points} />
         </div>
       ))}
     </div>
   )
 }
 
 function ExpensesSourceStripIsland({ replacementKey, state }: { replacementKey: string; state: ExpensesLiveState }) {
   const report = state.status === 'ready' ? state.report : null
+  const sourceTitle = reportHasSourceCacheMiss(report)
+    ? reportSourceCacheMissMessage(report)
+    : report?.headline || 'Расходы из 1С для P&L и сверки'
   const rows = getExpensesRows(report)
   const job = state.status === 'ready' ? describePnlReportJob(report?.reportJob ?? null) : state.job ?? null
   const cashFlow = report?.cashFlow
   const ready = state.status === 'ready'
   const chips = ready
     ? ['1С ДДС', cashFlow?.status === 'ready' ? 'готово' : cashFlow?.status ?? 'получено', `${rows.length} статей`, report?.meta?.dateRange?.from && report?.meta?.dateRange?.to ? `${report.meta.dateRange.from} - ${report.meta.dateRange.to}` : 'период выбран']
     : state.status === 'loading'
       ? ['1С ДДС', job?.state ?? 'отправляем job', job?.percent !== null && job?.percent !== undefined ? `${job.percent}%` : 'ожидание']
       : ['1С ДДС', 'ошибка backend']
   const title = state.status === 'error'
       ? 'Бэкенд расходов не ответил, мок-фоллбэк отключен'
       : state.status === 'loading'
         ? job?.label ?? 'Создаем job и ждем 1С cash-flow'
-        : report?.headline || 'Расходы из 1С для P&L и сверки'
+        : sourceTitle
   const meta = state.status === 'error'
       ? state.message
       : state.status === 'loading'
         ? job?.workerDelayed
           ? 'Задача больше 30 секунд ждёт worker. Проверьте Celery worker и очередь.'
           : job?.percent !== null && job?.percent !== undefined
             ? `Прогресс: ${job.percent}%`
             : '1С должна прислать cash-flow за выбранный период'
         : report?.warning || 'В таблице только расходные операционные статьи из 1С cash-flow.'
   return (
@@ -7741,20 +7813,24 @@ function ExpensesReportIsland({ replacementKey }: { replacementKey: string }) {
         setState({ status: 'error', message: 'Нет access token для запроса расходов' })
         return
       }
       try {
         const report = await apiRequest<ExpensesBackendReport>(reportPath, {
           headers: authorizationHeaders(accessToken),
         })
         if (cancelled) return
         const job = describePnlReportJob(report?.reportJob ?? null)
         const rows = getExpensesRows(report ?? null)
+        if (reportHasSourceCacheMiss(report)) {
+          setState({ status: 'ready', report: report ?? {} })
+          return
+        }
         if (backgroundReportIsRefreshing(report) && rows.length === 0) {
           setState({ status: 'loading', job })
         } else {
           const pnlReport = await fetchPnlSnapshot()
           if (!cancelled) setState({ status: 'ready', report: report ?? {}, pnlReport })
         }
         if (backgroundReportIsRefreshing(report)) {
           pollTimer = window.setTimeout(() => void fetchExpensesReport(), PNL_JOB_POLL_INTERVAL_MS)
         }
       } catch (error) {
@@ -7762,28 +7838,28 @@ function ExpensesReportIsland({ replacementKey }: { replacementKey: string }) {
         const message = error instanceof ApiError ? error.message : 'Не удалось получить расходы из 1С'
         setState({ status: 'error', message })
       }
     }
 
     async function startExpensesReportJob() {
       if (!accessToken) {
         setState({ status: 'error', message: 'Нет access token для запроса расходов' })
         return
       }
-      setState({ status: 'loading', job: describePnlReportJob(null) })
+      setState(retainReadyReportWhileRefreshing)
       try {
-        const job = await apiRequest<PnlReportJobPayload>(jobPath, {
+        await apiRequest<PnlReportJobPayload>(jobPath, {
           method: 'POST',
           headers: authorizationHeaders(accessToken),
         })
         if (cancelled) return
-        setState({ status: 'loading', job: describePnlReportJob(job ?? null) })
+        setState(retainReadyReportWhileRefreshing)
         await fetchExpensesReport()
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось запустить job расходов в 1С'
         setState({ status: 'error', message })
       }
     }
 
     void startExpensesReportJob()
     return () => {
@@ -8033,23 +8109,32 @@ function weekSignedPct(value: unknown, suffix = '%') {
   if (numeric == null) return '—'
   return `${numeric > 0 ? '+' : ''}${numeric.toLocaleString('ru-RU', { maximumFractionDigits: 1 })}${suffix}`
 }
 
 function weekMetricValue(metric: { units?: number | null } | null | undefined) {
   const units = weekNumber(metric?.units)
   return units == null ? '—' : Math.round(units).toLocaleString('ru-RU')
 }
 
 function WeekWorkbenchIsland({ replacementKey, state }: { replacementKey: string; state: WeekLiveState }) {
+  const report = state.status === 'ready' ? state.report : null
   const rows = state.status === 'ready' ? getWeekRows(state.report) : []
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const averageDelta = (selector: (row: WeekBackendRow) => unknown) => rows.length ? rows.reduce((sum, row) => sum + (weekNumber(selector(row)) ?? 0), 0) / rows.length : null
-  const signals = [
+  const signals = sourceCacheMiss
+    ? [
+        ['Продажи', reportSourceCacheMissMetricValue(report, '0%'), 'source cache недоступен', 'week-signal'],
+        ['Заказы', reportSourceCacheMissMetricValue(report, '0 шт'), 'source cache недоступен', 'week-signal'],
+        ['Маржа', 'нет данных', 'требуется source cache', 'week-signal warn'],
+        ['SKU ниже порогов', reportSourceCacheMissMetricValue(report, '0'), 'нет строк source cache', 'week-signal danger'],
+      ]
+    : [
     ['Продажи', state.status === 'loading' ? 'загрузка' : weekSignedPct(averageDelta((row) => row.sales?.deltaPct)), state.status === 'ready' ? formatAdsKopecks(rows.reduce((sum, row) => sum + (weekNumber(row.sales?.kopecks) ?? 0), 0)) : 'данные обновляются', 'week-signal'],
     ['Заказы', state.status === 'loading' ? 'загрузка' : weekSignedPct(averageDelta((row) => row.orders?.deltaPct)), state.status === 'ready' ? `+${rows.reduce((sum, row) => sum + (weekNumber(row.orders?.units) ?? 0), 0)} шт` : 'данные обновляются', 'week-signal'],
     ['Маржа', state.status === 'loading' ? 'загрузка' : weekSignedPct(averageDelta((row) => row.marginPct?.deltaPct), ' пп'), state.status === 'ready' ? 'по данным P&L/операционных расходов' : 'данные обновляются', 'week-signal warn'],
     ['SKU ниже порогов', state.status === 'ready' ? String(rows.filter((row) => (weekNumber(row.marginPct?.percent) ?? 0) < 0).length) : 'загрузка', state.status === 'ready' ? `${rows.filter((row) => row.productStatus === 'неликвид').length} в статусе неликвид` : 'данные обновляются', 'week-signal danger'],
   ]
   const metrics = ['Цены', 'Маржа', 'Прибыль', 'Продажи', 'Заказы', 'Корзины']
   return (
     <div
       key={replacementKey}
       className="week-workbench"
@@ -8067,36 +8152,39 @@ function WeekWorkbenchIsland({ replacementKey, state }: { replacementKey: string
         {metrics.map((metric) => (
           <span className="chip-toggle active" key={metric}>{metric}</span>
         ))}
       </div>
     </div>
   )
 }
 
 function StockLiveSourceStripIsland({ replacementKey, state }: { replacementKey: string; state: StockLiveState }) {
   const report = state.status === 'ready' ? state.report : null
+  const sourceTitle = reportHasSourceCacheMiss(report)
+    ? reportSourceCacheMissMessage(report)
+    : report?.headline || 'Остатки получены с бэкенда'
   const coverage = Array.isArray(report?.sourceCoverage) ? report.sourceCoverage : []
   const missingCount = coverage.filter((item) => !['fresh', 'cached'].includes(String(item.status ?? ''))).length
   const rowCount = getStockRows(report).length
   const card: SourceStateCard = {
     className: state.status === 'error' ? 'source-state-card stale' : missingCount > 0 ? 'source-state-card partial' : 'source-state-card fresh',
     kicker: 'live stock',
     chips: state.status === 'loading'
       ? ['backend', 'loading']
       : state.status === 'error'
         ? ['backend', 'error']
         : [report?.meta?.sourceType ?? 'backend', report?.meta?.freshnessState ?? 'live', `${coverage.length} sources`],
     title: state.status === 'error'
       ? 'Бэкенд остатков не ответил, мок-фоллбэк отключен'
       : state.status === 'loading'
         ? 'Загружаем остатки с бэкенда'
-        : report?.headline || 'Остатки получены с бэкенда',
+        : sourceTitle,
     meta: state.status === 'error'
       ? state.message
       : state.status === 'loading'
         ? currentStockReportPath()
         : `Строк: ${rowCount}; источников без fresh/cache: ${missingCount}`,
   }
   return <ReportSourceStripIsland replacementKey={replacementKey} islandName="stock-source-state-strip" cards={[card]} />
 }
 
 function StockTableShellIsland({ replacementKey, state }: { replacementKey: string; state: StockLiveState }) {
@@ -8310,62 +8398,73 @@ function adsTypeTags(row: AdsBackendRow) {
   if (typeText.includes('8') || nameText.includes('search') || nameText.includes('поиск')) tags.push('поиск')
   if (typeText.includes('9') || nameText.includes('catalog') || nameText.includes('каталог')) tags.push('каталог')
   if (typeText.includes('медиа') || nameText.includes('media') || nameText.includes('медиа')) tags.push('медиа')
   if ((row.drrPct ?? 0) >= 14) tags.push('дрр выше порога')
   if (row.unallocatedSpend || row.attributionLevel === 'campaign_only') tags.push('не распределено', 'на проверку')
   return tags.join('|')
 }
 
 function AdsLiveKpiStripIsland({ replacementKey, state }: { replacementKey: string; state: AdsLiveState }) {
   const report = state.status === 'ready' ? state.report : {}
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const cards = state.status === 'error'
     ? [
         ['Расход', 'нет данных', state.message, 'down'],
         ['Бюджет РК', 'нет данных', 'backend error', 'neutral'],
         ['Баланс кабинета', 'нет данных', 'backend error', 'neutral'],
         ['Строки daily', 'нет данных', 'backend error', 'neutral'],
       ]
-    : [
+    : sourceCacheMiss
+      ? [
+          ['Расход', reportSourceCacheMissMetricValue(report, '0 ₽'), 'source cache недоступен', 'neutral'],
+          ['Бюджет РК', 'нет данных', 'source cache недоступен', 'neutral'],
+          ['Баланс кабинета', 'нет данных', 'source cache недоступен', 'neutral'],
+          ['Строки daily', 'нет данных', 'нет строк source cache', 'neutral'],
+        ]
+      : [
         ['Расход', state.status === 'loading' ? 'загрузка' : adsKpiValue(report, 'ad_spend'), 'WB fullstats / upd', 'neutral'],
         ['Бюджет РК', state.status === 'loading' ? 'загрузка' : adsKpiValue(report, 'campaign_budget'), 'текущий budget.total', 'neutral'],
         ['Баланс кабинета', state.status === 'loading' ? 'загрузка' : adsKpiValue(report, 'cabinet_balance'), 'текущий balance', 'neutral'],
         ['Строки daily', state.status === 'loading' ? 'загрузка' : adsKpiValue(report, 'daily_rows'), 'fullstats.days', 'neutral'],
       ]
   return (
     <div key={replacementKey} className="stats" data-vella-island="ads-live-kpi-strip" data-vella-island-status="explicit-jsx">
       {cards.map(([label, value, delta, deltaClass]) => (
         <div className="stat" key={label}>
           <div className="stat-label">{label}</div>
           <div className="stat-val">{value}</div>
           <div className={`stat-delta ${deltaClass}`}>{delta}</div>
         </div>
       ))}
     </div>
   )
 }
 
 function AdsLiveSourceStripIsland({ replacementKey, state }: { replacementKey: string; state: AdsLiveState }) {
   const report = state.status === 'ready' ? state.report : null
+  const sourceTitle = reportHasSourceCacheMiss(report)
+    ? reportSourceCacheMissMessage(report)
+    : report?.headline || 'Реклама получена из WB API через backend cache'
   const evidence = report?.sourceEvidence?.map((item) => item.sourceId).filter((sourceId): sourceId is string => Boolean(sourceId)).slice(0, 4) ?? []
   const card: SourceStateCard = {
     className: state.status === 'error' ? 'source-state-card stale' : state.status === 'loading' ? 'source-state-card partial' : 'source-state-card fresh',
     kicker: 'WB ads backend',
     chips: state.status === 'ready'
       ? [report?.meta?.freshnessState ?? 'fresh', report?.cache?.status ?? 'cache', ...evidence]
       : state.status === 'loading'
         ? ['loading', 'backend']
         : ['error', 'backend'],
     title: state.status === 'error'
       ? 'Реклама не загружена с бэкенда, мок-фоллбэк отключен'
       : state.status === 'loading'
         ? 'Загружаем рекламу с бэкенда'
-        : report?.headline || 'Реклама получена из WB API через backend cache',
+        : sourceTitle,
     meta: state.status === 'error'
       ? state.message
       : state.status === 'loading'
         ? currentAdsReportPath()
         : `Строк: ${adsRows(report ?? {}).length}; кэш: ${report?.cache?.fetchedAt ?? report?.meta?.lastUpdatedAt ?? 'нет отметки'}`,
   }
   return <ReportSourceStripIsland replacementKey={replacementKey} islandName="ads-live-source-state-strip" cards={[card]} />
 }
 
 function AdsLiveChartPanelIsland({ replacementKey, state }: { replacementKey: string; state: AdsLiveState }) {
@@ -8396,24 +8495,25 @@ function AdsLiveChartPanelIsland({ replacementKey, state }: { replacementKey: st
           </div>
         ))}
       </div>
     </div>
   )
 }
 
 function AdsLiveSummaryGridIsland({ replacementKey, state }: { replacementKey: string; state: AdsLiveState }) {
   const report = state.status === 'ready' ? state.report : {}
   const rows = adsRows(report)
+  const sourceCacheMiss = reportHasSourceCacheMiss(report)
   const unallocated = rows.filter((row) => row.unallocatedSpend || row.attributionLevel === 'campaign_only').length
   const clicks = rows.reduce((sum, row) => sum + (row.adClicks ?? row.clicks ?? 0), 0)
   const updRows = Array.isArray(report.spendDocuments) ? report.spendDocuments.length : 0
-  const cards = state.status === 'ready'
+  const cards = state.status === 'ready' && !sourceCacheMiss
     ? [
         ['Кампаний', String(rows.length), 'campaign-first строки', 'ok'],
         ['Клики рекламы', formatAdsInteger(clicks), 'не openCount карточки', 'ok'],
         ['Не распределено', String(unallocated), 'WB не вернул nms', unallocated > 0 ? 'warn' : 'ok'],
         ['Акты расходов', String(updRows), '/adv/v1/upd', 'ok'],
       ]
     : [
         ['Кампаний', state.status === 'loading' ? 'загрузка' : 'нет данных', 'backend', state.status === 'error' ? 'danger' : ''],
         ['Клики рекламы', state.status === 'loading' ? 'загрузка' : 'нет данных', 'backend', state.status === 'error' ? 'danger' : ''],
         ['Не распределено', state.status === 'loading' ? 'загрузка' : 'нет данных', 'backend', state.status === 'error' ? 'danger' : ''],
@@ -8540,35 +8640,37 @@ function AdsTableShellIsland({ replacementKey, state }: { replacementKey: string
             )
           })}
         </tbody>
       </table>
     </div>
   )
 }
 
 function RnpLiveSourceStripIsland({ replacementKey, state = { status: 'loading' } as RnpLiveState }: { replacementKey: string; state?: RnpLiveState }) {
   const report = state.status === 'ready' ? state.report : null
+  const sourceTitle = reportHasSourceCacheMiss(report)
+    ? reportSourceCacheMissMessage(report)
+    : `Оперативная воронка · реклама ${report?.adsSourceStatus && report.adsSourceStatus !== 'fresh' ? 'частичная' : 'live'} · локомотивы отдельным срезом`
   const job = state.status === 'ready' ? describePnlReportJob(report?.reportJob ?? null) : state.job ?? null
-  const sourcePartial = report?.adsSourceStatus && report.adsSourceStatus !== 'fresh'
   const card: SourceStateCard = {
     className: state.status === 'error' || job?.workerDelayed ? 'source-state-card stale' : state.status === 'loading' ? 'source-state-card partial' : 'source-state-card fresh',
     kicker: 'статус источников',
     chips: state.status === 'ready'
       ? ['WB-19A', 'WB-02', report?.cache?.status ?? job?.state ?? 'ready']
       : state.status === 'loading'
         ? ['WB-19A', 'WB-02', job?.state ?? 'отправляем job']
         : ['WB-19A', 'WB-02', job?.state === 'failed' ? 'failed' : 'error'],
     title: state.status === 'error'
       ? job?.state === 'failed' ? 'Сборка РНП завершилась с ошибкой' : 'Оперативная воронка недоступна'
       : state.status === 'loading'
         ? job?.label ?? 'Запускаем сборку РНП'
-        : `Оперативная воронка · реклама ${sourcePartial ? 'частичная' : 'live'} · локомотивы отдельным срезом`,
+        : sourceTitle,
     meta: state.status === 'error'
       ? state.message
       : state.status === 'loading'
         ? job?.workerDelayed
           ? 'Задача больше 30 секунд ждёт worker. Проверьте Celery worker и очередь reports.'
           : job?.percent !== null && job?.percent !== undefined
             ? `Прогресс: ${job.percent}% · ${job.state}`
             : job?.state === 'queued'
               ? 'Задача поставлена в очередь и ждёт worker.'
               : 'РНП собирается из live WB Analytics и рекламной атрибуции WB Ads.'
@@ -8853,40 +8955,44 @@ function RnpReportIsland({ replacementKey }: { replacementKey: string }) {
     const reportPath = currentRnpReportPath({ fromIso: periodFromIso, toIso: periodToIso })
     const jobPath = backgroundReportJobPath(reportPath, 'rnp')
 
     async function fetchRnpReport() {
       try {
         const report = await apiRequest<RnpBackendReport>(reportPath, {
           headers: authorizationHeaders(authToken),
         })
         if (!cancelled) {
           const job = describePnlReportJob(report?.reportJob ?? null)
+          if (reportHasSourceCacheMiss(report)) {
+            setState({ status: 'ready', report: report ?? {} })
+            return
+          }
           if (backgroundReportIsRefreshing(report) && !getRnpRows(report ?? {}).length) setState({ status: 'loading', job })
           else setState({ status: 'ready', report: report ?? {} })
           if (backgroundReportIsRefreshing(report)) retryTimer = window.setTimeout(() => void fetchRnpReport(), PNL_JOB_POLL_INTERVAL_MS)
         }
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось получить РНП с бэкенда'
         setState({ status: 'error', message })
       }
     }
 
     async function startRnpReportJob() {
-      setState({ status: 'loading', job: describePnlReportJob(null) })
+      setState(retainReadyReportWhileRefreshing)
       try {
-        const job = await apiRequest<PnlReportJobPayload>(jobPath, {
+        await apiRequest<PnlReportJobPayload>(jobPath, {
           method: 'POST',
           headers: authorizationHeaders(authToken),
         })
         if (cancelled) return
-        setState({ status: 'loading', job: describePnlReportJob(job ?? null) })
+        setState(retainReadyReportWhileRefreshing)
         await fetchRnpReport()
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось запустить сборку РНП'
         setState({ status: 'error', message })
       }
     }
 
     void startRnpReportJob()
     return () => {
@@ -9018,35 +9124,39 @@ function PnlReportIsland({ replacementKey }: { replacementKey: string }) {
     if (!pnlReportActive) return
     let cancelled = false
     let pollTimer: number | null = null
     const reportPath = currentPnlReportPath({ fromIso: periodFromIso, toIso: periodToIso })
     const jobPath = backgroundReportJobPath(reportPath, 'pnl')
 
     async function loadCompletedReport() {
       const report = await apiRequest<PnlBackendReport>(reportPath, {
         headers: authorizationHeaders(accessToken!),
       })
+      if (reportHasSourceCacheMiss(report)) {
+        if (!cancelled) setState({ status: 'ready', report: report ?? {} })
+        return
+      }
       if (!cancelled) setState({ status: 'ready', report: report ?? {} })
     }
 
     async function handleJob(jobPayload: PnlReportJobPayload) {
       if (cancelled) return
       const job = describePnlReportJob(jobPayload)
       if (job.state === 'failed') {
         setState({ status: 'error', message: job.error ?? 'Фоновая сборка P&L завершилась с ошибкой', job })
         return
       }
       if (job.state === 'completed') {
         await loadCompletedReport()
         return
       }
-      setState({ status: 'loading', job })
+      setState(retainReadyReportWhileRefreshing)
       pollTimer = window.setTimeout(() => void pollJob(), PNL_JOB_POLL_INTERVAL_MS)
     }
 
     async function pollJob() {
       try {
         const job = await apiRequest<PnlReportJobPayload>(jobPath, {
           headers: authorizationHeaders(accessToken!),
         })
         await handleJob(job ?? {})
       } catch (error) {
@@ -9054,21 +9164,21 @@ function PnlReportIsland({ replacementKey }: { replacementKey: string }) {
         const message = error instanceof ApiError ? error.message : 'Не удалось проверить статус сборки P&L'
         setState({ status: 'error', message })
       }
     }
 
     async function startPnlReportJob() {
       if (!accessToken) {
         setState({ status: 'error', message: 'Нет access token для запроса P&L API' })
         return
       }
-      setState({ status: 'loading', job: describePnlReportJob(null) })
+      setState(retainReadyReportWhileRefreshing)
       try {
         const job = await apiRequest<PnlReportJobPayload>(jobPath, {
           method: 'POST',
           headers: authorizationHeaders(accessToken),
         })
         await handleJob(job ?? {})
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось запустить сборку P&L'
         setState({ status: 'error', message })
@@ -9182,21 +9292,25 @@ function AdsReportIsland({ replacementKey }: { replacementKey: string }) {
       setState(retainReadyReportWhileRefreshing)
       try {
         await apiRequest(backgroundReportJobPath(reportPath, 'ads'), {
           method: 'POST',
           headers: authorizationHeaders(accessToken),
         })
         const report = await apiRequest<AdsBackendReport>(reportPath, {
           headers: authorizationHeaders(accessToken),
         })
         if (!cancelled) {
-          if (backgroundReportIsRefreshing(report) && !adsRows(report ?? {}).length) setState({ status: 'loading' })
+          if (reportHasSourceCacheMiss(report)) {
+            setState({ status: 'ready', report: report ?? {} })
+            return
+          }
+          if (backgroundReportIsRefreshing(report) && !adsRows(report ?? {}).length) setState(retainReadyReportWhileRefreshing)
           else setState({ status: 'ready', report: report ?? {} })
           if (backgroundReportIsRefreshing(report)) retryTimer = window.setTimeout(() => void loadAdsReport(), 2500)
         }
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось получить рекламу с бэкенда'
         setState({ status: 'error', message })
       }
     }
 
@@ -9300,21 +9414,25 @@ function useStockReportState() {
       setState(retainReadyReportWhileRefreshing)
       try {
         await apiRequest(backgroundReportJobPath(reportPath, 'stock'), {
           method: 'POST',
           headers: authorizationHeaders(accessToken),
         })
         const report = await apiRequest<StockBackendReport>(reportPath, {
           headers: authorizationHeaders(accessToken),
         })
         if (!cancelled) {
-          if (backgroundReportIsRefreshing(report) && !getStockRows(report ?? {}).length) setState({ status: 'loading' })
+          if (reportHasSourceCacheMiss(report)) {
+            setState({ status: 'ready', report: report ?? {} })
+            return
+          }
+          if (backgroundReportIsRefreshing(report) && !getStockRows(report ?? {}).length) setState(retainReadyReportWhileRefreshing)
           else setState({ status: 'ready', report: report ?? {} })
           if (backgroundReportIsRefreshing(report)) retryTimer = window.setTimeout(() => void loadStockReport(), 2500)
         }
       } catch (error) {
         if (cancelled) return
         const message = error instanceof ApiError ? error.message : 'Не удалось получить остатки с бэкенда'
         setState({ status: 'error', message })
       }
     }
 
@@ -9394,20 +9512,24 @@ function WeekReportIsland({ replacementKey }: { replacementKey: string }) {
       debug[jobDebugIndex] = { stage: 'job', method: 'POST', path: jobPath, status: 'ok' }
       publishDebug()
     }
     async function loadReport(authToken: string) {
       const reportDebugIndex = debug.findIndex((step) => step.stage === 'report')
       debug[reportDebugIndex] = { stage: 'report', method: 'GET', path: reportPath, status: 'started' }
       publishDebug()
       const report = await apiRequest<WeekBackendReport>(reportPath, { headers: authorizationHeaders(authToken) })
       if (cancelled) return
       debug[reportDebugIndex] = { stage: 'report', method: 'GET', path: reportPath, status: 'ok' }
+      if (reportHasSourceCacheMiss(report)) {
+        setState({ status: 'ready', report: report ?? {}, debug })
+        return report
+      }
       if (
         (backgroundReportIsRefreshing(report) && !getWeekRows(report ?? {}).length)
         || shouldStartWeekJobFromReport(report ?? null)
       ) {
         setState({ status: 'loading', debug: [...debug, ...weekReportJobDebug(report ?? null)] })
       } else {
         setState({ status: 'ready', report: report ?? {}, debug })
       }
       if (backgroundReportIsRefreshing(report)) retryTimer = window.setTimeout(() => void loadReport(authToken), PNL_JOB_POLL_INTERVAL_MS)
       return report
@@ -9456,21 +9578,21 @@ function WeekReportIsland({ replacementKey }: { replacementKey: string }) {
   }, [state])
 
   return (
     <div
       key={replacementKey}
       className="tab-content"
       id="tab-week"
       data-vella-island="week"
       data-vella-island-status="explicit-jsx"
     >
-      <ReportSourceStripIsland replacementKey={`${replacementKey}-source`} islandName="week-source-state-strip" cards={[{ className: state.status === 'error' ? 'source-state-card stale' : state.status === 'loading' ? 'source-state-card partial' : 'source-state-card fresh', kicker: 'live WoW', chips: [state.status === 'ready' ? 'backend' : state.status], title: state.status === 'error' ? state.message : state.status === 'loading' ? 'Загружаем WoW-отчёт' : state.report.headline || 'WoW-отчёт получен с бэкенда', meta: weekDebugMeta(state, periodState) }]} />
+      <ReportSourceStripIsland replacementKey={`${replacementKey}-source`} islandName="week-source-state-strip" cards={[{ className: state.status === 'error' ? 'source-state-card stale' : state.status === 'loading' ? 'source-state-card partial' : 'source-state-card fresh', kicker: 'live WoW', chips: [state.status === 'ready' ? 'backend' : state.status], title: state.status === 'error' ? state.message : state.status === 'loading' ? 'Загружаем WoW-отчёт' : reportHasSourceCacheMiss(state.report) ? reportSourceCacheMissMessage(state.report) : state.report.headline || 'WoW-отчёт получен с бэкенда', meta: weekDebugMeta(state, periodState) }]} />
       <WeekDebugTraceIsland replacementKey={`${replacementKey}-debug`} state={state} />
       <SimpleReportToolbarIsland
         replacementKey={`${replacementKey}-toolbar`}
         islandName="week-toolbar"
         placeholder="SKU или сегмент..."
         chips={['Все', 'Рост', 'Ниже порога', 'Маржа ниже']}
       />
       <WeekWorkbenchIsland replacementKey={`${replacementKey}-workbench`} state={state} />
       <WeekTableShellIsland replacementKey={`${replacementKey}-table`} state={state} />
     </div>
diff --git a/frontend/src/features/vella-parity/reportSourceCacheMiss.test.ts b/frontend/src/features/vella-parity/reportSourceCacheMiss.test.ts
new file mode 100644
index 0000000..32a28a4
--- /dev/null
+++ b/frontend/src/features/vella-parity/reportSourceCacheMiss.test.ts
@@ -0,0 +1,31 @@
+import { describe, expect, it } from 'vitest'
+import { reportHasSourceCacheMiss, reportSourceCacheMissMetricValue, reportSourceCacheMissMessage } from './VellaHtmlParityPage'
+
+describe('report source cache miss helpers', () => {
+  it('detects source cache miss reports', () => {
+    const report = {
+      cache: {
+        status: 'source_cache_miss',
+        missingSources: ['finance', 'ads'],
+      },
+    }
+
+    expect(reportHasSourceCacheMiss(report)).toBe(true)
+    expect(reportSourceCacheMissMessage(report)).toContain('finance, ads')
+  })
+
+  it('ignores ordinary report cache misses', () => {
+    expect(reportHasSourceCacheMiss({ cache: { status: 'missing' } })).toBe(false)
+    expect(reportSourceCacheMissMessage({ cache: { status: 'missing' } })).toBe('Данные отчёта собираются')
+  })
+
+  it('replaces fabricated metrics for source cache misses', () => {
+    const report = { cache: { status: 'source_cache_miss' } }
+
+    expect(reportSourceCacheMissMetricValue(report, '0%')).toBe('нет данных')
+    expect(reportSourceCacheMissMetricValue(report, '0 SKU')).toBe('нет данных')
+    expect(reportSourceCacheMissMetricValue(report, '0 ₽')).toBe('нет данных')
+    expect(reportSourceCacheMissMetricValue(report, 'Строки: 0')).toBe('нет данных')
+    expect(reportSourceCacheMissMetricValue({ cache: { status: 'ready' } }, '0%')).toBe('0%')
+  })
+})
