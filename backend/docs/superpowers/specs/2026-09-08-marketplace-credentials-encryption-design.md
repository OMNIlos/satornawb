# Satorna Marketplace Credentials Encryption Design

**Status:** готово для решения владельца инфраструктуры; реализация и production-действия не выполнялись.

**Scope:** WB API credentials, Avito OAuth credentials/access-token cache и токен browser-extension ingestion. Канонический владелец секрета — `MarketplaceAccount`, а не пользователь или организация целиком.

## Источники и ограничение provenance

Дизайн основан на локально прочитанных `SATORNA_ARCHITECTURE_HANDOFF.md`, `SATORNA_SPEC_AUDIT.md`, фактическом backend-коде, Alembic-миграциях, тестах, `docker-compose.yml`, `Dockerfile` и `ops/runtime-db-role.sql`. Запрошенный исходный документ `frontend/docs/superpowers/specs/2026-08-26-satorna-platform-rebuild-architecture-design.md` отсутствует в обеих локальных копиях проекта, локальной Git-истории и доступных локальных refs. Его audit-пересказ не считается заменой оригиналу. До утверждения реализации владелец должен восстановить документ или письменно подтвердить, что этот дизайн может стать новой архитектурной нормой.

Никакие GitHub, production, внешние auth/review-сервисы или реальные значения секретов при подготовке не использовались.

## Наблюдаемое состояние

- WB token хранится как `Text` в `lk_user_wb_tokens.wb_token`; Avito `client_id`, `client_secret` и cached access token также хранятся как `Text` (`app/cabinet/orm.py:94-124`).
- `MarketplaceAccount` уже несёт tenant, provider/external identity и legacy `credential_ref`, но не ciphertext (`app/platform/integrations/orm.py:12-35`).
- WB binding связывает account с `lk_user_wb_tokens:<id>`, проверяет seller identity и затем при чтении снова извлекает plaintext из user-owned таблицы (`app/platform/integrations/wb_credentials.py:17-29`, `app/platform/integrations/wb_credentials.py:71-103`, `app/platform/integrations/wb_credentials.py:186-245`).
- Avito extension token хешируется, но индекс и verifier лежат в общем source cache; token действует на организацию и позволяет не только писать snapshot, но и читать returns-sync (`app/routers/avito_orders.py:709-776`, `app/repricer_cache/orm.py:33-60`).
- Celery broker/result backend — Redis, а некоторые task-signatures всё ещё принимают `wb_token`; ошибки местами сохраняются через `str(exc)` (`app/repricer_tasks.py:142-200`, `app/repricer_tasks.py:283-289`, `app/avito/returns_tasks.py:165-173`).
- Credential upsert endpoints сейчас используют общее `cabinet:read`, хотя изменение integration credentials должно требовать отдельного write permission (`app/routers/cabinet.py:250-264`).
- Compose отделяет one-shot `migrate` от runtime-контейнеров, но API/worker используют один runtime DB URL и provider secrets сейчас могут приходить через environment (`docker-compose.yml:32-60`, `docker-compose.yml:86-105`, `docker-compose.yml:127-145`).
- Runtime DB role не superuser и не `BYPASSRLS`, но имеет CRUD на все public-таблицы; `marketplace_accounts` входит в forced-RLS gate (`ops/runtime-db-role.sql:3-35`, `ops/runtime-db-role.sql:39-63`).

## Security objectives и non-goals

### Objectives

1. Украденный DB dump, volume snapshot или backup без host key не раскрывает WB/Avito credentials.
2. Секрет невозможно переставить между organization/account/provider/kind без отказа authenticated decryption.
3. Обычная migration/owner DB role не получает master key; runtime получает только необходимые версии ключа.
4. Новый writer никогда не пишет provider credentials в plaintext, включая rollback-период.
5. Celery, Redis, logs, exception text, audit, API responses и generic caches не получают значения секретов.
6. Ротация encryption key, provider credential и extension token независимы, наблюдаемы и обратимы в безопасной части окна.

