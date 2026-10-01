import assert from 'node:assert/strict'
import test from 'node:test'

delete globalThis.SatornaAvitoSizePolicy
await import(`../src/size-policy.js?test=${Date.now()}`).catch(() => {})

const apply = (item, mode, explicitSize, chatText = null) => (
  globalThis.SatornaAvitoSizePolicy?.applySizeEvidence?.(item, mode, explicitSize, chatText)
)

test('description mode sets final size and provenance', () => {
  const item = { sources: {} }
  apply(item, 'description', '54 (XL)')
  assert.deepEqual(item, { size: '54 (XL)', sources: { size: 'description' } })
})

test('chat AI mode keeps description only as fallback evidence', () => {
  const item = { sources: {} }
  apply(item, 'chat_ai', '54 (XL)', 'Сначала M\nНет, тогда L')
  assert.deepEqual(item, {
    descriptionSize: '54 (XL)',
    chatText: 'Сначала M\nНет, тогда L',
    sources: {},
  })
})

test('none mode removes size evidence', () => {
  const item = { size: 'XL', descriptionSize: 'XL', chatText: 'Беру XL', sources: { size: 'description' } }
  apply(item, 'none', '54 (XL)', 'Беру L')
  assert.deepEqual(item, { size: null, descriptionSize: null, chatText: null, sources: {} })
})

test('a later page without size does not erase already collected explicit size', () => {
  const item = { sources: {} }
  apply(item, 'description', '48 (M)')
  apply(item, 'description', null)
  assert.equal(item.size, '48 (M)')
  assert.equal(item.sources.size, 'description')
})
