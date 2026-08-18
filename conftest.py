"""Shared fixtures for the orders API test suite.

Configuration comes from environment variables so no credentials or hostnames
are ever committed:

    API_BASE_URL   e.g. https://api.example.com/v1   (required)
    API_TOKEN      bearer token                      (required if the API is authenticated)
    ORDERS_PATH    path to the orders collection      (default: /orders)
    REQUEST_TIMEOUT seconds before a request fails    (default: 10)
    MAX_LATENCY_MS latency budget per request         (default: 2000)
"""

import os
import time

import pytest
import requests


def _require(name):
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} is not set - skipping live API tests", allow_module_level=False)
    return value


@pytest.fixture(scope="session")
def base_url():
    return _require("API_BASE_URL").rstrip("/")


@pytest.fixture(scope="session")
def orders_path():
    return os.environ.get("ORDERS_PATH", "/orders")


@pytest.fixture(scope="session")
def orders_url(base_url, orders_path):
    return f"{base_url}{orders_path}"


@pytest.fixture(scope="session")
def timeout():
    return float(os.environ.get("REQUEST_TIMEOUT", "10"))


@pytest.fixture(scope="session")
def max_latency_ms():
    return float(os.environ.get("MAX_LATENCY_MS", "2000"))


@pytest.fixture(scope="session")
def auth_headers():
    token = os.environ.get("API_TOKEN")
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


@pytest.fixture(scope="session")
def client(auth_headers, timeout):
    """A requests session that rate-limits itself and never logs the token."""
    session = requests.Session()
    session.headers.update(auth_headers)

    original_request = session.request

    def throttled(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        response = original_request(method, url, **kwargs)
        time.sleep(0.1)  # be polite; avoid tripping rate limits
        if response.status_code == 429:
            retry_after = float(response.headers.get("Retry-After", "2"))
            time.sleep(retry_after)
            response = original_request(method, url, **kwargs)
        return response

    session.request = throttled
    yield session
    session.close()


@pytest.fixture
def sample_order():
    """Minimal valid order payload.

    ADJUST THIS to match your schema - it is the one place the suite makes
    assumptions about your data model.
    """
    return {
        "customerId": "test-customer-001",
        "items": [{"sku": "TEST-SKU-1", "quantity": 2, "unitPrice": 9.99}],
        "currency": "USD",
    }


@pytest.fixture
def created_order(client, orders_url, sample_order):
    """Create an order for a test, then always clean it up afterwards."""
    response = client.post(orders_url, json=sample_order)
    if response.status_code not in (200, 201):
        pytest.fail(
            f"Setup failed: POST {orders_url} returned {response.status_code} "
            f"- {response.text[:300]}"
        )
    order = response.json()
    order_id = order.get("id") or order.get("orderId")
    assert order_id, f"Created order has no id field. Body keys: {list(order)}"

    yield order

    client.delete(f"{orders_url}/{order_id}")


def pytest_configure(config):
    config.addinivalue_line("markers", "happy_path: valid-input checks per endpoint")
    config.addinivalue_line("markers", "schema: response contract validation")
    config.addinivalue_line("markers", "e2e: multi-step lifecycle flows")
    config.addinivalue_line("markers", "destructive: creates or deletes real data")
