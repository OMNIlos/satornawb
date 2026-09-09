# T3: Catalog, bound snapshots и dormant read HTTP

Продолжение `9d1f88b`. Общая очередь НЕ активирована; Production parity не заявляется.
Код живёт в T3 worktree/branch, shared registration/config/ORM/migrations не менялись.

## Реализовано

- Exact account/org Product -> Offer -> SKU lookup. Несколько offers неоднозначны,
  даже при одинаковом SKU; leading-zero IDs не преобразуются. Изменённый Catalog
  fingerprint даёт stale, manual assignment не подменяется автоматическим resolution.
- Первичная projection получает доказанный exact Catalog match вместо default unmapped.
  Никакого title/size/color matching или новой Product/Offer копии.
- `freeze_orders_view` принимает explicit coverage run на account, собственную guarded
  transaction и сохраняет immutable item-scoped view. Partial/changed source evidence
  блокирует readiness; current projection не регрессирует и старые snapshots неизменны.
  Проверяется полный набор current memberships/items, а не только найденные join rows.
- Coverage намеренно partial: structural manifest не доказывает provider completeness.
  Mixed source/adapter в одном account fail-closed до versioned coverage contract.
  `source_readiness_unproven`, `coverage_unproven`, Catalog/status/reconciliation blockers
  явные; deadlines пусты, когда provenance отсутствует. WB feed не становится FBS ready.
- HMAC cursor v1 связан с org/user/membership/session, exact account IDs, query checksum,
  snapshot и position. Strict canonical parsing, no trim/aliases, safe error без token echo.
- Frozen mark v2 связывает view с org/account/provider/external ID/exact nullable ref.
  Latest/explicit/cursor read отвергают старый snapshot после account rebind.
  Assembly также проверяет stamp selected coverage run и каждого current projection run.
  Unbound legacy history не backfill из current metadata и не принимается guarded read.
- `app/orders/router.py`: dormant typed `GET /api/v2/orders`, настоящая existing bearer
  auth dependency, canonical membership/account metadata discovery, затем повторный live
  guard до commit/return. Stale ActorContext.permissions не являются разрешением.
  GET не вызывает provider, не строит snapshot и не пишет Orders business state.
  Existing authentication resolver обновляет session last_seen_at: это не нулевое число
  SQL writes на всём request path; shared auth behavior не изменён.
- Pure Production AssignmentCommand byte codec соответствует ранее запрошенному schema1:
  ASCII escaped sorted compact JSON, exact replay decode, SHA256; без persistence/actor input.

## HTTP handoff T1/T4

Router object: `app.orders.router.router`, prefix уже `/api/v2/orders`.
Registration НЕ выполнена. До activation нужен immutable source binding (request `0b8ae9d`)
и T1 physical-root guard followup; никакие feature flags не включены.

Query: repeated positive `account_id` (все должны быть доступны, без silent omission),
`query_checksum` prepublished view, optional `snapshot_id` ИЛИ `cursor`, limit1..200.
Если selector отсутствует, под guard выбирается последний published storage snapshot
того же exact scope/query. Это не выбор последнего provider event по timestamp.
query_checksum является selector, не реализацией UI filters. Supported filter/query
registry ещё не определён; не интерпретировать произвольный hash как выполненный фильтр.

Response model: existing frozen `OrderReadPage`, snake_case, raw/canonical status,
mapping/source versions, per-item version/resolution/blockers, coverage, published_at,
snapshot_id/high_water_mark/next_cursor. OpenAPI schema реально строится в test app;
generated frontend artifacts здесь не создавались. HWM содержит hashes, не credential refs.

Errors: `detail.code`, 401 orders_authentication_required; 403 orders_access_denied;
400 orders_request_invalid/orders_account_scope_invalid; 409 orders_snapshot_unavailable;
503 orders_storage_unavailable/orders_cursor_unavailable. FastAPI parameter parsing
retains its normal422 contract. Snapshot conflict не является retry provider action.
Cursor codec использует существующий auth_secret с purpose-separated HMAC; minimum32bytes,
no new config/dependency. Rotation invalidates cursors. DB snapshot expiry/live auth
остаётся authority, собственной придуманной token TTL нет.

## Verification и review

TDD: missing Catalog/cursor/page/assembly/router/assignment codec imports -> pytest exit2.
Catalog variant rebind без timestamp: expected stale, previously resolved -> fixed.
Assembly missing current membership: expected validation, previously silently omitted -> fixed.
Completed account rebind: HTTP200 вместо409 -> mandatory binding fix. Independent critic
также нашёл order-dependent account/run checksum; canonical sorting исправляет его.
Повторный read-only critic: обе Important findings закрыты, новых Important нет.
Preflight skill file отсутствует локально; применён отдельный critic pass.

Fresh combined: **89 passed, 2 dependency deprecation warnings, 34.44s, exit0**:
`test_orders_bindings`, `test_orders_read_assembly`, `test_orders_catalog_resolution`,
`test_orders_publication_service`, `test_orders_cursor`, `test_orders_read_service`,
`test_orders_evidence_repository`, `test_orders_projection_repository`,
`test_orders_snapshot_repository`, `test_orders_http`.
Actual disposable PostgreSQL0064, runtime role, Unix-only sandbox, own DB/role cleanup
подтверждён. Existing `/dev/null` libpq passfile warning остаётся, не скрывался.
HTTP suite включает реальный signed token/resolver с dispatcher, закреплённым на synthetic
DB, missing/tampered bearer, между-транзакционный revoke/rebind и три late-rebind selectors.
Existing two-session logout/CAS tests не заменяются последовательными HTTP assertions.

Offline pure/legacy regression: **148 passed, 0.85s, exit0** (`orders_contract`,
`orders_ingestion`, `orders_read_contracts`, `orders_returns_characterization`,
`orders_xlsx_characterization`, `production_assignment_serialization`).
Перед commit: scoped Ruff, compileall, diff check и Git integrity. Full backend suite
не запускался в этом slice; broad baseline/parity не заявляется.

## Остаточные зависимости

Run binding stamps сейчас в legacy mutable audit JSON: service-level defense, НЕ DB
immutable provenance. `0b8ae9d` просит минимальный forward storage у T1; это activation gate.
Old unbound runs/snapshots intentional fail-closed, rollback не должен их relabel.
Guard physical-root followup пока не consumed; обычные Session(engine) используются в HTTP.
Production P1 DDL/permission ещё нужны; `0aa2c48` содержит согласованный witness amendment
и separate frozen/artifact/delivery requests. Source refresh/unassign/planning не придуманы.
Полные calendar/grouping/A4/sticker sources отсутствуют; WB fulfillment source отсутствует.
Полная матрица восьми этапов: `2026-09-09-t3-operations-progress.md`.

Никаких provider/production/print/export-operational-data/GitHub/push/deploy действий.
Только synthetic local tests; customer JSON, frontend, prototype и secrets не изменены.
