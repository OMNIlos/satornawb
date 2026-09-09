# T3 -> T1: immutable source-run account binding

Найдено на read preflight: numeric account ID недостаточен после завершённой
перепривязки external_account_id/credential_ref. Guard ловит изменение между fetch
и commit, но не доказывает, к какому external binding относится старая история.

T3 consumer теперь fail-closed:

- stamped publication receipt связывает run с fingerprint org/account/provider/
  external_account_id/exact nullable credential_ref;
- freeze проверяет selected coverage run и каждый current projection run;
- immutable snapshot high-water mark v2 содержит content и account-binding hashes;
- latest/explicit/cursor read сверяет frozen binding под live guard;
- unstamped runs и unbound snapshots не принимаются; ничего не backfill из current
  account metadata, поскольку это могло бы переименовать чужую старую историю.

**Остаточный blocker для activation:** сейчас run stamp хранится в `lk_audit_events.details`.
Эта legacy relation не является immutable/unique Orders provenance contract.
Это service-level проверка, не DB-enforced гарантия. Не выдавать её за завершённое
tenant hardening. Нужен narrow forward schema amendment владельца T1.

## Предлагаемый минимальный storage

Предпочтительно добавить versioned binding payload в существующую `order_sync_runs`,
не создавать отдельную domain table. Точные имена/representation выбирает T1:

- account_binding_schema_version=1;
- canonical binding payload (BYTEA + JSONB projection либо доказанный exact JSONB
  representation), exact fields organization_id, marketplace_account_id, provider,
  external_account_id, credential_ref (NULL сохраняется как NULL);
- account_binding_checksum SHA256 canonical bytes, не unique identity и не замена
  exact comparison. Payload содержит только metadata/ref, не secret/credential values.

Payload принадлежит exact org/account run, provider совпадает с marketplace;
positive integer types и nullable ref проверяются строго. Producer bytes могут
быть вынесены T3 в versioned codec после согласования representation с T1.
Состояние sealed run immutable уже должно защищать новые поля; проверить trigger
против их UPDATE явно, а не предполагать покрытие.

Existing unbound rows сохранить без подстановки. Consumer отказывает в публикации
derived view до доказанного исходного binding. Новый writer должен записывать
binding в staging run из уже проверенного guard и seal его в той же transaction.
Legacy writer compatibility/mandatory insert constraint согласовать с dormant
consumer rollout; никаких изменений live writer или feature flags в этой заявке.

Exact replay сравнивает frozen binding с actual guarded binding до возврата receipt.
Перепривязка не разрешает переиспользовать старые source observations под новым seller.
Snapshot v2 является derived fingerprint, не provider high-water mark и не auth token.

## Acceptance

Actual runtime SQL: UPDATE sealed binding denied; cross-org/account/provider rejected;
NULL отличается от non-NULL ref; exact Unicode unchanged. Two sessions rebind vs publish:
либо исходный guarded commit, либо отказ, никогда relabel. Старый sealed unbound run
не становится bound посредством read. Different binding exact replay rejected.
Wrong account FK/RLS отдельно от application guard. Downgrade с ненулевыми binding
данными отказывает без потери provenance; не удаляет новые поля с историей silently.

Статус: schema request, DB acceptance **NOT_RUN**. T3 не меняет shared ORM/migrations,
не подключает provider/production и не активирует новый HTTP router.
