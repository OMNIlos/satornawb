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

Production Satorna URL is built into the extension: `https://ogni-frontend.vercel.app`.

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

The collector prefers stable `data-marker`, link, image, and visible text selectors. It does not click Avito buttons or perform order actions.
