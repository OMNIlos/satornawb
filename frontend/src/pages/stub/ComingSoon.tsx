import { useLocation } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { findNavItemByPath } from '@/config/navigation'

export function ComingSoon() {
  const { pathname } = useLocation()
  const item = findNavItemByPath(pathname)
  const Icon = item?.icon ?? Sparkles

  return (
    <div className="flex h-full min-h-[60vh] items-center justify-center p-8">
      <div className="max-w-md text-center space-y-4">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
          <Icon className="size-6 text-muted-foreground" />
        </div>
        <h1 className="text-xl font-semibold text-foreground">
          {item?.label ?? 'Скоро'}
        </h1>
        <p className="text-sm text-muted-foreground">
          Этот раздел в разработке. Откроется в одной из ближайших фаз согласно утверждённому ТЗ.
        </p>
        <p className="font-mono text-[11px] text-muted-foreground/60">{pathname}</p>
      </div>
    </div>
  )
}
