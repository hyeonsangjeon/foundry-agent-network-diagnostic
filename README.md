<!-- Language toggle -->
**English | [한국어](README.ko.md)**

<h1 align="center">Foundry Agent Network Diagnostic</h1>

<p align="center">
  <strong>Pinpoint exactly where a Foundry Agent's private network path breaks — in one run.</strong>
</p>

<p align="center">
  <a href="https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/actions/workflows/ci.yml"><img src="https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/mode-read--only-1a7f37.svg" alt="Read-only">
  <img src="https://img.shields.io/badge/Foundry-Agent%20networking-0078D4.svg" alt="Foundry Agent">
  <img src="https://img.shields.io/badge/status-active-brightgreen.svg" alt="Status: active">
  <img src="https://img.shields.io/badge/dependencies-stdlib%20only-555.svg" alt="stdlib only">
</p>

<p align="center">
  <a href="https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/latest"><img src="docs/media/demo.gif" alt="One command — six checks — a color-coded root-cause verdict" width="860"></a>
</p>

<p align="center">
  <strong>One command → six checks → a shareable, color-coded root-cause verdict.</strong>
</p>

<div align="center">

<details>
<summary><img alt="▶ Watch the 5-minute walkthrough — KO & EN · click to expand" src="https://img.shields.io/badge/%E2%96%B6%20Watch%20the%205--min%20walkthrough-KO%20%26%20EN%20%C2%B7%20click%20to%20expand-d29922?style=for-the-badge"></summary>

<br>

<!-- INLINE PLAYER: drag-drop foundry-agent-network-diagnostic-tutorial.en.mp4 into any GitHub
     comment box; paste the resulting https://github.com/user-attachments/assets/<id> URL here as:
     <video src="https://github.com/user-attachments/assets/REPLACE-ME" controls width="820"></video> -->
<em>The full 5-minute walkthrough plays here once enabled — or watch / download it now:</em>

<p><b>⬇ Full video:</b>
<a href="https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/download/v1.1.0/foundry-agent-network-diagnostic-tutorial.en.mp4">English (5 min)</a> ·
<a href="https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/download/v1.1.0/foundry-agent-network-diagnostic-tutorial.ko.mp4">한국어 (5분)</a></p>

</details>

</div>

<p align="center">
  <sub><b>Step-by-step how-to</b> — <em>clone → local mock → test → deploy → verify → cleanup</em></sub>
</p>

> **TL;DR**
> - **What:** a read-only, one-shot diagnostic that isolates *where* a Standard Agent (BYO VNet)
>   call to a private backend (private APIM / private endpoint) breaks — targeting DNS resolution
>   failures on the BYO AI Gateway path.
> - **Who:** teams running Foundry Agents in a locked-down VNet, and the engineers who support them.
> - **How:** one command → six checks → a color-coded HTML dashboard with a clear root-cause verdict.

---

## ✨ Features

- **6-check diagnostic** that walks the path from "the VM is fine" to "here's the exact hop that breaks".
- **Template 16 topology diff** — compares your config to the official private-APIM pattern, with an
  *official / your environment / impact* table that explains **why** the path fails.
- **Static single-file HTML dashboard** — opens with no internet, no CDN, no JS dependencies
  (closed-network safe). Capture it and share it.
- **Read-only and safe** — only reads configuration and logs you already have access to.
- **Support-case-ready output** — a copy-paste summary block sized for a Microsoft support ticket.
- **Reusable across BYO VNet environments** — config-driven, zero hardcoded identifiers.

## 🎯 What it diagnoses

In a **Standard Agent BYO VNet** environment, a Foundry Agent's managed **Data Proxy** calls a
private backend (commonly an Azure API Management gateway). A frequent, confusing failure: a VM in
the same subnet resolves the backend hostname fine, but the agent call fails with:

```
Name or service not known
```

That is a **name-resolution failure before the backend is ever reached** — not a backend or TLS
problem. This tool isolates which stage breaks and whether the cause points to your configuration
or to the platform path.

## 🏗️ How it works

```mermaid
flowchart LR
    A[Agent endpoint] --> B[Tools Service]
    B --> C[Data Proxy<br/>managed host layer]
    C -->|name resolution + egress| D[(Your VNet)]
    D --> E[Backend<br/>private APIM]
    E --> F[Model / upstream]
    style C fill:#fff3cd,stroke:#9a6700
    style E fill:#e6f4ea,stroke:#1a7f37
```

