# 감바랩스 PPT 스킬 패키지

문서 하나를 **감바랩스 브랜드 발표자료(.pptx)**로 바꿔주는 재사용 패키지.
쓰는 사람은 이 폴더를 에이전트(Codex/Claude)에 물려주고 한 줄만 지시하면 된다.

## 쓰는 법 (Codex 기준)

1. Codex를 이 `ppt-skill/` 폴더에서 연다. (Codex가 `AGENTS.md`를 자동으로 읽음)
2. 이렇게 지시한다:
   > "`<문서경로>` 이 문서로 감바랩스 발표자료 만들어줘."
3. 에이전트가 문서를 구조화하고, 테마를 입혀 `pptxgenjs`로 `.pptx`를 생성한 뒤 검증까지 마친다.
4. 사람이 결과물을 검토하고 필요 시 수정 지시("3번 슬라이드를 표로", "표지 부제 바꿔") → 재생성.

> Claude Code를 쓰면 동봉된 `pptx-making-guide` 스킬 워크플로우와 그대로 호환된다. Codex는 `.skill` 포맷을 직접 읽지 못하므로, 이 패키지의 `AGENTS.md` + `GAMBALABS_PPT_GUIDE.md`가 그 역할을 대신한다.

## 폴더 구성

```
ppt-skill/
├── AGENTS.md                  # 에이전트 진입점(Codex가 자동 로드)
├── GAMBALABS_PPT_GUIDE.md     # 제작 규칙 전체
├── theme/gambalabs_theme.md   # 브랜드 테마 원본 명세
├── assets/
│   ├── logo/                  # 로고 4종 PNG + 원본 SVG
│   └── backgrounds/           # 표지 배경, 헤더 밴드 PNG
├── scripts/                   # 자산 재생성(로고/색 바뀔 때만)
│   ├── gen_logo.js            #   node scripts/gen_logo.js
│   └── gen_backgrounds.py     #   python scripts/gen_backgrounds.py
└── examples/
    ├── build_samples.js       # 레퍼런스 pptxgenjs 스크립트
    └── gambalabs_samples.pptx # 승인된 샘플(목표 이미지)
```

## 준비물
- Node.js + `pptxgenjs`, `@resvg/resvg-js`
- Python + `Pillow`
- (자산이 이미 들어 있으므로, 로고/브랜드색을 바꾸지 않는 한 재생성 불필요)

## 데이터 관련
PPT 내용(제안서·발표자료)은 외부향 콘텐츠라 외부 LLM(GPT/Claude) 사용이 허용된 범위다.
사내 대외비 문서를 다룰 땐 사내 에이전트/온프레 모델로 교체할 수 있다.
