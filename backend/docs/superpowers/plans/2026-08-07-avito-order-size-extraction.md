# Avito Order Size Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collect an Avito order's final size from the latest 50 chat messages with one backend AI batch request, while supporting strict listing-characteristic mode and description fallback.

**Architecture:** The logged-in extension extracts exact chat channel IDs from the profile-order payload, fetches and bounds the latest 50 messages, and posts `chatText` plus `descriptionSize` in the existing browser snapshot. The backend keeps the existing one-request OpenAI batch, applies AI sizes first, and finalizes unresolved items from `descriptionSize`.

**Tech Stack:** Chrome Manifest V3, browser JavaScript, Node built-in test runner, FastAPI/Pydantic, Python 3, pytest, OpenAI Responses API through `httpx`.

## Global Constraints

- Chat collection is enabled only when `sizeMode == "chat_ai"`.
- Retain at most the latest 50 messages across all channels for one order.
- Retain at most 4,000 chat characters per item, discarding oldest text first.
- Redact URLs and phone-like digit sequences of seven or more digits before posting a snapshot.
- Make exactly one OpenAI Responses API call per browser snapshot, never one call per order.
- AI size has priority; unresolved AI items fall back to `descriptionSize`.
- Description mode must not fetch chat.
- Size parsing requires an explicit `Размер`, `Размер одежды`, or `Size` label.
- Do not change color or seller-article behavior.
- Commit completed changes independently in each repository.

---

### Task 1: Strict Listing Size Parser

**Files:**
- Create: `../avito-orders-extension/src/item-size.js`
- Create: `../avito-orders-extension/tests/item-size.test.mjs`
- Modify: `../avito-orders-extension/package.json`

**Interfaces:**
- Consumes: listing `pageText`, description, or characteristic text as a string.
- Produces: `globalThis.SatornaAvitoItemSize.parseExplicitListingSize(text): string | null`.

- [ ] **Step 1: Write the failing parser tests**

```js
import assert from 'node:assert/strict'
import test from 'node:test'

delete globalThis.SatornaAvitoItemSize
await import(`../src/item-size.js?test=${Date.now()}`).catch(() => {})

const parse = (text) => globalThis.SatornaAvitoItemSize?.parseExplicitListingSize?.(text)

test('parses combined numeric and letter size from characteristics', () => {
  assert.equal(parse('Характеристики\nРазмер: 54 (XL)\nЦвет: Чёрный'), '54 (XL)')
})

test('normalizes explicit letter and range sizes', () => {
  assert.equal(parse('Size: xl'), 'XL')
  assert.equal(parse('Размер одежды: 46–48'), '46-48')
})

test('rejects unrelated numeric dimensions and prose', () => {
  assert.equal(parse('Фото 96 × 96\nЦена 2 139 ₽\nМодель размера oversize'), null)
})
```

- [ ] **Step 2: Run the parser tests and verify RED**

Run:

```powershell
node --test tests/item-size.test.mjs
```

Expected: FAIL because `SatornaAvitoItemSize` and `parseExplicitListingSize` do not exist.

- [ ] **Step 3: Implement the strict parser**

Create `src/item-size.js`:

```js
{
function normalizeSize(value) {
  return String(value || '')
    .trim()
    .replace(/[–—]/g, '-')
    .replace(/\s*-\s*/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/[a-z]+/gi, (part) => part.toUpperCase())
}

function parseExplicitListingSize(text) {
  const value = String(text || '')
  const pattern = /(?:Размер(?:\s+одежды)?|Size)\s*:\s*((?:\d{2}(?:\s*[-–—]\s*\d{2})?)(?:\s*\((?:[2-5]?XL|XXL|XS|[SML])\))?|(?:[2-5]?XL|XXL|XS|[SML]))(?=\s|$|[,.<])/iu
  const match = value.match(pattern)
  return match?.[1] ? normalizeSize(match[1]) : null
}

globalThis.SatornaAvitoItemSize = { parseExplicitListingSize }
}
```

Add `node --check src/item-size.js` to the extension's `check` script.

- [ ] **Step 4: Run parser tests and the extension suite**

Run:

```powershell
node --test tests/item-size.test.mjs
npm test
```

Expected: all parser tests and all existing extension tests PASS.

- [ ] **Step 5: Commit Task 1 in the extension repository**

```powershell
git add -- src/item-size.js tests/item-size.test.mjs package.json
git commit -m "feat: parse explicit Avito listing sizes"
```

---

### Task 2: Channel IDs and Bounded Chat Messages

