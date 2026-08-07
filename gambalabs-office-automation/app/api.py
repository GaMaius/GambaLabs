# -*- coding: utf-8 -*-
"""pywebview JS↔Python 브리지 (v2).

원칙: LLM/파서는 '무엇을' 판단, 실제 파일 수술(Excel 셀·PPT 렌더·차트)은 결정적 코드.
파일에 쓰기 전 UI에서 '확인' 게이트를 거친다.
"""
import os
import sys
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if os.path.dirname(HERE) not in sys.path:
    sys.path.insert(0, os.path.dirname(HERE))

from src.common import paths

from src.common.llm_client import get_llm_client_and_model, get_llm_provider, list_available_models
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

OUTPUT = paths.OUTPUT_DIR
paths.ensure_dirs()

def _ts(name, ext, sub_dir=""):
    """타임스탬프 파일명 생성 및 서브 폴더 지정"""
    out_dir = os.path.join(OUTPUT, sub_dir) if sub_dir else OUTPUT
    os.makedirs(out_dir, exist_ok=True)
    return os.path.join(out_dir, f"{name}_{datetime.datetime.now().strftime('%m%d_%H%M%S')}.{ext}")


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

    def project_dir(self):
        """실험 로거(gamba_log) 스니펫에 넣을 작업 폴더 경로."""
        return paths.DATA_DIR

    def path_info(self):
        """진단용 — 어느 폴더를 보고 있는지, node가 준비됐는지."""
        return paths.describe()

    # ── API 키 설정(앱 안에서 .env 편집) ─────────────
    def settings_get(self):
        from src.common import envfile
        d = envfile.read_all()
        d["_provider"] = get_llm_provider()
        d["_node_ready"] = paths.node_ready()
        return d

    def settings_save(self, values):
        """빈 칸은 '변경 없음', "-"는 삭제. 저장 즉시 적용된다(재시작 불필요)."""
        from src.common import envfile
        try:
            r = envfile.save(values or {})
            r["status"] = self.llm_status()
            return r
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def settings_test_image(self):
        """스톡 이미지 검색을 실제로 한 번 해 본다. 키가 없어도 Openverse로 되면 성공이다."""
        try:
            p = image_search.fetch_image("blue abstract texture", mode="region")
            if p and os.path.exists(p):
                return {"ok": True, "source": image_search.source_label(), "path": p}
            return {"ok": False, "error": "사진을 받지 못했습니다. 인터넷 연결을 확인하세요."}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    def settings_test(self):
        """현재 키로 실제 한 번 호출해 본다. 인수인계 받은 사람이 바로 확인할 수 있게."""
        try:
            client, model = get_llm_client_and_model()
            r = client.chat.completions.create(
                model=model, max_tokens=5,
                messages=[{"role": "user", "content": "ping"}])
            txt = (r.choices[0].message.content or "").strip()
            return {"ok": True, "model": model, "reply": txt[:40] or "(빈 응답)"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}

    def open_folder(self, path):
        try:
            os.startfile(path if os.path.isdir(path) else os.path.dirname(path))
        except Exception:
            pass
        return True

    def llm_status(self):
        # 키가 없으면 모델 이름을 보여줘 봐야 소용없다. 무엇을 해야 하는지 알려 준다.
        if not self._has_key():
            return "키 미설정 — 좌측 '🔑 API 키 설정'에서 입력하세요"
        info = list_available_models()
        return f"{info['label']} ({info['current']})"

    @staticmethod
    def _has_key():
        p = get_llm_provider()
        if p == "ollama":
            return True                      # 로컬 실행이라 키가 필요 없다
        if p == "groq":
            return bool(os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY2"))
        return bool(os.getenv("OPENAI_API_KEY"))

    def img_status(self):
        try:
            return image_search.source_label()
        except Exception:
            return "스톡 검색 ON"

    def get_llm(self):
        """현재 프로바이더/모델 + 선택 가능한 모델 목록 (Groq GPT OSS / Ollama / OpenAI)."""
        return list_available_models()

    def set_provider(self, provider_name):
        if provider_name in ("groq", "ollama", "openai"):
            os.environ["LLM_PROVIDER"] = provider_name
            self._chat = None
        return list_available_models()

    def set_model(self, name):
        if name:
            provider = get_llm_provider()
            if provider == "groq":
                # 폐기된 모델을 고르면 400 model_decommissioned가 나므로 살아 있는 것만 받는다.
                from src.common.llm_client import fetch_groq_models
                live = fetch_groq_models()
                if live and name not in live:
                    return dict(list_available_models(),
                                error=f"'{name}'은(는) Groq에서 더 이상 제공되지 않습니다. 목록을 갱신했습니다.")
                os.environ["GROQ_MODEL"] = name
            os.environ["OPENAI_MODEL"] = name
            self._chat = None  # 진행 중 대화는 새 모델로 재시작
        return list_available_models()

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

    def set_form_theme(self, bg, accent, ink, band_fill=True, font="맑은 고딕", gradient=False,
                       ratio="16:9"):
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
            # 비율은 예전엔 폼에서 받기만 하고 어디에도 쓰이지 않았다(죽은 항목).
            # 테마 설정에 실어 렌더까지 전달한다.
            cfg["ratio"] = ratio if ratio in ("16:9", "4:3") else "16:9"
            self._form_theme = cfg
            self.theme = "__form"
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    # ── 디자인 브리프(목적·자유 디렉션·참고자료) ─────────
    # 폼의 선택값 → 생성 프롬프트에 넣을 구체적 지시문.
    # 선택지가 결과를 실제로 바꾸게 하려면 '무엇을 다르게 할지'를 문장으로 못박아야 한다.
    _USAGE_RULE = {
        "talk": "이 덱은 발표자가 말로 설명하며 띄우는 자료다. 슬라이드 글은 키워드와 짧은 구로 줄이고, "
                "한 슬라이드에 핵심 메시지 하나만 둔다. 문장을 그대로 읽게 만들지 마라.",
        "read": "이 덱은 발표자 없이 읽는 배포 자료다. 각 항목을 완결된 문장으로 쓰고, 왜 그런지 근거를 "
                "한 줄씩 덧붙여 혼자 읽어도 이해되게 하라.",
        "draft": "이 덱은 내부 검토용 초안이다. 꾸미기보다 내용 전달이 우선이다. 항목을 빠짐없이 담고 "
                 "구조를 단순하게 유지하라.",
    }
    _LENGTH_RULE = {
        "auto": "",
        "short": "표지 포함 5장 내외로 압축하라. 비슷한 내용은 한 장으로 합쳐라.",
        "mid": "표지 포함 8~10장으로 구성하라.",
        "long": "표지 포함 14장 이상으로 충분히 펼쳐라. 각 주제를 슬라이드 하나씩 배정하라.",
    }
    _PHOTO_RULE = {
        "none": "사진을 쓰지 마라. 도형·색·타이포그래피만으로 구성하라(스톡 이미지 검색 금지).",
        "auto": "사진은 내용에 꼭 필요할 때만 쓰고, 그 외에는 도형과 여백으로 정리하라.",
        "rich": "표지와 주요 슬라이드에 사진을 적극적으로 쓰되, 글자가 얹히는 곳은 차분한 배경 이미지를 골라라.",
    }

    def set_design_brief(self, purpose="", direction="", refs=None,
                         usage="talk", length="auto", photos="auto"):
        """폼 입력을 저장. 생성 시 LLM 프롬프트에 주입된다.

        usage/length/photos는 '색·폰트'와 달리 덱의 내용 구성을 바꾸는 값이다.
        (예전 폼은 색·폰트만 다뤄서 무엇을 골라도 결과가 비슷했다)
        """
        if isinstance(refs, str):
            refs = [refs]
        refs = [r for r in (refs or []) if r and os.path.exists(r)]
        self._brief = {"purpose": (purpose or "").strip(),
                       "direction": (direction or "").strip(),
                       "refs": refs,
                       "usage": usage if usage in self._USAGE_RULE else "talk",
                       "length": length if length in self._LENGTH_RULE else "auto",
                       "photos": photos if photos in self._PHOTO_RULE else "auto"}
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
            parts.append(f"[발표 목적·청중]\n{b['purpose']}")

        rules = [self._USAGE_RULE.get(b.get("usage", "talk"), ""),
                 self._LENGTH_RULE.get(b.get("length", "auto"), ""),
                 self._PHOTO_RULE.get(b.get("photos", "auto"), "")]
        rules = [r for r in rules if r]
        if rules:
            parts.append("[구성 지침 — 반드시 지켜라]\n- " + "\n- ".join(rules))

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

    def gen_ppt_prompt(self, opts=None):
        """디자인 설정/테마/내용으로, 범용 LLM(GPT·Claude·Gemini 등)에 붙여넣어 발표자료를
        만들게 하는 자립형 프롬프트를 조립해 반환한다(복사용)."""
        o = opts or {}

        def g(k, d=""):
            v = o.get(k)
            return (str(v).strip() if v is not None else d)

        topic = g("topic")
        purpose = g("purpose")
        direction = g("direction")
        ratio = g("ratio", "16:9")
        bg_tone = g("bg_tone", "light")
        accent = g("accent", "0038A3").lstrip("#").upper()
        ink = g("ink", "1A1A1A").lstrip("#").upper()
        font = g("font", "맑은 고딕")
        gradient = bool(o.get("gradient"))
        theme_label = g("theme_label")
        output = g("output", "plan")           # plan | code | both
        strict = bool(o.get("strict"))
        refs = [r for r in (o.get("refs") or []) if r and os.path.exists(r)]

        bg_desc = ("어두운 배경" if bg_tone == "dark" else "밝은 배경") + (" · 은은한 그라데이션" if gradient else " · 단색")

        ref_block = ""
        for i, r in enumerate(refs, 1):
            t = self._load_ref_text(r)
            name = os.path.basename(r)
            ref_block += (f"\n[참고자료 {i}: {name}]\n{t}\n" if t else f"\n[참고자료 {i}: {name}] (텍스트 없음 — 디자인 참고용)\n")
        if not ref_block:
            ref_block = "\n(없음)\n"

        rule_mode = (
            "- 사용자가 준 구조를 존중하되, 각 슬라이드에 가장 알맞은 레이아웃을 스스로 '설계'하라. 자유도를 살려라."
            if not strict else
            "- 정해진 규칙을 엄격히 지켜라. 임의로 항목을 추가·과장하지 말고, 준 내용에 충실하라."
        )

        out_blocks = {
            "plan": (
                "[출력 형식]\n"
                "슬라이드별로 아래 표로 제시하라. 그리고 표지 제목 문장과 마무리 문구도 제안하라.\n"
                "| # | 제목 | 레이아웃 유형 | 핵심 내용(짧은 불릿) | 디자인 노트(색·강조·시각요소) |"
            ),
            "code": (
                "[출력 형식]\n"
                f"이 덱을 생성하는 완전한 코드를 작성하라. pptxgenjs(Node.js) 또는 python-pptx 중 하나로, 비율 {ratio}"
                "(16:9면 13.333×7.5인치), 위 색·폰트를 그대로 적용. 그대로 실행하면 .pptx가 나오도록 자립형으로."
            ),
        }
        out_blocks["both"] = out_blocks["plan"] + "\n\n그다음, " + out_blocks["code"]
        out_block = out_blocks.get(output, out_blocks["plan"])

        prompt = f"""너는 한국어 발표자료(PPT)를 설계하는 전문 디자이너다. 아래 [내용]과 [디자인 설정]에 맞춰 완성도 높은 슬라이드 덱을 설계하라.

[발표 주제·내용]
{topic or "※ 여기에 발표 주제 또는 원문(문서 텍스트)을 붙여넣으세요."}

[목적·대상·톤]
{purpose or "(미지정)"}

[제작자 추가 디렉션 — 최대한 반영]
{direction or "(없음)"}

[디자인 설정]
- 비율: {ratio}
- 배경: {bg_desc}
- 강조색(포인트): #{accent}
- 글자색: #{ink}
- 폰트: {font}
- 테마: {theme_label or "지정 색 기반"}

[참고자료 — 사실 근거로만 사용, 그대로 복붙 금지]{ref_block}
[슬라이드 설계 규칙]
- 표지·목차·본문·마무리를 모두 갖춘다. 표지는 전체를 관통하는 한 문장 제목 + 어울리는 이미지.
- 텍스트를 최소화한다. 슬라이드는 읽는 문서가 아니라 '보는' 자료다.
- 레이아웃을 내용에 맞게 골라 설계: text(불릿 요약) · cards(핵심 항목 2~4개) · table(비교·수치) · metrics(큰 숫자 지표 카드) · compare(2열 비교) · chart(막대/선/원형, 필요시 추세선).
- 본문 제목·소제목은 세로로 전체의 1/6 이하만 차지. 모든 페이지의 외곽 여백을 일정하게 유지. 도형 안 텍스트는 넘치지 않게 여백을 둔다.
- 색은 위 강조색·글자색을 일관되게 쓰고, 강조가 필요한 수치·키워드에만 포인트색을 쓴다.
{rule_mode}

{out_block}

설명 없이 결과물만 출력하라. 한국어로."""
        return {"prompt": prompt}

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
            from app.ppt import design_policy
            mode = "AI 자유설계" if (llm and not design_policy.is_strict()) else "AI 구조화"
            engine = f"{mode} · {get_llm_client_and_model()[1]}" if llm else "규칙 기반 (즉시)"
            return {"title": plan.get("title"), "subtitle": plan.get("subtitle"), "engine": engine,
                    "outline": [{"title": s.get("title", ""), "type": s.get("type", "")} for s in plan.get("slides", [])]}
        except Exception as e:
            return {"error": str(e)}

    def ppt_make_full(self, doc_path, use_llm=False):
        try:
            from app.ppt.ppt_engine import generate as ppt_generate_full
            out = _ts("deck_auto", "pptx", "ppt/auto")
            ppt_generate_full(doc_path, out, theme=self.theme, use_llm=use_llm, theme_config=self._theme_config(), brief=self._brief_text())
            from app.ppt import design_policy
            llm = use_llm and self._import_can_llm()
            mode = "AI 자유설계" if (llm and not design_policy.is_strict()) else "AI 구조화"
            engine = f"{mode} · {get_llm_client_and_model()[1]}" if llm else "규칙 기반"
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
            out = _ts("deck_design", "pptx", "ppt/spec")
            from app.ppt import design_policy
            if self._import_can_llm() and not design_policy.is_strict():
                from app.ppt.freeform_engine import generate_freeform
                generate_freeform(spec_text or "", out, theme=self.theme, theme_config=self._theme_config(), brief=self._brief_text())
                return {"out": out, "images": []}
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
                out = _ts(tag, "pptx", "ppt/chat")
                
                from app.ppt import design_policy
                if self._import_can_llm() and not design_policy.is_strict():
                    from app.ppt.freeform_engine import generate_freeform
                    plan_text = json.dumps(r["plan"], ensure_ascii=False, indent=2)
                    generate_freeform(plan_text, out, theme=self.theme, theme_config=self._theme_config(), brief=self._brief_text())
                    r["out"] = out
                    r["outline"] = [s.get("title", "") for s in r["plan"].get("slides", [])]
                    return r

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
            engine = f"AI 해석 · {get_llm_client_and_model()[1]}" if llm else "규칙 기반 (즉시)"
            return {"title": plan.get("title"), "subtitle": plan.get("subtitle", ""), "outline": out, "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    def ppt_import_make(self, pptx_path, use_llm=False):
        if not pptx_path or not os.path.exists(pptx_path):
            return {"error": "파워포인트 파일을 선택하세요."}
        try:
            llm = bool(use_llm) and self._import_can_llm()
            out = os.path.join(OUTPUT, _ts("deck_from_ppt", "pptx", "ppt/import"))
            from app.ppt import design_policy
            # 강한 모델이면 freeform 엔진(슬라이드 텍스트를 문서로 전달) 시도
            if llm and not design_policy.is_strict():
                from app.ppt.freeform_engine import generate_freeform_from_slides
                # 텍스트만 뽑으면 사용자가 넣어둔 사진이 사라진다 → 그림도 함께 추출해 넘긴다.
                media_dir = os.path.join(OUTPUT, "_images", "import_media")
                rich = pptx_import.extract_slides_rich(pptx_path, media_dir)
                slides_text = "\n\n".join(
                    f"[슬라이드 {i+1}]\n" + "\n".join(sl["texts"])
                    for i, sl in enumerate(rich) if sl["texts"])
                user_images = {i + 1: sl["images"] for i, sl in enumerate(rich) if sl["images"]}
                generate_freeform_from_slides(
                    slides_text, out, theme=self.theme,
                    theme_config=self._theme_config(), brief=self._brief_text(),
                    user_images=user_images)
                engine = f"AI 자유설계 · {get_llm_client_and_model()[1]}"
                return {"out": out, "engine": engine}
            
            # 폴백: 기존 JSON Plan + render_deck.js
            plan = pptx_import.build_plan(pptx_path, use_llm=llm, brief=self._brief_text())
            render_plan(plan, out, image_fetch=image_search.fetch_image, theme=self.theme, theme_config=self._theme_config())
            engine = f"AI 해석 · {get_llm_client_and_model()[1]}" if llm else "규칙 기반"
            return {"out": out, "count": len(plan.get("slides", [])), "engine": engine}
        except Exception as e:
            return {"error": str(e)}

    # ── 데이터: 자동 영수증 작성 ───────────────────────
    def receipt_template(self):
        """동봉된 영수증 표준 양식 경로. 예전엔 프런트가 프로젝트 **바깥**
        (../planing/…)을 문자열로 조립해서, 폴더째 전달하면 바로 깨졌다."""
        for name in ("엑셀 간이영수증 표준 양식 v2.0.xlsx", "receipt_template.xlsx"):
            p = os.path.join(paths.RES_DIR, "assets", name)
            if os.path.exists(p):
                return p
        return ""

    def excel_make_receipt(self, text, template_path):
        if not text:
            return {"error": "영수증 내용을 입력하세요."}
        if not template_path or not os.path.exists(template_path):
            return {"error": "영수증 표준 엑셀 양식을 선택하세요."}
        try:
            from src.excel.receipt_engine import generate_receipt
            out = _ts("receipt", "xlsx", "excel/receipt")
            result = generate_receipt(text, template_path, out)
            return result
        except Exception as e:
            return {"error": str(e)}

    # ── 데이터: 실험 기록 ───────────────────────────
    def tracker_analyze(self, xlsx_path, question):
        if not xlsx_path or not os.path.exists(xlsx_path):
            return {"error": "분석할 트래커 엑셀을 선택하세요."}
        try:
            from src.excel import excel_analysis
            return excel_analysis.analyze(xlsx_path, question or None)
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

    # ── 벡터 변환: 비트맵 → SVG (visioncortex/vtracer + VectorAutotuner) ──
    def vectorize(self, image_path, colormode="auto", mode="auto", filter_speckle="auto",
                  remove_bg=False, quantize="auto", max_dim=0, preset="auto", autotune=False):
        """비트맵 → SVG.

        preset: auto | lineart | diagram | logo | photo | custom
          - auto  : 이미지 분석으로 유형 자동 판별
          - custom: UI에서 고른 값(colormode/mode/filter_speckle/quantize)을 그대로 사용
        autotune: 후보 파라미터를 여러 개 돌려 원본과 가장 닮은 결과를 채택(느림, 정밀).
        max_dim: 트레이스 해상도 상한(0=유형별 기본값)
        """
        import json
        import subprocess
        if not image_path or not os.path.exists(image_path):
            return {"error": "이미지를 선택하세요."}
        try:
            import vtracer  # noqa: F401 설치 확인
        except Exception:
            return {"error": "vtracer 미설치. 터미널에서 'pip install vtracer' 후 다시 시도하세요."}
        try:
            from src.vector.vector_autotune import VectorAutotuner, METRIC, PRESETS
        except Exception as e:
            return {"error": f"벡터 엔진 로드 실패({type(e).__name__}: {e}). 'pip install opencv-python scikit-image' 확인."}

        tmp_dir = os.path.join(OUTPUT, "_images")
        os.makedirs(tmp_dir, exist_ok=True)

        try:
            in_size = os.path.getsize(image_path)

            # ── 1) 분석 ──
            try:
                tuner = VectorAutotuner(image_path)
            except Exception as e:
                return {"error": f"이미지를 읽을 수 없습니다({type(e).__name__}). PNG·JPG로 저장한 파일로 다시 시도하세요."}

            prof = tuner.profile()
            if preset in PRESETS:
                category = preset
            elif preset == "custom":
                category = tuner.classify()
            else:
                category = tuner.classify()

            # ── 2) 배경 제거(선택) — 이후 단계는 제거된 이미지를 원본으로 취급 ──
            removed = False
            work_path = image_path
            if remove_bg:
                try:
                    from src.vector.vector_autotune import defringe_cutout
                    cut = defringe_cutout(self._remove_bg(tuner.im_pil))
                    work_path = os.path.join(tmp_dir, "_vsrc_nobg.png")
                    cut.save(work_path)
                    tuner = VectorAutotuner(work_path)
                    prof = tuner.profile()
                    removed = True
                except Exception as e:
                    return {"error": f"배경 제거 실패({type(e).__name__}: {e}). 'pip install rembg[cpu]' 확인."}

            # ── 3) 후보 파라미터 ──
            overrides = {}
            q_override = None
            if preset == "custom":
                if colormode in ("color", "binary"):
                    overrides["colormode"] = colormode
                if mode in ("spline", "polygon", "pixel"):
                    overrides["mode"] = mode
                try:
                    overrides["filter_speckle"] = int(filter_speckle)
                except Exception:
                    pass
                try:
                    q_override = int(quantize)
                except Exception:
                    q_override = None

            try:
                cap = int(max_dim)
            except Exception:
                cap = 0

            cands = tuner.build_candidates(category, autotune=bool(autotune),
                                           overrides=overrides, cap=cap, quantize=q_override,
                                           max_tries=4 if autotune else 1)

            # ── 4) 후보별 전처리 이미지 저장 ──
            job_cands, dims = [], None
            for i, c in enumerate(cands):
                try:
                    im = tuner.preprocess(category, upscale=c["upscale"], cap=cap, quantize=c["quantize"])
                except Exception as e:
                    return {"error": f"전처리 실패({type(e).__name__}: {e})"}
                p = os.path.join(tmp_dir, f"_vsrc{i}.png")
                im.save(p)
                if dims is None:
                    dims = list(im.size)
                job_cands.append({"label": c["label"], "src": p, "params": c["params"]})

            out = _ts("vector", "svg", "vector")  # 출력은 ASCII 고정명(경로 문제 방지)
            job = {"out": out, "ref": work_path, "metric": METRIC.get(category, "color"),
                   "workdir": tmp_dir, "candidates": job_cands, "score": True}
            job_path = os.path.join(tmp_dir, "_vjob.json")
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job, f, ensure_ascii=False)

            # ── 5) 별도 프로세스 실행(시간제한 없음 — '중지' 버튼으로 취소) ──
            # 소스 실행이면 python으로 러너 스크립트를, 빌드본이면 exe가 자기 자신을
            # 작업자 모드로 재실행한다(빌드본에는 python.exe가 없다).
            if paths.IS_FROZEN:
                cmd = [sys.executable, "--vtrace", job_path]
            else:
                cmd = [sys.executable, os.path.join(HERE, "ppt", "_vtrace_run.py"), job_path]
            self._vec_cancelled = False
            # 파이프는 UTF-8 고정 — 한글 후보 라벨이 cp949 콘솔 인코딩에 깨지지 않도록.
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            proc = subprocess.Popen(cmd,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace", env=env)
            self._vec_proc = proc
            try:
                out_t, err_t = proc.communicate()
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
                return {"error": f"변환 실패: {(err_t or out_t or '')[-300:]}"}

            report = {}
            for line in (out_t or "").splitlines():
                line = line.strip()
                if line.startswith("{"):
                    try:
                        report = json.loads(line)
                    except Exception:
                        pass
            best = report.get("best", {})

            out_size = os.path.getsize(out)
            svg, preview, preview_png = "", False, ""
            if out_size <= 180_000:          # 큰 SVG 인라인 렌더는 webview를 멈추므로 상한
                try:
                    with open(out, "r", encoding="utf-8") as f:
                        svg = f.read()
                    preview = True
                except Exception:
                    pass
            else:
                # 용량이 크면 결과 SVG를 PNG로 렌더해 미리보기로 보여준다(미리보기 없음 방지).
                try:
                    import base64
                    from src.vector.quality import rasterize, node_available
                    if node_available():
                        pv = os.path.join(tmp_dir, "_vpreview.png")
                        if rasterize(out, pv, 760, timeout=90):
                            with open(pv, "rb") as f:
                                preview_png = "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
                except Exception:
                    pass

            # 사진은 원리상 벡터화가 손해다(원본보다 커지고 화질은 떨어짐). 숨기지 말고 알린다.
            warn = ""
            if category == "photo" and out_size > in_size * 2:
                warn = ("사진은 벡터로 바꾸면 원본보다 파일이 커지고 디테일은 오히려 떨어집니다. "
                        "발표자료에는 원본 이미지를 그대로 쓰는 편이 낫습니다. "
                        "용량을 줄이려면 '정밀 자동 튜닝'을 켜거나 수동 설정에서 색 단순화를 쓰세요.")

            return {
                "out": out, "svg": svg, "preview": preview, "preview_png": preview_png,
                "warn": warn,
                "removed_bg": removed,
                "dims": dims, "orig_dims": [prof["w"], prof["h"]],
                "upscaled": bool(dims and dims[0] > prof["w"]),
                "in_size": in_size, "out_size": out_size,
                "category": category,
                "params": best.get("params", {}),
                "variant": best.get("label"),
                # 채점 불가(node/resvg 없음)면 None — UI에서 표시하지 않는다.
                "ssim": (round(best["ssim"] * 100, 1) if best.get("ssim") is not None else None),
                # 획 보존은 선/글자가 핵심인 유형에서만 의미가 있다. 사진에 붙이면 오해를 부른다.
                "ink_f1": (round(best["ink_f1"] * 100, 1)
                           if (METRIC.get(category) == "ink" and best.get("ink_f1") is not None) else None),
                "tried": [{"label": t.get("label"), "ssim": t.get("ssim"),
                           "ink_f1": t.get("ink_f1"), "size": t.get("size")}
                          for t in report.get("tried", [])],
            }
        except Exception as e:
            return {"error": str(e)}
