import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function AuthPageFrame({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-md flex-col justify-center">
        <Link to="/wb/repricer" className="mb-8 text-sm font-semibold text-slate-300">
          Satorna
        </Link>
        <section className="rounded-2xl border border-white/10 bg-white/[0.04] p-6 shadow-2xl">
          <h1 className="text-2xl font-semibold tracking-normal">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-slate-400">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </section>
      </div>
    </main>
  )
}
