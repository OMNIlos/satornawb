import { useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Bell,
  Check,
  Download,
  RotateCcw,
  Save,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react'
import '../../components/vella/VellaFoundation.css'
import { getReportById, normalizeDateRange } from './repository'
import {
  createThresholdPreview,
  FIXED_ABC_SHARE,
  isFixedAbcShare,
  validateThresholdShare,
  type ThresholdPreviewInputRow,
} from './thresholds'
import type { ThresholdBand, ThresholdPreset, ThresholdPreview, ThresholdProfile, ThresholdAutomationAction, TableRow } from './types'

type Modal = 'preview' | 'export' | null
type Popover = 'notifications' | null
type BandGroup = keyof ThresholdProfile['qualityBands']
type BandKey = keyof ThresholdBand

interface AuditEvent {
  id: string
  time: string
  actor: string
  title: string
  meta: string
}

const reportTabs = [
  { label: 'Дайджест', href: '/wb/reports' },
  { label: 'ABC', href: '/wb/reports/abc' },
  { label: 'РНП', href: '/wb/reports/rnp' },
  { label: 'P&L', href: '/wb/reports/pnl' },
  { label: 'Реклама', href: '/wb/reports/ads' },
  { label: 'Остатки', href: '/wb/reports/stock' },
  { label: 'Неделя', href: '/wb/reports/week-over-week' },
  { label: 'Правила', href: '/wb/reports/rules' },
]

const automationLabels: Record<ThresholdAutomationAction, string> = {
  raise_price: 'кандидат · черновик',
  lower_price: 'ниже порога · черновик',
  rnp: 'на проверку',
  liquidation: 'ниже порога · черновик',
  stop_ads: 'кандидат · черновик',
  alert: 'алерт',
  audit: 'на проверку',
}

const presetNames: Record<ThresholdPreset, string> = {
  standard: 'Стандартный',
  conservative: 'Осторожный',
  aggressive: 'Агрессивный',
}

const thresholdPresets: Record<ThresholdPreset, ThresholdProfile> = {
  standard: {
    id: 'thr-standard',
    name: 'Стандартный профиль',
    preset: 'standard',
    version: 3,
    status: 'active',
    updatedAt: '2026-05-08T08:55:00+05:00',
    updatedBy: { id: 'user-maria-dudina', name: 'Мария Дудина', role: 'owner' },
    abc: { salesShare: FIXED_ABC_SHARE, netProfitShare: FIXED_ABC_SHARE },
    qualityBands: {
      ctrPct: { goodMin: 10, averageMin: 6 },
      crPct: { goodMin: 4, averageMin: 2 },
      cartToOrderPct: { goodMin: 45, averageMin: 25 },
      buyoutPct: { goodMin: 80, averageMin: 60 },
      marginPct: { goodMin: 25, thinMin: 10, lossBelow: 0 },
      drrPct: { goodMax: 9, warnMin: 14 },
      roiPct: { goodMin: 250, warnBelow: 100 },
      daysToOos: { warnBelow: 7 },
      stockUnits: { criticalBelow: 12 },
      localizationPct: { badBelow: 60 },
    },
    automationMapping: { aaGood: 'raise_price', badCr: 'rnp', loss: 'liquidation', highDrr: 'stop_ads', oos: 'alert', cWeak: 'audit' },
  },
  conservative: {
    id: 'thr-conservative',
    name: 'Осторожный профиль',
    preset: 'conservative',
    version: 1,
    status: 'draft',
    updatedAt: '2026-05-08T08:55:00+05:00',
    updatedBy: { id: 'user-maria-dudina', name: 'Мария Дудина', role: 'owner' },
    abc: { salesShare: FIXED_ABC_SHARE, netProfitShare: FIXED_ABC_SHARE },
    qualityBands: {
      ctrPct: { goodMin: 12, averageMin: 7 },
      crPct: { goodMin: 5, averageMin: 2.5 },
      cartToOrderPct: { goodMin: 50, averageMin: 30 },
      buyoutPct: { goodMin: 84, averageMin: 65 },
      marginPct: { goodMin: 30, thinMin: 14, lossBelow: 2 },
      drrPct: { goodMax: 8, warnMin: 12 },
      roiPct: { goodMin: 300, warnBelow: 130 },
      daysToOos: { warnBelow: 10 },
      stockUnits: { criticalBelow: 18 },
      localizationPct: { badBelow: 68 },
    },
    automationMapping: { aaGood: 'raise_price', badCr: 'rnp', loss: 'liquidation', highDrr: 'stop_ads', oos: 'alert', cWeak: 'audit' },
  },
  aggressive: {
    id: 'thr-aggressive',
    name: 'Агрессивный профиль',
    preset: 'aggressive',
    version: 1,
    status: 'draft',
    updatedAt: '2026-05-08T08:55:00+05:00',
    updatedBy: { id: 'user-maria-dudina', name: 'Мария Дудина', role: 'owner' },
    abc: { salesShare: FIXED_ABC_SHARE, netProfitShare: FIXED_ABC_SHARE },
    qualityBands: {
      ctrPct: { goodMin: 8, averageMin: 4.5 },
      crPct: { goodMin: 3.2, averageMin: 1.5 },
      cartToOrderPct: { goodMin: 38, averageMin: 20 },
      buyoutPct: { goodMin: 76, averageMin: 55 },
      marginPct: { goodMin: 20, thinMin: 7, lossBelow: -3 },
      drrPct: { goodMax: 11, warnMin: 18 },
      roiPct: { goodMin: 180, warnBelow: 70 },
      daysToOos: { warnBelow: 5 },
      stockUnits: { criticalBelow: 8 },
      localizationPct: { badBelow: 52 },
    },
    automationMapping: { aaGood: 'raise_price', badCr: 'rnp', loss: 'liquidation', highDrr: 'stop_ads', oos: 'alert', cWeak: 'audit' },
  },
}

const initialAudit: AuditEvent[] = [
  { id: 'audit-1', time: '08:55', actor: 'Менеджер', title: 'Активирован стандартный профиль', meta: 'ABC 20/30/50 · CR в норме от 4% · ДРР warn от 14%' },
  { id: 'audit-2', time: '08:41', actor: 'Финансы', title: 'Проверен осторожный профиль', meta: '22 SKU поменяли бы статус, профиль не применён' },
  { id: 'audit-3', time: '07:58', actor: 'Система', title: 'Жёсткие защиты проверены', meta: 'P_min и лимиты шага цены не зависят от профиля правил' },
]

function cloneProfile(profile: ThresholdProfile): ThresholdProfile {
  return {
    ...profile,
    abc: {
      salesShare: { ...FIXED_ABC_SHARE },
      netProfitShare: { ...FIXED_ABC_SHARE },
    },
    qualityBands: Object.fromEntries(
      Object.entries(profile.qualityBands).map(([key, value]) => [key, { ...value }]),
    ) as ThresholdProfile['qualityBands'],
    automationMapping: { ...profile.automationMapping },
    updatedBy: { ...profile.updatedBy },
  }
}

function toNumber(value: TableRow[string]) {
  return typeof value === 'number' ? value : Number(value) || 0
}

function previewRowsFromReport(rows: TableRow[]): ThresholdPreviewInputRow[] {
  const bySales = [...rows].sort((a, b) => toNumber(b.salesKopecks) - toNumber(a.salesKopecks))
  const byProfit = [...rows].sort((a, b) => toNumber(b.netTotalKopecks) - toNumber(a.netTotalKopecks))
  const salesRank = new Map(bySales.map((row, index) => [String(row.sku), index + 1]))
  const profitRank = new Map(byProfit.map((row, index) => [String(row.sku), index + 1]))
  const total = Math.max(rows.length, 1)

  return rows.map((row) => ({
    sku: String(row.sku),
    salesRankPct: (salesRank.get(String(row.sku)) ?? total) / total * 100,
    netProfitRankPct: (profitRank.get(String(row.sku)) ?? total) / total * 100,
    marginPct: toNumber(row.marginPct),
    crPct: toNumber(row.cartCrPct),
    drrPct: toNumber(row.drrSalesPct),
    roiPct: toNumber(row.adSpendKopecks) > 0 ? toNumber(row.netTotalKopecks) / toNumber(row.adSpendKopecks) * 100 : 0,
    daysToOos: Math.round(toNumber(row.wbStockUnits) / Math.max(0.2, toNumber(row.ordersUnits) / 7)),
    stockUnits: toNumber(row.wbStockUnits),
  }))
}

function profileMeta(profile: ThresholdProfile) {
  const state = profile.status === 'active' ? 'действует' : 'на проверке'
  return `версия ${profile.version} · ${state} · обновлено 08.05.2026 08:55`
}

function sumShare(profile: ThresholdProfile, axis: 'salesShare' | 'netProfitShare') {
  const share = profile.abc[axis]
  return share.aPct + share.bPct + share.cPct
}

function actionLabel(action: string) {
  return automationLabels[action as ThresholdAutomationAction] ?? action
}

function Field({
  label,
  group,
  field,
  unit,
  draft,
  onChange,
}: {
  label: string
  group: BandGroup
  field: BandKey
  unit: string
  draft: ThresholdProfile
  onChange: (group: BandGroup, field: BandKey, value: number) => void
}) {
  const value = draft.qualityBands[group][field] ?? 0
  return (
    <label className="vella-threshold-field">
      <span>{label}</span>
      <div className="vella-threshold-input">
        <input
          type="number"
          step={unit === '%' ? 0.1 : 1}
          value={value}
          onChange={(event) => onChange(group, field, Number(event.target.value))}
        />
        <em>{unit}</em>
      </div>
    </label>
  )
}

export function WbReportRulesPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const isInternalPreview = location.pathname.startsWith('/internal/vella-preview')
  const [activeProfile, setActiveProfile] = useState(() => cloneProfile(thresholdPresets.standard))
  const [draft, setDraft] = useState(() => cloneProfile(thresholdPresets.standard))
  const [audit, setAudit] = useState<AuditEvent[]>(initialAudit)
  const [modal, setModal] = useState<Modal>(null)
  const [popover, setPopover] = useState<Popover>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [preview, setPreview] = useState<ThresholdPreview | null>(null)

  const report = useMemo(() => getReportById('abc', normalizeDateRange({ preset: '7d' }), 'sku'), [])
  const previewRows = useMemo(() => previewRowsFromReport(report.rows), [report.rows])
  const livePreview = useMemo(() => createThresholdPreview(previewRows, activeProfile, draft), [activeProfile, draft, previewRows])
  const visiblePreviewRows = (preview ?? livePreview).sampleRows.filter((row) => !search || row.sku.toLowerCase().includes(search.toLowerCase()) || row.reason.toLowerCase().includes(search.toLowerCase()))
  const isDraftValid = validateThresholdShare(draft.abc.salesShare) && validateThresholdShare(draft.abc.netProfitShare) && isFixedAbcShare(draft.abc.salesShare) && isFixedAbcShare(draft.abc.netProfitShare)
  const hasChanges = JSON.stringify(activeProfile.qualityBands) !== JSON.stringify(draft.qualityBands) || activeProfile.preset !== draft.preset
  const automationTotal = livePreview.automationImpact.rnp + livePreview.automationImpact.liquidation + livePreview.automationImpact.alerts + livePreview.automationImpact.stopAds

  function pushToast(message: string) {
    setToast(message)
    window.setTimeout(() => setToast(null), 2400)
  }

  function choosePreset(preset: ThresholdPreset) {
    const next = cloneProfile(thresholdPresets[preset])
    next.status = 'draft'
    next.version = activeProfile.version
    setDraft(next)
    pushToast(`Пресет выбран: ${next.name}`)
  }

  function updateBand(group: BandGroup, field: BandKey, value: number) {
    setDraft((current) => ({
      ...current,
      status: 'draft',
      qualityBands: {
        ...current.qualityBands,
        [group]: {
          ...current.qualityBands[group],
          [field]: value,
        },
      },
    }))
  }

  function resetDraft() {
    setDraft(cloneProfile(activeProfile))
    setPreview(null)
    pushToast('Изменения сброшены к действующему профилю')
  }

  function openPreview() {
    if (!isDraftValid) {
      pushToast('ABC 20/30/50 зафиксирован и должен давать 100% по каждой оси')
      return
    }
    setPreview(createThresholdPreview(previewRows, activeProfile, draft))
    setModal('preview')
  }

  function applyProfile() {
    const nextVersion = activeProfile.version + 1
    const nextProfile: ThresholdProfile = {
      ...cloneProfile(draft),
      version: nextVersion,
      status: 'active',
      updatedAt: new Date().toISOString(),
      updatedBy: { id: 'user-maria-dudina', name: 'Мария Дудина', role: 'owner' },
    }
    const appliedPreview = createThresholdPreview(previewRows, activeProfile, nextProfile)
    setActiveProfile(nextProfile)
    setDraft(cloneProfile(nextProfile))
    setAudit((current) => [
      {
        id: `audit-${Date.now()}`,
        time: 'сейчас',
        actor: 'Мария Дудина',
        title: `Профиль применён: v${activeProfile.version} -> v${nextVersion}`,
        meta: `${appliedPreview.abcChanges} ABC · ${appliedPreview.statusChanges} статусов · автоматика: ${appliedPreview.automationImpact.rnp + appliedPreview.automationImpact.liquidation + appliedPreview.automationImpact.alerts + appliedPreview.automationImpact.stopAds}`,
      },
      ...current,
    ])
    setPreview(null)
    setModal(null)
    pushToast('Пороговый профиль применён. Автоматика возьмёт правила в следующий цикл.')
  }

  function routeFor(href: string) {
    return isInternalPreview ? href.replace('/wb/reports', '/internal/vella-preview/reports') : href
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <img className="vella-brand-logo" src="/brand/satorna-logo-white.svg" alt="Satorna" />
          </div>
          <div className="vella-nav-label">WB</div>
          <button className="vella-nav-button vella-nav-parent" type="button" onClick={() => navigate(isInternalPreview ? '/internal/vella-preview/repricer' : '/wb/repricer')}>
            <span className="vella-nav-dot" />
            Репрайсер
          </button>
          <div className="vella-nav-group">
            <button className="vella-nav-button active vella-nav-parent" type="button">
              <span className="vella-nav-dot" />
              Отчёты
            </button>
            {reportTabs.map((tab) => (
              <button className={`vella-nav-button ${tab.href === '/wb/reports/rules' ? 'active' : ''}`} key={tab.href} type="button" onClick={() => navigate(routeFor(tab.href))}>
                <span className="vella-nav-dot" />
                {tab.label}
              </button>
            ))}
          </div>
          <div className="vella-nav-label">Авито</div>
          {['Чаты', 'Объявления', 'Кошельки'].map((item) => <button className="vella-nav-button" type="button" key={item}><span className="vella-nav-dot" />{item}</button>)}
          <div className="vella-nav-label">Система</div>
          {['Уведомления', 'Настройки'].map((item) => <button className="vella-nav-button" type="button" key={item}><span className="vella-nav-dot" />{item}</button>)}
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> Отчёты <span>/</span> <b>Правила</b></div>
            <div className="vella-top-actions">
              <div className="vella-position">
                <button className="vella-icon-button" type="button" aria-label="Уведомления" onClick={() => setPopover(popover === 'notifications' ? null : 'notifications')}>
                  <Bell size={16} />
                </button>
                {popover === 'notifications' && (
                  <div className="vella-popover">
                    <button className="vella-popover-row" type="button" onClick={openPreview}>Проверка влияния: {livePreview.affectedSkuCount} SKU</button>
                    <button className="vella-popover-row" type="button" onClick={() => navigate(routeFor('/wb/reports/abc'))}>Открыть ABC после применения</button>
                  </div>
                )}
              </div>
              <button className="vella-button" type="button" onClick={() => setModal('export')}><Download size={16} /> Экспорт</button>
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-report-head">
              <div>
                <h1>Правила отчётов</h1>
                <p>Глобальные пороги классификации, статусов правил и автоматики. Перед сохранением можно проверить, сколько товаров изменят статус.</p>
              </div>
              <div className="vella-drawer-actions">
                <button className="vella-button" type="button" onClick={resetDraft}><RotateCcw size={15} /> Сбросить</button>
                <button className="vella-button" type="button" onClick={openPreview}>Проверить влияние</button>
                <button className="vella-button primary" type="button" disabled={!hasChanges} onClick={openPreview}><Save size={15} /> Сохранить после проверки</button>
              </div>
            </div>

            <div className="vella-kpis">
              <div className="vella-kpi"><div className="vella-kpi-label">Затронуто</div><div className="vella-kpi-value">{livePreview.affectedSkuCount} SKU</div><div className="vella-kpi-delta">{hasChanges ? 'есть изменения' : 'без изменений'}</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">ABC меняется</div><div className="vella-kpi-value">{livePreview.abcChanges}</div><div className="vella-kpi-delta good">20/30/50 зафиксирован</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Статусы</div><div className="vella-kpi-value">{livePreview.statusChanges}</div><div className="vella-kpi-delta warn">после проверки</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Автоматика</div><div className="vella-kpi-value">{automationTotal}</div><div className="vella-kpi-delta">следующий цикл</div></div>
            </div>

            <div className="vella-rules-layout">
              <nav className="vella-rules-anchors" aria-label="Разделы правил">
                {['Профиль', 'ABC', 'Воронка', 'Экономика', 'Реклама', 'Остатки', 'Автоматика', 'История'].map((item) => (
                  <a href={`#rules-${item.toLowerCase()}`} key={item}>{item}</a>
                ))}
              </nav>

              <div className="vella-rules-stack">
                <section className="vella-section" id="rules-профиль">
                  <div className="vella-section-title">Профиль правил</div>
                  <div className="vella-threshold-profile">
                    <div>
                      <strong>{draft.name}</strong>
                      <span>{profileMeta(draft)}</span>
                    </div>
                    <span className={`vella-badge ${draft.status === 'active' ? 'good' : 'warn'}`}>{draft.status === 'active' ? 'действует' : 'на проверке'}</span>
                  </div>
                  <div className="vella-preset-row">
                    {(Object.keys(presetNames) as ThresholdPreset[]).map((preset) => (
                      <button className={`vella-chip ${draft.preset === preset ? 'active' : ''}`} key={preset} type="button" onClick={() => choosePreset(preset)}>{presetNames[preset]}</button>
                    ))}
                  </div>
                  <div className="vella-blocked-note"><ShieldAlert size={15} /> Пороги меняют классификацию, статусы правил и алерты. P_min, лимит шага цены и дневной лимит остаются жёсткими защитами.</div>
                </section>

                <section className="vella-section" id="rules-abc">
                  <div className="vella-section-title">ABC-классификация</div>
                  <div className="vella-empty compact">ABC-пороги не редактируются: A = 20%, B = 30%, C = 50%.</div>
                  {(['salesShare', 'netProfitShare'] as const).map((axis) => (
                    <div className="vella-abc-lock" key={axis}>
                      <b>{axis === 'salesShare' ? 'Ось продаж' : 'Ось чистой прибыли'}</b>
                      {Object.entries(draft.abc[axis]).map(([key, value]) => <span key={key}>{key.replace('Pct', '').toUpperCase()}: {value}%</span>)}
                      <em className={sumShare(draft, axis) === 100 ? 'metric-up' : 'metric-down'}>Сумма: {sumShare(draft, axis)}%</em>
                    </div>
                  ))}
                </section>

                <section className="vella-section" id="rules-воронка">
                  <div className="vella-section-title">Воронка</div>
                  <div className="vella-threshold-grid">
                    <Field label="CTR норма от" group="ctrPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="CTR внимание от" group="ctrPct" field="averageMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="CR норма от" group="crPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="CR внимание от" group="crPct" field="averageMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="Корзина -> заказ норма" group="cartToOrderPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="Выкуп норма от" group="buyoutPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                  </div>
                </section>

                <section className="vella-section" id="rules-экономика">
                  <div className="vella-section-title">Экономика</div>
                  <div className="vella-threshold-grid">
                    <Field label="Good маржа от" group="marginPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="Тонкая от" group="marginPct" field="thinMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="Loss ниже" group="marginPct" field="lossBelow" unit="%" draft={draft} onChange={updateBand} />
                  </div>
                </section>

                <section className="vella-section" id="rules-реклама">
                  <div className="vella-section-title">Реклама</div>
                  <div className="vella-threshold-grid">
                    <Field label="ДРР good до" group="drrPct" field="goodMax" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="ДРР warn от" group="drrPct" field="warnMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="ROI good от" group="roiPct" field="goodMin" unit="%" draft={draft} onChange={updateBand} />
                    <Field label="ROI warn ниже" group="roiPct" field="warnBelow" unit="%" draft={draft} onChange={updateBand} />
                  </div>
                </section>

                <section className="vella-section" id="rules-остатки">
                  <div className="vella-section-title">Остатки</div>
                  <div className="vella-threshold-grid">
                    <Field label="OOS риск до" group="daysToOos" field="warnBelow" unit="дн" draft={draft} onChange={updateBand} />
                    <Field label="Крит. остаток ниже" group="stockUnits" field="criticalBelow" unit="шт" draft={draft} onChange={updateBand} />
                    <Field label="Локализация плохая ниже" group="localizationPct" field="badBelow" unit="%" draft={draft} onChange={updateBand} />
                  </div>
                </section>

                <section className="vella-section" id="rules-автоматика">
                  <div className="vella-section-title">Автоматика</div>
                  <div className="vella-rule-map">
                    {Object.entries(draft.automationMapping).map(([key, action]) => (
                      <div className="vella-rule-map-item" key={key}>
                        <div><b>{key}</b><span>{actionLabel(action)}</span></div>
                        <span className="vella-badge neutral">{actionLabel(action)}</span>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="vella-section" id="rules-история">
                  <div className="vella-section-title">История</div>
                  <div className="vella-audit-list">
                    {audit.map((event) => (
                      <div className="vella-audit-row" key={event.id}>
                        <span>{event.time} · {event.actor}</span>
                        <b>{event.title}</b>
                        <span>{event.meta}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            </div>
          </section>
        </main>
      </div>

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true">
          <div className="vella-modal wide">
            <div className="vella-modal-head">
              <div className="vella-modal-title">{modal === 'preview' ? 'Проверка влияния правил' : 'Экспорт правил'}</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}><X size={16} /></button>
            </div>
            {modal === 'preview' && (
              <>
                <div className="vella-modal-body">
                  <div className="vella-preview-grid">
                    <div><span>Затронуто</span><b>{livePreview.affectedSkuCount} SKU</b></div>
                    <div><span>ABC меняется</span><b>{livePreview.abcChanges}</b></div>
                    <div><span>Статус меняется</span><b>{livePreview.statusChanges}</b></div>
                    <div><span>Автоматика</span><b>{automationTotal}</b></div>
                  </div>
                  <div className="vella-blocked-note"><ShieldAlert size={15} /> Сохранение профиля не запускает мгновенное массовое изменение цен. Репрайсер и ликвидация возьмут правила в следующий плановый цикл.</div>
                  <div className="vella-search-wrap">
                    <Search size={15} />
                    <input className="vella-search" placeholder="Поиск по SKU или основанию" value={search} onChange={(event) => setSearch(event.target.value)} />
                  </div>
                  <div className="vella-table-wrap">
                    <table className="vella-table">
                      <thead><tr><th>SKU</th><th>ABC</th><th>Статус</th><th>Статус правила</th><th>Основание</th></tr></thead>
                      <tbody>
                        {visiblePreviewRows.map((row) => (
                          <tr key={`${row.sku}-${row.reason}`}>
                            <td className="vella-mono">{row.sku}</td>
                            <td><span className="vella-badge neutral">{row.before.abcCode}</span> {'->'} <span className="vella-badge neutral">{row.after.abcCode}</span></td>
                            <td>{row.before.status} {'->'} <b>{row.after.status}</b></td>
                            <td>{actionLabel(row.after.action)}</td>
                            <td>{row.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {visiblePreviewRows.length === 0 && <div className="vella-empty">Изменений под текущий поиск нет.</div>}
                  </div>
                </div>
                <div className="vella-modal-foot">
                  <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
                  <button className="vella-button primary" type="button" onClick={applyProfile}><Check size={15} /> Применить профиль</button>
                </div>
              </>
            )}
            {modal === 'export' && (
              <>
                <div className="vella-modal-body">Будет выгружен профиль «{draft.name}» v{draft.version}, проверка по {report.rows.length} SKU и история из {audit.length} событий.</div>
                <div className="vella-modal-foot">
                  <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
                  <button className="vella-button primary" type="button" onClick={() => {
                    setModal(null)
                    pushToast('Экспорт правил поставлен в очередь')
                  }}>Подтвердить</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {toast && <div className="vella-toast-stack"><div className="vella-toast">{toast}</div></div>}
    </div>
  )
}
