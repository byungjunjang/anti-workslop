# -*- coding: utf-8 -*-
"""J1 판정 · 라벨 있는 12편에서 jev 의 장르·유형 답이 맞는가. 키가 없으면 SKIP.

  python -X utf8 tests/eval_jev_gate.py [--threshold 0.9]

경로 앞의 @ 는 저장소 루트 기준, 없으면 .claude/skills/anti-workslop/ 기준이다.
라벨은 설계 문서(2026-09-22-pipeline-experiments-design.md §3-3-1)의 표다.
틀린 답이 나와도 라벨을 고치지 않는다. 문턱을 올리거나 선택지 설명을 손보고, 그래도
틀리면 .env.example 의 ANTI_WORKSLOP_JEV_GATE 기본을 0 으로 내린다.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parents[2]
sys.path.insert(0, str(SKILL / "scripts"))
import jev_gate                                            # noqa: E402

CASES = [
    ("tests/fixtures/ai-draft-prose.md", "줄글", "논설·설명"),
    ("tests/fixtures/three-lessons.md", "줄글", "논설·설명"),
    ("tests/fixtures/abstain/already-clean.md", "줄글", "논설·설명"),
    ("tests/fixtures/three-stages-gpt.md", "줄글", "논설·설명"),
    ("tests/fixtures/no-ai-slop-ko.md", "줄글", "논설·설명"),
    ("tests/fixtures/report-titles/decision.md", "줄글", "논설·설명"),
    ("tests/fixtures/explore-memo.md", "줄글", "논설·설명"),
    ("tests/fixtures/ai-draft-report.md", "개조식", "논설·설명"),
    ("@docs/superpowers/evals/2026-09-17/new/report.taste.md", "개조식", "논설·설명"),
    ("tests/fixtures/timeline.md", "개조식", "시간순"),
    ("tests/fixtures/quoted-law.md", "줄글", "인용·전재"),
    ("tests/fixtures/clean-control.md", "섞임", "논설·설명"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.9)
    a = ap.parse_args()
    if not jev_gate.enabled("gate"):
        print("SKIP eval_jev_gate · TYPESAFE_API_KEY 없음")
        return 0
    seen = wrong = 0
    for rel, genre, doc_type in CASES:
        p = (ROOT / rel[1:]) if rel.startswith("@") else (SKILL / rel)
        if not p.exists():
            print(f"- {rel} · 파일 없음, 건너뜀")
            continue
        got = jev_gate.classify_input(p.read_text(encoding="utf-8"))
        if not isinstance(got, dict):
            print(f"- {rel} · 실패({got})")
            continue
        bits = []
        for key, want in (("genre", genre), ("doc_type", doc_type)):
            val, conf = got[key]
            if conf >= a.threshold:
                seen += 1
                ok = val == want
                wrong += 0 if ok else 1
                bits.append(f"{key} {val} {conf:.2f} {'O' if ok else f'X(정답 {want})'}")
            else:
                bits.append(f"{key} {val} {conf:.2f} -문턱미만(정답 {want})")
        print(f"- {rel} · " + " · ".join(bits))
    print(f"확신 {a.threshold} 이상 {seen}개 중 오답 {wrong}개")
    print("PASS eval_jev_gate" if wrong == 0 else "FAIL eval_jev_gate")
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
