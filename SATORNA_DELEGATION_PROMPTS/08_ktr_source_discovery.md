DONE

# Задача: поиск canonical источника КТР/локализации

Ты работаешь отдельным read-only агентом в `/Users/ilagulakin/Desktop/Work/OgniWB`.

## Перед началом

Полностью прочитай handoff, spec audit, architecture design и применимые инструкции. Изучи все repositories, migrations, DB models, imports, XLSX/CSV assets, report builders и production evidence, где встречаются КТР, локализация, `ktr_table` или похожие термины. GitHub и production не использовать.

## Цель

Закрыть discovery-gate: существует ли подтверждённый canonical source КТР и локализации, ожидаемый архитектурой как `ktr_table`.

## Исследование

Установи:

- фактическое местонахождение данных: DB/table/file/API/import;
- владельца и процесс обновления;
- organization/account scope;
- grain и ключи;
- mapping к `nmId`, `chrtId`, offer и `CatalogSku`;
- business/effective dates;
- freshness и audit evidence;
- текущих consumers;
- различие между `ktr_table` и несовместимым `krp_table`.

Если валидный source найден, опиши typed contract, ingestion/backfill и data-quality checks. Если source отсутствует, зафиксируй `null + blocker` contract и точное условие снятия blocker.

## Жёсткие границы

- Никакого fallback на `krp_table` без доказанной совместимости grain/semantics.
- Никаких синтетических значений.
- Код, schema, migrations, reports, handoff и production не менять.
- Live DB можно исследовать только если пользователь отдельно даст явное разрешение; текущая задача такого разрешения не даёт.

## Результат

Один docs-only commit с evidence index, source verdict, grain/mapping, blocker contract и следующим минимальным действием.