**Files:**
- Create: `../avito-orders-extension/src/order-chat.js`
- Create: `../avito-orders-extension/tests/order-chat.test.mjs`
- Modify: `../avito-orders-extension/src/page-state.js`
- Modify: `../avito-orders-extension/tests/page-state.test.mjs`
- Modify: `../avito-orders-extension/package.json`

**Interfaces:**
- Consumes: profile-order JSON payloads and Avito messenger JSON responses.
- Produces:
  - `SatornaAvitoPageState.extractChannelIds(payload): string[]`;
  - `loadCandidateForOrderPage(...).channelIds: string[]`;
  - `SatornaAvitoOrderChat.normalizeChatMessages(payloads, limit, maxChars)`;
  - `SatornaAvitoOrderChat.loadOrderChat(channelIds, fetchApi)`;
  - `SatornaAvitoOrderChat.shouldCollectOrderChat(mode, channelIds): boolean`.

- [ ] **Step 1: Write the failing channel-ID test**

Append to `tests/page-state.test.mjs`:

```js
test('returns unique channel ids with the listing candidate', async () => {
  const fetchApi = async () => ({
    ok: true,
    status: 200,
    json: async () => ({
      channel: { channelId: 'u2i-~buyer-item' },
      duplicateAction: 'avito://chat?channelId=u2i-~buyer-item&isMiniMessenger=true',
      widgets: [{
        payload: 'action://open?itemId=8098284629',
        quantity: 1,
        title: 'Лонгслив y2k opium archive anime',
      }],
    }),
  })

  const loaded = await globalThis.SatornaAvitoPageState.loadCandidateForOrderPage(
    'https://www.avito.ru/orders/70000000486515763?source=orders_list',
    'Лонгслив y2k opium archive anime',
    fetchApi,
    'Asia/Yekaterinburg',
  )

  assert.deepEqual(loaded.channelIds, ['u2i-~buyer-item'])
})
```

- [ ] **Step 2: Run the page-state test and verify RED**

Run:

```powershell
node --test tests/page-state.test.mjs
```

Expected: FAIL because `channelIds` is absent.

- [ ] **Step 3: Implement channel-ID extraction in `page-state.js`**

Add:

```js
function extractChannelIds(root) {
  let source = ''
  try {
    source = JSON.stringify(root)
  } catch (_error) {
    return []
  }
  const values = []
  const patterns = [
    /"channelId"\s*:\s*"([^"]+)"/gi,
    /channelId(?:%3D|=)(u2[iI]-[~]?[a-zA-Z0-9_-]+)/gi,
    /(u2[iI]-[~]?[a-zA-Z0-9_-]{8,})/g,
  ]
  for (const pattern of patterns) {
    for (const match of source.matchAll(pattern)) {
      let value = String(match[1] || match[0] || '').split('&')[0]
      try {
        value = decodeURIComponent(value)
      } catch (_error) {
        // Keep the original value.
      }
      if (/^u2[iI]-[~]?[a-zA-Z0-9_-]{8,}$/.test(value) && !values.includes(value)) values.push(value)
    }
  }
  return values
}
```

In `loadCandidatesFromOrderResources`, collect channel IDs from every successful payload and return `channelIds`. In `loadCandidateForOrderPage`, forward `loaded.channelIds`. Export `extractChannelIds`.

- [ ] **Step 4: Write failing message normalization tests**

Create `tests/order-chat.test.mjs`:

```js
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
  assert.equal(result.chatText, 'Смотрите [ссылка]\\nТогда L, телефон [телефон]')
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
```

- [ ] **Step 5: Run message tests and verify RED**

Run:

```powershell
node --test tests/order-chat.test.mjs
```

Expected: FAIL because `SatornaAvitoOrderChat` does not exist.

- [ ] **Step 6: Implement `order-chat.js`**

Implement these exact boundaries:

```js
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
  while (messages.length > 1 && messages.join('\n').length > maxChars) messages.shift()
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
```

Add `node --check src/order-chat.js` to `package.json`.

- [ ] **Step 7: Run Task 2 tests**

Run:

```powershell
node --test tests/page-state.test.mjs tests/order-chat.test.mjs
npm test
```

Expected: all page-state, order-chat, and existing extension tests PASS.

- [ ] **Step 8: Commit Task 2 in the extension repository**

```powershell
git add -- src/page-state.js src/order-chat.js tests/page-state.test.mjs tests/order-chat.test.mjs package.json
git commit -m "feat: collect bounded Avito order chats"
```

---

