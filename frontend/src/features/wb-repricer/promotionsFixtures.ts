const now = Date.now()
const days = (d: number) => new Date(now + d * 86400_000).toISOString().slice(0, 10)

export interface WbPromotion {
  id: string
  name: string
  type: 'auto' | 'flash' | 'special'
  status: 'active' | 'upcoming' | 'ended'
  startDate: string
  endDate: string
  daysUntilEnd: number
  daysUntilStart: number
  eligibleSkuCount: number
  participatingSkuCount: number
  participationPct: number
  excelLoaded: boolean
  excelFileName?: string
  excelLoadedAt?: string
}

export interface PromotionSku {
  articleId: string
  name: string
  currentPriceKopecks: number
  promoThresholdKopecks: number | null
  isProtected: boolean
  // Экономика SKU — для расчёта маржи при акционной цене
  cogsKopecks: number
  wbCommissionPct: number
  logisticsKopecks: number
}

export const PROMOTIONS: WbPromotion[] = [
  // ── Active (3) ──────────────────────────────────────────────────────────
  {
    id: 'promo-001',
    name: 'Весенняя распродажа',
    type: 'auto',
    status: 'active',
    startDate: days(-5),
    endDate: days(3),
    daysUntilEnd: 3,
    daysUntilStart: 0,
    eligibleSkuCount: 47,
    participatingSkuCount: 23,
    participationPct: 49,
    excelLoaded: true,
    excelFileName: 'Весенняя распродажа.xlsx',
    excelLoadedAt: days(-5),
  },
  {
    id: 'promo-002',
    name: 'Недельная скидка апрель',
    type: 'auto',
    status: 'active',
    startDate: days(-2),
    endDate: days(7),
    daysUntilEnd: 7,
    daysUntilStart: 0,
    eligibleSkuCount: 12,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: false,
  },
  {
    id: 'promo-003',
    name: 'Флеш-акция выходного дня',
    type: 'flash',
    status: 'active',
    startDate: days(-1),
    endDate: days(2),
    daysUntilEnd: 2,
    daysUntilStart: 0,
    eligibleSkuCount: 8,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: false,
  },
  // ── Upcoming (3) ────────────────────────────────────────────────────────
  {
    id: 'promo-004',
    name: 'Майские праздники',
    type: 'auto',
    status: 'upcoming',
    startDate: days(5),
    endDate: days(12),
    daysUntilEnd: 12,
    daysUntilStart: 5,
    eligibleSkuCount: 62,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: false,
  },
  {
    id: 'promo-005',
    name: 'День рождения WB',
    type: 'special',
    status: 'upcoming',
    startDate: days(15),
    endDate: days(22),
    daysUntilEnd: 22,
    daysUntilStart: 15,
    eligibleSkuCount: 38,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: true,
    excelFileName: 'День рождения WB.xlsx',
    excelLoadedAt: days(-1),
  },
  {
    id: 'promo-006',
    name: 'Летний старт',
    type: 'auto',
    status: 'upcoming',
    startDate: days(30),
    endDate: days(40),
    daysUntilEnd: 40,
    daysUntilStart: 30,
    eligibleSkuCount: 55,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: false,
  },
  // ── Ended (2) ───────────────────────────────────────────────────────────
  {
    id: 'promo-007',
    name: 'Зимний сезон',
    type: 'auto',
    status: 'ended',
    startDate: days(-30),
    endDate: days(-10),
    daysUntilEnd: -10,
    daysUntilStart: 0,
    eligibleSkuCount: 41,
    participatingSkuCount: 31,
    participationPct: 76,
    excelLoaded: true,
    excelFileName: 'Зимний сезон.xlsx',
    excelLoadedAt: days(-31),
  },
  {
    id: 'promo-008',
    name: 'Февральская распродажа',
    type: 'flash',
    status: 'ended',
    startDate: days(-45),
    endDate: days(-20),
    daysUntilEnd: -20,
    daysUntilStart: 0,
    eligibleSkuCount: 18,
    participatingSkuCount: 0,
    participationPct: 0,
    excelLoaded: false,
  },
]

