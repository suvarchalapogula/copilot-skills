---
name: api-testing
description: |
  Tests an HTTP/REST API end to end: happy-path checks on every endpoint, response
  schema validation against an OpenAPI/JSON Schema contract, and multi-step E2E flow
  checks (create -> read -> update -> delete, auth, pagination). Produces a runnable
  pytest suite plus a pass/fail test report. Use when the user says "test my API",
  "run happy path tests", "validate the API response schema", "check my OpenAPI
  contract", "write E2E tests for this endpoint", "smoke test this service", or
  shares a Swagger/OpenAPI spec or a base URL to verify. Do NOT use for UI/browser
  testing, load or performance testing, security penetration testing, or for calling
  Microsoft 365 Graph endpoints on the user's behalf.
cowork:
  category: automation
  icon: TestBeaker
---

# API Testing Agent

Validate an HTTP API across three tiers — happy path, schema, and end-to-end flows —
and hand back a runnable test suite plus a readable report.

## When NOT to Use

- Browser/UI testing (Selenium, Playwright page flows) — not this skill.
- Load, stress, or performance benchmarking.
- Security penetration testing or vulnerability scanning.
- Calling the user's real Microsoft 365 / Graph data — use the M365 tools directly.
- Production endpoints with destructive verbs unless the user explicitly confirms.

## Inputs to Gather First

Ask only for what is missing; default rather than interrogate.

| Input | How to obtain | Default if absent |
|-------|---------------|-------------------|
| Base URL / environment | User message, README, `.env`, spec `servers:` | Ask once |
| API contract | OpenAPI/Swagger file (`glob **/openapi*.y*ml`, `**/swagger*.json`), or the spec URL | Infer schema from a sample 200 response |
| Auth | User message, env var names in repo | Bearer token from env var `API_TOKEN`, never hard-coded |
| Endpoints in scope | Spec paths, or user list | All paths in the spec |
| Test data | User-provided fixtures | Generate minimal valid payloads from the schema |

Never invent credentials, tokens, or production URLs. Use a clearly marked
placeholder (`[SET API_TOKEN]`) when a secret is missing.

## Workflow

1. **Discover the contract.** Use `glob`/`grep` to find an OpenAPI/Swagger spec, or
   `web_fetch` the spec URL. Parse paths, methods, required parameters, request
   bodies, and response schemas per status code. If no spec exists, derive an
   inferred JSON Schema from one live sample response per endpoint and label it
   "inferred — not contract-backed".
2. **Plan the matrix.** Build a table of `endpoint | method | tier | expected status`.
   Cover every endpoint at the happy-path tier; schema tier for every 2xx response;
   E2E tier for each resource lifecycle the spec supports.
3. **Happy-path tests.** One test per endpoint with valid inputs: assert expected
   2xx status, content-type, non-empty body, and response time under a stated
   threshold (default 2000 ms). Include the documented auth header.
4. **Schema validation tests.** Validate each response against its schema using
   `jsonschema` (draft 2020-12). Assert required fields present, types correct,
   enums honored, no unexpected `null` on non-nullable fields. Report additive
   drift (extra fields) as a warning, missing/mistyped fields as a failure.
5. **E2E flow tests.** Chain requests with state carried between steps — create a
   resource, read it back by returned id, update it, verify the change, delete it,
   confirm a 404 afterwards. Also cover auth (valid vs missing token), pagination
   (page 1 vs page 2 disjoint), and idempotency where documented. Always clean up
   created resources in teardown.
6. **Generate the suite.** Write `output/api_tests/test_<api>.py` using `pytest` +
   `requests` + `jsonschema`, with fixtures for base URL and auth read from env
   vars, plus `conftest.py` and `requirements.txt`.
7. **Run it if the API is reachable.** Execute
   `python -m pytest output/api_tests -q --json-report` via bash. If the host is
   unreachable or credentials are missing, skip execution and say so plainly —
   never fabricate results.
8. **Report.** Emit the output format below. Save the run log to
   `output/api-test-report.md`.

## Output Format

```
## API Test Summary — <api name> (<base url>)
Happy path:  X/Y passed
Schema:      X/Y passed
E2E flows:   X/Y passed

### Failures
| Test | Endpoint | Expected | Actual | Evidence |
|------|----------|----------|--------|----------|

### Warnings (non-blocking)
- <schema drift, slow responses, undocumented fields>

### Not tested
- <endpoints skipped and why>
```

Then: the file paths of the generated suite, and one recommended next fix.

## Guardrails

- **Never run destructive requests (DELETE/PUT/PATCH) against a production host**
  without explicit user confirmation naming the environment.
- **Never hard-code secrets** in generated code or the report; read from env vars
  and redact tokens in any logged output.
- **Never fabricate results.** If the suite did not run, say "not executed" — do
  not report passes. Every pass/fail line must trace to an actual response.
- Do not modify application source code; only create files under `output/`.
- Respect rate limits: default to sequential requests with a 100 ms gap; back off
  on 429 rather than retrying tightly.
- State clearly when schemas are inferred rather than contract-backed.
