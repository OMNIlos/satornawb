import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const projectRoot = resolve(__dirname, '../../..')

describe('wb reviews page mock cleanup', () => {
  it('does not ship legacy review fixture rows or static KPI placeholders', () => {
    const parityPage = readFileSync(resolve(projectRoot, 'src/features/vella-parity/VellaHtmlParityPage.tsx'), 'utf8')
    const legacyHtml = readFileSync(resolve(projectRoot, 'public/vella-production.html'), 'utf8')
    const combined = `${parityPage}\n${legacyHtml}`

    expect(combined).not.toContain('wb-review-001')
    expect(combined).not.toContain('Принт огонь, футболка мягкая')
    expect(combined).not.toContain('Позитивная оценка, но негативный текст')
    expect(combined).not.toContain('100-150 отзывов в день')
    expect(combined).not.toContain('34 мин')
    expect(combined).not.toContain("['brand', 'Anomie studio'")
    expect(combined).not.toContain("['brand', 'Bless T'")
  })
})
