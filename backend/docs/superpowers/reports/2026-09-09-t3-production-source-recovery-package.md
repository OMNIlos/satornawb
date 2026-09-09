# T3: Single Production Source Recovery Package

Owner input request, not implementation or production authorization.
Checked against T3 `35ea34e77d80920b0d8779a6b888e6f1d8e7bad0` on 2026-09-09.
KIZ, Honest Sign allocation and the separate matcher are expressly excluded.
Do not send operational PDFs, customer JSON, codes, credentials or production data.

## Where Checked

- Exact original tree `c88a474695569af905b294906ba604d61f3de62f` and local Git refs:
  `git log --all -- backend/app/production backend/app/routers/production.py`
  again returned no commits. This is a claim about these exact paths, not proof
  that no differently named implementation exists anywhere.
- Existing source inventory:
  `2026-09-08-orders-production-stage1-handoff.md:34`, missing-path evidence at
  `:55`, route conflicts at `:88`; discovery `edc5439` was read as evidence only.
- Current `frontend/public/vella-production.html` includes browser print styling
  (120x75 and 58x40 at lines5309-5317), prototype selection/manual rows and local
  delivery state. `142cf46` characterizes available HTML. This is real partial
  source, not proof of the missing backend renderer or durable delivery contract.
- Existing `backend/app/avito/orders_picking_xlsx.py` is available and tested;
  it is not the missing unified Production exporter.
- Prior local search under `/Users/bratishka/Downloads/satornawb-main` and
  `/Users/bratishka/Documents/Codex` is recorded in the independent-preparation
  report. A fresh filename search for production Python, print-list, sticker and
  pdfBuilder sources returned only the known external fragment
  `/Users/bratishka/Documents/Codex/_remote_wb_pdf_2/pdfBuilder.ts` (plus unrelated
  scheduler state filenames, whose contents were not opened).
- `2026-09-08-orders-independent-preparation.md:151-165` records that fragment's
  checksum, missing dependency closure and 58x58 dimensions. It belongs to the
  excluded matcher path and does not establish ordinary 58x40 parity. No output
  PDFs/images or runtime state were inspected or exported for this request.

## One Required Input Bundle

| Needed source | What is missing | Required owner response / acceptance evidence |
|---|---|---|
| A4 print-sheet renderer | Executable renderer, fonts/templates, full dependency lock, selection/order/group/quantity handling and >48-row behavior | Immutable source bundle + revision/checksums and synthetic expected text/page fixtures. If the old renderer truncates, explicitly approve a separate rule fix; do not call that unchanged parity |
| Ordinary 120x75 stickers | Actual selected order/unit expansion, barcode/QR encoding and printer/PDF layout contract, not only browser CSS | Source/template revision and synthetic multi-item quantity>1 fixture with expected per-unit identity/code and physical page size |
| Ordinary 58x40 stickers | Same source closure for this format; existing 58x58 matcher fragment is not a substitute | Separate 58x40 fixture/layout contract and barcode verification expectations; preserve ordinary historical codes without KIZ allocation logic |
| Calendar, batches and grouping | Executable Europe/Moscow schedule/cutoff/weekend/coverage/overdue rules, deterministic group ordering and selected-item behavior | Exact source/rule revision and synthetic Friday/weekend/Monday, midnight, cutoff and coverage cases. No inferred UI thresholds or calendar defaults |
| Delivery and archive/reprint | Destination/operation definition, original request/response shape, receipt meaning, timeout/retry semantics, historical artifact selection | Source/contract + synthetic acceptance, rejection, timeout-after-possible-acceptance and retry fixtures. UI click/localStorage is not provider receipt; download is not print/send |

Prefer the original complete `app/production/{repository,storage,contracts,
print_list,export,mapping_import}.py`, router, tests and lockfile bundle if those
components were distributed together. Supply source/schema definitions only,
not the whole customer JSON store. Exact source paths may differ: record them.

If this source cannot be recovered, root needs a single explicit owner decision
authorizing a NEW specification for the missing behaviors and its acceptance
fixtures. That changes the target from preserving unknowable legacy parity to
implementing approved replacement rules. T3 cannot infer that authorization from
the request to continue locally. P1, Orders reads and existing Avito XLSX continue
independently; these missing inputs do not block all platform work.

## Avito Progression: Separate Source-Semantics Decision

The current confirmed path is fake normalized complete manifest -> guarded
append-only observations -> initial current projection -> immutable snapshot read.
Changed facts are persisted but remain reconciliation; this is NOT completed
revision-to-current-read behavior (`app/orders/publication_service.py:343-402`).

Available adapter evidence is insufficient to authorize automatic progression:

- `app/avito/orders.py:356-381` fetches one page per call, with page/limit and
  optional status/date filters, not a proven immutable provider snapshot.
- `:428-432` substitutes page length when total is missing/false-like.
  `tests/test_orders_avito_adapter_characterization.py:95-105` proves partial-page
  fetch and missing-total fallback; neither proves complete account coverage.
- `:450-451` parses created/updated timestamps but supplies no monotonic-version,
  tie or mutation-order guarantee. Local receipt time and opaque snapshot IDs
  cannot supply that guarantee.
- `app/orders/ingestion.py:287-320` explicitly describes `changed` as evidence,
  not authority to update a projection. Account locks serialize DB writers,
  not marketplace events fetched earlier outside the transaction.

Minimum missing authority: identify the Avito source endpoint/body and a documented
per-order ordered revision or approved snapshot-replacement rule; specify ties,
equal-version changed bodies, missing items and completeness across pagination.
Also identify stable order-line IDs or the limits of repeated-listing occurrence
identity under row reorder/change. No status ranking or received-at rule is assumed.

Once that authority exists, the bounded T3 path is one source only: fake pages ->
complete validated manifest -> append changed observation -> CAS parent/items in
the same publication transaction -> freeze/read the new revision; exact replay,
partial fetch, same-version conflict and older event tests must retain history
without silently regressing current. This uses existing repositories, not a new
generic source engine. Real provider execution is unnecessary for these local tests.

## Verification Boundary

This package is a read-only source investigation plus documentation. No schema,
provider, network, production, customer JSON, renderer output, print/export or
frontend mutation was performed. Paths/line references are tied to the stated T3
revision; T4's independent UI cleanup does not change the evidence authority.
P1 physical schema is now released (`d57c544` + `bb7a958`), not absent. Shared
permission READY and T3 service acceptance are distinct pending gates at this
checkpoint. Root consolidated integration follows ONE accepted consumer SHA,
not a claim that all eight stages are complete.
