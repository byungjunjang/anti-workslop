# -*- coding: utf-8 -*-
"""check_taste.py — taste/writing-taste.md 의 W-NN 가운데 검출 필드가 있는 것을 초고에 대고 센다 (읽기 전용).

  python -X utf8 check_taste.py FILE... [--doc PATH] [--json] [--strict]
  python -X utf8 check_taste.py --list [--doc PATH]

검출 방식은 원칙 검사기(check_ai_tells.py)와 같은 어휘다. regex·literal 은 매치마다 finding,
density 는 단위당 임계 이상일 때 finding 하나, human 은 건너뛰고 summary.human 에 적는다.
finding 의 등급은 규칙 줄의 [규칙]·[경향]·[관찰]이다. --strict 는 [규칙] finding 이 있을 때만 exit 1.
「적용: …」은 규칙이 나온 장르이고 finding 의 scope 에 실어 보낸다. 모든 문서에 센다.
종료 0 / 1(--strict 실패) / 2(입력·규칙 파일 오류).
"""
from __future__ import annotations
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]
TASTE_MD = ROOT / "taste" / "writing-taste.md"
sys.path.insert(0, str(HERE))
from check_ai_tells import (Rule, compile_pattern, force_utf8_stdout, load_rules,   # noqa: E402
                            normalize_text, run_pattern_rule, segment_html, segment_markdown)

GRADES = ("규칙", "경향", "관찰")
RULE_RE = re.compile(r"^(W-\d+) \[(규칙|경향|관찰|보류)\] (.+?) — 적용: (.*?) — 근거: ")
DETECT_RE = re.compile(r" — 검출: (.*?)(?= — 갱신 |$)")
DETECT_PARSE_RE = re.compile(r"^(regex|literal|density|human)(?: (\d+)/(문서|문단|문장))?(?: `([^`]+)`)?$")
VERSION_RE = re.compile(r"^- 버전:\s*(\S+)", re.M)


class TasteRule:
    def __init__(self, rid: str, grade: str, statement: str, applies: str, detect: str,
                 rule: Rule | None):
        self.id, self.grade, self.statement, self.applies, self.detect, self.rule = \
            rid, grade, statement, applies, detect, rule


def load_taste(path: Path = TASTE_MD) -> tuple[str | None, list]:
    """(버전, TasteRule 목록). 보류(§7)는 적용하지 않으므로 싣지 않는다. 형식 오류는 SystemExit(2).
    문서가 없으면 (None, []) 이다. 취향은 사람마다 각자 쌓는 것이라 없는 상태가 정상이다(taste-builder init_taste.py)."""
    if not path.exists():
        return None, []
    try:
        md = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"입력 오류: {path}: {e}", file=sys.stderr); raise SystemExit(2)
    md = normalize_text(md)
    ver = VERSION_RE.search(md)
    errors, out = [], []
    for line in md.splitlines():
        m = RULE_RE.match(line)
        if not m:
            continue
        rid, grade, statement, applies = m.groups()
        if grade == "보류":
            continue
        dm = DETECT_RE.search(line)
        kind, n, unit, pat = "human", None, None, None
        if dm:
            p = DETECT_PARSE_RE.match(dm.group(1).strip())
            if not p:
                errors.append(f"{rid}: 검출 필드 형식 오류 {dm.group(1).strip()!r}"); continue
            kind, n, unit, pat = p.groups()
        rule = None
        if kind != "human":
            if pat is None:
                errors.append(f"{rid}: 검출 패턴 없음"); continue
            if kind == "density":
                if not (n and unit):
                    errors.append(f"{rid}: density 임계값 없음"); continue
                sev, thr = "S2", f"{n}/{unit}"
            else:
                sev, thr = "S1", ""
            # regex·density 는 정규식(백틱), literal 은 ` · ` 목록. validate_taste.py 와 같은 해석이다.
            rule = Rule(id=rid, category="취향", name=statement, severity=sev, detect=kind,
                        scopes={"prose", "list"}, genre="공통",
                        pattern=pat if kind == "literal" else f"`{pat}`", exception="", threshold=thr)
            compile_pattern(rule, errors)
        out.append(TasteRule(rid, grade, statement, applies, kind, rule))
    if errors:
        print("취향 문서 오류:\n  " + "\n  ".join(errors), file=sys.stderr); raise SystemExit(2)
    return (ver.group(1) if ver else ""), out


