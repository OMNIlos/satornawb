import test from 'node:test'
import assert from 'node:assert/strict'
await import('../src/labels.js')
const { downloadUrl, boundedPdf, selectAndGenerate } = globalThis.SatornaLabels

test('only accepts original Avito order-label download routes', () => {
  assert.equal(downloadUrl('/web/1/orders/labels/test-task/download'), 'https://www.avito.ru/web/1/orders/labels/test-task/download')
  for (const url of ['https://evil.test/web/1/orders/labels/a/download', 'http://www.avito.ru/web/1/orders/labels/a/download', 'https://www.avito.ru@evil.test/web/1/orders/labels/a/download', '/orders/confirm', 'javascript:alert(1)', '/web/1/orders/labels/../download']) assert.equal(downloadUrl(url), null)
})

test('download verifies PDF magic and bounded size', async () => {
  assert.equal(new TextDecoder().decode(await boundedPdf(new Response('%PDF-1.7\ntest'))), '%PDF-1.7\ntest')
  await assert.rejects(() => boundedPdf(new Response('<html>login</html>')), /Вместо PDF/)
  await assert.rejects(() => boundedPdf(new Response(new Uint8Array(12000001))), /12 МБ/)
  await assert.rejects(() => boundedPdf(new Response('denied', { status: 403 })), /не отдало/)
})

test('generation refuses a non-label page before selecting anything', async () => {
  globalThis.location = { origin: 'https://www.avito.ru', pathname: '/orders/confirm' }
  await assert.rejects(selectAndGenerate, /страницу печати/)
  delete globalThis.location
})

test('selects unchecked labels and invokes only generation, never physical print', async () => {
  const oldTimeout = globalThis.setTimeout
  const boxes = [false, true, false].map(checked => ({ checked, disabled: false, getAttribute: () => null, click() { this.checked = true } }))
  let generated = 0
  globalThis.location = { origin: 'https://www.avito.ru', pathname: '/orders/print-labels' }
  globalThis.window = { scrollTo() {}, print() { throw new Error('must not print') } }
  globalThis.document = { documentElement: { scrollHeight: 1000 }, querySelectorAll(selector) {
    return selector.startsWith('input') ? boxes : [{ textContent: 'Распечатать 3 этикетки', click() { generated++ } }]
  } }
  globalThis.setTimeout = callback => { callback(); return 1 }
  try {
    assert.equal(await selectAndGenerate(), 3)
    assert.equal(generated, 1)
    assert.ok(boxes.every(box => box.checked))
  } finally {
    globalThis.setTimeout = oldTimeout
    delete globalThis.location; delete globalThis.window; delete globalThis.document
  }
})
