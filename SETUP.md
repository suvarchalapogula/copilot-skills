# Running the API tests in GitHub Actions — setup

Follow these in order. Total time: about ten minutes.

## Step 1 — Get the files into the repo in the right layout

The workflow expects this structure. Note the tests must sit in a folder named
`api_tests` at the repository root:

```
your-repo/
  .github/
    workflows/
      api-tests.yml
  api_tests/
    conftest.py
    schemas.py
    test_orders_e2e.py
    pytest.ini
    requirements.txt
    README.md
```

**Uploading through the browser flattens folders**, which is what went wrong before.
To place a file at a nested path without dragging folders: use **Add file → Create new
file**, then type the full path into the filename box —
`.github/workflows/api-tests.yml` — and paste the contents in. GitHub creates each
folder as you type the `/`.

Do the same for each test file (`api_tests/conftest.py`, and so on), or push from a
terminal, which preserves structure automatically.

## Step 2 — Create the staging environment and its secrets

1. Repo → **Settings** → **Environments** → **New environment** → name it `staging`.
2. Under **Environment secrets**, add:

   | Secret | Value |
   |--------|-------|
   | `API_BASE_URL` | Your staging base URL, e.g. `https://staging.api.example.com/v1` |
   | `API_TOKEN` | A token for a **test account** — never your personal production credentials |

3. Optionally under **Environment variables**:

   | Variable | Purpose | Default |
   |----------|---------|---------|
   | `ORDERS_PATH` | Path to the orders collection | `/orders` |
   | `MAX_LATENCY_MS` | Latency budget per request | `2000` |

Secrets are write-only — GitHub masks them in logs and no one, including you, can read
them back afterwards.

## Step 3 — Create the production environment (with a gate)

Repeat Step 2 with the name `production` and your production values. Then, while still
on that environment's page, tick **Required reviewers** and add yourself.

This is the safety net: any run against production now pauses and waits for a human to
approve it. Without this, a scheduled or mistaken run could delete real orders.

## Step 4 — First run

Go to the **Actions** tab → **API Tests** → **Run workflow**. Leave the defaults
(`staging`, `read-only`) and click the green button.

The read-only scope skips every test that creates or deletes data, so this first run is
safe by design. Watch it complete, then open the run to see the results table in the
summary.

## Step 5 — Widen the scope once it's green

Re-run with **tier: all-including-destructive** against `staging`. This is when the full
lifecycle test — create, update, verify, delete — actually exercises your API.

Expect failures on this first full run if the inferred schemas don't match your real
payloads. That is the point: the failures tell you exactly which fields differ. Paste
them back to Copilot and the schemas get corrected.

## What runs automatically after that

| Trigger | Scope | Environment |
|---------|-------|-------------|
| Push to `main` touching the tests | read-only | staging |
| Pull request touching the tests | read-only | staging |
| Nightly at 01:30 UTC (07:00 IST) | read-only | staging |
| Manual | your choice | your choice |

Destructive tests never run automatically — only when you pick that scope by hand.

## Where results appear

- **Run summary** — a pass/fail table on the run page, no digging required.
- **Artifacts** — `results.xml` (JUnit) and `report.md`, kept 30 days.
- **Pull requests** — the check appears alongside the PR and blocks merge on failure
  once you add it as a required check under Settings → Branches.

## If something fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| "API_BASE_URL secret is not set" | Secret added to the repo instead of the environment | Settings → Environments → staging → Environment secrets |
| "Could not reach the API" | Your API is behind a firewall or VPN | Allow GitHub's runner IP ranges, or use a self-hosted runner inside your network |
| All tests fail with 401 | Token expired or wrong scope | Rotate `API_TOKEN` in the environment secrets |
| Schema failures naming specific fields | Inferred schemas don't match your payloads | Edit `api_tests/schemas.py` — or send the output to Copilot |
| Workflow doesn't appear in Actions | File not at `.github/workflows/api-tests.yml` | Check the exact path and spelling |

## A note on secrets and pull requests

Secrets are not exposed to workflows triggered by pull requests from forks. If external
contributors ever open PRs, those runs will fail at the reachability check rather than
leaking credentials — that is intended behavior, not a bug.
