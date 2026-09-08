# Задача: security design шифрования marketplace credentials

Ты работаешь отдельным read-only security-агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design, auth/session code, MarketplaceAccount models, credential stores/adapters и deployment configuration. Соблюдай все применимые security instructions. GitHub и production не использовать.

## Цель

Подготовить минимальный реализуемый план миграции WB/Avito/extension credentials из plaintext к MarketplaceAccount-owned encrypted storage.

## Threat model и design

Покрой:

- угрозу утечки DB dump/backup;
- доступ runtime и migration roles;
- ciphertext или external credential reference;
- master key вне базы;
- `keyVersion`;
- authenticated encryption;
- associated data с organization/account/provider;
- controlled re-encryption;
- rotation/revoke;
- dual-read/backfill/switch/cleanup;
- проверку успешной расшифровки до удаления plaintext;
- rollback без возврата к небезопасному writer;
- запрет secrets в Celery args, logs, errors, audit и API;
- ограниченный extension ingestion token;
- encrypted backup как дополнительный, но не единственный control.

Сравни 2–3 минимальных подхода с trade-offs и выбери один для текущего deployment. Не вводи KMS/Vault, если текущая инфраструктура не может их надёжно эксплуатировать; при этом master key не должен храниться в БД или repo.

## Жёсткие границы

- Никогда не читай, не декодируй и не выводи реальные production secrets.
- Не меняй код, dependencies, env, schema, migrations, backups или production.
- Не создавай фиктивный crypto implementation.
- Не использовать GitHub/external review/auth services.

## Результат

Один docs-only commit с threat model, выбранным crypto contract, data model, migration/runbook, key rotation, tests, rollback и решениями, требующими владельца инфраструктуры.
