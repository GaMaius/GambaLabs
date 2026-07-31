# 📋 [최종 정리본 & 구현 계획서] 감바랩스 오피스 LLM (PPT/Excel) 자동화 파이프라인

## 1. 개요 및 배경 맥락 (Context Summary)

### 💡 기획 배경 및 요구사항 분석
* **주제**: PowerPoint / Excel LLM 활용 시나리오 설계 및 사내 업무 자동화 파이프라인 구축
* **사내 활용 상황**:
  * **PPT**: 기술 소개, R&D 제안서, 연구 과제 수주용 발표 (기술 필요성, 개발 내용, 일정, 기대효과 등)
  * **Excel**: 문서에 흩어진 연구비 수치/실험 결과 정리, 일정 내역 표/대시보드 실시간 업데이트
* **핵심 제약 및 원칙 (신뢰성 중심 개발)**:
  * 인턴이 완전히 백지 상태에서 처음부터 끝까지 자체 개발한 모듈은 enterprise 신뢰도를 얻기 어려움.
  * **검증된 기술/오픈소스/Custom Skill/API** (`python-pptx`, `openpyxl`, `Polaris AI DataInsight`, GPT Custom Skill `pptx-guide`)를 엮은 **안정적인 인터페이스 및 오케스트레이션 에이전트**로 구현.
  * **사내 테마 일관성**: 감바랩스 전용 디자인 규격(딥네이비/브랜드네이비, HY견고딕/맑은고딕, 상단 헤더 밴드 등)을 상시 보장.

---

## 2. 세부 시나리오 최종 정의

### 📌 [시나리오 1] PowerPoint: Custom Skill (`pptx-guide`) 기반 R&D 제안서 & 발표 덱 자동 생성
* **입력**: 비정형 연구노트, 과제 공고문, HWP/PDF/TXT 기술 문서 (예: `gambalabs_tech_presentation.md`)
* **파이프라인**:
  1. **구조화 파싱**: Polaris AI DataInsight API를 통해 비정형 문서에서 텍스트 및 표 데이터를 JSON으로 추출.
  2. **오케스트레이션 & 테마 매핑**: `pptx-guide` 테마 규격(`gambalabs_theme_navy_white.md`)을 읽어 감바랩스 브랜드 컬러(`#123979`, `#0038A3`), 폰트, 레이아웃 적용.
  3. **PPTX 렌더링**: `python-pptx` 엔진으로 표준 슬라이드 덱 생성 (표지 -> 요약 -> 기술개요 -> 핵심성능/표 -> 솔루션 -> 마감).
* **출력**: 완제품 `.pptx` 파일 생성 및 저장.

---

### 📌 [시나리오 2] Excel: 연구비 집행 & 프로젝트 일정 실시간 대시보드 업데이트
* **입력**: MS Teams / 사용자 자연어 수정 요청 (예: `sample_update_requests.txt` - "종료일 연장, 진행상태 지연 변경", "서버 임차비 2,000,000원 추가 합산")
* **파이프라인**:
  1. **LLM 좌표 추론**: GPT-4o Structured Output을 활용해 사용자 자연어에서 (시트명, 셀 좌표, 변경 값) JSON 추출.
  2. **수식/차트 보존 셀 업데이트**: `openpyxl` (`data_only=False`)을 사용하여 엑셀 내 기존 `SUM`/`AVERAGE` 수식, 조건부 서식, 대시보드 차트를 100% 보존하면서 해당 셀만 안전하게 수정.
* **출력**: 수식 손상 없는 업데이트된 `.xlsx` 대시보드 저장.

---

### 📌 [추가 제안 시나리오] 사내 통합 오피스 에이전트 (Teams/CLI 인터페이스)
* **내용**: 
  * CLI 통합 메인 엔트리포인트 (`main.py`) 제공으로 PPT 생성 / Excel 업데이트 명령 통합 실행.
  * 추후 MS Teams Bot / Slack Bot 웹훅 연동이 용이하도록 모듈화 구조 설계.

---

## 3. 구현 기술 스택 및 라이브러리

| 영역 | 활용 도구 / 라이브러리 | 역할 |
| :--- | :--- | :--- |
| **AI Engine** | OpenAI GPT-4o / Pydantic | 자연어 요청 파싱, JSON 구조화, 셀 위치 추론 |
| **Document Parser** | Polaris AI DataInsight / Custom Mock | HWP, PDF 등 비정형 문서 구조화 파싱 |
| **PPT Engine** | `python-pptx`, Custom Theme Config | 감바랩스 브랜드 테마 기반 PPTX 자동화 생성 |
| **Excel Engine** | `openpyxl` | 수식/차트 보존 셀 단위 데이터 업데이트 |
| **Orchestrator** | Python 3.10+ CLI (`main.py`) | 전체 파이프라인 통합 실행 및 CLI 테스트 |

