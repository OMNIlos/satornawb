# Satorna Avito Orders Collector

Chrome Manifest V3 extension for collecting Avito seller order details that are missing from the Avito Orders API.

## Local Install

1. Run `npm install`.
2. Run `npm run build`.
3. Open `chrome://extensions`.
4. Enable Developer mode.
5. Click Load unpacked.
6. Select `avito-orders-extension/dist`.
7. Open a logged-in Avito orders page.
8. Open `/avito/orders` in Satorna.
9. Click `Создать токен` or `Перегенерировать токен`.
10. Paste the long-lived `sat_avito_...` token into the extension popup.
11. Choose what to collect: product photos, color/article from description, and size from description or chat AI.
12. Click `Собрать заказы`; the extension opens `https://www.avito.ru/orders` and sends the collected data to Satorna.

Default Satorna URL: `https://app.elfprint-system.ru`. Existing settings for the retired `satorna-wb.vercel.app` and `ogni-frontend.vercel.app` deployments are migrated automatically. The popup also supports an explicit server address.

## Local Satorna

1. Build this copy with `npm run build`. In Chrome extensions, load its `dist` folder unpacked. The installed Web Store copy is not modified by this build; disable it while testing to avoid two collectors on one page.
2. Open `http://127.0.0.1:5177/avito/orders`, sign in, and open «Настройки расширения». Create a local extension token (not the Avito API key).
3. In the new extension's Settings, click «Локальный проект :5177», paste that token, and save. Changing the address clears the previous token in the form. Connection credentials stay in local extension storage, not Chrome sync.
4. Choose photo/size/color/article collection, then run collection in your authorized Avito browser. Reload Satorna Orders when collection reports success.

The local frontend proxies `/api` to local backend `127.0.0.1:58017`; both must be running. Local delivery never falls back to the hosted platform and does not follow redirects. A production token is not a local token. Existing photos/fields can only appear if the collector finds them and the order identifiers match; collection does not change marketplace order statuses.

## What It Sends

The extension posts to:

```text
POST /api/v1/avito/orders/browser-snapshot
```

Payload shape:

```json
{
  "capturedAt": "2026-08-06T10:00:00.000Z",
  "pageUrl": "https://www.avito.ru/profile/orders",
  "orders": [
    {
      "orderId": "ord_1",
      "marketplaceId": "123456",
      "trackNumber": "TRACK-1",
      "buyerName": "Иван",
      "items": [
        {
          "itemId": "8098482225",
          "title": "Худи черный размер M",
          "itemUrl": "https://www.avito.ru/...",
          "imageUrl": "https://70.img.avito.st/...",
          "sellerArticle": "BT-42",
          "size": "M",
          "color": "черный"
        }
      ]
    }
  ]
}
```

## Notes

The collector prefers stable `data-marker`, link, image, and visible text selectors. It uses list pagination and label-generation controls, never shipping, publishing, or price-changing actions.
# Одноразовый сбор фото объявлений (локальная версия 0.2.5)

Обновите распакованное расширение и нажмите «Сохранить фото объявлений».
Репрайсер должен быть хотя бы один раз загружен в Satorna: список объявлений берётся из его сохранённых данных.
Расширение получает только объявления без сохранённой фотографии. В служебной вкладке проходит страницы списка Авито Pro и собирает фотографии пачками (включая CSS-миниатюры), привязывая их по ID объявления. Ожидает готовность карточек и пагинации, а не загрузку всех ресурсов страницы. Сами изображения скачиваются и сохраняются четырьмя параллельными обработчиками. Только оставшиеся фото ищет в отдельных объявлениях, используя одну служебную вкладку.
В БД сохраняются сами изображения и миниатюры; таблица читает их из Satorna, без повторного обхода Авито.
Повторный запуск пропускает сохранённые снимки и продолжает недостающие. Закрывать popup можно.
Отдельные объявления без фото пропускаются без остановки всего сбора. При остановке браузера или проверке безопасности сохранённое не теряется. Проверка безопасности остаётся в открытой вкладке для ручного прохождения; затем запустите сбор ещё раз.
Кнопка «Остановить сбор фото» завершает сбор после текущей операции.
Фотографии привязаны к организации, аккаунту и ID объявления, не к названию товара.