### Non-goals

- Application-layer encryption не защищает от root на runtime-host, чтения памяти процесса или полного RCE в API/worker, которому разрешено decrypt.
- Она не скрывает metadata: organization/account/provider, время обновления, тип credential и приблизительный размер ciphertext.
- Без внешнего monotonic register она не предотвращает возврат всего DB и key-set к согласованному старому snapshot. Provider-side revoke и контроль backup/restore остаются обязательными.
- Этот документ не создаёт crypto-код, ключи, schema, миграции, deployment или backup changes.

## Threat model

### Приоритет рисков

1. **Blocker:** plaintext credentials в DB и содержащих её backups; cleanup нельзя начинать без encrypted read-back verification и recovery rehearsal.
2. **High:** runtime/API/worker leak surfaces и общий runtime DB login расширяют blast radius; encryption at rest не лечит RCE.
3. **High:** user/org-owned lookup допускает неоднозначное сопоставление с несколькими MarketplaceAccounts, особенно для Avito.
4. **High:** текущий extension bearer organization-wide, долгоживущий и шире ingestion-only scope.
5. **Medium:** DB rollback/replay валидного старого ciphertext нельзя полностью устранить без внешнего monotonic state; provider revoke и restore governance уменьшают риск.

| Asset / boundary | Угроза | Control | Остаточный риск |
|---|---|---|---|
| DB dump, physical backup, replica | Offline-чтение plaintext credentials | AEAD ciphertext; master key вне DB/repo/backup set; backup encryption и ACL | Metadata и ciphertext видимы; украденный key вместе с backup раскрывает данные |
| Runtime API/worker | RCE/insider получает key и decrypt capability | Ключ монтируется только нужным сервисам; typed resolver; минимальный срок plaintext в памяти; запрет debug/error serialization | Компрометация разрешённого decrypt-process остаётся критичной |
| DB owner/migrate | Owner читает все таблицы или меняет строки | У migrate нет key mount; AEAD AAD; migration отделена от backfill | DB owner может удалять/откатывать ciphertext и вызвать DoS |
| One-shot backfill | Роль одновременно видит legacy plaintext и key | Краткоживущая отдельная роль, allowlist таблиц/операций, supervised run, немедленный revoke | Это максимальный blast radius миграции; запуск требует двухстороннего контроля |
| Tenant/account boundary | Подмена ciphertext/ref между accounts/providers | Forced RLS, composite FK, canonical AAD и AEAD tag | Ошибка в tenant context всё ещё требует DB/RLS тестов |
| Celery/Redis/log/audit/API | Секрет сериализуется или попадает в exception | Только IDs в task args; safe error codes; allowlisted audit/result schemas; redacted secret type | Сторонняя библиотека может логировать headers; нужен integration test/log capture |
| Extension token | Кража долгоживущего org-wide bearer | Account ownership, one-way verifier, narrow write scope, TTL, revoke, rate/body limits | Bearer остаётся replayable до expiry/revoke |
| Key loss/compromise | Потеря decrypt или чтение старых dumps | Versioned keyring, offline recovery copy, staged rotation, provider revoke on compromise | Re-encryption не стирает утёкшие старые dumps |

### Trust boundaries и роли

- **API:** encrypt при credential create/rotate; decrypt только для синхронного provider call. Имеет runtime DB grants и read-only keyring.
- **Workers, которым нужен marketplace call:** decrypt по `(organization_id, marketplace_account_id, provider, kind)`. Celery payload содержит только IDs и несекретные параметры.
- **Beat/scheduler:** только ставит задачи с IDs; keyring и decrypt capability не получает. Пока Compose использует общий runtime DB login, beat технически может видеть tenant-scoped ciphertext; отдельный DB login остаётся желательным hardening.
- **Schema migrator/DB owner:** создаёт DDL и RLS; keyring не получает.
- **Credential backfill runner:** отдельный однократный контейнер и DB role. Только он временно получает legacy `SELECT`, encrypted-table `SELECT/INSERT/UPDATE` и keyring. Доступ отзывается сразу после сверки.
- **Operator/root:** хранит key files и recovery material. Эта роль вне защиты application-layer encryption и должна быть явно назначена владельцем.

