# Avito Order Size Extraction Design

## Goal

Provide two explicit size collection modes for Avito orders:

- `description`: read the declared size from the listing characteristics;
- `chat_ai`: use the final buyer-confirmed size from the order chat, with the listing characteristic as a mandatory fallback.

The result must populate the existing order snapshot before `/avito/orders` and the picking-list export consume it.

## Existing Capabilities

The extension already exposes `none`, `description`, and `chat_ai` modes. It already opens the resolved listing page and sends a browser snapshot to `POST /api/v1/avito/orders/browser-snapshot`.

The backend already batches all snapshot items that need AI extraction into one OpenAI Responses API request. It uses structured JSON output and can select the final confirmed size when the conversation contains changed decisions.

The missing boundary is chat delivery. After item resolution moved to the stable orders-list API, the extension no longer opens an order detail page that happens to contain chat DOM. Consequently, `chatText` is empty and the existing backend AI path has no evidence to analyze.

## Selected Architecture

Use the logged-in browser session to fetch the exact order chat, then keep AI analysis on the backend.

For each order, the extension will:

1. Request the existing Avito profile-order resource from the `/orders` content script.
2. Extract the listing candidate and all valid `channelId` values from the same response.
3. In `chat_ai` mode only, request visible messages from:

   `POST https://www.avito.ru/web/1/messenger/getUserVisibleMessages`

   with body:

   ```json
   {
     "channelId": "<channel-id>",
     "limit": 50,
     "order": 0
   }
   ```

4. Normalize messages into chronological order, merge duplicate messages, and retain no more than the latest 50 messages in total for the order.
5. Attach the bounded conversation as `item.chatText`.
6. Parse the listing characteristic into `item.descriptionSize`, without setting `item.size` in `chat_ai` mode.
7. Send all collected orders in the existing browser snapshot request.

The backend will run the existing single batch OpenAI request. For each item it will set:

- `size` from the AI result when a final chat choice is returned;
- otherwise `size` from `descriptionSize`;
- otherwise `size` remains `null`.

This keeps exact Avito session access in the extension and centralized reasoning, prompt control, observability, and API credentials in the backend.

## Mode Semantics

### `none`

- Do not fetch chat messages.
- Do not parse or return a size.
- Size is not counted as missing.

### `description`

- Do not fetch chat messages.
- Parse size only from an explicit listing characteristic labelled `Размер` or `Size`.
- Set `item.size` directly.
- Set `item.sources.size` to `description`.

### `chat_ai`

- Fetch at most the latest 50 messages for the order.
- Parse and retain the explicit listing size as `item.descriptionSize`.
- Leave `item.size` empty in the extension so the AI result has priority.
- After backend AI analysis:
  - use the AI size and set `item.sources.size` to `chat_ai`;
  - if AI is unavailable, fails, is uncertain, or returns no size, use `descriptionSize` and set `item.sources.size` to `description_fallback`.

The selected fallback is intentionally permissive: choosing `chat_ai` guarantees a concrete listing size whenever the listing exposes one, even when the chat cannot be analyzed.

## Strict Listing Size Parsing

The parser must use explicit characteristic evidence and must not scan arbitrary numeric page text.

Accepted examples:

- `Размер: 54 (XL)` → `54 (XL)`
- `Размер: XL` → `XL`
- `Size: M` → `M`
- `Размер одежды: 46–48` → `46-48`

Rejected examples:

- image dimensions such as `96 × 96`;
- prices, delivery codes, order numbers, and item IDs;
- sizes mentioned only in the title or unrelated description prose;
- generic measurements without a `Размер` or `Size` label.

The characteristic value is normalized by trimming whitespace, normalizing dash characters, and uppercasing Latin letter sizes while preserving combined values such as `54 (XL)`.

## Chat Extraction and Bounds

The profile-order payload may expose more than one `channelId`. The extension may query each unique valid channel, but it must deduplicate the resulting messages and retain at most the latest 50 messages across the whole order.

Supported message text locations include:

- `body.text.text`;
- `content.text`;
- `text`;
- string-valued `body.text`.

Messages returned newest-first are reversed into chronological order before serialization. Empty and duplicate messages are removed. The serialized `chatText` keeps the newest evidence when applying a 4,000-character per-item bound; older messages are discarded first.

Phone-like digit sequences of seven or more digits and URLs are redacted before the snapshot is posted. Product titles, order IDs, item IDs, channel IDs, message timestamps, and normalized message text are sufficient for correlation and analysis.

## Backend AI Contract

