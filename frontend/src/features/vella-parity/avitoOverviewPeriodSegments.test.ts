import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const sourceRoot = path.resolve(__dirname, '../..')
const paritySource = fs.readFileSync(path.join(sourceRoot, 'features/vella-parity/VellaHtmlParityPage.tsx'), 'utf8')

describe('Avito overview period segments', () => {
  it('keeps preset period buttons clickable while backend data is loading', () => {
    const componentSource = paritySource.slice(
      paritySource.indexOf('function AvitoOverviewPeriodSegments'),
      paritySource.indexOf('function AvitoOverviewToolbarIsland'),
    )

    expect(componentSource).toContain('const applyPeriod = (period: string)')
    expect(componentSource).toContain('onClick={() => applyPeriod(option.id)}')
    expect(componentSource).not.toContain('disabled={loading}')
  })
})
