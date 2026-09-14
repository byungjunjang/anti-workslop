# -*- coding: utf-8 -*-
"""
run_acceptance.py — jangpm 종단 인수 테스트 (네트워크 없음).

  python -X utf8 tests/run_acceptance.py [--out DIR]   (기본: tests/.acceptance/jangpm, 끝나면 삭제. --keep 으로 보존)

  1. init_kit (assets/profiles/jangpm.profile.json) → fixtures/html 복사 → collect --urls fixtures/urls.txt
  2. analyze → derive → extract_reading_pack → fixtures/jangpm.worksheet.md 복사 → render --version 2026-09-07
  3. verify_guideline exit 0, selftest exit 0
  4. 핵심 수치 고정: n_sentences 1504, len_mean 55.4, pct_hapsyo 86.2
  5. 첨부 최종본(fixtures/exemplar.md)과 비교: 표제 집합 동일, 렌더본에 없는 최종본 줄은 known_deviations.txt 의 패턴 중 하나에 맞아야 한다
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
SKILL = TESTS.parent
S = SKILL / "scripts"
FAILS: list[str] = []


def run(*args, check=True) -> subprocess.CompletedProcess:
    cp = subprocess.run([sys.executable, "-X", "utf8", *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if check and cp.returncode != 0:
        print(cp.stdout); print(cp.stderr)
        raise SystemExit(f"명령 실패: {args[0]}")
    return cp


def ok(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(TESTS / ".acceptance" / "jangpm"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    kit = Path(a.out).resolve()
    if kit.exists():
        shutil.rmtree(kit)
    print("[1] 수집")
    run(S / "init_kit.py", "--out", kit, "--slug", "jangpm", "--author", "장병준", "--display", "장피엠",
        "--site", "blog.nocodecamp.kr", "--profile", SKILL / "assets" / "profiles" / "jangpm.profile.json")
    (kit / "corpus" / "html").mkdir(parents=True, exist_ok=True)
    for f in (TESTS / "fixtures" / "html").glob("*.html"):
        shutil.copy(f, kit / "corpus" / "html" / f.name)
    run(S / "collect.py", "--kit", kit, "--urls", TESTS / "fixtures" / "urls.txt")
    print("[2] 정량·정성·렌더")
    run(S / "analyze_corpus.py", "--kit", kit)
    run(S / "derive_targets.py", "--kit", kit)
    run(S / "extract_reading_pack.py", "--kit", kit)
    shutil.copy(TESTS / "fixtures" / "jangpm.worksheet.md", kit / "reading-worksheet.md")
    run(S / "render_guideline.py", "--kit", kit, "--version", "2026-09-07", "--quiet")
    print("[3] 검증")
    v = run(S / "verify_guideline.py", "--kit", kit, "--report", check=False)
    ok(v.returncode == 0, "verify_guideline exit 0" + ("" if v.returncode == 0 else "\n" + v.stdout))
    st = run(S / "selftest.py", "--kit", kit, check=False)
    ok(st.returncode == 0, "selftest exit 0")
    print("[4] 핵심 수치")
    o = json.loads((kit / "stats.json").read_text(encoding="utf-8"))["overall"]
    ok(o["n_sentences"] == 1504, f"n_sentences == 1504 ({o['n_sentences']})")
    ok(o["len_mean"] == 55.4, f"len_mean == 55.4 ({o['len_mean']})")
    ok(o["pct_hapsyo"] == 86.2, f"pct_hapsyo == 86.2 ({o['pct_hapsyo']})")
    print("[5] 최종본 비교")
    rendered = (kit / "장피엠 글쓰기 문체 가이드라인.md").read_text(encoding="utf-8")
    exemplar = (TESTS / "fixtures" / "exemplar.md").read_text(encoding="utf-8")
    h_r = [norm_line(l) for l in rendered.splitlines() if re.match(r"^#{1,3}\s", l)]
    h_e = [norm_line(l) for l in exemplar.splitlines() if re.match(r"^#{1,3}\s", l)]
    ok(h_r == h_e, f"표제 목록 동일 ({len(h_r)}개)" + ("" if h_r == h_e else f"\n    렌더에만: {[h for h in h_r if h not in h_e][:3]}\n    최종본에만: {[h for h in h_e if h not in h_r][:3]}"))
    r_lines = {norm_line(l) for l in rendered.splitlines() if norm_line(l)}
    missing = [norm_line(l) for l in exemplar.splitlines() if norm_line(l) and norm_line(l) not in r_lines]
    dev_file = TESTS / "known_deviations.txt"
    patterns = []
    if dev_file.exists():
        patterns = [re.compile(p.strip()) for p in dev_file.read_text(encoding="utf-8").splitlines() if p.strip() and not p.startswith("#")]
    unexplained = [l for l in missing if not any(p.search(l) for p in patterns)]
    ok(not unexplained, f"최종본 줄 {len(missing)}개가 렌더본과 다름, 그중 설명되지 않은 줄 {len(unexplained)}개")
    for l in unexplained[:40]:
        print("      - " + l[:140])
    if unexplained and len(unexplained) > 40:
        print(f"      … 외 {len(unexplained) - 40}")
    print()
    if not a.keep:
        shutil.rmtree(kit, ignore_errors=True)
    if FAILS:
        print(f"실패 {len(FAILS)}건"); return 1
    print("인수 테스트 통과"); return 0


if __name__ == "__main__":
    sys.exit(main())
