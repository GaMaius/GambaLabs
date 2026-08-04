# -*- coding: utf-8 -*-
"""pywebview JS↔Python 브리지 (v2).

원칙: LLM/파서는 '무엇을' 판단, 실제 파일 수술(Excel 셀·PPT 렌더·차트)은 결정적 코드.
파일에 쓰기 전 UI에서 '확인' 게이트를 거친다.
"""
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(HERE)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from src.excel.llm_extractor import LLMExtractor
from src.excel.excel_updater import ExcelUpdater
from src.excel.experiment_logger import ExperimentLogger
from src.excel import excel_analysis
from app.ppt.ppt_engine import generate as ppt_generate_full, build_plan as ppt_plan_full
from app.ppt.spec_engine import generate as ppt_generate_spec, build_plan as ppt_plan_spec, render_plan
from app.ppt import image_search
from app.ppt import pptx_import
from app.ppt import thememgr

# 아이폰(HEIC)·AVIF·WebP 등 확장 이미지 형식을 Pillow가 읽도록 등록(벡터 변환 입력 확대)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass
try:
    import pillow_avif  # noqa: F401  (임포트만으로 AVIF 오프너 등록)
except Exception:
    pass

OUTPUT = os.path.join(PROJECT_DIR, "output")


def _ts(name, ext):
    return f"{name}_{datetime.datetime.now().strftime('%m%d_%H%M%S')}.{ext}"


