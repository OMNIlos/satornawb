type ReportLoadState = { status: string }

export function retainReadyReportWhileRefreshing<TState extends ReportLoadState>(current: TState): TState {
  return current.status === 'ready' ? current : ({ status: 'loading' } as TState)
}
