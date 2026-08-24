# PRD: Защита от скачков цен и входных метрик

## 1. Назначение

Защитить WB-репрайсер от опасной отправки цен, если изменилась сама цена или дернулись входные метрики: остатки, СПП, себестоимость, логистика, выкуп, промо.

## 2. Роли

- Мария: видит, почему автоцены остановлены.
- Менеджер: разбирает строки с warning.
- `price_sender`: подтверждает безопасную отправку.
- `settings_editor/admin`: разблокирует freeze.
- Разработка: реализует guards на backend.

## 3. Пользовательские сценарии

- Система блокирует отправку цен, если WB не отдал остатки или СПП резко пропала.
- Менеджер видит affected SKU и причину блокировки.
- Пользователь с правом unlock сравнивает старое/новое значение и подтверждает или оставляет freeze.
- После восстановления источника система пересчитывает drafts.

## 4. Данные

- metric key;
- current value;
- previous baseline;
- delta absolute/percent;
- min/max threshold;
- source;
- freshness;
- affected strategies;
- affected SKU count;
- freeze reason;
- unlock audit.

## 5. Guards

### Price guards

- per-update change, default 6%;
- per-day change, default 20%;
- P_min/P_max;
- min_price/promo bounds;
- negative margin block;
- WB apply error block.

### Input guards

По INDEEPA и ТЗ:

- общая стоимость остатков;
- сумма себестоимости;
- доставка к клиенту;
- процент выкупа;
- наличие промо;
- наличие СПП;
- общий остаток, шт;
- общий остаток change %;
- логистика/хранение;
- forecast СПП, если включена.

## 6. Бизнес-правила

- Если критичная метрика вышла за порог, auto-send блокируется.
- Ручной draft можно показать, но commit требует approval.
- Разблокировка должна быть scoped: account/metric/period/SKU group.
- Unlock не меняет исторические baseline без отдельного действия.
- После unlock система пересчитывает affected drafts.
- Каждый guard должен объяснять, почему сработал и какие действия доступны.

## 7. Состояния

| State | Поведение |
|---|---|
| `ok` | Нет блокировок |
| `warning` | Можно смотреть, commit требует осторожности |
| `freeze` | Auto-send запрещен |
| `manual_approval_only` | Только ручной approval |
| `source_missing` | Источник не пришел |
| `source_stale` | Источник устарел |
| `unlock_pending` | Запрошено подтверждение |
| `unlocked` | Разблокировано с audit |

## 8. Опасные действия

- unlock freeze;
- изменение thresholds;
- игнорирование лимитов при входе в акцию;
- отправка цен при partial data;
- снижение цены ниже min threshold.

## 9. Что уже есть в Vella

- концепция guards и safe price;
- audit/draft-first паттерн;
- базовые threshold states в дизайне.

## 10. Что нужно доделать

- input guard engine;
- thresholds model;
- guard dashboard;
- freeze/unlock flow;
- backend enforcement перед WB apply;
- audit и alerting.

## 11. v1 replacement minimum

- price guards;
- input guards по СПП, остаткам, COGS, логистике, промо;
- freeze state в таблице и drawer;
- unlock только с правами;
- audit unlock.

## 12. Production hardening

- adaptive baselines;
- per-metric history charts;
- notifications to Telegram;
- incident summary;
- auto-retry after source recovery.

## 13. P2 / change request

- ML anomaly detection;
- сложные пользовательские guard expressions;
- full INDEEPA extension dependency graph.

## 14. Сложность

Оценка: 5-8 рабочих дней для v1 guards; 8-12 дней с dashboard и adaptive baseline.

## 15. Открытые вопросы

- Какие thresholds использовать по каждой метрике в v1?
- Кто имеет право unlock?
- Можно ли auto-unfreeze после восстановления источника, или всегда нужен человек?
- Нужно ли отдельное уведомление Филу/Марии при freeze?

