# GitHub Repo Setup

Дата: 2026-05-25

## 1. Backend repo

Локально готов:

```text
/Users/dima/Downloads/Projects/ogni-vella-backend
```

Статус:

- branch: `main`;
- initial commit: `6126f03 Initial WB Sprint A backend skeleton`;
- tests: `31 passed`;
- remote: not set;
- GitHub repo `DimonProgrammer/ogni-vella-backend` на момент проверки не существует.

После создания пустого repo на GitHub:

```bash
cd "/Users/dima/Downloads/Projects/ogni-vella-backend"
git remote add origin https://github.com/DimonProgrammer/ogni-vella-backend.git
git push -u origin main
```

## 2. Product/source repo

Текущий product repo:

```text
/Users/dima/Downloads/Projects/SAAS для Огней
```

Сейчас `origin` указывает на старый repo:

```text
https://github.com/DimonProgrammer/Satorna.git
```

Перед выдачей доступа backend-разработчику нужно выбрать один вариант:

1. Переименовать `Satorna` на GitHub в project-facing repo name и оставить remote.
2. Создать новый GitHub repo для product/source материалов и поменять `origin`.

Если создается новый repo, команды:

```bash
cd "/Users/dima/Downloads/Projects/SAAS для Огней"
git remote set-url origin https://github.com/DimonProgrammer/<new-product-repo>.git
git push -u origin codex/notifications-center
```

## 3. Access model

Backend-разработчику:

- read access к product/source repo;
- write access к `ogni-vella-backend`.

Не давать production secrets через GitHub. WB/Avito tokens должны идти через secure env/secret manager, не через repo files.
