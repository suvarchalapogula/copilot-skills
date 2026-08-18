"""End-to-end tests for the orders endpoint.

Three tiers:
  happy_path - each operation works with valid input
  schema     - responses match the contract
  e2e        - multi-step flows carry state correctly

Run:
    export API_BASE_URL=https://api.example.com/v1
    export API_TOKEN=...
    python -m pytest api_tests -v

Destructive tests (create/update/delete) are opt-in:
    python -m pytest api_tests -v -m "not destructive"   # read-only run
"""

import time
import uuid

import pytest
from jsonschema import Draft202012Validator

from schemas import ERROR_SCHEMA, ORDER_LIST_SCHEMA, ORDER_SCHEMA, extract_orders


def validate(instance, schema, context=""):
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: e.path)
    if errors:
        detail = "\n".join(f"  - {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:8])
        raise AssertionError(f"Schema validation failed {context}:\n{detail}")


def elapsed_ms(response):
    return response.elapsed.total_seconds() * 1000


# ---------------------------------------------------------------- happy path

@pytest.mark.happy_path
def test_list_orders_returns_200(client, orders_url, max_latency_ms):
    response = client.get(orders_url)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:300]}"
    assert "application/json" in response.headers.get("Content-Type", "")
    assert elapsed_ms(response) < max_latency_ms, (
        f"Response took {elapsed_ms(response):.0f}ms, budget is {max_latency_ms:.0f}ms"
    )
    assert response.json() is not None


@pytest.mark.happy_path
@pytest.mark.destructive
def test_create_order_returns_201(client, orders_url, sample_order):
    response = client.post(orders_url, json=sample_order)
    assert response.status_code in (200, 201), f"Got {response.status_code}: {response.text[:300]}"
    body = response.json()
    order_id = body.get("id") or body.get("orderId")
    assert order_id, "Created order must return an id"
    client.delete(f"{orders_url}/{order_id}")


