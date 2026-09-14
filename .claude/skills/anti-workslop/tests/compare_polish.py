# -*- coding: utf-8 -*-
"""compare_polish.py — 원문·윤문본 여러 판을 네 검사기(장르·AI 티·취향·의미 보존)로 같은 잣대로 채점해 표로 낸다 (읽기 전용).

  python -X utf8 compare_polish.py --genre 줄글|개조식 --orig ORIG.md LABEL=PATH [LABEL=PATH...]
  python -X utf8 compare_polish.py --genre 줄글|개조식 --orig ORIG.md LABEL=PATH [LABEL=PATH...] --json

네 검사기:
  - 장르: 줄글이면 check_style.py --kit styleguides/jangpm --json 의 hard_fail/soft_fail.
          개조식이면 styleguides/report/scripts/check_report.py 의 텍스트 출력에서
          "[반드시 고칠 것] N건"/"[검토할 것] N건" 절 머리글의 N (그 스크립트 자신의
          report["hard"]/report["soft"] 길이와 정확히 같다 — 절 안에는 H·S 접두 항목이
          섞여 있어(예: 검토할 것 절의 H6·H7·H8), 줄 접두어만으로 세면 어긋난다).
  - AI 티: check_ai_tells.py --genre GENRE --json 의 summary.by_severity.
  - 취향: check_taste.py --json 의 summary.by_grade (규칙 / 경향+관찰). 적용 범위는 보지 않는다.
  - 의미 보존: check_fidelity.py --json ORIG FILE 의 summary.by_severity·stats.length_ratio.
    원문 행 자신은 fidelity 를 매기지 않는다(자기 자신과 비교할 대상이 없다).

--strict 는 네 검사기 어디에도 넘기지 않는다(exit code 로 판을 가려내지 않고 수치만 모은다).
검사기가 exit 2(입력 오류)를 내면 그대로 exit 2 로 전파하고 자식의 stderr 를 그대로 흘려보낸다.
표준 라이브러리만 사용한다.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# tests/ -> anti-workslop -> skills -> .claude -> 프로젝트 루트.
# check_ai_tells.py·check_fidelity.py 와 같은 패턴(HERE -> SKILL_DIR -> ROOT)으로 구한다.
# 파이프라인이 부르지 않는 평가 도구라 scripts/ 가 아니라 tests/ 에 둔다(2026-09-14).
HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]

STYLE_CHECK = ROOT / ".claude/skills/styleguide-builder/scripts/check_style.py"
REPORT_CHECK = ROOT / "styleguides/report/scripts/check_report.py"
AI_TELLS_CHECK = ROOT / ".claude/skills/anti-workslop/scripts/check_ai_tells.py"
FIDELITY_CHECK = ROOT / ".claude/skills/anti-workslop/scripts/check_fidelity.py"
TASTE_CHECK = ROOT / ".claude/skills/anti-workslop/scripts/check_taste.py"

JANGPM_KIT = "styleguides/jangpm"

HARD_HDR_RE = re.compile(r"^\[반드시 고칠 것\]\s*(\d+)건", re.M)
SOFT_HDR_RE = re.compile(r"^\[검토할 것\]\s*(\d+)건", re.M)

PAIR_RE = re.compile(r"^([^=]+)=(.+)$")

TABLE_HEADER = ("| 판 | 장르 hard | 장르 soft | AI 티 S1 | AI 티 S2 | AI 티 S3 | 취향 규칙 | 취향 경향·관찰 | "
                "의미 보존 S1 | 의미 보존 S2 | 길이 비율 |")
TABLE_SEP = "|---|---|---|---|---|---|---|---|---|---|---|"


def force_utf8_stdout() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 네 검사기 실행
# ---------------------------------------------------------------------------
def run_checker(script: Path, *args: str) -> subprocess.CompletedProcess:
    """검사기 하나를 부른다. exit 0·1 만 정상이다. 입력 오류(2)와 예외로 죽은 경우는 exit 2 로 전파한다."""
    cmd = [sys.executable, "-X", "utf8", str(script), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode not in (0, 1):
        sys.stderr.write(r.stderr or r.stdout)
        sys.exit(2)
    return r


def _fail(msg: str, r: subprocess.CompletedProcess | None = None) -> None:
    """검사기 출력을 읽을 수 없을 때. 자식의 마지막 stderr 줄만 붙이고 exit 2."""
    tail = ((r.stderr or r.stdout).strip().splitlines() if r is not None else []) or [""]
    print(f"[오류] {msg}" + (f": {tail[-1]}" if tail[-1] else ""), file=sys.stderr)
    sys.exit(2)


def _json_of(what: str, r: subprocess.CompletedProcess):
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        _fail(f"{what} 출력이 JSON 이 아니다", r)


def run_genre_style(path: str) -> tuple[int, int]:
    """줄글: check_style.py --kit styleguides/jangpm --json 의 hard_fail/soft_fail."""
    r = run_checker(STYLE_CHECK, "--kit", JANGPM_KIT, "--json", path)
    data = _json_of("check_style", r)
    data = data[0] if isinstance(data, list) and data else data
    if not isinstance(data, dict) or "error" in data:
        _fail(f"check_style: {data.get('error') if isinstance(data, dict) else data!r}")
    return data.get("hard_fail", 0), data.get("soft_fail", 0)


def run_genre_report(path: str) -> tuple[int, int]:
    """개조식: check_report.py 텍스트 출력의 절 머리글 건수.

    "[반드시 고칠 것] N건" -> hard, "[검토할 것] N건" -> soft. 이 스크립트는 --json 이
    없고, 절 안에는 H·S 접두 항목이 섞여 있어(검토할 것 절의 H1·H4·H6·H7·H8 + S1·S2)
    줄 접두어(" - H"/" - S")만으로 세면 절 전체 개수(= report["hard"]/["soft"] 길이,
    스크립트 자신의 exit code 판정 기준)보다 적게 잡힌다. 머리글의 N 을 그대로 쓴다.
    """
    r = run_checker(REPORT_CHECK, path)
    hm = HARD_HDR_RE.search(r.stdout)
    sm = SOFT_HDR_RE.search(r.stdout)
    if hm is None or sm is None:
        _fail(f"check_report.py 출력에서 절 머리글을 찾지 못했다: {path}", r)
    return int(hm.group(1)), int(sm.group(1))


def run_genre(path: str, genre: str) -> tuple[int, int]:
    return run_genre_style(path) if genre == "줄글" else run_genre_report(path)


def run_ai_tells(path: str, genre: str) -> tuple[int, int, int]:
    r = run_checker(AI_TELLS_CHECK, "--genre", genre, "--json", path)
    sev = _json_of("check_ai_tells", r)["summary"]["by_severity"]
    return sev["S1"], sev["S2"], sev["S3"]


def run_taste(path: str) -> tuple[int, int]:
    """취향: check_taste.py --json 의 summary.by_grade. (규칙, 경향+관찰)."""
    r = run_checker(TASTE_CHECK, "--json", path)
    g = _json_of("check_taste", r)["summary"]["by_grade"]
    return g["규칙"], g["경향"] + g["관찰"]


def run_fidelity(orig: str, path: str) -> tuple[int, int, float]:
    r = run_checker(FIDELITY_CHECK, "--json", orig, path)
    d = _json_of("check_fidelity", r)
    sev = d["summary"]["by_severity"]
    return sev["S1"], sev["S2"], d["stats"]["length_ratio"]


# ---------------------------------------------------------------------------
# 행 조립
# ---------------------------------------------------------------------------
def build_row(label: str, path: str, genre: str, orig: str | None) -> dict:
    genre_hard, genre_soft = run_genre(path, genre)
    ai_s1, ai_s2, ai_s3 = run_ai_tells(path, genre)
    taste_rule, taste_lean = run_taste(path)
    if orig is None:
        fidelity_s1 = fidelity_s2 = None
        length_ratio = 1.0
    else:
        fidelity_s1, fidelity_s2, length_ratio = run_fidelity(orig, path)
    return {"label": label, "path": path, "genre_hard": genre_hard, "genre_soft": genre_soft,
            "ai_s1": ai_s1, "ai_s2": ai_s2, "ai_s3": ai_s3, "taste_rule": taste_rule, "taste_lean": taste_lean,
            "fidelity_s1": fidelity_s1, "fidelity_s2": fidelity_s2, "length_ratio": length_ratio}


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------
def _cell(v) -> str:
    return "—" if v is None else str(v)


def fmt_table(rows: list[dict]) -> str:
    lines = [TABLE_HEADER, TABLE_SEP]
    for r in rows:
        lines.append(
            f"| {r['label']} | {r['genre_hard']} | {r['genre_soft']} | "
            f"{r['ai_s1']} | {r['ai_s2']} | {r['ai_s3']} | {r['taste_rule']} | {r['taste_lean']} | "
            f"{_cell(r['fidelity_s1'])} | {_cell(r['fidelity_s2'])} | {r['length_ratio']:.2f} |"
        )
    return "\n".join(lines)


def to_json(rows: list[dict]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="compare_polish.py", add_help=True,
                                description="원문·윤문본 여러 판을 네 검사기로 같은 잣대로 채점해 표로 낸다.")
    p.add_argument("--genre", required=True, choices=["줄글", "개조식"], help="장르")
    p.add_argument("--orig", required=True, help="원문 경로")
    p.add_argument("pairs", nargs="+", metavar="LABEL=PATH", help="채점할 판. LABEL=PATH 형식, 여러 개 가능")
    p.add_argument("--json", action="store_true", help="같은 내용을 JSON 배열로 출력")
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    args = build_parser().parse_args(argv)

    rows = [build_row("원문", args.orig, args.genre, orig=None)]
    for raw in args.pairs:
        m = PAIR_RE.match(raw)
        if not m:
            print(f"인수 오류: LABEL=PATH 형식이 아니다: {raw!r}", file=sys.stderr)
            return 2
        label, path = m.group(1), m.group(2)
        rows.append(build_row(label, path, args.genre, orig=args.orig))

    print(to_json(rows) if args.json else fmt_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
