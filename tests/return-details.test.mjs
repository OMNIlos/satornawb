import assert from 'node:assert/strict'
import test from 'node:test'

await import('../src/return-details.js')
const { extract } = globalThis.SatornaAvitoReturnDetails

test('return readiness and code need explicit return context', () => {
  assert.deepEqual(extract('Возврат можно забрать. Код получения возврата: 001 234 567'), {
    status: 'ready_for_pickup', pickupCode: '001 234 567',
  })
  assert.deepEqual(extract('Возврат едет обратно. Трек P06516051994'), { status: 'in_transit', pickupCode: null })
  assert.deepEqual(extract('Заказ можно забрать. Номер отправления: 512 526 8946'), { status: null, pickupCode: null })
})
