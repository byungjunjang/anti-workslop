# -*- coding: utf-8 -*-
"""
check_style.py — 초고(.md/.txt)가 키트의 targets.json 을 만족하는지 검사한다 (읽기 전용).

  python -X utf8 check_style.py --kit styleguides/<slug> draft.md
  python -X utf8 check_style.py --kit … a.md b.md --summary
  python -X utf8 check_style.py --kit … draft.md --json
  python -X utf8 check_style.py --kit … draft.md --strict         # hard 실패 시 exit 1
  python -X utf8 check_style.py --kit … draft.md --subset counts  # 횟수·불리언 규칙만 (짧은 글, §9 '후' 문장)
  python -X utf8 check_style.py --targets T.json --profile P.json draft.md   # 키트 없이
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import force_utf8_stdout, load_kit, read_json  # noqa: E402
from metrics import analyze_blocks, blocks_from_markdown  # noqa: E402

COUNT_LIKE = {"count"}   # --subset counts: 글 전체 구조(불리언)·비율을 빼고 횟수 규칙만 (짧은 글, 변환 예시 문장)


def derive(m: dict) -> dict:
    d = dict(m)
    d["sensory_total"] = sum(m.get("sensory", {}).values())
    d["banned_total"] = sum(m.get("banned", {}).values())
    d["nonpref_total"] = sum(m.get("nonpreferred_spelling", {}).values())
    d["opening_ok"] = m.get("opening_type") in ("이력/인사", "질문", "정의")
    return d


def evaluate(m: dict, rules: list[dict], subset: str = "all") -> list[dict]:
    d = derive(m)
    out = []
    for r in rules:
        if subset == "counts" and r.get("kind") not in COUNT_LIKE:
            continue
        v = d.get(r["metric"])
        ok = v is not None
        if ok:
            if "min" in r and v < r["min"]: ok = False
            if "max" in r and v > r["max"]: ok = False
            if "equals" in r and v != r["equals"]: ok = False
            if "in" in r and v not in r["in"]: ok = False
        shown = ("예" if v else "아니오") if isinstance(v, bool) else v
        out.append({"label": r["label"], "metric": r["metric"], "value": shown, "target": r.get("target_text", ""),
                    "level": r.get("level", "soft"), "ok": ok})
    return out


def fmt_table(name: str, rows: list[dict], m: dict) -> str:
    lines = [f"## {name}", "",
             f"문장 {m['n_sentences']} / 문단 {m['n_paragraphs']} / 표제 {m['n_headings']} / 목록 {m['n_list_items']} / 표 {m.get('n_tables', 0)}",
             f"시작: [{m['opening_type']}] {m['opening_sentence'][:80]}",
             f"끝:   …{m['closing_sentence'][-80:]}", "",
             "| 항목 | 값 | 목표 | 판정 |", "|---|---|---|---|"]
    for r in rows:
        mark = "PASS" if r["ok"] else ("FAIL" if r["level"] == "hard" else "warn")
        lines.append(f"| {r['label']} | {r['value']} | {r['target']} | {mark} |")
    hard_fail = sum(1 for r in rows if not r["ok"] and r["level"] == "hard")
    soft_fail = sum(1 for r in rows if not r["ok"] and r["level"] != "hard")
    lines += ["", f"hard 실패 {hard_fail} / soft 경고 {soft_fail} / 전체 {len(rows)}"]
    extras = []
    if m.get("banned"): extras.append("금지어: " + ", ".join(f"{k}×{v}" for k, v in m["banned"].items()))
    if m.get("sensory"): extras.append("감각어: " + ", ".join(f"{k}×{v}" for k, v in m["sensory"].items()))
    if m.get("nonpreferred_spelling"): extras.append("표기: " + ", ".join(f"{k}→권장 표기로" for k in m["nonpreferred_spelling"]))
    if m.get("conj_top"): extras.append("접속부사: " + ", ".join(f"{k} {v}" for k, v in m["conj_top"].items()))
    if extras:
        lines += [""] + ["- " + e for e in extras]
    return "\n".join(lines)


def load_rules_profile(a):
    if a.kit:
        kit = load_kit(a.kit)
        return kit.targets()["rules"], kit.profile()
    if a.targets:
        return read_json(a.targets)["rules"], (read_json(a.profile) if a.profile else None)
    raise SystemExit("--kit 또는 --targets 가 필요합니다.")


def check_text(text: str, rules, profile, subset="all") -> dict:
    m = analyze_blocks(blocks_from_markdown(text), profile)
    if m.get("error"):
        return {"error": m["error"]}
    rows = evaluate(m, rules, subset)
    return {"metrics": m, "rows": rows,
            "hard_fail": sum(1 for r in rows if not r["ok"] and r["level"] == "hard"),
            "soft_fail": sum(1 for r in rows if not r["ok"] and r["level"] != "hard")}


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kit"); ap.add_argument("--targets"); ap.add_argument("--profile")
    ap.add_argument("--json", action="store_true"); ap.add_argument("--summary", action="store_true")
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--subset", default="all", choices=["all", "counts"])
    a = ap.parse_args()
    rules, profile = load_rules_profile(a)

    results = []
    for f in a.files:
        r = check_text(Path(f).read_text(encoding="utf-8"), rules, profile, a.subset)
        r["file"] = f
        results.append(r)

    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=1, sort_keys=True))
    elif a.summary:
        labels = [r["label"] for r in rules if a.subset == "all" or r.get("kind") in COUNT_LIKE]
        print("| 파일 | hard | soft | " + " | ".join(labels) + " |")
        print("|---|---|---|" + "---|" * len(labels))
        for r in results:
            if "error" in r:
                print(f"| {Path(r['file']).name} | - | - | {r['error']} |"); continue
            marks = ["O" if x["ok"] else ("X" if x["level"] == "hard" else "△") for x in r["rows"]]
            print(f"| {Path(r['file']).name} | {r['hard_fail']} | {r['soft_fail']} | " + " | ".join(marks) + " |")
    else:
        for r in results:
            if "error" in r:
                print(f"## {r['file']}\n{r['error']}\n"); continue
            print(fmt_table(Path(r["file"]).name, r["rows"], r["metrics"])); print()
    if a.strict and any(r.get("hard_fail", 0) for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
