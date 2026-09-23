# -*- coding: utf-8 -*-
"""T1 판정 · 09-17 독립 검토가 찾은 의미 변경을 새 위험 추출이 그대로 덮는가.

  python -X utf8 tests/eval_semantic_recall.py

쌍 파일(tests/pairs.json 의 경로)이 없으면 그 줄을 건너뛴다. 모델을 부르지 않는다.
재현 = 옛 기록에서 「의미 변경」인 위험 ID 의 행 구간을, 새 위험 가운데 어느 하나가 같은 쪽
(orig/polished)에서 덮는 것. 옛 ID 와 새 ID 는 다르므로 행 구간이 겹치는지로 맞춘다.
역할이 「재현율」인 쌍에서 하나라도 놓치면 실패다. 「오탐」 쌍은 위험 수만 적는다.
"""
from __future__ import annotations
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
from check_fidelity import load_pair                      # noqa: E402
from semantic_review import risks                         # noqa: E402


def overlap(a, b) -> bool:
    """두 위치가 같은 행 구간을 건드리는가. 한쪽이라도 없으면 겹치지 않는다."""
    if not a or not b:
        return False
    return a["line"] <= b["end_line"] and b["line"] <= a["end_line"]


def main() -> int:
    pairs = json.loads((HERE / "pairs.json").read_text(encoding="utf-8"))
    rows, ok = [], True
    for slug, p in pairs.items():
        op, pp = ROOT / p["orig"], ROOT / p["polished"]
        if not (op.exists() and pp.exists()):
            print(f"SKIP · {slug}: 쌍 파일 없음")
            continue
        record = json.loads((ROOT / p["record"]).read_text(encoding="utf-8"))
        # 옛 위험의 행 구간은 같은 실행의 fidelity JSON 에 있다(검토 기록에는 ID 와 판정만 있다).
        fid_path = ROOT / p["record"].replace(".semantic.json", ".fidelity.json")
        old_risks = {r["id"]: r for r in json.loads(fid_path.read_text(encoding="utf-8"))["semantic_review"]["risks"]}
        changed = [x["id"] for x in record["items"] if x["verdict"] == "의미 변경" and x["id"] in old_risks]
        od, pd, _ = load_pair(str(op), str(pp), "auto", False)
        t0 = time.time()
        new = risks(od, pd)
        elapsed = time.time() - t0
        missed = [rid for rid in changed
                  if not any(overlap(old_risks[rid]["orig"], n["orig"])
                             or overlap(old_risks[rid]["polished"], n["polished"]) for n in new)]
        rows.append((slug, p["role"], len(old_risks), len(new), len(changed), missed, elapsed,
                     Counter(r["reasons"][0] for r in new)))
        if p["role"] == "재현율" and missed:
            ok = False
    print("| 쌍 | 역할 | 옛 위험 | 새 위험 | 정답 변경 | 놓친 것 | 초 |")
    print("|---|---|---|---|---|---|---|")
    for slug, role, o, n, c, m, sec, _k in rows:
        print(f"| {slug} | {role} | {o} | {n} | {c} | {', '.join(m) or '없음'} | {sec:.1f} |")
    for slug, _role, _o, _n, _c, _m, _s, kinds in rows:
        print(f"{slug} 사유 · " + " · ".join(f"{k} {v}" for k, v in kinds.most_common()))
    print("PASS eval_semantic_recall" if ok else "FAIL eval_semantic_recall · 재현율 100% 미달")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
