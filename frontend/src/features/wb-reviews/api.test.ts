import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiData, apiRequest } from '@/lib/api'
import {
  approveWbReviewDraft,
  generateWbReviewDraft,
  generateWbReviewDraftsBatch,
  listWbReviewFeedbacks,
  mapWbFeedbackToVellaReview,
  mergeWbDraftIntoVellaReview,
  requestWbReviewSend,
  syncWbReviewFeedbacks,
  updateWbReviewSyncSettings,
} from './api'

vi.mock('@/lib/api', () => ({
  apiData: vi.fn(),
  apiRequest: vi.fn(),
}))

const mockedApiData = vi.mocked(apiData)
const mockedApiRequest = vi.mocked(apiRequest)

describe('wb reviews api', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads feedbacks from backend without mock fixtures', async () => {
    mockedApiRequest.mockResolvedValueOnce({ items: [], total: 0, limit: 100, offset: 0, timestamp: 'now' })

    await listWbReviewFeedbacks('token')

    expect(mockedApiRequest).toHaveBeenCalledWith('/api/v1/wb-reviews/feedbacks?limit=100&offset=0', {
      headers: { Authorization: 'Bearer token' },
      cache: 'no-store',
    })
  })

  it('uses backend sync and draft endpoints for review actions', async () => {
    mockedApiData.mockResolvedValue({})

    await syncWbReviewFeedbacks('token')
    await generateWbReviewDraft('token', 'feedback-1')
    await generateWbReviewDraftsBatch('token', [{ feedbackId: 'feedback-1', brandVoiceId: 'anomie-studio' }])
    await approveWbReviewDraft('token', 'draft-1', 'looks good')
    await requestWbReviewSend('token', 'draft-1')
    await updateWbReviewSyncSettings('token', { enabled: true, intervalMinutes: 12, tokenType: 'base', unansweredOnly: true, take: 200, lookbackDays: 14, aiPrompt: 'Отвечай на отзывы WB.' })

    expect(mockedApiData).toHaveBeenNthCalledWith(1, '/api/v1/wb-reviews/sync', {
      method: 'POST',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ scenario: 'complete', take: 500, skip: 0, order: 'dateDesc' }),
    })
    expect(mockedApiData).toHaveBeenNthCalledWith(2, '/api/v1/wb-reviews/drafts/generate', {
      method: 'POST',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ feedbackId: 'feedback-1', brandVoiceId: 'wb-default', regenerate: true }),
    })
    expect(mockedApiData).toHaveBeenNthCalledWith(3, '/api/v1/wb-reviews/drafts/generate-batch', {
      method: 'POST',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ items: [{ feedbackId: 'feedback-1', brandVoiceId: 'anomie-studio' }], regenerate: true }),
    })
    expect(mockedApiData).toHaveBeenNthCalledWith(4, '/api/v1/wb-reviews/drafts/draft-1/approve', {
      method: 'POST',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ approvalRef: 'frontend-approval', reason: 'looks good' }),
    })
    expect(mockedApiData).toHaveBeenNthCalledWith(5, '/api/v1/wb-reviews/drafts/draft-1/send', {
      method: 'POST',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ dryRun: true, reason: 'frontend draft-only smoke' }),
    })
    expect(mockedApiData).toHaveBeenNthCalledWith(6, '/api/v1/wb-reviews/sync-settings', {
      method: 'PUT',
      headers: { Authorization: 'Bearer token' },
      body: JSON.stringify({ enabled: true, intervalMinutes: 12, tokenType: 'base', unansweredOnly: true, take: 200, lookbackDays: 14, aiPrompt: 'Отвечай на отзывы WB.' }),
    })
  })

  it('maps backend feedbacks and draft-only answers into the reviews page model', () => {
    const row = mapWbFeedbackToVellaReview({
      feedbackId: 'safe-review-001',
      nmId: 218094212,
      brandName: 'Anomie studio',
      productName: 'Футболка белая, принт Space Cat',
      createdDate: new Date(Date.now() - 10 * 60_000).toISOString(),
      text: 'Принт огонь',
      pros: '',
      cons: '',
      answerText: null,
      isAnswered: false,
      rating: 5,
      syncedAt: new Date().toISOString(),
      sourceStatus: 'fresh',
    })

    expect(row).toMatchObject({
      id: 'safe-review-001',
      brand: 'Anomie studio',
      rating: 5,
      status: 'new',
      risk: 'low',
    })
    expect(row.draftId).toBeUndefined()

    const withDraft = mergeWbDraftIntoVellaReview(row, {
      draftId: 'draft-1',
      feedbackId: 'safe-review-001',
      rating: 5,
      brandVoiceId: 'wb-default',
      approvalState: 'not_required',
      approvalActorId: null,
      approvedAt: null,
      externalSendAllowed: false,
      sendState: 'draft_only',
      generatedText: 'Спасибо за отзыв!',
      moderation: { state: 'clean', reasons: [], matchedRuleIds: [], matchedStopTopicIds: [] },
      promptTraceId: null,
      cacheMetrics: null,
      createdByActorId: 'u1',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    })

    expect(withDraft).toMatchObject({
      draftId: 'draft-1',
      status: 'pending_review',
      draft: 'Спасибо за отзыв!',
      reason: 'Черновик готов; отправка в WB отключена',
    })
  })

  it('keeps latest backend draft when feedbacks are reloaded', () => {
    const row = mapWbFeedbackToVellaReview({
      feedbackId: 'safe-review-002',
      nmId: 218094212,
      brandName: 'Anomie studio',
      productName: 'Футболка белая',
      createdDate: new Date().toISOString(),
      text: 'Классная футболка',
      pros: '',
      cons: '',
      answerText: null,
      isAnswered: false,
      rating: 5,
      syncedAt: new Date().toISOString(),
      sourceStatus: 'fresh',
      latestDraft: {
        draftId: 'draft-2',
        rating: 5,
        brandVoiceId: 'anomie-studio',
        templateId: null,
        approvalState: 'required',
        sendState: 'draft_only',
        generatedText: 'Спасибо за отзыв, рады, что футболка понравилась.',
        moderationState: 'manual_review',
        moderationReasons: ['manual queue'],
        updatedAt: new Date().toISOString(),
      },
    })

    expect(row).toMatchObject({
      draftId: 'draft-2',
      status: 'pending_review',
      draft: 'Спасибо за отзыв, рады, что футболка понравилась.',
      reason: 'Черновик готов; отправка в WB отключена',
    })
  })
})
