from io import BytesIO
import pytest
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.avito import listing_photos as store
from app.avito.images_orm import AvitoListingPhoto
from app.routers import avito_listing_photos as routes


@pytest.fixture
def photos(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    AvitoListingPhoto.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(store, 'get_session_factory', lambda: factory)
    image = BytesIO()
    Image.new('RGB', (800, 600), 'red').save(image, format='PNG')
    yield image.getvalue()
    engine.dispose()


def test_persistent_first_wins_tenant_and_account_isolation(photos):
    photo_id, created = store.save_photo(1, 'a', '123', photos)
    assert created
    assert store.save_photo(1, 'a', '123', b'not redownloaded') == (photo_id, False)
    assert store.photo_index(1) == {('a', '123'): photo_id}
    assert store.photo_index(2) == {}
    assert store.read_photo(2, photo_id) is None
    thumb = store.read_photo(1, photo_id)
    assert Image.open(BytesIO(thumb)).size == (240, 180)
    assert store.save_photo(1, 'b', '123', photos)[0] != photo_id
    with pytest.raises((ValueError, OSError)):
        store.save_photo(1, 'a', '124', b'not an image')


def test_context_only_missing_http_import_offline_and_auth(monkeypatch, photos):
    rows = [{'accountId': 'a', 'itemId': str(i), 'url': f'https://www.avito.ru/city/clothes/t_{i}'} for i in (123, 124)]
    monkeypatch.setattr(routes, 'list_source_cache_by_prefix', lambda org, *a, **kw: [{'rows': rows}] if org == 1 else [])
    monkeypatch.setattr(routes, 'get_source_cache', lambda *a, **kw: None)
    def auth(request):
        if not request.headers.get('X-Test-Tenant'):
            raise HTTPException(401)
        return int(request.headers['X-Test-Tenant'])
    monkeypatch.setattr(routes, 'organization', auth)
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)
    base, headers = '/api/v1/avito/repricer/photos', {'X-Test-Tenant': '1'}
    assert client.get(base + '/collection-context').status_code == 401
    assert len(client.get(base + '/collection-context', headers=headers).json()['missing']) == 2
    response = client.post(base + '/import?accountId=a&itemId=123', content=photos, headers=headers)
    assert response.status_code == 200
    photo_id = response.json()['photoId']
    context = client.get(base + '/collection-context', headers=headers).json()
    assert context['saved'] == 1 and [r['itemId'] for r in context['missing']] == ['124']
    assert client.post(base + '/import?accountId=a&itemId=123', content=photos, headers=headers).json()['created'] is False
    assert client.post(base + '/import?accountId=other&itemId=123', content=photos, headers=headers).status_code == 404
    assert client.post(base + '/import?accountId=a&itemId=124', content=b'bad', headers=headers).status_code == 422
    assert client.get(base + f'/{photo_id}', headers={'X-Test-Tenant': '2'}).status_code == 404
    response = client.get(base + f'/{photo_id}', headers=headers)
    assert response.status_code == 200 and response.headers['content-type'] == 'image/jpeg'
    assert 'private' in response.headers['cache-control']


def test_inventory_does_not_bind_foreign_or_wrong_product_urls(monkeypatch):
    monkeypatch.setattr(routes, 'list_source_cache_by_prefix', lambda *a, **kw: [{'rows': [
        {'accountId': 'a', 'itemId': '123', 'url': url} for url in (
            'https://evil.test/item_123', 'https://www.avito.ru/item_124', 'http://www.avito.ru/item_123')]}])
    monkeypatch.setattr(routes, 'get_source_cache', lambda *a, **kw: None)
    assert routes.inventory(1) == {}


def test_repricer_inventory_does_not_scrape_photos():
    from app.avito.listings import LiveAvitoListingsClient
    assert LiveAvitoListingsClient._PUBLIC_IMAGE_FETCH_LIMIT == 0
