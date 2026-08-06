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
### 발표자료 (`app/ppt/`) — 최종 렌더는 `render_deck.js`(pptxgenjs)
UI 모드(현재): **테마 개발 · PPT 디자인 · 자동 생성 PPT**(+플로팅 편집기는 숨김 처리, 코드 보존).
- **자동 생성 PPT**(옛 '풀 자동'): 문서(md/txt) → `ppt_engine.py` 파싱/LLM 구조화 → 덱. `AI 구조화(Ollama)` 토글.
- **PPT 디자인**(옛 'PPT 입력'): `pptx_import.py` — 러프 PPT의 텍스트·설명 읽어 레이아웃 설계. `AI 정밀 해석(Ollama)` 토글.
- **테마 개발**: 디자인 폼 값으로 재사용 테마 저장(`thememgr.add_from_spec`).
- (내부 보존, UI 비노출) `spec_engine.py`(스펙 문법), `agent_chat.py`(대화형). 재활성화 가능.
- **🎨 디자인 테마**(공통): 내장 gamba/light/none + **커스텀 업로드/제작**(`thememgr.py`, `app/ppt/themes/*.json`).
- **🎨 디자인 설정 폼**(`#designForm`, 3모드 공통): pptx-making-guide 질문을 항목형으로. 폼 값 → 임시 테마(`set_form_theme`) + **디자인 브리프**(`set_design_brief`: 목적·자유 디렉션·참고자료)로 생성에 주입.
  - 폼→생성 연결 흐름: `applyFormTheme()`(색·폰트·그라데이션) + `applyDesignBrief()`(목적+디렉션+참고자료 텍스트) → `ppt_make_full`/`ppt_import_make`가 `brief`를 build_plan→interpret_llm 프롬프트에 넣음.
  - 참고 이미지 색 추출: `api.extract_palette(image)`(Pillow 양자화) → 강조/배경/글자 추천.

### 데이터 & 차트 (`src/excel/`)
- **실험/재무 기록 + 자동차트**: `experiment_logger.py`. 실험 스크립트에 `from gamba_log import log_result` 한 줄이면 트래커 누적+차트 갱신.
- **대시보드 수정**: `llm_extractor.py`(NL→셀) + `excel_updater.py`(openpyxl, 수식·차트 보존, `_is_formula` 가드). 미리보기→적용.
- **분석/요약**: `excel_analysis.py`(pandas 로드 + LLM 요약/추세/이상치).

### 벡터 변환 (`app/api.py::vectorize` + `src/vector/`)
비트맵→SVG (visioncortex **vtracer**). 별도 프로세스로 실행 → '중지' 버튼으로 kill 취소.
- `src/vector/vector_autotune.py` — 분류(**lineart/diagram/logo/photo**) · 유형별 전처리 · 후보 파라미터 생성.
- `src/vector/quality.py` — 결과 SVG를 resvg로 되-래스터화해 원본과 비교(**SSIM + 획 보존 F1**). node/resvg 없으면 `None` 반환(가짜 점수 금지).
- `src/vector/svgmin.py` — 좌표 표기 무손실 축소(약 7%). `.` 앞 공백은 절대 지우면 안 됨(`1 .5`→`1.5`로 좌표 소실).
- `app/ppt/_vtrace_run.py` — job.json을 받아 후보들을 트레이스·채점·최적안 채택. 구버전 positional 호출도 유지.
- 유형별 핵심: 선화=**그레이 2배 확대+Otsu 이진화 → binary 모드**, 컬러 도식=**BICUBIC 2배 확대·색 보존·filter_speckle 2**, 사진=등배·색 제한 없음·filter_speckle 4.
- 확대 배율은 `small_mark_ratio`(작은 획 덩어리 비율)로 자동 결정 — 글자 많으면 2배, 큰 면 아이콘은 등배.
- 확대 보간은 **BICUBIC**. LANCZOS는 오버슈트(링잉)해 획 둘레에 후광을 만든다.
- 배경 제거 후엔 `defringe_cutout()` 필수 — rembg의 반투명 경계가 검은 윤곽선으로 트레이스된다.
- **글자 깨짐 3대 원인(수정 완료, 재발 주의)**
  1. `filter_speckle`을 크게 잡으면 `=`·`i`의 점 같은 작은 획이 통째로 사라진다. (옛 코드: 색 수 6000 초과 시 무조건 10으로 올림 → 도식 텍스트 전멸)
  2. `length_threshold`의 vtracer 유효 범위는 **[3.5, 10]**. 범위 밖(옛 코드 1.5) 값은 과분할로 경로를 붕괴시킨다. → `clamp_params()`가 강제.
  3. 트레이스 전 **언샤프 마스킹 금지**. 글자 테두리 헤일로가 별도 색 레이어로 잡혀 획이 이중으로 찍힌다. → 확대만 하고 샤프닝은 안 함.
