import type { AuditActor, SkuAuditEvent, SkuComment, SkuSettingsResponse } from './schemas'
import { getSkuAnalyticsSummary } from '../wb-reports/repository'

const WB_COMMISSION = 25
const now = Date.now()
const ago = (hours: number) => new Date(now - hours * 3600_000).toISOString()
const systemActor: AuditActor = { id: 'system', name: 'Система', role: 'system' }
const mariaActor: AuditActor = { id: 'manager-maria-dudina', name: 'Мария Дудина', role: 'manager' }
const financeActor: AuditActor = { id: 'finance-maxim', name: 'Максим', role: 'finance' }
const managerAssignments: Record<string, { managerId: string | null; managerName: string; assignmentSource: 'manual' | 'xlsx' | 'none'; assignedAt: string | null }> = {
  LBBT_03: { managerId: null, managerName: 'Без ответственного', assignmentSource: 'none', assignedAt: null },
  HCBT_19: { managerId: 'manager-irina', managerName: 'Ирина', assignmentSource: 'xlsx', assignedAt: ago(24) },
}

// Базовые параметры по типам
const COSTS = {
  F: { cogsKopecks: 45000, logisticsKopecks: 5000, pMaxKopecks: 190000 },
  H: { cogsKopecks: 85000, logisticsKopecks: 5500, pMaxKopecks: 320000 },
  L: { cogsKopecks: 60000, logisticsKopecks: 5200, pMaxKopecks: 240000 },
}

function row(
  articleId: string,
  name: string,
  overrides: Partial<SkuSettingsResponse['meta']> & { priceKopecks: number },
  settingsOverride: Partial<SkuSettingsResponse['settings']> = {},
): SkuSettingsResponse {
  const typeKey = articleId[0] as 'F' | 'H' | 'L'
  const costs = COSTS[typeKey]
  const norm = typeKey === 'F' ? 20 : typeKey === 'H' ? 15 : 10
  const num = parseInt(articleId.split('_')[1] ?? '0', 10)
  const status = overrides.status ?? 'auto'
  const source: 'auto' | 'fallback' = status === 'warmup' ? 'fallback' : 'auto'
  const comments = commentsFor(articleId)
  const assignment = managerAssignments[articleId] ?? {
    managerId: status === 'manual' ? 'manager-maria-dudina' : 'manager-irina',
    managerName: status === 'manual' ? 'Мария Дудина' : 'Ирина',
    assignmentSource: 'manual' as const,
    assignedAt: ago(48),
  }
  return {
    meta: {
      articleId,
      nmId: 185000000 + num,
      name,
      status,
      currentPriceKopecks: overrides.priceKopecks,
      basketsLast7d: norm,
      basketNorm: norm,
      basketNormSource: source,
      warmupDaysLeft: null,
      lastSavedAt: ago(2),
      ...assignment,
      ...overrides,
    },
    settings: {
      cogsKopecks: costs.cogsKopecks,
      wbCommissionPct: WB_COMMISSION,
      logisticsKopecks: costs.logisticsKopecks,
      minMarginPct: 15,
      pMinKopecks: 0,
      pMaxKopecks: costs.pMaxKopecks,
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
      ...settingsOverride,
    },
    analytics: getSkuAnalyticsSummary(articleId),
    commentSummary: commentSummary(comments),
    comments,
    auditEvents: auditFor(articleId, status),
    cachedAt: null,
  }
}

function commentsFor(sku: string): SkuComment[] {
  const map: Record<string, SkuComment[]> = {
    FBBT_42: [
      { id: 'comment-fbbt-42-1', sku, author: mariaActor, createdAt: ago(26), text: 'Проверить, почему рост корзин не даёт такой же рост продаж.' },
      { id: 'comment-fbbt-42-2', sku, author: financeActor, createdAt: ago(3), text: 'Перед повышением цены сверить ДРР и маржу после СПП.' },
    ],
    LBBT_03: [
      { id: 'comment-lbbt-03-1', sku, author: mariaActor, createdAt: ago(7), text: 'Нужен разбор логистики и хранения перед решением по ликвидации.' },
    ],
    HCBT_19: [
      { id: 'comment-hcbt-19-1', sku, author: mariaActor, createdAt: ago(5), text: 'Низкие корзины, не запускать снижение без проверки рекламы.' },
    ],
  }
  return map[sku] ?? []
}

