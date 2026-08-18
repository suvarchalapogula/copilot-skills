
Previewing README.md
Orders API — E2E Test Suite
14 tests across three tiers: happy path, schema validation, and end-to-end flows.

Setup
pip install -r requirements.txt

export API_BASE_URL=https://your-api.example.com/v1   # required
export API_TOKEN=<your token>                          # required if authenticated
export ORDERS_PATH=/orders                             # optional, this is the default
export MAX_LATENCY_MS=2000                             # optional latency budget
Nothing is hard-coded — with no API_BASE_URL set, the suite skips rather than fails.

Running
python -m pytest . -v                       # everything
python -m pytest . -v -m "not destructive"  # read-only: safe against shared environments
python -m pytest . -v -m happy_path         # one tier at a time
python -m pytest . -v -m schema
python -m pytest . -v -m e2e
Start with -m "not destructive". The destructive tests create, update, and delete real orders. Point them at a test or staging environment first — never production until you have reviewed what they do.

What each tier covers
Happy path (3) — list orders, create an order, fetch one by id. Asserts status code, Content-Type, non-empty body, and response time against the latency budget.

Schema (5) — validates responses against schemas.py using JSON Schema draft 2020-12: required fields present, types correct, status within its enum, no nulls in required fields. Also checks that a 404 returns a structured error and that an invalid payload is rejected with 400/422.

E2E (6) — the full lifecycle (create → read → update → verify the change persisted → delete → confirm 404), auth enforcement with a missing and an invalid token, pagination pages being disjoint and honoring pageSize, read-after-write visibility with retry for eventual consistency, and delete idempotency.

Every test that creates data cleans it up in teardown, including when the test fails.

Before your first run — two files to adjust
conftest.py → sample_order is the one place the suite assumes a data model. Change the payload to something your API accepts.

schemas.py contains inferred schemas describing the conventional REST order shape — they are not generated from a contract. Adjust required and the status enum to match your actual API, or regenerate them from your OpenAPI spec.

Adapting to your API
The suite handles several common conventions automatically:

Order id in either id or orderId
List responses as a bare array, or wrapped in data, items, orders, or results
Update via PATCH, falling back to PUT on a 405
429 rate limiting, with a Retry-After backoff and a 100 ms gap between requests
If your API is public by design, delete test_auth_is_enforced — it asserts that an unauthenticated request is rejected.

