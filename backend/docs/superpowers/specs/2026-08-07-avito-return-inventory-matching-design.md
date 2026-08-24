# Avito Return Inventory Matching Design

## Goal

Build a backend-backed Avito return inventory that periodically captures returned order items and enriches the Avito orders response with reuse suggestions. A returned item becomes reusable as soon as Avito exposes the order with status `on_return` or a non-empty `returnStatus`; physical warehouse acceptance is not required in this version.

## Architecture

The current Avito orders flow stays the primary source for order rows: `GET /api/v1/avito/orders` calls Avito Order Management, enriches rows from browser snapshots/listings, and caches the response. The new return inventory lives beside it in `app/avito/returns.py` and a dedicated database table so reusable return candidates survive normal response-cache expiry and can be matched across pages and sync runs.

Celery Beat runs an Avito returns sync task for every organization with Avito credentials. The sync fetches recent Avito orders, selects orders with `status == "on_return"` or `returnStatus`, normalizes each item, and upserts it by `organization_id + account_id + order_id + item_id`. The orders endpoint reads active return candidates and adds match metadata to each order item before returning JSON.

## Data Model

Add `avito_return_items`:

- `return_item_id`: integer primary key.
- `organization_id`: required organization id.
- `account_id`: nullable Avito account id.
- `account_name`: nullable display name.
- `order_id`: required Avito order id.
- `marketplace_id`: nullable Avito marketplace order number.
- `item_id`: nullable Avito item/listing id.
- `title`: required item title.
- `seller_article`: nullable seller article.
- `size`: nullable size.
- `color`: nullable color.
- `quantity`: non-negative quantity.
- `status`: source order status, normally `on_return`.
- `return_status`: nullable source return status.
- `source_updated_at`: nullable timestamp/text from Avito.
- `first_seen_at`, `last_seen_at`: UTC timestamps.
- `last_payload`: JSON copy of the normalized return item.

Use a unique constraint on `organization_id, account_id, order_id, item_id` with empty strings substituted for nullable identity parts in the store layer, or an equivalent stable identity key if Postgres nullable uniqueness would allow duplicates.

## Matching Rules

Normalize text by trimming, lowercasing, replacing `ё` with `е`, collapsing whitespace, and stripping punctuation that does not carry product meaning. Color aliases should treat Russian/English and grammatical variants as equal for the known base colors: black/черный/чёрный, white/белый/белая, milk/молочный, graphite/графит.

Match score:

- `sellerArticle + size + color` all equal: score `100`, reason `article_size_color`.
- `title + size + color` all equal: score `90`, reason `title_size_color`.
- `sellerArticle + size` equal and both colors missing: score `82`, reason `article_size_color_missing`.
- `title + size` equal and both colors missing: score `72`, reason `title_size_color_missing`.

Do not match when size conflicts or color conflicts. Do not suggest a return item to its own original order. Return only active candidates from `on_return`/`returnStatus` inventory.

## API Contract

Extend `AvitoOrderItem` with:

- `returnMatches: list[AvitoReturnMatch] = []`
- `reuseSuggestion: AvitoReturnMatch | None = None`

`AvitoReturnMatch` fields:

- `returnOrderId`
- `marketplaceId`
- `itemId`
- `title`
- `sellerArticle`
- `size`
- `color`
- `quantity`
- `score`
- `reason`
- `status`
- `returnStatus`
- `lastSeenAt`

The orders response source metadata gets `returnInventory` with `status`, `candidates`, and `lastSyncedAt` when available.

## Sync Behavior

Add tasks:

- `avito.sync_returns_for_org(organization_id: int, scenario: str = "complete", force: bool = False)`
- `avito.sync_returns_all_orgs(scenario: str = "complete")`

The task uses organization-level Avito credentials, resolves an access token, fetches recent orders with `statuses=["on_return"]`, and also scans a general recent order page as fallback because Avito return fields are not fully confirmed. The default lookback is 30 days and interval is 15 minutes.

On Avito auth/scope/rate-limit errors, save a sync status payload in source cache under `avito_returns_sync_status` and do not delete existing candidates. On successful sync, update `last_seen_at` for found candidates and keep older candidates until a later manual/automated reconciliation proves they are no longer reusable.

## Frontend Behavior

The existing `/avito/orders` UI should show the backend-provided suggestion near the matching item: "В возврате есть такой же товар" with size/color/article evidence and a lightweight action label "Использовать возврат". This first version does not reserve inventory or perform a mutating action; the button can be a non-mutating UI affordance until a reservation workflow is designed.

## Testing

Backend tests cover:

- extracting `on_return` rows into return candidates;
- upserting candidates without duplicates;
- matching by article/size/color;
- refusing matches on conflicting color or size;
- enriching `/api/v1/avito/orders` rows with `reuseSuggestion`.

Frontend tests, when the UI change is implemented, should assert that the suggestion copy appears only when the API item contains `reuseSuggestion`.

## Out Of Scope

This design does not implement QR-code generation, courier tables, physical warehouse acceptance, return reservation, or inventory decrement. Those can layer on top of the persisted return inventory later.
