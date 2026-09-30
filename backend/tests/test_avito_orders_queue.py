from app.avito.orders import AvitoOrderItem, AvitoOrderRow, AvitoOrdersBrowserOrder, AvitoOrdersBrowserSnapshot, AvitoOrdersFetchResult, LiveAvitoOrdersClient
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

from fastapi import BackgroundTasks, Request

from app.avito.orders_picking_xlsx import build_avito_orders_picking_xlsx
from app.avito.orders_queue import fetch_full_queue, merge_queue_rows, select_queue
from app.routers import avito_orders


def order(order_id: str, status: str, updated: str = "2026-09-30T10:00:00+00:00") -> AvitoOrderRow:
    return AvitoOrderRow(
        orderId=order_id, accountId="account-1", status=status, createdAt="2026-07-01T00:00:00+00:00",
        statusSource="avito_api", statusObservedAt=updated, sourceStatus="fresh",
        items=[AvitoOrderItem(itemId="item-1", title="Товар", size="M", color="чёрный")],
    )


class Pages:
    def __init__(self, pages, total=None, by_id=None):
        self.pages = pages
        self.total = total
        self.by_id = by_id or {}
        self.requests = []

    def fetch_orders(self, request):
        self.requests.append(request)
        if request.ids:
            rows = [self.by_id[key] for key in request.ids if key in self.by_id]
            return AvitoOrdersFetchResult(status="synced", orders=rows, total=len(rows))
        value = self.pages[request.page - 1]
        return value if isinstance(value, AvitoOrdersFetchResult) else AvitoOrdersFetchResult(status="synced", orders=value, total=self.total or sum(len(page) for page in self.pages if isinstance(page, list)))


def test_queue_fetches_old_active_order_across_pages_and_moves_status_without_duplicate():
    first = [order(f"order-{index}", "ready_to_ship") for index in range(20)]
    second = [order("old-order", "in_transit")]
    client = Pages([first, second])
    rows, complete, error = fetch_full_queue(client, previous=[order("old-order", "ready_to_ship", "2026-09-29T10:00:00+00:00")], snapshot=None)
    assert complete and error is None
    assert len(rows) == 21
    assert len(client.requests) == 2
    assert all(request.dateFrom is None for request in client.requests)
    assert "old-order" not in {row.orderId for row in select_queue(rows, "ready_to_ship")}
    assert "old-order" in {row.orderId for row in select_queue(rows, "in_transit")}


def test_stale_snapshot_cannot_restore_old_status_or_shipment_number():
    prior = order("order-1", "in_transit")
    prior.shipmentNumber = "009 888 7777"
    prior.shipmentNumberObservedAt = "2026-09-30T11:00:00+00:00"
    incoming = order("order-1", "ready_to_ship", "2026-09-29T10:00:00+00:00")
    snapshot = AvitoOrdersBrowserSnapshot(capturedAt="2026-09-29T09:00:00+00:00", orders=[
        AvitoOrdersBrowserOrder(orderId="order-1", accountId="account-1", status="ready_to_ship", shipmentNumber="001 111 2222"),
    ])
    merged = merge_queue_rows([prior], [incoming], snapshot)
    assert merged[0].status == "in_transit"
    assert merged[0].shipmentNumber == "009 888 7777"


def test_current_listing_cannot_replace_ordered_variant_or_duplicate_item_id():
    prior = order("order-1", "ready_to_ship")
    prior.items = [
        AvitoOrderItem(itemId="item-1", lineIndex=0, title="Худи", size="M", color="чёрный"),
        AvitoOrderItem(itemId="item-1", lineIndex=1, title="Худи", size="L", color="белый"),
    ]
    current = order("order-1", "ready_to_ship")
    current.items = [item.model_copy(deep=True) for item in prior.items]
    snapshot = AvitoOrdersBrowserSnapshot(capturedAt="2026-09-30T12:00:00Z", orders=[
        AvitoOrdersBrowserOrder(orderId="order-1", accountId="account-1", items=[
            {"itemId": "item-1", "size": "XL", "color": "красный", "imageUrl": "https://70.img.avito.st/new.jpg", "sources": {"size": "description", "color": "listing", "imageUrl": "listing"}},
        ]),
    ])
    rows = merge_queue_rows([prior], [current], snapshot)
    assert [(item.size, item.color, item.imageUrl) for item in rows[0].items] == [("M", "чёрный", None), ("L", "белый", None)]


