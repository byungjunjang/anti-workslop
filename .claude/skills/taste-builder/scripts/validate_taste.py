#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writing-taste.md ↔ cases.jsonl 정합 검사.

  python validate_taste.py --doc taste/writing-taste.md [--ledger taste/cases/cases.jsonl]
exit 0 = 통과 (stdout: OK rules=R cases=C), 1 = 위반 (stderr: E<n> 줄)
"""
import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]   # scripts → taste-builder → skills → .claude → 프로젝트 루트
DEFAULT_LEDGER = PROJECT_ROOT / "taste" / "cases" / "cases.jsonl"
RULE_RE = re.compile(r"^(W-\d+) \[(규칙|경향|관찰|보류)\] (.+?) — .*?근거: (.+?) \(n=(-?\d+)\)")
HEAD_RE = re.compile(r"케이스: (\d+)건 · 규칙 (\d+) · 경향 (\d+) · 관찰 (\d+) · 보류 (\d+)")
EVID_RE = re.compile(r"(-?)(T-\d{4,})")
WEIGHT = {"규칙": 2}
DETECT_FIELD_RE = re.compile(r" — 검출: (.*?)(?= — 갱신 |$)")
DETECT_PARSE_RE = re.compile(r"^(\S+)(?: (\d+)/(문서|문단|문장))?(?: `([^`]+)`)?$")
EXAMPLE_RE = re.compile(r" — 예: (.*?) → (.*?) — (?=검출: |갱신 )")
DETECT_KINDS = ("regex", "literal", "density", "human")
LITERAL_SEP = " · "   # check_ai_tells.py 와 같은 구분자 (공백 + U+00B7 + 공백)


def grade_for(n):
    if n >= 4:
        return "규칙"
    if n >= 2:
        return "경향"
    if n == 1:
        return "관찰"
    return "보류"


def _unquote(s):
    s = s.strip()
    if len(s) >= 2 and s[0] in "\"'“" and s[-1] in "\"'”":
        return s[1:-1]
    return s


def check_detect(rid, line, errors):
    """규칙 줄의 `검출` 필드를 검사한다. 없으면 human 으로 보고 통과."""
    m = DETECT_FIELD_RE.search(line)
    if not m:
        return
    p = DETECT_PARSE_RE.match(m.group(1).strip())
    if not p:
        errors.append(f"E11 검출 필드 형식 오류 ({rid}: {m.group(1).strip()!r})")
        return
    kind, n, unit, pat = p.groups()
    if kind not in DETECT_KINDS:
        errors.append(f"E10 검출 방식 오류 ({rid}: {kind})")
        return
    if kind == "human":
        return
    if pat is None:
        errors.append(f"E11 검출 패턴 없음 ({rid}: 백틱으로 감싼 패턴 필요)")
        return
    if kind == "density" and not (n and unit):
        errors.append(f"E11 density 임계값 없음 ({rid}: n/문서|문단|문장)")
        return
    if kind == "literal":
        needles = [t for t in pat.split(LITERAL_SEP) if t]
        count = lambda text: sum(text.count(t) for t in needles)
    else:
        try:
            rx = re.compile(pat)
        except re.error as e:
            errors.append(f"E11 정규식 컴파일 실패 ({rid}: {e})")
            return
        count = lambda text: len(rx.findall(text))
    ex = EXAMPLE_RE.search(line)
    if not ex:
        return
    before, after = _unquote(ex.group(1)), _unquote(ex.group(2))
    if (before, after) == ("전", "후"):
        return
    if count(before) < 1:
        errors.append(f"E12 검출이 예의 전에 매치하지 않음 ({rid})")
    if count(after) > 0:
        errors.append(f"E12 검출이 예의 후에 매치함 ({rid})")


def validate(doc_path, ledger_path):
    errors = []
    text = Path(doc_path).read_text(encoding="utf-8")
    cases = {}
    lp = Path(ledger_path)
    if lp.exists():
        for l in lp.read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cases[c["case_id"]] = c
    head = HEAD_RE.search(text)
    if not head:
        errors.append("E0 머리 집계 줄 없음")
    section = 0
    rules = {}
    grades = {"규칙": 0, "경향": 0, "관찰": 0, "보류": 0}
    for line in text.splitlines():
        m = re.match(r"^## (\d+)\.", line)
        if m:
            section = int(m.group(1))
            continue
        r = RULE_RE.match(line)
        if not r:
            continue
        rid, grade, _, evid, n_doc = r.group(1), r.group(2), r.group(3), r.group(4), int(r.group(5))
        if rid in rules:
            errors.append(f"E1 규칙 ID 중복 ({rid})")
        rules[rid] = grade
        grades[grade] += 1
        check_detect(rid, line, errors)
        n = 0
        has_neg = False
        for sign, cid in EVID_RE.findall(evid):
            if cid not in cases:
                errors.append(f"E2 없는 케이스 인용 ({rid}, {cid})")
                continue
            w = WEIGHT.get(cases[cid].get("kind"), 1)
            if sign == "-":
                n -= w
                has_neg = True
            else:
                n += w
        if n != n_doc:
            errors.append(f"E3 n 불일치 ({rid}: 문서 n={n_doc}, 원장 가중합 n={n})")
        expected = grade_for(n)
        if grade == "보류":
            if section != 7:
                errors.append(f"E4 보류 항목이 §7 밖 ({rid}, §{section})")
            if n > 0 and not has_neg:
                errors.append(f"E5 보류 근거 없음: 반대 케이스도 없고 n={n} ({rid})")
        else:
            if section == 7:
                errors.append(f"E4 §7에 보류 아닌 항목 ({rid})")
            if expected != grade:
                errors.append(f"E6 등급 불일치 ({rid}: 문서 {grade}, n={n} → {expected})")
    for cid, c in cases.items():
        if c.get("status") == "반영":
            if not c.get("rule_ids"):
                errors.append(f"E7 반영 케이스에 rule_ids 없음 ({cid})")
            for rid in c.get("rule_ids", []):
                if rid not in rules:
                    errors.append(f"E8 케이스가 없는 규칙을 가리킴 ({cid} → {rid})")
    if head:
        hc, hr, ht, ho, hh = (int(x) for x in head.groups())
        if hc != len(cases):
            errors.append(f"E9 머리 케이스 수 {hc} ≠ 원장 {len(cases)}")
        actual = (grades["규칙"], grades["경향"], grades["관찰"], grades["보류"])
        if (hr, ht, ho, hh) != actual:
            errors.append(f"E9 머리 등급 집계 {(hr, ht, ho, hh)} ≠ 본문 {actual}")
    return errors, len(rules), len(cases)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--doc", required=True)
    p.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    a = p.parse_args(argv)
    if not Path(a.doc).exists():
        print(f"E0 취향 문서 없음: {a.doc} — init_taste.py 로 만든다", file=sys.stderr)
        return 1
    errors, nr, nc = validate(a.doc, a.ledger)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"OK rules={nr} cases={nc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
