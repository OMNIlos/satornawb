import type { AuditActor, PriceChangeEntry } from './schemas'

const now = Date.now()
const t = (hoursAgo: number, minutesAgo = 0) =>
  new Date(now - hoursAgo * 3600_000 - minutesAgo * 60_000).toISOString()
const systemActor: AuditActor = { id: 'system', name: 'Система', role: 'system' }
const mariaActor: AuditActor = { id: 'manager-maria-dudina', name: 'Мария Дудина', role: 'manager' }
const maximActor: AuditActor = { id: 'finance-maxim', name: 'Максим', role: 'finance' }

let _id = 1
const id = () => String(_id++)

function entry(
  articleId: string,
  skuName: string,
  trigger: PriceChangeEntry['trigger'],
  hoursAgo: number,
  oldKopecks: number,
  newKopecks: number,
  marginAfterPct: number,
  minutesAgo = 0,
): PriceChangeEntry {
  const changePct = +((newKopecks / oldKopecks - 1) * 100).toFixed(1)
  const manual = trigger === 'manual'
  const bulk = trigger === 'liquidation'
  const actor = manual ? mariaActor : bulk ? maximActor : systemActor
  const reason = manual
    ? 'Ручная корректировка после проверки корзин и маржи'
    : bulk
      ? 'Массовый шаг ликвидации по слабому спросу'
      : undefined
  return {
    id: id(),
    articleId,
    skuName,
    trigger,
    timestamp: t(hoursAgo, minutesAgo),
    oldPriceKopecks: oldKopecks,
    newPriceKopecks: newKopecks,
    changePct,
    marginAfterPct,
    actor,
    source: manual ? 'manager' : bulk ? 'bulk' : 'system',
    scope: bulk ? 'bulk' : 'sku',
    reason,
    oldValue: `${oldKopecks / 100} ₽`,
    newValue: `${newKopecks / 100} ₽`,
  }
}

// Ночная медиана: подъём ~23:00, восстановление ~04:00
// Алгоритм: изменения в рабочее время и ночью
// Ликвидация: плановые шаги

