import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const empty = { status: 'disconnected', totalOffers: 0, observedOffers: 0, accepted: 0, ignored: 0, unmatched: 0, partialSellers: 0 }
async function load(initial = empty, failCommand = false) {
  let state = initial
  const elements = new Map(); const sent = []
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, { value: '', textContent: '', disabled: false, hidden: false, handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn } })
    return elements.get(id)
  }
  const context = vm.createContext({ Date, Number, document: { getElementById: element }, setInterval: () => 1,
    chrome: { runtime: { sendMessage: async (message) => {
      sent.push(message)
      if (failCommand && message.type !== 'status') throw new Error('private transport detail')
      if (message.type === 'connect') state = { ...empty, status: 'ready', totalOffers: 4 }
      return { ok: true, state, forbiddenEcho: '<script>secret</script>' }
    } } } })
  const path = new URL('../src/popup.js', import.meta.url)
  assert.ok(existsSync(path), 'popup is implemented')
  vm.runInContext(readFileSync(path, 'utf8'), context)
  await new Promise((resolve) => setImmediate(resolve))
  return { element, sent }
}

test('a pasted token alone never presents connected state, and verified connect clears its input', async () => {
  const h = await load()
  h.element('token').value = `sat_wbp_${'a'.repeat(43)}`
  assert.equal(h.element('start').disabled, true)
  assert.match(h.element('status').textContent, /Не подключено/)
  await h.element('connect-form').handlers.submit({ preventDefault() {} })
  assert.match(h.element('status').textContent, /Каталог проверен/)
  assert.equal(h.element('start').disabled, false)
  assert.equal(h.element('token').value, '')
})

test('partial coverage and server acknowledgements remain distinct and unknown error text is never rendered', async () => {
  const h = await load({ ...empty, status: 'complete', totalOffers: 5, observedOffers: 2, accepted: 1, ignored: 1,
    reason: '<script>secret</script>', lastAckAt: '2026-09-16T09:00:00Z' })
  assert.equal(h.element('coverage').textContent, '2 / 5')
  assert.equal(h.element('missing').textContent, '3')
  assert.equal(h.element('accepted').textContent, '1')
  assert.equal(h.element('ignored').textContent, '1')
  assert.equal(h.element('reason').textContent.includes('secret'), false)
})

test('waiting cycle can be stopped and displays the next run without claiming full coverage', async () => {
  const h = await load({ ...empty, status: 'waiting', totalOffers: 5, observedOffers: 2, reason: 'partial_coverage', nextRunAt: Date.now() + 1200000 })
  assert.equal(h.element('stop').disabled, false)
  assert.match(h.element('status').textContent, /Следующий проход/)
  assert.match(h.element('next-run').textContent, /20 минут|Следующий/)
  assert.equal(h.element('coverage').textContent, '2 / 5')
})

test('command transport failure remains visible after busy state clears, without raw details', async () => {
  const h = await load(empty, true)
  await h.element('connect-form').handlers.submit({ preventDefault() {} })
  assert.match(h.element('reason').textContent, /Фоновый процесс/)
  assert.equal(h.element('reason').textContent.includes('private'), false)
})
