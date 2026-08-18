# Live API Test Suite — restful-api.dev Objects

14 tests against a **real, public, internet-facing API**: `https://api.restful-api.dev/objects`.

No credentials needed — the service requires no authentication. This is the suite that
proves the pipeline works against a genuine service rather than a mock.

## Why this target

It supports the full set of verbs the E2E tier needs (POST, GET, PUT, PATCH, DELETE),
requires no signup, and is stable enough to run on a schedule. That combination is rare
in free public APIs — most are read-only, which makes the lifecycle tests untestable.

## Running it

```bash
pip install -r requirements.txt
python -m pytest . -v                       # all 14
python -m pytest . -v -m "not destructive"  # 9 read-only tests
```

Defaults are baked in, so no environment variables are required. Override if needed:
`API_BASE_URL`, `OBJECTS_PATH`, `REQUEST_TIMEOUT`, `MAX_LATENCY_MS`.

## The contract these tests assert

The schemas were derived from an **observed live response**, not a published OpenAPI
document — the service does not provide one. What was directly confirmed:

- `GET /objects` returns a **bare array**, not a wrapped envelope
- `id` is a **string**, not an integer — including long hex ids on newly created objects
- `data` is an object **or null**; object id 2 has `data: null`
- keys inside `data` are free-form, vary per object, and include keys with spaces

Where behaviour could not be observed directly (the exact error-body shape on a 404),
the schema stays permissive rather than asserting a guess.

## What the tests cover

**Happy path (4)** — list the collection, fetch a known object, filter by repeated `id`
query parameters, create an object.

**Schema (5)** — list and single-object validation against the observed contract, plus
three checks that pin real contract details worth knowing: ids are strings, `data` is
nullable, and an unknown id returns 404.

**E2E (5)** — the full lifecycle (create, read, update, verify persistence, delete,
confirm gone), partial update preserving untouched fields, read-after-write by id,
delete idempotency, and id uniqueness across the collection.

## Two things this suite deliberately does not do

**It never asserts an exact collection size.** The target is a shared sandbox — other
people are creating and deleting objects while your tests run. A test that assumes a
stable count would fail randomly and teach the team to ignore red builds.

**It never leaves data behind.** Every created object is deleted in teardown, including
when the test fails. The payloads contain no real information.

## Adapting this to your own API

The three-tier structure and the test patterns transfer directly. What changes is
`schemas_objects.py` (your response shape) and the `sample_object` fixture in
`conftest.py` (a payload your API accepts). Everything else — the polite session with
retry-on-429, the cleanup fixtures, the marker-based scoping — is API-agnostic.
