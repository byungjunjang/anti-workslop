# -*- coding: utf-8 -*-
"""check_ai_tells.py — principles/ai-tells-ko.md 의 규칙 표를 런타임에 읽어 초고의 AI 티를 찾는다 (읽기 전용).

  python -X utf8 check_ai_tells.py FILE... [--genre 줄글|개조식|all] [--json|--summary|--md] [--strict] [--rules PATH]
  python -X utf8 check_ai_tells.py --selftest      # 규칙 파일만으로 자체 검증. exit 0/2
  python -X utf8 check_ai_tells.py --list          # 핸드셰이크 한 줄 + 규칙 목록
  python -X utf8 check_ai_tells.py --explain human # 설명표 human 행 + §4 표 (진단이 규칙 파일 대신 읽는 묶음)

규칙은 코드에 두지 않는다. 표를 고치면 검사가 바뀐다.
"""
from __future__ import annotations
import argparse, bisect, html, json, re, sys, unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]
RULES_MD = ROOT / "principles" / "ai-tells-ko.md"
SB_SCRIPTS = ROOT / ".claude" / "skills" / "styleguide-builder" / "scripts"
sys.path.insert(0, str(SB_SCRIPTS))
from metrics import split_sentences, is_label  # noqa: E402  (styleguide-builder 내부 함수 재사용)

SEVERITIES = ("S1", "S2", "S3")
DETECTS = ("regex", "literal", "density", "structure", "human", "위임")
GENRES = ("공통", "줄글", "개조식")
SCOPES = ("prose", "list", "heading", "table")
RULE_HEADER = ["ID", "범주", "패턴", "심각도", "검출", "범위", "장르", "정규식·문자열", "예외", "임계값"]
NOTE_HEADER = ["ID", "판정 질문", "지양 예", "권장 예·수정 원칙", "유지 조건", "참조", "출처"]
TEACH_HEADER = ["왼쪽 헤더", "오른쪽 헤더"]
# STRUCTURE_KEYS 는 검출기 레지스트리 STRUCTURE_DETECTORS 에서 만든다(아래). 키 목록을 두 곳에 두지 않는다.
PATTERNED = ("regex", "literal", "density")   # 지양·권장 예로 자체 검증이 가능한 검출 방식
LITERAL_SEP = " · "                            # 공백 + U+00B7 + 공백
EXC_WINDOW = 60                                # 문장을 못 찾을 때 예외 판정에 쓰는 좌우 폭


def force_utf8_stdout():
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass


@dataclass
class Rule:
    id: str; category: str; name: str; severity: str; detect: str
    scopes: set; genre: str; pattern: str; exception: str; threshold: str
    question: str = ""; bad: str = ""; good: str = ""; keep: str = ""; refs: str = ""; source: str = ""
    compiled: object = None          # re.Pattern | list[str] | None
    exc_compiled: object = None      # re.Pattern | None
    exc_tokens: frozenset = frozenset()   # 예외 칸의 구조 토큰(EXC_TOKENS)
    structure_key: str = ""; structure_regex: object = None
    thr_n: int = 1; thr_unit: str = "문서"

    def scope_text(self) -> str:
        return ",".join(s for s in SCOPES if s in self.scopes)


@dataclass
class Ruleset:
    version: str; declared_count: int; rules: list; teaching_headers: set
    by_id: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 마스킹 — 검사에서 빼는 구간. Task 3 의 엔진도 이 함수를 쓴다.
# ---------------------------------------------------------------------------
# 홑따옴표('…' ‘…’)는 일부러 마스킹하지 않는다. AT-13 이 그 쌍을 보고,
# 장피엠 문체는 개념어를 홑따옴표로 적기 때문이다.
MASK_PATTERNS = [
    re.compile(r"`[^`\n]*`"),                 # 인라인 코드
    re.compile(r"https?://\S+"),              # URL
    re.compile(r"「[^」]*」"),                 # 인용
    re.compile(r"『[^』]*』"),
    re.compile(r'"[^"\n]*"'),
    re.compile(r"“[^”]*”"),
    re.compile(r"\[[^\]]*필요[^\]]*\]"),       # 자리표시자 [사례 필요: …]
    re.compile(r"</?[A-Za-z][^>\n]*>"),       # HTML 태그(주석 <!-- --> 는 AT-39 가 잡아야 하므로 남긴다)
]


def _blank(m: "re.Match") -> str:
    """길이와 줄 구조를 보존한 공백으로 바꾼다(오프셋과 ^/$ 가 그대로 유지된다)."""
    return "".join("\n" if ch == "\n" else " " for ch in m.group(0))


# 작성자 확인 트레일러 — 윤문 결과 파일 끝에 붙는 구역(2026-09-22). 읽는 사람이 한 파일에서
# 다 보게 하되, 검사기는 본문이 아닌 이 구역을 보지 않는다. 떼는 일은 check_all 이 한 번에 한다.
TRAILER_MARK = "<!-- anti-workslop:작성자 확인"


def strip_trailer(text: str) -> str:
    """작성자 확인 트레일러를 뗀 본문. 표시가 없으면 그대로 돌려준다."""
    i = text.find(TRAILER_MARK)
    return text if i < 0 else text[:i].rstrip() + "\n"


def mask(text: str) -> str:
    out = text
    for rx in MASK_PATTERNS:
        out = rx.sub(_blank, out)
    return out


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """split_sentences 가 돌려준 문장을 원문 오프셋에 되맞춘다(공백 정규화를 건너뛰고 비공백만 맞춘다)."""
    idx = [i for i, ch in enumerate(text) if not ch.isspace()]
    stream = "".join(text[i] for i in idx)
    spans, cur = [], 0
    for s in split_sentences(text):
        core = "".join(ch for ch in s if not ch.isspace())
        if not core:
            continue
        j = stream.find(core, cur)
        if j < 0:
            j = stream.find(core)
        if j < 0:
            continue
        spans.append((idx[j], idx[j + len(core) - 1] + 1))
        cur = j + len(core)
    return spans


def sentence_at(text: str, spans: list[tuple[int, int]], pos: int) -> str:
    """pos 를 품은 문장. 못 찾으면 ±EXC_WINDOW 창."""
    for a, b in spans:
        if a <= pos < b:
            return text[a:b]
    return text[max(0, pos - EXC_WINDOW): pos + EXC_WINDOW]


def find_hits(rule: Rule, masked: str) -> list[tuple[int, int]]:
    """마스킹된 텍스트에서 규칙의 원시 매치 위치."""
    if rule.compiled is None:
        return []
    if isinstance(rule.compiled, list):
        out = []
        for w in rule.compiled:
            start = 0
            while True:
                j = masked.find(w, start)
                if j < 0:
                    break
                out.append((j, j + len(w)))
                start = j + len(w)
        return sorted(out)
    return [(m.start(), m.end()) for m in rule.compiled.finditer(masked)]


def filtered_hits(rule: Rule, text: str) -> list[tuple[int, int, int]]:
    """마스킹한 텍스트의 매치 중 예외 문장에 든 것을 뺀 목록. (시작, 끝, 문장 번호).
    예외는 원문(마스킹 전) 문장에 대고 본다. selftest 의 count_raw 와 판정 엔진의 run_pattern_rule 이 같이 쓴다."""
    hits = find_hits(rule, mask(text))
    if not hits:
        return []
    spans = sentence_spans(text)
    out = []
    for a, b in hits:
        if rule.exc_compiled is not None and rule.exc_compiled.search(sentence_at(text, spans, a)):
            continue
        si = next((k for k, (x, y) in enumerate(spans) if x <= a < y), -1)
        out.append((a, b, si))
    return out


