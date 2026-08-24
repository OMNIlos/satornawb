import { describe, expect, it } from 'vitest'

import { shouldPollBackgroundReportJob } from './backgroundReportPolling'

describe('background report polling', () => {
  it('polls only active jobs until the five minute deadline', () => {
    expect(shouldPollBackgroundReportJob({ state: 'queued' }, 0)).toBe(true)
    expect(shouldPollBackgroundReportJob({ state: 'running' }, 149)).toBe(true)
    expect(shouldPollBackgroundReportJob({ state: 'completed' }, 0)).toBe(false)
    expect(shouldPollBackgroundReportJob({ state: 'waiting_1c' }, 0)).toBe(false)
    expect(shouldPollBackgroundReportJob({ state: 'running' }, 150)).toBe(false)
  })
})
