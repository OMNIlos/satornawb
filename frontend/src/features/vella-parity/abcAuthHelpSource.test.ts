import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('./VellaHtmlParityPage.tsx', import.meta.url), 'utf8')

describe('ABC auth and help source', () => {
  it('shows a reauthorization panel and hides report blocks when ABC auth token is expired', () => {
    expect(source).toContain('function isAbcAuthExpiredError')
    expect(source).toContain('window.__vellaAbcLiveAuthExpired = authExpired')
    expect(source).toContain('data-vella-island="abc-auth-expired-panel"')
    expect(source).toContain('Переавторизоваться')
    expect(source).toContain('if (state.authExpired) return null')
  })

  it('adds customer-facing help and formulas to ABC KPIs and table headers', () => {
    expect(source).toContain('help: \'Две буквы: первая по доле продаж')
    expect(source).toContain('Формула: продажи минус себестоимость')
    expect(source).toContain('Конверсия корзины в заказ. Формула: заказы / корзины * 100%.')
    expect(source).toContain('className="stat-tip abc-header-help"')
    expect(source).toContain('data-tip={stat.help}')
  })
})
