# CLAUDE.md — 감바랩스 오피스 AI (세션 인수인계)

다른 세션이 이 문서만 읽고 작업을 이어받을 수 있도록 정리한 프로젝트 맥락·구조·결정사항.

## 0. 프로젝트 목표
감바랩스(온디바이스 음성인식 KWS 회사 "WordSense")의 **사내 오피스 업무 자동화 데스크톱 앱**.
인턴(가람)이 맡은 과제 "PowerPoint/Excel LLM 활용 시나리오 설계·구현"의 결과물.
- 핵심 원칙: **LLM은 '무엇을' 판단, 실제 파일 수술(디자인·수식·차트)은 결정적 코드.** (검증된 도구를 엮어 신뢰도↑, human-in-the-loop)
- 데이터 주권: 로컬/사내 LLM로 대외비 문서 외부 전송 0. 데모는 로컬 Ollama.

## 1. 실행
```
run_app.bat                 # 또는:
python -m app.main_app      # (프로젝트 루트에서)
```
- pywebview 데스크톱 앱(HTML/CSS/JS UI + Python js_api). Windows=Edge WebView2.
- 종료: 앱 창 닫기. 콘솔의 pywebview 로그는 억제됨(main_app.py에서 logger CRITICAL).
- **주의(중요 버그 이력)**: `Api` 객체에 창을 붙일 땐 반드시 `self._window`(밑줄). 공개 속성으로 두면
  pywebview가 `window.native`(.NET) 그래프를 무한 재귀 훑어 UI 스레드가 멈춤("응답없음"). `api.py`/`main_app.py` 참고.

## 2. 앱 구조 — 3탭
### 발표자료 (`app/ppt/`) — 4모드, 최종 렌더는 `render_deck.js`(pptxgenjs)
- **풀 자동**: 문서(md/txt) → `ppt_engine.py` 파싱/LLM 구조화 → 덱. `AI 구조화(Ollama)` 토글.
- **디자인 보조(스펙)**: `spec_engine.py` — `#제목/-불릿[강조]/[차트:..]/[이미지:..]` 문법. UI에서 기본 숨김(토글로 표시).
- **AI 대화형**: `agent_chat.py` — GPT/Claude식 단일 채팅면(입력 하단 고정). 질문하며 샘플→전체.
- **PPT 입력**: `pptx_import.py` — 러프 PPT의 텍스트·설명 읽어 해석. `AI 정밀 해석(Ollama)` 토글.
- **🎨 디자인 테마**(4모드 공통): 내장 gamba/light/none + **커스텀 업로드/제작**(`thememgr.py`, `app/ppt/themes/*.json`).

### 데이터 & 차트 (`src/excel/`)
- **실험/재무 기록 + 자동차트**: `experiment_logger.py`. 실험 스크립트에 `from gamba_log import log_result` 한 줄이면 트래커 누적+차트 갱신.
- **대시보드 수정**: `llm_extractor.py`(NL→셀) + `excel_updater.py`(openpyxl, 수식·차트 보존, `_is_formula` 가드). 미리보기→적용.
- **분석/요약**: `excel_analysis.py`(pandas 로드 + LLM 요약/추세/이상치).

### 벡터 변환 (`app/api.py::vectorize`)
- 비트맵→SVG (visioncortex **vtracer**, `pip install vtracer`). 별도 프로세스+60초 타임아웃(무한로딩 방지).
- 입력은 Pillow로 **RGBA 정규화**(투명 유지; RGB로 바꾸면 투명→검정 버그) + 800px 다운스케일.
- HEIC/AVIF/WebP 지원(`pillow-heif`, `pillow-avif-plugin`, api.py에서 등록). 큰 SVG(>180KB)는 인라인 미리보기 생략.

## 3. 설계 방침 분리 (중요) — `app/ppt/design_policy.py`
모델 급에 따라 설계 강도를 바꿈(**과제약의 역설** 회피). 자세한 건 README.md 참고.
- `template`(로컬 3b/7b): 프롬프트 규칙 강제 + 후처리 적극 개입(지시문구 제거·카드 자동변환·1:1 매핑).
- `freeform`(회사 GPT/Claude): 설계를 모델에 위임, 후처리 최소.
- 자동 선택: 비로컬 + `gpt-*`/`claude-*` → freeform, 아니면 template. 수동: `.env` `PPT_DESIGN_MODE=auto|template|freeform`.
- 렌더 자동 글자크기: `render_deck.js`의 `fitSize`/`fitList`가 박스에 맞게 폰트 계산(오버플로 방지).
- 신규 레이아웃: `metrics`(지표 카드), `compare`(2열+도넛), 막대+추세선(`chart.trend`), 그라데이션(`gradient.py`).

## 4. LLM 백엔드 — `.env` (gitignore됨)
- `OPENAI_BASE_URL`/`OPENAI_MODEL`/`OPENAI_API_KEY` 스왑. 데모=로컬 Ollama(`http://localhost:11434/v1`, `qwen2.5:7b-instruct`/`3b`).
- 모델 선택 UI(사이드바 7b/3b). **실배포는 회사 GPT로 URL·모델만 교체**(코드 0 변경) → 품질·속도↑.
- 이미지: `PEXELS_API_KEY`(있음, 우선) → 없으면 **Openverse**(키 불필요·CC) 폴백. `image_search.py`.
- ⚠️ `.env`에 사용자 실제 키 존재 — **절대 출력/커밋 금지**(gitignore 확인).

## 5. 검증된 사실 / 한계
- 로컬 모델 천장: 7b는 metrics/compare 설계 가능(느림 ~5분), 3b는 예시 없는 새 입력에서 붕괴(빈 결과→규칙 폴백).
  → 목표급(`planing/클로드 버전.pptx` 12장)엔 회사 GPT 필요. 이게 정직한 결론.
- 시각 QA 제약: LibreOffice 미설치라 덱을 이미지로 못 봄 → 사용자 PowerPoint 확인 의존. python-pptx로 구조는 검증 가능.
- 샘플 픽스처: `planing/`(sample_*.pptx/xlsx/txt, 클로드 버전.pptx=목표품질, 샘플로 넣은 버전.pptx=러프 입력).

## 6. 스택
Python 3.11: pywebview 6.2.1, openai 2.x, openpyxl, pandas, python-pptx, Pillow(+heif/avif), reportlab, vtracer, requests, python-dotenv.
Node: pptxgenjs, @resvg/resvg-js. 에셋: `ppt-skill/assets/`(로고·배경), 스킬 가이드 `ppt-skill/*.md`, `THEME_AUTHORING.md`.

## 7. 백로그 (미완)
- 7b 설계 실수(1:1 매핑·오분류) 추가 완화 / 회사 GPT 연동 시 freeform 실검증
- 팀장님 PDF 보고서에 경쟁툴+3b/7b 벤치마크 반영 / PyInstaller .exe 패키징 / Word(docx) 탭
- 테마 업로드·제작 실제 앱 클릭 테스트(현재 DOM 검증만)
