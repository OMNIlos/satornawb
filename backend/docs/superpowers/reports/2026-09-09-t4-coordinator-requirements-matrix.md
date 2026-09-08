# T4 — requirement → commit → evidence → remaining work

Snapshot на `9284fe0`, worktree clean. Координатор: задача
`01a082e2-4420-70a3-b4f4-2c4ad061e587`; начальная передача подтверждена tool.
Stage completion оценивается по исходному заданию T4, не числу pure modules/documents.
GitHub push/integration выполняет координатор после общего gate.

| Требование | Commit / артефакт | Проверка | Незавершённое |
|---|---|---|---|
| 1. Canonical ABC/P&L frontend | 7cd1fd9,028168b,81ee4b9 | focused75; typecheck/build0; immutable base193pass29fail →261pass29fail, exact same failure IDs | Hosted canary/browser E2E, missing backend freshness policy; no release approval |
| 2. Review Facts + shadow | 4a7d669 request, accepted T1 d38e923; existing canonical_contract.py | existing normalization38 cases в текущем combined173 | DDL, canonical_orm/repository, same-fetch shadow hook, actual PG replay/manifest/watermark/source-order/CAS/RLS/outage/restart |
| 3. Policy/draft/approval | 98d1331 pure decision, 8f4a6c4+b17638f exact payload/head/audit proposals | 40 decision tests + lifecycle subset; revoked/stale/scope/checksum predicates | Canonical serializers, immutable rows/head publication CAS, fake generation service, authenticated actions, atomic audit, PG races/restart |
| 4. Send/recovery | e4818e3 pure recovery; b17638f exact lease/result/evidence/audit | 35 recovery tests, current-read boundary/live lease/ambiguity; 8 provider lifecycle | Durable idempotency, exclusive attempt/marker, worker enqueue and credential resolution, actual provider-fake crash/restart/CAS; no live send |
| 5. Notifications | 98d1331 safe projection; 9284fe0 read-only preferences | 31 projection +21 SQLite preferences tests | Immutable events, per-member receipt/upsert/visible-ID mark-all, atomic outbox, recipient/cache isolation, delivery storage/attempts, verified destination/receipt contracts |
| 6. Other frontend consumers | Существующий ABC adapter; новые domain endpoints ещё не approved | Stage1/bd6139f проверены; другие capability cutovers не заявляются | T1 credential/token policy; T2 repricer/finance/sources HTTP schemas; T3 Orders/Production HTTP commands/read/export/receipt contracts; adapters/UI/default-off flags после parity |
| 7. Rollout/retirement | e4818e3 frontend canary-rollback-runbook | read-only critic, explicit NO-GO, build-time rollback and old tabs | Approved release budgets/window/artifacts, отдельно разрешённый canary; legacy retirement только после actual parity |
| 8. Test debt/handoff | bd6139f clock fix, все bounded handoffs | fresh frontend261/29 →264/28, exact0new1resolved, skips0; typecheck0 | Остальные28 frontend failures, integration full suite/baseline, real generator pipeline по контракту, final ready set |

Latest scoped combined T4: **173 passed, exit0**, zero external-action attempts under
Python audit hooks. 21 SQLite tests доказывают query/projection, не PostgreSQL RLS.
Полный backend suite для T4 continuation не запускался; исторические baseline failures
не автоматически утверждённый release allowlist. Frontend runtime после Stage1 не менялся.

## Exact requests координатору и владельцам

### T1 — prerequisites в порядке возможности

1. Принятый Review Facts DDL по `4a7d669`, actual revision от единственной head, scoped
   FKs/RLS/runtime privileges и committed test handoff. T4 после проверки пишет
   `app/reviews/canonical_orm.py` + repository, не competing T1 domain ORM.
2. Review local policy/draft/decision/head DDL по `8f4a6c4` и `b17638f`.
   b17638f уточняет head initialization, distinct head/draft versions и per-event audit;
   независимый critic прошёл, acceptance T1 ещё не подтверждено.
3. Send command/attempt/evidence + domain audit/enqueue atomic persistence по тем же
   matrices. No provider/production policy defaults. Shared transaction-local context,
   grants и physical outbox принадлежат T1; T4 получает готовый интерфейс/DDL.
4. Account-scoped notification events/receipts DDL можно выпускать независимо от Telegram.
   Explicit visible-ID mark-all, integer membership, composite owner FKs. Preferences
   остаются в lk_user_preferences; read-only adapter9284fe0 уже готов. Writer требует
   T1 extension existing owner's version/CAS, не новой preferences table.
5. External Telegram позже: verified versioned destination binding, scoped provider
   receipt, immutable delivery policy relation/ref. Org-wide events отдельно требуют
   platform registry. Missing policy/binding блокирует активацию, не in-app storage.
6. Disposable PostgreSQL environment: T1 report9438186 сообщает bootstrap ENOMEM.
   T4 не меняет sysctl/shared memory/чужие процессы. Координатор определяет разрешённую
   remediation/isolated runtime; новый PG запуск только после безопасной готовности.

### T2

Нужны committed approved HTTP schemas/routes/permissions/capabilities для repricer,
finance/sources: exact read pagination/snapshot/error contracts и command expected_version/
idempotency/409 semantics. Observed HEAD ee7bd6e; незакоммиченный reserve/dispatch amendment
не импортирован. Pure repository proposal не служит источником придуманных HTTP endpoints.

### T3

Нужны committed approved Orders/Production HTTP read/commands + status mapping, print/download/
delivery/backend receipt distinctions и parity evidence. Observed HEAD2f1724a. T1 currently
интегрирует Orders candidate; незакоммиченная0062 не imported и не названа ready. Legacy
serverless snapshot writer отключается только при agreed single-owner cutover/rollback.

## Готовые bounded commits и следующий шаг

Текущий ready для review набор — T4 история от c88a474 до9284fe0, включая docs; это не
разрешение общего merge и не stop/ready declaration всей задачи. После каждого следующего
slice координатор получает exact commit/tests/gaps. Независимый следующий шаг — canonical
serializers для уже описанных policy/generation/send bytes, чтобы repository повторно
использовал проверенную реализацию. Это не заменит DDL/DB/HTTP acceptance.
