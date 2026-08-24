import { describe, expect, it } from 'vitest'

import {
  DEFAULT_REVIEW_PROMPT_MATRIX,
  buildReviewPromptInstruction,
  findReviewPromptRule,
} from './reviewsPromptMatrix'

describe('reviews prompt matrix', () => {
  it('selects the photo and text 5 star prompt before generic 5 star rules', () => {
    const rule = findReviewPromptRule(DEFAULT_REVIEW_PROMPT_MATRIX, {
      rating: 5,
      hasText: true,
      hasPhoto: true,
      text: 'Отличный лонгслив, фото приложила',
      orderState: 'buyout',
    })

    expect(rule?.id).toBe('five_text_photo')
    expect(rule?.prompt).toContain('цитата')
  })

  it('selects return/refund prompt for low rating returns', () => {
    const rule = findReviewPromptRule(DEFAULT_REVIEW_PROMPT_MATRIX, {
      rating: 2,
      hasText: true,
      hasPhoto: false,
      text: 'оформила возврат',
      orderState: 'return',
    })

    expect(rule?.id).toBe('low_return')
    expect(rule?.title).toContain('отказ')
  })

  it('builds instruction with the matched rule example and quote pool', () => {
    const instruction = buildReviewPromptInstruction({
      matrix: DEFAULT_REVIEW_PROMPT_MATRIX,
      context: {
        rating: 5,
        hasText: true,
        hasPhoto: true,
        text: 'классная футболка',
        orderState: 'buyout',
      },
      platform: 'wb',
    })

    expect(instruction).toContain('отзыв 5* с текстом и фото')
    expect(instruction).toContain('Пример ответа')
    expect(instruction).toContain('Цитаты')
  })
})
