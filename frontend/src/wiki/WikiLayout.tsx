import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ROUTES } from '@/lib/routes'

export type WikiSection = { id: string; title: string }

const MODULE_LINKS = [
  { label: 'WB Репрайсер', path: ROUTES.wiki.wbRepricer },
  { label: 'Ликвидация', path: ROUTES.wiki.liquidation },
  { label: 'Акции WB', path: ROUTES.wiki.promotions },
  { label: 'Алгоритм', path: ROUTES.wiki.algorithm },
  { label: 'Шаблоны', path: ROUTES.wiki.templates },
]

interface WikiLayoutProps {
  title: string
  subtitle?: string
  sections: WikiSection[]
  activeModule: string
  children: React.ReactNode
}

export function WikiLayout({ title, subtitle, sections, activeModule, children }: WikiLayoutProps) {
  const navigate = useNavigate()
  const [activeId, setActiveId] = useState<string>(sections[0]?.id ?? '')
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    const sectionIds = sections.map((s) => s.id)

    observerRef.current?.disconnect()
    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
            break
          }
        }
      },
      { rootMargin: '-20% 0px -70% 0px', threshold: 0 },
    )

    sectionIds.forEach((id) => {
      const el = document.getElementById(id)
      if (el) observerRef.current?.observe(el)
    })

    return () => observerRef.current?.disconnect()
  }, [sections])

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-border bg-background">
        <Button
          variant="ghost"
          size="sm"
          className="h-8 gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
          onClick={() => navigate(-1)}
        >
          <ChevronLeft className="size-4" />
          Назад
        </Button>
        <div className="h-4 w-px bg-border" />
        <div>
          <h1 className="text-base font-semibold text-foreground leading-none">{title}</h1>
          {subtitle && <p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 shrink-0 border-r border-border overflow-y-auto sticky top-0 h-full">
          <div className="p-4">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 mb-2">
              На этой странице
            </p>
            <nav className="space-y-0.5">
              {sections.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => scrollTo(s.id)}
                  className={[
                    'w-full text-left text-sm px-2 py-1.5 rounded-md transition-colors',
                    activeId === s.id
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'text-muted-foreground hover:text-foreground hover:bg-muted/50',
                  ].join(' ')}
                >
                  {s.title}
                </button>
              ))}
            </nav>

            <div className="my-4 border-t border-border" />

            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60 mb-2">
              Другие модули
            </p>
            <nav className="space-y-0.5">
              {MODULE_LINKS.filter((l) => l.path !== activeModule).map((l) => (
                <button
                  key={l.path}
                  type="button"
                  onClick={() => navigate(l.path)}
                  className="w-full text-left text-sm px-2 py-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                >
                  {l.label}
                </button>
              ))}
            </nav>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">
          <article className="max-w-3xl mx-auto px-8 py-8 pb-20">{children}</article>
        </main>
      </div>
    </div>
  )
}

export function WikiSection({
  id,
  title,
  children,
}: {
  id: string
  title: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="mb-10 scroll-mt-6">
      <h2 className="text-lg font-semibold text-foreground mb-4 pb-2 border-b border-border">{title}</h2>
      {children}
    </section>
  )
}
