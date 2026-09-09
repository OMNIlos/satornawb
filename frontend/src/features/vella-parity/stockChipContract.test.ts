import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { expect, it } from 'vitest'

const html = readFileSync(new URL('../../../public/vella-production.html', import.meta.url), 'utf8')
function extract(start: string, end: string) {
  if (html.split(start).length !== 2 || html.split(end).length !== 2) throw new Error('Nonunique stock filter boundary')
  return html.slice(html.indexOf(start), html.indexOf(end))
}
const source = extract('function normalizeReportFilterText(value){', 'function managerFilterValue(tab){')
  + extract('function rowMatchesChip(tab, row, chipText){', 'function updateReportEmptyState(table){')

it.each([
  ['Риск нехватки', { daysToOos: '4' }, true],
  ['OOS риск', { daysToOos: '7' }, true],
  ['Риск нехватки', { daysToOos: '20' }, false],
  ['Избыток', { daysToOos: '90' }, true],
  ['Избыток', { daysToOos: '20' }, false],
  ['Избыток', {}, false],
  ['Избыток', { daysToOos: '' }, false],
  ['Риск нехватки', {}, false],
  ['Риск нехватки', { availableUnits: '0' }, true],
  ['Риск нехватки', { availableUnits: '5' }, false],
  ['Риск нехватки', { availableUnits: '' }, false],
  ['Топ-склады', { warehouse: 'Казань' }, true],
  ['Топ-склады', { warehouse: 'Екатеринбург' }, false],
  ['В акции', {}, false],
] as const)('matches stock chip %s only with available evidence %j', (chipText, dataset, expected) => {
  const actual = runInNewContext(`${source}\nrowMatchesChip(tab, row, chipText)`, {
    tab: { id: 'tab-stock' }, row: { dataset }, chipText,
  }, { timeout: 1000 })
  expect(actual).toBe(expected)
})
