# -*- coding: utf-8 -*-
"""
verify_guideline.py — 렌더된 가이드라인이 입력과 일치하고, 구조·인용·규칙이 건전한지 검증한다 (읽기 전용).

  python -X utf8 verify_guideline.py --kit styleguides/<slug> [--doc PATH] [--report]

  ① 스냅샷: posts/stats/targets/profile/metrics 해시 일치, render-manifest 의 입력 해시가 현재와 같음
  ② 재렌더 → 바이트 동일 (완성본을 손으로 고쳤거나 입력이 바뀌면 실패)
  ③ 템플릿의 모든 ##/### 표제가 정확히 1회, 같은 순서로 존재
  ④ '{{' '[TODO' U+FFFD 없음
  ⑤ §11-1 표의 행 == targets.json 규칙 (라벨·기준·등급·순서)
  ⑥ 워크시트 인용(12자 이상 "…"/“…”)이 코퍼스 본문에 존재 (제외 슬롯: conversion_examples, voice_*, *_short, profile_proposals, policy_flag_notes)
  ⑦ check_style: 코퍼스 원문 전부 hard 통과, 대조군 hard 실패 ≥ N, 워크시트 변환 예시의 '후' 문장이 counts 규칙 통과
  ⑧ selftest exit 0
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_style import check_text  # noqa: E402
from kitlib import SKILL_DIR, assert_snapshot, dump_json_sorted, force_utf8_stdout, load_kit, read_json, read_text, resolve_skill_path, sha256_file  # noqa: E402
from metrics import blocks_from_markdown  # noqa: E402
from render_guideline import Renderer, parse_table, parse_worksheet  # noqa: E402

QUOTE_EXEMPT_PREFIX = ("conversion_examples", "voice", "profile_proposals", "policy_flag_notes", "body_order", "regression")
QUOTE_EXEMPT_SUFFIX = ("_short",)


def norm(s: str) -> str:
    return re.sub(r"[\s\"“”'‘’]+", "", s)


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--doc", default=None)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    kit = load_kit(a.kit)
    doc_path = Path(a.doc) if a.doc else kit.guideline
    results, fails = [], []

    def rec(name: str, ok: bool, detail: str = ""):
        results.append({"check": name, "ok": ok, "detail": detail})
        print(("  ok   " if ok else "  FAIL ") + name + (f" — {detail}" if detail else ""))
        if not ok:
            fails.append(name)

    # ① 스냅샷
    try:
        assert_snapshot(kit, need_stats=True, need_targets=True)
        rec("① 스냅샷 해시 일치", True)
    except SystemExit as e:
        rec("① 스냅샷 해시 일치", False, str(e)); print(); return 1
    if not kit.render_manifest.exists():
        rec("① render-manifest 존재", False, "render_guideline.py 를 먼저 실행"); return 1
    mf = read_json(kit.render_manifest)
    tpl = SKILL_DIR / mf["template"] if not Path(mf["template"]).is_absolute() else Path(mf["template"])
    same = (mf["template_sha256"] == sha256_file(tpl) and mf["worksheet_sha256"] == sha256_file(kit.worksheet)
            and mf["stats_sha256"] == sha256_file(kit.stats_json) and mf["targets_sha256"] == sha256_file(kit.targets_json)
            and mf["profile_sha256"] == sha256_file(kit.profile_json))
    rec("① render-manifest 입력 해시 일치", same, "" if same else "템플릿/워크시트/stats/targets/profile 중 하나가 렌더 후 바뀜")

    # ② 재렌더 바이트 동일
    r = Renderer(kit, mf["version"], allow_todo=True)
    rendered = r.render(read_text(tpl))
    rendered = rendered if rendered.endswith("\n") else rendered + "\n"
    current = read_text(doc_path)
    rec("② 재렌더 결과가 완성본과 바이트 동일", rendered == current, "" if rendered == current else "완성본을 손으로 고쳤거나 워크시트가 바뀜 → 다시 render")

    # ③ 표제
    tpl_heads = [l.strip() for l in read_text(tpl).split("\n") if re.match(r"^#{2,3}\s", l)]
    doc_heads = [l.strip() for l in current.split("\n") if re.match(r"^#{2,3}\s", l)]
    tpl_heads_r = [r.render_line(h) for h in tpl_heads]
    missing = [h for h in tpl_heads_r if doc_heads.count(h) != 1]
    order_ok = [h for h in doc_heads if h in tpl_heads_r] == tpl_heads_r
    rec("③ 템플릿 표제가 정확히 1회·같은 순서", not missing and order_ok, "; ".join(missing[:5]) if missing else ("" if order_ok else "순서 불일치"))

    # ④ 잔여 슬롯·TODO
    leftovers = [w for w in ("{{", "[TODO", "�") if w in current]
    rec("④ 잔여 슬롯·TODO·깨진 문자 없음", not leftovers, ", ".join(repr(x) for x in leftovers))

    # ⑤ §11-1 표 == targets
    m = re.search(r"### 11-1[^\n]*\n(.*?)\n### 11-2", current, flags=re.S)
    ok5, detail5 = False, "§11-1 표를 찾지 못함"
    if m:
        rows = parse_table(m.group(1))
        rules = kit.targets()["rules"]
        got = [(x.get("항목"), x.get("기준"), x.get("등급")) for x in rows]
        want = [(x["label"], x["target_text"], x["level"]) for x in rules]
        ok5 = got == want
        detail5 = "" if ok5 else f"표 {len(got)}행 vs 규칙 {len(want)}개"
    rec("⑤ §11-1 표가 targets.json 과 일치", ok5, detail5)

    # ⑥ 워크시트 인용 무결성
    slots = parse_worksheet(read_text(kit.worksheet)) if kit.worksheet.exists() else {}
    corpus_norm = norm(" ".join(b["text"] for p in kit.posts() for b in p["blocks"]))
    bad = []
    for name, body in slots.items():
        if name.startswith(QUOTE_EXEMPT_PREFIX) or name.endswith(QUOTE_EXEMPT_SUFFIX):
            continue
        # 같은 줄 안에서 왼쪽부터 짝을 짓는다(짧은 인용의 닫는 따옴표가 다음 인용의 여는 따옴표로 오인되지 않게)
        for q in re.findall(r"[\"“]([^\"“”\n]*?)[\"”]", body):
            if len(q) < 12:
                continue
            parts = [x for x in re.split(r"[…]|\.\.\.", q) if len(norm(x)) >= 8]
            if not parts:
                continue
            if not all(norm(x) in corpus_norm for x in parts):
                bad.append(f"{name}: {q[:40]}")
    rec("⑥ 워크시트 인용이 코퍼스에 존재", not bad, "; ".join(bad[:4]) + (f" 외 {len(bad)-4}" if len(bad) > 4 else ""))

    # ⑦ check_style
    rules, profile = kit.targets()["rules"], kit.profile()
    hard_fail_posts = []
    for p in kit.posts():
        txt = "\n\n".join(b["text"] for b in p["blocks"] if b["tag"] == "p")
        res = check_text(txt, rules, profile)
        if res.get("error") or res["hard_fail"]:
            hard_fail_posts.append(p["slug"])
    rec("⑦a 코퍼스 원문 전부 hard 통과", not hard_fail_posts, ", ".join(hard_fail_posts))
    ctrl = Path(resolve_skill_path(profile.get("control_sample", "${SKILL_DIR}/assets/samples/ai_draft.md")))
    need = int(profile.get("control_min_hard_fails", 5))
    cres = check_text(read_text(ctrl), rules, profile)
    rec(f"⑦b 대조군 hard 실패 ≥ {need}", cres.get("hard_fail", 0) >= need, f"{cres.get('hard_fail')}개")
    conv = parse_table(slots.get("conversion_examples", ""))
    after_fail = []
    for row in conv:
        after = row.get("후", "")
        if len(after) < 20:
            continue
        res = check_text(after, rules, profile, subset="counts")
        if not res.get("error") and res["hard_fail"]:
            after_fail.append(after[:30])
    rec("⑦c 변환 예시 '후' 문장이 counts 규칙 통과", not after_fail, "; ".join(after_fail))

    # ⑧ selftest
    st = subprocess.run([sys.executable, "-X", "utf8", str(HERE / "selftest.py"), "--kit", str(kit.root)], capture_output=True, text=True, encoding="utf-8")
    rec("⑧ selftest 통과", st.returncode == 0, "" if st.returncode == 0 else st.stdout.strip().splitlines()[-1] if st.stdout else "")

    print()
    if a.report:
        dump_json_sorted({"doc": doc_path.name, "doc_sha256": sha256_file(doc_path), "corpus_sha256": kit.stats()["corpus_sha256"],
                          "checks": results, "passed": not fails}, kit.verification)
        print(f"[report] {kit.verification}")
    if fails:
        print(f"실패 {len(fails)}건: " + "; ".join(fails)); return 1
    print("검증 통과"); return 0


if __name__ == "__main__":
    sys.exit(main())
