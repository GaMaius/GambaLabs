# 감바랩스 오피스 AI

**만든 사람: 지우가람 (Jiwoo Garam)** · 감바랩스 인턴 과제 "PowerPoint/Excel LLM 활용 시나리오 설계·구현"의 결과물

흩어진 수작업(브랜드 PPT 제작 · 대시보드 수식 수정 · 실험 기록 · 벡터 변환)을 데스크톱 앱 하나로 묶은 사내 자동화 도구.

**설계 원칙 — LLM은 '무엇을' 판단하고, 실제 파일 수술은 결정적 코드가 한다.**
LLM에게 파일을 통째로 맡기면 수식이 날아가고 레이아웃이 무너진다. 그래서 LLM은 구조화·기획만 하고,
엑셀 셀 수정은 openpyxl, PPT 렌더는 pptxgenjs가 담당한다. 결과물은 사람이 검토한 뒤 내보낸다(human-in-the-loop).

---

## 1. 실행

### 받는 사람 (빌드본)
`GambaLabsOffice/` 폴더의 **`GambaLabsOffice.exe`** 를 더블클릭. 파이썬·Node 설치 불필요.
처음 한 번 `.env.example`을 `.env`로 복사하고 API 키를 채운다(4절).

### 개발 (소스)
```
pip install -r requirements.txt
npm install
run_app.bat            # 또는  python -m app.main_app
```
- LibreOffice가 설치돼 있으면 만든 덱을 이미지로 렌더해 눈으로 검증할 수 있다(`app/ppt/deck_render.py`).
- 경로·Node 준비 상태 확인: `python main.py paths`

### 빌드
```
python tools/build_exe.py
```
`dist/GambaLabsOffice/` 에 자립 실행 폴더가 만들어진다(Node 런타임·에셋 포함). 자세한 건 `tools/BUILD.md`.

---

## 2. 기능 (탭 3개)

| 탭 | 하는 일 | 엔진 |
|---|---|---|
| **PPT** | 러프 PPT나 문서를 넣으면 브랜드 디자인을 입힌 발표자료 생성. 테마 제작·재사용 지원 | `app/ppt/` + pptxgenjs |
| **Excel** | 자연어로 대시보드 수정(수식·차트 보존) · 실험 기록 자동 누적 + 차트 · 영수증 작성 | `src/excel/` + openpyxl |
| **SVG 변환** | 비트맵 → SVG 벡터화(로고·도식·사진 유형별 자동 튜닝, 품질 채점) | `src/vector/` + vtracer |

### PPT 파이프라인 (핵심)
```
러프 PPT/문서
   → 기획 (LLM: 슬라이드 구성 JSON, lead·카드·차트 지정)
   → 배경 장식 합성 (decor.py: 그라데이션＋사진을 한 장으로)
   → 코드 생성 (LLM: pptxgenjs 코드를 직접 작성 — '자유 설계')
   → 실행 → deck_lint 기하·품질 검사 → 결함 있으면 지적하고 재작성 (최대 3회)
   → 끝내 통과 못 하면 템플릿 레이아웃으로 폴백
```
설계 자유도는 모델에 주되, **스타일과 그리드는 헬퍼가 고정**한다(`app/ppt/freeform_helpers.js`).
레이아웃 그리드 상수는 `CLAUDE.md` 3-0절 참고 — helpers·engine·lint 세 곳이 같은 값을 쓴다.

### 실험 기록 한 줄 연동
실험 스크립트에 아래 한 줄이면 엑셀 트래커에 누적되고 차트가 갱신된다.
```python
from gamba_log import log_result
log_result(정확도=91.2, 손실=0.08)
```
C 프로젝트는 `gamba_log.h`(예제: `examples/c_logger/demo.c`).

---

## 3. 폴더 구조

```
app/
  main_app.py        pywebview 진입점
  api.py             JS↔Python 브리지(모든 기능의 입구)
  ui/                HTML·CSS·JS 화면
  ppt/               PPT 엔진 — freeform_engine(자유 설계) · ppt_engine/spec_engine(템플릿)
                     freeform_helpers.js(레이아웃·스타일) · render_deck.js(템플릿 렌더)
                     deck_lint.py(품질 검사) · deck_render.py(눈으로 보기) · decor.py(배경 합성)
                     thememgr.py(테마) · image_search.py(스톡) · pptx_import.py(러프 PPT 읽기)
src/
  common/paths.py    ★ 경로 단일 기준점 (소스/빌드 공통) — 새 경로가 필요하면 여기에 추가
  common/llm_client.py  Groq · Ollama · OpenAI 통합 팩토리
  excel/             엑셀 수술·분석·실험로거·영수증
  vector/            벡터 변환 튜닝·품질채점·SVG 축소
ppt-skill/           브랜드 에셋(로고·배경) + 디자인 가이드 문서
assets/docs/         보고서용 구조도(SVG·PNG)
tools/               빌드 스크립트·유틸
tests/ examples/     테스트·예제
gamba_log.py .h      실험 기록 한 줄 연동 모듈
output/              ▶ 생성물·캐시 (실행 중 자동 생성, 지워도 됨)
themes/              ▶ 사용자가 만든 테마 (실행 중 생성)
```
▶ 표시는 실행하면서 만들어지는 폴더다. 소스 관리 대상이 아니다.

**경로 규칙 (중요)**: 새 코드에서 `os.path.dirname(...)`을 겹쳐 쓰지 말고 `src/common/paths.py`를 쓴다.
읽기 전용 리소스는 `paths.RES_DIR`, 쓰기 대상은 `paths.DATA_DIR`. 이 둘을 섞으면 exe 빌드본에서 깨진다.

---

## 4. LLM 설정 — `.env`

`.env.example`을 `.env`로 복사해서 채운다. **`.env`는 절대 커밋하지 않는다.**

| 항목 | 설명 |
|---|---|
| `LLM_PROVIDER` | `groq` \| `ollama` \| `openai` (미지정 시 키 유무로 자동 감지) |
| `GROQ_API_KEY` | Groq LPU — 빠르고 무료 티어 있음. PPT 자유 설계에 권장 |
| `GROQ_MODEL` | 기본 `llama-3.3-70b-versatile` |
| `PPT_CODE_MODEL` | 코드 생성 전용 모델 강제(기본은 `openai/gpt-oss-120b` 우선 자동 선택) |
| `PPT_FREE_LAYOUT` | `0`이면 자유 설계를 끄고 템플릿만 사용 |
| `PEXELS_API_KEY` | 스톡 이미지(없으면 Openverse로 폴백, 키 불필요) |

모델은 앱 좌하단 선택기에서도 바꿀 수 있다.

---

## 5. 이어서 작업할 때

- 프로젝트 맥락·결정사항·재발 주의 사항은 **`CLAUDE.md`** 에 정리돼 있다. 먼저 읽을 것.
- 진행 중이던 개선 항목은 `IMPROVEMENTS.md`.
- PPT 작업 후에는 **반드시 덱을 이미지로 렌더해서 눈으로 확인**한다. 구조 검사만으로는
  "들어가긴 했는데 보기엔 엉망"을 못 잡는다(실제로 여러 번 놓쳤다).
