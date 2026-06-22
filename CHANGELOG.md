# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 한국어 요약은 각 버전 하단의 **(한국어)** 블록을 참고하세요.

## [1.0.1] - 2026-06-22

Quality polish: tests, CI, and neutral wording. No change to how the diagnosis works.

### Added
- **Test suite** (`tests/`) — standard-library `unittest` only (no new dependencies): an
  end-to-end `--mock` smoke test, per-check verdict logic, the root-cause `direction` mapping,
  `config_loader` validation, the single-file HTML guarantee + JSON round-trip, and Template 16
  data integrity. Run with `python -m unittest discover -s tests`.
- **Continuous integration** (`.github/workflows/ci.yml`) — byte-compiles the sources and runs
  the test suite on Python 3.10/3.11/3.12, syntax-checks `deploy/*.sh` (`bash -n`), and compiles
  the Bicep template (`az bicep build`).

### Changed
- **Neutral wording** across `README` (EN/KO), `docs/`, and rendered report text: configuration is
  now described in environment/operator terms rather than "customer" framing. The HTML topology
  column header remains **"Your environment."**
- **`report.json` field rename** — the Check 4 topology rows now use the key **`observed`**
  (previously `customer`); the root-cause verdict `direction` value is now **`configuration`**
  (previously `customer`). Documented here because v1.0.0 had only just shipped with no downstream
  consumers; the CLI flags, `config.json` schema, check IDs, and HTML/console output are otherwise
  unchanged.
- Removed cross-repository attribution and editorial phrasing from the docs and the deploy script
  header.

**(한국어)** 품질 폴리시: 테스트·CI·중립적 표현 정리. 진단 동작에는 변화가 없습니다. **추가:** 표준 라이브러리
`unittest` 기반 **테스트 스위트**(`tests/`, 의존성 추가 없음)와 Python 3.10/3.11/3.12 행렬 + `bash -n` +
`az bicep build`를 수행하는 **CI 워크플로**(`.github/workflows/ci.yml`). **변경:** README(영/한)·`docs/`·
리포트 문구를 "고객" 프레이밍에서 환경/운영자 관점으로 중립화(HTML 토폴로지 열 머리글은 **"Your environment"**
유지), `report.json`의 Check 4 토폴로지 행 키를 `customer` → **`observed`**, 판정 `direction` 값을
`customer` → **`configuration`** 으로 변경(v1.0.0가 막 배포되어 사용처가 없어 패치로 문서화; CLI 플래그·
`config.json` 스키마·체크 ID·HTML/콘솔 출력은 그대로). 문서·배포 스크립트의 외부 레포 참조 및 홍보성 문구 제거.

## [1.0.0] - 2026-06-22

