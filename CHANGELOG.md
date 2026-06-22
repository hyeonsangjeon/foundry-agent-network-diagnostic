# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> 한국어 요약은 각 버전 하단의 **(한국어)** 블록을 참고하세요.

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
- **Root-cause verdict** banner that splits "platform path" vs "customer configuration".
- **Static single-file HTML dashboard** (`report.html`) — color-coded cards, verdict banner,
  topology table, and a copy-paste support-case block. No external CDN/JS (closed-network safe).
- **Machine-readable `report.json`** with every check, raw evidence, and timestamps.
- **`--mock` mode** — run end-to-end with built-in placeholder data, no Azure or network access.
- **`--checks` selector** to run a subset (e.g. `--checks 1,2,4`).
- **Config-driven, zero hardcoding** — `config.sample.json` with placeholder-only values;
  `config.json` is gitignored so customer values are never committed.
- **Bilingual docs** — full English + Korean `README`, `docs/USAGE`, plus `docs/PLATFORM_PATTERN.md`,
  `docs/SUPPORT_CASE_GUIDE.md`, and `docs/REFERENCES.md`.
- **Optional `examples/sdk_ab_test.py`** — SDK vs Playground A/B helper (guide, not auto-verdict).

### Known limitations
- **Check 5 / Check 6 log auto-query depends on customer permissions.** When the Log Analytics
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
알려진 한계: Check 5/6 로그 자동 조회는 고객 권한에 의존(없으면 수동 fallback), Data Proxy 내부 직접 관측 불가
(주변 신호 기반 추론), SDK/Playground A/B는 가이드 제공. 검증 기준일 2026-06.

[0.1.0]: https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic/releases/tag/v0.1.0
