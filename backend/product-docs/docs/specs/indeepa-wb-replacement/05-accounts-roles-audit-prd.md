# PRD: Аккаунты, роли, доступы, audit trail

## 1. Назначение

Раздел задает production-governance: WB account health, token status, права пользователей и audit trail для действий с ценами, настройками и финансовыми данными.

## 2. Роли

- `admin`: аккаунты, токены, роли, integrations.
- `viewer`: просмотр без опасных действий.
- `settings_editor`: настройки и стратегии.
- `price_sender`: отправка цен.
- `finance_viewer`: P&L, налоги, расходы.
- `manager`: свои SKU, комментарии, отчеты.

## 3. Пользовательские сценарии

- Проверить, подключен ли WB-аккаунт и когда истекает token.
- Назначить пользователю право просмотра, редактирования настроек или отправки цен.
- Ограничить финансовые данные для менеджеров.
- Посмотреть, кто изменил стратегию или отправил цену.
- Заблокировать опасное действие без backend permission.

## 4. Данные

- account id, display name, marketplace, token status, expiry, scopes;
- user id, email/name, role, account scope, manager scope;
- permission matrix;
- audit event: actor, action, entity, old/new, approval id, timestamp, result;
- session/source metadata for system jobs.

## 5. Контролы

- account health table;
- token expiry warning;
- role matrix;
- search users;
- add/remove user;
- permission toggles;
- audit filters by actor/action/entity/date/status;
- export audit for review.

## 6. Бизнес-правила

- UI visibility не заменяет backend enforcement.
- `price_sender` не равен `settings_editor`.
- Finance access отдельный от report access.
- Изменение ролей требует admin approval.
- Token/scopes не показываются полностью в UI и audit.
- System jobs пишутся как actor `system`, но с job id и formula version.

## 7. Состояния

| State | Поведение |
|---|---|
| `connected` | Account ready |
| `token_expiring` | Warning заранее |
| `token_expired` | Price apply и data refresh blocked |
| `scope_missing` | Показать missing capability |
| `no_access` | Нет права на действие/раздел |
| `audit_empty` | Нет событий по фильтру |
| `audit_partial` | Часть событий недоступна из-за retention |

## 8. Опасные действия

- изменение токена;
- изменение ролей;
- выдача `price_sender`;
- выдача `finance_viewer`;
- удаление пользователя;
- отключение account;
- массовый export audit с sensitive fields.

## 9. Что уже есть в Vella

- роль/видимость частично заложены в навигации;
- audit-концепция видна в shell;
- dangerous actions уже проектируются через approval.

## 10. Что нужно доделать

- permission matrix;
- backend policy checks;
- account health API;
- token expiry warning;
- audit persistence;
- audit filters;
- sensitive data redaction.

## 11. v1 replacement minimum

- один WB account с health/status;
- роли `viewer`, `settings_editor`, `price_sender`, `finance_viewer`, `admin`;
- backend enforcement;
- audit для цен, настроек, imports, unlock, roles;
- no-access states.

## 12. Production hardening

- manager-level SKU scopes;
- approval workflow для role changes;
- audit retention policy;
- alerts for token expiry;
- access review report.

## 13. P2 / change request

- SSO/1C-Битрикс role sync;
- много организаций;
- сложные policy rules;
- external auditor portal.

## 14. Сложность

Оценка: 3-6 рабочих дней для v1. С approval workflow и detailed audit filters: 6-10 дней.

## 15. Открытые вопросы

- Кто в клиентской команде admin?
- Нужно ли менеджерам видеть только свои SKU?
- За сколько дней предупреждать о token expiry?
- Нужно ли Филу иметь read-only доступ в production?