export const CHANGELOG_ENTRIES: PriceChangeEntry[] = [
  // ── 23:00–23:40 — ночная медиана вверх ───────────────────────────────────
  entry('FBBT_42', 'Футболка белая «Принт 42»', 'night_median_up', 23,     129000, 137000, 38, 0),
  entry('FBBT_01', 'Футболка белая «Принт 1»',  'night_median_up', 23,     139000, 148000, 36, 4),
  entry('FBBT_02', 'Футболка белая «Принт 2»',  'night_median_up', 23,     119000, 126000, 34, 8),
  entry('FBBT_03', 'Футболка белая «Принт 3»',  'night_median_up', 23,     149000, 158000, 37, 12),
  entry('HBBT_01', 'Худи белое «Принт 1»',      'night_median_up', 22,     229000, 243000, 35, 55),
  entry('HBBT_02', 'Худи белое «Принт 2»',      'night_median_up', 22,     249000, 264000, 36, 51),
  entry('HCBT_01', 'Худи чёрное «Принт 1»',     'night_median_up', 22,     259000, 275000, 37, 47),
  entry('HCBT_02', 'Худи чёрное «Принт 2»',     'night_median_up', 22,     269000, 285000, 38, 43),
  entry('LBBT_01', 'Лонгслив белый «Принт 1»',  'night_median_up', 22,     189000, 200000, 34, 39),
  entry('LCBT_01', 'Лонгслив чёрный «Принт 1»', 'night_median_up', 22,     199000, 211000, 35, 35),
  entry('FBBT_04', 'Футболка белая «Принт 4»',  'night_median_up', 22,     125000, 132000, 33, 30),
  entry('FBBT_06', 'Футболка белая «Принт 6»',  'night_median_up', 22,     132000, 140000, 34, 25),
  entry('FBBT_07', 'Футболка белая «Принт 7»',  'night_median_up', 22,     159000, 169000, 39, 20),
  entry('FCBT_01', 'Футболка чёрная «Принт 1»', 'night_median_up', 22,     139000, 147000, 36, 15),
  entry('FCBT_02', 'Футболка чёрная «Принт 2»', 'night_median_up', 22,     145000, 154000, 37, 10),

  // ── 04:00–04:40 — восстановление ───────────────────────────────────────
  entry('FBBT_42', 'Футболка белая «Принт 42»', 'night_median_restore', 19, 137000, 129000, 34, 0),
  entry('FBBT_01', 'Футболка белая «Принт 1»',  'night_median_restore', 19, 148000, 139000, 32, 4),
  entry('FBBT_02', 'Футболка белая «Принт 2»',  'night_median_restore', 19, 126000, 119000, 30, 8),
  entry('FBBT_03', 'Футболка белая «Принт 3»',  'night_median_restore', 19, 158000, 149000, 33, 12),
  entry('HBBT_01', 'Худи белое «Принт 1»',      'night_median_restore', 18, 243000, 229000, 31, 55),
  entry('HBBT_02', 'Худи белое «Принт 2»',      'night_median_restore', 18, 264000, 249000, 32, 51),
  entry('HCBT_01', 'Худи чёрное «Принт 1»',     'night_median_restore', 18, 275000, 259000, 33, 47),
  entry('LBBT_01', 'Лонгслив белый «Принт 1»',  'night_median_restore', 18, 200000, 189000, 30, 39),

  // ── Алгоритм — дневные корректировки ────────────────────────────────────
  entry('FBBT_55', 'Футболка белая «Принт 55»', 'algorithm', 16, 165000, 155000, 28, 15),
  entry('HCBT_19', 'Худи чёрное «Принт 19»',    'algorithm', 16, 285000, 268000, 26, 30),
  entry('LCBT_08', 'Лонгслив чёрный «Принт 8»', 'algorithm', 15, 195000, 184000, 27, 0),
  entry('FBBT_07', 'Футболка белая «Принт 7»',  'algorithm', 14, 159000, 169000, 39, 10),
  entry('FCBT_02', 'Футболка чёрная «Принт 2»', 'algorithm', 13, 145000, 154000, 37, 45),
  entry('HBBT_04', 'Худи белое «Принт 4»',      'algorithm', 12, 275000, 291000, 40, 20),
  entry('HCBT_05', 'Худи чёрное «Принт 5»',     'algorithm', 11, 285000, 270000, 31, 0),
  entry('LBBT_02', 'Лонгслив белый «Принт 2»',  'algorithm', 10, 209000, 220000, 38, 35),
  entry('FBBT_09', 'Футболка белая «Принт 9»',  'algorithm', 9,  142000, 134000, 29, 50),
  entry('FCBT_03', 'Футболка чёрная «Принт 3»', 'algorithm', 8,  122000, 129000, 33, 15),
  entry('FBBT_13', 'Футболка белая «Принт 13»', 'algorithm', 7,  129000, 137000, 36, 40),
  entry('FBBT_14', 'Футболка белая «Принт 14»', 'algorithm', 6,  155000, 147000, 32, 5),
  entry('HCBT_03', 'Худи чёрное «Принт 3»',     'algorithm', 5,  229000, 216000, 28, 30),
  entry('LCBT_02', 'Лонгслив чёрный «Принт 2»', 'algorithm', 4,  215000, 228000, 39, 10),
  entry('FBBT_10', 'Футболка белая «Принт 10»', 'algorithm', 3,  138000, 146000, 37, 25),
  entry('HBBT_05', 'Худи белое «Принт 5»',      'algorithm', 2,  239000, 225000, 29, 50),
  entry('FBBT_15', 'Футболка белая «Принт 15»', 'algorithm', 2,  119000, 126000, 34, 10),
  entry('FCBT_06', 'Футболка чёрная «Принт 6»', 'algorithm', 1,  149000, 158000, 38, 35),

  // ── Ручные изменения ─────────────────────────────────────────────────────
  entry('FBBT_12', 'Футболка белая «Принт 12»', 'manual', 20, 145000, 139000, 30, 0),
  entry('HBBT_07', 'Худи белое «Принт 7»',      'manual', 11, 250000, 265000, 37, 15),
  entry('FCBT_05', 'Футболка чёрная «Принт 5»', 'manual',  3, 155000, 145000, 27, 20),

  // ── Ликвидация ───────────────────────────────────────────────────────────
  entry('FBBT_55', 'Футболка белая «Принт 55»', 'liquidation', 24, 175000, 165000, 18, 0),
  entry('HCBT_19', 'Худи чёрное «Принт 19»',    'liquidation', 24, 300000, 285000, 15, 30),

  // ── Выход из прогрева ────────────────────────────────────────────────────
  entry('LBBT_04', 'Лонгслив белый «Принт 4»',  'warmup_end', 17, 175000, 182000, 33, 0),
]
  .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
