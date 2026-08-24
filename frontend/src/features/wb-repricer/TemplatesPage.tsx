import { useEffect, useMemo, useState } from 'react'
import { computePMinKopecks } from './pricing'
import { formatRub } from '../../lib/formatRub'

type TypeKey = 'F' | 'H' | 'L'

interface TypeTemplate {
  cogsKopecks: number
  logisticsKopecks: number
  minMarginPct: number
  pMaxKopecks: number
}

interface TemplatesData {
  globalCommissionPct: number
  types: Record<TypeKey, TypeTemplate>
  skuCountByType: Record<TypeKey, number>
}

const TYPE_META: Record<TypeKey, { label: string; emoji: string; color: string }> = {
  F: { label: 'Футболки', emoji: '👕', color: 'indigo' },
  H: { label: 'Худи', emoji: '🧥', color: 'violet' },
  L: { label: 'Лонгсливы', emoji: '🧣', color: 'blue' },
}

function Field({
  label,
  value,
  onChange,
  suffix,
  hint,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  suffix: string
  hint?: string
}) {
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">{label}</div>
      <div className="flex items-center gap-1.5">
        <input
          type="number"
          value={value}
          min={0}
          step={suffix === '₽' ? 10 : 1}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full border border-border rounded px-2 py-1.5 text-sm font-mono focus:border-indigo-500 focus:outline-none"
        />
        <span className="text-xs text-muted-foreground/70 flex-shrink-0">{suffix}</span>
      </div>
      {hint && <div className="text-xs text-muted-foreground/70 mt-0.5">{hint}</div>}
    </div>
  )
}