// SKUs per promotion (only for active/upcoming that have Excel loaded or for detail view)
export const PROMOTION_SKUS: Record<string, PromotionSku[]> = {
  'promo-001': [
    { articleId: 'FBBT_31', name: 'Футболка белая «Принт 31»',  currentPriceKopecks: 135000, promoThresholdKopecks: 114800, isProtected: true,  cogsKopecks: 45000, wbCommissionPct: 25, logisticsKopecks: 5000 },
    { articleId: 'HCBT_07', name: 'Худи чёрное «Принт 7»',      currentPriceKopecks: 210000, promoThresholdKopecks: 178500, isProtected: true,  cogsKopecks: 85000, wbCommissionPct: 25, logisticsKopecks: 5500 },
    { articleId: 'LBBT_03', name: 'Лонгслив белый «Принт 3»',   currentPriceKopecks: 164000, promoThresholdKopecks: 139400, isProtected: true,  cogsKopecks: 60000, wbCommissionPct: 25, logisticsKopecks: 5200 },
    { articleId: 'FBBT_55', name: 'Футболка белая «Принт 55»',  currentPriceKopecks: 125000, promoThresholdKopecks: 114800, isProtected: true,  cogsKopecks: 45000, wbCommissionPct: 25, logisticsKopecks: 5000 },
    { articleId: 'HBBT_22', name: 'Худи белое «Принт 22»',      currentPriceKopecks: 239000, promoThresholdKopecks: 255300, isProtected: false, cogsKopecks: 85000, wbCommissionPct: 25, logisticsKopecks: 5500 },
    { articleId: 'LBBT_11', name: 'Лонгслив белый «Принт 11»',  currentPriceKopecks: 189000, promoThresholdKopecks: 139400, isProtected: true,  cogsKopecks: 60000, wbCommissionPct: 25, logisticsKopecks: 5200 },
  ],
  'promo-002': [
    { articleId: 'FCBT_18', name: 'Футболка чёрная «Принт 18»', currentPriceKopecks: 130000, promoThresholdKopecks: null, isProtected: false, cogsKopecks: 45000, wbCommissionPct: 25, logisticsKopecks: 5000 },
    { articleId: 'HCBT_19', name: 'Худи чёрное «Принт 19»',     currentPriceKopecks: 285000, promoThresholdKopecks: null, isProtected: false, cogsKopecks: 85000, wbCommissionPct: 25, logisticsKopecks: 5500 },
    { articleId: 'FBBT_31', name: 'Футболка белая «Принт 31»',  currentPriceKopecks: 135000, promoThresholdKopecks: null, isProtected: false, cogsKopecks: 45000, wbCommissionPct: 25, logisticsKopecks: 5000 },
  ],
  'promo-003': [
    { articleId: 'FBBT_55', name: 'Футболка белая «Принт 55»',  currentPriceKopecks: 125000, promoThresholdKopecks: null, isProtected: false, cogsKopecks: 45000, wbCommissionPct: 25, logisticsKopecks: 5000 },
    { articleId: 'LBBT_11', name: 'Лонгслив белый «Принт 11»',  currentPriceKopecks: 189000, promoThresholdKopecks: null, isProtected: false, cogsKopecks: 60000, wbCommissionPct: 25, logisticsKopecks: 5200 },
  ],
  'promo-005': [
    { articleId: 'HBBT_22', name: 'Худи белое «Принт 22»',      currentPriceKopecks: 239000, promoThresholdKopecks: 203200, isProtected: true,  cogsKopecks: 85000, wbCommissionPct: 25, logisticsKopecks: 5500 },
    { articleId: 'HCBT_07', name: 'Худи чёрное «Принт 7»',      currentPriceKopecks: 210000, promoThresholdKopecks: 178500, isProtected: true,  cogsKopecks: 85000, wbCommissionPct: 25, logisticsKopecks: 5500 },
    { articleId: 'LBBT_03', name: 'Лонгслив белый «Принт 3»',   currentPriceKopecks: 164000, promoThresholdKopecks: 139400, isProtected: true,  cogsKopecks: 60000, wbCommissionPct: 25, logisticsKopecks: 5200 },
  ],
}