class Api:
    def __init__(self):
        # 주의: pywebview는 Api의 '공개' 속성을 훑어 JS에 노출한다. 창 객체를 공개로 두면
        # window.native(.NET) 그래프를 무한 재귀로 훑다 UI 스레드가 멈춘다(=응답없음).
        # 반드시 밑줄(_)로 시작해 pywebview introspection에서 제외한다.
        self._window = None
        self._chat = None
        self.theme = "gamba"
        self._rembg_session = None   # 배경 제거 세션(최초 사용 시 로드·재사용)
        self._vec_proc = None        # 진행 중 벡터 변환 프로세스(중지용)
        self._vec_cancelled = False
        self._form_theme = None      # 디자인 설정 폼에서 만든 임시 테마
        self._float_window = None     # 플로팅 편집기 창
        self._brief = None            # 디자인 브리프(목적·자유 디렉션·참고자료) — 생성에 주입

    # ── 파일 다이얼로그 ─────────────────────────────
    def pick_file(self, kind="doc"):
        import webview
        types = {
            "doc": ("문서 (*.md;*.txt;*.docx;*.pdf)", "All files (*.*)"),
            "xlsx": ("엑셀 (*.xlsx)", "All files (*.*)"),
            "pptx": ("파워포인트 (*.pptx)", "All files (*.*)"),
            "theme": ("테마 파일 (*.json)", "All files (*.*)"),
            "image": ("이미지 (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp)", "All files (*.*)"),
        }.get(kind, ("All files (*.*)",))
        try:
            r = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=types)
        except Exception as e:
            print("[pick_file] filter error, retry without filter:", e)
            r = self._window.create_file_dialog(webview.OPEN_DIALOG)
        return r[0] if r else ""

    def open_folder(self, path):
        try:
            os.startfile(path if os.path.isdir(path) else os.path.dirname(path))
        except Exception:
            pass
        return True

    def llm_status(self):
        return "GPT(온라인)" if (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")) else "오프라인 휴리스틱"

    def img_status(self):
        try:
            return image_search.source_label()
        except Exception:
            return "스톡 검색 ON"

    def get_llm(self):
        """현재 모델 + 선택 가능한 모델 목록(로컬 Ollama면 설치된 것들)."""
        cur = os.getenv("OPENAI_MODEL", "gpt-4o")
        base = os.getenv("OPENAI_BASE_URL")
        options = []
        if base:
            try:
                import requests
                r = requests.get(base.rstrip("/") + "/models", timeout=4)
                options = [m["id"] for m in r.json().get("data", [])]
            except Exception:
                options = []
        if not options:
            options = [cur]
        if cur not in options:
            options.insert(0, cur)
        return {"current": cur, "options": options, "backend": base or "OpenAI"}

    def set_model(self, name):
        if name:
            os.environ["OPENAI_MODEL"] = name
            self._chat = None  # 진행 중 대화는 새 모델로 재시작
        return {"current": os.getenv("OPENAI_MODEL")}

    # ── 발표자료 테마 선택/추가/제작 ─────────────────
    def get_themes(self):
        return {"current": self.theme, "options": thememgr.list_themes()}

    def set_theme(self, name):
        if name and any(t["id"] == name for t in thememgr.list_themes()):
            self.theme = name
        return {"current": self.theme}

    def theme_colors(self, theme_id):
        """폼 '기반 테마' 시드용: 테마의 배경/강조/글자 색을 반환."""
        _BUILTIN = {
            "gamba": {"bg": "ECECEC", "accent": "0038A3", "ink": "123979"},
            "light": {"bg": "F4F6FA", "accent": "0038A3", "ink": "123979"},
            "none":  {"bg": "FFFFFF", "accent": "2456C7", "ink": "222222"},
        }
        if theme_id in _BUILTIN:
            return _BUILTIN[theme_id]
        try:
            cfg = thememgr.resolve(theme_id)
            if cfg and isinstance(cfg.get("C"), dict):
                C = cfg["C"]
                return {"bg": C.get("body", "FFFFFF"), "accent": C.get("brand", "2456C7"),
                        "ink": C.get("hero", "1A1A1A")}
        except Exception:
            pass
        return {}

    def _theme_config(self):
        """현재 테마가 폼(__form)이면 임시 설정, 커스텀이면 전체 설정, 내장이면 None."""
        if self.theme == "__form" and self._form_theme:
            return self._form_theme
        try:
            return thememgr.resolve(self.theme)
        except Exception:
            return None

    def set_form_theme(self, bg, accent, ink, band_fill=True, font="맑은 고딕", gradient=False):
        """디자인 설정 폼 값으로 '임시 테마'를 만들어 현재 적용(저장 안 함).
        gradient=True면 배경 그라데이션 PNG를 만들어 themeConfig.gradientBg로 첨부(render_deck.js가 콘텐츠 슬라이드 배경에 사용)."""
        try:
            cfg = thememgr.build_config("디자인 설정", bg, accent, ink, bool(band_fill), font, font)
            if gradient:
                try:
                    from app.ppt import gradient as _grad
                    from app.ppt import thememgr as _tm
                    bg_hex = _tm._norm_hex(bg, "FFFFFF")
                    # 배경색 → 강조 쪽으로 12% 섞은 색으로 은은한 그라데이션(밝으면 살짝 어둡게, 어두우면 살짝 밝게)
                    c2 = _tm._mix(bg_hex, _tm._rgb(accent), 0.14)
                    cfg["gradientBg"] = _grad.gradient_png("#" + bg_hex, "#" + c2, direction="v")
                except Exception as e:
                    print("[set_form_theme] gradient 생성 실패:", e)
            self._form_theme = cfg
            self.theme = "__form"
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    # ── 디자인 브리프(목적·자유 디렉션·참고자료) ─────────
    def set_design_brief(self, purpose="", direction="", refs=None):
        """폼의 자유 입력(목적·추가 디렉션)과 참고자료 경로 목록을 저장. 생성 시 LLM 프롬프트에 주입된다."""
        if isinstance(refs, str):
            refs = [refs]
        refs = [r for r in (refs or []) if r and os.path.exists(r)]
        self._brief = {"purpose": (purpose or "").strip(),
                       "direction": (direction or "").strip(),
                       "refs": refs}
        return {"ok": True, "refs": len(refs)}

    def _load_ref_text(self, path, limit=1500):
        """참고자료 파일에서 텍스트를 추출(md/txt/docx). 실패·이미지 등은 파일명만."""
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in (".md", ".txt", ".csv"):
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()[:limit]
            if ext == ".docx":
                from docx import Document  # python-docx
                d = Document(path)
                return "\n".join(p.text for p in d.paragraphs if p.text.strip())[:limit]
        except Exception:
            pass
        return ""

    def _brief_text(self):
        """저장된 브리프를 LLM 프롬프트용 문자열로 조립(없으면 빈 문자열)."""
        b = self._brief
        if not b:
            return ""
        parts = []
        if b.get("purpose"):
            parts.append(f"[발표 목적·톤]\n{b['purpose']}")
        if b.get("direction"):
            parts.append(f"[제작자 추가 디렉션 — 최대한 반영]\n{b['direction']}")
        for i, r in enumerate(b.get("refs") or [], 1):
            txt = self._load_ref_text(r)
            name = os.path.basename(r)
            if txt:
                parts.append(f"[참고자료 {i}: {name}]\n{txt}")
            else:
                parts.append(f"[참고자료 {i}: {name}] (내용 텍스트 없음 — 디자인 참고용 파일)")
        return "\n\n".join(parts).strip()

    def extract_palette(self, image_path=None, n=6):
        """참고 이미지에서 대표색을 추출(Pillow 양자화). 강조/배경/글자 추천색도 함께 반환.
        image_path 없으면 파일 선택 다이얼로그를 띄운다."""
        try:
            if not image_path:
                image_path = self.pick_file("image")
            if not image_path or not os.path.exists(image_path):
                return {"cancelled": True}
            from PIL import Image
            im = Image.open(image_path)
            im.load()
            im = im.convert("RGB")
            im.thumbnail((240, 240))
            try:
                nn = max(2, min(int(n), 8))
            except Exception:
                nn = 6
            q = im.quantize(colors=nn, method=Image.MEDIANCUT)
            pal = q.getpalette()
            counts = sorted(q.getcolors() or [], reverse=True)   # (빈도, 팔레트 index)
            colors = []
            for _cnt, idx in counts:
                r, g, b = pal[idx * 3:idx * 3 + 3]
                colors.append("%02X%02X%02X" % (r, g, b))
            if not colors:
                return {"error": "색을 추출하지 못했습니다."}

            def _lum(h):
                r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                return 0.299 * r + 0.587 * g + 0.114 * b

            def _sat(h):
                r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                mx, mn = max(r, g, b), min(r, g, b)
                return 0 if mx == 0 else (mx - mn) / mx
            bg = max(colors, key=_lum)                    # 가장 밝은 색 → 배경
            ink = min(colors, key=_lum)                   # 가장 어두운 색 → 글자
            accent = max(colors, key=lambda h: _sat(h) * (0.5 + _lum(h) / 510))  # 선명한 색 → 강조
            return {"colors": colors, "accent": accent, "bg": bg, "ink": ink,
                    "file": os.path.basename(image_path)}
        except Exception as e:
            return {"error": f"색 추출 실패({type(e).__name__}): {e}"}

    def open_float(self):
        """항상 위에 뜨는 작은 메모/편집 창을 연다(플로팅 편집기)."""
        try:
            import webview
            if self._float_window is not None:
                return {"ok": True, "already": True}
            fhtml = os.path.join(HERE, "ui", "float.html")
            win = webview.create_window("메모 · 플로팅 편집기", fhtml,
                                        width=340, height=440, on_top=True, min_size=(240, 240))
            self._float_window = win

            def _closed():
                self._float_window = None
            try:
                win.events.closed += _closed
            except Exception:
                pass
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def add_theme_upload(self, name):
        """테마 JSON 파일을 골라 업로드·저장."""
        try:
            src = self.pick_file("theme")
            if not src:
                return {"cancelled": True}
            r = thememgr.add_from_file(name, src)
            self.theme = r["id"]
            return {"added": r, "options": thememgr.list_themes(), "current": self.theme}
        except Exception as e:
            return {"error": f"테마 파일이 올바르지 않습니다: {e}"}

    def add_theme_build(self, name, bg, accent, ink, band_fill=True, font="맑은 고딕"):
        """제작 창/디자인 설정 폼에서 받은 색·폰트로 테마 생성·저장."""
        try:
            r = thememgr.add_from_spec(name, bg, accent, ink, bool(band_fill), font, font)
            self.theme = r["id"]
            self._form_theme = None
            return {"added": r, "options": thememgr.list_themes(), "current": self.theme}
        except Exception as e:
            return {"error": str(e)}

    def delete_theme(self, theme_id):
        ok = thememgr.delete_theme(theme_id)
        if ok and self.theme == theme_id:
            self.theme = "gamba"
        return {"deleted": ok, "options": thememgr.list_themes(), "current": self.theme}

    # ── 발표자료: 풀 자동 ──────────────────────────
    def ppt_preview(self, doc_path, use_llm=False):
        if not doc_path or not os.path.exists(doc_path):
            return {"error": "문서를 선택하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            plan = ppt_plan_full(doc_path, use_llm=llm, brief=self._brief_text())
            engine = f"AI 구조화 · {os.getenv('OPENAI_MODEL', 'LLM')}" if llm else "규칙 기반 (즉시)"
            return {"title": plan.get("title"), "subtitle": plan.get("subtitle"), "engine": engine,
                    "outline": [{"title": s.get("title", ""), "type": s.get("type", "")} for s in plan.get("slides", [])]}
        except Exception as e:
            return {"error": str(e)}

    def ppt_make_full(self, doc_path, use_llm=False):
        try:
            llm = bool(use_llm) and self._import_can_llm()
            out = os.path.join(OUTPUT, _ts("deck_auto", "pptx"))
            ppt_generate_full(doc_path, out, theme=self.theme, use_llm=llm,
                              theme_config=self._theme_config(), brief=self._brief_text())
            engine = f"AI 구조화 · {os.getenv('OPENAI_MODEL', 'LLM')}" if llm else "규칙 기반"
            return {"out": out, "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    # ── 발표자료: 디자인 보조(스펙) ──────────────────
    def ppt_spec_preview(self, spec_text):
        try:
            plan = ppt_plan_spec(spec_text or "")
            out = []
            for s in plan.get("slides", []):
                extras = []
                if s.get("chart"):
                    extras.append(f"{s['chart']['kind']} 차트")
                if s.get("image"):
                    extras.append(f"이미지:{s['image']['query']}")
                out.append({"title": s.get("title", ""), "extras": ", ".join(extras)})
            return {"title": plan.get("title"), "outline": out}
        except Exception as e:
            return {"error": str(e)}

    def ppt_make_spec(self, spec_text):
        try:
            out = os.path.join(OUTPUT, _ts("deck_design", "pptx"))
            ppt_generate_spec(spec_text or "", out, image_fetch=image_search.fetch_image, theme=self.theme, theme_config=self._theme_config())
            return {"out": out, "images": image_search.available()}
        except Exception as e:
            return {"error": str(e)}

    # ── 발표자료: AI 대화형(질문하며 제작) ───────────
    def _chat_post(self, r):
        """sample/final이면 플랜을 렌더해 파일 경로·구성 요약을 붙인다."""
        try:
            if r.get("type") in ("sample", "final") and r.get("plan"):
                tag = "deck_sample" if r["type"] == "sample" else "deck_chat"
                out = os.path.join(OUTPUT, _ts(tag, "pptx"))
                render_plan(r["plan"], out, image_fetch=image_search.fetch_image, theme=self.theme, theme_config=self._theme_config())
                r["out"] = out
                r["outline"] = [s.get("title", "") for s in r["plan"].get("slides", [])]
        except Exception as e:
            r["render_error"] = str(e)
        return r

    def chat_start(self, brief):
        if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
            return {"type": "error", "error": "AI 대화형은 LLM이 필요합니다(.env에 키/엔드포인트)."}
        try:
            from app.ppt.agent_chat import PPTChatAgent
            self._chat = PPTChatAgent()
            return self._chat_post(self._chat.start(brief or "감바랩스 기술 소개 발표자료"))
        except Exception as e:
            return {"type": "error", "error": str(e)}

    def chat_reply(self, text):
        if not self._chat:
            return {"type": "error", "error": "대화가 시작되지 않았습니다."}
        try:
            return self._chat_post(self._chat.reply(text or ""))
        except Exception as e:
            return {"type": "error", "error": str(e)}

    # ── 발표자료: PPT 입력(적어둔 설명·위치 파악) ────
    def _import_can_llm(self):
        return bool(os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL"))

    def ppt_import_preview(self, pptx_path, use_llm=False):
        if not pptx_path or not os.path.exists(pptx_path):
            return {"error": "파워포인트 파일을 선택하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            plan = pptx_import.build_plan(pptx_path, use_llm=llm, brief=self._brief_text())
            out = []
            for s in plan.get("slides", []):
                extras = []
                if s.get("chart"):
                    extras.append(f"{s['chart']['kind']} 차트")
                if s.get("image"):
                    extras.append(f"이미지:{s['image'].get('query','')}")
                out.append({"title": s.get("title", ""), "extras": ", ".join(extras)})
            engine = f"AI 해석 · {os.getenv('OPENAI_MODEL', 'LLM')}" if llm else "규칙 기반 (즉시)"
            return {"title": plan.get("title"), "subtitle": plan.get("subtitle", ""), "outline": out, "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    def ppt_import_make(self, pptx_path, use_llm=False):
        if not pptx_path or not os.path.exists(pptx_path):
            return {"error": "파워포인트 파일을 선택하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            plan = pptx_import.build_plan(pptx_path, use_llm=llm, brief=self._brief_text())
            out = os.path.join(OUTPUT, _ts("deck_from_ppt", "pptx"))
            render_plan(plan, out, image_fetch=image_search.fetch_image, theme=self.theme, theme_config=self._theme_config())
            engine = f"AI 해석 · {os.getenv('OPENAI_MODEL', 'LLM')}" if llm else "규칙 기반"
            return {"out": out, "count": len(plan.get("slides", [])), "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    # ── 데이터: 대시보드 셀 수정(수식 보존) ───────────
    def excel_preview(self, request_text, xlsx_path):
        if not xlsx_path or not os.path.exists(xlsx_path):
            return {"error": "대상 엑셀을 선택하세요."}
        try:
            return {"updates": LLMExtractor().extract_updates(request_text or "", xlsx_path), "engine": self.llm_status()}
        except Exception as e:
            return {"error": str(e)}

    def excel_apply(self, request_text, xlsx_path, updates=None):
        try:
            if updates is None:
                updates = LLMExtractor().extract_updates(request_text or "", xlsx_path)
            if not updates:
                return {"error": "반영할 변경이 없습니다."}
            out = os.path.join(OUTPUT, _ts("updated_dashboard", "xlsx"))
            logs = ExcelUpdater().apply_updates(xlsx_path, updates, out)
            return {"logs": logs, "out": out}
        except Exception as e:
            return {"error": str(e)}

    # ── 데이터: Excel → LLM 분석/요약 ────────────────
    def excel_analyze(self, xlsx_path, question):
        if not xlsx_path or not os.path.exists(xlsx_path):
            return {"error": "분석할 엑셀을 선택하세요."}
        try:
            return excel_analysis.analyze(xlsx_path, question or None)
        except Exception as e:
            return {"error": str(e)}

    # ── 데이터: 실험/재무 기록 + 자동 차트 ────────────
    def exp_log_preview(self, xlsx_path, description, use_llm=False):
        """저장 전에, 자연어 설명이 어떤 한 행으로 기록될지 미리보기."""
        if not xlsx_path or not os.path.exists(xlsx_path):
            return {"error": "트래커 엑셀을 선택하세요."}
        if not (description or "").strip():
            return {"error": "기록할 결과 설명을 입력하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            return ExperimentLogger().preview_result(xlsx_path, description, use_llm=llm)
        except Exception as e:
            return {"error": str(e)}

    def exp_log(self, xlsx_path, description, use_llm=False, chart_mode="auto"):
        if not xlsx_path or not os.path.exists(xlsx_path):
            return {"error": "트래커 엑셀을 선택하세요."}
        if not (description or "").strip():
            return {"error": "기록할 결과 설명을 입력하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            out = os.path.join(OUTPUT, _ts("experiment_logged", "xlsx"))
            res = ExperimentLogger().append_result(xlsx_path, description, out, use_llm=llm,
                                                    chart_mode=(chart_mode or "auto"))
            return res
        except Exception as e:
            return {"error": str(e)}

    def create_tracker(self, headers_text, name=""):
        """사용자가 지정한 헤더로 새 트래커 xlsx를 만든다(저장 위치는 다이얼로그로 선택)."""
        import re as _re
        import webview
        cols = [h.strip() for h in _re.split(r"[,\n\t]", headers_text or "") if h.strip()]
        if not cols:
            return {"error": "헤더를 쉼표로 구분해 입력하세요. (예: 회차, 날짜, 정확도(%), 비고)"}
        default = ((name or "").strip() or "tracker") + ".xlsx"
        try:
            path = self._window.create_file_dialog(
                webview.SAVE_DIALOG, save_filename=default,
                file_types=("엑셀 (*.xlsx)", "All files (*.*)"))
        except Exception as e:
            return {"error": f"저장 위치 선택 실패: {e}"}
        if not path:
            return {"cancelled": True}
        if isinstance(path, (list, tuple)):
            path = path[0]
        path = str(path)
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            r = ExperimentLogger().create_tracker(path, cols, title=((name or "").strip() or "기록"))
            return r
        except Exception as e:
            return {"error": str(e)}

    def cancel_vectorize(self):
        """진행 중인 벡터 변환을 즉시 중지(프로세스 kill)."""
        p = self._vec_proc
        if p is not None and p.poll() is None:
            self._vec_cancelled = True
            try:
                p.kill()
            except Exception:
                pass
            return {"cancelled": True}
        return {"cancelled": False}

    def _remove_bg(self, im):
        """rembg(U²-Net)로 배경 제거 → 투명 배경 RGBA 반환. 세션은 최초 1회 로드·재사용."""
        from rembg import remove, new_session
        if self._rembg_session is None:
            self._rembg_session = new_session("u2netp")   # 경량 모델(빠름·소용량)
        return remove(im, session=self._rembg_session).convert("RGBA")

    # ── 벡터 변환: 비트맵 → SVG (visioncortex/vtracer) ──
    def vectorize(self, image_path, colormode="color", mode="spline", filter_speckle=4, remove_bg=False, quantize=0, max_dim=800):
        import subprocess
        if not image_path or not os.path.exists(image_path):
            return {"error": "이미지를 선택하세요."}
        try:
            import vtracer  # noqa: F401 설치 확인
        except Exception:
            return {"error": "vtracer 미설치. 터미널에서 'pip install vtracer' 후 다시 시도하세요."}
        try:
            in_size = os.path.getsize(image_path)
            try:
                fs = int(filter_speckle)
            except Exception:
                fs = 4
            # Pillow로 반드시 깨끗한 PNG(ASCII 경로)로 정규화 — vtracer는 원본을 넘기면
            # 형식에 따라 "No image file found" 패닉을 낸다. Pillow가 못 읽으면 명확히 안내.
            downscaled = False
            noisy = False
            tmp_dir = os.path.join(OUTPUT, "_images")
            os.makedirs(tmp_dir, exist_ok=True)
            src = os.path.join(tmp_dir, "_vsrc.png")
            try:
                from PIL import Image
                im = Image.open(image_path)
                im.load()
                # RGBA 유지: 투명 배경을 살려 vtracer가 투명 영역을 건너뛰게 함.
                # (RGB로 바꾸면 투명 부분이 검정으로 합성돼 배경이 시커멓게 나옴)
                im = im.convert("RGBA")
            except Exception as e:
                return {"error": f"이미지를 읽을 수 없습니다({type(e).__name__}). PNG·JPG로 저장한 파일로 다시 시도하세요."}

            w, h = im.size
            try:
                md = int(max_dim)
            except Exception:
                md = 800
            if md <= 0:
                MAX = min(max(w, h), 8000)    # '원본' = 파일 실제 해상도 그대로(안전상 8000 상한)
            else:
                MAX = min(max(md, 200), 8000)
            if max(w, h) > MAX:
                sc = MAX / max(w, h)
                im = im.resize((max(1, int(w * sc)), max(1, int(h * sc))))
                downscaled = True
            removed = False
            if remove_bg:   # 원할 때만: 배경 제거(투명) 후 벡터화 → 피사체만 깔끔히
                try:
                    im = self._remove_bg(im)
                    removed = True
                except Exception as e:
                    return {"error": f"배경 제거 실패({type(e).__name__}: {e}). 'pip install rembg[cpu]' 확인."}
            # 색 단순화(포스터화): 복잡한 사진·그림을 N색으로 줄여 깔끔한 벡터로 (알파 보존)
            try:
                n = int(quantize)
            except Exception:
                n = 0
            if n >= 2:
                try:
                    from PIL import Image as _Img
                    if im.mode == "RGBA":
                        alpha = im.getchannel("A")
                        rgb = im.convert("RGB").quantize(colors=n, method=_Img.MEDIANCUT).convert("RGB")
                        im = rgb.convert("RGBA")
                        im.putalpha(alpha)
                    else:
                        im = im.convert("RGB").quantize(colors=n, method=_Img.MEDIANCUT).convert("RGB")
                except Exception:
                    pass
            try:  # 색이 매우 많으면(사진) 속도·용량 위해 잡티 제거 강화
                if colormode == "color" and len(im.getcolors(maxcolors=20000) or [1] * 20001) > 6000:
                    noisy = True
                    fs = max(fs, 10)
            except Exception:
                pass
            try:
                im.save(src)
            except Exception as e:
                return {"error": f"임시 이미지 저장 실패({e})."}
            if not os.path.exists(src):
                return {"error": "임시 이미지 생성에 실패했습니다."}

            out = os.path.join(OUTPUT, _ts("vector", "svg"))  # 출력은 ASCII 고정명(경로 문제 방지)
            cprec = 8   # 색 정밀도 최대 — 원본에 최대한 가깝게(트레이스는 원리상 포스터화됨)
            runner = os.path.join(HERE, "ppt", "_vtrace_run.py")
            # 별도 프로세스(시간제한 없음) — 오래 걸리면 사용자가 '중지' 버튼으로 취소
            self._vec_cancelled = False
            proc = subprocess.Popen(
                [sys.executable, runner, src, out, str(colormode), str(mode), str(fs), str(cprec)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self._vec_proc = proc
            try:
                _out_t, err_t = proc.communicate()   # 완료 또는 kill될 때까지 대기(무한 아님: 사용자 취소 가능)
            finally:
                self._vec_proc = None
            if self._vec_cancelled:
                self._vec_cancelled = False
                if os.path.exists(out):
                    try:
                        os.remove(out)
                    except Exception:
                        pass
                return {"cancelled": True}
            if proc.returncode != 0 or not os.path.exists(out):
                return {"error": f"변환 실패: {(err_t or '')[-300:]}"}

            out_size = os.path.getsize(out)
            svg, preview = "", False
            if out_size <= 180_000:          # 큰 SVG 인라인 렌더는 webview를 멈추므로 상한
                try:
                    with open(out, "r", encoding="utf-8") as f:
                        svg = f.read()
                    preview = True
                except Exception:
                    pass
            return {"out": out, "svg": svg, "preview": preview, "downscaled": downscaled,
                    "noisy": noisy, "removed_bg": removed, "dims": [im.size[0], im.size[1]],
                    "orig_dims": [w, h], "in_size": in_size, "out_size": out_size}
        except Exception as e:
            return {"error": str(e)}
