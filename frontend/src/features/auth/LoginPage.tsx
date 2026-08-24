import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/lib/api'
import { AuthPageFrame } from './AuthPageFrame'
import { useAuth } from './authContext'

function loginErrorMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    return 'Неверный email или пароль'
  }
  if (error instanceof TypeError) {
    return 'Не удалось подключиться к серверу. Проверьте интернет и попробуйте еще раз.'
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Не удалось войти'
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const target =
    typeof location.state === 'object' &&
    location.state &&
    'from' in location.state &&
    typeof location.state.from === 'string'
      ? location.state.from
      : '/wb/repricer'

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login({ email, password })
      navigate(target, { replace: true })
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthPageFrame title="Вход" subtitle="Войдите в рабочую область Огни, чтобы открыть репрайсер и настройки.">
      <form className="grid gap-4" onSubmit={handleSubmit}>
        <label className="grid gap-1 text-sm">
          <span className="text-slate-300">Email</span>
          <input className="rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-slate-100 outline-none focus:border-sky-400" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label className="grid gap-1 text-sm">
          <span className="text-slate-300">Пароль</span>
          <input className="rounded-lg border border-white/10 bg-white/10 px-3 py-2 text-slate-100 outline-none focus:border-sky-400" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        {error ? <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{error}</div> : null}
        <button className="rounded-lg bg-sky-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-60" type="submit" disabled={submitting}>
          {submitting ? 'Входим...' : 'Войти'}
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-400">
        Нет аккаунта? <Link className="text-sky-300" to="/auth/register">Зарегистрироваться</Link>
      </p>
    </AuthPageFrame>
  )
}
