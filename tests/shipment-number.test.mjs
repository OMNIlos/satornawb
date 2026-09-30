import assert from 'node:assert/strict'
import test from 'node:test'

await import('../src/shipment-number.js')
const { extract } = globalThis.SatornaAvitoShipmentNumber

test('accepts only a labelled dispatch number in the order block', () => {
  assert.deepEqual(extract('Заказ 7000000048 Телефон 89123456789 Трек P06516051994 На месте назовите номер отправления: 001 526 8946'), {
    number: '001 526 8946', state: 'confirmed',
  })
  assert.deepEqual(extract('Заказ 7000000048 Трек P06516051994 Баркод 123456789'), { number: null, state: 'missing' })
  assert.deepEqual(extract('Номер отправления: AB-001 526 8946'), { number: 'AB-001 526 8946', state: 'confirmed' })
  assert.deepEqual(extract('Номер отправления: 00123 Номер отправления: 00987'), { number: null, state: 'ambiguous' })
})