### Task 3: Extension Size Modes and Snapshot Evidence

**Files:**
- Create: `../avito-orders-extension/src/size-policy.js`
- Create: `../avito-orders-extension/tests/size-policy.test.mjs`
- Modify: `../avito-orders-extension/src/content.js`
- Modify: `../avito-orders-extension/src/background.js`
- Modify: `../avito-orders-extension/manifest.json`
- Modify: `../avito-orders-extension/package.json`

**Interfaces:**
- Consumes:
  - `parseExplicitListingSize(text)`;
  - `loadOrderChat(channelIds, fetchApi)`;
  - `loadCandidateForOrderPage(...).channelIds`.
- Produces:
  - snapshot item fields `size`, `descriptionSize`, `chatText`, and `sources.size`;
  - backend-aware final status for `chat_ai`.

- [ ] **Step 1: Write failing mode-policy tests**

Create `tests/size-policy.test.mjs`:

```js
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
  apply(item, 'chat_ai', '54 (XL)', 'Сначала M\\nНет, тогда L')
  assert.deepEqual(item, {
    descriptionSize: '54 (XL)',
    chatText: 'Сначала M\\nНет, тогда L',
    sources: {},
  })
})

test('none mode removes size evidence', () => {
  const item = { size: 'XL', descriptionSize: 'XL', chatText: 'Беру XL', sources: { size: 'description' } }
  apply(item, 'none', '54 (XL)', 'Беру L')
  assert.deepEqual(item, { size: null, descriptionSize: null, chatText: null, sources: {} })
})
```

- [ ] **Step 2: Run mode-policy tests and verify RED**

Run:

```powershell
node --test tests/size-policy.test.mjs
```

Expected: FAIL because `SatornaAvitoSizePolicy` does not exist.

- [ ] **Step 3: Implement `size-policy.js`**

```js
{
function applySizeEvidence(item, mode, explicitSize, chatText = null) {
  if (!item.sources || typeof item.sources !== 'object') item.sources = {}
  delete item.sources.size
  if (mode === 'none') {
    item.size = null
    item.descriptionSize = null
    item.chatText = null
    return item
  }
  if (mode === 'description') {
    item.size = explicitSize || null
    item.descriptionSize = null
    item.chatText = null
    if (item.size) item.sources.size = 'description'
    return item
  }
  item.size = null
  item.descriptionSize = explicitSize || null
  item.chatText = chatText || null
  return item
}

globalThis.SatornaAvitoSizePolicy = { applySizeEvidence }
}
```

Add `node --check src/size-policy.js` to `package.json`.

- [ ] **Step 4: Wire helpers into `manifest.json`**

Set content script order exactly:

```json
"js": [
  "src/item-size.js",
  "src/order-chat.js",
  "src/size-policy.js",
  "src/page-state.js",
  "src/content.js"
]
```

Change `executeContentScript` in `src/background.js` to inject the same helper files before `src/content.js`.

- [ ] **Step 5: Integrate chat and strict size evidence in `content.js`**

In the direct profile-order resolution block:

```js
let orderChat = null
if (globalThis.SatornaAvitoOrderChat.shouldCollectOrderChat(options.sizeMode, direct?.channelIds)) {
  orderChat = await globalThis.SatornaAvitoOrderChat.loadOrderChat(direct.channelIds, globalThis.fetch)
  logEvent('info', 'order chat collected', {
    orderId: order.orderId,
    channelIds: direct.channelIds.length,
    rawMessages: orderChat.rawCount,
    retainedMessages: orderChat.retainedCount,
    truncated: orderChat.truncated,
    requests: orderChat.requests,
  })
}
if (order.items?.[0] && orderChat?.chatText) order.items[0].chatText = orderChat.chatText
```

Replace `parseSize(text)` use in `mergeItemDetails` with:

```js
const explicitSize = globalThis.SatornaAvitoItemSize.parseExplicitListingSize(text)
globalThis.SatornaAvitoSizePolicy.applySizeEvidence(
  item,
  options.sizeMode,
  explicitSize,
  item.chatText || details.chatText || null,
)
```

Ensure order-row collection never pre-fills a numeric size from arbitrary card text. Keep `sources` on each item.

- [ ] **Step 6: Use backend AI metadata in completion status**

After `postSnapshot(payload)` in `collectAndPostFromAvito`:

```js
const ai = result?.browserSnapshot?.aiExtraction || {}
const sizeText = settings.collectOptions?.sizeMode === 'chat_ai'
  ? ` Размеры: AI ${ai.aiSizeCount || 0}, из характеристик ${ai.descriptionFallbackCount || 0}, не найдено ${ai.missingFinalSizeCount || 0}.`
  : ''
const text = `Собрано заказов: ${meta?.orders ?? payload?.orders?.length ?? 0}.${sizeText}`
```

Log the complete `aiExtraction` object without chat contents.

- [ ] **Step 7: Bump extension version and run checks**

Change `manifest.json` version from `0.1.5` to `0.2.0`.

Run:

```powershell
npm run build
```

Expected: all tests PASS, all `node --check` commands PASS, `Manifest OK`, and `dist/manifest.json` reports `0.2.0`.

- [ ] **Step 8: Commit Task 3 in the extension repository**

```powershell
git add -- src/size-policy.js tests/size-policy.test.mjs src/content.js src/background.js manifest.json package.json
git commit -m "feat: add Avito chat AI size mode"
```

---

### Task 4: Backend Snapshot Size Evidence and Provenance

**Files:**
- Modify: `app/avito/orders.py`
- Modify: `tests/test_avito_orders.py`

**Interfaces:**
- Consumes: browser item fields `descriptionSize` and `sources`.
- Produces: cached and merged `AvitoOrderItem.descriptionSize` and `AvitoOrderItem.sources`.

- [ ] **Step 1: Write the failing model/merge test**

Add to `tests/test_avito_orders.py`:

```python
def test_browser_snapshot_preserves_size_fallback_and_provenance():
    snapshot = AvitoOrdersBrowserSnapshot.model_validate(
        {
            "orders": [
                {
                    "orderId": "order-1",
                    "items": [
                        {
                            "itemId": "8098284629",
                            "title": "Свитшот",
                            "descriptionSize": "54 (XL)",
                            "sources": {"size": "description_fallback"},
                        }
                    ],
                }
            ]
        }
    )
    rows = [
        AvitoOrderRow(
            orderId="order-1",
            items=[AvitoOrderItem(itemId="8098284629", title="Свитшот")],
        )
    ]

    merge_browser_snapshot_orders(rows, snapshot)

    assert snapshot.orders[0].items[0].descriptionSize == "54 (XL)"
    assert rows[0].items[0].descriptionSize == "54 (XL)"
    assert rows[0].items[0].sources == {"size": "description_fallback"}
```

Import `AvitoOrderItem`, `AvitoOrderRow`, `AvitoOrdersBrowserSnapshot`, and `merge_browser_snapshot_orders` from `app.avito.orders` if the test module does not already import them.

- [ ] **Step 2: Run the test and verify RED**

Run:

```powershell
pytest tests/test_avito_orders.py::test_browser_snapshot_preserves_size_fallback_and_provenance -q
```

Expected: FAIL because `descriptionSize` and `sources` are not model fields.

- [ ] **Step 3: Add fields and merge behavior**

Add to both `AvitoOrderItem` and `AvitoOrdersBrowserItem`:

```python
descriptionSize: str | None = None
sources: dict[str, str | None] = Field(default_factory=dict)
```

Extend `_merge_browser_item`:

```python
if browser_item.descriptionSize:
    item.descriptionSize = browser_item.descriptionSize
if browser_item.sources:
    item.sources = {**item.sources, **browser_item.sources}
```

- [ ] **Step 4: Run backend order tests**

Run:

```powershell
pytest tests/test_avito_orders.py -q
```

Expected: the new merge test and all existing Avito order tests PASS.

- [ ] **Step 5: Commit Task 4 in the backend repository**

```powershell
git add -- app/avito/orders.py tests/test_avito_orders.py
git commit -m "feat: preserve Avito size evidence"
```

---

### Task 5: One-Request AI Priority and Description Fallback

**Files:**
- Create: `tests/test_avito_orders_ai.py`
- Modify: `app/avito/orders_ai.py`

**Interfaces:**
- Consumes: `AvitoOrdersBrowserSnapshot` with `chatText`, `descriptionSize`, and collector `sizeMode`.
- Produces:
  - final `item.size`;
  - `item.sources.size`;
  - metadata `aiSizeCount`, `descriptionFallbackCount`, and `missingFinalSizeCount`.

- [ ] **Step 1: Write the failing AI-priority and single-request test**

Create `tests/test_avito_orders_ai.py` with a minimal real response double:

```python
import json
from types import SimpleNamespace

from app.avito.orders import AvitoOrdersBrowserSnapshot
from app.avito.orders_ai import enrich_avito_orders_snapshot_with_ai


class FakeResponse:
    def __init__(self, output: dict):
        self.output = output

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(self.output, ensure_ascii=False)}],
                }
            ]
        }


class RecordingClient:
    base_url = "https://api.openai.com/v1"

    def __init__(self, output: dict):
        self.output = output
        self.posts: list[dict] = []

    def post(self, url: str, **kwargs):
        self.posts.append({"url": url, **kwargs})
        return FakeResponse(self.output)


def snapshot_with_two_sizes() -> AvitoOrdersBrowserSnapshot:
    return AvitoOrdersBrowserSnapshot.model_validate(
        {
            "collector": {"options": {"sizeMode": "chat_ai", "colorFromDescription": False, "articleFromDescription": False}},
            "orders": [
                {
                    "orderId": "order-1",
                    "items": [
                        {
                            "title": "Свитшот",
                            "chatText": "Сначала M\\nНет, тогда L\\nДа, фиксируем L",
                            "descriptionSize": "54 (XL)",
                        },
                        {
                            "title": "Футболка",
                            "chatText": "Какой размер есть?",
                            "descriptionSize": "46 (M)",
                        },
                    ],
                }
            ],
        }
    )

def settings(api_key: str | None):
    return SimpleNamespace(
        openai_api_key=api_key,
        openai_api_base_url="https://api.openai.com/v1",
        openai_review_model="gpt-4o-mini",
        openai_review_timeout_seconds=20.0,
    )


def test_ai_size_wins_and_all_items_use_one_request(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    client = RecordingClient(
        {
            "items": [
                {"key": "0:0", "size": "L", "color": None, "sellerArticle": None, "confidence": "high", "notes": "final confirmation"},
                {"key": "0:1", "size": "S", "color": None, "sellerArticle": None, "confidence": "low", "notes": "uncertain guess"},
            ]
        }
    )

    snapshot, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=client)

    assert len(client.posts) == 1
    assert snapshot.orders[0].items[0].size == "L"
    assert snapshot.orders[0].items[0].sources["size"] == "chat_ai"
    assert snapshot.orders[0].items[1].size == "46 (M)"
    assert snapshot.orders[0].items[1].sources["size"] == "description_fallback"
    assert meta["aiSizeCount"] == 1
    assert meta["descriptionFallbackCount"] == 1
    assert meta["missingFinalSizeCount"] == 0
```

- [ ] **Step 2: Run the AI test and verify RED**

Run:

```powershell
pytest tests/test_avito_orders_ai.py::test_ai_size_wins_and_all_items_use_one_request -q
```

Expected: FAIL because fallback and size provenance are not applied.

- [ ] **Step 3: Write failing missing-key and failed-response fallback tests**

Append:

```python
def test_missing_openai_key_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings(None))
    snapshot = snapshot_with_two_sizes()

    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot)

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "skipped"
    assert meta["descriptionFallbackCount"] == 2
    assert meta["missingFinalSizeCount"] == 0


class FailingClient:
    base_url = "https://api.openai.com/v1"

    def post(self, *_args, **_kwargs):
        raise TimeoutError("timeout")


def test_failed_ai_request_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=FailingClient())

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "failed"
    assert meta["descriptionFallbackCount"] == 2


class MalformedResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"output": []}


class MalformedClient:
    base_url = "https://api.openai.com/v1"

    def post(self, *_args, **_kwargs):
        return MalformedResponse()


def test_malformed_ai_output_still_applies_description_fallback(monkeypatch):
    monkeypatch.setattr("app.avito.orders_ai.get_settings", lambda: settings("test-key"))
    enriched, meta = enrich_avito_orders_snapshot_with_ai(snapshot_with_two_sizes(), client=MalformedClient())

    assert [item.size for item in enriched.orders[0].items] == ["54 (XL)", "46 (M)"]
    assert meta["status"] == "failed"
    assert meta["descriptionFallbackCount"] == 2
```

- [ ] **Step 4: Run fallback tests and verify RED**

Run:

```powershell
pytest tests/test_avito_orders_ai.py -q
```

Expected: FAIL because early-return branches do not finalize `descriptionSize`.

- [ ] **Step 5: Refactor AI enrichment through one finalizer**

Add a helper:

