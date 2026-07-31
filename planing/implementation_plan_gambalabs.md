# 🛠️ [구현 계획서] Antigravity / Claude Code 기반 오피스 LLM 자동화 파이프라인

**작성자:** ⭐가람⭐  
**대상 프로젝트:** 감바랩스 오피스 LLM 자동화 (PPT / Excel)  
**개발 환경:** Antigravity / Claude Code (Agentic IDE), Python 3.10+  

---

## 📂 1. 전체 프로젝트 디렉토리 구조

```text
gambalabs-office-automation/
├── .env                         # API 키 및 설정 정보
├── requirements.txt             # 파이썬 의존성 패키지
├── config/
│   └── pptx_guide_skill.json    # pptx-guide 스킬 테마 및 레이아웃 규격
├── src/
│   ├── parsers/
│   │   └── polaris_parser.py    # Polaris AI DataInsight HWP/PDF 파서 Module
│   ├── ppt/
│   │   └── ppt_generator.py     # GPT-4o + pptx-guide 기반 PPTX 생성 엔진
│   ├── excel/
│   │   ├── llm_extractor.py     # 자연어 요청 -> Cell JSON 추출기
│   │   └── excel_updater.py     # openpyxl 수식/차트 보존 셀 수정기
│   └── utils/
│       └── delivery.py          # OneDrive/Teams 파일 전달 모듈
├── tests/
│   ├── test_scenario_1.py       # 시나리오 1 파이프라인 통합 테스트
│   └── test_scenario_2.py       # 시나리오 2 파이프라인 통합 테스트
└── main.py                      # 전체 통합 실행 CLI Entry Point
```

---

## 📌 2. [시나리오 1] PowerPoint 자동 생성 파이프라인 구현 계획

비정형 문서(HWP/PDF)를 읽어 감바랩스 표준 브랜드 테마가 적용된 `.pptx` 파일로 변환하는 모듈 개발 단계입니다.

```
[입력 문서 (PDF/HWP)] ──► [1. polaris_parser.py] ──► [JSON] ──► [2. ppt_generator.py (GPT + pptx-guide)] ──► [완성 .pptx]
```

### Step 1.1: Polaris AI 문서 파서 구현 (`src/parsers/polaris_parser.py`)
* **목표**: Polaris AI DataInsight API를 호출하여 HWP/PDF 파일에서 구조화된 텍스트와 표(Table) 데이터를 추출.
* **구현 세부사항**:
  * Polaris API REST Endpoint 연동 (`https://datainsight.polarisoffice.com/_api/reference`).
  * 비정형 문서를 파싱하여 `title`, `sections`, `tables`, `metadata`가 담긴 파이썬 Dictionary/JSON 객체로 반환.
* **에이전트 구현 명령**:
  > "Polaris AI DataInsight API를 호출하는 `PolarisParser` 클래스를 구현해줘. HWP/PDF 파일 경로를 받아 표 데이터와 섹션 텍스트가 분리된 JSON으로 변환하는 `parse_document()` 메서드를 작성해줘."

### Step 1.2: GPT-4o + `pptx-guide` 생성 엔진 구현 (`src/ppt/ppt_generator.py`)
* **목표**: `pptx-guide` 커스텀 스킬 규격과 Polaris AI가 파싱한 JSON 데이터를 받아 `.pptx` 슬라이드 생성.
* **구현 세부사항**:
  * `config/pptx_guide_skill.json`에서 감바랩스 표준 브랜드 컬러(Dark Navy `#1B365D`, Vivid Blue `#3182CE`) 및 폰트 규칙 로드.
  * OpenAI GPT-4o Code Interpreter / `python-pptx` 연동 모듈 작성.
  * 슬라이드 레이아웃 매핑:
    * Slide 1: 표지 슬라이드 (Navy 배경 + 타이틀)
    * Slide 2: 기술 개발 필요성 및 배경 (텍스트 카드)
    * Slide 3: 핵심 개발 내용 (3-Column 카드 구조)
    * Slide 4: 연구비 예산 및 추진 일정 (표/Table 및 기대효과)
