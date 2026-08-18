"""Live tests against the public Objects API at https://api.restful-api.dev.

Three tiers, same structure as the orders suite:
    happy_path - endpoints answer correctly with valid input
    schema     - responses match the observed contract
    e2e        - create, read, update, verify, delete flows carry state

The target is a SHARED public sandbox. Two consequences shape these tests:
  1. Other people are writing to it concurrently, so no test asserts an exact
     collection size or that the collection is unchanged between two calls.
  2. Objects created here are visible to everyone, so payloads carry no real data
     and every created object is deleted in teardown.

    python -m pytest . -v                      # everything (creates + deletes data)
    python -m pytest . -v -m "not destructive" # read-only
"""

import uuid

import pytest
from jsonschema import Draft202012Validator

from schemas_objects import ERROR_SCHEMA, OBJECT_LIST_SCHEMA, OBJECT_SCHEMA


def validate(instance, schema, context=""):
    errors = sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: e.path)
    if errors:
        detail = "\n".join(
            f"  - {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors[:8]
        )
        raise AssertionError(f"Schema validation failed {context}:\n{detail}")


def elapsed_ms(response):
    return response.elapsed.total_seconds() * 1000


# ---------------------------------------------------------------- happy path

@pytest.mark.happy_path
def test_list_objects_returns_200(client, objects_url, max_latency_ms):
    response = client.get(objects_url)
    assert response.status_code == 200, f"Got {response.status_code}: {response.text[:300]}"
    assert "application/json" in response.headers.get("Content-Type", "")
    assert elapsed_ms(response) < max_latency_ms, (
        f"Took {elapsed_ms(response):.0f}ms against a budget of {max_latency_ms:.0f}ms"
    )
    payload = response.json()
    assert isinstance(payload, list) and payload, "Expected a non-empty array"


@pytest.mark.happy_path
def test_get_single_object_returns_200(client, objects_url):
    """Object id 1 is part of the service's seeded data."""
    response = client.get(f"{objects_url}/1")
    assert response.status_code == 200, f"Got {response.status_code}: {response.text[:300]}"
    assert response.json().get("id") == "1"


@pytest.mark.happy_path
def test_filter_by_multiple_ids(client, objects_url):
    """The collection supports repeated id query parameters."""
    response = client.get(objects_url, params=[("id", "1"), ("id", "3")])
    assert response.status_code == 200
    returned = {item["id"] for item in response.json()}
    assert returned == {"1", "3"}, f"Expected exactly ids 1 and 3, got {returned}"


@pytest.mark.happy_path
@pytest.mark.destructive
def test_create_object_succeeds(client, objects_url, sample_object):
    response = client.post(objects_url, json=sample_object)
    assert response.status_code in (200, 201), f"Got {response.status_code}: {response.text[:300]}"
    created = response.json()
    assert created.get("name") == sample_object["name"]
    client.delete(f"{objects_url}/{created['id']}")


# ------------------------------------------------------------------- schema

@pytest.mark.schema
def test_object_list_matches_schema(client, objects_url):
    response = client.get(objects_url)
    validate(response.json(), OBJECT_LIST_SCHEMA, "for GET /objects")


@pytest.mark.schema
def test_single_object_matches_schema(client, objects_url):
    response = client.get(f"{objects_url}/1")
    validate(response.json(), OBJECT_SCHEMA, "for GET /objects/1")


@pytest.mark.schema
def test_id_is_a_string_not_a_number(client, objects_url):
    """A real contract detail worth pinning: ids are strings.

    Client code that assumes integers breaks on the hex ids the service assigns
    to newly created objects.
    """
    for item in client.get(objects_url).json()[:5]:
        assert isinstance(item["id"], str), f"id {item['id']!r} is {type(item['id']).__name__}"


@pytest.mark.schema
def test_data_field_may_be_null(client, objects_url):
    """data is nullable; consumers must handle it rather than assume a dict."""
    for item in client.get(objects_url).json():
        assert item.get("data") is None or isinstance(item["data"], dict), (
            f"Object {item['id']} has data of type {type(item.get('data')).__name__}"
        )


@pytest.mark.schema
def test_unknown_id_returns_404(client, objects_url):
    response = client.get(f"{objects_url}/{uuid.uuid4().hex}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    if response.content and "json" in response.headers.get("Content-Type", ""):
        validate(response.json(), ERROR_SCHEMA, "for a 404 response")


# ---------------------------------------------------------------------- e2e

@pytest.mark.e2e
@pytest.mark.destructive
def test_full_object_lifecycle(client, objects_url, sample_object):
    """create -> read back -> update -> verify -> delete -> confirm gone."""
    create = client.post(objects_url, json=sample_object)
    assert create.status_code in (200, 201), f"Create failed: {create.text[:300]}"
    object_id = create.json()["id"]
    detail_url = f"{objects_url}/{object_id}"

    try:
        read = client.get(detail_url)
        assert read.status_code == 200, "Object not readable immediately after creation"
        validate(read.json(), OBJECT_SCHEMA, "after create")
        assert read.json()["name"] == sample_object["name"], "Persisted name does not match"

        updated_name = "CI Test Device (updated)"
        update = client.put(detail_url, json={**sample_object, "name": updated_name})
        assert update.status_code in (200, 202), f"Update failed: {update.status_code}"

        verify = client.get(detail_url)
        assert verify.json()["name"] == updated_name, (
            f"Update did not persist. Expected {updated_name!r}, got {verify.json()['name']!r}"
        )
    finally:
        delete = client.delete(detail_url)
        assert delete.status_code in (200, 202, 204), f"Delete failed: {delete.status_code}"

    gone = client.get(detail_url)
    assert gone.status_code in (404, 410), (
        f"Deleted object still readable (got {gone.status_code}) - possible soft delete"
    )


@pytest.mark.e2e
@pytest.mark.destructive
def test_partial_update_preserves_other_fields(client, objects_url, created_object):
    """PATCH changes only what it names."""
    detail_url = f"{objects_url}/{created_object['id']}"
    original_data = created_object.get("data") or {}

    response = client.patch(detail_url, json={"name": "CI Test Device (patched)"})
    assert response.status_code in (200, 202), f"PATCH failed: {response.status_code}"

    after = client.get(detail_url).json()
    assert after["name"] == "CI Test Device (patched)"
    if original_data:
        assert after.get("data"), "PATCH of name wiped the data field"


@pytest.mark.e2e
@pytest.mark.destructive
def test_created_object_is_retrievable_by_id(client, objects_url, created_object):
    """Read-after-write: a new object is immediately addressable."""
    response = client.get(f"{objects_url}/{created_object['id']}")
    assert response.status_code == 200, (
        f"Object {created_object['id']} was created but returned {response.status_code} on read"
    )
    assert response.json()["id"] == created_object["id"]


@pytest.mark.e2e
@pytest.mark.destructive
def test_delete_then_delete_again(client, objects_url, sample_object):
    """A second delete must not report success on an object that is already gone."""
    object_id = client.post(objects_url, json=sample_object).json()["id"]
    detail_url = f"{objects_url}/{object_id}"

    first = client.delete(detail_url)
    assert first.status_code in (200, 202, 204)
    second = client.delete(detail_url)
    assert second.status_code in (204, 404, 410), (
        f"Second delete returned {second.status_code} - it should report the object is gone"
    )


@pytest.mark.e2e
def test_object_ids_are_unique_across_the_collection(client, objects_url):
    items = client.get(objects_url).json()
    ids = [item["id"] for item in items]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"Collection contains duplicate ids: {duplicates}"
