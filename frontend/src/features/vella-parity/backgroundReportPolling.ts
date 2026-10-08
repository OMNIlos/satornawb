// Large historical ranges may need hundreds of rate-limited campaign reads.
// Keep polling bounded, but do not stop before a normal collection can finish.
export const BACKGROUND_REPORT_MAX_POLL_ATTEMPTS = 600

type BackgroundReportJob = {
  state?: string | null
}

export function shouldPollBackgroundReportJob(
  job: BackgroundReportJob | null | undefined,
  attempts: number,
) {
  if (attempts >= BACKGROUND_REPORT_MAX_POLL_ATTEMPTS) return false
  return job?.state === 'queued' || job?.state === 'running'
}