## Рассмотренные минимальные подходы

| Подход | Плюсы | Минусы | Решение |
|---|---|---|---|
| Application AEAD + versioned host-mounted key files | Работает с текущим single-VPS Docker Compose; DB/backup не содержат key; контролируемая rotation; малая runtime-зависимость | Host root/RCE видит key; нужен строгий mount и offline recovery | **Выбран сейчас** |
| External reference в KMS/Vault/secret manager | Централизованный audit/revoke, envelope keys, меньше key material на диске приложения | В текущем deployment нет доказанной HA/операционной способности; добавляет сетевую availability-зависимость и runbook burden | Будущий вариант после отдельного readiness review |
| PostgreSQL `pgcrypto`, key/session setting | Меньше application-кода, простая SQL-миграция | Key достигает DB boundary; owner/backfill blast radius шире; высок риск попадания в SQL/log/history; rotation и разделение ролей хуже | Отклонён |

### Выбор

Использовать application-layer AES-256-GCM через поддерживаемую библиотеку `cryptography`, с versioned keyring из read-only host files. Не писать собственные primitives и не использовать общий `VELLA_AUTH_SECRET` как encryption key. Не вводить KMS/Vault до подтверждённой способности инфраструктуры эксплуатировать его надёжно.

Предлагаемый host path — `/etc/satorna/credential-keys/<keyVersion>` с bind mount read-only в `/run/secrets/satorna-credential-keys/`. Это имя — контракт deployment, не указание создать файлы сейчас. Каждый файл содержит ровно 32 raw bytes без newline; рекомендуемые host permissions: directory `0750`, file `0440`, `root:<dedicated-service-group>`. Ключи не передаются через environment, Compose interpolation, image layer, repo, DB, logs или обычный application backup. Key directory явно исключается из backup set с DB; offline recovery copy хранится отдельно. Environment может содержать только несекретный `current keyVersion` и путь к mounted directory.

## Crypto contract v1

### Primitive и encoding

- Algorithm: `AES-256-GCM`.
- Key: ровно 32 случайных bytes на `keyVersion`.
- Nonce: 12 случайных bytes для каждой операции encrypt; повтор nonce с тем же key запрещён.
- Authentication tag: 16 bytes, сохраняется как часть результата стандартного `AESGCM.encrypt`.
- Storage encoding: DB `BYTEA` для nonce и `ciphertext || tag`; base64 нужен только в тестовых fixtures/CLI transport и никогда не является encryption.
- Decrypt принимает только известные `algorithm`, `keyVersion`, `aadVersion`, `payloadSchemaVersion`. Unknown version, invalid length или invalid tag дают fail-closed non-secret error code.
- Если encrypted row существует, любая ошибка decrypt запрещает fallback в legacy plaintext. Fallback разрешён только при полном отсутствии encrypted row в явно включённом compatibility mode.

### Canonical associated data

AAD v1 — length-delimited canonical UTF-8 representation следующих полей в фиксированном порядке. Числа — minimal unsigned decimal ASCII; `expiresAt` — UTC RFC 3339 с целыми секундами и суффиксом `Z`:

1. domain separator `satorna.marketplace-credential`;
2. `aadVersion`;
3. `algorithm`;
4. `keyVersion`;
5. `credentialId` UUID;
6. decimal `generation`;
7. decimal `organizationId`;
8. decimal `marketplaceAccountId`;
9. lowercase `provider` (`wb` или `avito`);
10. `credentialKind`;
11. `payloadSchemaVersion`;
12. canonical `expiresAt` или explicit null marker.

Нельзя строить AAD простой конкатенацией с неоднозначными separators или JSON без canonicalization. Изменение ownership, key version, generation или expiry выполняется только decrypt → validate → encrypt с новым nonce/AAD; прямой SQL update этих полей запрещён.