* **에이전트 구현 명령**:
  > "`pptx_guide_skill.json`의 색상/폰트 규칙을 적용하여 `python-pptx` 기반으로 슬라이드를 동적 생성하는 `PPTGenerator` 클래스를 작성해줘. Polaris JSON 데이터를 받아 4장 분량의 표준 제안서 PPTX 파일로 저장하는 메서드를 만들어줘."

---

## 📌 3. [시나리오 2] Excel 대시보드 실시간 업데이트 파이프라인 구현 계획

자연어 요청을 처리하여 기존 엑셀의 계산 수식, 조건부 서식, 차트를 100% 보존하면서 특정 셀만 안전하게 수정하는 모듈 개발 단계입니다.

```
[MS Teams 자연어 요청] ──► [1. llm_extractor.py (GPT-4o)] ──► [Cell 좌표 JSON] ──► [2. excel_updater.py (openpyxl)] ──► [업데이트된 .xlsx]
```

### Step 2.1: 자연어 요청 셀 좌표 추출기 구현 (`src/excel/llm_extractor.py`)
* **목표**: 임직원의 자연어 텍스트(예: "일정 10일 연장", "서버 비용 200만원 추가")를 분석하여 변경 대상 시트명, 셀 좌표, 수정 값을 JSON으로 정형화.
* **구현 세부사항**:
  * Pydantic 기반 Structured Output 사용 (`TargetCellUpdate` 스키마 정의).
  * 엑셀 파일의 구조 메타데이터(시트 이름 목록, 헤더 컬럼명)를 GPT-4o에 프롬프트로 전달하여 정확한 Cell 위치(예: `프로젝트_일정!D2`, `연구비_집행내역!C3`) 추론.
* **에이전트 구현 명령**:
  > "OpenAI Structured Outputs를 사용하여 사용자 수정 요청 문장을 분석하고 `sheet_name`, `cell_address`, `new_value` 리스트를 반환하는 `LLMExtractor` 클래스를 작성해줘."

### Step 2.2: 수식 보존 Excel 셀 업데이트 엔진 구현 (`src/excel/excel_updater.py`)
* **목표**: `openpyxl`을 사용하여 기존 엑셀 대시보드의 `SUM`, `AVERAGE` 수식과 차트를 손상시키지 않고 대상 셀만 업데이트.
* **구현 세부사항**:
  * `openpyxl.load_workbook(filename, data_only=False)`로 수식 원본 보존 로드.
  * JSON 추출 결과를 바탕으로 해당 시트/셀에 데이터 주입.
  * 파일 저장 후 업데이트된 변경 이력 로그 반환.
* **에이전트 구현 명령**:
  > "`openpyxl`을 사용해 기존 엑셀 파일의 수식과 차트를 손상시키지 않는 `ExcelUpdater` 클래스를 구현해줘. Extractor가 넘겨준 JSON 배열을 받아 개별 셀 값만 교체하고 저장하는 `apply_updates()` 메서드를 작성해줘."

---

## 🚀 4. Claude Code / Antigravity 실행 가이드 (단계별 프롬프트)

### 1단계: 환경 및 의존성 설정
```bash
Create a Python 3.10+ virtual environment and write requirements.txt containing:
openai>=1.0.0
openpyxl>=3.1.0
python-pptx>=0.6.21
pydantic>=2.0.0
python-dotenv>=1.0.0
requests>=2.31.0
```

### 2단계: 시나리오 1 (PPT 생성) 빌드
```bash
Implement `src/parsers/polaris_parser.py` and `src/ppt/ppt_generator.py`.
Use `pptx_guide_skill_sample.md` rules as layout configuration in `config/pptx_guide_skill.json`.
Then write `tests/test_scenario_1.py` using `sample_input_research_note.pdf` to test full PPT generation.
```

### 3단계: 시나리오 2 (Excel 수정) 빌드
```bash
Implement `src/excel/llm_extractor.py` and `src/excel/excel_updater.py`.
Then write `tests/test_scenario_2.py` that takes `sample_update_requests.txt` as prompt input, extracts JSON cell coordinates, and updates `sample_gambalabs_dashboard.xlsx` without breaking formulas.
```
