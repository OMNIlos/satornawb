print('start before imports', flush=True)
from tests.test_app import auth_headers, client
print('imported test helpers', flush=True)
from app.routers import wb_reports_bff
print('imported bff', flush=True)
api = client()
print('client made', flush=True)
headers = auth_headers(api, 'viewer')
print('headers made', flush=True)