### Payload schemas

- `wb_api/v1`: UTF-8 JSON object с единственным полем WB token.
- `avito_oauth_client/v1`: UTF-8 JSON object с client ID и client secret.
- `avito_oauth_access/v1`: отдельный короткоживущий object с access token и expiry. Его overwrite не создаёт audit payload с token.

После decrypt выполняются exact schema, UTF-8, non-empty и разумные size limits; для access cache expiry в payload обязана совпасть с AAD/column. Plaintext существует только как local value на время provider call; secret-bearing objects реализуют redacted `repr`/`str` и не включаются в Pydantic/API models, Celery results или audit JSON.

## Data model

### `marketplace_account_credentials`

Новая account-owned таблица:

| Column | Contract |
|---|---|
| `credential_id UUID PK` | Генерируется до encrypt и входит в AAD |
| `organization_id BIGINT NOT NULL` | Tenant key, forced RLS, входит в AAD |
| `marketplace_account_id BIGINT NOT NULL` | Account owner, входит в AAD |
| `provider VARCHAR NOT NULL` | Должен совпадать с `marketplace_accounts.marketplace`, входит в AAD |
| `credential_kind VARCHAR NOT NULL` | `wb_api`, `avito_oauth_client`, `avito_oauth_access` |
| `algorithm VARCHAR NOT NULL` | Только `AES-256-GCM` для v1 |
| `key_version INTEGER NOT NULL` | Выбор keyring entry |
| `aad_version SMALLINT NOT NULL` | Только `1` для v1 |
| `payload_schema_version SMALLINT NOT NULL` | Только разрешённая пара provider/kind |
| `nonce BYTEA NOT NULL` | Check length 12 |
| `ciphertext BYTEA NOT NULL` | Включает 16-byte tag; check minimum length |
| `generation BIGINT NOT NULL DEFAULT 1` | Compare-and-swap при controlled re-encryption |
| `created_at`, `updated_at` | Несекретные timestamps |
| `expires_at` | Только для access cache |
| `revoked_at`, `revocation_reason_code` | Reason — allowlisted code, не свободный secret-bearing text |

Нужны composite FK `(organization_id, marketplace_account_id, provider)` → соответствующий unique key на `marketplace_accounts`, partial unique для одной active credential на `(organization_id, marketplace_account_id, credential_kind)`, indexes для account lookup и `key_version`, forced RLS и tenant-context tests. Из-за текущего `GRANT ... ON ALL TABLES` общий runtime login увидит только tenant-scoped ciphertext; decrypt-capability определяется key mount. Предпочтительное hardening — отдельные API/worker/beat logins и явные grants, но оно требует решения владельца и не блокирует encryption-at-rest.

`MarketplaceAccount.credential_ref` остаётся только legacy migration locator. Новый resolver не следует user-owned reference. После encrypted-only switch и cleanup поле очищается, затем удаляется отдельной совместимой миграцией.

### `marketplace_account_ingestion_tokens`

Extension bearer не нуждается в reversible encryption: генерируется минимум 256 bits entropy, один раз показывается владельцу, в DB хранится только SHA-256 verifier. Offline guessing такого случайного token практически неосуществим; encryption key для verifier не нужен.

Строка принадлежит конкретному Avito `MarketplaceAccount` и содержит random public `token_id`, tenant/account/provider, verifier, exact scope `avito.browser_snapshot.write`, issued/expiry/revoked/last-used timestamps. Bearer имеет self-locating format `prefix.organizationId.publicTokenId.randomSecret`: endpoint парсит untrusted organization locator, открывает короткую transaction с этим tenant context только для exact token lookup под forced RLS, затем constant-time сравнивает SHA-256 random-secret. Глобальный перебор rows и privileged cross-tenant lookup запрещены; malformed/unknown/revoked/wrong-secret ответы одинаковы. Organization/public IDs не являются авторизацией. Token не может читать returns-sync, менять settings или выбирать другую organization/account; account для записи берётся только из проверенной token row, не из request body. Snapshot/cache key также включает этот account ID. Обязательны finite TTL, rotation/revoke, request size limit, unauthenticated IP abuse limit до lookup, per-token rate limit только после успешной проверки и one-time reveal только в successful authenticated issue-response по TLS; invalid public IDs не создают unbounded rate-limit keys. Status/retry endpoints token повторно не возвращают. Текущий org-wide token невозможно безопасно «перепривязать» по одному hash: его надо отозвать и перевыпустить для выбранного account.

