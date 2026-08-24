import type { AuditActor, SkuSettingsResponse } from './schemas'

const mariaActor: AuditActor = { id: 'manager-maria-dudina', name: 'Мария Дудина', role: 'manager' }
const systemActor: AuditActor = { id: 'system', name: 'Система', role: 'system' }
const commentCreatedAt = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString()

const BASE: SkuSettingsResponse = {
  meta: {
    articleId: 'FBBT_42',
    nmId: 185432671,
    name: 'Футболка белая «Логотип», размер L',
    status: 'auto',
    currentPriceKopecks: 129000,
    basketsLast7d: 34,
    basketNorm: 20,
    basketNormSource: 'auto',
    warmupDaysLeft: null,
    lastSavedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    managerId: 'manager-maria-dudina',
    managerName: 'Мария Дудина',
    assignmentSource: 'manual',
    assignedAt: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
  },
  settings: {
    cogsKopecks: 45000,
    wbCommissionPct: 25,
    logisticsKopecks: 5000,
    minMarginPct: 15,
    pMinKopecks: 0,
    pMaxKopecks: 190000,
    priceStepPct: 6,
    priceStepHours: 1,
    rrpKopecks: 0,
    allowNegativeMargin: false,
    automationEnabled: true,
    basketNormMode: 'auto',
    basketNormManual: null,
    repricerMode: 'baskets',
    revenueComparisonDays: 7,
    nightMedianEnabled: false,
    promoBoostEnabled: false,
    promoBoostPct: 25,
    promoBoostHours: 48,
  },
  commentSummary: {
    count: 1,
    latestText: 'Проверить цену перед следующим циклом ночной медианы.',
    latestAuthor: mariaActor.name,
    latestAt: commentCreatedAt,
  },
  comments: [
    {
      id: 'comment-fixture-1',
      sku: 'FBBT_42',
      author: mariaActor,
      createdAt: commentCreatedAt,
      text: 'Проверить цену перед следующим циклом ночной медианы.',
    },
  ],
  auditEvents: [
    {
      id: 'audit-fixture-sync',
      sku: 'FBBT_42',
      actor: systemActor,
      source: 'system',
      scope: 'sku',
      action: 'Пересчёт репрайсера',
      createdAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
      oldValue: 'предыдущий цикл',
      newValue: 'актуальные корзины и маржа',
    },
  ],
  cachedAt: null,
}

export const successFixture: SkuSettingsResponse = BASE

export const warmupFixture: SkuSettingsResponse = {
  ...BASE,
  meta: {
    ...BASE.meta,
    status: 'warmup',
    warmupDaysLeft: 12,
    basketsLast7d: 3,
    basketNormSource: 'fallback',
  },
}

export function partialFixture(): SkuSettingsResponse {
  return {
    ...BASE,
    cachedAt: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
  }
}

export type Scenario =
  | 'success'
  | 'loading'
  | 'error'
  | 'partial'
  | 'warmup'
  | 'validation'
  | 'saving'
  | 'save-error'
  | 'save-success'
  | 'negative-margin'

export const SCENARIOS: { value: Scenario; label: string; description: string }[] = [
  { value: 'success', label: 'Success (idle)', description: 'Обычный SKU в режиме auto' },
  { value: 'loading', label: 'Loading (GET 5s)', description: 'Скелетон карточки' },
  { value: 'error', label: 'Error (GET 500)', description: 'Баннер + retry' },
  { value: 'partial', label: 'Partial (кэш 10 мин)', description: 'Badge устаревших данных' },
  { value: 'warmup', label: 'Warmup', description: 'SKU < 30 дней, автоматика выкл' },
  { value: 'validation', label: 'Validation error', description: 'Ввести P_max < P_min' },
  { value: 'saving', label: 'Saving (PUT 3s)', description: 'Spinner в Save' },
  { value: 'save-error', label: 'Save error (PUT 500)', description: 'Inline banner' },
  { value: 'save-success', label: 'Save success', description: 'Toast «Сохранено»' },
  {
    value: 'negative-margin',
    label: 'Negative margin confirm',
    description: 'Чекбокс ликвидации → модалка',
  },
]