```python
def _finalize_size_fallbacks(
    snapshot: AvitoOrdersBrowserSnapshot,
    metadata: dict[str, Any],
    *,
    ai_size_count: int = 0,
) -> tuple[AvitoOrdersBrowserSnapshot, dict[str, Any]]:
    fallback_count = 0
    missing_count = 0
    options = (snapshot.collector or {}).get("options") if isinstance(snapshot.collector, dict) else {}
    chat_ai = isinstance(options, dict) and options.get("sizeMode") == "chat_ai"
    for order in snapshot.orders:
        for index, item in enumerate(order.items):
            patch: dict[str, Any] = {}
            sources = dict(item.sources or {})
            if not item.size and chat_ai and item.descriptionSize:
                patch["size"] = item.descriptionSize
                sources["size"] = "description_fallback"
                patch["sources"] = sources
                fallback_count += 1
            elif chat_ai:
                missing_count += 1
            if patch:
                order.items[index] = item.model_copy(update=patch)
    return snapshot, {
        **metadata,
        "aiSizeCount": ai_size_count,
        "descriptionFallbackCount": fallback_count,
        "missingFinalSizeCount": missing_count,
    }
```

Apply an AI size only when the returned confidence is `high` or `medium`:

```python
if not item.size and found.get("size") and found.get("confidence") in {"high", "medium"}:
    sources = dict(item.sources or {})
    sources["size"] = "chat_ai"
    patch["size"] = str(found["size"]).strip()
    patch["sources"] = sources
    ai_size_count += 1
```

Route every return from `enrich_avito_orders_snapshot_with_ai` through `_finalize_size_fallbacks`, including missing options, disabled fields, missing key, no extraction candidates, response without text, malformed output, request exceptions, and success.

Build prompt text so recent chat survives bounds:

```python
description = str(item.description or "").strip()[:1500]
chat = str(item.chatText or "").strip()[-4000:]
text = "\n".join(
    part
    for part in (
        f"Название: {item.title}" if item.title else "",
        f"Описание: {description}" if description else "",
        f"Чат: {chat}" if chat else "",
    )
    if part
)[:6000]
```

- [ ] **Step 6: Run AI and Avito order tests**

Run:

```powershell
pytest tests/test_avito_orders_ai.py tests/test_avito_orders.py -q
```

Expected: all new AI tests and existing Avito order tests PASS.

- [ ] **Step 7: Commit Task 5 in the backend repository**

```powershell
git add -- app/avito/orders_ai.py tests/test_avito_orders_ai.py
git commit -m "feat: finalize Avito sizes from chat AI"
```

---

### Task 6: End-to-End Verification and Handoff

**Files:**
- Verify: backend repository working tree and test suite.
- Verify: `../avito-orders-extension` working tree and built `dist`.

**Interfaces:**
- Consumes: completed extension snapshot and backend enrichment contracts.
- Produces: installable extension `0.2.0`, clean repositories, and observable live-run diagnostics.

- [ ] **Step 1: Run the full focused backend verification**

Run:

```powershell
pytest tests/test_avito_orders_ai.py tests/test_avito_orders.py tests/test_avito_chats.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run the complete extension build**

Run from `../avito-orders-extension`:

```powershell
npm run build
```

Expected: all Node tests PASS, syntax checks PASS, `Manifest OK`, and `dist` is rebuilt.

- [ ] **Step 3: Verify built manifest and repository cleanliness**

Run:

```powershell
$manifest = Get-Content -LiteralPath 'dist\manifest.json' -Raw | ConvertFrom-Json
$manifest.version
$manifest.content_scripts[0].js
git status --short
```

Expected:

```text
0.2.0
src/item-size.js
src/order-chat.js
src/size-policy.js
src/page-state.js
src/content.js
```

The extension working tree must be clean after Task 3's commit.

Run from the backend repository:

```powershell
git status --short
git log -3 --oneline
```

Expected: backend working tree is clean and Task 4/Task 5 commits are present.

- [ ] **Step 4: Perform the authenticated browser smoke test**

1. Open `chrome://extensions`.
2. Reload the unpacked extension from `../avito-orders-extension/dist`.
3. Fully refresh `https://www.avito.ru/orders`.
4. Select `Из чата с AI ✨`.
5. Collect the current orders once.
6. Confirm logs show `order chat collected` with `retainedMessages <= 50`.
7. Confirm completion status reports AI, description fallback, and missing counts.
8. Open `/avito/orders` and confirm:
   - a changed chat decision uses the final confirmed size;
   - an order without usable chat uses the listing characteristic;
   - no image dimension, order number, or price appears as a size.

- [ ] **Step 5: Record live evidence without another code commit**

Save or attach the extension logs containing:

```text
order chat collected
snapshot posted
collection finished
```

Do not include raw chat contents in logs or the handoff.
