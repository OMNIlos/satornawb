import { AlertTriangle, Check, Database, Download, RefreshCw, Upload } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SourceStatusResponseSchema, type SourceStatusResponse } from '../wb-reports/schemas'
import '../../components/vella/VellaFoundation.css'

const sourceStatusFixture = {
  sourceStatus: 'blocked',
  confidence: 'blocked',
  blockerIds: ['WB-02', 'WB-03', 'WB-06', 'WB-12', 'WB-13', 'WB-22', 'WB-23', 'WB-24'],
  sourceEvidence: [
    {
      sourceId: 'wb-source-status',
      sourceType: 'manual',
      sourceName: 'Статус источников WB',
      lastSyncedAt: null,
      freshnessTtlMinutes: null,
      fieldsUsed: ['sourceStatus', 'freshnessTtlMinutes', 'blockerIds', 'evidenceRefs'],
    },
  ],
  calculatedAt: '2026-06-30T08:15:00.000Z',
  period: { dateFrom: '2026-05-01', dateTo: '2026-05-19' },
  rows: [
    {
      sourceId: 'wb-finance-report',
      label: 'Финансовый отчёт WB',
      surface: 'P&L / расходы',
      sourceStatus: 'blocked',
      confidence: 'blocked',
      freshnessTtlMinutes: null,
      lastSyncedAt: null,
      nextRunAt: null,
      blockerIds: ['WB-12', 'WB-13', 'WB-24'],
      evidenceRefs: ['ТЗ/TZ-WB.md#p-l', 'docs/open-questions-current.md#WB-12'],
      owner: 'Максим / интеграция',
    },
    {
      sourceId: 'manual-expenses',
      label: 'Ручные/Excel расходы',
      surface: 'Расходы / P&L',
      sourceStatus: 'blocked',
      confidence: 'blocked',
      freshnessTtlMinutes: null,
      lastSyncedAt: null,
      nextRunAt: null,
      blockerIds: ['WB-12', 'WB-13', 'WB-24'],
      evidenceRefs: ['docs/open-questions-current.md#WB-12', 'docs/open-questions-current.md#WB-24'],
      owner: 'Максим',
    },
    {
      sourceId: 'wb-ads',
      label: 'Реклама WB',
      surface: 'РНП / ABC / P&L',
      sourceStatus: 'blocked',
      confidence: 'blocked',
      freshnessTtlMinutes: null,
      lastSyncedAt: null,
      nextRunAt: null,
      blockerIds: ['WB-02', 'WB-23'],
      evidenceRefs: ['docs/open-questions-current.md#WB-02'],
      owner: 'интеграция',
    },
    {
      sourceId: 'wb-spp-price',
      label: 'СПП и цена покупателя',
      surface: 'Репрайсер / защита цены',
      sourceStatus: 'blocked',
      confidence: 'blocked',
      freshnessTtlMinutes: null,
      lastSyncedAt: null,
      nextRunAt: null,
      blockerIds: ['WB-06', 'WB-22', 'WB-23'],
      evidenceRefs: ['docs/open-questions-current.md#WB-06'],
      owner: 'интеграция',
    },
  ],
  manualUploadAllowed: true,
  productionMetricsBlocked: true,
} satisfies SourceStatusResponse

const importJobs = [
  { id: 'job-opex-preview', type: 'Проверка Excel', source: 'maxim-opex-may.xlsx', status: 'черновой слой, запись закрыта', rows: 42, blockerIds: 'WB-12, WB-13, WB-24' },
  { id: 'job-wb-finance', type: 'Финансовый отчёт WB', source: 'financial_report_weekly', status: 'нет маппинга', rows: 0, blockerIds: 'WB-03, WB-12, WB-13' },
  { id: 'job-ads', type: 'Синхронизация рекламы WB', source: 'campaign statistics', status: 'требует действия', rows: 0, blockerIds: 'WB-02, WB-23' },
]

function statusLabel(status: string) {
  if (status === 'fresh') return 'свежее'
  if (status === 'partial') return 'частично готово'
  if (status === 'stale') return 'устарело'
  if (status === 'blocked') return 'требует действия'
  return 'неизвестно'
}

function badgeClass(status: string) {
  if (status === 'fresh') return 'good'
  if (status === 'partial' || status === 'stale') return 'warn'
  return 'bad'
}

function HelpTip({ children }: { children: string }) {
  return (
    <span className="vella-tooltip-wrap">
      <span className="vella-help-dot" tabIndex={0}>?</span>
      <span className="vella-tooltip">{children}</span>
    </span>
  )
}