def handshake(version: str | None, rules: list) -> str:
    c = Counter(r.detect for r in rules)
    return (f"writing-taste {'없음' if version is None else (version or '?')} · 규칙 {len(rules)} (regex {c['regex']} · literal {c['literal']} · "
            f"density {c['density']} · human {c['human']})")


def check(text: str, rules: list, is_html: bool, teaching: set) -> dict:
    segs = segment_html(text, teaching) if is_html else segment_markdown(text, teaching)
    findings, human = [], []
    for tr in rules:
        if tr.rule is None:
            human.append(tr.id); continue
        fs, _raw = run_pattern_rule(tr.rule, segs)
        for f in fs:
            findings.append({"rule": tr.id, "grade": tr.grade, "line": f.line, "col": f.col,
                             "excerpt": f.excerpt, "detail": tr.statement, "scope": tr.applies,
                             "count": f.count, "threshold": f.threshold, "unit": f.unit})
    findings.sort(key=lambda f: (f["line"], f["col"], f["rule"]))
    by_grade = {g: 0 for g in GRADES}
    by_rule: dict = {}
    for f in findings:
        by_grade[f["grade"]] += 1
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {"findings": findings,
            "summary": {"total": len(findings), "by_grade": by_grade, "by_rule": by_rule,
                        "human": human, "strict_fail": by_grade["규칙"] > 0},
            "stats": {"chars_nospace": len("".join(normalize_text(text).split()))}}


def fmt_text(reports: list, version: str, rules: list) -> str:
    out = []
    for rep in reports:
        for f in rep["findings"]:
            out.append(f'{rep["file"]}:{f["line"]}:{f["col"]}  [{f["rule"]} {f["grade"]}] {f["detail"]}  '
                       f'"{f["excerpt"]}"  (적용: {f["scope"]})')
    tot = Counter()
    for rep in reports:
        tot.update(rep["summary"]["by_grade"])
    human = reports[0]["summary"]["human"] if reports else []
    out.append(f"규칙 {tot['규칙']} · 경향 {tot['경향']} · 관찰 {tot['관찰']}  |  {handshake(version, rules)}"
               f"  |  human {len(human)}: {', '.join(human) or '-'}")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="check_taste.py", add_help=True,
                                description="취향 문서의 검출 필드로 초고를 센다(읽기 전용).")
    p.add_argument("files", nargs="*", help="검사할 파일")
    p.add_argument("--doc", default=None, help="취향 문서 경로(기본 taste/writing-taste.md)")
    p.add_argument("--json", action="store_true", help="JSON 출력")
    p.add_argument("--strict", action="store_true", help="[규칙] finding 이 있으면 실패")
    p.add_argument("--list", dest="list_rules", action="store_true", help="핸드셰이크 + 규칙 목록")
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    a = build_parser().parse_args(argv)
    doc = Path(a.doc) if a.doc else TASTE_MD
    version, rules = load_taste(doc)
    if a.list_rules:
        print(handshake(version, rules))
        for r in rules:
            print(f"{r.id}  {r.grade}  {r.detect}  적용: {r.applies}  {r.statement}")
        return 0
    if not a.files:
        print("검사할 파일이 없다. --list 를 쓴다.", file=sys.stderr); return 2
    try:
        teaching = load_rules().teaching_headers
    except (SystemExit, OSError, ValueError):
        teaching = set()
    reports = []
    for name in a.files:
        p = Path(name)
        try:
            src = p.read_text(encoding="utf-8")
        except OSError as e:
            print(f"입력 오류: {name}: {e}", file=sys.stderr); return 2
        rep = check(src, rules, p.suffix.lower() in (".html", ".htm"), teaching)
        rep["file"] = str(name).replace("\\", "/")
        reports.append(rep)
    if a.json:
        payload = [{"tool": "check_taste", "doc_version": version, "doc": doc.as_posix(),
                    "doc_state": "missing" if version is None else "ok",
                    "rules_loaded": len(rules), **r} for r in reports]
        print(json.dumps(payload[0] if len(payload) == 1 else payload, ensure_ascii=False, indent=2))
    else:
        print(fmt_text(reports, version, rules))
    if a.strict and any(r["summary"]["strict_fail"] for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
