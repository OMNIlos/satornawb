import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { BarChart3, MessageSquare, Package } from 'lucide-react'
import { cn } from '@/lib/utils'

export const avitoAccounts = [
  'Bless T · Москва',
  'Anomie Studio · Москва',
  'Bless T · Улица',
  'Anomie Studio · Скидки',
  'Bless T · Outlet',
]

export function AvitoModuleTabs() {
  const tabs = [
    { label: 'Обзор', path: '/avito', icon: BarChart3 },
    { label: 'Сообщения', path: '/avito/chats', icon: MessageSquare },
    { label: 'Объявления', path: '/avito/listings', icon: Package },
  ]

  return (
    <nav className="flex gap-1 overflow-x-auto rounded-lg border border-slate-200 bg-white p-1 shadow-sm" aria-label="Разделы Авито">
      {tabs.map((tab) => (
        <NavLink
          className={({ isActive }) =>
            cn(
              'inline-flex h-9 shrink-0 items-center gap-2 rounded-md px-3 text-sm font-semibold transition',
              isActive ? 'bg-slate-950 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-950',
            )
          }
          end={tab.path === '/avito'}
          key={tab.path}
          to={tab.path}
        >
          <tab.icon className="size-4" aria-hidden="true" />
          {tab.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function AvitoPageShell({
  title,
  subtitle,
  status,
  children,
}: {
  title: string
  subtitle: string
  status?: string
  children: ReactNode
}) {
  return (
    <div className="min-h-full overflow-auto bg-slate-50">
      <section className="mx-auto flex w-full max-w-[1320px] flex-col gap-4 px-5 py-4">
        <header className="flex flex-col gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">Авито</p>
              <h1 className="mt-1 text-xl font-extrabold tracking-tight text-slate-950">{title}</h1>
              <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{subtitle}</p>
            </div>
            {status && (
              <span className="inline-flex w-fit items-center rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800">
                {status}
              </span>
            )}
          </div>
          <AvitoModuleTabs />
        </header>
        {children}
      </section>
    </div>
  )
}

export function AvitoKpiCard({
  label,
  value,
  detail,
  tone = 'slate',
}: {
  label: string
  value: string
  detail: string
  tone?: 'slate' | 'blue' | 'green' | 'amber' | 'red'
}) {
  const tones = {
    slate: 'border-slate-200 text-slate-950',
    blue: 'border-blue-200 text-blue-700',
    green: 'border-emerald-200 text-emerald-700',
    amber: 'border-amber-200 text-amber-700',
    red: 'border-red-200 text-red-700',
  }

  return (
    <div className={cn('rounded-lg border bg-white px-3 py-2.5 shadow-sm', tones[tone])}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-extrabold leading-none">{value}</div>
      <div className="mt-1 text-xs font-medium text-slate-500">{detail}</div>
    </div>
  )
}

export function AvitoChip({
  active,
  children,
  onClick,
}: {
  active?: boolean
  children: ReactNode
  onClick?: () => void
}) {
  return (
    <button
      className={cn(
        'inline-flex h-8 shrink-0 items-center rounded-full border px-3 text-xs font-semibold transition',
        active ? 'border-slate-950 bg-slate-950 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50',
      )}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
  )
}

export function AccountBadge({ name }: { name: string }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700 shadow-sm">
      <span className="size-2 rounded-full bg-blue-500" aria-hidden="true" />
      {name}
    </span>
  )
}