function commentSummary(comments: SkuComment[]): SkuSettingsResponse['commentSummary'] {
  const latest = comments.at(-1)
  return {
    count: comments.length,
    latestText: latest?.text ?? null,
    latestAuthor: latest?.author.name ?? null,
    latestAt: latest?.createdAt ?? null,
  }
}

function auditFor(sku: string, status: SkuSettingsResponse['meta']['status']): SkuAuditEvent[] {
  const base: SkuAuditEvent[] = [
    {
      id: `audit-${sku}-sync`,
      sku,
      createdAt: ago(2),
      actor: systemActor,
      source: 'system',
      scope: 'sku',
      action: 'Пересчёт репрайсера',
      oldValue: 'предыдущий цикл',
      newValue: 'актуальные корзины и маржа',
    },
  ]
  if (status === 'manual') {
    base.push({
      id: `audit-${sku}-manual`,
      sku,
      createdAt: ago(5),
      actor: mariaActor,
      source: 'manager',
      scope: 'sku',
      action: 'Ручной контроль',
      reason: 'Нужно проверить спрос и рекламные расходы перед автоматикой',
      oldValue: 'авто',
      newValue: 'ручной',
    })
  }
  return base
}

export const SKU_LIST: SkuSettingsResponse[] = [
  // ── Ручной контроль ───────────────────────────────────────────────────────
  row('HCBT_07', 'Худи чёрное «Принт 7»', {
    priceKopecks: 210000, status: 'manual',
    basketsLast7d: 3, lastSavedAt: ago(20),
  }, { automationEnabled: false }),

  row('FBBT_31', 'Футболка белая «Принт 31»', {
    priceKopecks: 135000, status: 'manual',
    basketsLast7d: 8, lastSavedAt: ago(21),
  }, { automationEnabled: false }),

  // ── Отрицательная маржа ───────────────────────────────────────────────────
  row('LBBT_03', 'Лонгслив белый «Принт 3»', {
    priceKopecks: 64000, status: 'manual', basketsLast7d: 4, lastSavedAt: ago(5),
  }, { automationEnabled: false }),

  row('FCBT_18', 'Футболка чёрная «Принт 18»', {
    priceKopecks: 62000, status: 'manual', basketsLast7d: 6, lastSavedAt: ago(8),
  }, { automationEnabled: false }),

  // ── Корзины << нормы ──────────────────────────────────────────────────────
  row('FBBT_55', 'Футболка белая «Принт 55»', {
    priceKopecks: 165000, basketsLast7d: 1, basketNorm: 20, lastSavedAt: ago(1),
  }),
  row('HCBT_19', 'Худи чёрное «Принт 19»', {
    priceKopecks: 285000, basketsLast7d: 2, basketNorm: 15, lastSavedAt: ago(3),
  }),
  row('LCBT_08', 'Лонгслив чёрный «Принт 8»', {
    priceKopecks: 195000, basketsLast7d: 3, basketNorm: 10, lastSavedAt: ago(4),
  }),

  // ── Прогрев ───────────────────────────────────────────────────────────────
  row('FBBT_44', 'Футболка белая «Принт 44»', {
    priceKopecks: 129000, status: 'warmup', warmupDaysLeft: 12,
    basketsLast7d: 5, lastSavedAt: ago(1),
  }, { automationEnabled: false }),
  row('HBBT_22', 'Худи белое «Принт 22»', {
    priceKopecks: 239000, status: 'warmup', warmupDaysLeft: 8,
    basketsLast7d: 3, lastSavedAt: ago(2),
  }, { automationEnabled: false }),
  row('LBBT_11', 'Лонгслив белый «Принт 11»', {
    priceKopecks: 189000, status: 'warmup', warmupDaysLeft: 24,
    basketsLast7d: 2, lastSavedAt: null,
  }, { automationEnabled: false }),

  // ── Ручной режим ──────────────────────────────────────────────────────────
  row('FBBT_12', 'Футболка белая «Принт 12»', {
    priceKopecks: 145000, status: 'manual', basketsLast7d: 18,
  }, { automationEnabled: false }),
  row('FCBT_05', 'Футболка чёрная «Принт 5»', {
    priceKopecks: 155000, status: 'manual', basketsLast7d: 14,
  }, { automationEnabled: false }),
  row('HBBT_07', 'Худи белое «Принт 7»', {
    priceKopecks: 250000, status: 'manual', basketsLast7d: 11,
  }, { automationEnabled: false }),

  // ── Нормальный auto ───────────────────────────────────────────────────────
  row('FBBT_42', 'Футболка белая «Принт 42»', { priceKopecks: 129000, basketsLast7d: 34, basketNorm: 20 }),
  row('FBBT_01', 'Футболка белая «Принт 1»',  { priceKopecks: 139000, basketsLast7d: 28 }),
  row('FBBT_02', 'Футболка белая «Принт 2»',  { priceKopecks: 119000, basketsLast7d: 22 }),
  row('FBBT_03', 'Футболка белая «Принт 3»',  { priceKopecks: 149000, basketsLast7d: 31 }),
  row('FBBT_04', 'Футболка белая «Принт 4»',  { priceKopecks: 125000, basketsLast7d: 19 }),
  row('FBBT_06', 'Футболка белая «Принт 6»',  { priceKopecks: 132000, basketsLast7d: 25 }),
  row('FBBT_07', 'Футболка белая «Принт 7»',  { priceKopecks: 159000, basketsLast7d: 42 }),
  row('FBBT_08', 'Футболка белая «Принт 8»',  { priceKopecks: 115000, basketsLast7d: 16 }),
  row('FBBT_09', 'Футболка белая «Принт 9»',  { priceKopecks: 142000, basketsLast7d: 27 }),
  row('FBBT_10', 'Футболка белая «Принт 10»', { priceKopecks: 138000, basketsLast7d: 23 }),
  row('FBBT_13', 'Футболка белая «Принт 13»', { priceKopecks: 129000, basketsLast7d: 21 }),
  row('FBBT_14', 'Футболка белая «Принт 14»', { priceKopecks: 155000, basketsLast7d: 38 }),
  row('FBBT_15', 'Футболка белая «Принт 15»', { priceKopecks: 119000, basketsLast7d: 17 }),
  row('FCBT_01', 'Футболка чёрная «Принт 1»', { priceKopecks: 139000, basketsLast7d: 29 }),
  row('FCBT_02', 'Футболка чёрная «Принт 2»', { priceKopecks: 145000, basketsLast7d: 33 }),
  row('FCBT_03', 'Футболка чёрная «Принт 3»', { priceKopecks: 122000, basketsLast7d: 20 }),
  row('FCBT_04', 'Футболка чёрная «Принт 4»', { priceKopecks: 135000, basketsLast7d: 24 }),
  row('FCBT_06', 'Футболка чёрная «Принт 6»', { priceKopecks: 149000, basketsLast7d: 36 }),
  row('HBBT_01', 'Худи белое «Принт 1»',      { priceKopecks: 229000, basketsLast7d: 16 }),
  row('HBBT_02', 'Худи белое «Принт 2»',      { priceKopecks: 249000, basketsLast7d: 18 }),
  row('HBBT_03', 'Худи белое «Принт 3»',      { priceKopecks: 219000, basketsLast7d: 14 }),
  row('HBBT_04', 'Худи белое «Принт 4»',      { priceKopecks: 275000, basketsLast7d: 22 }),
  row('HBBT_05', 'Худи белое «Принт 5»',      { priceKopecks: 239000, basketsLast7d: 19 }),
  row('HCBT_01', 'Худи чёрное «Принт 1»',     { priceKopecks: 259000, basketsLast7d: 17 }),
  row('HCBT_02', 'Худи чёрное «Принт 2»',     { priceKopecks: 269000, basketsLast7d: 21 }),
  row('HCBT_03', 'Худи чёрное «Принт 3»',     { priceKopecks: 229000, basketsLast7d: 13 }),
  row('HCBT_04', 'Худи чёрное «Принт 4»',     { priceKopecks: 245000, basketsLast7d: 16 }),
  row('HCBT_05', 'Худи чёрное «Принт 5»',     { priceKopecks: 285000, basketsLast7d: 24 }),
  row('LBBT_01', 'Лонгслив белый «Принт 1»',  { priceKopecks: 189000, basketsLast7d: 11 }),
  row('LBBT_02', 'Лонгслив белый «Принт 2»',  { priceKopecks: 209000, basketsLast7d: 14 }),
  row('LBBT_04', 'Лонгслив белый «Принт 4»',  { priceKopecks: 175000, basketsLast7d: 10 }),
  row('LBBT_05', 'Лонгслив белый «Принт 5»',  { priceKopecks: 195000, basketsLast7d: 12 }),
  row('LCBT_01', 'Лонгслив чёрный «Принт 1»', { priceKopecks: 199000, basketsLast7d: 13 }),
  row('LCBT_02', 'Лонгслив чёрный «Принт 2»', { priceKopecks: 215000, basketsLast7d: 15 }),
]
