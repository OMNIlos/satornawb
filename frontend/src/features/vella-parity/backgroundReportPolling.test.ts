import { describe, expect, it } from 'vitest'

import { shouldPollBackgroundReportJob } from './backgroundReportPolling'

describe('background report polling', () => {
  it('polls only active jobs up to the bounded twenty minute allowance', () => {
    expect(shouldPollBackgroundReportJob({ state: 'queued' }, 0)).toBe(true)
    expect(shouldPollBackgroundReportJob({ state: 'running' }, 150)).toBe(true)
    expect(shouldPollBackgroundReportJob({ state: 'running' }, 599)).toBe(true)
    expect(shouldPollBackgroundReportJob({ state: 'completed' }, 0)).toBe(false)
    expect(shouldPollBackgroundReportJob({ state: 'waiting_1c' }, 0)).toBe(false)
    expect(shouldPollBackgroundReportJob({ state: 'running' }, 600)).toBe(false)
  })
})
