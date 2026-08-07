# -*- coding: utf-8 -*-
"""덱을 눈으로 보기 — .pptx를 슬라이드별 PNG로 렌더한다.

이게 없으면 "구조는 들어갔는데 보기엔 엉망"인 결과를 잡을 방법이 없다.
(사진이 카드에 가려짐, 파이 조각이 전부 같은 파랑, 글자 넘침 …)

경로: pptx --(LibreOffice)--> pdf --(pypdfium2)--> png
LibreOffice가 없으면 available()이 False를 돌려주고 호출부는 시각 검증을 건너뛴다.
"""
import os
import glob
import shutil
import subprocess
import tempfile

_SOFFICE_CANDIDATES = [
    os.environ.get("SOFFICE_PATH", ""),
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
]

_soffice_cached = None


def soffice_path():
    global _soffice_cached
    if _soffice_cached is not None:
        return _soffice_cached
    for p in _SOFFICE_CANDIDATES:
        if p and os.path.exists(p):
            _soffice_cached = p
            return p
    w = shutil.which("soffice") or shutil.which("libreoffice")
    _soffice_cached = w or ""
    return _soffice_cached


def available() -> bool:
    if not soffice_path():
        return False
    try:
        import pypdfium2  # noqa: F401
        return True
    except Exception:
        return False


def to_pdf(pptx_path: str, out_dir: str, timeout: int = 180) -> str:
    """LibreOffice로 pptx → pdf. 실패하면 빈 문자열."""
    exe = soffice_path()
    if not exe:
        return ""
    os.makedirs(out_dir, exist_ok=True)
    # 사용자 프로필을 격리해야 앱이 떠 있어도 헤드리스 변환이 막히지 않는다.
    profile = os.path.join(tempfile.gettempdir(), "gamba_lo_profile")
    uri = "file:///" + profile.replace("\\", "/")
    try:
        r = subprocess.run(
            [exe, "--headless", "--norestore", f"-env:UserInstallation={uri}",
             "--convert-to", "pdf", "--outdir", out_dir, pptx_path],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return ""
    pdf = os.path.join(out_dir, os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf")
    if os.path.exists(pdf):
        return pdf
    hits = sorted(glob.glob(os.path.join(out_dir, "*.pdf")), key=os.path.getmtime)
    return hits[-1] if hits else ""


def to_images(pptx_path: str, out_dir: str, width: int = 1280, max_pages: int = 30):
    """슬라이드별 PNG 경로 목록. 렌더 불가면 빈 목록."""
    if not available():
        return []
    os.makedirs(out_dir, exist_ok=True)
    pdf = to_pdf(pptx_path, out_dir)
    if not pdf:
        return []
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf)
    out = []
    for i in range(min(len(doc), max_pages)):
        page = doc[i]
        scale = width / max(page.get_width(), 1)
        img = page.render(scale=scale).to_pil()
        p = os.path.join(out_dir, f"slide{i + 1:02d}.png")
        img.save(p)
        out.append(p)
    doc.close()
    return out
