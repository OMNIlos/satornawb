import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const source = readFileSync(join(process.cwd(), 'public/vella-production.html'), 'utf8')

describe('updateSelection', () => {
  it('tolerates the products table being unmounted', () => {
    // Leaving the products tab unmounts #bulkBar and #cbAll, but a queued
    // renderTable() still runs.  Dereferencing them unguarded threw
    // "Cannot read properties of null (reading 'classList')", which unmounted
    // the whole React tree - the white screen users hit when switching tabs.
    const body = source.slice(source.indexOf('function updateSelection()'))
    const fn = body.slice(0, body.indexOf('\nfunction '))

    // Every node it touches must be behind a guard.
    expect(fn).toContain('if (!bar) return')
    expect(fn).toMatch(/if \(cbAll\)/)
    expect(fn).toMatch(/if \(bulkCount\)/)
    // and nothing may be dereferenced before that first guard runs
    const beforeGuard = fn.slice(0, fn.indexOf('if (!bar) return'))
    expect(beforeGuard).not.toMatch(/\.classList|\.textContent|\.innerHTML/)
  })
})