The existing structured response schema remains the authority for AI output. The batch contains only items where `sizeMode == "chat_ai"` and `item.size` is empty.

Each AI item includes:

- stable batch key (`orderIndex:itemIndex`);
- order and marketplace identifiers;
- product title;
- `needSize: true`;
- chronological bounded `chatText`.

The system instruction must continue to require the final confirmed selection, account for changed decisions, and return `null` rather than invent a size.

All eligible items from one browser snapshot are sent in one OpenAI Responses API request. No per-order OpenAI calls are introduced.

Fallback application runs even when:

- `OPENAI_API_KEY` is missing;
- there is no usable chat text;
- the OpenAI request fails or times out;
- structured output is absent or malformed;
- a particular item is omitted from the AI response;
- the returned size is null.

## Data Model

Add an optional snapshot item field:

```json
{
  "descriptionSize": "54 (XL)"
}
```

Continue using the existing `sources` object for provenance:

```json
{
  "sources": {
    "size": "chat_ai"
  }
}
```

Allowed size provenance values are:

- `description`;
- `chat_ai`;
- `description_fallback`.

`descriptionSize` is supporting evidence and is not displayed as the selected production size.

The backend browser-item and final order-item models must preserve the optional `sources` object so provenance survives cache storage, row merging, and XLSX preparation.

## Error Handling and Diagnostics

Chat failures never abort order collection or listing enrichment.

Extension diagnostics record:

- number of extracted channel IDs;
- chat request status per channel;
- number of raw and retained messages;
- whether truncation occurred;
- whether `descriptionSize` was found.

The existing backend `aiExtraction` metadata continues to report `completed`, `skipped`, or `failed`, plus sent, returned, and updated item counts. Add `aiSizeCount`, `descriptionFallbackCount`, and `missingFinalSizeCount` so a run can distinguish AI-derived sizes, description fallbacks, and unresolved items.

`POST /api/v1/avito/orders/browser-snapshot` already returns `browserSnapshot.aiExtraction`. The extension background worker must read these final counts and use them for the completion status in `chat_ai` mode. It must not claim an AI size was found before the snapshot response is processed.

## Components and Repository Scope

### Extension: `../avito-orders-extension`

- Extend `src/page-state.js` to extract channel IDs and fetch/normalize the latest 50 chat messages.
- Tighten listing size parsing in a small testable module rather than expanding arbitrary page-text matching.
- Update `src/content.js` to implement the three mode semantics and include `descriptionSize` and chat diagnostics in the snapshot.
- Update `src/background.js` to display the backend `aiExtraction` result after snapshot posting.
- Keep the existing popup choices; only explanatory copy may change.
- Add focused Node tests for channel extraction, message normalization/bounds/redaction, and strict size parsing.

### Backend: current repository

- Extend browser and final order item models with optional `descriptionSize` and `sources`.
- Refactor `app/avito/orders_ai.py` so description fallback is finalized independently of OpenAI availability.
- Preserve one OpenAI request per snapshot.
- Add tests for changed chat decisions, missing/failed AI, description fallback, and provenance.

### Frontend: `../ogni-react-frontend`

No new control is required because mode selection lives in the extension popup. The frontend must continue rendering the final `item.size`; it may expose `sources.size` later, but provenance UI is outside this feature.

## Testing

Extension tests cover:

1. profile-order payload yields all unique valid channel IDs;
2. newest-first API messages become chronological;
3. only the latest 50 messages are retained;
4. duplicate and empty messages are removed;
5. URLs and phone-like sequences are redacted;
6. `Размер: 54 (XL)` parses exactly;
7. unrelated `96 × 96` does not become a size;
8. `description` mode does not fetch chat;
9. `chat_ai` retains `descriptionSize` without pre-filling `size`.

Backend tests cover:

1. one snapshot with multiple items makes one OpenAI request;
2. chat changing from `M` to confirmed `L` applies `L`;
3. AI null falls back to `54 (XL)`;
4. missing API key still applies description fallback;
5. failed or malformed OpenAI response still applies description fallback;
6. an AI result takes priority over a conflicting `descriptionSize`;
7. AI success records `chat_ai`, direct description mode records `description`, and AI fallback records `description_fallback`.

## Out of Scope

- Publishing the extension to Chrome Web Store.
- AI analysis inside the extension.
- Fetching every Avito inbox chat through the backend and heuristically matching it to orders.
- Changes to color or seller-article extraction.
- Displaying confidence scores or chat contents in the Satorna frontend.
