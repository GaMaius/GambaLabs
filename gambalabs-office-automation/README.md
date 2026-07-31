# 감바랩스 오피스 LLM 자동화

흩어진 수작업(브랜드 PPT 제작 · 대시보드 수식 수정)을 **명령 한 줄**로 묶는 사내 자동화 도구.
검증된 오픈소스·에이전트를 엮은 오케스트레이션이라 인턴 자체개발 대비 신뢰도가 높고, **사람이 최종 검토·전송**하는 human-in-the-loop 구조다.

## 구조

```
[문서]        → PPT 스킬 패키지(ppt-skill/, Codex 에이전트) → 브랜드 .pptx
[Teams 요청문] → Excel 엔진(src/excel, openpyxl)           → 수식·차트 보존 .xlsx
                         ▲
             모니터 레이어(src/monitor): 감지 → "실행할까요?" 확인 → 엔진 실행
```

| 시나리오 | 방식 | 엔진 | LLM |
|---|---|---|---|
| **PPT 생성** | 에이전트+스킬(내용 적응형, 브랜드 고정) | `pptxgenjs` (`ppt-skill/`) | 외부 GPT/Claude (제안서=외부향) |
| **Excel 업데이트** | 결정적 코드(수식·차트 보존) | `openpyxl` (`src/excel/`) | OpenAI 호환(스왑) |
| **모니터(오케스트레이션)** | 감지→확인→실행 | `src/monitor/watcher.py` | — |

## 설치

```bash
pip install -r requirements.txt          # Python 엔진
npm install                              # PPT 렌더러(pptxgenjs, resvg)
cp .env.example .env                     # 키·엔드포인트 설정
```

## 실행

```bash
# 1) Excel: 자연어 요청으로 대시보드 업데이트 (수식·차트 보존)
python main.py excel planing/sample_update_requests.txt

# 2) 모니터: 감시 폴더(inbox/)에 요청이 들어오면 감지→확인→실행
python main.py monitor --once            # 1회 처리 (상주는 --once 없이)

# 3) PPT: 문서를 스킬(Codex)로 제작 — 안내 출력
python main.py ppt gambalabs_tech_presentation.md
#   → ppt-skill/ 폴더를 Codex에서 열고: "<문서> 이 문서로 감바랩스 발표자료 만들어줘"
```

테스트: `python tests/test_scenario_2.py` (수식·차트 보존 검증)

## LLM 백엔드 스왑 (데이터 주권)

`.env`의 `OPENAI_BASE_URL`만 바꾸면 코드 변경 없이 엔진 전환:
- 미설정 = **OpenAI**(데모)
- `http://localhost:11434/v1` = **로컬 Ollama**
- `http://<사내서버>:11434/v1` = **사내 LLM 서버**(대외비 문서용, 외부 전송 0)

렌더링(PPT)·셀 수정(Excel)은 **항상 결정적 코드**라 어느 백엔드든 브랜드·수식 보장은 동일.

## 발표자료 설계 방침 — 로컬 모델 vs 강한 모델 분리 (중요)

**모델 급에 따라 '설계 강도'를 다르게 쓴다.** 약한 로컬 모델엔 가드레일을, 강한 클라우드 모델엔 자유를.
같은 제약을 모든 모델에 씌우면 강한 모델의 품질을 오히려 깎기 때문이다(**과제약의 역설**).

| 방침 | 대상 | 동작 |
|---|---|---|
| `template` (가드레일) | 로컬 3b/7b 등 약한 모델 | 프롬프트에 슬라이드 1:1 매핑·유형 강제 규칙을 상세히. 후처리에서 **지시문구 제거·카드 자동변환·빈 슬라이드 정리** 등 적극 개입해 약한 모델의 실수를 코드가 보정. |
| `freeform` (위임) | 회사 GPT-4급/Claude 등 강한 모델 | 프롬프트는 목표·스키마만 주고 **설계는 모델에 위임**(잔소리 최소). 후처리는 형식 검증·빈 값 제거 등 **안전 수준만** — 모델의 레이아웃 선택을 존중. |

**왜 분리하나:** 강한 모델은 "큰 주제는 크게, 여백 있으면 가운데 배치" 같은 판단을 스스로 더 잘한다.
여기에 로컬용 가드레일을 그대로 씌우면 낭비이자 품질 저하다. 그래서 템플릿 규칙을 무한히 정교화하는
대신 **방침 자체를 코드로 분리**(`app/ppt/design_policy.py`)해, GPT 연결 시 다른 방침이 자동 적용되게 했다.

**전환:**
- **자동(기본)**: 엔드포인트·모델명으로 판단 — 비(非)로컬 + `gpt-*`/`claude-*` 등 → `freeform`, 아니면 `template`.
- **수동**: `.env`에 `PPT_DESIGN_MODE=auto|template|freeform`.
- **참조 위치**: `design_policy.py`(감지·선택) → `pptx_import.py`(PPT 입력)·`ppt_engine.py`(풀 자동)가 이 방침으로 프롬프트 강도와 후처리 개입도를 바꾼다.

**두 방침 모두 렌더는 결정적**(`render_deck.js`)이라 자유도만 오를 뿐 코드 실행 위험은 없다.

**로드맵**: `freeform`을 더 밀어 "강한 모델이 `pptxgenjs` 코드를 직접 생성 → `validate` 후 렌더"까지
확장하면 `클로드 버전`급 자유설계가 가능. 현재는 안전을 위해 *플랜 → 결정적 렌더*를 유지한다.

## vs Microsoft 365 Copilot

| | Copilot | 이 도구 |
|---|---|---|
| PPT 브랜드 | 제네릭 | **감바랩스 테마 강제** |
| Excel 수식 | 깨질 수 있음 | **수식·차트 100% 보존 + 수식 셀 보호 가드** |
| 데이터 | MS 클라우드 전송 | **온프레/사내서버 선택(데이터 주권)** |
| 비용 | 좌석당 라이선스 | 검증된 오픈소스 조합 |

## 배포 로드맵

- **지금(데모)**: 온디맨드 로컬 실행 + 감시폴더 트리거.
- **다음**: 모니터 트리거를 MS Teams/Outlook(`teams-sdk`·Graph)로 교체(IT 승인 필요). 엔진·확인 로직은 그대로.
- **전사 보급**: 사내 LLM 서버 1대 + 경량 클라이언트 배포(각 PC에 모델 설치 불필요).
