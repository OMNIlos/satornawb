import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))
const sourcePath = resolve(__dirname, 'VellaHtmlParityPage.tsx')
const source = readFileSync(sourcePath, 'utf8')

function functionSource(name: string) {
  const start = source.indexOf(`function ${name}`)
  expect(start).toBeGreaterThanOrEqual(0)
  const next = source.indexOf('\nfunction ', start + 1)
  return source.slice(start, next > start ? next : undefined)
}

describe('report info buttons source coverage', () => {
  it('renders generic report help tips in shared KPI strip', () => {
    const kpiStrip = functionSource('KpiStripIsland')
    expect(kpiStrip).toContain('<ReportHelpTip tip={stat.help} />')
    expect(source).toContain('Это сумма выкупленных продаж WB за выбранный период')
    expect(source).toContain('Товары, по которым остатка может не хватить')
  })

  it('adds human help to report table headers with formulas', () => {
    expect(functionSource('ExpensesTableShellIsland')).toContain('<ReportHeaderCell label="Статья ДДС"')
    expect(functionSource('StockTableShellIsland')).toContain('Дней до OOS = доступный остаток / средние заказы в день')
    expect(functionSource('AdsTableShellIsland')).toContain('ДРР = расход рекламы / сумму заказов или продаж')
    expect(functionSource('PnlLiveTableShellIsland')).toContain('Прибыль = выручка - себестоимость - комиссия')
    expect(functionSource('WeekTableShellIsland')).toContain('Наличие 7 дней')
  })

  it('adds info tips to report summary cards', () => {
    expect(functionSource('AdsLiveKpiStripIsland')).toContain('Сколько денег списано на рекламу WB')
    expect(functionSource('AdsLiveSummaryGridIsland')).toContain('<ReportHelpTip tip={tip} />')
    expect(functionSource('PnlLiveWorkbenchIsland')).toContain('Маржа = прибыль / выручка * 100%.')
    expect(functionSource('WeekWorkbenchIsland')).toContain('Среднее изменение продаж к прошлой неделе')
  })
})