export function WbSourcesPage() {
  const navigate = useNavigate()
  const [toast, setToast] = useState<string | null>(null)
  const status = useMemo(() => SourceStatusResponseSchema.parse(sourceStatusFixture), [])
  const blockerCount = new Set(status.rows.flatMap((row) => row.blockerIds)).size

  function pushToast(text: string) {
    setToast(text)
    window.setTimeout(() => setToast(null), 2400)
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <img className="vella-brand-logo" src="/brand/satorna-logo-white.svg" alt="Satorna" />
          </div>
          <div className="vella-nav-label">WB</div>
          <button className="vella-nav-button" type="button" onClick={() => navigate('/wb/repricer')}><span className="vella-nav-dot" />Репрайсер</button>
          <button className="vella-nav-button" type="button" onClick={() => navigate('/wb/reports')}><span className="vella-nav-dot" />Отчёты</button>
          <button className="vella-nav-button active" type="button"><span className="vella-nav-dot" />Источники и загрузки</button>
          <div className="vella-nav-label">Финансы</div>
          <button className="vella-nav-button" type="button" onClick={() => navigate('/wb/reports/expenses')}><span className="vella-nav-dot" />Расходы</button>
          <button className="vella-nav-button" type="button" onClick={() => navigate('/wb/reports/pnl')}><span className="vella-nav-dot" />P&L</button>
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> <b>Источники и загрузки</b></div>
            <div className="vella-top-actions">
              <button className="vella-button" type="button" onClick={() => pushToast('Проверка свежести поставлена в очередь')}><RefreshCw size={16} /> Проверить свежесть</button>
              <button className="vella-button primary" type="button" onClick={() => pushToast('Открыта проверка Excel; запись закрыта до WB-12/WB-13/WB-24')}><Upload size={16} /> Загрузить Excel</button>
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-report-head">
              <div>
                <h1>Источники и загрузки</h1>
                <p>Единая страница показывает свежесть источников, загрузки, ошибки WB API и блокеры, которые мешают клиентским метрикам.</p>
              </div>
              <span className="vella-badge bad">метрики требуют проверки</span>
            </div>

            <div className="vella-kpis">
              <div className="vella-kpi">
                <div className="vella-kpi-label">Источников под контролем <HelpTip>Каждая строка должна иметь статус, свежесть, блокеры и подтверждение.</HelpTip></div>
                <div className="vella-kpi-value">{status.rows.length}</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Открытых блокеров <HelpTip>Блокеры видны пользователю и команде, а не спрятаны в техработах.</HelpTip></div>
                <div className="vella-kpi-value">{blockerCount}</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Ручные загрузки <HelpTip>Excel проходит проверку. Запись закрыта, пока Максим не подтвердит расходы, налоги и видимость финансов.</HelpTip></div>
                <div className="vella-kpi-value">{status.manualUploadAllowed ? 'проверка' : 'закрыты'}</div>
              </div>
              <div className="vella-kpi">
                <div className="vella-kpi-label">Финансы <HelpTip>P&L к закрытию периода невозможен до WB-12/WB-13/WB-24.</HelpTip></div>
                <div className="vella-kpi-value">требует действия</div>
                <div className="vella-kpi-delta warn">ждём Максима</div>
              </div>
            </div>

            <div className="vella-report-grid">
              <div className="vella-section">
                <div className="vella-section-title">Что мешает клиентским метрикам</div>
                <button className="vella-plan-row" type="button" onClick={() => navigate('/wb/reports/expenses')}>
                  <span>Операционные расходы и налоги</span>
                  <strong>WB-12 / WB-13 / WB-24</strong>
                  <em>Открыть расходы</em>
                </button>
                <button className="vella-plan-row" type="button" onClick={() => navigate('/wb/repricer/stats')}>
                  <span>СПП и защита применения цены</span>
                  <strong>WB-06 / WB-22 / WB-23</strong>
                  <em>Открыть статистику</em>
                </button>
                <button className="vella-plan-row" type="button" onClick={() => navigate('/wb/reports/ads')}>
                  <span>Реклама per-SKU/per-period</span>
                  <strong>WB-02 / WB-23</strong>
                  <em>Открыть рекламу</em>
                </button>
              </div>
              <div className="vella-section">
                <div className="vella-section-title">Правила загрузки</div>
                <p className="vella-muted">Ручной ввод и Excel не пишут финансовые значения напрямую. Временный дефолт: месяц, ручное распределение, налог не задан. Подтверждение не записывает данные в P&L к закрытию периода, пока открыты WB-12/WB-13/WB-24.</p>
                <button className="vella-button" type="button" onClick={() => pushToast('Шаблон Excel: статья, период, сумма, распределение, владелец, комментарий')}>
                  <Download size={16} /> Шаблон расходов
                </button>
              </div>
            </div>

            <div className="vella-panel">
              <div className="vella-table-wrap">
                <table className="vella-table">
                  <thead>
                    <tr>
                      <th className="sticky">Источник</th>
                      <th>Экран</th>
                      <th>Статус</th>
                      <th>Freshness</th>
                      <th>Блокеры</th>
                      <th>Evidence</th>
                      <th>Владелец</th>
                    </tr>
                  </thead>
                  <tbody>
                    {status.rows.map((row) => (
                      <tr key={row.sourceId}>
                        <td className="sticky"><span className="vella-mono">{row.sourceId}</span><br />{row.label}</td>
                        <td>{row.surface}</td>
                        <td><span className={`vella-badge ${badgeClass(row.sourceStatus)}`}>{statusLabel(row.sourceStatus)}</span></td>
                        <td>{row.lastSyncedAt ?? 'нет подтверждённой синхронизации'}</td>
                        <td>{row.blockerIds.join(', ')}</td>
                        <td>{row.evidenceRefs.join(' · ')}</td>
                        <td>{row.owner}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="vella-panel">
              <div className="vella-section-title">Последние sync/import jobs</div>
              <div className="vella-table-wrap">
                <table className="vella-table">
                  <thead><tr><th>Job</th><th>Источник</th><th>Статус</th><th className="num">Строк</th><th>Блокеры</th></tr></thead>
                  <tbody>
                    {importJobs.map((job) => (
                      <tr key={job.id}>
                        <td><Database size={14} /> {job.type}</td>
                        <td>{job.source}</td>
                        <td><AlertTriangle size={14} /> {job.status}</td>
                        <td className="num">{job.rows}</td>
                        <td>{job.blockerIds}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>
        </main>
      </div>
      {toast && <div className="vella-toast-stack"><div className="vella-toast"><Check size={16} /> {toast}</div></div>}
    </div>
  )
}
