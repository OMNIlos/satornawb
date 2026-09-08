# T4 → T1: exact Review storage matrices

Ответ на `9438186:2026-09-09-t1-schema-amendment-feedback.md`, уточняет `8f4a6c4`.
Domain proposal для принятия T1; физическая schema и runtime не меняются. Review Facts
остаются отдельно принятыми. Подтверждённое чтение T1 amendment — commit `9438186`.

## Lease и head initialization

Lease token — UUIDv4, генерируется доверенным worker service при claim из OS random,
не принимается из HTTP/body/queue. Unique(owner, lease_token), immutable на attempt;
он является fencing identity, не credential и не заменяет authorization. Attempt UUID
также server UUIDv4; claim создаёт оба в transaction, возвращает их только winning worker.
Каждый новый attempt получает новый token. Queue передаёт command ID/version, не token.

Renewal разрешён только при command=leased, attempt=claimed, dispatched_at=null,
current attempt/token/version match и DB now<lease_expires_at. Dispatched/ambiguous
никогда не renew. Dispatch меняет attempt claimed→dispatched; command остаётся leased,
version V→V+1. Audit tuple leased→leased. Result write потребляет именно V+1, либо
актуальную version после допустимого CAS read; любой failed CAS требует reread, не blind overwrite.
Delivery fencing использует тот же predicate с delivery version/current attempt/token/live DB lease;
renewal только claimed/pre-marker, не ambiguous. Это дополняет прежние delivery matrices.

Policy head: отдельный server UUID, unique(owner), создаётся только с первым выбранным
policy-version FK, version=1. Committed empty policy heads запрещены. При select существующего
head expectedVersion>=1, при первом select expectedVersion=0 означает отсутствие строки,
unique race проигравшего даёт409. Immutable policy creation само по себе head не создаёт.

Workflow head: отдельный server UUID, unique(owner,review_id), создаётся с первой опубликованной
draft revision, current_draft_id non-null, current_decision_id=null, version=1.
Committed empty workflow head запрещён. Первая publication expectedVersion=0 проверяет absence;
последующие publication/decisions CAS-ят head version. Draft revision — отдельный монотонный
счётчик по review; approval increments head version, но не draft revision. Pure publication
predicate использует current draft revision, не workflow-head version: repository проверяет оба.
Decision устанавливает current_decision_id, draft остаётся прежним. Новая draft очищает decision.
Scoped FK гарантирует, что current decision относится к current draft этого же review.

## Result evidence и reason nullability

Review evidence хранит explicit discriminator `evidenceKind=dispatch_ack|reconciliation_read`,
`evidenceVersion=review-answer-evidence-v1`, verifierVersion (nonempty version label).
Stored `outcome=incomplete|exact|different`; immutable записи имеют UUID, owner/review/command/
attempt, observed_at и optional provider_answer_id/answer_checksum. Для reconciliation_read
required readId(UUID) и reconciliation_started_at: dispatch≤read_start≤observed≤server now.
Для dispatch_ack оба read поля null; observed>=dispatch; authenticated direct response должен
доказать exact review/account и answer, а не просто transport HTTP200.

Incomplete: отсутствует хотя бы answer ID или checksum; допустимы оба null. Exact/different:
оба обязательны, outcome соответствует сравнению checksum с immutable command text checksum.
Dispatch ack без достаточного содержимого становится incomplete/ambiguous. Если provider не
предоставляет доказуемый exact answer checksum/ID, success не угадывается из отправленного request.
No raw provider response/customer text в evidence. Read identity или direct response evidence UUID
replay сравнивает exact bytes; разные bytes → conflict без изменения history.
Pure recovery принимает только projection verified reconciliation_read; direct ack обрабатывается
отдельным worker transaction gate, не поддельным read timestamp.

| Command state | result_evidence_id | reason_code |
|---|---|---|
| queued, leased | null | null |
| ambiguous | null либо incomplete evidence | RESULT_UNKNOWN |
| sent | required exact evidence | VERIFIED_EXACT_ANSWER |
| conflict | required different evidence | VERIFIED_DIFFERENT_ANSWER |
| blocked | null | ACCESS_REVOKED, SOURCE_CHANGED, POLICY_CHANGED, NOT_ANSWERABLE, CREDENTIAL_UNAVAILABLE |
| cancelled | null | USER_CANCELLED |

| Attempt state | result_evidence_id | reason_code |
|---|---|---|
| claimed, dispatched | null | null |
| ambiguous | null либо incomplete evidence | RESULT_UNKNOWN |
| sent | required exact evidence | VERIFIED_EXACT_ANSWER |
| conflict | required different evidence | VERIFIED_DIFFERENT_ANSWER |
| blocked | null | те же пять blocked codes |
| abandoned | null | LEASE_EXPIRED_UNDISPATCHED |

