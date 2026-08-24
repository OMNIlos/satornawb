export type ReviewPromptPlatform = 'wb' | 'avito' | 'both'
export type ReviewOrderState = 'buyout' | 'return' | 'unknown'

export type ReviewPromptContext = {
  rating: number
  hasText: boolean
  hasPhoto: boolean
  text: string
  orderState?: ReviewOrderState
}

export type ReviewPromptRule = {
  id: string
  title: string
  platform: ReviewPromptPlatform
  ratingFrom: number
  ratingTo: number
  hasText?: boolean
  hasPhoto?: boolean
  orderState?: ReviewOrderState
  keywords?: string[]
  prompt: string
  example: string
  isActive: boolean
}

export type ReviewPromptMatrix = {
  version: 1
  rules: ReviewPromptRule[]
  quotes: string[]
}

export const REVIEW_PROMPT_MATRIX_STORAGE_KEY = 'vella:reviews-prompt-matrix:v1'

export const DEFAULT_REVIEW_QUOTES = [
  '«Шли мы как-то всемером - я и мой друг-шестерка.»',
  '«Если перед тобой закрылась одна дверь, просто открой ее, ведь именно так работают двери.»',
  '«Позвоночник знаешь? Я позвонил.»',
  '«Взял нож - режь, взял дошик - ешь.»',
  '«Я не решаю проблемы - я их перезагружаю... кувалдой.»',
]

export const DEFAULT_REVIEW_PROMPT_MATRIX: ReviewPromptMatrix = {
  version: 1,
  quotes: DEFAULT_REVIEW_QUOTES,
  rules: [
    {
      id: 'wrong_item',
      title: 'приехало не то',
      platform: 'both',
      ratingFrom: 1,
      ratingTo: 5,
      keywords: ['не то', 'другой товар', 'пересорт', 'перепутали'],
      prompt: 'Обращение по имени, сожаление в связи со сложившейся ситуацией, просьба не занижать рейтинг и оценивать только качество товара, так как это пересорт не по вине продавца.',
      example: 'Здравствуйте! Нам очень жаль, что вам доставили не тот товар. Такое иногда случается, если предыдущий покупатель перепутал товары и пакеты. Вы можете оформить возврат и перезаказать товар заново. В отзывах просим учитывать качество товара и не занижать оценку из-за подобных ситуаций.',
      isActive: true,
    },
    {
      id: 'print_failed',
      title: 'принт отвалился',
      platform: 'both',
      ratingFrom: 1,
      ratingTo: 5,
      keywords: ['принт', 'отвалился', 'стерся', 'потрескался', 'слез'],
      prompt: 'Обращение по имени, выразить сожаление в связи с тем, что вещь потеряла первоначальный вид, сообщить о том, что в карточке товара указаны рекомендации по уходу за вещью и их важно соблюдать.',
      example: 'Здравствуйте! Нам жаль, что вещь потеряла первоначальный вид. В карточке товара указаны рекомендации по уходу: при их соблюдении принт может прослужить больше 50 стирок. Пожалуйста, соблюдайте эти рекомендации.',
      isActive: true,
    },
    {
      id: 'five_text_photo',
      title: 'отзыв 5* с текстом и фото',
      platform: 'both',
      ratingFrom: 5,
      ratingTo: 5,
      hasText: true,
      hasPhoto: true,
      prompt: 'цитата Стэтхэма. Ответ должен быть дружелюбным, с приветствием, благодарностью за отзыв и одной случайной цитатой из одобренного списка.',
      example: 'Здравствуйте, Джейсон Стэтхем оценил ваш отзыв и решил подарить вам одну из своих цитат: "если тебе где-то не рады в рваных носках, то и в целых туда идти не стоит"',
      isActive: true,
    },
    {
      id: 'five_photo',
      title: 'отзыв 5* с фото',
      platform: 'both',
      ratingFrom: 5,
      ratingTo: 5,
      hasText: false,
      hasPhoto: true,
      prompt: 'Приветствие по имени, благодарность за высокую оценку, покупку и выбор бренда. Поблагодарить за фото. Призыв добавить бренд в Избранное, чтобы не пропустить новинки.',
      example: 'Здравствуйте! Огромное спасибо за такие крутые фотографии. Нам очень приятно, что наша вещь стала частью вашего образа. Добавляйте наш бренд в избранное, чтобы первыми видеть новинки.',
      isActive: true,
    },
    {
      id: 'five_text',
      title: 'отзыв 5* с текстом',
      platform: 'both',
      ratingFrom: 5,
      ratingTo: 5,
      hasText: true,
      hasPhoto: false,
      prompt: 'Приветствие по имени, если имя корректное; если имя содержит мат, политические имена или мусор - обращаться "дорогой покупатель". Благодарность за высокую оценку, уделенное время, покупку и выбор бренда. Призыв добавить бренд в Избранное.',
      example: 'Добрый день! Благодарим за высокую оценку. Рады, что наш товар вам понравился. Носите с удовольствием! Подписывайтесь на наш магазин, чтобы не пропустить скидки и новинки.',
      isActive: true,
    },
    {
      id: 'five_empty',
      title: 'отзыв 5* без комментария',
      platform: 'both',
      ratingFrom: 5,
      ratingTo: 5,
      hasText: false,
      hasPhoto: false,
      prompt: 'Приветствие и обращение по имени, благодарность за положительный отзыв, предложение купить у нас что-то еще из списка рекомендаций менеджера на 30 дней.',
      example: 'Здравствуйте! Спасибо за положительный отзыв! Носите с удовольствием. Добавляйте наш бренд в избранное и следите за обновлениями ассортимента и скидками!',
      isActive: true,
    },
    {
      id: 'four_star',
      title: 'отзыв 4*',
      platform: 'both',
      ratingFrom: 4,
      ratingTo: 4,
      prompt: 'Приветствие по имени, благодарность за уделение времени на отзыв, сообщить что учтем нюансы на будущее, пожелать хороших покупок в магазине.',
      example: 'Здравствуйте! Благодарим вас за обратную связь. Нам жаль, что товар не оправдал ваши ожидания на все 100%. Мы обязательно передадим замечание в отдел производства, чтобы стать еще лучше.',
      isActive: true,
    },
    {
      id: 'low_return',
      title: 'отзыв 3*2*1* (отказ и возврат)',
      platform: 'both',
      ratingFrom: 1,
      ratingTo: 3,
      orderState: 'return',
      keywords: ['возврат', 'отказ', 'вернула', 'вернул', 'не подошло'],
      prompt: 'Обращение по имени, выразить сожаление, что товар не оправдал ожиданий, благодарность за время и сообщение о проблеме, обязательно будем работать над этим в будущем.',
      example: 'Добрый день! Сожалеем, что товар не оправдал ваших ожиданий. Мы обязательно примем меры и учтем вашу обратную связь. Спасибо вам за внимательность!',
      isActive: true,
    },
    {
      id: 'low_buyout',
      title: 'отзыв 3*2*1* (выкуп)',
      platform: 'both',
      ratingFrom: 1,
      ratingTo: 3,
      orderState: 'buyout',
      prompt: 'Обращение по имени, просьба связаться с нами через чат для решения возникшей проблемы.',
      example: 'Благодарим вас за то, что поделились своей проблемой. Мы очень хотим помочь разобраться в ситуации лично и найти решение. Пожалуйста, напишите нам в чат.',
      isActive: true,
    },
  ],
}

