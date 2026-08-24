import { useMemo, useState } from 'react'
import {
  Bell,
  Check,
  Columns3,
  Download,
  ExternalLink,
  Upload,
  X,
} from 'lucide-react'
import { formatRub } from '../../lib/formatRub'
import '../../components/vella/VellaFoundation.css'
import { computePMinKopecks, marginStatusAt } from './pricing'
import { PROMOTIONS, PROMOTION_SKUS, type PromotionSku, type WbPromotion } from './promotionsFixtures'

type StatusFilter = WbPromotion['status'] | 'all'
type ColumnKey = 'name' | 'type' | 'status' | 'deadline' | 'participation' | 'excel' | 'risk'

const columns: Array<{ key: ColumnKey; label: string }> = [
  { key: 'name', label: 'Акция' },
  { key: 'type', label: 'Тип' },
  { key: 'status', label: 'Статус' },
  { key: 'deadline', label: 'Срок' },
  { key: 'participation', label: 'Участие' },
  { key: 'excel', label: 'XLSX' },
  { key: 'risk', label: 'Риск' },
]

function typeLabel(type: WbPromotion['type']) {
  if (type === 'flash') return 'флеш'
  if (type === 'special') return 'спец'
  return 'авто'
}

function statusLabel(status: WbPromotion['status']) {
  if (status === 'active') return 'активна'
  if (status === 'upcoming') return 'скоро'
  return 'завершена'
}

function promoRisk(promo: WbPromotion) {
  if (!promo.excelLoaded) return 'no_excel'
  if (promo.participationPct === 0 && promo.status !== 'ended') return 'not_joined'
  if (promo.status === 'active' && promo.daysUntilEnd <= 2) return 'deadline'
  return 'ok'
}

function skuPMin(sku: PromotionSku) {
  return computePMinKopecks(sku.cogsKopecks, sku.wbCommissionPct, sku.logisticsKopecks, 10)
}

function promoMarginPct(sku: PromotionSku) {
  const price = sku.promoThresholdKopecks ?? sku.currentPriceKopecks
  if (price <= 0) return 0
  const net = price * (1 - sku.wbCommissionPct / 100) - sku.logisticsKopecks - sku.cogsKopecks
  return net / price * 100
}

function promoSkuRisk(sku: PromotionSku) {
  if (!sku.promoThresholdKopecks) return 'no_threshold'
  if (sku.promoThresholdKopecks < skuPMin(sku)) return 'below_pmin'
  return marginStatusAt(sku.promoThresholdKopecks, sku.cogsKopecks, sku.wbCommissionPct, sku.logisticsKopecks)
}

