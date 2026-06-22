# Usage Guide (English)

Full install and usage walkthrough. For the short version, see the
[Quickstart in the README](../README.md#-quickstart). Korean: [`USAGE.ko.md`](USAGE.ko.md).

---

## 1. Prerequisites

| Requirement | Why |
| --- | --- |
| Linux jump-box VM **inside the VNet** | Check 1 establishes the "VM baseline" and reads `/etc/resolv.conf` |
| Python **3.10+** | The diagnostic uses standard library only |
| Azure CLI (`az`) signed in | Checks 3/5/6 query Azure read-only via `az` |
| `dig` or `nslookup` (optional) | Gives Check 1 a second-opinion DNS answer |
| Read access to resources/logs | Checks degrade gracefully to SKIPPED without it |

The diagnostic itself needs **no third-party packages**. `requirements.txt` lists only the optional
extras for the SDK A/B helper (`examples/sdk_ab_test.py`).

## 2. Install

```bash
git clone https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic.git
cd foundry-agent-network-diagnostic
pip install -r requirements.txt   # no-op for the core tool; installs nothing required
```

## 3. Authenticate (read-only)

```bash
az login
# optional: target the right subscription
az account set --subscription "<your-subscription-guid>"
```

The tool never writes — it only runs `show`/`list`/`query` style commands.

## 4. Configure

```bash
cp config.sample.json config.json
```

Edit `config.json`. `config.json` is **gitignored**, so your values are never committed.

### Field reference

| Field | Required | Notes |
| --- | --- | --- |
| `subscription_id` | ✅ | Your subscription GUID |
| `resource_group` | ✅ | Resource group of the Foundry account |
| `region` | ✅ | Azure region (e.g. `eastus`) |
| `foundry_account` | ✅ | Foundry account/resource name |
| `foundry_project` | ✅ | Foundry project name |
| `backend_fqdn` | ✅ | The backend hostname that fails to resolve, e.g. `llm.<your-apim>.<your-domain>` |
| `expected_private_vip` | ✅ | The private IP the FQDN should resolve to (e.g. `10.x.x.x`) |
| `agent_subnet_id` | ⬜ | Full resource ID of the agent (managed) subnet — enables delegation check |
| `pe_subnet_id` | ⬜ | Full resource ID of the private-endpoint subnet |
| `apim_resource_id` | ⬜ | APIM resource ID (used in the support summary) |
| `apim_mode` | ⬜ | `internal` \| `external` \| `PE` \| `unknown` |
| `dns_resolver_log` | ⬜ | `{ "workspace_id": "<guid>" }` — omit for Check 5 manual fallback |
| `apim_gateway_log` | ⬜ | `{ "workspace_id": "<guid>" }` — omit for Check 6 manual fallback |

Keys beginning with `_` (e.g. the `_help` block in the sample) are documentation only and ignored.

Missing or placeholder required fields produce a **friendly validation error** (the tool tells you
exactly which field to fix) and exit code `2`.

## 5. Run

```bash
# Full run
python src/diagnose.py --config config.json

# Demo with no Azure / network (built-in mock scenario)
python src/diagnose.py --config config.sample.json --mock

# Subset of checks
python src/diagnose.py --config config.json --checks 1,2,4

# Choose an output directory and disable console colors
python src/diagnose.py --config config.json --out-dir ./out --no-color
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--config` | `config.json` | Path to the config file |
| `--mock` | off | Use built-in placeholder data; no Azure/network calls |
| `--checks` | all | Comma-separated subset, e.g. `1,2,4` |
| `--out-dir` | `.` | Where `report.html` / `report.json` are written |
| `--no-color` | off | Plain console output (good for CI/logs) |

## 6. Read the output

Three artifacts are produced:

- **`report.html`** — the dashboard. Open it in any browser; it needs no internet. Top banner = the
  root-cause verdict; cards = the six checks; bottom = a copy-paste support-case block.
- **`report.json`** — machine-readable: `verdict`, `summary_counts`, and `checks[]` with raw
  `evidence` and per-check `timestamp`.
- **Console summary** — the same verdict + status table, handy for CI or a terminal session.

### The verdict (3-way)

Check 5 drives the verdict:

| Check 5 evidence `verdict` | Direction | Meaning |
| --- | --- | --- |
| `no_query` | platform | No query for the FQDN reached the resolver → managed path appears to bypass this VNet DNS path (needs verification) |
| `nxdomain_or_timeout` | configuration | Query arrived but failed → DNS zone-link / forwarding issue |
| `answered_but_failed` | platform | DNS answered fine yet the call failed → platform cache / alternate resolver path |

Check 6 corroborates: if **no request reached APIM** in the same window, the break is **before the
backend** — consistent with the DNS stage.

## 7. Manual fallback (Checks 5 & 6)

If you do not provide a Log Analytics workspace (or the tool can't read it), Checks 5/6 print the
exact question to answer manually:

- **Check 5:** In your DNS resolver / Azure DNS Private Resolver query log, filter for the backend
  FQDN around the agent-call UTC time. Did a query arrive? If so, was it NXDOMAIN/timeout or a normal
  A record?
- **Check 6:** In the APIM gateway logs, did **any** request arrive in that window? No request →
  the break is before APIM.

Record the answers (or add the workspace IDs to `config.json`) and re-run.

## 8. SDK vs Playground A/B (optional)

`examples/sdk_ab_test.py` calls the same gateway connection from the Agent SDK so you can compare
against the Playground UI. **This is the only script that creates a temporary agent** (and deletes
it afterward) — it is intentionally outside `src/` and not part of the read-only diagnostic.

```bash
pip install azure-identity azure-ai-projects
python examples/sdk_ab_test.py \
  --project-endpoint https://<your-foundry>.services.ai.azure.com/api/projects/<your-project> \
  --model <your-chat-deployment>
```

- SDK succeeds + Playground fails → likely a UI support-scope issue.
- Both fail → consistent with the network-path break; rely on `src/diagnose.py`.

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| `config error ... placeholder value` | A required field still has `<...>` — replace it |
| Check 3 connection lookup "needs verification" | The preview connections API couldn't be read; verify the category in the Foundry portal |
| Check 5/6 SKIPPED | No `*_log` workspace provided — use the manual fallback |
| `'az' not found on PATH` | Install the Azure CLI; the affected checks SKIP meanwhile |
| Report won't open offline | It should — it's a single file. Check file permissions / path |

See also [`SUPPORT_CASE_GUIDE.md`](SUPPORT_CASE_GUIDE.md) and [`REFERENCES.md`](REFERENCES.md).
