# Step-by-step Quickstart — Run It Locally (English)

A **hand-holding** guide for first-time users. Copy and paste one line at a time.
Short version: [Quickstart in the README](../README.md#-quickstart). Korean: [`QUICKSTART.ko.md`](QUICKSTART.ko.md).

---

## Step 0 — Move into the folder (always first)

```bash
cd /path/to/foundry-agent-network-diagnostic
```

Prerequisite: just **Python 3.10+** (`python3 --version`). The diagnostic engine is standard-library
only, so there is no `pip install` step.

---

## Step 1 — See what the tool does with the mock demo ⭐easiest (no Azure)

```bash
python3 src/diagnose.py --config config.sample.json --mock
```

→ Writes `report.html` and `report.json` into the current folder. Open the report:

```bash
open report.html        # macOS
# xdg-open report.html  # Linux
# start report.html     # Windows
```

**What you'll see:** a **root-cause verdict banner** at the top, **six color-coded cards**
(green PASS / amber WARN / red FAIL / grey SKIPPED), the **Check 4 topology table**, and a
**copy-paste support-case block** at the bottom. This demo uses no Azure and no network at all.

---

## Step 2 — Confirm the tests pass (optional)

```bash
python3 -m unittest discover -s tests
```

→ You should see `OK` and `Ran 30 tests` at the end.

That's everything you can do **without Azure**. For a real diagnosis, pick **one** of the two
methods below.

---

## Step 3 (Method A) — Verify an already-deployed environment ⭐safe, creates nothing

Make sure you're signed in to Azure first (`az login`). Then:

```bash
bash deploy/verify-existing.sh
```

→ Prompts for the endpoint + network settings → writes `config.json` → runs the diagnostic →
`report.html`. It **creates nothing**.

You can also fill the config in yourself:

```bash
cp config.sample.json config.json
# edit config.json: set backend_fqdn, expected_private_vip, etc. to real values
python3 src/diagnose.py --config config.json
open report.html
```

`config.json` is gitignored, so it is never committed.

---

## Step 3 (Method B) — Deploy a reproduction lab and look at it (creates small resources you own)

Start with a free, zero-cost preview (creates nothing):

```bash
bash deploy/deploy.sh --what-if --location koreacentral
```

Real deploy → diagnose → report:

```bash
bash deploy/deploy.sh --scenario lab --location koreacentral --yes
```

Tear it down when you're done:

```bash
bash deploy/destroy.sh
```

> **Tip:** matching the **same region** as the Foundry environment you're diagnosing makes the
> reproduction more faithful (e.g. `koreacentral`). Full options in [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).

### Running against a separate, isolated profile (tenant)

To deploy into a different tenant/subscription without touching your default `az login`, use
`--env-file`:

```bash
cp .env.sample .env.external.local
# edit .env.external.local: EXTERNAL_AZURE_CONFIG_DIR, tenant/subscription, LOCATION, etc.
bash deploy/deploy.sh --env-file .env.external.local --what-if
```

`.env*.local` files are gitignored too, so they are never committed.

---

## Recommended order

1. Do **Step 1 (mock)** first — it's the easiest and safest.
2. If you like what you see → choose **Method A** (safe, no creation) or **Method B** (reproduction lab).

## If you get stuck

- `python3: command not found` → install Python 3.10+ and retry.
- A permission/login error in `bash deploy/...` → check your `az login` state and selected subscription.
- Otherwise, capture the exact on-screen message — it pinpoints the cause quickly.

For the full walkthrough see [`docs/USAGE.md`](USAGE.md), and for the two diagnostic methods in detail
see [`docs/DEPLOYMENT.md`](DEPLOYMENT.md).
