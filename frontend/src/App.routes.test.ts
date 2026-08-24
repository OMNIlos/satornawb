import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const appSource = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8')

describe('production routes', () => {
  it('keeps WB reports on the Vella parity interface', () => {
    expect(appSource).toContain('<Route path="/wb/reports" element={<VellaHtmlParityPage />} />')
    expect(appSource).toContain('<Route path="/wb/reports/rules" element={<VellaHtmlParityPage />} />')
    expect(appSource).not.toContain('<Route path="/wb/reports" element={<WbReportsPage />} />')
  })
})
