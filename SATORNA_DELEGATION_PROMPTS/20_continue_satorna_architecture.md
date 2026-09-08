# Продолжение архитектурной пересборки Satorna

Продолжай автономную пересборку архитектуры Satorna в workspace:

```text
/Users/ilagulakin/Desktop/Work/OgniWB
```

Главный источник состояния: `SATORNA_ARCHITECTURE_HANDOFF.md`.

Сначала полностью прочитай:

1. `SATORNA_ARCHITECTURE_HANDOFF.md`.
2. Все документы из его раздела `Read first`.
3. Последний план:
   `.worktrees/backend-satorna-canonical-advertising/docs/superpowers/plans/2026-09-06-satorna-advertising-operational-authority.md`.
4. Связанные architecture specs и `AGENTS.md`.
5. После чтения самостоятельно проверь фактическое состояние Git, кода,
   тестов и production. Не полагайся только на handoff.

## Текущее подтверждённое состояние

- Backend worktree:
  `.worktrees/backend-satorna-canonical-advertising`.
- Branch: `codex/satorna-canonical-funnel-ads-raw`.
- Git HEAD: `ec14d73`.
- Runtime revision, развёрнутая в production: `8c84e1e`.
- Production source: `/var/tmp/satorna-ads-authority-8c84e1e`.
- Production image:
  `sha256:a247504bcb3db354f77fa5b11e5bbdf73127852abf912ecc400eab9dad41339a`.
- Alembic head: `20260905_0060`.
- Текущая оценка архитектуры: около `77%` выполнено,
  `23% ±5 п.п.` осталось.
- Canonical scheduler выключен, allowlist пуст.
- Immediate rollback:
  `ogni-elfs-{api,worker,canonical-shadow-worker,beat,migrate}:rollback-1a7354f-pre-8c84e1e`.
- Backup:
  `/var/backups/satorna-ads-authority-pre-8c84e1e-20260906T210945Z`.

Обязательно сохранить пользовательские изменения:

- `var/vella_repricer_runtime_state.json`;
- `.venv`;
- любые другие уже существующие незакоммиченные файлы.

Не выполнять `reset`, `clean`, checkout чужих файлов, rebase или broad Docker
prune. Production checkout `/var/www/ogni-elfs` намеренно грязный: не изменять
и не использовать как источник релиза. GitHub не использовать.

## Следующий рекомендуемый bounded slice

Canonical final net-profit и profit/ABC classification authority.

Перед реализацией найди доказанную бизнес-формулу в документации,
существующем коде, контрактах и production. Не придумывай пороги классификации
и не выводи их эвристически из UI. Проверь:

- является ли `profitAfterLoyaltyKopecks` действительно последним полным входом
  для net profit;
- не отсутствует ли ещё один canonical expense domain;
- правила profit class, ABC code, границ, ties, нулевой и отрицательной прибыли;
- независимость результата от pagination;
- поведение exact/custom periods и incomplete evidence.

Если авторитетную формулу доказать невозможно, ничего не фабрикуй: оставь поля
`null`, зафиксируй точный blocker и автономно перейди к следующему безопасному
evidence-backed slice из handoff.

## Процесс работы

1. Проверь все worktree и пользовательские изменения.
2. Проследи текущий data flow end-to-end.
3. Составь минимальный implementation plan.
4. Реализуй через TDD: RED → минимальный GREEN → regression gate.
5. Не добавляй таблицы, абстракции, зависимости, cache или scheduler без
   доказанной необходимости.
6. Сохраняй tenant/account isolation, PostgreSQL RLS, exact-period semantics,
   missing-vs-zero и cache-only HTTP reads.
7. Выполни focused tests, Ruff, compileall, one-Alembic-head и Git integrity
   checks.
8. Выполни один изолированный полный backend suite и сравни failure IDs с
   `ops/legacy-test-failures.txt`. Известный baseline — `105` failures; новых
   или исчезнувших без объяснения быть не должно.
9. Проведи самостоятельный полный review diff.
10. После зелёных gates создай immutable release только из committed Git tree,
    исключив `.venv`, runtime-state, secrets и caches.
11. Перед production deployment создай checksum-protected backup и rollback
    tags.
12. Деплой разрешён. Используй один image digest для migrate, API, обоих
    workers и beat.
13. После rollout проверь schema, health/live/ready, два Celery pong, очереди,
    restart/OOM, строгие error logs, scheduler state, неизменность `.env` и
    production checkout.
14. Проведи transaction-read-only closed-day canary и latency gate
    `p95 ≤ 500 ms`. Не изменяй production данные ради канарейки.
15. Обнови implementation plan и корневой `SATORNA_ARCHITECTURE_HANDOFF.md`:
    commits, tests, release, backup, rollback, canary, процент готовности и
    следующий slice.
16. Коммить только свои файлы. GitHub не использовать.

Работай автономно до полностью безопасной границы, без запросов ко мне. При
неопределённости выбирай консервативное fail-closed решение и документируй его.
Регулярно сообщай краткий прогресс, но не останавливай работу ради подтверждений.
