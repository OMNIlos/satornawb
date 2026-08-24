import { useState } from 'react'
import { CalendarDays } from 'lucide-react'
import type { DatePreset, DateRange } from './types'

const PRESETS: Array<{ value: DatePreset; label: string }> = [
  { value: '1d', label: '1 день' },
  { value: '7d', label: '7 дней' },
  { value: '14d', label: '14 дней' },
  { value: '30d', label: '30 дней' },
]

export function defaultDateRange(): DateRange {
  return { preset: '7d', from: '2026-05-01', to: '2026-05-07' }
}

function rangeForPreset(preset: DatePreset): DateRange {
  if (preset === 'custom') return defaultDateRange()
  const days = preset === '1d' ? 1 : preset === '14d' ? 14 : preset === '30d' ? 30 : 7
  const to = new Date('2026-05-07T00:00:00.000Z')
  const from = new Date(to)
  from.setUTCDate(to.getUTCDate() - days + 1)
  const iso = (d: Date) => d.toISOString().slice(0, 10)
  return { preset, from: iso(from), to: iso(to) }
}

export function DateRangeControl({
  value,
  onChange,
}: {
  value: DateRange
  onChange: (value: DateRange) => void
}) {
  const [customOpen, setCustomOpen] = useState(value.preset === 'custom')

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="inline-flex rounded-md border border-border bg-background p-0.5">
        {PRESETS.map((preset) => (
          <button
            key={preset.value}
            type="button"
            onClick={() => {
              setCustomOpen(false)
              onChange(rangeForPreset(preset.value))
            }}
            className={[
              'px-2.5 py-1 text-sm rounded transition-colors',
              value.preset === preset.value ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted/60',
            ].join(' ')}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <button
        type="button"
        onClick={() => setCustomOpen((open) => !open)}
        className={[
          'inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm',
          value.preset === 'custom' ? 'border-primary/40 text-primary bg-primary/10' : 'border-border text-foreground bg-background hover:bg-muted/60',
        ].join(' ')}
      >
        <CalendarDays className="size-4" />
        {value.from} - {value.to}
      </button>

      {customOpen ? (
        <div className="flex items-center gap-2 rounded-md border border-border bg-background px-2 py-1">
          <input
            type="date"
            value={value.from}
            onChange={(event) => onChange({ ...value, preset: 'custom', from: event.target.value })}
            className="bg-transparent text-sm outline-none"
          />
          <span className="text-muted-foreground">-</span>
          <input
            type="date"
            value={value.to}
            onChange={(event) => onChange({ ...value, preset: 'custom', to: event.target.value })}
            className="bg-transparent text-sm outline-none"
          />
        </div>
      ) : null}
    </div>
  )
}
