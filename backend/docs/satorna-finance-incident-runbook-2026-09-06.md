# Canonical finance observability and incident runbook

Дата: 2026-09-06. Область: только canonical WB finance tables `0047…0060`.
SQL pack: `ops/satorna-finance-observability-20260906.sql`.

## Безопасность

Pack выполняет только catalog reads, `SELECT` и `EXPLAIN (ANALYZE, BUFFERS)`.
Он открывает `REPEATABLE READ READ ONLY` transaction, меняет tenant context только
через `SET LOCAL app.organization_id` и завершает transaction через `ROLLBACK`.
Подключение, credentials и connection string в репозитории не хранятся.

Не запускайте pack через роль с `SUPERUSER` или `BYPASSRLS` для доказательства
tenant isolation. Не добавляйте в incident artifact raw WB payload, session data,
connection settings или environment dump.

## Запуск

Runtime-проверка требует два разных tenant ID, account ID и точный период. Имена
`PGSERVICE` ниже — примеры локально управляемых profiles вне репозитория.

```bash
umask 077
PGSERVICE=satorna-runtime psql -X \
  --set=runtime_checks=true \
  --set=owner_checks=false \
  --set=organization_id=2 \
  --set=other_organization_id=1 \
  --set=marketplace_account_id=2 \
  --set=date_from=2026-08-31 \
  --set=date_to=2026-08-31 \
  --file=ops/satorna-finance-observability-20260906.sql \
  > finance-observability-$(date -u +%Y%m%dT%H%M%SZ).txt 2>&1
```

Проверка migration head выполняется отдельно владельцем миграций. Значение
`expected_revision` берётся из immutable image/release manifest, а не из этой
инструкции.

```bash
umask 077
PGSERVICE=satorna-migration-owner psql -X \
  --set=runtime_checks=false \
  --set=owner_checks=true \
  --set=expected_revision=20260905_0060 \
  --file=ops/satorna-finance-observability-20260906.sql \
  > finance-owner-check-$(date -u +%Y%m%dT%H%M%SZ).txt 2>&1
```

`psql -X` исключает локальный `.psqlrc`. Pack сам включает `ON_ERROR_STOP`.
Ненулевой exit code означает, что результат неполный и не может закрыть gate.

## Что читать в результате