## Resolver и write contract

Единственная application boundary:

- `put_marketplace_credential(account_identity, kind, plaintext) -> credential metadata` — encrypt-only, atomic insert/rotation; никогда не возвращает ciphertext/plaintext в API/audit.
- `resolve_marketplace_credential(account_identity, kind) -> redacted secret value` — exact tenant/account/provider lookup, AEAD decrypt, schema validate, no auth-failure fallback.
- `reencrypt_credential(credential_id, expected_generation, target_key_version)` — privileged batch path; same ownership/AAD fields, fresh nonce, decrypt-verify before CAS update.
- `revoke_marketplace_credential(...)` — сначала provider-side revoke/replace, затем local `revoked_at`; ciphertext удаляется по retention policy.

API credential writes требуют `integrations:write`, а не текущего `cabinet:read`. Response содержит только account ID, status и timestamps; не содержит даже mask/prefix, ciphertext, nonce, tag, key version inventory или иное производное от secret. Единственное исключение — deliberate one-time delivery нового extension bearer на authenticated issue endpoint.

## Leakage controls

1. Удалить secret параметры из всех Celery task signatures. Задача получает organization/account IDs и сама вызывает resolver непосредственно перед provider call.
2. Не передавать secrets в task names, retry kwargs, result backend, progress payload, Redis/source cache или FastAPI `BackgroundTasks` arguments.
3. Не сохранять `str(exc)` из provider/crypto/http libraries. На boundary переводить в allowlisted codes (`credential_missing`, `credential_auth_failed`, `provider_auth_rejected`, `provider_unavailable`) и отдельные безопасные numeric/status diagnostics.
4. Никогда не логировать request/response headers, query strings с token, request bodies credential endpoints, decrypted payload, ciphertext или extension bearer. Logging filters — defense in depth, а не основной control.
5. Audit содержит actor, tenant/account, kind, operation, old/new keyVersion, generation, result code и timestamps; без credential ref, mask/prefix, ciphertext, verifier или exception text.
6. Secret input fields имеют `repr=False`; API validation errors не должны отражать rejected body. OpenAPI examples используют только очевидно синтетические placeholders.

## Migration/runbook and rollout

### Phase 0 — owner gates и inventory

- Восстановить/waive отсутствующий architecture design.
- Зафиксировать custodian, recovery, key versions, observation window, backup retention, Avito/WB account mapping и extension policies.
- Считать только row counts и mapping statuses. Не экспортировать, печатать, хешировать для отчёта или логировать credential values.

### Phase 1 — additive compatibility release

- Добавить crypto boundary, новые tables/RLS/grants и key mount только API/нужным workers.
- Startup fail-closed: при включённом encrypted reader/writer отсутствие current key или permission прекращает старт сервиса.
- Writer сразу **encrypted-only**. Reader — encrypted-first; legacy fallback только когда encrypted row отсутствует и compatibility flag включён. Auth/tag/schema failure никогда не включает fallback.
- Rollback target с этого момента — эта compatibility release, а не старый plaintext writer.

### Phase 2 — deterministic account mapping

- WB: использовать только уже seller-info-verified `MarketplaceAccount.credential_ref` mapping; повторная live verification выполняется позднее только в утверждённом production runbook.
- Avito: нельзя переносить «последнюю credential организации» во все accounts. Владелец даёт mapping, затем official provider identity проверяется отдельно. Неоднозначные rows остаются unmapped и блокируют cleanup.
- Avito cached access tokens не backfill: это короткоживущие производные credentials. После verified decrypt client credentials и успешного OAuth exchange новый access token пишется сразу encrypted, а legacy cached token удаляется. До этого удаление запрещено.
- Extension: каждый старый org token отозвать; после выбора account выпустить новый scoped token.