The tool concentrates on the **Data Proxy → backend** hop. Checks 1–2 prove the backend is healthy
and reachable from a VM; Checks 4–6 localize the break to the **resolution stage on the managed
path**. See [`docs/PLATFORM_PATTERN.md`](docs/PLATFORM_PATTERN.md) for the full path model.

## 📋 Prerequisites

- A **Linux jump-box VM inside the VNet** (run the tool from there).
- **Python 3.10+** (the diagnostic uses the standard library only — nothing to `pip install`).
- **Azure CLI** authenticated read-only: `az login`.
- **Read access** to the relevant resources and (optionally) the DNS resolver / APIM logs.

## 🚀 Quickstart

> 🟢 **New here?** For a slower, copy-paste, step-by-step walkthrough, start with
> **[`docs/QUICKSTART.md`](docs/QUICKSTART.md)** — no Azure needed for the first demo.

```bash
# 1. Clone (the diagnostic is stdlib-only — nothing to pip install)
git clone https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic.git
cd foundry-agent-network-diagnostic

# 2. Authenticate (read-only)
az login

# 3. Configure
cp config.sample.json config.json
# edit config.json with your environment values (config.json is gitignored)

# 4. Run the diagnostic
python3 src/diagnose.py --config config.json

# 5. Open the report
open report.html        # macOS
# xdg-open report.html  # Linux
```

**Try it right now with zero Azure** — built-in mock data renders the full dashboard:

```bash
python3 src/diagnose.py --config config.sample.json --mock
open report.html
```

Run a **subset of checks**:

```bash
python3 src/diagnose.py --config config.json --checks 1,2,4
```

Full install/usage walkthrough: [`docs/USAGE.md`](docs/USAGE.md).

## 🧭 Two ways to diagnose

