# -*- coding: utf-8 -*-
"""J2 판정 · jev 1차 판정이 09-17 정답을 새지 않고 오탐을 내지 않는가. 키가 없으면 SKIP.

  python -X utf8 tests/eval_jev_semantic.py [--keep 0.9] [--change 0.8]

재현율 쌍(AX)에서 09-17 독립 검토가 「의미 변경」이라고 한 자리를 jev 가 자동 「보존 확인」으로
덮어 버리면 샌 것이다(판단 불가는 사람에게 가므로 새지 않은 것으로 센다). 오탐 쌍(마케팅 2차)은
09-17 검토가 91건 전부 보존 확인이라, jev 가 자동 「의미 변경」을 내면 오탐이다.

판정 · ① 재현율 쌍에서 샌 것 0 ② 오탐 쌍에서 자동 변경 0. 해소율은 표에만 적는다.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(HERE))
import jev_gate                                            # noqa: E402
import semantic_review                                     # noqa: E402
from check_fidelity import load_pair                       # noqa: E402
from eval_semantic_recall import overlap                   # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=float, default=None, help="보존 자동 판정 문턱")
    ap.add_argument("--change", type=float, default=None, help="변경 자동 판정 문턱")
    a = ap.parse_args()
    if a.keep is not None:
        semantic_review.KEEP = a.keep
    if a.change is not None:
        semantic_review.CHANGE = a.change
    if not jev_gate.enabled("semantic"):
        print("SKIP eval_jev_semantic · TYPESAFE_API_KEY 없음")
        return 0
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))
    rows, ok = [], True
    for slug, p in pairs.items():
        op, pp = ROOT / p["orig"], ROOT / p["polished"]
        if not (op.exists() and pp.exists()):
            print(f"SKIP · {slug}: 쌍 파일 없음")
            continue
        record = json.loads((ROOT / p["record"]).read_text(encoding="utf-8"))
        fid_path = ROOT / p["record"].replace(".semantic.json", ".fidelity.json")
        old_risks = {r["id"]: r for r in json.loads(fid_path.read_text(encoding="utf-8"))["semantic_review"]["risks"]}
        changed_ids = [x["id"] for x in record["items"] if x["verdict"] == "의미 변경" and x["id"] in old_risks]
        od, pd, _ = load_pair(str(op), str(pp), "auto", False)
        pack = semantic_review.packet(od, pd)
        t0 = time.time()
        rec = semantic_review.judge(pack)
        elapsed = time.time() - t0
        preserved = set(rec["preserved"])
        auto_change = [x["id"] for x in rec["items"] if x["verdict"] == "의미 변경"]
        unsure = [x["id"] for x in rec["items"] if x["verdict"] == "판단 불가"]
        by_id = {r["id"]: r for r in pack["risks"]}
        leaked = []
        for rid in changed_ids:
            old = old_risks[rid]
            hits = [n["id"] for n in pack["risks"]
                    if overlap(old["orig"], n["orig"]) or overlap(old["polished"], n["polished"])]
            if hits and all(h in preserved for h in hits):
                leaked.append(f'{rid}→{",".join(hits)}')
            elif not hits:
                leaked.append(f"{rid}→위험없음")
        rows.append((slug, p["role"], len(pack["risks"]), len(preserved), len(auto_change),
                     len(unsure), len(changed_ids), leaked, elapsed))
        if p["role"] == "재현율" and leaked:
            ok = False
        if p["role"] == "오탐" and auto_change:
            ok = False
            rows[-1] = rows[-1][:7] + (leaked + [f"오탐 {len(auto_change)}건: {', '.join(auto_change[:5])}"], elapsed)
        del by_id
    print("| 쌍 | 역할 | 위험 | 자동 보존 | 자동 변경 | 판단 불가 | 정답 변경 | 샌 것 | 해소율 | 초 |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for slug, role, total, keep, chg, uns, gt, leaked, sec in rows:
        rate = f"{keep / total:.0%}" if total else "-"
        print(f"| {slug} | {role} | {total} | {keep} | {chg} | {uns} | {gt} | "
              f"{', '.join(leaked) or '없음'} | {rate} | {sec:.0f} |")
    print(f"문턱 · 보존 {semantic_review.KEEP} · 변경 {semantic_review.CHANGE}")
    print("PASS eval_jev_semantic" if ok else "FAIL eval_jev_semantic")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
