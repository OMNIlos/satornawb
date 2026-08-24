# Avito Orders Browser Extension Design

## Goal

Build a Chrome Manifest V3 extension that lets a logged-in Avito browser session collect order details that the public Avito Orders API does not provide reliably: product photos, size, color, seller article, listing description, and chat-derived size hints.

## Architecture

The backend remains the source of truth for the Satorna UI and XLSX export. The extension is a separate static project next to the backend repository at `../avito-orders-extension`; it reads Avito DOM pages and sends browser snapshots to a new backend endpoint. The existing `/api/v1/avito/orders` and `/api/v1/avito/orders/picking-list.xlsx` flows merge those snapshots into API rows by `orderId`, `marketplaceId`, and `itemId`.

## Data Flow

1. User opens Satorna `/avito/orders` and copies an extension token from the app.
2. User loads the unpacked extension in Chrome and saves backend URL plus token in the popup.
3. On Avito order pages, the content script reads visible order cards, item links/photos, listing descriptions, and chat text when present.
4. The background worker posts a normalized snapshot to `/api/v1/avito/orders/browser-snapshot`.
5. The backend stores the snapshot in the existing source cache and merges it into order responses and picking XLSX.

## Parsing Rules

Selectors must prefer stable attributes such as `data-marker`, `href`, `img[src]`, `time[datetime]`, and visible labels. Hash-like CSS module classes are only fallback evidence. Color, size, and seller article are parsed from listing description with regular expressions; chat size extraction uses deterministic "last mention wins" parsing for now, so no AI dependency is introduced in this first version.

## Security

The extension does not inject remote code. It only has host permissions for Avito and the configured backend. Backend writes require the normal Satorna bearer token, so browser snapshots cannot be posted anonymously.

## Scope

This version builds the local extension package, backend snapshot ingestion and merge, frontend copy/status affordance, and XLSX enrichment. It does not publish the extension to Chrome Web Store and does not automate destructive Avito actions.
