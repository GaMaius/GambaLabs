# 빌드 · 배포 메모

made by 지우가람 (Jiwoo Garam)

## 빌드하기

```bat
pip install -r requirements.txt
pip install pyinstaller
npm install
python tools/build_exe.py --clean
```

결과: `dist/GambaLabsOffice/` — **이 폴더째로 압축**해서 전달한다.

| 옵션 | 뜻 |
|---|---|
| `--clean` | `build/`·`dist/`를 지우고 새로 |
| `--no-node` | Node 런타임을 넣지 않는다(받는 사람이 Node.js 설치) |

## 왜 이런 구조인가

**onedir(폴더형)을 쓴다.** onefile은 실행할 때마다 수백 MB를 임시 폴더에 풀어서
시작이 느리고, Node를 exe 옆에 두는 구조와도 맞지 않는다.

**리소스와 작업 폴더를 나눈다.** `src/common/paths.py` 참고.

| | 소스 실행 | exe 실행 |
|---|---|---|
| `RES_DIR` (읽기 전용: 에셋·JS) | 프로젝트 루트 | `_internal/` (PyInstaller 추출본) |
| `DATA_DIR` (쓰기: output·themes·.env) | 프로젝트 루트 | **exe가 있는 폴더** |

이 둘을 섞으면 빌드본이 읽기 전용 폴더에 쓰려다 조용히 실패하거나,
임시 폴더에 써서 앱을 끄는 순간 결과물이 사라진다. 새 경로가 필요하면
`dirname()`을 겹쳐 쓰지 말고 반드시 `paths`에 추가한다.

**Node는 `runtime/node/node.exe`로 함께 넣는다.** PPT 렌더(pptxgenjs)와
SVG 래스터화(resvg)가 Node에서 돌기 때문에 파이썬만 묶어서는 반쪽짜리다.
`paths.node_exe()`가 번들본을 먼저 찾고, 없으면 PATH의 `node`를 쓴다.

## 받는 사람의 첫 실행

1. `GambaLabsOffice.exe` 더블클릭
2. 좌측 사이드바 **🔑 API 키 설정** → 키 입력 → 저장 → **연결 확인**
   - 키는 exe 옆 `.env`에 저장되고 재시작 없이 바로 적용된다.
   - 메모장으로 `.env`를 직접 고쳐도 된다(그때는 재시작 필요).
3. 결과물은 exe 옆 `output/`에 쌓인다.

## 확인 목록 (빌드 후 직접 해 볼 것)

- [ ] exe 실행 → 창이 뜨는가 (안 뜨면 Edge WebView2 런타임 설치)
- [ ] 🔑 API 키 설정 → 저장 → **연결 확인**이 초록으로 뜨는가
- [ ] PPT 탭에서 러프 PPT 하나 넣고 생성 → `output/ppt/`에 파일이 생기는가
- [ ] Excel 탭에서 대시보드 수정 미리보기 → 적용
- [ ] 폴더를 다른 경로(예: `D:\temp\`)로 옮겨도 똑같이 되는가

마지막 항목이 핵심이다. 경로를 절대경로로 박아 두면 여기서 깨진다.

## 알려진 제약

- **Windows 전용.** pywebview가 Edge WebView2를 쓴다.
- 덱을 이미지로 렌더해 보는 기능(`deck_render.py`)은 LibreOffice가 설치돼 있어야 한다.
  개발용 검증 도구라 빌드본에는 필수가 아니다.
- 코드 서명은 하지 않았다. SmartScreen 경고가 뜨면 '추가 정보 → 실행'.
- 사용 가이드 화면의 코드 하이라이팅은 CDN(highlight.js)을 쓴다.
  인터넷이 없으면 색만 안 입고 내용은 정상 표시된다.
