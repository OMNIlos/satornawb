// Конвенция: деньги хранятся в копейках (целые числа).
// См. docs/api-contracts/README.md — копейки как integer, не рубли с плавающей точкой.
//
// Intl.NumberFormat с style:'currency' автоматически использует NBSP (U+00A0)
// между группами цифр и перед «₽» — цена не ломается переносом строки.
const RUB_FMT = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'RUB',
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
})

export function formatRub(kopecks: number): string {
  if (!Number.isFinite(kopecks)) return '∞ ₽'
  return RUB_FMT.format(kopecks / 100)
}
