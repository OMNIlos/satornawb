import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('./VellaHtmlParityPage.tsx', import.meta.url), 'utf8')
const productsLoader = source.slice(
  source.indexOf('async function loadProductsPageFromRuntime'),
  source.indexOf('function formatPromoNumber'),
)

describe('Products live loading source', () => {
  it('renders SKU rows before loading the slower price changes KPI', () => {
    const render = productsLoader.indexOf('applyLiveProductsToRuntime(payload.products')
    expect(render).toBeGreaterThanOrEqual(0)
    expect(render).toBeLessThan(productsLoader.indexOf('loadProductsPriceChangesCountInBackground', render))
  })

  it('finalizes product loads with the returned payload so empty state cannot flicker before rows sync', () => {
    expect(source).toContain('function finalizeProductsBackendLoad(result?: { products?: unknown[]')
    expect(source).toContain('const loadedTotal = Array.isArray(result?.products) ? result.products.length : null')
    expect(source).toContain('finalizeProductsBackendLoad(result)')
    expect(source).toContain('finalizeProductsBackendLoad(loaded)')
  })

  it('keeps the products page vertically scrollable on short viewports', () => {
    expect(source).toContain('.vella-html-parity-root #tab-products.tab-content {')
    expect(source).toContain('overflow-y: auto !important;')
    expect(source).toContain('flex: 1 0 min(720px, calc(100vh - 220px));')
    expect(source).toContain('@media (max-height: 760px)')
    expect(source).toContain('min-height: min(440px, calc(100vh - 126px));')
  })
})