- Role rows: у runtime role должны совпадать effective/login role, а `rolinherit`,
  `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, `rolbypassrls`
  должны быть `false`. У доступных через membership ролей не должно быть
  privileged attributes или ownership canonical finance relations.
- RLS inventory: все шесть relations существуют, `rls_enabled=true`,
  `rls_forced=true`; у каждой есть tenant policy с `USING` и `WITH CHECK`.
- Visibility probes: оба JSON объекта `no_context` и
  `other_organization.target_rows_visible` содержат только нули;
  `target_organization.visible_rows = target_rows_visible`.
- Lifecycle inventory: `published`, `pending_rollup`, `incomplete`.
- Per-run row: chain health, physical/effective counts, three rollup counts,
  freshness and `revenue_deltas_kopecks`. Для каждого `published` run все deltas
  должны быть `0`, а `zero_tolerance_reconciled=true`.
- Orphans: operation without membership, membership without operation/run.
- Explain: фактический exact-period projection plan, time и buffers.
- Lock sections: waits и open transactions, которые держат relation locks на
  finance tables. Runtime role может видеть неполные поля `pg_stat_activity`;
  полный lock triage требует отдельно одобренной роли с `pg_monitor` либо owner.
- Owner row: ровно одна Alembic revision и `revision_matches_image=true`.

`operation_count` — effective snapshot membership после разрешения parent delta,
а не число физических membership-change rows. Для delta run эти числа обязаны
различаться, если snapshot унаследовал неизменившиеся операции.
`daily_expected_operation_count` включает только операции с `business_date` внутри
run period; `daily_excluded_operation_count` показывает undated/out-of-period
операции, которые входят в aggregate P&L, но корректно отсутствуют в daily rollup.

## Пороги

Пороги применяются только к источнику, который по rollout policy должен
обновляться. Старый frozen period сам по себе не является stale incident.

| Сигнал | Normal | Warning | Critical |
|---|---|---|---|
| Lifecycle | ожидаемые завершённые runs `published`; transient pending младше 15 минут подтверждён активным job | `pending_rollup`/`incomplete` 15–30 минут | старше 30 минут либо нужный exact period недоступен |
| Rollup readiness | три flags `true`; counts согласованы | transient flags `false` только у подтверждённого активного run | flag `true` при count/parity mismatch либо заброшенный pending run |
| Snapshot chain | depth 0–1, cycle `false`, base reached, вся цепочка materialized | depth 2–8 | cycle, base не достигнут, нематериализованный ancestor, depth limit либо depth >8 |
| Operation count | declared = effective membership = operation rows = SKU/P&L counts; daily count = dated in-period operations | нет денежного warning-допуска; расследуется только незавершённый run | любое различие у `published` run |
| Revenue | каждый элемент `revenue_deltas_kopecks = 0` | отсутствует | любая ненулевая копейка |
| Source freshness | age не больше cadence + 2 часа; для daily cadence до 26 часов | 26–48 часов | больше 48 часов либо required snapshot отсутствует |
| Orphan operation | 0 | любое ненулевое значение ниже Critical; возраст <15 минут при подтверждённой publication — transient context | строка старше 24 часов или число растёт |
| Orphan membership | 0 | отсутствует | любое значение больше 0 |
| Runtime/RLS | effective = login; `NOINHERIT`; нет privileged/owner membership; ENABLE + FORCE; visibility probe = 0 | отсутствует | любое отклонение |
| Exact query | spot-check до 50 ms | 50–500 ms или новый disk-read regression | больше 500 ms либо timeout |
| Lock wait | 0 | ненулевой wait младше 30 секунд | wait 30 секунд и дольше либо блокируется API/worker |
| Finance transaction | до 5 минут для известного sync/materialization | 5–15 минут | больше 15 минут; `idle in transaction` больше 60 секунд |
| Migration | одна revision совпадает с image | DB впереди только при доказанном schema-compatible image rollback | DB позади image, несколько revisions или migration failed |

Один `EXPLAIN` — spot-check, не p95. Для performance gate снимайте минимум 25
одинаковых cache-only reads в тихом окне и сохраняйте нагрузку/host вместе с
результатом.

## Данные до вмешательства

Сначала сохраните неизменённый вывод pack и UTC timestamp, затем:

1. application commit, immutable image digest, deployment/release ID и ожидаемую
   Alembic revision;
2. organization/account, period, `sync_run_id`, parent ID, snapshot checksum,
   formula version, captured/last-observed timestamps и все readiness flags;
3. declared/effective/physical counts, rollup row counts и полный объект денежных
   deltas;
4. source manifest/checksum, external request IDs и operation-identity diff без
   raw response body;
5. effective/login DB roles, role attributes, table owners, policies и tenant GUC;
6. blocking/waiting PIDs, application names, states, transaction ages and lock
   modes; отдельно — worker/job ID, retry count и queue age;
7. health/readiness result, последние структурированные errors по request/sync/job
   IDs и backup/restore-check evidence.

Incident artifacts считаются sensitive operational data: доступ ограничивается,
retention фиксируется в incident ticket.

## Pending rollup или incomplete run

1. Убедитесь, что run действительно активен: сопоставьте его возраст с job ID,
   worker state и lock output. Наличие строки само по себе не доказывает работу.
2. Проверьте, что предыдущий полностью published snapshot остаётся доступным.
   Если да, оставьте reader на нём со stale/partial state.
3. Остановите новый dispatch только для затронутого organization/account через
   существующий rollout control; не останавливайте независимые accounts.
4. Сохраните counts, chain, locks и первый error до retry.
5. После устранения причины используйте только существующий application
   ingest/backfill path. Повторите pack и разрешите dispatch лишь после трёх ready
   flags и `zero_tolerance_reconciled=true`.

Нельзя вручную переключать materialization flags или собирать rollup SQL-записью.

## Financial mismatch

1. Немедленно блокируйте consumer cutover/publication затронутого snapshot; не
   меняйте уже опубликованные immutable rows.
2. Зафиксируйте snapshot/source checksums, effective operation IDs, removed/added
   membership IDs и каждую ненулевую копейку из deltas.
3. Разделите две причины: projection defect и реальная WB source revision.
   Source revision допустима только с полным identity-level diff.
4. Повторите read-only pack в той же revision. Затем исправляйте общий ingest или
   projection path тест-first и прогоняйте на clone.
5. Публикуйте новую immutable snapshot revision только через штатный sync.

Денежный tolerance равен нулю. Исторические `120800` копеек без retained raw
identity остаются открытым evidence gate, а не строкой для ручного добавления.

## Stale snapshot

1. Сверьте age с реальной cadence и rollout state. Намеренно отключённый schedule
   не является неожиданным stale, пока consumer contract не требует обновления.
2. Проверьте source availability, account binding, credential health, queue/worker
   и последний retry по идентификаторам; значения credentials не извлекайте.
3. Сохраните `captured_at` и `last_observed_at`: replay того же checksum должен
   менять только observation freshness, а source change — создавать revision.
4. Запустите approved sync path. До ready оставьте последний snapshot того же
   source/semantics с явным `stale`; не подменяйте его другим периодом.

## Failed migration

1. Остановите rollout и повторный запуск migrate job. Сохраните первый failure,
   SQLSTATE, transaction outcome, image digest, expected/actual revision, locks и
   backup checksum evidence.
2. Не выполняйте ручной DDL. Воспроизведите exact upgrade на task-owned
   production-schema clone и установите, была ли migration transactional.
3. Если текущая DB revision additive и предыдущий image доказанно совместим,
   верните только application images. Migration service остаётся остановлен.
4. Если совместимость не доказана, не запускайте ни новый, ни старый image до
   решения release owner. Restore/downgrade требует отдельного rehearsal и
   подтверждения; это не первичная incident-команда.

## RLS violation

Это всегда Critical/security incident.

1. Остановите затронутые API/worker lanes и finance rollout, сохраняя DB/log
   evidence. Не проверяйте leak через пользовательские запросы повторно.
2. Зафиксируйте effective/login role, tenant GUC, role attributes, table owner,
   policy definitions, organization/account и request/job IDs.
3. Проверьте, не использует ли workload owner, inherited elevated role или
   `BYPASSRLS`, и что context установлен transaction-local.
4. Исправление выполняется отдельным audited security change с cross-tenant test.
   Pack не выдаёт grants и не изменяет policy.
5. Возврат трафика — только после no-context, other-tenant и target-tenant probes
   под реальной runtime role.

## Image rollback без немедленного DB downgrade

1. Выберите previous immutable image только из проверенного release manifest и
   подтвердите его совместимость с текущей additive schema.
2. Остановите новые canonical finance writes/dispatch существующим rollout
   control, сохраните evidence и не запускайте migrate service.
3. Верните API и workers на один и тот же previous image digest. DB revision и
   новые immutable данные оставьте на месте.
4. Проверьте health/readiness, role attributes, RLS visibility, доступность
   предыдущего published snapshot и отсутствие новых mismatch/lock waits.
5. DB downgrade рассматривается позже, только после clone rehearsal, backup
   verification и проверки migration guards. Populated delta/loyalty downgrade
   намеренно может быть запрещён.

## Запрещённая «коррекция»

Никогда не создавайте synthetic finance operation, membership или rollup и не
меняйте сумму/flag ради прохождения reconciliation. Не копируйте текущую
себестоимость назад и не превращайте missing evidence в zero. Допустимы только
новая неизменяемая source observation через штатный service либо исправление
детерминированной projection с полной повторной сверкой.

## Локальная verification

На 2026-09-06 pack проверен без production/GitHub:

- focused baseline: `26 passed` для finance normalization/service/migration и
  runtime-role tests;
- disposable PostgreSQL 15 fixture прошла canonical migrations до
  `20260905_0060` с документированным stamp обходом legacy `0019`;
- runtime и owner modes исполнились без SQL error;
- два snapshot через существующий `FinanceService` (base + parent delta с одной
  out-of-period operation) дали `2/2` published/reconciled rows и ожидаемые daily
  counts `1 included / 1 excluded`;
- exact-period `EXPLAIN` и owner revision match получены по одному разу;
- fixture cluster и его файлы удалены после проверки.

Статическая перепроверка:

```bash
git diff --check

! rg -n -i --pcre2 \
  '\b(insert|update|delete|merge|create|alter|drop|truncate|copy|call|do|grant|revoke|vacuum|refresh|reindex|cluster)\b' \
  ops/satorna-finance-observability-20260906.sql

! rg -n -i --pcre2 \
  '(password|secret|token|cookie|dsn|postgres(?:ql)?://|[[:alnum:]_.-]+://[^[:space:]]+@)' \
  ops/satorna-finance-observability-20260906.sql
```

## Намеренно отсутствует

Нет scheduler, exporter, alert routing, dashboard, auto-remediation, automatic
rollback и monitoring framework. Добавлять их следует только после утверждения
общего metrics sink, worker/beat heartbeat и владельцев alert response; этот pack
остаётся ручным read-only источником проверок.
