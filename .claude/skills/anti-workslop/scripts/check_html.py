# -*- coding: utf-8 -*-
"""check_html.py — HTML 의 산문 블록을 md 로 뽑아 md 장르 검사기에 그대로 넘긴다 (읽기 전용).

  python -X utf8 check_html.py --guide <가이드> [--short] FILE.html     # 가이드 = base-guidelines.json 에 등록된 이름
  python -X utf8 check_html.py --extract-only FILE.html [-o OUT.md]

HTML 전용 검사기를 따로 두지 않는다. 임계값은 md 검사기(targets.json·가이드 §11 표) 하나만 산다.
추출은 check_ai_tells.segment_html 이 한다(표·코드·스크립트는 빼고 표제·문단·목록·인용만).
검사 명령은 references/base-guidelines.json 의 _checks[가이드][md](--short 면 _checks_short)를 쓰고,
자식 검사기의 stdout·stderr·종료 코드를 그대로 돌려준다. 입력 오류는 exit 2.
"""
from __future__ import annotations
import argparse, json, re, shlex, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]
BASE = SKILL_DIR / "references" / "base-guidelines.json"
sys.path.insert(0, str(HERE))
from check_ai_tells import force_utf8_stdout, normalize_text, segment_html  # noqa: E402

PREFIX = {"heading": "## ", "list": "- ", "quote": "> ", "prose": ""}
REPORT_MARKS = ("□ ", "○ ", "- ")                  # check_report 는 기호로 층위를 읽는다(parse_items)
BULLET_HEAD = re.compile(r"^[□○▪◦●·※•■▶◆\-*+]\s")


def extract_md_mapped(html: str, kind: str = "style") -> tuple[str, dict]:
    """(md, {md 줄 번호: HTML 줄 번호}). 표제는 층위를 모르므로 모두 ## 로 적는다(검사기는 개수만 센다).
    목록은 깊이를 kind 에 맞춰 표기한다 — report 는 □·○·들여쓴 -, style 은 두 칸 들여쓰기."""
    out, lines = [], {}
    for s in segment_html(normalize_text(html)):
        p = PREFIX.get(s.kind)
        if p is None:                              # 표·코드·면제 구역은 뽑지 않는다
            continue
        text = " ".join(s.text.split())
        if not text:
            continue
        if s.kind == "list":
            d = getattr(s, "depth", 0)
            if kind == "report":
                mark = "" if BULLET_HEAD.match(text) else REPORT_MARKS[min(d, 2)]
                p = ("  " if d >= 2 else "") + mark
            else:
                p = "  " * min(d, 3) + "- "
        lines[2 * len(out) + 1] = s.line_start     # 블록은 빈 줄로 잇는다: 0→1행, 1→3행 …
        out.append(p + text)
    return "\n\n".join(out) + ("\n" if out else ""), lines


def extract_md(html: str, kind: str = "style") -> str:
    return extract_md_mapped(html, kind)[0]


def load_bg() -> dict:
    return json.loads(BASE.read_text(encoding="utf-8"))


def command_for(guide: str, short: bool) -> str:
    bg = load_bg()
    table = bg["_checks_short"] if short else bg["_checks"]
    try:
        return table[guide]["md"]
    except KeyError:
        print(f"입력 오류: base-guidelines.json 에 {guide!r} 의 md 명령이 없다.", file=sys.stderr)
        raise SystemExit(2)


LINE_REF = re.compile(r"^(\s*-?\s*[A-Z]\d+)\s+(\d+)행", re.M)


def remap_lines(text: str, lines: dict) -> str:
    """자식 검사기가 추출 md 줄로 낸 번호를 HTML 줄로 바꾼다."""
    def sub(m: "re.Match") -> str:
        n = int(m.group(2))
        return f"{m.group(1)} {lines.get(n, n)}행"
    return LINE_REF.sub(sub, text)


def run_check(cmd: str, md_path: Path, lines: dict | None = None) -> int:
    argv = shlex.split(cmd.replace("{file}", md_path.as_posix()), posix=True)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    sys.stdout.write(remap_lines(r.stdout, lines) if lines else r.stdout)
    sys.stderr.write(r.stderr)
    return r.returncode


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="check_html.py", add_help=True,
                                description="HTML 의 산문 블록을 md 로 뽑아 md 장르 검사기에 넘긴다(읽기 전용).")
    p.add_argument("file", help="검사할 HTML")
    p.add_argument("--guide", choices=[k for k in load_bg() if not k.startswith("_")],
                   help="가이드 이름(base-guidelines.json 의 밑줄 없는 키)")
    p.add_argument("--short", action="store_true", help="짧은 글용 명령(_checks_short)을 쓴다")
    p.add_argument("--extract-only", action="store_true", help="md 로 뽑기만 한다")
    p.add_argument("-o", "--out", help="--extract-only 의 저장 경로(없으면 stdout)")
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    a = build_parser().parse_args(argv)
    src = Path(a.file)
    try:
        html = src.read_text(encoding="utf-8")
    except OSError as e:
        print(f"입력 오류: {a.file}: {e}", file=sys.stderr)
        return 2
    kind = load_bg().get("_checker_kind", {}).get(a.guide, "style")
    md, line_map = extract_md_mapped(html, kind)
    if a.extract_only:
        if a.out:
            Path(a.out).write_text(md, encoding="utf-8")
        else:
            sys.stdout.write(md)
        return 0
    if not a.guide:
        print("--guide <가이드> 가 필요하다(또는 --extract-only).", file=sys.stderr)
        return 2
    cmd = command_for(a.guide, a.short)
    with tempfile.TemporaryDirectory() as d:
        md_path = Path(d) / (src.stem + ".md")
        md_path.write_text(md, encoding="utf-8")
        return run_check(cmd, md_path, line_map)


if __name__ == "__main__":
    raise SystemExit(main())
