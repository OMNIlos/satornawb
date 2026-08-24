export const BACKGROUND_REPORT_MAX_POLL_ATTEMPTS = 150

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