---

## 4. 상세 구현 계획 (Proposed Changes)

```text
gambalabs-office-automation/
├── .env.example                 # 환경변수 템플릿 (OPENAI_API_KEY 등)
├── requirements.txt             # 파이썬 의존성 목록
├── config/
│   └── gambalabs_theme.json     # 감바랩스 PPT 테마 색상/폰트/레이아웃 설정
├── src/
│   ├── parsers/
│   │   └── polaris_parser.py    # 비정형 문서 파서
│   ├── ppt/
│   │   └── ppt_generator.py     # python-pptx 기반 PPT 생성기
│   ├── excel/
│   │   ├── llm_extractor.py     # 자연어 -> 셀 수정 JSON 추출기
│   │   └── excel_updater.py     # openpyxl 수식/차트 보존 수정기
│   └── utils/
│       └── logger.py            # 실행 로그 및 알림 유틸
├── tests/
│   ├── test_scenario_1.py       # PPT 생성 파이프라인 통합 테스트
│   └── test_scenario_2.py       # Excel 업데이트 파이프라인 통합 테스트
└── main.py                      # 통합 실행 Entry point
```

### [NEW] `requirements.txt`
* `openai>=1.0.0`, `openpyxl>=3.1.0`, `python-pptx>=0.6.21`, `pydantic>=2.0.0`, `python-dotenv>=1.0.0`

### [NEW] `config/gambalabs_theme.json`
* `gambalabs_theme_navy_white.md` 규격 정의:
  * 히어로 네이비 (`123979`), 브랜드 네이비 (`0038A3`), 본문 바탕 (`ECECEC`)
  * 폰트: 제목 (`HY견고딕` / `Arial Bold`), 본문 (`맑은 고딕` / `Arial`)

### [NEW] `src/parsers/polaris_parser.py`
* 비정형 텍스트/PDF 마크다운 문서를 읽어 제목, 섹션, 테이블 데이터를 정형화된 JSON dict 구조로 리턴하는 파서 클래스 (`PolarisParser`).

### [NEW] `src/ppt/ppt_generator.py`
* JSON 데이터 및 `gambalabs_theme.json` 설정을 읽어 `python-pptx`로 표지, 요약, 본문(카드/테이블/큰숫자), 마무리 슬라이드를 생성하는 클래스 (`PPTGenerator`).

### [NEW] `src/excel/llm_extractor.py`
* OpenAI GPT API 및 Pydantic Structured Output(`TargetCellUpdate`)을 사용하여 자연어 요청 문장에서 target sheet, cell address, new value 추출 (`LLMExtractor`).

### [NEW] `src/excel/excel_updater.py`
* `openpyxl.load_workbook(filename, data_only=False)`를 사용하여 대상 셀 데이터 수정 및 수식/차트 보존 저장 클래스 (`ExcelUpdater`).

### [NEW] `main.py` & `tests/`
* `sample_update_requests.txt`, `sample_gambalabs_dashboard.xlsx`, `gambalabs_tech_presentation.md` 데이터를 이용해 두 시나리오를 통합 동작/검증하는 CLI 엔트리포인트 및 테스트 코드.

---

## 5. 검증 계획 (Verification Plan)

### Automated Tests
1. **PPT 파이프라인 검증 (`tests/test_scenario_1.py`)**:
   * `gambalabs_tech_presentation.md` 파싱 후 PPTX 생성 실행.
   * 생성된 `.pptx` 파일의 존재 여부, 슬라이드 수(10개), 테마 컬러 적용 및 텍스트 데이터 매핑 검증.
2. **Excel 파이프라인 검증 (`tests/test_scenario_2.py`)**:
   * `sample_update_requests.txt` 자연어 요청 파싱.
   * `sample_gambalabs_dashboard.xlsx`에 셀 수정 적용 후 `SUM` 수식 및 차트 객체 보존 여부 검증.

### Manual Verification
* 생성된 `.pptx` 및 `.xlsx` 파일 직접 점검 (레이아웃, 색상, 수식 동작 상태).

---

## 6. 사용자 확인 및 질문 사항 (User Review Required)

> [!IMPORTANT]
> **검증된 툴 엮기(Orchestration) 방안 채택**
> 본 계획은 인턴 독자 개발 방식 대신, **`python-pptx` + `openpyxl` + `OpenAI API` + 감바랩스 테마 규격**을 하나로 결합한 파이프라인 엔진을 구축하는 방식으로 설계되었습니다.

1. 위 구현 계획서 내용에 대해 승인해 주시면, 바로 코드 구조 설계 및 구현(Phase 1~4)을 진행하겠습니다.
