# Vella / SaaS для Огней

Рабочий product repo по сервису для команды "Огни": PRD, ТЗ, research, frontend, API contracts, handoff-пакеты и evidence.

Основной порядок разработки: сначала WB replacement / замена INDEEPA, затем Авито + заказы.

## Читать первым

1. `00-START-HERE.md` - короткая карта проекта для человека и AI-агента.
2. `AGENTS.md` - рабочие правила проекта, ограничения WB/Авито и routing по задачам.
3. `docs/PROJECT_STRUCTURE.md` - что лежит в каждой папке и что является source-of-truth.
4. `docs/handoffs/wb-backend-programmer-brief.md` - первое сообщение backend-разработчику.
5. `docs/handoffs/wb-backend-data-handoff-index.md` - карта данных WB для backend.

## Репозитории

Текущий repo:

- source-of-truth по требованиям, handoff, frontend, contracts, research и evidence;
- не должен становиться основным backend repo для production-разработки.

Отдельный backend repo:

- локально подготовлен как sibling folder: `/Users/dima/Downloads/Projects/ogni-vella-backend`;
- ожидаемое GitHub имя: `ogni-vella-backend`;
- пишет FastAPI/PostgreSQL/Redis/Celery backend и использует этот repo как источник требований.

## Главное для передачи backend

Backend-разработчику отправлять:

- `docs/handoffs/wb-backend-programmer-brief.md`
- `docs/handoffs/wb-backend-dev-package.md`
- `docs/handoffs/wb-backend-data-handoff-index.md`
- `docs/open-questions-current.md`
- `docs/api-contracts/README.md`

Клиенту отправлять:

- `docs/client-questions-wb-data-handoff-2026-05-25.md`

## Что не обещать

- WB auto-actions management через API: API нет, только защита через `min_price`.
- WB Personal Token для SaaS: запрещён, нужен Base Token сейчас или Service Token через WB Catalog.
- Final P&L без формул Максима.
- Реальную отправку цен без guards, approval и audit.
- Авито-мутации без отдельного API/UAT discovery.
