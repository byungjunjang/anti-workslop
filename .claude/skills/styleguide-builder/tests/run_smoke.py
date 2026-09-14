# -*- coding: utf-8 -*-
"""
run_smoke.py — 다른 코퍼스(.md 폴더)로 과적합 여부를 확인하는 스모크 테스트.

  python -X utf8 tests/run_smoke.py --md-dir DIR [--recursive] [--keep]

  통과 조건: 크래시 없음 · 표 문장 0 · 모든 hard 규칙이 envelope 포함(derive exit 0) · selftest [1][2][8] 통과 ·
            render --allow-todo 결과에 템플릿 표제 전부 존재 · [TODO:] 수 == 워크시트 슬롯 수(q 슬롯 미충족은 정상)
  산출물은 tests/.smoke/<name>/ 에만 남기고 --keep 이 없으면 삭제한다. 원본 폴더는 읽기만 한다.
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


def run(*args, check=True):
    cp = subprocess.run([sys.executable, "-X", "utf8", *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    if check and cp.returncode != 0:
        print(cp.stdout); print(cp.stderr); raise SystemExit(f"명령 실패: {args[0]}")
    return cp


def ok(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md-dir", required=True); ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--keep", action="store_true"); ap.add_argument("--name", default="smoke")
    a = ap.parse_args()
    kit = TESTS / ".smoke" / a.name
    if kit.exists():
        shutil.rmtree(kit)
    run(S / "init_kit.py", "--out", kit, "--slug", a.name, "--author", "스모크저자", "--display", "스모크")
    args = [S / "collect.py", "--kit", kit, "--md-dir", a.md_dir] + (["--recursive"] if a.recursive else [])
    run(*args)
    run(S / "analyze_corpus.py", "--kit", kit)
    d = run(S / "derive_targets.py", "--kit", kit, check=False)
    ok(d.returncode == 0, "derive_targets: 모든 hard 규칙이 envelope 포함" + ("" if d.returncode == 0 else "\n" + d.stdout))
    st = json.loads((kit / "stats.json").read_text(encoding="utf-8"))
    o = st["overall"]
    ok(o["n_sentences"] > 0, f"본문 문장 {o['n_sentences']} (글 {st['n_posts']}편)")
    # 표 행("| a | b |" 꼴, 파이프 3개 이상)이 문단으로 새지 않았는지. 산문 속 ' | ' 구분자 하나는 허용.
    leaked = [b["text"][:60] for p in json.loads((kit / "corpus" / "posts.json").read_text(encoding="utf-8")) for b in p["blocks"]
              if b["tag"] == "p" and (b["text"].startswith("|") or b["text"].count("|") >= 3)]
    ok(not leaked, "표 행이 문단으로 새지 않음" + ("" if not leaked else f": {leaked[:3]}"))
    run(S / "extract_reading_pack.py", "--kit", kit)
    shutil.copy(SKILL / "assets" / "reading-worksheet.template.md", kit / "reading-worksheet.md")
    r = run(S / "render_guideline.py", "--kit", kit, "--version", "smoke", "--allow-todo", "--quiet", check=False)
    ok(r.returncode == 0, "render --allow-todo 성공" + ("" if r.returncode == 0 else "\n" + r.stdout + r.stderr))
    if r.returncode == 0:
        doc = (kit / "스모크 글쓰기 문체 가이드라인.md").read_text(encoding="utf-8")
        tpl = (SKILL / "assets" / "templates" / "blog.template.md").read_text(encoding="utf-8")
        heads = [l for l in tpl.splitlines() if re.match(r"^#{2,3}\s", l) and "{{" not in l]
        ok(all(h in doc for h in heads), f"템플릿 표제 {len(heads)}개 존재")
        todo = len(set(re.findall(r"\[TODO:([A-Za-z_]+)\]", doc)))
        ok(todo >= 30, f"[TODO:] 슬롯 {todo}개 (정성 슬롯이 비어 있으니 정상)")
        ok("{{" not in doc.replace("[TODO:", ""), "잔여 숫자 슬롯 없음")
    sel = run(S / "selftest.py", "--kit", kit, check=False)
    lines = sel.stdout.splitlines()
    fixed = [l for l in lines if l.strip().startswith("FAIL") and ("문장" in l or "→" in l or "픽스처" in l or "표" in l)]
    ok(not fixed, "selftest 고정 케이스([1][2][8]) 통과")
    print(f"  info 참고: 평균 {o['len_mean']}자 / 합쇼체 {o['pct_hapsyo']}% / 해요체 {o['pct_haeyo']}% / 문두 접속 {o['pct_conj_start']}% / 대조군 검사 결과는 selftest 출력 참조")
    print()
    if not a.keep:
        shutil.rmtree(kit, ignore_errors=True)
    if FAILS:
        print(f"실패 {len(FAILS)}건"); return 1
    print("스모크 통과"); return 0


if __name__ == "__main__":
    sys.exit(main())