Для current attempt sent/conflict/ambiguous/blocked command и attempt result/reason совпадают.
Reclaim exception: command queued очищает result/reason, historical attempt abandoned сохраняет
LEASE_EXPIRED_UNDISPATCHED; audit описывает причину transition. Все result FKs scoped по owner,
review, command и attempt. Evidence exact/different не может ссылаться на чужой attempt.
Incomplete reads могут добавляться без lifecycle change; они не заменяют существующую evidence
и не переводят sent/conflict обратно. Их immutable insert атомарно завершается сам по себе,
без send transition audit; состояние ambiguous остаётся прежним.

## Exact Review audit matrix v1

Общий envelope из `8f4a6c4` сохраняется. Audit state enum расширяется только для head-проекций:
policy_selected, draft_current, decision_current. Null указан явно; никаких free JSON snapshots.
Owner/org/account, event UUID, occurredAt и aggregate identity/version обязательны у всех rows.
Все не перечисленные ниже entity refs null. Worker actorMembershipId null; membership actor
required canonical **positive INTEGER membership ID**, проверенный по organization composite FK.
Notification recipientMembershipId также canonical INTEGER, не UUID и не user_id.

Обозначения refs: P=policyId, D=draftId, Q=decisionId, C=commandId, A=attemptId.
Local immutable events и head updates выполняет membership; send worker lifecycle — worker.

| Event | Aggregate / version | before→after | Required refs | Actor | reason |
|---|---|---|---|---|---|
| policy.created | policy UUID / policy version | null→null | P | membership | null |
| policy.selected | policy-head UUID / new head version | null→policy_selected при init, иначе policy_selected→policy_selected | P | membership | null |
| draft.published | workflow-head UUID / new head version | null при init, иначе draft_current либо decision_current → draft_current | P,D | membership | null |
| decision.approved | workflow-head UUID / new head version | draft_current либо decision_current → decision_current | D,Q | membership | null |
| decision.rejected | workflow-head UUID / new head version | draft_current либо decision_current → decision_current | D,Q | membership | null |
| send.created | command UUID / 1 | null→queued | C,D,Q | membership | null |
| send.claimed | command UUID / new version | queued→leased | C,A | worker | null |
| send.lease_renewed | command UUID / new version | leased→leased | C,A | worker | null |
| send.dispatched | command UUID / new version | leased→leased | C,A | worker | null |
| send.reclaimed | command UUID / new version | leased→queued | C,A исторической abandoned attempt | worker | LEASE_EXPIRED_UNDISPATCHED |
| send.ambiguous | command UUID / new version | leased→ambiguous | C,A | worker | RESULT_UNKNOWN |
| send.sent | command UUID / new version | leased либо ambiguous → sent | C,A | worker для direct ack/read; membership только для authorized reconciliation_read | VERIFIED_EXACT_ANSWER |
| send.conflict | command UUID / new version | leased либо ambiguous → conflict | C,A | как send.sent | VERIFIED_DIFFERENT_ANSWER |
| send.blocked | command UUID / new version | queued либо leased → blocked | C; A required если leased, иначе null | worker | пять blocked codes из таблицы |
| send.cancelled | command UUID / new version | queued→cancelled | C | membership | USER_CANCELLED |

No membership-supplied 'verified' flag: reconciliation evidence читает доверенный adapter/service,
membership только инициатор разрешённого действия. При user result CAS service повторяет свежие
membership/account permissions. Worker actor нельзя присвоить из HTTP. Result evidence reference
берётся из scoped command/attempt для audit review; envelope не дублирует payload evidence.
BeforeState определяется фактически прочитанной locked row, а не аргументом клиента.

Unique audit `(owner,aggregateId,aggregateVersion,eventKind)` и exact replay как раньше.
Init создаёт head+target+audit одной transaction. Policy.selected того же target с прежним
idempotent command не создаёт новую version; новое явное select требует expected version и
считается новым head update даже при том же target. Draft/decision/current pointers и audit
согласованы при commit. Cross-row CHECK/trigger/transaction mechanics выбирает T1.

## Сохраняемые отдельные gates

External notification destination/receipt/policy relations и org-wide system registry остаются
platform contracts T1; их FK/production values здесь не выдумываются. Account-scoped in-app
events/receipts от них не зависят. Policies/drafts/send schema может выпускаться отдельно.
Retentions/leases/retries production values остаются owner decision; локальные test values
не являются разрешением активации. T1 сообщил ENOMEM при disposable PostgreSQL bootstrap;
этот документ не устраняет environment blocker и не доказывает DB gates.

Проверка этого изменения: docs-only сопоставление с T1 feedback, фактическим canonical identity
и pure predicates; новых runtime/test/schema changes нет. Следующий gate — review/acceptance T1,
committed DDL и реальные disposable PostgreSQL tests. Не заявляется installed storage.