- 투명 유지: 입력은 RGBA로 다룬다(RGB로 바꾸면 투명→검정). 선화만 흰 배경 합성 후 이진화.
- HEIC/AVIF/WebP 지원(`pillow-heif`, `pillow-avif-plugin`, api.py에서 등록).
- 미리보기: SVG ≤180KB면 인라인, 크면 resvg로 PNG 렌더해 data URI로 표시.

## 3. 설계 방침 분리 (중요) — `app/ppt/design_policy.py`
모델 급에 따라 설계 강도를 바꿈(**과제약의 역설** 회피). 자세한 건 README.md 참고.
- `template`(로컬 3b/7b): 프롬프트 규칙 강제 + 후처리 적극 개입(지시문구 제거·카드 자동변환·1:1 매핑).
- `freeform`(고성능 Groq LPU 70B / OpenAI GPT-4o / Claude): 설계를 모델에 위임, 후처리 최소(풀 컨텍스트 및 자유 레이아웃 생성).
- 자동 선택: Groq (`groq`), OpenAI (`openai`), 또는 고성능 70B/32B/GPT/Claude 모델 ➡️ **freeform**, 로컬 소형 모델 ➡️ template. 수동: `.env` `PPT_DESIGN_MODE=auto|template|freeform`.
- 렌더 자동 글자크기: `render_deck.js`의 `fitSize`/`fitList`가 박스에 맞게 폰트 계산(오버플로 방지).
- 신규 레이아웃: `metrics`(지표 카드), `compare`(2열+도넛), 막대+추세선(`chart.trend`), 그라데이션(`gradient.py`).

## 4. LLM 백엔드 — `src/common/llm_client.py` 및 `.env` (gitignore됨)
- **Groq (GPT OSS - Llama 3.3 70B, Qwen 2.5 32B, DeepSeek R1)** / **Ollama** / **OpenAI** 3원 통합 팩토리.
- `LLM_PROVIDER=groq|ollama|openai` 설정 또는 `GROQ_API_KEY` 유무로 자동 감지.
- Groq 선택 시 `https://api.groq.com/openai/v1` 엔드포인트 및 `GROQ_MODEL=llama-3.3-70b-versatile` 기본 작동.
- 모델 선택 UI(사이드바). **Groq/Ollama/OpenAI 프로바이더 및 모델 스왑 완비**.
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

## 7. 진행 중 — 디자인 입력 폼 강화 (IMPROVEMENTS.md 참고)
"퀄리티·자유도·UI/UX" 목표로 폼을 개편 중. 착수 시점 스냅샷:
- 진단: 폼이 색·폰트만 임시 테마로 쓰고 **목적·참고자료·비율·그라데이션은 수집만 하고 버려짐** → 생성 품질에 폼이 거의 영향 없음.
- 착수 항목(체크리스트 IMPROVEMENTS.md "디자인 입력 폼 강화"): (1)플로팅 숨김 (2)참고자료 다중 (3)이미지 색 추출 (4)자유 디렉션 (5)폼→생성 brief 주입 (6)기반 테마 시드 (7)그라데이션 실적용 (8)UX 정돈.
- 신규 API(구현/예정): `set_design_brief(purpose,direction,refs[])`, `extract_palette(image)`, `set_form_theme(...,gradient)`; 엔진 `interpret_llm(...,brief)`·`build_plan(...,brief)`·`generate(...,brief)`.

## 8. 백로그 (미완)
- 7b 설계 실수(1:1 매핑·오분류) 추가 완화 / 회사 GPT 연동 시 freeform 실검증
- 팀장님 PDF 보고서에 경쟁툴+3b/7b 벤치마크 반영 / PyInstaller .exe 패키징 / Word(docx) 탭
- 테마 업로드·제작 실제 앱 클릭 테스트(현재 DOM 검증만)
- 플로팅 편집기: 현재 숨김. PPT 임베드 편집은 pywebview 한계로 보류.