function TypeCard({
  typeKey,
  template,
  commission,
  skuCount,
  onChange,
  onSave,
  onApply,
  saving,
}: {
  typeKey: TypeKey
  template: TypeTemplate
  commission: number
  skuCount: number
  onChange: (t: TypeTemplate) => void
  onSave: () => void
  onApply: () => void
  saving: boolean
}) {
  const meta = TYPE_META[typeKey]

  const pMin = useMemo(
    () =>
      computePMinKopecks(
        template.cogsKopecks,
        commission,
        template.logisticsKopecks,
        template.minMarginPct,
      ),
    [template, commission],
  )

  const pMinValid = Number.isFinite(pMin) && pMin < template.pMaxKopecks

  return (
    <div className="bg-card rounded-lg border border-border flex flex-col">
      {/* Header */}
      <div className={`px-5 py-3 border-b border-border/60 flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <span className="text-xl">{meta.emoji}</span>
          <div>
            <div className="font-semibold text-foreground text-sm">{meta.label}</div>
            <div className="text-xs text-muted-foreground/70">{skuCount} артикулов</div>
          </div>
        </div>
        <span className="text-xs font-mono font-bold text-muted-foreground/70">{typeKey}*BT_*</span>
      </div>

      {/* Fields */}
      <div className="px-5 py-4 grid grid-cols-2 gap-4">
        <Field
          label="Себестоимость"
          value={template.cogsKopecks / 100}
          onChange={(v) => onChange({ ...template, cogsKopecks: Math.round(v * 100) })}
          suffix="₽"
          hint="производство 1 шт."
        />
        <Field
          label="Логистика WB"
          value={template.logisticsKopecks / 100}
          onChange={(v) => onChange({ ...template, logisticsKopecks: Math.round(v * 100) })}
          suffix="₽"
          hint="доставка до покупателя"
        />
        <Field
          label="Целевая маржа"
          value={template.minMarginPct}
          onChange={(v) => onChange({ ...template, minMarginPct: v })}
          suffix="%"
          hint="минимальная прибыль"
        />
        <Field
          label="Макс. цена (P_max)"
          value={template.pMaxKopecks / 100}
          onChange={(v) => onChange({ ...template, pMaxKopecks: Math.round(v * 100) })}
          suffix="₽"
          hint="потолок алгоритма"
        />
      </div>

      {/* P_min preview */}
      <div className={`mx-5 mb-4 px-3 py-2 rounded border text-sm ${pMinValid ? 'bg-indigo-500/10 border-indigo-500/20' : 'bg-red-500/10 border-red-500/30'}`}>
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">P_min</span>
          <span className={`font-mono font-semibold ${pMinValid ? 'text-indigo-600 dark:text-indigo-400' : 'text-red-600'}`}>
            {pMinValid ? formatRub(pMin) : '⚠ невалидно'}
          </span>
        </div>
        {!pMinValid && Number.isFinite(pMin) && (
          <div className="text-xs text-red-600 mt-0.5">P_min ({formatRub(pMin)}) превышает P_max</div>
        )}
        {!Number.isFinite(pMin) && (
          <div className="text-xs text-red-600 mt-0.5">Комиссия + маржа ≥ 100%</div>
        )}
      </div>

      {/* Actions */}
      <div className="px-5 pb-4 flex gap-2 mt-auto">
        <button
          type="button"
          onClick={onSave}
          disabled={saving || !pMinValid}
          className="flex-1 px-3 py-1.5 bg-indigo-500 text-white text-sm rounded hover:bg-indigo-600 disabled:bg-muted disabled:text-muted-foreground/70 font-medium"
        >
          {saving ? 'Сохранение…' : 'Сохранить шаблон'}
        </button>
        <button
          type="button"
          onClick={onApply}
          disabled={saving || !pMinValid}
          className="px-3 py-1.5 border border-border text-foreground text-sm rounded hover:bg-muted/40 disabled:opacity-40"
          title={`Применить ко всем ${meta.label}`}
        >
          Применить →
        </button>
      </div>
    </div>
  )
}

export function TemplatesPage() {
  const [data, setData] = useState<TemplatesData | null>(null)
  const [commission, setCommission] = useState(25)
  const [types, setTypes] = useState<Record<TypeKey, TypeTemplate> | null>(null)
  const [skuCounts, setSkuCounts] = useState<Record<TypeKey, number>>({ F: 0, H: 0, L: 0 })
  const [saving, setSaving] = useState<TypeKey | null>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [applyModal, setApplyModal] = useState<TypeKey | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/v1/wb-repricer/templates', { signal: controller.signal })
      .then((r) => r.json())
      .then((d: TemplatesData) => {
        setData(d)
        setCommission(d.globalCommissionPct)
        setTypes(d.types)
        setSkuCounts(d.skuCountByType)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        showToast('Ошибка загрузки шаблонов')
      })
    return () => controller.abort()
  }, [])

  function showToast(msg: string) {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  async function saveTemplate(typeKey: TypeKey) {
    if (!types) return
    setSaving(typeKey)
    try {
      await fetch('/api/v1/wb-repricer/templates', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ globalCommissionPct: commission, types }),
      })
      setSaving(null)
      showToast(`Шаблон «${TYPE_META[typeKey].label}» сохранён`)
    } catch {
      showToast('Ошибка: не удалось сохранить шаблон')
      setSaving(null)
    }
  }

  async function applyTemplate(typeKey: TypeKey) {
    setApplyModal(null)
    setSaving(typeKey)
    try {
      const res = await fetch(`/api/v1/wb-repricer/templates/${typeKey}/apply`, { method: 'POST' })
      const d = (await res.json()) as { updated: number }
      setSaving(null)
      showToast(`Обновлено ${d.updated} артикулов ${TYPE_META[typeKey].label}`)
    } catch {
      showToast('Ошибка: не удалось применить шаблон')
      setSaving(null)
    }
  }

  if (!data || !types) {
    return (
      <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-5 animate-pulse">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-48 rounded-lg bg-muted" />
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-foreground text-background text-sm px-4 py-2 rounded-lg shadow-lg">
          {toast}
        </div>
      )}

      {/* Apply modal */}
      {applyModal && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg shadow-lg max-w-md w-full">
            <div className="px-6 py-4 border-b border-border">
              <div className="font-semibold text-foreground">Применить шаблон {TYPE_META[applyModal].label}?</div>
            </div>
            <div className="px-6 py-4 text-sm text-muted-foreground space-y-2">
              <p>
                Шаблон будет применён к <strong>{skuCounts[applyModal]} артикулам</strong> типа{' '}
                {TYPE_META[applyModal].label}.
              </p>
              <p className="text-xs text-muted-foreground/70">
                Артикулы с индивидуальными настройками будут обновлены. Это действие можно
                откорректировать вручную для каждого артикула.
              </p>
            </div>
            <div className="px-6 py-4 border-t border-border flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setApplyModal(null)}
                className="px-4 py-2 border border-border text-foreground rounded text-sm hover:bg-muted/40"
              >
                Отмена
              </button>
              <button
                type="button"
                onClick={() => applyTemplate(applyModal)}
                className="px-4 py-2 bg-indigo-500 text-white rounded text-sm hover:bg-indigo-600 font-medium"
              >
                Применить ко всем {TYPE_META[applyModal].label}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Глобальная комиссия */}
      <div className="bg-card rounded-lg border border-border px-6 py-4 mb-6 flex items-center gap-6">
        <div className="flex-1">
          <div className="font-semibold text-sm text-foreground">Комиссия WB</div>
          <div className="text-xs text-muted-foreground/70 mt-0.5">
            Единая для всех товаров. Меняется при переходе в другую категорию WB.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={commission}
            min={0}
            max={50}
            onChange={(e) => setCommission(Number(e.target.value))}
            className="w-20 border border-border rounded px-2 py-1.5 text-sm font-mono text-right focus:border-indigo-500 focus:outline-none"
          />
          <span className="text-sm text-muted-foreground">%</span>
        </div>
      </div>

      {/* Карточки типов */}
      <div className="grid grid-cols-3 gap-5">
        {(['F', 'H', 'L'] as TypeKey[]).map((typeKey) => (
          <TypeCard
            key={typeKey}
            typeKey={typeKey}
            template={types[typeKey]}
            commission={commission}
            skuCount={skuCounts[typeKey]}
            onChange={(t) => setTypes((prev) => prev ? { ...prev, [typeKey]: t } : prev)}
            onSave={() => saveTemplate(typeKey)}
            onApply={() => setApplyModal(typeKey)}
            saving={saving === typeKey}
          />
        ))}
      </div>

      <div className="mt-5 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-700 dark:text-amber-300">
        <strong>Как это работает:</strong> шаблоны задают дефолтные значения для каждого типа товара.
        Кнопка «Применить →» обновит все артикулы этого типа. Отдельные карточки SKU могут иметь
        индивидуальные переопределения.
      </div>
    </div>
  )
}