### Phase 3 — one-shot backfill

Для каждой mapped row в короткой transaction:

1. Lock legacy WB token или Avito client credentials и target account; legacy Avito access-token cache исключён из backfill по правилу выше.
2. Сформировать typed payload в памяти; создать `credential_id`, fresh nonce и canonical AAD.
3. Encrypt current key; вставить encrypted row.
4. Тут же прочитать target, decrypt через production resolver, проверить schema/AAD и exact in-memory equality с legacy source constant-time, где применимо.
5. Только при успехе commit. В лог/metric попадают row ID, account ID, status и counters, но не value, digest, ciphertext или mask.

Backfill idempotent по legacy locator + account/kind и не перезаписывает более новую encrypted generation. Роль и key mount отзываются после 100% verification; schema migrator их не наследует.

### Phase 4 — verification и switch

- Для 100% expected mappings повторить decrypt/schema/AAD verification и in-memory equality до удаления plaintext.
- Запустить account/provider consumer canaries без вывода response bodies и secret-bearing errors.
- Наблюдать fallback counter по account/kind. Переключать encrypted-only только после нуля для согласованного окна и отсутствия unresolved mappings.
- Сделать encrypted backup и изолированный restore rehearsal. Backup encryption — дополнительный control; успешный restore ciphertext без отдельного recovery key не считается recovery.

### Phase 5 — cleanup

- Encrypted-only readers/writers уже deployed.
- Удалить plaintext columns/rows, user/org-latest resolvers, raw in-memory fallback и provider credential env fallbacks.
- Очистить/удалить `credential_ref`; удалить old extension cache entries после revoke.
- Отозвать backfill grants/role, убрать legacy access из runtime, проверить новые backups и retention purge старых plaintext backups.

Удаление plaintext разрешено только после сохранённого non-secret отчёта: expected=mapped=encrypted=decrypt_verified=consumer_verified, fallback=0, unresolved=0. Отчёт не содержит hashes/digests секретов.

## Key rotation и revoke

### Плановая encryption-key rotation

1. Custodian создаёт `vN+1`, хранит offline recovery copy и монтирует рядом с `vN`.
2. Readers принимают обе версии; writer получает current=`vN+1`.
3. Batch выбирает old rows через `FOR UPDATE SKIP LOCKED`, decrypt/validate старым key, encrypt fresh nonce новым key, немедленно decrypt-verify и CAS-update по `generation`.
4. Metrics содержат counts/errors/IDs и версии, не данные. Ошибка одной строки не вызывает plaintext fallback.
5. После zero old active rows, consumer canary и backup/restore verification старый key удаляется из runtime. Offline retention согласуется с rollback и сроком старых backups.

### Provider credential revoke/replace

Provider credential rotation создаёт новую encrypted generation/row и проверяет provider identity до активации. Старую credential отзывают у WB/Avito, затем помечают revoked и удаляют по короткому rollback retention. Encryption-key rotation не заменяет provider revoke.

### Key compromise

Считать скомпрометированными все credentials в dumps/backups, доступных утёкшему key. Выполнить: containment key mounts, новый encryption key, provider-side rotation/revoke WB/Avito credentials, revoke/reissue extension tokens, определить и уничтожить/изолировать старые backups по policy. Простая re-encryption текущей DB недостаточна.

## Rollback contract

- **До plaintext cleanup:** откатить read mode с encrypted-only на encrypted-first + absence-only legacy fallback, но writer остаётся encrypted-only. Нельзя запускать image, который пишет plaintext.
- **После cleanup:** разрешены только encrypted-aware image/schema. Alembic downgrade не должен пересоздавать или заполнять plaintext columns. Восстановление — из encrypted backup плюс соответствующий offline key.
- **Decrypt/auth failure:** остановить affected account operations, сохранить ciphertext, восстановить нужную key version или исправить metadata через controlled re-encryption. Не читать legacy plaintext для строки, где encrypted row существует.
- **Старый backup:** восстанавливать только изолированно, без внешних provider calls; сразу мигрировать/reencrypt под действующий contract. Не подключать к нему unsafe writer.

