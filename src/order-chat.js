{
function messageText(message) {
  const value = message?.body?.text?.text
    ?? message?.content?.text
    ?? message?.text
    ?? (typeof message?.body?.text === 'string' ? message.body.text : '')
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').trim() : ''
}

function redactMessage(text) {
  return String(text || '')
    .replace(/https?:\/\/\S+/giu, '[ссылка]')
    .replace(/(?:\+?\d[\s()\-]*){7,}/gu, '[телефон]')
    .replace(/\s+/g, ' ')
    .trim()
}

function normalizeChatMessages(payloads, limit = 50, maxChars = 4000) {
  const rows = []
  for (const payload of payloads || []) {
    const messages = payload?.success?.messages || payload?.messages || payload?.result?.messages || []
    for (const message of messages) {
      const text = redactMessage(messageText(message))
      if (!text) continue
      const rawCreated = message?.created || message?.createdAt || message?.timestamp || 0
      const numericCreated = Number(rawCreated)
      rows.push({
        id: String(message?.id || ''),
        created: Number.isFinite(numericCreated) ? numericCreated : Date.parse(String(rawCreated)) || 0,
        text,
      })
    }
  }
  rows.sort((left, right) => left.created - right.created)
  const unique = rows.filter((row, index, all) => (
    all.findIndex((value) => (
      (value.id && row.id && value.id === row.id) || value.text === row.text
    )) === index
  ))
  let messages = unique.slice(-Math.max(1, limit)).map((row) => row.text)
  let truncated = unique.length > messages.length
  while (messages.length > 1 && messages.join('\n').length > maxChars) {
    messages.shift()
    truncated = true
  }
  let chatText = messages.join('\n')
  if (chatText.length > maxChars) {
    chatText = chatText.slice(-maxChars)
    truncated = true
  }
  return {
    messages,
    chatText: chatText || null,
    rawCount: rows.length,
    retainedCount: messages.length,
    truncated: truncated || rows.length > unique.length,
  }
}

async function loadOrderChat(channelIds, fetchApi = globalThis.fetch) {
  const payloads = []
  const requests = []
  for (const channelId of Array.from(new Set(channelIds || []))) {
    try {
      const response = await fetchApi('https://www.avito.ru/web/1/messenger/getUserVisibleMessages', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channelId, limit: 50, order: 0 }),
      })
      requests.push({ channelId, status: Number(response?.status || 0) })
      if (response?.ok) payloads.push(await response.json())
    } catch (error) {
      requests.push({ channelId, status: 0, error: error instanceof Error ? error.message : String(error) })
    }
  }
  return { ...normalizeChatMessages(payloads, 50, 4000), requests }
}

function shouldCollectOrderChat(mode, channelIds) {
  return mode === 'chat_ai' && Array.isArray(channelIds) && channelIds.length > 0
}

globalThis.SatornaAvitoOrderChat = {
  normalizeChatMessages,
  loadOrderChat,
  shouldCollectOrderChat,
}
}