You can either spin up a throwaway **reproduction lab** and watch the tool work end to
end, or point it at an **environment you already have**. Both end at the same read-only
`report.html`. Full guide: [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

| | **Method 1 — deploy & verify** | **Method 2 — verify existing** |
| --- | --- | --- |
| Use when | You want a clean lab to see it work | You already have a deployed environment |
| Creates Azure resources? | Yes (a small lab you own) | **No** — read-only |
| Command | `bash deploy/deploy.sh` | `bash deploy/verify-existing.sh` |

**Method 1 — deploy a reproduction lab, then verify:**

```bash
bash deploy/deploy.sh --what-if --location eastus          # free preview, creates nothing
bash deploy/deploy.sh --scenario lab --location eastus --yes   # deploy → diagnose → report.html
bash deploy/destroy.sh --resource-group rg-agent-net-lab --yes # tear it down when done
```

It provisions a small real network path (VNet + delegated agent subnet + private-endpoint
backend behind a custom private FQDN), writes `config.json` from the outputs, runs the
diagnostic, and opens `report.html`. Use `--scenario apim` for a faithful (but ~45-min,
costlier) API Management gateway path.

**Method 2 — verify an environment that is already deployed** (creates nothing):

```bash
bash deploy/verify-existing.sh        # prompts for endpoint + network settings, then diagnoses
```

> Only `deploy.sh` / `destroy.sh` touch Azure resources (a resource group you name). The
> **diagnostic itself is always read-only.**

<details>
<summary>Example console output (mock)</summary>

```
Foundry Agent Network Diagnostic
  mode=mock  generated=2026-06-22T05:17:28Z  v1.0.1
------------------------------------------------------------------------
            [PASS]  Hostname resolution (VM perspective)
            [PASS]  Backend reachability (network layer)
            [WARN]  Foundry connection topology
            [WARN]  Topology diff vs official Template 16
            [FAIL]  DNS query observation (root-cause)
            [FAIL]  APIM gateway log correlation
------------------------------------------------------------------------
  PASS=2  WARN=2  FAIL=2  SKIPPED=0  INFO=0

  VERDICT: DNS query never reached your resolver — the managed agent path appears to bypass this VNet DNS path
           Check 6 corroborates: no request reached APIM in the window — the break is before the backend.
```
</details>

## 🔍 The 6 checks

| # | Check | What it looks at | PASS / WARN / FAIL means |
| --- | --- | --- | --- |
| 1 | **Hostname resolution (VM)** | Resolves the backend FQDN from the VM; dumps `/etc/resolv.conf` | PASS = VM baseline OK · FAIL = VM can't resolve |
| 2 | **Backend reachability** | TCP + TLS to the VIP:443 (SNI = your FQDN) | PASS = backend alive & reachable · FAIL = network/backend issue |
| 3 | **Foundry connection topology** | Connection category (`ModelGateway` vs `ApiManagement`); agent subnet delegation | WARN = diverges from recommended |
| 4 | **Topology diff vs Template 16** | 5-dimension diff: official / your environment / impact | WARN = config diverges from the supported pattern |
| 5 | **DNS query observation** ★ | Did a query for the FQDN reach the resolver? 3-way verdict | FAIL = no query / failed query · root-cause direction |
| 6 | **APIM gateway log correlation** | Did a request reach APIM in the same window? | FAIL = break is before APIM (DNS stage) |

★ Check 5 is the heart: it splits **environment configuration** (DNS zone-link / forwarding) from the
**platform path** (managed resolver behavior).

## 📊 Sample output

<p align="center">
  <img src="examples/sample_report.png" alt="Foundry Agent Network Diagnostic full HTML dashboard" width="760">
</p>

The dashboard ([`examples/sample_report.html`](examples/sample_report.html), shown above) shows:

- a **root-cause verdict banner** at the top (which of the 3-way outcomes + a one-line explanation),
- six **color-coded cards** (green PASS / amber WARN / red FAIL / grey SKIPPED) with raw evidence,
- the **Check 4 topology table**, and
- a **copy-paste support-case block** at the bottom.

## 🔒 Safety

> **This tool is read-only and makes NO changes to your resources.**
> It only reads configuration and logs you already have access to. No resource is ever created,
> updated, or deleted. The generated reports contain only the values you put in `config.json`
> (which is gitignored so it is never committed).

## 💡 Example scenario

A regulated enterprise runs a Standard Agent in a BYO VNet, with a **classic internal-mode APIM**
behind a **custom private-only FQDN** (`llm.<your-apim>.<your-domain>`). A VM in the agent subnet
resolves that FQDN and reaches APIM on 443 — yet the agent call fails with `Name or service not
known`. Running this tool produces: Checks 1–2 **PASS** (VM + backend fine), Check 4 **WARN**
(four dimensions diverge from Template 16), Checks 5–6 **FAIL** (no DNS query and no APIM request at
repro time). Verdict: the break is **before the backend, at the resolution stage** — direction
*platform path*, marked "needs verification".

## ❓ FAQ / Troubleshooting

- **Do I need to install anything?** No — the diagnostic is standard-library only. `requirements.txt`
  only lists *optional* extras for the SDK A/B helper.
- **`az` calls return permission errors.** Those checks become **SKIPPED** with a manual-input
  fallback — the tool never crashes. Re-run with broader read access if you can.
- **Check 5/6 are SKIPPED.** You didn't provide a Log Analytics workspace, so they ran in manual
  mode. Answer the single question each prints, or add `dns_resolver_log` / `apim_gateway_log` to
  `config.json`.
- **Can I run it offline / in a closed network?** Yes. `report.html` is a single self-contained file
  with no external dependencies. `--mock` runs with no Azure or network at all.
- **Is it safe to share the report?** Yes — it contains only your `config.json` values. Use
  placeholders if you need to redact before sharing.

## 📚 References

- [`docs/QUICKSTART.md`](docs/QUICKSTART.md) — a step-by-step, run-it-locally guide for first-time users.
- [`docs/REFERENCES.md`](docs/REFERENCES.md) — official Microsoft Learn pages and the foundry-samples
  network-secured Standard Agent (private-APIM) templates that define the **Template 16** baseline.
- [`docs/PLATFORM_PATTERN.md`](docs/PLATFORM_PATTERN.md) — the Foundry Agent path model and why
  internal-mode + custom FQDN diverges.
- [`docs/SUPPORT_CASE_GUIDE.md`](docs/SUPPORT_CASE_GUIDE.md) — what to include in a Microsoft support case.
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — the two diagnostic methods + the reproduction-lab deploy automation.

## 📝 Changelog

See [`CHANGELOG.md`](CHANGELOG.md). Current release: **v1.1.0**.

## 👤 Author

**Hyeonsang Jeon** · Microsoft Global Black Belt AI Apps

---

**English | [한국어](README.ko.md)** · Licensed under [MIT](LICENSE).
