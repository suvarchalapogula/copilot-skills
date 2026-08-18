"""Fixtures for the live Objects API suite (https://api.restful-api.dev).

This target is a real, public, internet-facing service that needs no credentials,
which makes it useful for proving the pipeline end to end. It is a shared sandbox:
anyone can read and write it, so tests never assume the collection is unchanged
between two calls.

Configuration:
    API_BASE_URL     default https://api.restful-api.dev
    OBJECTS_PATH     default /objects
    REQUEST_TIMEOUT  default 15 (public host, be generous)
    MAX_LATENCY_MS   default 5000 (internet round trip, not localhost)
"""

import os
import time

import pytest
import requests

DEFAULT_BASE = "https://api.restful-api.dev"


@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("API_BASE_URL", DEFAULT_BASE).rstrip("/")


@pytest.fixture(scope="session")
def objects_url(base_url):
    return f"{base_url}{os.environ.get('OBJECTS_PATH', '/objects')}"


@pytest.fixture(scope="session")
def timeout():
    return float(os.environ.get("REQUEST_TIMEOUT", "15"))


@pytest.fixture(scope="session")
def max_latency_ms():
    return float(os.environ.get("MAX_LATENCY_MS", "5000"))


@pytest.fixture(scope="session")
def client(timeout):
    """Session with retry-on-429 and a courtesy gap between calls.

    This is a free public service; hammering it is both rude and a good way to
    get rate limited mid-run.
    """
    session = requests.Session()
    session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
    original = session.request

    def polite(method, url, **kwargs):
        kwargs.setdefault("timeout", timeout)
        response = original(method, url, **kwargs)
        time.sleep(0.2)
        if response.status_code == 429:
            time.sleep(float(response.headers.get("Retry-After", "3")))
            response = original(method, url, **kwargs)
        return response

    session.request = polite
    yield session
    session.close()


@pytest.fixture
def sample_object():
    """A payload matching the shape the API actually accepts."""
    return {
        "name": "CI Test Device",
        "data": {"color": "Graphite", "capacity": "256 GB", "price": 499.99},
    }


@pytest.fixture
def created_object(client, objects_url, sample_object):
    """Create an object for one test and always delete it afterwards."""
    response = client.post(objects_url, json=sample_object)
    if response.status_code not in (200, 201):
        pytest.fail(f"Setup failed: POST returned {response.status_code} - {response.text[:300]}")
    created = response.json()
    assert created.get("id"), f"Create response has no id. Keys: {list(created)}"

    yield created

    client.delete(f"{objects_url}/{created['id']}")


def pytest_configure(config):
    config.addinivalue_line("markers", "happy_path: valid-input checks")
    config.addinivalue_line("markers", "schema: response contract validation")
    config.addinivalue_line("markers", "e2e: multi-step lifecycle flows")
    config.addinivalue_line("markers", "destructive: creates or deletes real data")