export function reviewTextHasPhotoHint(text: string) {
  return /\b(фото|фотк|снимок|картинк|изображени)/i.test(text)
}

function keywordScore(rule: ReviewPromptRule, text: string) {
  const normalized = text.toLocaleLowerCase('ru-RU')
  return (rule.keywords ?? []).filter((keyword) => normalized.includes(keyword.toLocaleLowerCase('ru-RU'))).length
}

function ruleMatches(rule: ReviewPromptRule, context: ReviewPromptContext, platform: ReviewPromptPlatform) {
  if (!rule.isActive) return false
  if (rule.platform !== 'both' && platform !== 'both' && rule.platform !== platform) return false
  if (context.rating < rule.ratingFrom || context.rating > rule.ratingTo) return false
  if (rule.hasText !== undefined && rule.hasText !== context.hasText) return false
  if (rule.hasPhoto !== undefined && rule.hasPhoto !== context.hasPhoto) return false
  if (rule.orderState && rule.orderState !== (context.orderState ?? 'unknown') && keywordScore(rule, context.text) === 0) return false
  if (rule.keywords?.length && keywordScore(rule, context.text) === 0) return false
  return true
}

export function findReviewPromptRule(matrix: ReviewPromptMatrix, context: ReviewPromptContext, platform: ReviewPromptPlatform = 'both') {
  return matrix.rules
    .filter((rule) => ruleMatches(rule, context, platform))
    .sort((left, right) => {
      const keywordDelta = keywordScore(right, context.text) - keywordScore(left, context.text)
      if (keywordDelta) return keywordDelta
      const rightSpecificity = Number(right.hasText !== undefined) + Number(right.hasPhoto !== undefined) + Number(Boolean(right.orderState))
      const leftSpecificity = Number(left.hasText !== undefined) + Number(left.hasPhoto !== undefined) + Number(Boolean(left.orderState))
      return rightSpecificity - leftSpecificity
    })[0]
}

export function buildReviewPromptInstruction({
  matrix,
  context,
  platform,
}: {
  matrix: ReviewPromptMatrix
  context: ReviewPromptContext
  platform: ReviewPromptPlatform
}) {
  const rule = findReviewPromptRule(matrix, context, platform) ?? matrix.rules.find((item) => item.isActive)
  if (!rule) return ''
  const quotes = matrix.quotes.slice(0, 12).join('\n')
  return [
    `Вариант промпта: ${rule.title}`,
    `Площадка: ${platform}`,
    `Условия: рейтинг ${context.rating}, текст ${context.hasText ? 'есть' : 'нет'}, фото ${context.hasPhoto ? 'есть' : 'нет'}, заказ ${context.orderState ?? 'unknown'}`,
    `Инструкция: ${rule.prompt}`,
    `Пример ответа: ${rule.example}`,
    quotes ? `Цитаты:\n${quotes}` : '',
    'Сгенерируй ответ на русском языке. Не обещай компенсации, скидки или действия, которых нет в инструкции. Если имя покупателя выглядит некорректным, обращайся "дорогой покупатель".',
  ].filter(Boolean).join('\n\n')
}

export function normalizeReviewPromptMatrix(value: unknown): ReviewPromptMatrix {
  if (!value || typeof value !== 'object') return DEFAULT_REVIEW_PROMPT_MATRIX
  const maybe = value as Partial<ReviewPromptMatrix>
  if (!Array.isArray(maybe.rules)) return DEFAULT_REVIEW_PROMPT_MATRIX
  return {
    version: 1,
    quotes: Array.isArray(maybe.quotes) ? maybe.quotes.map(String).filter(Boolean) : DEFAULT_REVIEW_QUOTES,
    rules: maybe.rules.map((rule, index) => ({
      ...DEFAULT_REVIEW_PROMPT_MATRIX.rules[index % DEFAULT_REVIEW_PROMPT_MATRIX.rules.length],
      ...rule,
      id: String((rule as Partial<ReviewPromptRule>).id || `custom_${index}`),
      isActive: (rule as Partial<ReviewPromptRule>).isActive !== false,
    })),
  }
}