def count_raw(rule: Rule, text: str) -> int:
    """예외를 걸러낸 원시 매치 수."""
    return len(filtered_hits(rule, text))


# ---------------------------------------------------------------------------
# 규칙 파일 파싱
# ---------------------------------------------------------------------------
def split_table_row(line: str) -> list[str]:
    r"""마크다운 표 한 줄을 셀로 나눈다. `\|` 는 셀 구분이 아니라 문자 '|' 다."""
    line = line.strip()
    if line.startswith("|"): line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"): line = line[:-1]
    cells, buf, i = [], [], 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|"); i += 2; continue
        if ch == "|":
            cells.append("".join(buf).strip()); buf = []; i += 1; continue
        buf.append(ch); i += 1
    cells.append("".join(buf).strip())
    return cells


_SEP_CELL = re.compile(r"^:?-{2,}:?$")


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEP_CELL.match(c or "") for c in cells)


def find_tables(md: str) -> list[tuple[list[str], list[list[str]], int]]:
    """(헤더, 행들, 시작 행 번호) 목록. 구분 행(---)은 버린다."""
    out, lines = [], md.split("\n")
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("|"):
            i += 1; continue
        start = i
        block = []
        while i < len(lines) and lines[i].lstrip().startswith("|"):
            block.append(lines[i]); i += 1
        parsed = [split_table_row(b) for b in block]
        parsed = [p for p in parsed if not _is_separator(p)]
        if len(parsed) >= 2:
            out.append((parsed[0], parsed[1:], start + 1))
    return out


def parse_threshold(s: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)\s*/\s*(문장|문단|문서)", s.strip())
    if m: return int(m.group(1)), m.group(2)
    m = re.fullmatch(r"(\d+)\s*(항|자|%)", s.strip())  # structure 자유 형식
    if m: return int(m.group(1)), m.group(2)
    if not s.strip(): return 1, "문서"
    raise ValueError(f"임계값 형식 오류: {s!r}")


