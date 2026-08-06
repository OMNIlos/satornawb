# Satorna Avito Orders Collector

Chrome Manifest V3 extension for collecting Avito seller order details that are missing from the Avito Orders API.

## Local Install

1. Open `chrome://extensions`.
2. Enable Developer mode.
3. Click Load unpacked.
4. Select this folder: `avito-orders-extension`.
5. Open a logged-in Avito orders page.
6. Open the extension popup, set backend URL, paste the Satorna access token, and click `Собрать заказы`.

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
