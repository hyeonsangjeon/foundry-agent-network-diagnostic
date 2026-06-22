# 사용 가이드 (한국어)

설치 및 사용 전체 안내입니다. 요약본은 [README의 빠른 시작](../README.ko.md#-빠른-시작-quickstart)을
참고하세요. English: [`USAGE.md`](USAGE.md).

---

## 1. 사전 요구사항

| 요구사항 | 이유 |
| --- | --- |
| **VNet 내부**의 Linux jump-box VM | Check 1이 "VM baseline"을 잡고 `/etc/resolv.conf`를 읽음 |
| Python **3.10+** | 진단 본체는 표준 라이브러리만 사용 |
| 로그인된 Azure CLI(`az`) | Check 3/5/6이 read-only로 Azure 조회 |
| `dig` 또는 `nslookup` (선택) | Check 1에 second-opinion DNS 응답 제공 |
| 리소스/로그 읽기 권한 | 없으면 체크는 SKIPPED로 우아하게 강등 |

진단 본체는 **외부 패키지가 필요 없습니다.** `requirements.txt`에는 SDK A/B 헬퍼
(`examples/sdk_ab_test.py`)용 선택 패키지만 적혀 있습니다.

## 2. 설치

```bash
git clone https://github.com/hyeonsangjeon/foundry-agent-network-diagnostic.git
cd foundry-agent-network-diagnostic
pip install -r requirements.txt   # 본체에는 영향 없음, 필수 설치 없음
```

## 3. 인증 (read-only)

```bash
az login
# 선택: 올바른 구독 지정
az account set --subscription "<your-subscription-guid>"
```

이 도구는 절대 쓰기를 하지 않습니다 — `show`/`list`/`query` 류 명령만 실행합니다.

## 4. 설정

```bash
cp config.sample.json config.json
```

`config.json`을 편집합니다. `config.json`은 **gitignore** 처리되어 값이 커밋되지 않습니다.

### 필드 레퍼런스

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `subscription_id` | ✅ | 구독 GUID |
| `resource_group` | ✅ | Foundry account의 리소스 그룹 |
| `region` | ✅ | Azure 리전 (예: `eastus`) |
| `foundry_account` | ✅ | Foundry account/리소스 이름 |
| `foundry_project` | ✅ | Foundry project 이름 |
| `backend_fqdn` | ✅ | resolve에 실패하는 backend hostname, 예: `llm.<your-apim>.<your-domain>` |
| `expected_private_vip` | ✅ | 해당 FQDN이 resolve돼야 하는 private IP (예: `10.x.x.x`) |
| `agent_subnet_id` | ⬜ | agent(managed) subnet의 전체 resource ID — delegation 체크 활성화 |
| `pe_subnet_id` | ⬜ | private-endpoint subnet의 전체 resource ID |
| `apim_resource_id` | ⬜ | APIM resource ID (support 요약에 사용) |
| `apim_mode` | ⬜ | `internal` \| `external` \| `PE` \| `unknown` |
| `dns_resolver_log` | ⬜ | `{ "workspace_id": "<guid>" }` — 생략 시 Check 5 manual fallback |
| `apim_gateway_log` | ⬜ | `{ "workspace_id": "<guid>" }` — 생략 시 Check 6 manual fallback |

`_`로 시작하는 키(예: 샘플의 `_help` 블록)는 문서용이며 도구가 무시합니다.

필수 필드가 비었거나 placeholder인 경우 **친절한 검증 오류**(어느 필드를 고쳐야 하는지 명시)와 함께 종료
코드 `2`를 반환합니다.

## 5. 실행

```bash
# 전체 실행
python src/diagnose.py --config config.json

# Azure/네트워크 없이 데모 (내장 mock 시나리오)
python src/diagnose.py --config config.sample.json --mock

# 일부 체크만
python src/diagnose.py --config config.json --checks 1,2,4

# 출력 디렉터리 지정 및 콘솔 색상 비활성화
python src/diagnose.py --config config.json --out-dir ./out --no-color
```

| 플래그 | 기본값 | 의미 |
| --- | --- | --- |
| `--config` | `config.json` | config 파일 경로 |
| `--mock` | off | 내장 placeholder 데이터 사용; Azure/네트워크 호출 없음 |
| `--checks` | 전체 | 쉼표로 구분한 부분집합, 예: `1,2,4` |
| `--out-dir` | `.` | `report.html` / `report.json` 출력 위치 |
| `--no-color` | off | 단색 콘솔 출력 (CI/로그에 적합) |

## 6. 출력 읽기

세 가지 산출물이 생성됩니다:

- **`report.html`** — 대시보드. 아무 브라우저에서나 열리며 인터넷이 필요 없습니다. 상단 배너 = root-cause
  판정, 카드 = 6개 체크, 하단 = 복붙용 support-case 블록.
- **`report.json`** — 머신 리더블: `verdict`, `summary_counts`, 그리고 raw `evidence`와 체크별
  `timestamp`가 담긴 `checks[]`.
- **콘솔 요약** — 동일한 판정 + 상태 표. CI나 터미널 세션에 유용.

### 판정 (3-way)

Check 5가 판정을 주도합니다:

| Check 5 evidence `verdict` | 방향 | 의미 |
| --- | --- | --- |
| `no_query` | 플랫폼 | FQDN 질의가 resolver에 도착하지 않음 → managed 경로가 이 VNet DNS path를 안 쓰는 것으로 보임 (확인 필요) |
| `nxdomain_or_timeout` | 구성 | 질의는 도착했으나 실패 → DNS zone-link / forwarding 문제 |
| `answered_but_failed` | 플랫폼 | DNS는 정상 응답했는데 호출 실패 → 플랫폼 cache / 다른 resolver path |

Check 6 교차검증: 같은 시간대에 **APIM에 request가 도착하지 않았다면** 문제는 **backend 도달 전** —
DNS 단계와 일치합니다.

## 7. Manual fallback (Check 5 & 6)

Log Analytics workspace를 제공하지 않으면(또는 도구가 읽지 못하면) Check 5/6은 수동으로 답할 정확한
질문을 출력합니다:

- **Check 5:** DNS resolver / Azure DNS Private Resolver query log에서 agent 호출 UTC 시각 부근의
  backend FQDN을 필터링하세요. 질의가 도착했나요? 도착했다면 NXDOMAIN/timeout인가요, 정상 A 레코드인가요?
- **Check 6:** APIM gateway 로그에서 그 시간대에 **어떤** request라도 도착했나요? 없다면 문제는 APIM 도달
  전입니다.

답을 기록하거나(또는 workspace ID를 `config.json`에 추가) 다시 실행하세요.

## 8. SDK vs Playground A/B (선택)

`examples/sdk_ab_test.py`는 같은 gateway connection을 Agent SDK에서 호출해 Playground UI와 비교하게
해줍니다. **임시 agent를 생성하는 유일한 스크립트**이며(이후 삭제), 의도적으로 `src/` 밖에 두었고 read-only
진단의 일부가 아닙니다.

```bash
pip install azure-identity azure-ai-projects
python examples/sdk_ab_test.py \
  --project-endpoint https://<your-foundry>.services.ai.azure.com/api/projects/<your-project> \
  --model <your-chat-deployment>
```

- SDK 성공 + Playground 실패 → UI 지원 범위 이슈 가능성.
- 둘 다 실패 → 네트워크 경로 문제와 일치; `src/diagnose.py`에 의존하세요.

## 9. 문제 해결

| 증상 | 원인 / 해결 |
| --- | --- |
| `config error ... placeholder value` | 필수 필드에 아직 `<...>`가 있음 — 교체 |
| Check 3 connection lookup "needs verification" | preview connections API를 읽지 못함; Foundry 포털에서 category 확인 |
| Check 5/6 SKIPPED | `*_log` workspace 미제공 — manual fallback 사용 |
| `'az' not found on PATH` | Azure CLI 설치; 그동안 해당 체크는 SKIP |
| 리포트가 오프라인에서 안 열림 | 단일 파일이므로 열려야 정상 — 파일 권한/경로 확인 |

[`SUPPORT_CASE_GUIDE.md`](SUPPORT_CASE_GUIDE.md), [`REFERENCES.md`](REFERENCES.md)도 함께 보세요.
