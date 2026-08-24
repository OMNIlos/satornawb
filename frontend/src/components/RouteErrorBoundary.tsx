import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  children: ReactNode
  /** Remounts the boundary when the route changes, so a fixed route recovers on its own. */
  resetKey?: string
}

type State = { error: Error | null }

/**
 * Keeps one failing screen from blanking the whole app.
 *
 * The Vella shell runs a large body of legacy inline DOM code next to React.
 * When a tab unmounts, a queued handler can still reach for a node that is
 * already gone; without a boundary that throw propagates to the root and React
 * unmounts everything, which is what showed up as a white screen that only a
 * reload fixed.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Route crashed', error, info.componentStack)
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null })
    }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div
        role="alert"
        style={{
          minHeight: '60vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
        }}
      >
        <div
          style={{
            maxWidth: 460,
            padding: 24,
            borderRadius: 16,
            background: 'var(--white, #fff)',
            border: '1px solid var(--gray-200, #e5e7eb)',
            color: 'var(--gray-900, #111827)',
          }}
        >
          <h1 style={{ fontSize: 18, margin: '0 0 8px' }}>Раздел не открылся</h1>
          <p style={{ fontSize: 14, lineHeight: 1.5, margin: '0 0 16px', opacity: 0.75 }}>
            Произошла ошибка при отрисовке. Остальные разделы работают — выберите другой пункт меню
            или обновите страницу.
          </p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              border: 0,
              background: 'var(--gray-900, #111827)',
              color: '#fff',
              cursor: 'pointer',
            }}
          >
            Попробовать снова
          </button>
        </div>
      </div>
    )
  }
}
