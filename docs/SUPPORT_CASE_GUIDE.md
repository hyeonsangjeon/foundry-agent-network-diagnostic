# Support Case Guide

If the diagnostic points toward the **platform path** (Check 5 verdict = "no query" or
"answered but failed", corroborated by Check 6), you may need to open a Microsoft support case.
This guide lists what to include so the case routes correctly the first time.

## Before you open a case

1. Run the diagnostic and **save both outputs** (`report.html` and `report.json`).
2. Open `report.html` and copy the **Support case summary** block at the bottom (it is a
   ready-to-paste, plain-text summary of every check + the verdict).
3. Confirm the **read-only** nature in your description — nothing was changed in the tenant.

## What to include

| Item | Why it matters | Where to find it |
| --- | --- | --- |
| **Region** | Routing + feature availability differ by region | `config.json` → `region` |
| **Foundry account / project** | Identifies the agent deployment | `config.json` |
| **Backend FQDN + expected VIP** | The exact name that fails to resolve | `config.json` |
| **APIM mode** (internal / external / PE) | Distinguishes from the official PE pattern | `config.json` → `apim_mode` |
| **Topology diff (Check 4)** | Shows precisely how the config diverges from Template 16 | `report.html` topology table |
| **DNS verdict (Check 5)** | The 3-way root-cause direction | `report.json` → `checks[].evidence.verdict` |
| **APIM correlation (Check 6)** | Confirms break is before the backend | `report.json` |
| **Timestamps (UTC)** | Lets support correlate platform-side logs | `report.json` → per-check `timestamp` |
| **IcM / case ID** (if you already have one) | Links related investigations | your support portal |

## Questions support will likely ask

- Is the failure **reproducible**, and at what UTC time? (Capture a fresh `report.json` at repro time.)
- Does a **VM in the same subnet** resolve the backend FQDN? (Check 1 answers this — usually "yes".)
- Is the backend **reachable** at the network layer from that VM? (Check 2 — usually "yes".)
- Is the topology the **supported private-APIM pattern** or a variant? (Check 4 makes this explicit.)
- Did the **resolver / APIM logs** see the query/request at repro time? (Checks 5/6.)

## Framing the ask

Keep the request factual and avoid asserting unverified platform behavior. A good framing:

> "From a VM in the agent subnet, the backend FQDN resolves and the backend is reachable (Checks 1–2
> PASS). The configuration diverges from the network-secured Standard Agent + private-APIM pattern on
> N dimensions (Check 4). At repro time \<UTC\>, no DNS query for the backend FQDN reached our resolver
> and no request reached APIM (Checks 5–6). We need confirmation of whether the managed agent path is
> expected to resolve a custom private-only FQDN in our configuration, and the supported path if not."

## Scope reminder

This tool is **read-only** and makes **no changes** to your resources. It only reads configuration
and logs you already have access to. Share the generated reports freely — they contain only the
values you put in `config.json` (use placeholders if you need to redact before sharing).

See [`docs/REFERENCES.md`](REFERENCES.md) for the official documentation to cite in the case.
