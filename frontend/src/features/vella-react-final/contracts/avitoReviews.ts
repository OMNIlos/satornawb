export type AvitoReviewBrandSettings = {
  brandId: string
  brandLabel: string
  voicePreset: 'market_neutral' | 'warm_brand' | 'jason_statham_meme' | 'custom'
  formality: 1 | 2 | 3 | 4 | 5
  warmth: 1 | 2 | 3 | 4 | 5
  length: 'short' | 'medium' | 'long_for_negative'
  emojiPolicy: 'never' | 'match_customer_positive_only' | 'rare_positive'
  languagePolicy: 'match_review' | 'ru_only'
  publishDelayMinutes: 15 | 30 | 60 | 1440
  ownerUserId: string
  customInstructions: string
  stopTopics: string[]
}

export type AvitoReviewRow = {
  id: string
  author: string
  rating: 1 | 2 | 3 | 4 | 5
  accountLabel: string
  brandLabel: string
  listingTitle: string
  reviewText: string
  risk: 'low' | 'medium' | 'high'
  status: 'pending' | 'scheduled' | 'blocked'
  aiStatus: string
  answerPreview: string
  ageLabel: string
}

export function requiresHumanApproval(row: Pick<AvitoReviewRow, 'rating' | 'risk' | 'reviewText'>, stopTopics: string[]) {
  const text = row.reviewText.toLowerCase()
  return row.rating <= 3 || row.risk === 'high' || stopTopics.some((topic) => text.includes(topic.toLowerCase()))
}
