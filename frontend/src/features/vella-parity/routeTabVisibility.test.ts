import { describe, expect, it } from 'vitest'

import { enforceRouteTabVisibility } from './VellaHtmlParityPage'

describe('enforceRouteTabVisibility', () => {
  it('hides WB tabs and keeps the Avito orders tab visible on /avito/orders', () => {
    const elements = new Map([
      ['tab-products', fakeTabElement('tab-products', true)],
      ['tab-work-status', fakeTabElement('tab-work-status', true)],
      ['tab-orders-print', fakeTabElement('tab-orders-print', false)],
    ])
    const root = {
      dataset: {} as Record<string, string>,
      querySelectorAll: (selector: string) => selector === '.tab-content' ? Array.from(elements.values()) : [],
    } as unknown as HTMLElement

    enforceRouteTabVisibility(root, 'orders-avito')

    expect(root.dataset.vellaActiveTab).toBe('orders-avito')
    expect(elements.get('tab-products')?.hidden).toBe(true)
    expect(elements.get('tab-products')?.classList.contains('active')).toBe(false)
    expect(elements.get('tab-work-status')?.hidden).toBe(true)
    expect(elements.get('tab-orders-print')?.hidden).toBe(false)
    expect(elements.get('tab-orders-print')?.classList.contains('active')).toBe(true)
  })
})

function fakeTabElement(id: string, active: boolean) {
  const classes = new Set(active ? ['tab-content', 'active'] : ['tab-content'])
  return {
    id,
    hidden: false,
    classList: {
      add: (value: string) => classes.add(value),
      remove: (value: string) => classes.delete(value),
      toggle: (value: string, force?: boolean) => {
        if (force === false) {
          classes.delete(value)
          return false
        }
        classes.add(value)
        return true
      },
      contains: (value: string) => classes.has(value),
    },
    dataset: {} as Record<string, string>,
  } as unknown as HTMLElement
}