def test_multiple_shipments_keep_previous_number_only_as_history():
    prior = order("order-1", "ready_to_ship")
    prior.shipmentNumber = "001 222 3333"
    prior.shipmentNumberState = "confirmed"
    incoming = LiveAvitoOrdersClient("test-token")._order_row({
        "id": "order-1", "accountId": "account-1", "status": "ready_to_ship",
        "shipments": [{"id": "first"}, {"id": "second"}],
    })
    snapshot = AvitoOrdersBrowserSnapshot(capturedAt="2026-09-30T13:00:00Z", orders=[
        AvitoOrdersBrowserOrder(orderId="order-1", accountId="account-1", shipmentNumber="999 888 7777"),
    ])
    row = merge_queue_rows([prior], [incoming], snapshot)[0]
    assert row.shipmentNumber is None and row.shipmentNumberState == "ambiguous"
    assert row.shipmentNumberHistory[0]["number"] == "001 222 3333"


def test_incomplete_fetch_keeps_previous_rows_and_blocks_refresh():
    blocked = AvitoOrdersFetchResult(status="blocked", error={"code": "rate_limited", "message": "429", "retryable": True})
    rows, complete, error = fetch_full_queue(Pages([[order(f"new-{index}", "ready_to_ship") for index in range(20)], blocked], total=21), previous=[order("old", "ready_to_ship")], snapshot=None)
    assert not complete and error is not None
    assert [row.orderId for row in rows] == ["old"]


def test_known_active_order_is_rechecked_by_id_when_list_omits_it():
    old = order("old", "ready_to_ship", "2026-09-29T10:00:00+00:00")
    client = Pages([[]], by_id={"old": order("old", "in_transit")})
    rows, complete, error = fetch_full_queue(client, previous=[old], snapshot=None)
    assert complete and error is None
    assert client.requests[-1].ids == ["old"]
    assert [row.orderId for row in select_queue(rows, "in_transit")] == ["old"]
    assert select_queue(rows, "ready_to_ship") == []


def test_unverified_old_active_order_blocks_working_export():
    old = order("old", "ready_to_ship")
    rows, complete, error = fetch_full_queue(Pages([[]]), previous=[old], snapshot=None)
    assert not complete and error["code"] == "active_orders_unverified"
    assert rows == [old]


def test_unknown_and_return_phase_never_enter_working_exports():
    unknown = order("unknown", "mystery")
    returned = order("return", "on_return")
    returned.returnStatus = "started"
    pickup = order("pickup", "on_return")
    pickup.returnStatus = "ready_for_pickup"
    rows = merge_queue_rows([], [unknown, returned, pickup], None)
    assert [row.orderId for row in select_queue(rows, "return_pickup")] == ["pickup"]
    assert [row.orderId for row in select_queue(rows, "return_inbound")] == ["return"]
    assert [row.orderId for row in select_queue(rows, "review")] == ["unknown"]


def test_xlsx_preserves_shipment_text_and_embeds_safe_image():
    row = order("order-1", "ready_to_ship")
    row.shipmentNumber = "001 526 8946"
    row.items[0].imageUrl = "https://70.img.avito.st/photo.png"
    image = b"\x89PNG\r\n\x1a\n" + b"synthetic image"
    content = build_avito_orders_picking_xlsx(
        [row], date_from=date(2026, 9, 30), as_of="2026-09-30T10:00:00Z",
        image_loader=lambda _url: (image, "png"),
    )
    with ZipFile(BytesIO(content)) as book:
        sheet = book.read("xl/worksheets/sheet1.xml").decode()
        assert 'r="C6" s="2" t="inlineStr"' in sheet
        assert "001 526 8946" in sheet
        assert "<drawing r:id=\"rId1\"/>" in sheet
        assert book.read("xl/media/image1.png") == image


def test_stale_queue_returns_existing_rows_and_refreshes_in_background(monkeypatch):
    cached = {
        "rows": [order("old", "ready_to_ship").model_dump(mode="json")],
        "complete": True,
        "lastSuccessfulRefresh": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
    }
    monkeypatch.setattr(avito_orders, "_orders_client_for_request", lambda _request: (SimpleNamespace(organization_id=1), object(), "test-token"))
    monkeypatch.setattr(avito_orders, "get_source_cache", lambda *_args, **_kwargs: cached)
    monkeypatch.setattr(avito_orders, "_enrich_orders_with_return_matches", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(avito_orders, "_pickup_unreceived", lambda rows, *_args: rows)
    monkeypatch.setattr(avito_orders, "_browser_snapshot_from_cache", lambda *_args: None)
    tasks = BackgroundTasks()
    response = avito_orders.get_avito_orders_queue(
        Request({"type": "http", "headers": []}), tasks,
        mode="active", account_id=None, search="", history_from=None, page=1, limit=50, force_refresh=False,
    )
    assert [row["orderId"] for row in response["rows"]] == ["old"]
    assert response["source"]["error"]["code"] == "refresh_in_progress"
    assert response["source"]["complete"] is False
    assert len(tasks.tasks) == 1