@pytest.mark.happy_path
@pytest.mark.destructive
def test_get_order_by_id_returns_200(client, orders_url, created_order):
    order_id = created_order.get("id") or created_order.get("orderId")
    response = client.get(f"{orders_url}/{order_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert str(fetched.get("id") or fetched.get("orderId")) == str(order_id)


# ------------------------------------------------------------------- schema

@pytest.mark.schema
def test_order_list_matches_schema(client, orders_url):
    response = client.get(orders_url)
    assert response.status_code == 200
    validate(response.json(), ORDER_LIST_SCHEMA, "for GET /orders")


@pytest.mark.schema
@pytest.mark.destructive
def test_single_order_matches_schema(client, orders_url, created_order):
    order_id = created_order.get("id") or created_order.get("orderId")
    response = client.get(f"{orders_url}/{order_id}")
    validate(response.json(), ORDER_SCHEMA, f"for GET /orders/{order_id}")


@pytest.mark.schema
def test_not_found_returns_structured_error(client, orders_url):
    response = client.get(f"{orders_url}/{uuid.uuid4()}")
    assert response.status_code == 404, f"Expected 404 for unknown id, got {response.status_code}"
    if response.content and "json" in response.headers.get("Content-Type", ""):
        validate(response.json(), ERROR_SCHEMA, "for a 404 response")


@pytest.mark.schema
@pytest.mark.destructive
def test_invalid_payload_returns_400(client, orders_url):
    response = client.post(orders_url, json={"items": []})
    assert response.status_code in (400, 422), (
        f"Invalid payload should be rejected, got {response.status_code}"
    )


@pytest.mark.schema
def test_no_unexpected_nulls_in_required_fields(client, orders_url):
    response = client.get(orders_url)
    orders = extract_orders(response.json())
    if not orders:
        pytest.skip("No orders returned - nothing to inspect")
    for order in orders[:10]:
        for field in ("id", "status"):
            assert order.get(field) is not None, f"Order {order.get('id')} has null {field}"


# ---------------------------------------------------------------------- e2e

@pytest.mark.e2e
@pytest.mark.destructive
def test_full_order_lifecycle(client, orders_url, sample_order):
    """create -> read back -> update -> verify -> delete -> confirm gone."""
    create = client.post(orders_url, json=sample_order)
    assert create.status_code in (200, 201), f"Create failed: {create.text[:300]}"
    order_id = create.json().get("id") or create.json().get("orderId")
    detail_url = f"{orders_url}/{order_id}"

    try:
        read = client.get(detail_url)
        assert read.status_code == 200, "Order not readable immediately after creation"
        validate(read.json(), ORDER_SCHEMA, "after create")
        assert read.json().get("customerId") == sample_order["customerId"], (
            "Persisted customerId does not match what was submitted"
        )

        update = client.patch(detail_url, json={"status": "confirmed"})
        if update.status_code == 405:
            update = client.put(detail_url, json={**sample_order, "status": "confirmed"})
        assert update.status_code in (200, 202, 204), f"Update failed: {update.status_code}"

        verify = client.get(detail_url)
        assert verify.json().get("status") == "confirmed", (
            f"Status did not persist. Expected 'confirmed', got {verify.json().get('status')!r}"
        )
    finally:
        delete = client.delete(detail_url)
        assert delete.status_code in (200, 202, 204, 404), f"Delete failed: {delete.status_code}"

    gone = client.get(detail_url)
    assert gone.status_code in (404, 410), (
        f"Deleted order is still readable (got {gone.status_code}) - delete may be a soft delete"
    )


@pytest.mark.e2e
def test_auth_is_enforced(orders_url, timeout):
    """A request with no token must not return data."""
    import requests

    response = requests.get(orders_url, timeout=timeout, headers={"Accept": "application/json"})
    assert response.status_code in (401, 403), (
        f"Unauthenticated request returned {response.status_code} - the endpoint may be public. "
        "If that is intentional, delete this test."
    )


@pytest.mark.e2e
def test_invalid_token_is_rejected(orders_url, timeout):
    import requests

    response = requests.get(
        orders_url,
        timeout=timeout,
        headers={"Authorization": "Bearer invalid-token-for-testing", "Accept": "application/json"},
    )
    assert response.status_code in (401, 403), f"Invalid token accepted with {response.status_code}"


@pytest.mark.e2e
def test_pagination_pages_are_disjoint(client, orders_url):
    page1 = client.get(orders_url, params={"page": 1, "pageSize": 5})
    page2 = client.get(orders_url, params={"page": 2, "pageSize": 5})
    assert page1.status_code == 200 and page2.status_code == 200

    ids1 = {str(o.get("id")) for o in extract_orders(page1.json())}
    ids2 = {str(o.get("id")) for o in extract_orders(page2.json())}
    if not ids2:
        pytest.skip("Fewer than 2 pages of data - cannot verify pagination")
    assert not (ids1 & ids2), f"Pages 1 and 2 share {len(ids1 & ids2)} order(s) - pagination is leaking"
    assert len(ids1) <= 5, f"pageSize=5 ignored; got {len(ids1)} orders"


@pytest.mark.e2e
@pytest.mark.destructive
def test_created_order_appears_in_list(client, orders_url, created_order):
    """A newly created order must be visible in the collection (read-after-write)."""
    order_id = str(created_order.get("id") or created_order.get("orderId"))
    for attempt in range(3):
        listing = client.get(orders_url, params={"pageSize": 100})
        ids = {str(o.get("id")) for o in extract_orders(listing.json())}
        if order_id in ids:
            return
        time.sleep(1)  # allow for eventual consistency
    pytest.fail(f"Order {order_id} was created but never appeared in the list (checked 3 times)")


@pytest.mark.e2e
@pytest.mark.destructive
def test_delete_is_idempotent(client, orders_url, sample_order):
    create = client.post(orders_url, json=sample_order)
    order_id = create.json().get("id") or create.json().get("orderId")
    detail_url = f"{orders_url}/{order_id}"

    first = client.delete(detail_url)
    assert first.status_code in (200, 202, 204)
    second = client.delete(detail_url)
    assert second.status_code in (204, 404, 410), (
        f"Second delete returned {second.status_code} - delete is not idempotent"
    )