export function WbPromotionsPage() {
  const [promotions, setPromotions] = useState<WbPromotion[]>(PROMOTIONS)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('active')
  const [onlyRisk, setOnlyRisk] = useState(false)
  const [hiddenColumns, setHiddenColumns] = useState<Set<ColumnKey>>(() => new Set())
  const [sortKey, setSortKey] = useState<ColumnKey>('deadline')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc')
  const [popover, setPopover] = useState<'status' | 'columns' | 'notifications' | null>(null)
  const [drawerPromo, setDrawerPromo] = useState<WbPromotion | null>(null)
  const [modal, setModal] = useState<'export' | 'import' | 'apply' | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const visibleColumns = columns.filter((column) => !hiddenColumns.has(column.key))
  const filteredPromotions = useMemo(() => {
    const q = query.trim().toLowerCase()
    return [...promotions]
      .filter((promo) => status === 'all' || promo.status === status)
      .filter((promo) => !onlyRisk || promoRisk(promo) !== 'ok')
      .filter((promo) => !q || `${promo.name} ${promo.type} ${promo.status}`.toLowerCase().includes(q))
      .sort((a, b) => {
        const values: Record<ColumnKey, [number | string, number | string]> = {
          name: [a.name, b.name],
          type: [a.type, b.type],
          status: [a.status, b.status],
          deadline: [a.status === 'active' ? a.daysUntilEnd : a.daysUntilStart, b.status === 'active' ? b.daysUntilEnd : b.daysUntilStart],
          participation: [a.participationPct, b.participationPct],
          excel: [Number(a.excelLoaded), Number(b.excelLoaded)],
          risk: [promoRisk(a), promoRisk(b)],
        }
        const [left, right] = values[sortKey]
        const result = typeof left === 'string' ? left.localeCompare(String(right), 'ru') : left - Number(right)
        return sortDirection === 'asc' ? result : -result
      })
  }, [onlyRisk, promotions, query, sortDirection, sortKey, status])

  const drawerSkus = drawerPromo ? PROMOTION_SKUS[drawerPromo.id] ?? [] : []
  const stats = useMemo(() => {
    const active = promotions.filter((promo) => promo.status === 'active').length
    const upcoming = promotions.filter((promo) => promo.status === 'upcoming').length
    const noExcel = promotions.filter((promo) => !promo.excelLoaded && promo.status !== 'ended').length
    const risk = promotions.filter((promo) => promoRisk(promo) !== 'ok').length
    return { active, upcoming, noExcel, risk }
  }, [promotions])
  const drawerRiskCount = drawerSkus.filter((sku) => ['below_pmin', 'negative', 'no_threshold'].includes(promoSkuRisk(sku))).length

  function pushToast(text: string) {
    setToast(text)
    window.setTimeout(() => setToast(null), 2400)
  }

  function toggleSort(column: ColumnKey) {
    if (sortKey === column) {
      setSortDirection((current) => current === 'asc' ? 'desc' : 'asc')
      return
    }
    setSortKey(column)
    setSortDirection('asc')
  }

  function mockImportExcel(promo: WbPromotion) {
    setPromotions((current) => current.map((item) => item.id === promo.id ? {
      ...item,
      excelLoaded: true,
      excelFileName: `${promo.name}.xlsx`,
      excelLoadedAt: new Date().toISOString().slice(0, 10),
    } : item))
    if (drawerPromo?.id === promo.id) {
      setDrawerPromo({ ...promo, excelLoaded: true, excelFileName: `${promo.name}.xlsx`, excelLoadedAt: new Date().toISOString().slice(0, 10) })
    }
    pushToast(`XLSX загружен: ${promo.name}`)
  }

  function renderCell(promo: WbPromotion, key: ColumnKey) {
    if (key === 'name') {
      return (
        <div>
          <div>{promo.name}</div>
          <div className="vella-muted">{promo.startDate} → {promo.endDate}</div>
        </div>
      )
    }
    if (key === 'type') return <span className="vella-badge neutral">{typeLabel(promo.type)}</span>
    if (key === 'status') return <span className={`vella-badge ${promo.status === 'active' ? 'good' : promo.status === 'upcoming' ? 'warn' : 'neutral'}`}>{statusLabel(promo.status)}</span>
    if (key === 'deadline') {
      if (promo.status === 'active') return promo.daysUntilEnd <= 2 ? <span className="metric-down">{promo.daysUntilEnd} дн.</span> : `${promo.daysUntilEnd} дн.`
      if (promo.status === 'upcoming') return `через ${promo.daysUntilStart} дн.`
      return 'завершена'
    }
    if (key === 'participation') return `${promo.participatingSkuCount}/${promo.eligibleSkuCount} · ${promo.participationPct}%`
    if (key === 'excel') return promo.excelLoaded ? <span className="vella-badge good">загружен</span> : <span className="vella-badge bad">нет XLSX</span>
    const risk = promoRisk(promo)
    if (risk === 'no_excel') return <span className="vella-badge bad">нет порогов</span>
    if (risk === 'deadline') return <span className="vella-badge warn">срок</span>
    if (risk === 'not_joined') return <span className="vella-badge warn">не участвуем</span>
    return <span className="vella-badge good">норма</span>
  }

  return (
    <div className="vella-root">
      <div className="vella-shell">
        <aside className="vella-sidebar">
          <div className="vella-brand">
            <div className="vella-brand-mark">S</div>
            <div>
              <div className="vella-brand-name">Satorna</div>
              <div className="vella-brand-sub">Promo guard</div>
            </div>
          </div>
          <div className="vella-nav-group">
            <div className="vella-nav-label">Акции WB</div>
            {['Активные', 'Предстоящие', 'Нет XLSX', 'Риски P_min', 'Архив'].map((item) => (
              <button className="vella-nav-button" key={item} type="button" onClick={() => {
                if (item === 'Активные') setStatus('active')
                if (item === 'Предстоящие') setStatus('upcoming')
                if (item === 'Архив') setStatus('ended')
                if (item === 'Нет XLSX' || item === 'Риски P_min') setOnlyRisk(true)
                pushToast(`Фильтр: ${item}`)
              }}>
                <span className="vella-nav-dot" />
                {item}
              </button>
            ))}
          </div>
        </aside>

        <main className="vella-main">
          <header className="vella-topbar">
            <div className="vella-breadcrumb">WB <span>/</span> <b>Акции WB</b></div>
            <div className="vella-top-actions">
              <div className="vella-position">
                <button className="vella-icon-button" type="button" aria-label="Уведомления" onClick={() => setPopover(popover === 'notifications' ? null : 'notifications')}>
                  <Bell size={16} />
                </button>
                {popover === 'notifications' && (
                  <div className="vella-popover">
                    <button className="vella-popover-row" type="button" onClick={() => setOnlyRisk(true)}>Акций с риском: {stats.risk}</button>
                    <button className="vella-popover-row" type="button" onClick={() => setStatus('upcoming')}>Предстоящих: {stats.upcoming}</button>
                  </div>
                )}
              </div>
              <button className="vella-button" type="button" onClick={() => setModal('import')}>
                <Upload size={16} /> Импорт XLSX
              </button>
              <button className="vella-button primary" type="button" onClick={() => setModal('export')}>
                <Download size={16} /> Экспорт
              </button>
            </div>
          </header>

          <section className="vella-content">
            <div className="vella-report-head">
              <div>
                <h1>Акции WB</h1>
                <p>Проверяем участие в акциях через пороги XLSX и `P_min`. Массовое управление автоакциями WB не обещаем: защита идёт через минимальную цену.</p>
              </div>
              <button className="vella-badge warn" type="button" onClick={() => setOnlyRisk((value) => !value)}>Риски: {stats.risk}</button>
            </div>

            <div className="vella-kpis">
              <div className="vella-kpi"><div className="vella-kpi-label">Активные</div><div className="vella-kpi-value">{stats.active}</div><div className="vella-kpi-delta good">идут сейчас</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Предстоящие</div><div className="vella-kpi-value">{stats.upcoming}</div><div className="vella-kpi-delta">готовим XLSX</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Нет XLSX</div><div className="vella-kpi-value">{stats.noExcel}</div><div className="vella-kpi-delta warn">нет порогов WB</div></div>
              <div className="vella-kpi"><div className="vella-kpi-label">Риски</div><div className="vella-kpi-value">{stats.risk}</div><div className="vella-kpi-delta warn">нужна проверка</div></div>
            </div>

            <div className="vella-toolbar">
              <div className="vella-toolbar-left">
                <div className="vella-search-wrap">
                  <input className="vella-search" placeholder="Поиск акции" value={query} onChange={(event) => setQuery(event.target.value)} />
                </div>
                <div className="vella-position">
                  <button className={`vella-chip ${status !== 'all' ? 'active' : ''}`} type="button" onClick={() => setPopover(popover === 'status' ? null : 'status')}>
                    Статус: {status === 'all' ? 'Все' : statusLabel(status)}
                  </button>
                  {popover === 'status' && (
                    <div className="vella-popover">
                      {(['all', 'active', 'upcoming', 'ended'] as StatusFilter[]).map((item) => (
                        <button className="vella-popover-row" key={item} type="button" onClick={() => {
                          setStatus(item)
                          setPopover(null)
                        }}>
                          <Check size={14} opacity={status === item ? 1 : 0.15} /> {item === 'all' ? 'Все' : statusLabel(item)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button className={`vella-chip ${onlyRisk ? 'active' : ''}`} type="button" onClick={() => setOnlyRisk((value) => !value)}>Только риски</button>
              </div>
              <div className="vella-toolbar-right">
                <div className="vella-position">
                  <button className="vella-button" type="button" onClick={() => setPopover(popover === 'columns' ? null : 'columns')}>
                    <Columns3 size={16} /> Колонки
                  </button>
                  {popover === 'columns' && (
                    <div className="vella-popover">
                      {columns.map((column) => (
                        <button className="vella-popover-row" key={column.key} type="button" onClick={() => {
                          setHiddenColumns((current) => {
                            const next = new Set(current)
                            if (next.has(column.key)) next.delete(column.key)
                            else next.add(column.key)
                            return next
                          })
                        }}>
                          <Check size={14} opacity={hiddenColumns.has(column.key) ? 0.15 : 1} /> {column.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="vella-panel">
              <div className="vella-table-wrap">
                <table className="vella-table">
                  <thead><tr>{visibleColumns.map((column) => <th className="sortable" key={column.key} onClick={() => toggleSort(column.key)}>{column.label}{sortKey === column.key ? (sortDirection === 'asc' ? ' ↑' : ' ↓') : ''}</th>)}<th>Действия</th></tr></thead>
                  <tbody>
                    {filteredPromotions.map((promo) => (
                      <tr key={promo.id}>
                        {visibleColumns.map((column) => <td key={column.key}>{renderCell(promo, column.key)}</td>)}
                        <td>
                          <button className="vella-button" type="button" onClick={() => setDrawerPromo(promo)}><ExternalLink size={14} /> Детали</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {filteredPromotions.length === 0 && <div className="vella-empty">Нет акций под текущие фильтры.</div>}
              </div>
            </div>
          </section>
        </main>
      </div>

      {drawerPromo && (
        <>
          <div className="vella-drawer-overlay" onClick={() => setDrawerPromo(null)} />
          <aside className="vella-drawer" aria-label="Детали акции">
            <div className="vella-drawer-head">
              <div><div className="vella-drawer-title">{drawerPromo.name}</div><div className="vella-muted">{statusLabel(drawerPromo.status)} · {typeLabel(drawerPromo.type)}</div></div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setDrawerPromo(null)}><X size={16} /></button>
            </div>
            <div className="vella-drawer-body">
              <div className="vella-section">
                <div className="vella-section-title">Участие</div>
                <div className="vella-price-grid">
                  <span>Доступно SKU</span><b>{drawerPromo.eligibleSkuCount}</b>
                  <span>Участвует</span><b>{drawerPromo.participatingSkuCount}</b>
                  <span>XLSX</span><b>{drawerPromo.excelLoaded ? drawerPromo.excelFileName ?? 'загружен' : 'нет'}</b>
                  <span>Рисковые SKU</span><b className={drawerRiskCount ? 'metric-down' : 'metric-up'}>{drawerRiskCount}</b>
                </div>
              </div>
              <div className="vella-section">
                <div className="vella-section-title">Проверка P_min</div>
                <div className="vella-mini-table">
                  {drawerSkus.length === 0 && <div className="vella-muted">SKU появятся после импорта XLSX или API WB.</div>}
                  {drawerSkus.map((sku) => {
                    const risk = promoSkuRisk(sku)
                    return (
                      <div className="vella-mini-row" key={sku.articleId}>
                        <span><b className="vella-mono">{sku.articleId}</b><em>{sku.name}</em></span>
                        <strong>{sku.promoThresholdKopecks ? formatRub(sku.promoThresholdKopecks) : 'нет порога'}</strong>
                        <i className={risk === 'below_pmin' || risk === 'negative' || risk === 'no_threshold' ? 'metric-down' : risk === 'thin' ? 'vella-warn-text' : 'metric-up'}>
                          {risk === 'no_threshold' ? 'нет XLSX' : `${promoMarginPct(sku).toFixed(1)}%`}
                        </i>
                      </div>
                    )
                  })}
                </div>
              </div>
              <div className="vella-drawer-actions">
                <button className="vella-button" type="button" onClick={() => mockImportExcel(drawerPromo)}><Upload size={16} /> Mock XLSX</button>
                <button className="vella-button primary" type="button" onClick={() => setModal('apply')}>Preview защиты</button>
              </div>
            </div>
          </aside>
        </>
      )}

      {modal && (
        <div className="vella-modal-overlay" role="dialog" aria-modal="true">
          <div className="vella-modal">
            <div className="vella-modal-head">
              <div className="vella-modal-title">{modal === 'export' ? 'Экспорт акций' : modal === 'import' ? 'Импорт XLSX' : 'Preview защиты'}</div>
              <button className="vella-icon-button" type="button" aria-label="Закрыть" onClick={() => setModal(null)}><X size={16} /></button>
            </div>
            <div className="vella-modal-body">
              {modal === 'export' && `Будет выгружено ${filteredPromotions.length} акций с текущими фильтрами, XLSX-статусом и рисками P_min.`}
              {modal === 'import' && 'В production сюда подключим загрузку XLSX WB. Сейчас импорт можно проверить через drawer конкретной акции: кнопка Mock XLSX меняет состояние.'}
              {modal === 'apply' && `Автоакции WB нельзя управлять API. Preview показывает защиту через min_price: рисковых SKU ${drawerRiskCount}. Массовое применение требует подтверждения и audit trail.`}
            </div>
            <div className="vella-modal-foot">
              <button className="vella-button" type="button" onClick={() => setModal(null)}>Отмена</button>
              <button className="vella-button primary" type="button" onClick={() => {
                pushToast(modal === 'apply' ? 'Preview защиты сохранен в mock-state' : 'Действие поставлено в mock-очередь')
                setModal(null)
              }}>Подтвердить</button>
            </div>
          </div>
        </div>
      )}

      {toast && <div className="vella-toast-stack"><div className="vella-toast">{toast}</div></div>}
    </div>
  )
}