def _strip_ticks(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == "`" and s[-1] == "`" else s


EXC_TOKENS = {"마지막 세그먼트"}   # 예외 칸에 쓸 수 있는 구조 토큰. 뜻은 규칙 파일 §1-2


def compile_pattern(rule: Rule, errors: list[str]) -> None:
    src = _strip_ticks(rule.pattern)
    if rule.detect in ("human", "위임"):
        if src:
            errors.append(f"{rule.id}: {rule.detect} 규칙은 정규식·문자열 칸이 비어야 한다")
        return
    if not src:
        errors.append(f"{rule.id}: {rule.detect} 규칙에 정규식·문자열이 없다")
        return
    if rule.detect == "structure":
        key, _, rx = src.partition(" :: ")
        rule.structure_key = key.strip()
        if rule.structure_key not in STRUCTURE_KEYS:
            errors.append(f"{rule.id}: 모르는 structure 키 {rule.structure_key!r}")
        if rx.strip():
            if "\\b" in rx: errors.append(f"{rule.id}: 정규식에 \\b 금지")
            try: rule.structure_regex = re.compile(rx.strip(), re.M)
            except re.error as e: errors.append(f"{rule.id}: 정규식 오류 {e}")
    else:
        is_regex = rule.pattern.strip().startswith("`")
        if is_regex:
            if "\\b" in src: errors.append(f"{rule.id}: 정규식에 \\b 금지")
            try: rule.compiled = re.compile(src, re.M)
            except re.error as e: errors.append(f"{rule.id}: 정규식 오류 {e}")
        else:
            rule.compiled = [w.strip() for w in src.split(LITERAL_SEP) if w.strip()]
            if not rule.compiled: errors.append(f"{rule.id}: literal 목록 비어 있음")
    if rule.exception.strip():
        parts = [x.strip() for x in rule.exception.split(LITERAL_SEP) if x.strip()]
        rule.exc_tokens = frozenset(x for x in parts if x in EXC_TOKENS)
        exc_src = _strip_ticks(LITERAL_SEP.join(x for x in parts if x not in EXC_TOKENS))
        if exc_src:
            if "\\b" in exc_src: errors.append(f"{rule.id}: 예외 정규식에 \\b 금지")
            try: rule.exc_compiled = re.compile(exc_src)
            except re.error as e: errors.append(f"{rule.id}: 예외 정규식 오류 {e}")
    if rule.detect in ("density", "structure") and rule.severity in ("S2", "S3") and not rule.threshold.strip():
        errors.append(f"{rule.id}: {rule.detect} 규칙은 임계값 필수")
    try:
        rule.thr_n, rule.thr_unit = parse_threshold(rule.threshold)
    except ValueError as e:
        errors.append(f"{rule.id}: {e}")


def load_rules(path: Path = RULES_MD) -> Ruleset:
    """규칙표·설명표·교육용 헤더를 읽고 검증한다. 오류가 하나라도 있으면 SystemExit(2)."""
    md = path.read_text(encoding="utf-8")
    md = unicodedata.normalize("NFC", md.replace("\r\n", "\n"))
    ver = re.search(r"^버전:\s*(\S+)$", md, re.M); cnt = re.search(r"^규칙 수:\s*(\d+)$", md, re.M)
    errors = []
    if not ver or not cnt: errors.append("머리에 '버전:'·'규칙 수:'가 필요")
    tables = find_tables(md)
    rule_tbl = next((t for t in tables if t[0][:10] == RULE_HEADER), None)
    note_tbl = next((t for t in tables if t[0][:7] == NOTE_HEADER), None)
    teach_tbl = next((t for t in tables if t[0][:2] == TEACH_HEADER), None)
    if not rule_tbl or not note_tbl or not teach_tbl:
        errors.append("규칙표/설명표/교육용 헤더표 중 하나를 찾지 못함")
        print("규칙 파일 오류:\n  " + "\n  ".join(errors), file=sys.stderr); raise SystemExit(2)

    rules, by_id = [], {}
    for row in rule_tbl[1]:
        if len(row) < 10:
            errors.append(f"규칙표 열 부족({len(row)}): {row[:1]}"); continue
        rid, cat, name, sev, det, scope, genre, pat, exc, thr = row[:10]
        if not re.fullmatch(r"AT-\d\d", rid):
            errors.append(f"ID 형식 오류: {rid!r}"); continue
        if rid in by_id:
            errors.append(f"{rid}: 중복 ID"); continue
        if sev not in SEVERITIES: errors.append(f"{rid}: 모르는 심각도 {sev!r}")
        if det not in DETECTS: errors.append(f"{rid}: 모르는 검출 {det!r}")
        if genre not in GENRES: errors.append(f"{rid}: 모르는 장르 {genre!r}")
        scopes = {s.strip() for s in scope.split(",") if s.strip()}
        if not scopes or not scopes <= set(SCOPES): errors.append(f"{rid}: 모르는 범위 {scope!r}")
        if not name: errors.append(f"{rid}: 패턴 이름이 비어 있다")
        r = Rule(id=rid, category=cat, name=name, severity=sev, detect=det, scopes=scopes,
                 genre=genre, pattern=pat, exception=exc, threshold=thr)
        if det in DETECTS:
            compile_pattern(r, errors)
        rules.append(r); by_id[rid] = r

    notes = {}
    for row in note_tbl[1]:
        if len(row) < 7:
            errors.append(f"설명표 열 부족({len(row)}): {row[:1]}"); continue
        if not re.fullmatch(r"AT-\d\d", row[0]):
            errors.append(f"설명표 ID 형식 오류: {row[0]!r}"); continue
        if row[0] in notes: errors.append(f"{row[0]}: 설명표 중복 ID"); continue
        notes[row[0]] = row[:7]
    only_rule = sorted(set(by_id) - set(notes))
    only_note = sorted(set(notes) - set(by_id))
    if only_rule: errors.append("설명표에 없는 ID: " + ", ".join(only_rule))
    if only_note: errors.append("규칙표에 없는 ID: " + ", ".join(only_note))
    for rid, row in notes.items():
        r = by_id.get(rid)
        if r is None: continue
        r.question, r.bad, r.good, r.keep, r.refs, r.source = row[1], row[2], row[3], row[4], row[5], row[6]

    teaching = set()
    for row in teach_tbl[1]:
        if len(row) >= 2 and row[0] and row[1]:
            teaching.add((row[0], row[1]))

    declared = int(cnt.group(1)) if cnt else 0
    if cnt and len(rules) != declared:
        errors.append(f"규칙 수 불일치: 머리 {declared} vs 규칙표 {len(rules)}")
    if errors:
        print("규칙 파일 오류:\n  " + "\n  ".join(errors), file=sys.stderr); raise SystemExit(2)
    return Ruleset(version=ver.group(1) if ver else "", declared_count=declared,
                   rules=rules, teaching_headers=teaching, by_id=by_id)


# ---------------------------------------------------------------------------
# 핸드셰이크 · 목록 · 자체 검증
# ---------------------------------------------------------------------------
def active_rules(rs: Ruleset, genre: str | None) -> list:
    return [r for r in rs.rules if genre == "all" or r.genre == "공통" or r.genre == genre]


def handshake_line(rs: Ruleset, genre: str | None) -> str:
    c = Counter(r.detect for r in rs.rules)
    active = active_rules(rs, genre)
    g = genre or "공통"
    return (f"ai-tells-ko {rs.version} · 규칙 {len(rs.rules)} (regex {c['regex']} · literal {c['literal']} · "
            f"density {c['density']} · structure {c['structure']} · human {c['human']} · 위임 {c['위임']}) · "
            f"활성 {len(active)} (--genre {g})")


def list_rules(rs: Ruleset, genre: str | None) -> int:
    print(handshake_line(rs, genre))
    for r in rs.rules:
        print(f"{r.id}  {r.severity}  {r.detect}  {r.scope_text()}  {r.genre}  {r.name}")
    return 0


def _section(md: str, num: int) -> str:
    """`## N.` 표제부터 다음 `## ` 앞까지."""
    m = re.search(rf"^## {num}\.[^\n]*\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1).strip("\n") if m else ""


def explain_human(rs: Ruleset, md: str) -> str:
    """진단이 읽는 원칙 묶음. 설명표의 human 행(판정 질문·지양·권장·유지 조건)과 §4 표만.
    규칙 파일 전문 대신 이것을 읽는다. regex·density 행은 검사기가 이미 셌으므로 싣지 않는다."""
    out = ["## 원칙 · 사람 판단 규칙 (설명표 human 행)", "",
           "| ID | 판정 질문 | 지양 예 | 권장 예·수정 원칙 | 유지 조건 |", "|---|---|---|---|---|"]
    for r in rs.rules:
        if r.detect == "human":
            cells = [r.id, r.question, r.bad, r.good, r.keep]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    out += ["", "## 원칙 · §4 바꾸지 않는 것", "", _section(md, 4)]
    return "\n".join(out)


def _positive_need(rule: Rule) -> int:
    """지양 예 한 덩이에서 요구하는 최소 매치 수."""
    if rule.detect == "density" and rule.thr_unit in ("문장", "문단"):
        return max(1, rule.thr_n)
    return 1


def selftest(rs: Ruleset) -> int:
    fails: list[str] = []
    # (a) 규칙 수
    if not rs.rules:
        fails.append("(a) 규칙이 하나도 없다")
    # (b) 두 표의 ID 집합 — load_rules 가 이미 막지만 명시적으로 다시 본다
    missing = [r.id for r in rs.rules if not r.question and not r.bad and not r.good]
    if missing:
        fails.append("(b) 설명표 행이 비어 있다: " + ", ".join(missing))
    pos = neg = 0
    for r in rs.rules:
        if r.detect in PATTERNED:
            need = _positive_need(r)
            got = count_raw(r, r.bad)
            if got >= need:
                pos += 1
            else:
                fails.append(f"(c) {r.id} 지양 예 매치 {got} < {need} — {r.bad[:40]!r}")
            bad_neg = count_raw(r, r.good)
            if bad_neg == 0:
                neg += 1
            else:
                fails.append(f"(d) {r.id} 권장 예가 매치 {bad_neg} — {r.good[:40]!r}")
        # (e) structure 키
        if r.detect == "structure" and r.structure_key not in STRUCTURE_KEYS:
            fails.append(f"(e) {r.id} 모르는 structure 키 {r.structure_key!r}")
    # (f) 교육용 헤더표
    if len(rs.teaching_headers) < 5:
        fails.append(f"(f) 교육용 헤더 행 {len(rs.teaching_headers)} < 5")
    if fails:
        print("selftest FAIL")
        for f in fails:
            print("  " + f)
        return 2
    print(f"selftest OK · 규칙 {len(rs.rules)} · 양성 {pos} · 음성 {neg}")
    return 0


# ---------------------------------------------------------------------------
# 세그먼트 — 검사 단위. 규칙의 '범위' 칸이 kind 를 고른다.
# ---------------------------------------------------------------------------
ZERO_WIDTH = re.compile(r"[\u200b\ufeff]")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(\s{0,3}#{1,6}(?:\s+|$))(.*)$")
QUOTE = re.compile(r"^(\s{0,3}>\s?)(.*)$")
LIST_MARK = re.compile(r"^(\s*)(?:(?:[-*+]|\d{1,3}[.)]|[가나다라마바사아자차카타파하][.)])\s+|"
                       r"[□○▪◦●·※•■▶◆]\s*|[\u2460-\u2473]\s*)")
THEMATIC = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")   # 구분선. 문단이 아니다
SETEXT = re.compile(r"^\s{0,3}(?:=+|-+)\s*$")                   # 앞 줄이 글이면 Setext 표제 밑줄, 아니면 구분선
EXEMPT_MARK = re.compile(r"<!--\s*style-exempt\s*-->")
TEACH_MARK = re.compile(r"<!--\s*style-teaching\s*-->")
COMMENT_ONLY = re.compile(r"^\s*<!--.*?-->\s*$")
SHORT_DOC_SENTENCES = 8         # 이보다 문장이 적으면 문서 단위 S2 를 info 로 강등한다


@dataclass
class Seg:
    kind: str                   # prose|heading|list|table|quote|code|frontmatter|exempt
    line_start: int
    line_end: int
    text: str                   # 검사 대상 텍스트(표지·태그를 걷어낸 뒤)
    raw: str                    # 원본 줄
    index: list = field(default_factory=list)   # (텍스트 오프셋, 행, 0-기준 열, 길이)
    depth: int = 0                              # 목록 깊이. 최상위 li 가 0, 그 아래가 1

    def locate(self, pos: int) -> tuple[int, int]:
        """세그먼트 텍스트의 오프셋을 원본 (행, 열 1-기준)로 되돌린다."""
        best = (self.line_start, 1)
        for start, ln, c0, length in self.index:
            if start <= pos < start + length:
                return ln, c0 + (pos - start) + 1
            if start <= pos:
                best = (ln, c0 + length + 1)
        return best


def normalize_text(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    return ZERO_WIDTH.sub("", unicodedata.normalize("NFC", t))


def _squeeze(s: str) -> str:
    return "".join(s.split())


def _mkseg(kind: str, pieces: list, raw: str | None = None, join: str = "\n") -> Seg:
    """pieces = [(행, 0-기준 열, 텍스트)]. 조각을 이어 붙이며 오프셋 표를 만든다."""
    parts, index, pos = [], [], 0
    for k, (ln, c0, s) in enumerate(pieces):
        if k:
            parts.append(join); pos += len(join)
        index.append((pos, ln, c0, len(s)))
        parts.append(s); pos += len(s)
    text = "".join(parts)
    return Seg(kind, pieces[0][0], pieces[-1][0], text, raw if raw is not None else text, index)


def split_table_row_spans(line: str) -> list:
    """split_table_row 와 같은 규칙으로 나누되 셀마다 [(0-기준 열, 조각)] 을 준다(`\\|` 는 문자 '|')."""
    n = len(line)
    s, e = 0, n
    while s < n and line[s].isspace(): s += 1
    while e > s and line[e - 1].isspace(): e -= 1
    if s < e and line[s] == "|": s += 1
    if e > s and line[e - 1] == "|" and not (e - 2 >= s and line[e - 2] == "\\"): e -= 1
    cells, buf, i = [], [], s
    def flush():
        a, b = 0, len(buf)
        while a < b and buf[a][0].isspace(): a += 1
        while b > a and buf[b - 1][0].isspace(): b -= 1
        runs = []
        for ch, off in buf[a:b]:
            if runs and runs[-1][0] + len(runs[-1][1]) == off:
                runs[-1][1] += ch
            else:
                runs.append([off, ch])
        cells.append([(o, t) for o, t in runs])
    while i < e:
        ch = line[i]
        if ch == "\\" and i + 1 < e and line[i + 1] == "|":
            buf.append(("|", i)); i += 2; continue
        if ch == "|":
            flush(); buf = []; i += 1; continue
        buf.append((ch, i)); i += 1
    flush()
    return cells


def _cell_text(cell: list) -> str:
    return "".join(t for _, t in cell)


def _exempt_lines(lines: list) -> set:
    """<!-- style-exempt --> 가 든 블록(빈 줄로 갈린 덩이)의 행 번호. 주석만 있는 블록이면 다음 블록까지."""
    out, n, i = set(), len(lines), 0
    while i < n:
        if not lines[i].strip():
            i += 1; continue
        j = i
        while j < n and lines[j].strip():
            j += 1
        block = range(i, j)
        if any(EXEMPT_MARK.search(lines[k]) for k in block):
            out.update(k + 1 for k in block)
            if all(COMMENT_ONLY.match(lines[k]) for k in block):
                k = j
                while k < n and not lines[k].strip():
                    k += 1
                m = k
                while m < n and lines[m].strip():
                    m += 1
                out.update(x + 1 for x in range(k, m))
        i = j
    return out


def _table_segs(lines: list, i: int, j: int, teaching: set, prev_line: str) -> list:
    rows = []
    for k in range(i, j):
        cells = split_table_row_spans(lines[k])
        if _is_separator([_cell_text(c) for c in cells]):
            continue
        rows.append((k + 1, cells))
    span = [(k + 1, 0, lines[k]) for k in range(i, j)]
    if not rows:
        return []                          # 구분선만 있는 표 조각. 문단이 아니다
    header = [_cell_text(c) for c in rows[0][1]]
    if tuple(header[:2]) in teaching or (header and header[0] == "ID") or TEACH_MARK.search(prev_line):
        return [_mkseg("exempt", span)]
    if len(rows) == 1:
        return [_mkseg("exempt", span)]    # 헤더만 있는 표. 헤더 셀은 본문 표에서도 검사하지 않으므로 같은 대우다. prose 로 떨어뜨리지 않는다
    out = []
    for ln, cells in rows[1:]:
        for cell in cells:
            txt = _cell_text(cell)
            if not txt:
                continue
            out.append(_mkseg("table", [(ln, c0, t) for c0, t in cell], raw=txt, join=""))
    return out


_TEACHING_CACHE: set | None = None


def _default_teaching() -> set:
    """teaching 인자 없이 부르는 쪽(Task 5 등)을 위해 규칙 파일의 교육용 헤더를 한 번만 읽어 둔다."""
    global _TEACHING_CACHE
    if _TEACHING_CACHE is None:
        try:
            _TEACHING_CACHE = load_rules().teaching_headers
        except (SystemExit, OSError, ValueError):   # 로더는 오류에 SystemExit(2) 를 낸다. 규칙 파일이 없거나 깨져도 분할은 계속된다
            _TEACHING_CACHE = set()
    return _TEACHING_CACHE


def segment_markdown(text: str, teaching: set | None = None) -> list:
    text = normalize_text(text)
    lines = text.split("\n")
    n = len(lines)
    teaching = _default_teaching() if teaching is None else teaching
    exempt = _exempt_lines(lines)
    segs, i = [], 0
    if lines and lines[0].strip() == "---":
        j = 1
        while j < n and lines[j].strip() != "---":
            j += 1
        if j < n:
            segs.append(_mkseg("frontmatter", [(k + 1, 0, lines[k]) for k in range(0, j + 1)]))
            i = j + 1
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1; continue
        mf = FENCE.match(line)
        if mf:
            fence, j = mf.group(1), i + 1
            while j < n:
                m2 = FENCE.match(lines[j])
                if m2 and m2.group(1)[0] == fence[0] and len(m2.group(1)) >= len(fence):
                    break
                j += 1
            end = min(j, n - 1)
            segs.append(_mkseg("code", [(k + 1, 0, lines[k]) for k in range(i, end + 1)]))
            i = end + 1; continue
        if line.lstrip().startswith("|"):
            j = i
            while j < n and lines[j].lstrip().startswith("|"):
                j += 1
            prev = next((lines[k] for k in range(i - 1, -1, -1) if lines[k].strip()), "")
            segs.extend(_table_segs(lines, i, j, teaching, prev))
            i = j; continue
        if QUOTE.match(line):
            pieces, j = [], i
            while j < n and QUOTE.match(lines[j]):
                mq = QUOTE.match(lines[j])
                pieces.append((j + 1, len(mq.group(1)), mq.group(2)))
                j += 1
            segs.append(_mkseg("quote", pieces))
            i = j; continue
        mh = HEADING.match(line)
        if mh:
            segs.append(_mkseg("heading", [(i + 1, len(mh.group(1)), mh.group(2))]))
            i += 1; continue
        if THEMATIC.match(line):
            i += 1; continue               # 구분선은 문단이 아니다(문단 수·마지막 세그먼트 계산에서 뺀다)
        ml = LIST_MARK.match(line)
        if ml:
            indent = len(ml.group(1))
            pieces, j = [(i + 1, ml.end(), line[ml.end():])], i + 1
            while j < n and lines[j].strip() and not LIST_MARK.match(lines[j]) \
                    and not HEADING.match(lines[j]) and not FENCE.match(lines[j]) \
                    and not lines[j].lstrip().startswith("|") \
                    and (len(lines[j]) - len(lines[j].lstrip())) > indent:
                stripped = lines[j].lstrip()
                pieces.append((j + 1, len(lines[j]) - len(stripped), stripped))
                j += 1
            segs.append(_mkseg("list", pieces))
            i = j; continue
        if i + 1 < n and SETEXT.match(lines[i + 1]) and not COMMENT_ONLY.match(line):
            segs.append(_mkseg("heading", [(i + 1, 0, line.strip())]))   # Setext 표제. 밑줄은 구분선이 아니다
            i += 2; continue
        pieces, j = [], i
        while j < n and lines[j].strip() and not FENCE.match(lines[j]) \
                and not lines[j].lstrip().startswith("|") and not QUOTE.match(lines[j]) \
                and not HEADING.match(lines[j]) and not LIST_MARK.match(lines[j]) \
                and not THEMATIC.match(lines[j]):
            pieces.append((j + 1, 0, lines[j]))
            j += 1
        if not pieces:
            pieces, j = [(i + 1, 0, lines[i])], i + 1
        i = j
        if all(COMMENT_ONLY.match(p[2]) for p in pieces):
            continue                       # HTML 주석 줄만 있는 블록은 버린다
        segs.append(_mkseg("prose", pieces))
    for s in segs:
        if any(ln in exempt for ln in range(s.line_start, s.line_end + 1)):
            s.kind = "exempt"
    return segs


# --- HTML -------------------------------------------------------------------
HTML_BLANK = ("script", "style", "pre", "code", "svg", "table")
HTML_OWNER = {"h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading", "h5": "heading",
              "h6": "heading", "blockquote": "quote", "li": "list", "p": "prose"}
HTML_LISTS = ("ul", "ol")
HTML_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# 태그 하나씩 읽어 스택을 쌓는다. 여는 태그와 닫는 태그를 정규식으로 짝지으면 중첩 목록에서
# 상위 li 가 첫 하위 li 를 삼키고 하위 목록 뒤의 상위 텍스트를 잃는다(2026-09-15 재현).
HTML_TOKEN = re.compile(r"<!--.*?-->|<(/?)([A-Za-z][A-Za-z0-9]*)\b[^>]*?(/?)>|<![^>]*>|<\?[^>]*>", re.S)
TAG_RE = re.compile(r"<[^>]*>")
ENT_RE = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]{1,31});")


def _line_starts(text: str) -> list:
    out, pos = [0], 0
    for line in text.split("\n")[:-1]:
        pos += len(line) + 1
        out.append(pos)
    return out


def _line_col(starts: list, off: int) -> tuple[int, int]:
    k = bisect.bisect_right(starts, off) - 1
    return k + 1, off - starts[k] + 1


def _strip_tags_mapped(frag: str, base: int) -> tuple[str, list]:
    """태그를 지우고 엔티티를 풀되 글자마다 원본 오프셋을 남긴다."""
    out, offs, i, n = [], [], 0, len(frag)
    while i < n:
        if frag[i] == "<":
            m = TAG_RE.match(frag, i)
            if m:
                i = m.end(); continue
        if frag[i] == "&":
            m = ENT_RE.match(frag, i)
            if m:
                for ch in html.unescape(m.group(0)):
                    out.append(ch); offs.append(base + i)
                i = m.end(); continue
        out.append(frag[i]); offs.append(base + i); i += 1
    return "".join(out), offs


def _blank_html_elements(text: str) -> tuple[str, bytearray]:
    """검사에서 뺄 요소를 같은 길이의 공백으로 지운다(Task 2 의 `_blank`).

    길이를 보존해야 같은 줄에서 뒤따르는 글자의 열이 밀리지 않는다.
    지운 자리를 `holes` 로 함께 돌려주어, 세그먼트 텍스트에서 그 자리를 아예 빼고
    오프셋 런이 거기서 끊기게 한다 — 발췌가 원문에서 이어진 한 토막임을 보장한다.
    """
    blanked, holes = text, bytearray(len(text))

    def record(m: "re.Match") -> str:
        for k in range(m.start(), m.end()):
            holes[k] = 1
        return _blank(m)

    for tag in HTML_BLANK:
        blanked = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}\s*>", record, blanked, flags=re.I | re.S)
    return blanked, holes


def segment_html(text: str, teaching: set | None = None) -> list:
    """블록 요소마다 '직접 붙은 텍스트'를 모아 세그먼트로 만든다. 글자마다 원본 오프셋을 남겨
    행·열이 원본 자리와 같다. li 는 깊이를 담고, <!-- style-exempt --> 다음 요소는 안쪽까지 exempt 다."""
    text = normalize_text(text)
    blanked, holes = _blank_html_elements(text)
    starts = _line_starts(blanked)
    segs: list = []
    stack: list = []                 # [태그, 소유자|None, 면제 뿌리 여부]
    pending_exempt = False

    def owner_top():
        for e in reversed(stack):
            if e[1] is not None:
                return e[1]
        return None

    def emit(o: dict) -> None:
        chars = o["chars"]
        a, b = 0, len(chars)
        while a < b and chars[a][0].isspace(): a += 1
        while b > a and chars[b - 1][0].isspace(): b -= 1
        chars = chars[a:b]
        if not chars:
            return
        body = "".join(c for c, _ in chars)
        offs = [x for _, x in chars]
        index, k = [], 0
        while k < len(body):
            ln, col = _line_col(starts, offs[k])
            j = k + 1
            while j < len(body) and offs[j] == offs[j - 1] + 1 and _line_col(starts, offs[j])[0] == ln:
                j += 1
            index.append((k, ln, col - 1, j - k))
            k = j
        segs.append(Seg(o["kind"], index[0][1], index[-1][1], body, body, index, o["depth"]))

    def close(i: int) -> None:
        while len(stack) > i:
            e = stack.pop()
            if e[1] is not None:
                emit(e[1])

    def add_text(a: int, b: int) -> None:
        o = owner_top()
        if o is None or a >= b:
            return
        body, offs = _strip_tags_mapped(blanked[a:b], a)
        for ch, off in zip(body, offs):
            if not holes[off]:                                        # 지운 요소 자리는 뺀다
                o["chars"].append((ch, off))

    pos = 0
    for m in HTML_TOKEN.finditer(blanked):
        add_text(pos, m.start())
        pos = m.end()
        tok = m.group(0)
        if tok.startswith("<!--"):
            if EXEMPT_MARK.fullmatch(tok):
                pending_exempt = True
            continue
        if m.group(2) is None:
            continue
        tag = m.group(2).lower()
        if m.group(1) == "/":
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == tag:
                    close(i)
                    break
            continue
        exempt_root, pending_exempt = pending_exempt, False
        if tag in ("p", "li") and stack and stack[-1][0] == tag:
            close(len(stack) - 1)                                     # 닫는 태그를 생략한 p·li
        owner = None
        if tag in HTML_OWNER and (tag == "li" or owner_top() is None):
            exempt = exempt_root or any(e[2] for e in stack)
            depth = max(sum(1 for e in stack if e[0] in HTML_LISTS) - 1, 0) if tag == "li" else 0
            owner = {"kind": "exempt" if exempt else HTML_OWNER[tag], "chars": [], "depth": depth}
        if tag in HTML_VOID or m.group(3) == "/":
            continue
        stack.append([tag, owner, exempt_root])
    add_text(pos, len(blanked))
    close(0)
    segs.sort(key=lambda s: (s.line_start, s.index[0][2]))
    return segs


# ---------------------------------------------------------------------------
# 판정 엔진
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    rule: str; severity: str; line: int; col: int; excerpt: str; detail: str
    fix: str = ""; scope: str = ""; count: int = 1; threshold: int = 1; unit: str = ""
    demoted: bool = False

    def as_dict(self) -> dict:
        d = {"rule": self.rule, "severity": self.severity, "line": self.line, "col": self.col,
             "excerpt": self.excerpt, "detail": self.detail, "fix": self.fix, "scope": self.scope,
             "count": self.count, "threshold": self.threshold, "unit": self.unit}
        if self.demoted:
            d["demoted"] = True
        return d


@dataclass
class Report:
    genre: str
    rules_active: int
    findings: list
    summary: dict
    stats: dict
    rows: list = field(default_factory=list)
    file: str = ""


def sentences_with_offsets(text: str) -> list:
    """[(시작, 끝, 문장)] — 원문 오프셋 그대로."""
    return [(a, b, text[a:b]) for a, b in sentence_spans(text)]


def excerpt_at(text: str, a: int, b: int, width: int = 40,
               lo_lim: int = 0, hi_lim: int | None = None) -> str:
    """원문 그대로의 발췌 한 줄(매치 앞 10자 ~ 뒤 width 자, 줄과 오프셋 런을 넘지 않는다)."""
    hi_lim = len(text) if hi_lim is None else hi_lim
    lo = max(text.rfind("\n", 0, a) + 1, a - 10, lo_lim)
    hi = text.find("\n", a)
    if hi < 0:
        hi = len(text)
    heads = list(re.finditer(r"[.!?…]\s+", text[lo:a]))   # 앞 문장 꼬리는 잘라낸다
    if heads:
        lo += heads[-1].end()
    return text[lo: min(hi, hi_lim, max(b, a + width))].strip()


def _run_bounds(seg: "Seg", pos: int) -> tuple[int, int]:
    """pos 를 품은 오프셋 런의 [시작, 끝). 이 구간은 원문에서 이어진 한 토막이다."""
    for start, _ln, _c0, length in seg.index:
        if start <= pos < start + length:
            return start, start + length
    return 0, len(seg.text)


def fix_hint(rule: Rule) -> str:
    """설명표 '권장 예·수정 원칙' 칸의 마지막 문장이 수정 원칙이다."""
    parts = split_sentences(rule.good)
    return (parts[-1] if parts else rule.good).strip()


def _finding(rule: Rule, seg: Seg, a: int, b: int, count: int, unit: str, thr: int | None = None) -> Finding:
    ln, col = seg.locate(a)
    lo_lim, hi_lim = _run_bounds(seg, a)
    return Finding(rule=rule.id, severity=rule.severity, line=ln, col=col,
                   excerpt=excerpt_at(seg.text, a, b, lo_lim=lo_lim, hi_lim=hi_lim),
                   detail=rule.name, fix=fix_hint(rule),
                   scope=seg.kind, count=count, threshold=rule.thr_n if thr is None else thr,
                   unit=unit if unit in ("문장", "문단", "문서") else "문서")   # structure 임계 단위(자·%·항)는 밖으로 내지 않는다


def run_pattern_rule(rule: Rule, segs: list) -> tuple[list, int]:
    """regex·literal·density 공통 경로. (finding 목록, 원시 매치 수)."""
    hits = []
    for s in segs:
        if s.kind not in rule.scopes:
            continue
        hits.extend((s, a, b, si) for a, b, si in filtered_hits(rule, s.text))
    if not hits:
        return [], 0
    if rule.severity == "S1":
        return [_finding(rule, s, a, b, 1, "문장", thr=1) for s, a, b, _ in hits], len(hits)
    unit = rule.thr_unit if rule.thr_unit in ("문장", "문단", "문서") else "문서"
    groups: dict = {}
    for k, (s, a, b, si) in enumerate(hits):
        if unit == "문서":
            key = "문서"
        elif unit == "문단":
            key = id(s)
        else:
            key = (id(s), si if si >= 0 else -1 - k)
        groups.setdefault(key, []).append((s, a, b))
    out = []
    for g in groups.values():
        if len(g) < max(1, rule.thr_n):
            continue
        s, a, b = g[0]
        out.append(_finding(rule, s, a, b, len(g), unit))
    return out, len(hits)


# --- structure 검출기 -------------------------------------------------------
BOLD_LABEL = re.compile(r"^\*\*([^*:：\n]+)[:：]?\*\*")
EMOJI_RX = re.compile("[\U0001F300-\U0001FAFF]|[\u2600-\u27BF]\uFE0F|"
                      "[\u2705\u274C\u274E\u2728\u2B50\u26A1\u26D4\u2757\u2753]")
PARA_CLOSER_RX = re.compile(r"^(?:결국|즉|이처럼|이렇듯|요컨대|그래서)")
SHORT_SENTENCE = 12
SHORT_RUN_LEN = 3


def _list_blocks(segs: list) -> list:
    blocks, cur = [], []
    for s in segs:
        if s.kind != "list":
            if cur: blocks.append(cur); cur = []
            continue
        if cur and s.line_start > cur[-1].line_end + 1:
            blocks.append(cur); cur = []
        cur.append(s)
    if cur:
        blocks.append(cur)
    return blocks


def _proses(segs: list) -> list:
    return [s for s in segs if s.kind == "prose"]


def _para_segs(rule: Rule, segs: list) -> list:
    """규칙 범위에 list 가 있으면 목록 항목도 문단으로 본다(개조식 문서는 prose 세그먼트가 없다)."""
    kinds = {"prose", "list"} if "list" in rule.scopes else {"prose"}
    return [s for s in segs if s.kind in kinds]


def _is_label_phrase(label: str) -> bool:
    """라벨은 문장이 아니다. 마침표·물음표·느낌표로 끝나면 굵은 소제목 문장으로 본다."""
    t = label.strip()
    return bool(t) and t[-1] not in ".!?"


def _label_runs(block: list) -> list:
    """목록 블록을 굵은 라벨 항목의 연속 구간으로 나눈다. 문장 라벨(마침표로 끝남)이나 라벨 없는 항목이 구간을 끊는다."""
    runs, cur = [], []
    for s in block:
        m = BOLD_LABEL.match(s.text.lstrip())
        if m and _is_label_phrase(m.group(1)):
            cur.append((s, m))
        else:
            if cur: runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    return runs


def st_bold_label_run(rule: Rule, segs: list) -> list:
    out, need = [], max(1, rule.thr_n)
    for block in _list_blocks(segs):
        for run in _label_runs(block):
            if len(run) < need:
                continue
            echo = 0
            for s, m in run:
                label = _squeeze(m.group(1))
                body = _squeeze(s.text.lstrip()[m.end():])
                head = "".join(ch for ch in label if "가" <= ch <= "힣")[:2]
                if label and (label in body or (len(head) == 2 and head in body)):
                    echo += 1
            if echo * 2 >= len(run):
                s = run[0][0]
                out.append(_finding(rule, s, 0, min(len(s.text), 24), len(run), rule.thr_unit))
    return out


def st_heading_echo(rule: Rule, segs: list) -> list:
    out = []
    for k, s in enumerate(segs):
        if s.kind != "heading":
            continue
        nxt, kinds = None, ({"prose", "list"} if "list" in rule.scopes else {"prose"})
        for t in segs[k + 1:]:
            if t.kind == "heading":
                break
            if t.kind in kinds:
                nxt = t; break
        if nxt is None or len(nxt.text) > rule.thr_n:
            continue
        title = _squeeze(s.text)
        if title and _squeeze(nxt.text).startswith(title):
            out.append(_finding(rule, nxt, 0, min(len(nxt.text), 30), 1, rule.thr_unit))
    return out


def st_emoji(rule: Rule, segs: list) -> list:
    out, last = [], None
    if "마지막 세그먼트" in rule.exc_tokens:
        paras = [s for s in segs if s.kind in ("prose", "list")]
        last = paras[-1] if paras else None
    hits = []
    for s in segs:
        if s.kind not in rule.scopes or (last is not None and s is last):
            continue
        spans = sentence_spans(s.text)
        for m in EMOJI_RX.finditer(mask(s.text)):
            if rule.exc_compiled is not None and rule.exc_compiled.search(sentence_at(s.text, spans, m.start())):
                continue
            hits.append((s, m.start(), m.end()))
    if rule.severity == "S1":
        return [_finding(rule, s, a, b, 1, "문장", thr=1) for s, a, b in hits], len(hits)
    if len(hits) >= max(1, rule.thr_n):
        s, a, b = hits[0]
        out = [_finding(rule, s, a, b, len(hits), rule.thr_unit)]
    return out, len(hits)


def st_short_run(rule: Rule, segs: list) -> list:
    out = []
    for s in _proses(segs):
        real = [(a, b, t) for a, b, t in sentences_with_offsets(s.text) if not is_label(t)]
        run = 0
        for k, (a, b, t) in enumerate(real):
            if len(t) <= SHORT_SENTENCE:
                run += 1
                if run >= SHORT_RUN_LEN:
                    first = real[k - SHORT_RUN_LEN + 1]
                    out.append(_finding(rule, s, first[0], first[1], run, rule.thr_unit))
                    break
            else:
                run = 0
    return out


def st_triad_lists(rule: Rule, segs: list) -> list:
    blocks = _list_blocks(segs)
    threes = [b for b in blocks if len(b) == 3]
    if not threes or len(threes) < max(1, rule.thr_n) or len(threes) != len(blocks):
        return []
    s = threes[0][0]
    return [_finding(rule, s, 0, min(len(s.text), 24), len(threes), rule.thr_unit)]


def st_closing_kicker(rule: Rule, segs: list) -> list:
    proses = _proses(segs)
    if not proses:
        return []
    s = proses[-1]
    if len(sentences_with_offsets(s.text)) != 1:
        return []
    t = s.text.strip()
    if not t or len(t) > rule.thr_n or re.search(r"\d", t) or "?" in t:
        return []
    return [_finding(rule, s, 0, min(len(s.text), 30), 1, rule.thr_unit)]


def st_para_closer(rule: Rule, segs: list) -> list:
    proses = _proses(segs)
    if len(proses) < 4:
        return []
    body = proses[:-1]
    hits = []
    for s in body:
        sents = sentences_with_offsets(s.text)
        if not sents:
            continue
        a, b, t = sents[-1]
        if PARA_CLOSER_RX.match(t.strip()):
            hits.append((s, a, b))
    if hits and 100.0 * len(hits) / len(body) >= rule.thr_n:
        s, a, b = hits[0]
        return [_finding(rule, s, a, b, len(hits), rule.thr_unit)]
    return []


def _structure_regex_hit(rule: Rule, seg: Seg | None) -> list:
    if seg is None or rule.structure_regex is None:
        return []
    m = rule.structure_regex.search(seg.text)
    return [_finding(rule, seg, m.start(), m.end(), 1, rule.thr_unit)] if m else []


def st_opening_platitude(rule: Rule, segs: list) -> list:
    paras = _para_segs(rule, segs)
    return _structure_regex_hit(rule, paras[0] if paras else None)


def st_closing_moral(rule: Rule, segs: list) -> list:
    paras = _para_segs(rule, segs)
    return _structure_regex_hit(rule, paras[-1] if paras else None)


STRUCTURE_DETECTORS = {
    "bold_label_run": st_bold_label_run,
    "heading_echo": st_heading_echo,
    "emoji": st_emoji,
    "short_run": st_short_run,
    "triad_lists": st_triad_lists,
    "closing_kicker": st_closing_kicker,
    "para_closer": st_para_closer,
    "opening_platitude": st_opening_platitude,
    "closing_moral": st_closing_moral,
}
STRUCTURE_KEYS = frozenset(STRUCTURE_DETECTORS)   # 규칙 표의 structure 키는 이 레지스트리에 있어야 한다. 없으면 로더가 exit 2


def run_structure_rule(rule: Rule, segs: list) -> tuple[list, int]:
    """(finding 목록, 원시 매치 수). 검출기가 (목록, raw) 를 돌려주면 그대로 쓴다."""
    fn = STRUCTURE_DETECTORS.get(rule.structure_key)
    if fn is None:
        return [], 0
    res = fn(rule, segs)
    return res if isinstance(res, tuple) else (res, len(res))


def check(text: str, rs: Ruleset, genre: str | None, is_html: bool = False) -> Report:
    segs = segment_html(text, rs.teaching_headers) if is_html else segment_markdown(text, rs.teaching_headers)
    active = active_rules(rs, genre)
    live = {r.id for r in active}
    skipped = {"human": [], "위임": [], "genre": [r.id for r in rs.rules if r.id not in live]}
    findings, raw = [], {}
    for r in active:
        if r.detect in ("human", "위임"):
            skipped[r.detect].append(r.id); continue
        if r.detect == "structure":
            fs, n = run_structure_rule(r, segs)
        else:
            fs, n = run_pattern_rule(r, segs)
        if n:
            raw[r.id] = n
        findings.extend(fs)
    if genre == "all":
        # 장르가 다른 두 규칙이 같은 검출기를 같은 자리에 쓰면(AT-35·AT-59 emoji) 심각한 쪽 하나만 남긴다.
        rank = {"S1": 0, "S2": 1, "S3": 2}
        best: dict = {}
        for f in findings:
            key = rs.by_id[f.rule].structure_key
            if not key:
                continue
            k = (key, f.line, f.col)
            if k not in best or rank[f.severity] < rank[best[k].severity]:
                best[k] = f
        findings = [f for f in findings
                    if not rs.by_id[f.rule].structure_key
                    or best[(rs.by_id[f.rule].structure_key, f.line, f.col)] is f]
    findings.sort(key=lambda f: (f.line, f.col, f.rule))

    sent_total = sum(len(sentence_spans(s.text)) for s in segs if s.kind in ("prose", "list"))
    demoted = []
    if sent_total < SHORT_DOC_SENTENCES:
        for f in findings:
            r = rs.by_id[f.rule]
            if r.severity == "S2" and r.thr_unit == "문서":
                f.demoted = True
                if r.id not in demoted:
                    demoted.append(r.id)

    by_sev = {s: 0 for s in SEVERITIES}
    by_rule: dict = {}
    for f in findings:
        by_sev[f.severity] += 1
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
    strict_fail = any(f.severity == "S1" for f in findings) or \
        any(f.severity == "S2" and not f.demoted for f in findings)
    summary = {"total": len(findings), "by_severity": by_sev, "by_rule": by_rule, "raw": raw,
               "strict_fail": strict_fail, "skipped": skipped, "demoted": demoted}
    stats = {"chars": len(normalize_text(text)), "chars_nospace": len("".join(normalize_text(text).split())),
             "sentences": sent_total,
             "paragraphs": sum(1 for s in segs if s.kind == "prose"),
             "list_items": sum(1 for s in segs if s.kind == "list"),
             "headings": sum(1 for s in segs if s.kind == "heading")}
    rows = [(r.id, r.severity, by_rule.get(r.id, 0), raw.get(r.id, 0),
             "건너뜀" if r.detect in ("human", "위임") else (r.threshold.strip() or "-"))
            for r in active]
    return Report(genre=genre or "공통", rules_active=len(active), findings=findings,
                  summary=summary, stats=stats, rows=rows)


# ---------------------------------------------------------------------------
# 출력
# ---------------------------------------------------------------------------
GUIDANCE = "인용이 꼭 필요하면 「」·백틱으로 감싸거나 블록에 <!-- style-exempt --> 를 단다."


def _tail(reports: list, rs: Ruleset, genre: str | None) -> str:
    s1 = sum(r.summary["by_severity"]["S1"] for r in reports)
    s2 = sum(r.summary["by_severity"]["S2"] for r in reports)
    s3 = sum(r.summary["by_severity"]["S3"] for r in reports)
    sk = reports[0].summary["skipped"] if reports else {"human": [], "위임": [], "genre": []}
    return (f"S1 {s1} · S2 {s2} · S3 {s3}  |  규칙 {len(rs.rules)} 중 활성 "
            f"{reports[0].rules_active if reports else 0} (--genre {genre or '공통'}), "
            f"건너뜀 human {len(sk['human'])}·위임 {len(sk['위임'])}·장르 외 {len(sk['genre'])}")


def fmt_text(reports: list, rs: Ruleset, genre: str | None) -> str:
    out, many = [], len(reports) > 1
    for rep in reports:
        for f in rep.findings:
            if f.severity == "S3" or f.demoted:
                continue
            out.append(f'{rep.file}:{f.line}:{f.col}  [{f.rule} {f.severity}] {f.detail}  '
                       f'"{f.excerpt}"  → {f.fix}')
    for rep in reports:
        for f in rep.findings:
            if not (f.severity == "S3" or f.demoted):
                continue
            head = f"{rep.file}  " if many else ""
            out.append(f"[info] {head}{f.rule} {f.detail} {f.count}회/{f.unit or '문서'}")
    out.append(_tail(reports, rs, genre))
    out.append(GUIDANCE)
    return "\n".join(out)


def fmt_summary(reports: list, rs: Ruleset, genre: str | None) -> str:
    out, many = [], len(reports) > 1
    for rep in reports:
        if many:
            out.append(f"## {rep.file}")
        out.append("| 규칙 | 심각도 | finding | raw | 임계값 |")
        out.append("|---|---|---|---|---|")
        for rid, sev, nf, nraw, thr in rep.rows:
            out.append(f"| {rid} | {sev} | {nf} | {nraw} | {thr} |")
        out.append("")
    out.append(_tail(reports, rs, genre))
    return "\n".join(out)


def _cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def fmt_md(reports: list, rs: Ruleset, genre: str | None) -> str:
    out, many = [], len(reports) > 1
    for rep in reports:
        if many:
            out.append(f"## {rep.file}")
        out.append("| 규칙 | 심각도 | 행 | 발췌 | 수정 원칙 |")
        out.append("|---|---|---|---|---|")
        for f in rep.findings:
            sev = "info" if f.demoted else f.severity
            out.append(f"| {f.rule} | {sev} | {f.line} | {_cell(f.excerpt)} | {_cell(f.fix)} |")
        out.append("")
    out.append(_tail(reports, rs, genre))
    return "\n".join(out)


def to_json(rep: Report, rs: Ruleset) -> dict:
    return {"tool": "check_ai_tells", "rules_version": rs.version, "genre": rep.genre,
            "rules_loaded": len(rs.rules), "rules_active": rep.rules_active, "file": rep.file,
            "findings": [f.as_dict() for f in rep.findings],
            "summary": rep.summary, "stats": rep.stats}


# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="check_ai_tells.py", add_help=True,
                                description="ai-tells-ko.md 규칙으로 초고의 AI 티를 찾는다(읽기 전용).")
    p.add_argument("files", nargs="*", help="검사할 파일")
    p.add_argument("--genre", default=None, choices=["공통", "줄글", "개조식", "all"], help="장르 필터")
    p.add_argument("--rules", default=None, help="규칙 파일 경로(기본 principles/ai-tells-ko.md)")
    p.add_argument("--json", action="store_true", help="JSON 출력")
    p.add_argument("--summary", action="store_true", help="요약만 출력")
    p.add_argument("--md", action="store_true", help="마크다운 표 출력")
    p.add_argument("--strict", action="store_true", help="S1·S2 finding 이 있으면 실패")
    p.add_argument("--selftest", action="store_true", help="규칙 파일만으로 자체 검증")
    p.add_argument("--list", dest="list_rules", action="store_true", help="핸드셰이크 + 규칙 목록")
    p.add_argument("--explain", choices=["human"], help="human 행과 §4 표만 출력(진단이 읽는 묶음)")
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    args = build_parser().parse_args(argv)
    rules_path = Path(args.rules) if args.rules else RULES_MD
    rs = load_rules(rules_path)
    if args.explain:
        md = unicodedata.normalize("NFC", rules_path.read_text(encoding="utf-8").replace("\r\n", "\n"))
        print(explain_human(rs, md))
        return 0
    if args.selftest:
        return selftest(rs)
    if args.list_rules:
        return list_rules(rs, args.genre or "all")
    if not args.files:
        print("검사할 파일이 없다. --selftest 또는 --list 를 쓴다.", file=sys.stderr)
        return 2
    genre = args.genre
    if genre is None:
        print("[warn] 장르 미지정: 공통 규칙만 검사", file=sys.stderr)
        genre = "공통"
    reports = []
    for name in args.files:
        p = Path(name)
        try:
            src = p.read_text(encoding="utf-8")
        except OSError as e:
            print(f"입력 오류: {name}: {e}", file=sys.stderr)
            return 2
        rep = check(src, rs, genre, is_html=p.suffix.lower() in (".html", ".htm"))
        rep.file = str(name).replace("\\", "/")
        reports.append(rep)
    if args.json:
        payload = to_json(reports[0], rs) if len(reports) == 1 else [to_json(r, rs) for r in reports]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.summary:
        print(fmt_summary(reports, rs, genre))
    elif args.md:
        print(fmt_md(reports, rs, genre))
    else:
        print(fmt_text(reports, rs, genre))
    if args.strict and any(r.summary["strict_fail"] for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
