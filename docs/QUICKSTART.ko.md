# 단계별 빠른 시작 — 로컬에서 직접 실행 (한국어)

처음 사용하는 분을 위한 **따라 하기** 가이드입니다. 터미널에 한 줄씩 복붙하세요.
요약본은 [README의 빠른 시작](../README.ko.md#-빠른-시작-quickstart), English: [`QUICKSTART.md`](QUICKSTART.md).

---

## 0단계 — 폴더로 이동 (항상 먼저)

```bash
cd /path/to/foundry-agent-network-diagnostic
```

전제 조건: **Python 3.10 이상**만 있으면 됩니다(`python3 --version`). 진단 엔진은 표준 라이브러리만
사용하므로 `pip install`이 필요 없습니다.

---

## 1단계 — mock 데모로 "이게 뭐 하는 도구인지" 보기 ⭐가장 쉬움 (Azure 불필요)

```bash
python3 src/diagnose.py --config config.sample.json --mock
```

→ 현재 폴더에 `report.html`, `report.json`이 생성됩니다. 리포트를 열어보세요:

```bash
open report.html        # macOS
# xdg-open report.html  # Linux
# start report.html     # Windows
```

**보이는 화면:** 상단 **root-cause 판정 배너** + **6개 색깔 카드**(초록 PASS / 노랑 WARN / 빨강 FAIL /
회색 SKIPPED) + **Check 4 토폴로지 표** + 하단 **복붙용 support-case 블록**. 여기서 도구 감을 잡으면
됩니다. 이 데모는 Azure도 네트워크도 전혀 사용하지 않습니다.

---

## 2단계 — 테스트가 잘 도는지 확인 (선택)

```bash
python3 -m unittest discover -s tests
```

→ 마지막에 `OK` 와 `Ran 30 tests` 가 나오면 정상입니다.

여기까지가 **Azure 없이** 할 수 있는 부분입니다. 실제 환경 진단은 아래 두 방법 중 **하나만** 고르세요.

---

## 3단계 (방법 A) — 이미 배포된 환경 점검 ⭐안전, 아무것도 만들지 않음

먼저 Azure 로그인이 되어 있어야 합니다(`az login`). 그다음:

```bash
bash deploy/verify-existing.sh
```

→ 엔드포인트·네트워크 설정을 물어보고 → `config.json` 생성 → 진단 → `report.html`.
리소스를 **생성하지 않습니다**.

직접 config를 채우는 방법도 있습니다:

```bash
cp config.sample.json config.json
# config.json 을 열어 backend_fqdn, expected_private_vip 등 실제 값으로 채우기
python3 src/diagnose.py --config config.json
open report.html
```

`config.json`은 `.gitignore`에 포함되어 커밋되지 않습니다.

---

## 3단계 (방법 B) — 재현 랩을 직접 배포해서 보기 (본인 구독에 작은 리소스 생성)

비용 0 미리보기부터(아무것도 만들지 않음):

```bash
bash deploy/deploy.sh --what-if --location koreacentral
```

실제 배포 → 진단 → 리포트:

```bash
bash deploy/deploy.sh --scenario lab --location koreacentral --yes
```

다 보고 나면 정리(삭제):

```bash
bash deploy/destroy.sh
```

> **팁:** 진단 대상 Foundry 환경과 **같은 리전**으로 맞추면 재현이 더 충실합니다(예: `koreacentral`).
> 전체 옵션은 [`docs/DEPLOYMENT.ko.md`](DEPLOYMENT.ko.md)를 참고하세요.

### 격리된 별도 프로필(테넌트)로 돌리기

기본 `az login`을 건드리지 않고 다른 테넌트/구독으로 안전하게 배포하려면 `--env-file`을 사용합니다:

```bash
cp .env.sample .env.external.local
# .env.external.local 편집: EXTERNAL_AZURE_CONFIG_DIR, 테넌트/구독, LOCATION 등
bash deploy/deploy.sh --env-file .env.external.local --what-if
```

`.env*.local` 파일도 `.gitignore`에 포함되어 커밋되지 않습니다.

---

## 추천 순서

1. **1단계(mock)** 만 먼저 — 제일 쉽고 안전합니다.
2. 화면이 마음에 들면 → **방법 A**(안전, 생성 없음) 또는 **방법 B**(재현 랩) 중 택1.

## 막혔을 때

- `python3: command not found` → Python 3.10+ 설치 후 다시 시도.
- `bash deploy/...`에서 권한/로그인 오류 → `az login` 상태와 구독 선택을 확인.
- 그 외 화면에 뜬 메시지를 그대로 캡처해 두면 원인 파악이 빠릅니다.

전체 사용 설명은 [`docs/USAGE.ko.md`](USAGE.ko.md), 두 진단 방법의 상세는 [`docs/DEPLOYMENT.ko.md`](DEPLOYMENT.ko.md)를 참고하세요.
