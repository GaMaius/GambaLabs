# -*- coding: utf-8 -*-
"""vtracer 변환 + 자동 튜닝을 별도 프로세스에서 실행.

호출부(app/api.py)가 프로세스를 kill 하면 통째로 취소되므로, 후보 여러 개를
돌리는 autotune도 안전하게 중단된다.

사용법
  신규(권장): python _vtrace_run.py <job.json>
  구버전 호환: python _vtrace_run.py <src> <out> <colormode> <mode> <speckle> <cprec> [hierarchical]

job.json
{
  "out": "결과 SVG 경로",
  "ref": "원본 이미지 경로(채점 기준, 없으면 채점 생략)",
  "metric": "ink" | "color",
  "workdir": "임시 파일 폴더",
  "candidates": [ {"label": "기본", "src": "전처리된 png", "params": { vtracer kwargs }} ]
}
stdout에 JSON 결과 한 줄을 출력한다.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")))

import vtracer  # noqa: E402

# 점수 동률 판정 폭 — 이보다 작은 차이는 눈으로 구분되지 않는다.
EPS = 0.003


def _legacy():
    _, src, out, colormode, mode, speckle, cprec = sys.argv[:7]
    hierarchical = sys.argv[7] if len(sys.argv) > 7 else "stacked"
    spk = int(speckle)
    vtracer.convert_image_to_svg_py(
        src, out,
        colormode=colormode if colormode in ("color", "binary") else "color",
        hierarchical=hierarchical if hierarchical in ("stacked", "cutout") else "stacked",
        mode=mode if mode in ("spline", "polygon", "pixel") else "spline",
        filter_speckle=spk,
        color_precision=int(cprec),
        corner_threshold=60,
        length_threshold=4.0,
        path_precision=3,
    )
    print("OK")


def _job(job_path):
    with open(job_path, "r", encoding="utf-8") as f:
        job = json.load(f)

    out = job["out"]
    ref = job.get("ref")
    metric = job.get("metric", "ink")
    workdir = job.get("workdir") or os.path.dirname(out)
    cands = job.get("candidates") or []
    if not cands:
        raise SystemExit("no candidates")

    scorer = None
    if ref and os.path.exists(ref) and job.get("score", True):
        try:
            from src.vector.quality import score_svg, node_available
            if node_available():
                scorer = score_svg
        except Exception:
            scorer = None

    tried, best = [], None
    for i, c in enumerate(cands):
        svg_i = os.path.join(workdir, f"_cand{i}.svg")
        try:
            vtracer.convert_image_to_svg_py(c["src"], svg_i, **c["params"])
        except Exception as e:
            tried.append({"label": c.get("label", str(i)), "error": f"{type(e).__name__}: {e}"})
            continue

        rec = {"label": c.get("label", str(i)), "svg": svg_i,
               "size": os.path.getsize(svg_i), "params": c["params"]}
        if scorer is not None:
            try:
                m = scorer(svg_i, ref, metric, workdir=workdir)
                if m:
                    rec.update(m)
            except Exception:
                pass
        tried.append(rec)

        # 점수가 없으면(채점 불가) 첫 후보 = 프리셋 기본값을 그대로 채택
        if best is None:
            best = rec
        elif "score" in rec and "score" not in best:
            best = rec
        elif "score" in rec and "score" in best:
            if rec["score"] > best["score"] + EPS:
                best = rec
            elif rec["score"] > best["score"] - EPS and rec["size"] < best["size"] * 0.7:
                # 품질이 사실상 동률이면 파일이 작은 쪽 (PPT 삽입 시 용량이 곧 성능)
                best = rec

    if best is None:
        raise SystemExit("all candidates failed: " + json.dumps(tried, ensure_ascii=False))

    shutil.move(best["svg"], out)
    # 좌표 표기 축소(무손실 — 렌더 결과 바이트 동일)
    try:
        from src.vector.svgmin import minify_file
        _b, a = minify_file(out)
        best["size"] = a
    except Exception:
        pass
    for r in tried:
        p = r.pop("svg", None)
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    best.pop("svg", None)

    print(json.dumps({"ok": True, "best": best, "tried": tried}, ensure_ascii=False))


def run_job(job_path: str) -> int:
    """job.json 하나를 처리한다. 빌드본에서 exe가 자기 자신을 작업자로 부를 때도 이 함수를 쓴다."""
    try:
        _job(job_path)
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].lower().endswith(".json"):
        raise SystemExit(run_job(sys.argv[1]))
    else:
        _legacy()