**First stable release.** The tool is feature-complete, documented (EN/KO), and verified
end-to-end against a real Foundry environment (Korea Central, external tenant). From this
release on, the public surface is governed by [Semantic Versioning](https://semver.org/):
breaking changes bump the major version.

### Stable public surface
- **Diagnostic CLI** — `python src/diagnose.py` flags `--config`, `--mock`, `--checks`,
  `--out-dir`, `--no-color`.
- **`config.json` schema** — keys consumed by the six checks (see `config.sample.json`).
- **Check IDs 1–6** — Hostname resolution, Backend reachability, Foundry connection topology,
  Template 16 topology diff, DNS query observation, APIM gateway log correlation. IDs and verdict
  semantics are stable.
- **Outputs** — self-contained `report.html`, machine-readable `report.json`, and the console
  summary, all stamped with mode + version.
- **Deploy automation** — `deploy/deploy.sh` (Method 1), `deploy/verify-existing.sh` (Method 2),
  `deploy/destroy.sh`, with `--env-file` external-tenant isolation and tenant/subscription safety
  rails.

### Capabilities (consolidated)
- **Read-only, six-step diagnosis** of a Foundry Standard Agent's BYO-VNet private network path
  (Data Proxy → private APIM / private endpoint), targeting DNS-resolution failures, plus a
  **Template 16 topology diff** that explains *why* the managed resolver path can break.
- **Two ways to diagnose** — (1) deploy a small real reproduction lab, then verify; (2) verify an
  already-deployed environment by feeding in its endpoints/config.
- **Safe-by-default** — graceful degradation to manual fallbacks when log access is
  missing; no resource is ever mutated.
- **Bilingual docs** — `README` + `docs/` in English and Korean; `examples/` sample report.

### Notes
- The lab does not provision a Foundry account, so Foundry-specific checks (3, and the log-based
  5/6) report **SKIPPED / manual** by design; the network-path checks (1, 2, 4) run for real.
- No code change versus `0.3.0` behavior — this release blesses the verified `0.3.0` surface as
  stable `1.0.0`.

**(한국어)** **첫 정식 안정 릴리스.** 기능 완성 + 영/한 문서 + 실제 Foundry 환경(Korea Central,
외부 테넌트)에서 처음부터 끝까지 검증 완료. 이번 릴리스부터 공개 인터페이스(진단 CLI 플래그,
`config.json` 스키마, 체크 ID 1–6, `report.html/json` 포맷, 배포 스크립트 플래그)는
**유의적 버전(SemVer)**으로 관리되며, 호환성을 깨는 변경은 메이저 버전을 올립니다. 동작은 검증된
`0.3.0`과 동일하며, 그 표면을 안정 버전 `1.0.0`으로 확정합니다.

## [0.3.0] - 2026-06-22

External-tenant deploy support + verified live run.

### Added
- **Isolated external-tenant deploys** — `deploy/deploy.sh`, `deploy/destroy.sh`, and
  `deploy/verify-existing.sh` now accept `--env-file <path>`. The env file is sourced and,
  when it sets `EXTERNAL_AZURE_CONFIG_DIR`, `AZURE_CONFIG_DIR` is pointed at that isolated
  Azure CLI profile so **every** `az` call in the run (including the diagnostic's) uses it —
  your default/internal `az login` is never touched.
- **Safety rails** — deploy/destroy abort unless the active tenant and subscription match
  `E2E_EXPECTED_TENANT_ID` / `E2E_EXPECTED_SUBSCRIPTION_NAME` (or `--tenant`), making a
  wrong-tenant deploy impossible. Resolution order is CLI flag > env-file > default.
- **`.env.sample`** documenting `EXTERNAL_AZURE_CONFIG_DIR`, `EXTERNAL_TENANT_ID`,
  `SUBSCRIPTION`, `LOCATION`, `SCENARIO`, `ENV_NAME`, and the two `E2E_EXPECTED_*` rails.
  `.env.external.local` / `.env*.local` are git-ignored so real tenant values never get committed.
- **External-tenant workflow docs** in `docs/DEPLOYMENT.md` and `docs/DEPLOYMENT.ko.md`.

### Changed
- `--what-if` messaging clarified: a free, empty resource group may be created so that
  group-scope validate/what-if can run; no billable resources are created in preview.

### Verified
- Ran **Method 1 end-to-end against a real external tenant** (isolated profile): 9 resources
  deployed, the live private-endpoint VIP resolved from the NIC, `config.json` generated, and the
  read-only diagnostic produced `report.html` — correctly flagging the **DNS resolution failure**
  (Check 1) for the custom private zone and degrading to safe manual fallbacks for the
  log-based checks.

**(한국어)** 외부 테넌트 배포 지원. 모든 `deploy/` 스크립트가 `--env-file`을 받아
`EXTERNAL_AZURE_CONFIG_DIR` 격리 프로필로 `az`를 실행하므로 기본 로그인은 건드리지 않습니다.
활성 테넌트/구독이 `E2E_EXPECTED_*`와 다르면 배포를 중단하는 안전장치 포함. `.env.sample` 추가,
`.env.external.local`은 git-ignore. 실제 외부 테넌트에서 방법 1을 처음부터 끝까지 검증(9개 리소스
배포 → 라이브 VIP 해석 → 진단 실행 → `report.html` 생성, 커스텀 프라이빗 존 DNS 실패를 정확히 탐지).

## [0.2.0] - 2026-06-22

Deployment automation + two diagnostic methods.

### Added
- **`deploy/` automation** with a progress-tracked UX (progress bar, stepwise `[OK]/[WARN]/[FAIL]`
  status, timestamped logs under `.deployment/`).
- **Method 1 — deploy & verify** (`deploy/deploy.sh`): provisions a small, real reproduction lab
  (VNet + agent subnet delegated to `Microsoft.App/environments` + private-endpoint subnet + a
  custom private DNS zone + a private backend behind a custom FQDN), writes `config.json` from the
  deployment outputs, runs the read-only diagnostic, and points you at `report.html`. Two scenarios:
  `lab` (Storage + Private Endpoint, fast/cheap, default) and `apim` (API Management in internal VNet
  mode, faithful but ~45 min and costlier).
- **Method 2 — verify existing** (`deploy/verify-existing.sh`): collects an already-deployed
  endpoint + network settings via flags or interactive prompts, writes `config.json`, and runs the
  diagnostic. Creates nothing.
- **`deploy/destroy.sh`** teardown with a typed-name confirmation.
- **`deploy/infra/main.bicep`** (+ `main.parameters.json`) — the reproduction-lab template.
- **`--what-if`** preview path in `deploy.sh` (preflight + validate + ARM what-if, creates nothing).
- **Docs:** [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) + [`docs/DEPLOYMENT.ko.md`](docs/DEPLOYMENT.ko.md);
  README (EN/KO) now documents the two methods; `.gitignore` covers `.deployment/`, `deployments/`,
  and `config.json` backups.

### Notes
- The **diagnostic engine remains 100% read-only.** Only `deploy.sh` / `destroy.sh` create or delete
  resources, and only inside a resource group you name. The reproduction lab is opt-in.
- `deploy.sh` registers required resource providers best-effort; if your subscription denies provider
  registration (common in enterprise tenants), it warns and continues — the deploy still works when
  the providers are already registered.

**(한국어)** 배포 자동화 + 두 가지 진단 방법 추가. 진행률 추적 UX의 **`deploy/` 자동화**,
**방법 1 배포 후 검증**(`deploy.sh` — 재현 랩 프로비저닝 →
`config.json` 생성 → 진단 → `report.html`; `lab`/`apim` 시나리오), **방법 2 기존 환경 검증**
(`verify-existing.sh`, 아무것도 생성하지 않음), **`destroy.sh`** 삭제, **Bicep 템플릿**, **`--what-if`**
미리보기, 영/한 **`docs/DEPLOYMENT`** 문서 제공. 진단 엔진은 여전히 100% 읽기 전용이며, 리소스 생성/
삭제는 사용자가 지정한 리소스 그룹 내 `deploy.sh`/`destroy.sh`만 수행합니다.

## [0.1.0] - 2026-06-22

Initial public release.

### Added
- **6-check read-only diagnostic engine** for the Foundry Agent BYO VNet private network path:
  1. Hostname resolution (VM perspective)
  2. Backend reachability (TCP + TLS, network layer)
  3. Foundry connection topology (connection category + agent subnet delegation)
  4. **Topology diff vs official Template 16** (official / your environment / impact table)
  5. **DNS query observation** (3-way root-cause verdict)
  6. APIM gateway log correlation (cross-check for Check 5)
- **Root-cause verdict** banner that splits "platform path" vs "environment configuration".
- **Static single-file HTML dashboard** (`report.html`) — color-coded cards, verdict banner,
  topology table, and a copy-paste support-case block. No external CDN/JS (closed-network safe).
- **Machine-readable `report.json`** with every check, raw evidence, and timestamps.
- **`--mock` mode** — run end-to-end with built-in placeholder data, no Azure or network access.
- **`--checks` selector** to run a subset (e.g. `--checks 1,2,4`).
- **Config-driven, zero hardcoding** — `config.sample.json` with placeholder-only values;
  `config.json` is gitignored so your values are never committed.
- **Bilingual docs** — full English + Korean `README`, `docs/USAGE`, plus `docs/PLATFORM_PATTERN.md`,
  `docs/SUPPORT_CASE_GUIDE.md`, and `docs/REFERENCES.md`.
- **Optional `examples/sdk_ab_test.py`** — SDK vs Playground A/B helper (guide, not auto-verdict).

### Known limitations
- **Check 5 / Check 6 log auto-query depends on your permissions.** When the Log Analytics
  workspace is not provided or not readable, both checks fall back to **manual input** with the
  exact question to answer — they never crash.
- **The managed Data Proxy cannot be observed directly.** The verdict is inferred from surrounding
  signals (VM baseline, backend reachability, resolver/APIM logs), not from inside the Data Proxy.
- **SDK vs Playground A/B is a guide**, not an automatic determination — comparison is a human call.
- **Preview surfaces evolve.** The Foundry connections control-plane shape and exact sample template
  numbering are preview; unverifiable items are reported as "needs verification".

### References
- Verification baseline: **2026-06**. See [`docs/REFERENCES.md`](docs/REFERENCES.md) for official
  Microsoft Learn pages and the foundry-samples network-secured Standard Agent templates.

**(한국어)** 최초 공개 릴리스. Foundry Agent BYO VNet 프라이빗 네트워크 경로용 **읽기 전용 6단계 진단**,
**Template 16 토폴로지 diff**, **단일 파일 HTML 대시보드**, **JSON 출력**, **mock 모드**, 영/한 문서 제공.
알려진 한계: Check 5/6 로그 자동 조회는 사용자 권한에 의존(없으면 수동 fallback), Data Proxy 내부 직접 관측 불가
(주변 신호 기반 추론), SDK/Playground A/B는 가이드 제공. 검증 기준일 2026-06.

[1.0.1]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v1.0.1
[1.0.0]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v1.0.0
[0.3.0]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v0.3.0
[0.2.0]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v0.2.0
[0.1.0]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v0.1.0