## Required tests и release gates

### Crypto unit tests

- AES-GCM round-trip для каждого payload schema; random nonce uniqueness sample.
- Mutation каждого AAD ownership field, nonce, ciphertext и tag даёт typed auth failure.
- Unknown key/aad/payload version, bad lengths, invalid UTF-8/schema и oversize payload fail closed.
- Secret wrapper `repr`/`str`, exception и validation output не содержат plaintext.

### Persistence/RLS tests

- Composite FK и checks не позволяют tenant/account/provider mismatch; one-active constraint работает.
- Forced RLS: no-context, cross-org select/insert/update/delete запрещены.
- Runtime grants достаточны API/worker и недостаточны beat; migrator без key не decrypt; backfill role отозвана после run.
- CAS generation защищает от lost update; re-encryption использует fresh nonce и сохраняет semantic plaintext.

### Migration tests

- Empty DB upgrade; production-shaped disposable clone upgrade. Downgrade проверяет только безопасную schema compatibility и не восстанавливает plaintext.
- Dual-read matrix: encrypted wins; absent row may fallback only with flag; invalid encrypted row never fallback.
- Idempotent interrupted backfill; new encrypted rotation не перезаписывается старым source.
- 100% decrypt-and-compare gate до cleanup; unresolved/ambiguous Avito mapping блокирует cleanup.
- Restore encrypted backup + separately supplied recovery key; backup без key не decrypt.

### Leakage/API/task tests

- Capture logs, audit rows, HTTP responses/errors, Celery args/results/retries и Redis/source-cache writes для success/failure; secret canaries нигде не встречаются.
- Credential writes требуют `integrations:write`; read-only roles не могут менять secret.
- Extension token: exact account and write-only scope, expiry, revoke, constant-time verifier, rate/body limits; GET returns-sync и cross-account requests запрещены.
- Provider clients не логируют Authorization headers/body; crypto/provider exceptions преобразуются в safe codes.

### Go/no-go

No-go при любом decrypt mismatch, auth-failure fallback, secret canary leak, missing forced RLS, ambiguous mapping, unresolved key recovery, plaintext-capable rollback image или отсутствии проверенного encrypted-backup restore.

## Решения владельца инфраструктуры

1. Восстановить исходный architecture design либо утвердить этот документ как заменяющий security contract.
2. Назначить двух custodian/operator для host key install и offline recovery; утвердить file ownership/mode, mount list и emergency access.
3. Одобрить поддерживаемую версию `cryptography` и процедуру dependency/security updates.
4. Утвердить точный WB/Avito account mapping и способ provider identity verification.
5. Утвердить extension TTL, rate limit, request size и rollout/reissue UX.
6. Утвердить observation/rollback window, provider-revoke delay и политику удаления старых plaintext backups.
7. Решить, вводятся ли отдельные API/worker/beat DB logins в этом slice; независимо от решения beat не получает decrypt/key access.
8. Утвердить incident runbook: кто отзывает WB/Avito credentials, ключи и extension tokens, и какой SLA.

## Принятые решения

- Ciphertext, а не external credential reference, для текущего deployment.
- AES-256-GCM, versioned external keyring, canonical account-bound AAD.
- Master key вне DB/repo/environment/application backup; отдельный ключ от auth/session secrets.
- Encrypted-only writer с первого compatibility release; absence-only legacy fallback временно.
- Account-owned reversible provider secrets; one-way account-owned verifier для extension token.
- Проверка decrypt и exact in-memory equality обязательна до удаления plaintext.
- Rollback никогда не возвращает небезопасный writer.
- Backup encryption остаётся дополнительным, но не единственным control.
