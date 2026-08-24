import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(
  join(process.cwd(), 'src/features/vella-parity/VellaHtmlParityPage.tsx'),
  'utf8',
)

describe('cold sync stage badge', () => {
  it('does not call a partially loaded stage an error', () => {
    // The backend reports state="partial" with error=null for a window that is
    // still filling in.  Rendering that as "ошибка" told users a load had
    // failed when nothing had - the 30-day stage showed an error while its
    // report rendered real numbers.
    expect(source).not.toContain("const isError = state === 'partial' || state === 'error'")
    expect(source).toContain("const isPartial = state === 'partial'")
    expect(source).toContain("isPartial ? 'частично'")
  })
})
