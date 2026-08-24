# Исправление сохранения отчёта остатков WB

## Проблема

Фоновая задача `reports.build_report_for_org` успешно получает остатки WB и строит stock payload, но ключ кэша
`reports_payload_stock_<from>_<to>_warehouse_operational` имеет длину 65 символов. Колонка
`wb_repricer_source_cache.source_key` ограничена `VARCHAR(64)`, поэтому PostgreSQL отклоняет INSERT.

Слой кэша проглатывает `SQLAlchemyError` и возвращает несохранённый payload как fallback. Celery-задача после этого
записывает короткий job key со статусом `completed`. API видит 100%, но не находит report payload и отдаёт пустой отчёт.

## Решение

1. Расширить `source_key` до `VARCHAR(255)` в SQLAlchemy ORM и отдельной Alembic-миграции.
2. После сохранения report payload в фоновой задаче прочитать его обратно из общего хранилища. Если payload отсутствует,
   завершить job как `failed` с явной ошибкой вместо ложного `completed`.
3. Добавить регрессионные тесты:
   - ORM допускает ключ длиннее 64 символов;
   - миграция расширяет колонку и корректно откатывается;
   - background report не публикует `completed`, если payload не сохранился.

## Границы

Исправление не меняет расчёты отчёта и контракт frontend API. Ошибки отдельных enrichment-запросов WB `400/404` и
двухминутное ожидание лимита Statistics остаются отдельными задачами: они не являются причиной исчезновения уже
собранного stock payload.

## Критерии готовности

- Ключ stock report для `groupBy=warehouse&source=operational` сохраняется в PostgreSQL.
- При невозможности сохранить payload job возвращает `failed`, а не `completed`.
- Целевые backend-тесты и полный `pytest` проходят.
