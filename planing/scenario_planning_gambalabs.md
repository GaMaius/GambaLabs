# 📄 [기획서] 감바랩스 오피스 LLM 활용 시나리오 설계 및 테스트 방안

**작성자:** ⭐가람⭐  
**대상 서비스:** 감바랩스 사내 문서 자동화 파이프라인 (PPT / Excel)  
**기반 인프라:** OpenAI GPT (Codex / API), Polaris AI DataInsight, MS Ecosystem (Teams, Outlook, OneDrive), GitHub, VSCode  

---

## 1. 개요 및 핵심 전략

### 💡 기획 배경
본 기획은 감바랩스가 사용 중인 오피스 생태계(MS Teams, Outlook, OneDrive) 및 개발 도구(VSCode, GitHub), 그리고 OpenAI GPT 모델을 결합하여 **R&D 제안서/발표용 PPT 제작** 및 **연구비/프로젝트 일정 Excel 정산**을 자동화하는 최적의 파이프라인을 다룹니다.

### 🎯 핵심 원칙 (GPT Custom Skill 기반 오케스트레이션)
1. **신뢰성 보장 (검증된 파이프라인 결합)**: LLM이 코드를 백지부터 짜거나 레이아웃을 임의로 그리지 않고, **GPT Custom Skill (`pptx-guide`)**과 검증된 오픈소스(`openpyxl`, `OfficeCLI`)를 엮어 양식과 디자인의 깨짐을 방지합니다.
2. **사내 테마 일관성**: `pptx-guide` 스킬 내에 감바랩스 브랜드 컬러, 폰트, 레이아웃 규칙을 등록하여 상시 균일한 품질의 결과물을 보장합니다.
3. **기존 인프라 100% 활용**: 추가 소프트웨어 도입 없이 기존 MS Teams/Outlook/OneDrive 및 GitHub 연동으로 인프라 구축 비용을 최적화합니다.

---

## 2. 세부 시나리오 정의

### 📌 [시나리오 1] PowerPoint: Custom Skill (`pptx-guide`) 기반 R&D 제안서 & 발표 덱 자동 생성

* **목적**: 비정형 연구 노트, 과제 공고문, 기술 메모를 감바랩스 표준 브랜드 테마가 적용된 `.pptx` 파일로 변환.
* **주요 흐름**:
  1. **입력**: Outlook 메일 첨부파일 또는 MS Teams 채널에 HWP / PDF / TXT 형식의 기술 문서 업로드.
  2. **구조화 (Polaris AI)**: Polaris AI DataInsight API를 통해 비정형 문서 내 텍스트, 표, 차트 수치를 경량 JSON/Markdown으로 파싱.
  3. **슬라이드 생성 (ChatGPT + `pptx-guide` Skill)**:
     - `pptx-guide` 스킬에 정의된 감바랩스 테마(컬러 팔레트, Typography, 마스터 슬라이드 구조) 불러오기.
     - GPT가 파싱된 JSON 데이터를 슬라이드별 핵심 요약(제목, Bullet point, 구조화 표)으로 매핑 및 PPTX 생성.
  4. **전달**: 생성된 완제품 `.pptx`를 OneDrive 공유 폴더에 자동 저장하고 MS Teams 대화창 및 Outlook 답장으로 전달.

---

### 📌 [시나리오 2] Excel: 연구비 집행 & 프로젝트 일정 실시간 대시보드 업데이트

* **목적**: 흩어진 영수증 수치, 수작업 변경 요청을 기존 Excel 수식과 차트가 유지된 대시보드에 실시간 반영.
* **주요 흐름**:
  1. **입력**: MS Teams 대화창의 자연어 요청("AI 모듈 테스트 일정 10일 연장, 서버 임차비 350만원 추가") 또는 영수증 파일.
  2. **추론 (GPT-4o / Codex)**: 변경해야 할 셀의 좌표, 항목, 수정 수치를 지정된 JSON 구조체로 파싱.
  3. **셀 데이터 주입 (`openpyxl` / `OfficeCLI`)**:
     - 기존 엑셀 파일의 **수식(SUM, AVERAGE 등), 조건부 서식, 대시보드 차트를 100% 보존**.
     - 대상 셀에만 데이터 및 날짜를 정확히 업데이트.
  4. **동기화**: OneDrive 내 엑셀 파일 자동 저장(Auto-save) 및 MS Teams 관리자 채널에 업데이트 결과 알림.

---

## 3. 기술 스택 및 역할 매핑

| 카테고리 | 활용 도구 / 기술 | 주요 역할 및 담당 업무 |
| :--- | :--- | :--- |
| **AI Engine** | OpenAI GPT-4o / Codex | 문서 요약, JSON 구조화, 수치 변경지점 추론 |
| **Custom Skill** | Custom GPT (`pptx-guide`) | 감바랩스 디자인 테마 유지, 슬라이드 레이아웃 오케스트레이션 |
| **Parser** | Polaris AI DataInsight | HWP / PDF 문서의 표, 차트, 메타데이터 구조화 파싱 |
| **Document Control** | `openpyxl`, `OfficeCLI` | 엑셀 수식/차트 보존 셀 단위 데이터 수정 |
| **Interface** | MS Teams, Outlook | 사용자 입력 접수 및 최종 파일 전달 매개체 |
| **Storage & Code** | OneDrive, GitHub, VSCode | 파일 중앙 저장 및 파이프라인 코드 버전 관리 |

---

## 4. 테스트 및 검증 방안

* 제공된 샘플 파일(`sample_input_research_note.pdf`, `pptx_guide_skill_sample.md`, `sample_gambalabs_dashboard.xlsx`, `sample_update_requests.txt`)을 활용하여 각 단계별 입출력 결과를 검증합니다.
