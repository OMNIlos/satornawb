import assert from 'node:assert/strict'
import test from 'node:test'

delete globalThis.SatornaAvitoOrderChat
await import(`../src/order-chat.js?test=${Date.now()}`).catch(() => {})

test('keeps only the latest 50 messages in chronological order', () => {
  const newestFirst = Array.from({ length: 55 }, (_, index) => ({
    id: `m-${55 - index}`,
    created: 55 - index,
    body: { text: { text: `message ${55 - index}` } },
  }))
  const result = globalThis.SatornaAvitoOrderChat?.normalizeChatMessages?.(
    [{ success: { messages: newestFirst } }],
    50,
    4000,
  )

  assert.equal(result.messages.length, 50)
  assert.equal(result.messages[0], 'message 6')
  assert.equal(result.messages[49], 'message 55')
})

test('deduplicates and redacts chat text', () => {
  const payload = {
    success: {
      messages: [
        { id: '2', created: 2, text: 'Тогда L, телефон +7 999 123-45-67' },
        { id: '1', created: 1, text: 'Смотрите https://example.com' },
        { id: '1-copy', created: 1, text: 'Смотрите https://example.com' },
      ],
    },
  }
  const result = globalThis.SatornaAvitoOrderChat?.normalizeChatMessages?.([payload], 50, 4000)

  assert.deepEqual(result.messages, ['Смотрите [ссылка]', 'Тогда L, телефон [телефон]'])
  assert.equal(result.chatText, 'Смотрите [ссылка]\nТогда L, телефон [телефон]')
})

test('description mode never enables chat collection', () => {
  assert.equal(
    globalThis.SatornaAvitoOrderChat?.shouldCollectOrderChat?.('description', ['u2i-~buyer-item']),
    false,
  )
  assert.equal(
    globalThis.SatornaAvitoOrderChat?.shouldCollectOrderChat?.('chat_ai', ['u2i-~buyer-item']),
    true,
  )
})
