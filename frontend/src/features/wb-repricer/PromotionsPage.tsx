import { useEffect, useRef, useState } from 'react'
import { formatRub } from '../../lib/formatRub'
import { type WbPromotion, type PromotionSku } from './promotionsFixtures'
import { computePMinKopecks, marginStatusAt, type MarginStatus } from './pricing'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '../../components/ui/sheet'

type Tab = 'active' | 'upcoming' | 'ended'

// ── helpers ──────────────────────────────────────────────────────────────────

function typeBadge(type: WbPromotion['type']) {
  const map = {
    auto: { label: 'авто', cls: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300' },
    flash: { label: 'флеш', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
    special: { label: 'спец', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' },
  }
  const { label, cls } = map[type]
  return <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
}

function excelChip(loaded: boolean) {
  if (loaded) {
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 font-medium">✓ загружен</span>
  }
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 font-medium">! нет</span>
}

function deadlineLabel(p: WbPromotion) {
  if (p.status === 'active') {
    if (p.daysUntilEnd <= 0) return <span className="text-red-600 font-semibold">сегодня</span>
    if (p.daysUntilEnd <= 2) return <span className="text-red-500 font-semibold">{p.daysUntilEnd} дн.</span>
    if (p.daysUntilEnd <= 5) return <span className="text-amber-600 font-semibold">{p.daysUntilEnd} дн.</span>
    return <span className="text-muted-foreground">{p.daysUntilEnd} дн.</span>
  }
  if (p.status === 'upcoming') {
    return <span className="text-blue-600">через {p.daysUntilStart} дн.</span>
  }
  return <span className="text-muted-foreground/60">завершена</span>
}

function ParticipationBar({ participating, eligible }: { participating: number; eligible: number }) {
  const pct = eligible > 0 ? Math.round((participating / eligible) * 100) : 0
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs font-mono text-muted-foreground w-16 text-right">{participating}/{eligible}</span>
      <div className="w-16 bg-muted rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${pct > 50 ? 'bg-emerald-500' : pct > 0 ? 'bg-amber-400' : 'bg-muted-foreground/20'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground">{pct}%</span>
    </div>
  )
}

function promoMarginPct(sku: PromotionSku, priceKopecks: number): number {
  const net = priceKopecks * (1 - sku.wbCommissionPct / 100) - sku.logisticsKopecks - sku.cogsKopecks
  return (net / priceKopecks) * 100
}

function verdictBadge(status: MarginStatus, pct: number) {
  const label = `${pct.toFixed(0)}%`
  if (status === 'ok')
    return <span className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300 font-medium">{label} ✓</span>
  if (status === 'thin')
    return <span className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300 font-medium">{label} ⚠</span>
  return <span className="inline-flex items-center gap-0.5 text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400 font-medium">{label} ✗</span>
}

// ── PromoCalcPanel ────────────────────────────────────────────────────────────

function CalcField({
  label,
  value,
  onChange,
  placeholder,
  suffix,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  suffix?: string
}) {
  return (
    <div>
      <label className="block text-xs text-muted-foreground mb-1">{label}</label>
      <div className="relative">
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full text-xs border border-border rounded px-2 py-1.5 bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary/50 pr-6"
        />
        {suffix && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground pointer-events-none">
            {suffix}
          </span>
        )}
      </div>
    </div>
  )
}

function PromoCalcPanel() {
  const [open, setOpen] = useState(false)
  const [cogs, setCogs] = useState('')
  const [commission, setCommission] = useState('25')
  const [logistics, setLogistics] = useState('')
  const [minMargin, setMinMargin] = useState('10')
  const [promoPrice, setPromoPrice] = useState('')

  const cogsK = parseFloat(cogs) * 100
  const commPct = parseFloat(commission)
  const logK = parseFloat(logistics) * 100
  const minMargPct = parseFloat(minMargin)
  const promoPriceK = parseFloat(promoPrice) * 100

  const hasBase = !isNaN(cogsK) && cogsK > 0 && !isNaN(commPct) && !isNaN(logK) && !isNaN(minMargPct)
  const hasPromo = !isNaN(promoPriceK) && promoPriceK > 0

  const pMinK = hasBase ? computePMinKopecks(cogsK, commPct, logK, minMargPct) : null
  const marginPct = hasBase && hasPromo
    ? ((promoPriceK * (1 - commPct / 100) - logK - cogsK) / promoPriceK) * 100
    : null
  // Use user's minMargPct threshold, not the hardcoded 10% inside marginStatusAt
  const status: MarginStatus | null = marginPct !== null
    ? marginPct < 0 ? 'negative' : marginPct < minMargPct ? 'thin' : 'ok'
    : null
  const deltaK = pMinK !== null && hasPromo ? promoPriceK - pMinK : null

  return (
    <div className="mx-6 my-3 border border-border rounded-lg overflow-hidden bg-card">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full px-4 py-2.5 flex items-center justify-between text-sm font-medium hover:bg-muted/30 transition-colors"
      >
        <span className="flex items-center gap-2 text-foreground">
          Калькулятор акции
          <span className="text-xs text-muted-foreground font-normal">— стоит ли входить?</span>
        </span>
        <span className={`text-muted-foreground text-xs transition-transform duration-150 ${open ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          <div className="grid grid-cols-5 gap-2 mb-4">
            <CalcField label="Себест., ₽" value={cogs} onChange={setCogs} placeholder="450" />
            <CalcField label="Комиссия WB" value={commission} onChange={setCommission} placeholder="25" suffix="%" />
            <CalcField label="Логистика, ₽" value={logistics} onChange={setLogistics} placeholder="50" />
            <CalcField label="Мин. маржа" value={minMargin} onChange={setMinMargin} placeholder="10" suffix="%" />
            <CalcField label="Акц. цена WB, ₽" value={promoPrice} onChange={setPromoPrice} placeholder="1190" />
          </div>

          {!hasBase && (
            <p className="text-xs text-muted-foreground/60 text-center py-2">
              Заполните поля для расчёта
            </p>
          )}

          {hasBase && (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
                <div className="text-xs text-muted-foreground mb-1">P_min (порог входа)</div>
                <div className="text-base font-bold font-mono text-foreground">
                  {pMinK !== null && isFinite(pMinK) ? formatRub(pMinK) : '—'}
                </div>
              </div>

              <div className={`rounded-lg p-3 border ${
                status === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20' :
                status === 'thin' ? 'bg-amber-500/10 border-amber-500/20' :
                status === 'negative' ? 'bg-red-500/10 border-red-500/20' :
                'bg-muted/30 border-border/50'
              }`}>
                <div className="text-xs text-muted-foreground mb-1">Маржа при акц. цене</div>
                <div className={`text-base font-bold font-mono ${
                  status === 'ok' ? 'text-emerald-600 dark:text-emerald-400' :
                  status === 'thin' ? 'text-amber-600 dark:text-amber-400' :
                  status === 'negative' ? 'text-red-600 dark:text-red-400' :
                  'text-muted-foreground'
                }`}>
                  {marginPct !== null ? `${marginPct.toFixed(1)}%` : '—'}
                </div>
              </div>

              <div className={`rounded-lg p-3 border ${
                deltaK !== null && deltaK >= 0 ? 'bg-emerald-500/10 border-emerald-500/20' :
                deltaK !== null ? 'bg-red-500/10 border-red-500/20' :
                'bg-muted/30 border-border/50'
              }`}>
                <div className="text-xs text-muted-foreground mb-1">Δ от P_min</div>
                <div className={`text-base font-bold font-mono ${
                  deltaK !== null && deltaK >= 0 ? 'text-emerald-600 dark:text-emerald-400' :
                  deltaK !== null ? 'text-red-600 dark:text-red-400' :
                  'text-muted-foreground'
                }`}>
                  {deltaK !== null ? `${deltaK >= 0 ? '+' : ''}${formatRub(deltaK)}` : '—'}
                </div>
              </div>
            </div>
          )}

          {status !== null && (
            <div className={`mt-3 flex items-center gap-2 px-3 py-2 rounded text-sm font-medium ${
              status === 'ok' ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400' :
              status === 'thin' ? 'bg-amber-500/10 text-amber-700 dark:text-amber-400' :
              'bg-red-500/10 text-red-700 dark:text-red-400'
            }`}>
              {status === 'ok' && `✓ Войти — маржа выше ${minMargPct}%`}
              {status === 'thin' && `⚠ Тонкая маржа — меньше ${minMargPct}%, взвесьте риски`}
              {status === 'negative' && '✗ Убыток — акционная цена ниже себестоимости + комиссия + логистика'}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── main component ────────────────────────────────────────────────────────────

export function PromotionsPage() {
  const [promotions, setPromotions] = useState<WbPromotion[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<Tab>('active')
  const [selectedPromo, setSelectedPromo] = useState<WbPromotion | null>(null)
  const [drawerSkus, setDrawerSkus] = useState<PromotionSku[]>([])
  const [drawerSkusLoading, setDrawerSkusLoading] = useState(false)
  const [uploadingId, setUploadingId] = useState<string | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [dragOverDrawer, setDragOverDrawer] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const bulkInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/wb-repricer/promotions', { signal: controller.signal })
      .then((r) => r.json())
      .then((d: WbPromotion[]) => {
        setPromotions(d)
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        showToast('Ошибка загрузки акций')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }

  async function openDrawer(promo: WbPromotion) {
    setSelectedPromo(promo)
    setDrawerSkus([])
    setDrawerSkusLoading(true)
    try {
      const res = await fetch(`/api/v1/wb-repricer/promotions/${promo.id}/skus`)
      const skus: PromotionSku[] = await res.json()
      setDrawerSkus(skus)
      setDrawerSkusLoading(false)
    } catch {
      showToast('Ошибка: не удалось загрузить SKU акции')
      setDrawerSkusLoading(false)
    }
  }

  async function uploadExcel(promoId: string, file: File) {
    setUploadingId(promoId)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`/api/v1/wb-repricer/promotions/${promoId}/upload-excel`, {
        method: 'POST',
        body: fd,
      })
      const updated: WbPromotion = await res.json()
      setUploadingId(null)
      setPromotions((prev) => prev.map((p) => (p.id === promoId ? updated : p)))
      if (selectedPromo?.id === promoId) setSelectedPromo(updated)
      showToast(`Excel загружен · ${updated.name}`)
    } catch {
      showToast('Ошибка: не удалось загрузить Excel')
      setUploadingId(null)
    }
  }

  function handleRowUploadClick(promoId: string) {
    if (fileInputRef.current) {
      fileInputRef.current.dataset.promoId = promoId
      fileInputRef.current.click()
    }
  }

  function handleFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    const promoId = e.target.dataset.promoId
    if (file && promoId) {
      void uploadExcel(promoId, file)
    }
    e.target.value = ''
  }

  async function handleBulkUpload(files: FileList) {
    const fileArr = Array.from(files)
    if (!fileArr.length) return
    try {
      const fd = new FormData()
      fileArr.forEach((file) => fd.append('files', file))
      const res = await fetch('/api/v1/wb-repricer/promotions/upload-excel', {
        method: 'POST',
        body: fd,
      })
      if (!res.ok) throw new Error('Bulk upload failed')
      const result: {
        matchedCount?: number
        unmatchedCount?: number
        errorCount?: number
      } = await res.json()
      const refreshed = await fetch('/api/v1/wb-repricer/promotions')
      if (refreshed.ok) {
        const next: WbPromotion[] = await refreshed.json()
        setPromotions(next)
      }
      showToast(`Excel: распознано ${result.matchedCount ?? 0}, не распознано ${result.unmatchedCount ?? 0}, ошибок ${result.errorCount ?? 0}`)
    } catch {
      showToast('Ошибка: не удалось загрузить Excel')
    }
  }

  function handleDrawerDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOverDrawer(false)
    const file = e.dataTransfer.files[0]
    if (file && selectedPromo) {
      void uploadExcel(selectedPromo.id, file)
    }
  }

  const filtered = promotions.filter((p) => p.status === tab)

  const activePromos = promotions.filter((p) => p.status === 'active')
  const upcomingPromos = promotions.filter((p) => p.status === 'upcoming')
  const activeNoExcel = activePromos.filter((p) => !p.excelLoaded)
  const totalParticipating = activePromos.reduce((s, p) => s + p.participatingSkuCount, 0)
  const nextUpcomingDays = upcomingPromos.length > 0
    ? Math.min(...upcomingPromos.map((p) => p.daysUntilStart))
    : null

  const tabCounts: Record<Tab, number> = {
    active: activePromos.length,
    upcoming: upcomingPromos.length,
    ended: promotions.filter((p) => p.status === 'ended').length,
  }

  const tabLabels: Record<Tab, string> = {
    active: 'Активные',
    upcoming: 'Предстоящие',
    ended: 'Завершённые',
  }

  if (loading) {
    return <div className="p-8 text-sm text-muted-foreground/70">Загрузка…</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* Hidden file inputs */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls"
        className="hidden"
        onChange={handleFileInputChange}
      />
      <input
        ref={bulkInputRef}
        type="file"
        accept=".xlsx,.xls"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) void handleBulkUpload(e.target.files)
          e.target.value = ''
        }}
      />

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-foreground text-background text-sm px-4 py-2 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      {/* Header */}
      <div className="px-6 pt-5 pb-4 bg-card border-b border-border">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-foreground">Акции WB</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              Управление участием в акциях Wildberries и загрузка порогов входа
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {activeNoExcel.length > 0 && (
              <span className="flex items-center gap-1.5 text-sm text-amber-700 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded px-3 py-1.5">
                ⚠ {activeNoExcel.length} {activeNoExcel.length === 1 ? 'акция' : 'акции'} без Excel
              </span>
            )}
            <button
              type="button"
              onClick={() => bulkInputRef.current?.click()}
              className="px-3 py-1.5 text-sm border border-border text-foreground rounded hover:bg-muted/40 flex items-center gap-1.5"
            >
              ↑ Загрузить все
            </button>
            <a
              href="https://seller.wildberries.ru/discount-and-prices/promotions"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 text-sm border border-border text-foreground rounded hover:bg-muted/40 flex items-center gap-1.5"
            >
              → ЛК WB
            </a>
          </div>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-4 gap-3 mt-4">
          <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
            <div className="text-2xl font-bold text-foreground">{activePromos.length}</div>
            <div className="text-xs text-muted-foreground mt-0.5">Активных акций</div>
          </div>
          <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
            <div className="text-2xl font-bold text-foreground">{totalParticipating}</div>
            <div className="text-xs text-muted-foreground mt-0.5">SKU участвует</div>
          </div>
          <div className={`rounded-lg p-3 border ${activeNoExcel.length > 0 ? 'bg-red-500/10 border-red-500/20' : 'bg-muted/30 border-border/50'}`}>
            <div className={`text-2xl font-bold ${activeNoExcel.length > 0 ? 'text-red-600 dark:text-red-400' : 'text-foreground'}`}>
              {activeNoExcel.length}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">Без порогов Excel</div>
          </div>
          <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
            <div className="text-2xl font-bold text-foreground">
              {nextUpcomingDays !== null ? `${nextUpcomingDays} дн.` : '—'}
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">До следующей</div>
          </div>
        </div>
      </div>

      {/* Alert strip */}
      {activeNoExcel.length > 0 && (
        <div className="px-6 py-3 bg-amber-500/10 border-b border-amber-500/20 flex items-center gap-2 text-sm text-amber-800 dark:text-amber-300">
          <span className="text-base">⚠</span>
          <span>
            {activeNoExcel.length === 1
              ? `1 активная акция без порогов входа`
              : `${activeNoExcel.length} активные акции без порогов входа`}
            {' '}— пороги неизвестны, min_price защищает от попадания ниже себестоимости.{' '}
            <button
              type="button"
              className="underline hover:no-underline font-medium"
              onClick={() => {
                setTab('active')
              }}
            >
              Загрузить Excel
            </button>
          </span>
        </div>
      )}

      {/* Promo calculator */}
      <PromoCalcPanel />

      {/* Tabs */}
      <div className="px-6 bg-card border-b border-border flex items-end gap-0" role="tablist" aria-label="Акции по статусу">
        {(['active', 'upcoming', 'ended'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm border-b-2 transition-colors ${
              tab === t
                ? 'border-primary text-primary font-medium'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {tabLabels[t]}
            {tabCounts[t] > 0 && (
              <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${
                tab === t
                  ? 'bg-primary/10 text-primary'
                  : 'bg-muted text-muted-foreground'
              }`}>
                {tabCounts[t]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto p-6">
        {filtered.length === 0 ? (
          <div className="text-center py-12 text-sm text-muted-foreground/70">
            {tab === 'active' && 'Нет активных акций.'}
            {tab === 'upcoming' && 'Нет предстоящих акций.'}
            {tab === 'ended' && 'Завершённых акций нет.'}
          </div>
        ) : (
          <table className="w-full text-left border-collapse bg-card rounded-lg border border-border overflow-hidden">
            <thead className="bg-muted/40">
              <tr className="border-b border-border">
                <th className="px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Название акции</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Тип</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  {tab === 'active' ? 'До конца' : tab === 'upcoming' ? 'Старт' : 'Дата'}
                </th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Excel</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">SKU участвует</th>
                <th className="px-3 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Действия</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((promo) => {
                const isUploading = uploadingId === promo.id
                const rowBg = !promo.excelLoaded && promo.status === 'active'
                  ? 'bg-red-500/5 hover:bg-red-500/10'
                  : 'hover:bg-muted/30'
                return (
                  <tr
                    key={promo.id}
                    className={`border-b border-border/60 cursor-pointer transition-colors ${rowBg}`}
                    onClick={() => openDrawer(promo)}
                  >
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-foreground">{promo.name}</div>
                      {promo.excelFileName && (
                        <div className="text-xs text-muted-foreground/60 mt-0.5 truncate max-w-[220px]">
                          {promo.excelFileName}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-3">{typeBadge(promo.type)}</td>
                    <td className="px-3 py-3 text-sm">{deadlineLabel(promo)}</td>
                    <td className="px-3 py-3">{excelChip(promo.excelLoaded)}</td>
                    <td className="px-3 py-3">
                      <ParticipationBar
                        participating={promo.participatingSkuCount}
                        eligible={promo.eligibleSkuCount}
                      />
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          disabled={isUploading}
                          onClick={() => handleRowUploadClick(promo.id)}
                          className="px-2.5 py-1 text-xs border border-border rounded text-muted-foreground hover:text-foreground hover:bg-muted/40 disabled:opacity-50 flex items-center gap-1"
                        >
                          {isUploading ? (
                            <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          ) : '↑'}
                          Excel
                        </button>
                        <button
                          type="button"
                          onClick={() => openDrawer(promo)}
                          className="px-2.5 py-1 text-xs border border-border rounded text-muted-foreground hover:text-foreground hover:bg-muted/40"
                        >
                          → Детали
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Drawer */}
      <Sheet open={selectedPromo !== null} onOpenChange={(open) => { if (!open) setSelectedPromo(null) }}>
        <SheetContent
          side="right"
          className="w-[480px] sm:max-w-[480px] flex flex-col gap-0 p-0 overflow-hidden"
        >
          {selectedPromo && (
            <>
              {/* Drawer header */}
              <div className={`px-5 pt-5 pb-4 border-b border-border flex-shrink-0 ${
                !selectedPromo.excelLoaded && selectedPromo.status === 'active'
                  ? 'bg-amber-500/5'
                  : ''
              }`}>
                {!selectedPromo.excelLoaded && selectedPromo.status === 'active' && (
                  <div className="mb-3 flex items-start gap-2 px-3 py-2.5 bg-amber-500/10 border border-amber-500/20 rounded text-sm text-amber-800 dark:text-amber-300">
                    <span className="text-base flex-shrink-0">⚠</span>
                    <span>Excel с порогами входа не загружен. Без него неизвестно, попадёт ли артикул в акцию.</span>
                  </div>
                )}
                <SheetHeader>
                  <SheetTitle className="pr-8 text-base leading-snug">{selectedPromo.name}</SheetTitle>
                  <SheetDescription className="flex items-center gap-2 mt-1">
                    {typeBadge(selectedPromo.type)}
                    <span className="text-muted-foreground">·</span>
                    <span className="text-sm">{selectedPromo.startDate} — {selectedPromo.endDate}</span>
                  </SheetDescription>
                </SheetHeader>

                {/* Excel status row */}
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {excelChip(selectedPromo.excelLoaded)}
                    {selectedPromo.excelLoaded && selectedPromo.excelFileName && (
                      <span className="text-xs text-muted-foreground/70 truncate max-w-[180px]">
                        {selectedPromo.excelFileName}
                        {selectedPromo.excelLoadedAt && ` · ${selectedPromo.excelLoadedAt}`}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    disabled={uploadingId === selectedPromo.id}
                    onClick={() => {
                      if (fileInputRef.current) {
                        fileInputRef.current.dataset.promoId = selectedPromo.id
                        fileInputRef.current.click()
                      }
                    }}
                    className="text-xs px-3 py-1.5 border border-border rounded text-muted-foreground hover:text-foreground hover:bg-muted/40 disabled:opacity-50 flex items-center gap-1"
                  >
                    {uploadingId === selectedPromo.id ? (
                      <span className="inline-block w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : '↑'}
                    {selectedPromo.excelLoaded ? 'Перезагрузить' : 'Загрузить Excel'}
                  </button>
                </div>
              </div>

              {/* Drag-drop zone */}
              <div
                className={`mx-5 mt-4 mb-0 flex-shrink-0 border-2 border-dashed rounded-lg p-4 text-center transition-colors ${
                  dragOverDrawer
                    ? 'border-indigo-500 bg-indigo-500/10'
                    : 'border-border/60 hover:border-border'
                }`}
                onDragOver={(e) => { e.preventDefault(); setDragOverDrawer(true) }}
                onDragLeave={() => setDragOverDrawer(false)}
                onDrop={handleDrawerDrop}
              >
                <p className="text-xs text-muted-foreground/70">
                  Перетащите .xlsx файл с порогами входа
                </p>
              </div>

              {/* SKU list */}
              <div className="flex-1 overflow-auto px-5 pt-4 pb-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium text-foreground">
                    SKU в акции
                    {drawerSkus.length > 0 && (
                      <span className="ml-1.5 text-muted-foreground font-normal">({drawerSkus.length})</span>
                    )}
                  </span>
                  <a
                    href="https://seller.wildberries.ru/discount-and-prices/promotions"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-600 hover:underline"
                  >
                    → Открыть в ЛК WB
                  </a>
                </div>

                {drawerSkusLoading && (
                  <div className="py-8 text-center text-sm text-muted-foreground/60">Загрузка SKU…</div>
                )}

                {!drawerSkusLoading && drawerSkus.length === 0 && (
                  <div className="py-8 text-center text-sm text-muted-foreground/60">
                    {selectedPromo.excelLoaded
                      ? 'Нет SKU в этой акции.'
                      : 'Загрузите Excel чтобы увидеть пороги входа для каждого SKU.'}
                  </div>
                )}

                {!drawerSkusLoading && drawerSkus.length > 0 && (
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">Артикул</th>
                        <th className="pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Цена</th>
                        <th className="pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Порог</th>
                        <th className="pb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-right">Маржа</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drawerSkus.map((sku) => {
                        const threshold = sku.promoThresholdKopecks
                        const marginCell = threshold !== null
                          ? verdictBadge(
                              marginStatusAt(threshold, sku.cogsKopecks, sku.wbCommissionPct, sku.logisticsKopecks),
                              promoMarginPct(sku, threshold),
                            )
                          : <span className="text-muted-foreground/40 text-xs">—</span>
                        return (
                          <tr key={sku.articleId} className="border-b border-border/40">
                            <td className="py-2 pr-2">
                              <div className="font-mono text-xs text-indigo-600 font-semibold">{sku.articleId}</div>
                              <div className="text-xs text-muted-foreground/70 truncate max-w-[130px]">{sku.name}</div>
                            </td>
                            <td className="py-2 text-right text-xs font-mono font-semibold">
                              {formatRub(sku.currentPriceKopecks)}
                            </td>
                            <td className="py-2 text-right text-xs font-mono text-muted-foreground">
                              {threshold !== null ? formatRub(threshold) : '—'}
                            </td>
                            <td className="py-2 text-right">{marginCell}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
