# -*- coding: utf-8 -*-
"""check_fidelity.py — 원문과 윤문 결과를 대조해 뜻이 그대로 남았는지 본다 (읽기 전용).

  python -X utf8 check_fidelity.py ORIG POLISHED [--json|--summary] [--strict]
                                   [--mode md|html|auto] [--prose-only]

모든 비교는 문서 단위 다중집합(collections.Counter)이다. 문장을 짝지어 맞추지 않는다.
규칙은 F1~F5·F7~F9. 표제(F4)·문단·항목 수(F5)는 S3 보고만 하고 길이는 stats.length_ratio 로만 남긴다(2026-09-17 자율 재작성 —
재작성이 구조를 다시 짜고 늘릴 수 있으므로 막지 않는다). 막는 것은 수치·인용·부정·자리표시자·링크·코드·표·각주의 S1 이다. F9 각주는 humanize-korean finalizer 의 의미 보존 15항 가운데
「각주 원위치·원번호·개수 보존」에서 가져왔다(2026-09-14). 불변식 2 가 각주를 약속하는데 검사기가 없었다.
종료 0 / 1(--strict 이고 S1 이 하나라도 있을 때) / 2(입력 오류).
"""
from __future__ import annotations
import argparse
import bisect
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from semantic_review import packet as semantic_packet

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_ai_tells import (force_utf8_stdout, find_tables, load_rules, mask,   # noqa: E402
                            normalize_text, segment_html, segment_markdown)

RULE_NAMES = {
    "F1": "수치·단위·날짜·비율",
    "F2": "고유명사·인용",
    "F3": "부정·조건",
    "F4": "표제",
    "F5": "문단·항목 수",
    "F7": "자리표시자",
    "F8": "링크·코드·표",
    "F9": "각주",
}
RULE_ORDER = ["F1", "F2", "F3", "F4", "F5", "F7", "F8", "F9"]
SEVERITIES = ("S1", "S2", "S3")
KINDS = ("missing", "added", "changed", "ratio")
SIDES = ("orig", "polished", "both")

MD_KINDS = {"prose", "heading", "list", "table", "quote", "code", "frontmatter", "exempt"}
# HTML 모드는 산문 외에 표제·목록·인용도 견준다. F4(표제)·F5(항목 수)가 그 세그먼트를 쓰기 때문이다.
# 산문만 견주려면 --prose-only. 원래 브리프는 산문만이었고 이 확장은 구현 중 결정이다(2026-09-08 검토에서 유지).
HTML_KINDS = {"prose", "heading", "list", "quote", "exempt"}   # md(MD_KINDS)와 같이 면제 구역도 견준다

# --- F1 수치·단위·날짜 -------------------------------------------------------
UNITS = ["%p", "%", "퍼센트", "개월", "km", "kg", "GB", "MB", "KB", "px", "pt",
         "원", "천", "만", "억", "조", "건", "명", "개", "회", "일", "주", "년",
         "시", "분", "초", "배", "위", "등", "호", "쪽", "m", "g", "㎡", "평", "℃"]
UNITS_SORTED = sorted(UNITS, key=len, reverse=True)     # %p 를 % 보다, 개월 을 개 보다 먼저 본다
AMOUNT_WORD = {"조": 10 ** 12, "억": 10 ** 8, "만": 10 ** 4, "천": 10 ** 3}
BIG = 10 ** 4                       # 만 이상은 앞 마디를 통째로 곱해 닫는다
# 단위 뒤에 붙어도 단위로 인정하는 조사·접미사. '12 원래' 를 12원 으로 읽지 않기 위한 경계다.
JOSA = set("은는이가을를에의으과와도만씩로나부까보밖정당짜째간여차반며랑엔란함")
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
DATE_RE = re.compile(r"(?<![\d,.])(\d{4})\s?[.\-/년]\s?(\d{1,2})(?!\d)"
                     r"(?:\s?[.\-/월]\s?(\d{1,2})(?!\d))?")

# --- F2 고유명사·인용 --------------------------------------------------------
LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9.+\-]{1,}")
IDENT_RE = re.compile(r"[A-Z]-?\d+")
QUOTE_RES = [re.compile(r"「([^」]*)」"), re.compile(r"『([^』]*)』"),
             re.compile(r'"([^"\n]*)"'), re.compile(r"“([^”]*)”"), re.compile(r"‘([^’]*)’")]

# --- F3 부정·조건 ------------------------------------------------------------
# 아니 계열은 통째로 부정이고 대조형 셋만 뺀다. 「A가 아니라 B」·「A도 아니고 B」·「A 아닌 B」는
# 부정이 아니라 병렬이고 AT-01·02·44 가 지우라고 하는 자리다. 뒤에 공백·쉼표·문장 끝이 와야
# 대조로 보므로 아니라고·아니라서·아닌데·아닌가는 부정으로 남는다. 열거가 아니라 제외 방식이라
# 아니지만·아니거나·아니니·아니면·아니되 처럼 이어지는 꼴도 빠짐없이 센다.
# 아닙니다·아님·아냐는 둘째 음절이 니가 아니라서 따로 적는다.
NEG_ANI = (r"아니(?!라(?=[\s,，、.!?…]|$)|고(?=[\s,，、.!?…]|$))"
           r"|아닌(?![\s,，、.!?…]|$)|아닙|아님|아냐")
NEG_RE = re.compile(r"않|없|못\s?하|못\s|" + NEG_ANI +
                    r"|안\s|불가|미정|미확|미달|미비|미이행|미측정|미검토|미완")
# 표지 계열 둘. S1 은 계열별 개수만 본다 — 없다↔않다 같은 갈아 끼우기는 뜻이 아니라 표현이다.
NEG_UNSURE_RE = re.compile(r"^(?:불가|미정|미확|미달|미비|미이행|미측정|미검토|미완)$")
COND_RE = re.compile(r"이면|라면|다면|면\s|경우|한하|제외|예외|이상|이하|초과|미만|까지|부터|이전|이후")
COND_LEAD_RE = re.compile(r"단,|다만")
PREV_RE = re.compile(r"[가-힣]{1,6}$")
# 개조식은 판단을 명사형으로 끝낸다(가이드 36행·775행). 아래 둘은 계열이 옮겨 가도 뜻이 같다.
# 「없다 → 미정」처럼 확정 수준이 바뀌는 치환은 여기 없으므로 계속 S1 이다.
NEG_EQUIV_STEM = re.compile(r"^(확인|확정|측정|검토|이행|완료)(?:되|하)지$")
NEG_EQUIV_MARK = {"확인": "미확", "확정": "미확", "측정": "미측정",
                  "검토": "미검토", "이행": "미이행", "완료": "미완"}
# 앞 내용어에서 떼는 조사·어미. 짝 키가 조사 교체·띄어쓰기 손질에 깨지지 않게 한다.
PARTICLES = ("지는", "은지", "까지", "부터", "에서", "에게",
             "은", "는", "이", "가", "도", "을", "를", "진")

# --- F7 자리표시자 -----------------------------------------------------------
HOLE_RE = re.compile(r"\[(?:사례|숫자|출처|확인|근거|마무리)\s?필요[^\]]*\]|담당 미정|일정 미정|미정\(")

# --- F8 링크·코드·표 ---------------------------------------------------------
URL_RE = re.compile(r"https?://\S+")
PRE_RE = re.compile(r"<pre\b", re.I)
TABLE_TAG_RE = re.compile(r"<table\b", re.I)

# --- F9 각주 -----------------------------------------------------------------
# 마크다운 각주 참조 [^id](뒤에 콜론이 없는 것)와 정의 줄 [^id]: 를 따로 센다. 개조식의 ※ 주석은 개수만 본다.
FOOT_REF_RE = re.compile(r"\[\^([^\]\s]+)\](?!:)")
FOOT_DEF_RE = re.compile(r"^[ \t]{0,3}\[\^([^\]\s]+)\]:", re.M)

RATIO_LO, RATIO_HI = 0.6, 1.4       # F5 문단·항목 수 허용 구간

# --- 검수 상태 문자열 ----------------------------------------------------------
# AT-39 가 지우라는 작업 상태(「검수 결과 수정 없음」)는 본문의 주장이 아니다. 그 안의 「없」을 F3 가
# 부정 소실로 세면 원칙 검사기와 이 검사기가 같은 자리에서 반대로 말한다(before-after.md §3-3).
# 규칙표의 AT-39 literal 을 읽어 F3 대조 전에 지운다. 규칙 파일이 없거나 깨지면 지우지 않고 계속한다.
_STATUS_LITERALS: list | None = None


def status_literals() -> list:
    global _STATUS_LITERALS
    if _STATUS_LITERALS is None:
        try:
            rule = load_rules().by_id.get("AT-39")
            _STATUS_LITERALS = list(rule.compiled) if rule is not None and isinstance(rule.compiled, list) else []
        except (SystemExit, OSError, ValueError):
            _STATUS_LITERALS = []
    return _STATUS_LITERALS


def blank_status(text: str) -> str:
    """검수 상태 문자열을 같은 길이의 공백으로 바꾼다(오프셋 보존)."""
    out = text
    for lit in status_literals():
        start = 0
        while True:
            j = out.find(lit, start)
            if j < 0:
                break
            out = out[:j] + " " * len(lit) + out[j + len(lit):]
            start = j + len(lit)
    return out


# ---------------------------------------------------------------------------
# 자료 구조
# ---------------------------------------------------------------------------
@dataclass
class Item:
    """비교 단위 하나. key 로 다중집합을 만들고 start/end 로 원문 자리를 돌려준다."""
    key: tuple
    label: str
    start: int
    end: int


@dataclass
class Heading:
    text: str
    line: int


@dataclass
class Finding:
    rule: str
    severity: str
    line: int
    col: int
    excerpt: str
    detail: str
    kind: str
    side: str

    def as_dict(self) -> dict:
        return {"rule": self.rule, "severity": self.severity, "line": self.line, "col": self.col,
                "excerpt": self.excerpt, "detail": self.detail, "kind": self.kind, "side": self.side}


class Doc:
    """검사 대상 한 편. scan 은 비교에 쓰는 텍스트, locate 는 그 오프셋을 원본 행·열로 되돌린다."""

    def __init__(self, path: str, text: str, is_html: bool, prose_only: bool):
        self.path = str(path).replace("\\", "/")
        self.raw = normalize_text(text)
        self.lines = self.raw.split("\n")
        self.is_html = is_html
        self.segs = segment_html(self.raw) if is_html else segment_markdown(self.raw)
        if is_html:
            kinds = {"prose"} if prose_only else HTML_KINDS
        else:
            kinds = {"prose"} if prose_only else MD_KINDS
        self.kinds = kinds
        # md 전체 모드는 원문 자체를 훑는다(표 머리 셀·코드까지 빠짐없이, 행 계산도 그대로).
        self.identity = (not is_html) and (not prose_only)
        if self.identity:
            self.scan = self.raw
            self.spans, self.starts = [], []
        else:
            parts, self.spans, pos = [], [], 0
            for s in self.segs:
                if s.kind not in kinds:
                    continue
                if parts:
                    parts.append("\n")
                    pos += 1
                self.spans.append((pos, s))
                parts.append(s.text)
                pos += len(s.text)
            self.scan = "".join(parts)
            self.starts = [a for a, _ in self.spans]
        self.masked = mask(blank_status(self.scan))

    def rawloc(self, off: int) -> tuple:
        off = max(0, min(off, len(self.raw)))
        line = self.raw.count("\n", 0, off) + 1
        col = off - (self.raw.rfind("\n", 0, off) + 1) + 1
        return line, col

    def locate(self, pos: int) -> tuple:
        if self.identity:
            return self.rawloc(pos)
        if not self.spans:
            return 1, 1
        i = bisect.bisect_right(self.starts, pos) - 1
        if i < 0:
            return 1, 1
        start, seg = self.spans[i]
        return seg.locate(pos - start)

    def excerpt(self, a: int, b: int, width: int = 36) -> str:
        t = self.scan
        lo = max(t.rfind("\n", 0, a) + 1, a - 12)
        hi = t.find("\n", a)
        hi = len(t) if hi < 0 else hi
        heads = list(re.finditer(r"[.!?…]\s+", t[lo:a]))     # 앞 문장 꼬리는 잘라낸다
        if heads:
            lo += heads[-1].end()
        return t[lo:min(hi, max(b, a + width))].strip()


# ---------------------------------------------------------------------------
# 추출기
# ---------------------------------------------------------------------------
def canon_num(s: str) -> str:
    """'12.0' ≡ '12', '1,234' ≡ '1234'."""
    t = s.replace(",", "").rstrip(".")
    if not t:
        return "0"
    if "." in t:
        f = float(t)
        return str(int(f)) if f == int(f) else ("%g" % f)
    return str(int(t))


def canon_amount(atoms: list) -> int:
    """숫자·자릿수 낱말 열을 정수 원으로 편다. 자릿수 낱말은 제 숫자가 없어도 앞 마디에 곱해진다.

    3천만 = 3×1000×10000, 1억 2천만 = 1e8 + 2×1000×10000,
    2,134만 5천 = 2134×10000 + 5×1000, 21,345천 = 21345×1000, 1조 2천억 = 1e12 + 2×1000×1e8.
    """
    total = section = num = 0.0
    for kind, v in atoms:
        if kind == "num":
            num = v
        elif v < BIG:                   # 천 — 마디 안에서 더한다
            section += (num or 1) * v
            num = 0.0
        else:                           # 만·억·조 — 여기까지의 마디를 통째로 곱해 닫는다
            section = (section + num) * v
            total += section
            section = num = 0.0
    return int(round(total + section + num))


def _unit_boundary_ok(text: str, k: int) -> bool:
    ch = text[k] if k < len(text) else ""
    if not ch or not ("가" <= ch <= "힣"):
        return True
    if ch in JOSA:
        return True
    return any(text.startswith(u, k) for u in UNITS_SORTED)


def _unit_at(text: str, i: int) -> tuple:
    """text[i:] 머리에 붙은 단위. 없으면 ('', i). 공백 하나까지는 건너뛴다."""
    for gap in (0, 1):
        if gap and not text.startswith(" ", i):
            break
        j = i + gap
        for u in UNITS_SORTED:
            if text.startswith(u, j) and _unit_boundary_ok(text, j + len(u)):
                return u, j + len(u)
    return "", i


def _mag_at(text: str, p: int) -> int:
    """text[p:] 머리의 자릿수 낱말 자리(공백 하나까지 건너뛴다). 없으면 -1."""
    q = p + 1 if text.startswith(" ", p) else p
    if q < len(text) and text[q] in AMOUNT_WORD and _unit_boundary_ok(text, q + 1):
        return q
    return -1


def _amount_atoms(text: str, start: int, blocked: list) -> tuple:
    """start 에서 시작하는 '숫자 + 자릿수 낱말' 열. ([('num'|'mag', 값)], 끝 오프셋).

    자릿수 낱말은 제 숫자 없이 이어 붙을 수 있다(3천'만'). 자릿수 낱말이 뒤따르지 않는
    숫자에서 멈춰, '3만 5' 의 5 나 날짜의 연도를 금액으로 빨아들이지 않는다.
    """
    atoms, pos, end = [], start, start
    while True:
        m = NUM_RE.match(text, pos)
        if not m or any(a <= m.start() < b for a, b in blocked):
            break
        p = _mag_at(text, m.end())
        if p < 0:
            break
        atoms.append(("num", float(m.group(0).replace(",", ""))))
        while p >= 0:
            atoms.append(("mag", AMOUNT_WORD[text[p]]))
            end = p + 1
            p = _mag_at(text, end)
        pos = end + 1 if text.startswith(" ", end) else end
    return atoms, end


def _in_identifier(text: str, i: int) -> bool:
    """숫자가 라틴 토큰에 붙어 있나(T-0012, v1.2). 그 숫자는 수치가 아니라 이름의 일부다."""
    if i == 0:
        return False
    prev = text[i - 1]
    if prev.isascii() and prev.isalpha():
        return True
    return prev == "-" and i >= 2 and text[i - 2].isascii() and text[i - 2].isalpha()


def extract_dates(text: str) -> list:
    """'2024년 12월 10일' ≡ '2024. 12. 10.' ≡ '2024-12-10' → ('2024-12-10', '날짜')."""
    out = []
    for m in DATE_RE.finditer(text):
        y, mo, d = m.group(1), m.group(2), m.group(3)
        iso = "%04d-%02d" % (int(y), int(mo)) + ("-%02d" % int(d) if d else "")
        out.append(Item((iso, "날짜"), m.group(0).strip(), m.start(), m.end()))
    return out


def extract_numbers(text: str) -> list:
    """날짜 + 수치. 값은 (정규화값, 단위) 키. 금액은 천·만·억·조를 펴서 정수 원으로 모은다."""
    dates = extract_dates(text)
    blocked = [(d.start, d.end) for d in dates]
    toks = []
    for m in NUM_RE.finditer(text):
        if any(a <= m.start() < b for a, b in blocked):
            continue
        if _in_identifier(text, m.start()):
            continue                    # T-0012 의 0012 는 수치가 아니라 이름이다. F2 가 본다
        u, uend = _unit_at(text, m.end())
        toks.append((m.start(), uend, canon_num(m.group(0)), u))
    out, i = list(dates), 0
    while i < len(toks):
        start, uend, val, unit = toks[i]
        atoms, end = _amount_atoms(text, start, blocked) if unit in AMOUNT_WORD else ([], uend)
        if atoms:
            tail, tend = _unit_at(text, end)     # 사슬을 닫는 단위: '원', 때로는 '명'
            if tail:
                end = tend
            out.append(Item((str(canon_amount(atoms)), tail), text[start:end].strip(), start, end))
            while i < len(toks) and toks[i][0] < end:
                i += 1
        else:
            out.append(Item((val, unit), text[start:uend].strip(), start, uend))
            i += 1
    out.sort(key=lambda it: it.start)
    return out


def extract_names(text: str) -> tuple:
    """(라틴 토큰·식별자, 인용 내용). 인용은 내용 문자열만 비교한다."""
    names, spans = [], []
    for m in LATIN_RE.finditer(text):
        tok = m.group(0).rstrip(".-+")
        if len(tok) < 2:
            continue
        spans.append((m.start(), m.start() + len(tok)))
        names.append(Item((tok,), tok, m.start(), m.start() + len(tok)))
    for m in IDENT_RE.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            continue
        names.append(Item((m.group(0),), m.group(0), m.start(), m.end()))
    quotes = []
    for rx in QUOTE_RES:
        for m in rx.finditer(text):
            body = m.group(1).strip()
            if body:
                quotes.append(Item((body,), body, m.start(), m.end()))
    names.sort(key=lambda it: it.start)
    quotes.sort(key=lambda it: it.start)
    return names, quotes


def _prev_word(text: str, i: int) -> str:
    """표지 앞 내용어. 조사·어미를 떼어 「해롭진」과 「해롭지는」이 같은 키가 되게 한다."""
    m = PREV_RE.search(text[:i].rstrip())
    if not m:
        return ""
    w = m.group(0)
    for p in PARTICLES:
        if len(w) > len(p) and w.endswith(p):
            return w[:-len(p)]
    return w


def _neg_class(mark: str) -> str:
    """표지 계열 둘. 부정(않·없·못·안·아니…) / 미확정(미정·미달·불가…)."""
    return "미확정" if NEG_UNSURE_RE.match(mark.replace(" ", "")) else "부정"


def _neg_marks(items: list) -> Counter:
    """부정 표지 계열 다중집합. 짝이 아니라 표지만 센다(S1 기준)."""
    return Counter(it.key[1] for it in items)


def _equiv_shifts(oneg: list, pneg: list) -> Counter:
    """부정 → 미확정 치환 가운데 뜻이 같은 짝의 수. 「할 수 없음 → 불가」·「확인되지 않 → 미확인」."""
    want = Counter()
    for it in oneg:
        _kind, cls, prev, mark = it.key
        if cls != "부정":
            continue
        if mark == "없" and prev == "수":
            want["불가"] += 1
        elif mark == "않":
            m = NEG_EQUIV_STEM.match(prev)
            if m:
                want[NEG_EQUIV_MARK[m.group(1)]] += 1
    have = Counter(it.key[3] for it in pneg if it.key[1] == "미확정")
    base = Counter(it.key[3] for it in oneg if it.key[1] == "미확정")
    out = Counter()
    for mark, n in want.items():
        got = have[mark] - base[mark]
        if got > 0:
            out[mark] = min(n, got)
    return out


def _ctx(text: str, at: int, width: int = 10) -> str:
    """표지 앞 문맥. 공백을 털어 줄바꿈·띄어쓰기 손질에 흔들리지 않게 한다."""
    return "".join(text[max(0, at - width):at].split())


def _unpaired(o_items: list, p_items: list, otext: str, ptext: str, n: int) -> list:
    """같은 키가 여럿일 때 앞 문맥이 결과에도 그대로 있는 자리를 짝지어 빼고 남은 자리를 준다."""
    left = list(o_items)
    for pit in p_items:
        c = _ctx(ptext, pit.start)
        hit = next((o for o in left if _ctx(otext, o.start) == c), None)
        if hit is not None:
            left.remove(hit)
    if len(left) >= n:
        return left[:n]
    return (left + [o for o in o_items if o not in left])[:n]


def _shift_echo(pd: "Doc", oneg: list, pneg: list, otext: str, ptext: str) -> str:
    """결과 쪽에서 새로 생긴 미확정 표지 하나를 덧붙인다. 어디로 옮겨 갔는지 사람이 바로 보게."""
    seen = {_ctx(otext, it.start) for it in oneg}
    for it in pneg:
        if it.key[1] == "미확정" and _ctx(ptext, it.start) not in seen:
            return f" (결과 {pd.locate(it.start)[0]}행 「{it.label}」)"
    return ""


def extract_polarity(text: str) -> tuple:
    """(부정 짝, 조건 짝). 부정 키 = (NEG, 계열, 앞 내용어, 표지). 문장 정렬은 하지 않는다."""
    neg, cond = [], []
    for m in NEG_RE.finditer(text):
        mark = m.group(0).strip()
        prev = _prev_word(text, m.start())
        neg.append(Item(("NEG", _neg_class(mark), prev, mark), f"{prev}{mark}", m.start(), m.end()))
    for m in COND_RE.finditer(text):
        mark = m.group(0).strip()
        prev = _prev_word(text, m.start())
        cond.append(Item(("COND", prev, mark), f"{prev}{mark}", m.start(), m.end()))
    for m in COND_LEAD_RE.finditer(text):
        mark = m.group(0)
        cond.append(Item(("COND", "", mark), mark, m.start(), m.end()))
    neg.sort(key=lambda it: it.start)
    cond.sort(key=lambda it: it.start)
    return neg, cond


def extract_headings(doc: Doc) -> list:
    """표제의 텍스트와 행. 층위는 F4 가 보지 않으므로 담지 않는다(짝짓기는 텍스트 유사도만 쓴다)."""
    return [Heading(s.text.strip(), s.line_start) for s in doc.segs if s.kind == "heading"]


def _norm_head(t: str) -> str:
    return re.sub(r"[^\w]", "", t)


def _bigrams(t: str) -> set:
    return {t[i:i + 2] for i in range(len(t) - 1)} or ({t} if t else set())


def _jaccard(a: str, b: str) -> float:
    ga, gb = _bigrams(a), _bigrams(b)
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def match_headings(a: list, b: list) -> tuple:
    """정규화 텍스트 동일 → 2-gram Jaccard ≥ 0.5 순으로 짝짓는다. (짝, 남은 원문, 남은 결과)."""
    used_b, pairs = set(), []
    for i, ha in enumerate(a):
        for j, hb in enumerate(b):
            if j in used_b:
                continue
            if _norm_head(ha.text) == _norm_head(hb.text):
                pairs.append((i, j))
                used_b.add(j)
                break
    matched_a = {i for i, _ in pairs}
    for i, ha in enumerate(a):
        if i in matched_a:
            continue
        best, bj = 0.0, -1
        for j, hb in enumerate(b):
            if j in used_b:
                continue
            s = _jaccard(_norm_head(ha.text), _norm_head(hb.text))
            if s > best:
                best, bj = s, j
        if bj >= 0 and best >= 0.5:
            pairs.append((i, bj))
            used_b.add(bj)
            matched_a.add(i)
    pairs.sort()
    left_a = [i for i in range(len(a)) if i not in matched_a]
    left_b = [j for j in range(len(b)) if j not in used_b]
    return pairs, left_a, left_b


def extract_structure(doc: Doc) -> dict:
    """문단·항목·표제 수와 길이, 코드 펜스·표·표 셀."""
    if doc.is_html:
        fences = len(PRE_RE.findall(doc.raw))
        tables = len(TABLE_TAG_RE.findall(doc.raw))
        cells: list = []
    else:
        fences = sum(1 for s in doc.segs if s.kind == "code")
        found = find_tables(doc.raw)
        tables = len(found)
        cells = []
        for header, rows, _ln in found:
            cells.extend(c for c in header if c)
            for row in rows:
                cells.extend(c for c in row if c)
    return {"paragraphs": sum(1 for s in doc.segs if s.kind == "prose"),
            "list_items": sum(1 for s in doc.segs if s.kind == "list"),
            "headings": sum(1 for s in doc.segs if s.kind == "heading"),
            "chars": sum(1 for ch in doc.scan if not ch.isspace()),
            "fences": fences, "tables": tables, "cells": cells}


# ---------------------------------------------------------------------------
# 대조
# ---------------------------------------------------------------------------
def _index(items: list) -> tuple:
    counts: Counter = Counter()
    where: dict = {}
    for it in items:
        counts[it.key] += 1
        where.setdefault(it.key, []).append(it)
    return counts, where


def _finding(rule: str, sev: str, kind: str, side: str, doc: Doc, it, detail: str) -> Finding:
    if it is None or doc is None:
        return Finding(rule, sev, 1, 1, "", detail, kind, side)
    line, col = doc.locate(it.start)
    return Finding(rule, sev, line, col, doc.excerpt(it.start, it.end), detail, kind, side)


def _pick(where: dict, key: tuple, n: int) -> list:
    """그 값이 놓인 자리 중 앞에서 n 개."""
    return where.get(key, [])[:n]


def _aggregate(rule: str, sev: str, kind: str, side: str, doc: Doc, where: dict,
               diff: Counter, head: str) -> list:
    """개수 수준 신호(S2)는 규칙마다 한 건으로 묶는다."""
    if not diff:
        return []
    names = []
    for key, n in sorted(diff.items()):
        seen = where.get(key)
        names.append(seen[0].label if seen else "·".join(str(x) for x in key if x))
        if n > 1:
            names[-1] += f"×{n}"
    shown = ", ".join(names[:5]) + (" …" if len(names) > 5 else "")
    first = None
    for key in sorted(diff, key=lambda k: (where.get(k, [Item(k, "", 10 ** 9, 0)])[0].start)):
        cand = where.get(key)
        if cand:
            first = cand[0]
            break
    return [_finding(rule, sev, kind, side, doc, first, f"{head} {sum(diff.values())}개: {shown}")]


def _urls(text: str) -> list:
    """링크 집합. `\\S+` 로 잡은 뒤 따옴표·꺾쇠·닫는 부호를 떼어 md 와 html 이 같은 키를 갖게 한다."""
    out = []
    for m in URL_RE.finditer(text):
        url = re.split(r"[\"'<>]", m.group(0), maxsplit=1)[0].rstrip(".,;:)]}」』】")
        if url:
            out.append(Item((url,), url, m.start(), m.start() + len(url)))
    return out


def _ratio(new: float, old: float) -> float:
    if old == 0:
        return 1.0 if new == 0 else 99.0
    return round(new / old, 4)


def compare(od: Doc, pd: Doc) -> tuple:
    fs: list = []

    # --- F1 수치·단위·날짜·비율 -------------------------------------------
    mo, wo = _index(extract_numbers(od.scan))
    mp, wp = _index(extract_numbers(pd.scan))
    deficit, surplus = mo - mp, mp - mo
    changed = []
    for kd in sorted(deficit):
        for ks in sorted(surplus):
            if kd[0] != ks[0] or kd[1] == ks[1] or deficit[kd] == 0 or surplus[ks] == 0:
                continue
            n = min(deficit[kd], surplus[ks])
            changed.append((kd, ks, n))
            deficit[kd] -= n
            surplus[ks] -= n
    deficit += Counter()        # 0 이 된 항목을 턴다
    surplus += Counter()
    for kd, ks, n in changed:
        a = _pick(wo, kd, n)
        b = _pick(wp, ks, n)
        for t in range(n):
            oi = a[t] if t < len(a) else None
            pi = b[t] if t < len(b) else None
            pl = pd.locate(pi.start)[0] if pi else 0
            fs.append(_finding("F1", "S1", "changed", "both", od, oi,
                               f"같은 값 다른 단위: {oi.label if oi else kd[0]} → "
                               f"{pi.label if pi else ks[0]} (polished {pl}행)"))
    for key, n in sorted(deficit.items()):
        gone = mp.get(key, 0) == 0
        for it in _pick(wo, key, n):
            if gone:
                fs.append(_finding("F1", "S1", "missing", "orig", od, it, f"원문에만: {it.label}"))
            else:
                fs.append(_finding("F1", "S2", "missing", "orig", od, it,
                                   f"빈도가 줄었다: {it.label} {mo[key]}회 → {mp[key]}회"))
    for key, n in sorted(surplus.items()):
        fresh = mo.get(key, 0) == 0
        for it in _pick(wp, key, n):
            if fresh:
                fs.append(_finding("F1", "S1", "added", "polished", pd, it, f"결과에만: {it.label}"))
            else:
                fs.append(_finding("F1", "S3", "added", "polished", pd, it,
                                   f"빈도가 늘었다: {it.label} {mo[key]}회 → {mp[key]}회"))

    # --- F2 고유명사·인용 ---------------------------------------------------
    on, oq = extract_names(od.scan)
    pn, pq = extract_names(pd.scan)
    for it in oq:
        if it.key[0] not in pd.scan:
            fs.append(_finding("F2", "S1", "missing", "orig", od, it, f"인용이 그대로 남지 않았다: {it.label}"))
    ct_o, wt_o = _index(on)
    ct_p, wt_p = _index(pn)
    fs += _aggregate("F2", "S2", "missing", "orig", od, wt_o, ct_o - ct_p, "원문에만 있는 이름·토큰")
    fs += _aggregate("F2", "S2", "added", "polished", pd, wt_p, ct_p - ct_o, "결과에만 있는 이름·토큰")

    # --- F3 부정·조건 -------------------------------------------------------
    oneg, ocond = extract_polarity(od.masked)
    pneg, pcond = extract_polarity(pd.masked)
    cn_o, wn_o = _index(oneg)
    cn_p, wn_p = _index(pneg)
    # 두 층이다. S1 은 표지 계열 개수만 본다 — 부정이 정말 사라졌는가.
    # 짝(앞 내용어 + 표지)이 달라지기만 한 것은 어미·조사 손질이므로 S2 에 둔다.
    lost = _neg_marks(oneg) - _neg_marks(pneg)
    shift = sum(_equiv_shifts(oneg, pneg).values())
    if shift:
        lost = lost - Counter({"부정": shift})       # 뜻이 같은 명사형 치환은 사라진 부정이 아니다
    gone = []
    for key, n in sorted((cn_o - cn_p).items()):
        gone.extend(_unpaired(wn_o.get(key, []), wn_p.get(key, []), od.masked, pd.masked, n))
    gone.sort(key=lambda it: it.start)
    quota, rest = dict(lost), Counter()
    for it in gone:
        cls = it.key[1]
        if quota.get(cls, 0) > 0:
            quota[cls] -= 1
            echo = _shift_echo(pd, oneg, pneg, od.masked, pd.masked)
            fs.append(_finding("F3", "S1", "missing", "orig", od, it, f"부정이 사라졌다: {it.label}{echo}"))
        else:
            rest[it.key] += 1
    fs += _aggregate("F3", "S2", "missing", "orig", od, wn_o, rest, "표지는 남고 짝이 달라진 부정")
    fs += _aggregate("F3", "S2", "added", "polished", pd, wn_p, cn_p - cn_o, "결과에만 있는 부정 짝")
    cc_o, wc_o = _index(ocond)
    cc_p, wc_p = _index(pcond)
    fs += _aggregate("F3", "S2", "missing", "orig", od, wc_o, cc_o - cc_p, "원문에만 있는 조건 짝")
    fs += _aggregate("F3", "S2", "added", "polished", pd, wc_p, cc_p - cc_o, "결과에만 있는 조건 짝")

    # --- F4 표제 (S3 보고만) ---------------------------------------------------
    oh, ph = extract_headings(od), extract_headings(pd)
    pairs, left_a, left_b = match_headings(oh, ph)
    seq = [j for _i, j in pairs]
    for k in range(1, len(seq)):
        if seq[k] < seq[k - 1]:
            i, j = pairs[k]
            fs.append(Finding("F4", "S3", oh[i].line, 1, oh[i].text,
                              f"표제 순서가 바뀌었다: 「{oh[i].text}」 (polished {ph[j].line}행)",
                              "changed", "both"))
            break
    if len(oh) != len(ph):
        fs.append(Finding("F4", "S3", 1, 1, "", f"표제 수가 다르다: {len(oh)}개 → {len(ph)}개", "ratio", "both"))
    for i, j in zip(left_a, left_b):
        fs.append(Finding("F4", "S3", oh[i].line, 1, oh[i].text,
                          f"표제 글이 바뀌었다: 「{oh[i].text}」 → 「{ph[j].text}」 (polished {ph[j].line}행)",
                          "changed", "both"))
    for i in left_a[len(left_b):]:
        fs.append(Finding("F4", "S3", oh[i].line, 1, oh[i].text,
                          f"표제가 사라졌다: 「{oh[i].text}」", "missing", "orig"))
    for j in left_b[len(left_a):]:
        fs.append(Finding("F4", "S3", ph[j].line, 1, ph[j].text,
                          f"표제가 새로 생겼다: 「{ph[j].text}」", "added", "polished"))

    # --- F5 문단·항목 수 (S3 보고만), 길이는 stats 에만 ---------------------------
    so, sp = extract_structure(od), extract_structure(pd)
    para = _ratio(sp["paragraphs"], so["paragraphs"])
    lst = _ratio(sp["list_items"], so["list_items"])
    length = _ratio(sp["chars"], so["chars"])
    if not (RATIO_LO <= para <= RATIO_HI):
        fs.append(Finding("F5", "S3", 1, 1, "",
                          f"문단 수 비율 {para} (허용 {RATIO_LO}~{RATIO_HI}, "
                          f"{so['paragraphs']} → {sp['paragraphs']})", "ratio", "both"))
    if not (RATIO_LO <= lst <= RATIO_HI):
        fs.append(Finding("F5", "S3", 1, 1, "",
                          f"항목 수 비율 {lst} (허용 {RATIO_LO}~{RATIO_HI}, "
                          f"{so['list_items']} → {sp['list_items']})", "ratio", "both"))

    # --- F7 자리표시자 -------------------------------------------------------
    oho = [Item((re.sub(r"\s+", " ", m.group(0)),), m.group(0), m.start(), m.end())
           for m in HOLE_RE.finditer(od.scan)]
    pho = [Item((re.sub(r"\s+", " ", m.group(0)),), m.group(0), m.start(), m.end())
           for m in HOLE_RE.finditer(pd.scan)]
    cho, who = _index(oho)
    chp, whp = _index(pho)
    for key, n in sorted((cho - chp).items()):
        for it in _pick(who, key, n):
            fs.append(_finding("F7", "S1", "missing", "orig", od, it,
                               f"자리표시자가 사라졌다: {it.label}"))
    for key, n in sorted((chp - cho).items()):
        for it in _pick(whp, key, n):
            fs.append(_finding("F7", "S3", "added", "polished", pd, it,
                               f"자리표시자가 새로 생겼다: {it.label}"))

    # --- F8 링크·코드·표 -----------------------------------------------------
    ou = _urls(od.raw)
    pu = _urls(pd.raw)
    cuo, wuo = _index(ou)
    cup, wup = _index(pu)
    for key, n in sorted((cuo - cup).items()):
        for it in _pick(wuo, key, n):
            line, col = od.rawloc(it.start)
            fs.append(Finding("F8", "S1", line, col, it.label, f"링크가 사라졌다: {it.label}",
                              "missing", "orig"))
    for key, n in sorted((cup - cuo).items()):
        for it in _pick(wup, key, n):
            line, col = pd.rawloc(it.start)
            fs.append(Finding("F8", "S3", line, col, it.label, f"링크가 새로 생겼다: {it.label}",
                              "added", "polished"))
    if so["fences"] != sp["fences"]:
        fs.append(Finding("F8", "S2", 1, 1, "",
                          f"코드 블록 수가 다르다: {so['fences']} → {sp['fences']}", "ratio", "both"))
    if so["tables"] != sp["tables"]:
        fs.append(Finding("F8", "S2", 1, 1, "",
                          f"표 수가 다르다: {so['tables']} → {sp['tables']}", "ratio", "both"))
    cell_o, cell_p = Counter(so["cells"]), Counter(sp["cells"])
    if cell_o != cell_p:
        gone, fresh = cell_o - cell_p, cell_p - cell_o
        bits = []
        if gone:
            bits.append("원문에만 " + ", ".join(sorted(gone)[:3]))
        if fresh:
            bits.append("결과에만 " + ", ".join(sorted(fresh)[:3]))
        fs.append(Finding("F8", "S2", 1, 1, "", "표 셀이 달라졌다: " + " · ".join(bits),
                          "changed", "both"))

    # --- F9 각주 -------------------------------------------------------------
    def _foot(rx: "re.Pattern", text: str) -> list:
        return [Item((m.group(1),), m.group(0), m.start(), m.end()) for m in rx.finditer(text)]
    fr_o, fr_p = _foot(FOOT_REF_RE, od.scan), _foot(FOOT_REF_RE, pd.scan)
    fd_o, fd_p = _foot(FOOT_DEF_RE, od.scan), _foot(FOOT_DEF_RE, pd.scan)
    for what, a, b, da, db in (("참조", fr_o, fr_p, od, pd), ("정의", fd_o, fd_p, od, pd)):
        ca, wa = _index(a)
        cb, wb = _index(b)
        for key, n in sorted((ca - cb).items()):
            for it in _pick(wa, key, n):
                fs.append(_finding("F9", "S1", "missing", "orig", da, it, f"각주 {what}가 사라졌다: {it.label}"))
        for key, n in sorted((cb - ca).items()):
            for it in _pick(wb, key, n):
                fs.append(_finding("F9", "S1", "added", "polished", db, it, f"각주 {what}가 새로 생겼다: {it.label}"))
    if fr_o and [i.key for i in fr_o] != [i.key for i in fr_p] and _index(fr_o)[0] == _index(fr_p)[0]:
        fs.append(Finding("F9", "S2", 1, 1, "", "각주 참조 순서가 바뀌었다: "
                          + " ".join(i.label for i in fr_o) + " → " + " ".join(i.label for i in fr_p), "changed", "both"))
    note_o, note_p = od.scan.count("※"), pd.scan.count("※")
    if note_o != note_p:
        fs.append(Finding("F9", "S2", 1, 1, "", f"※ 주석 수가 다르다: {note_o} → {note_p}", "ratio", "both"))

    fs.sort(key=lambda f: (RULE_ORDER.index(f.rule), SEVERITIES.index(f.severity),
                           f.side != "orig", f.line, f.col))
    stats = {"length_ratio": length, "paragraph_ratio": para, "list_ratio": lst,
             "neg_pairs_orig": len(oneg), "neg_pairs_polished": len(pneg),
             "chars_orig": so["chars"], "chars_polished": sp["chars"],
             "paragraphs_orig": so["paragraphs"], "paragraphs_polished": sp["paragraphs"],
             "list_items_orig": so["list_items"], "list_items_polished": sp["list_items"],
             "headings_orig": so["headings"], "headings_polished": sp["headings"]}
    return fs, stats


# ---------------------------------------------------------------------------
# 입력·출력
# ---------------------------------------------------------------------------
def load_pair(orig: str, polished: str, mode: str, prose_only: bool) -> tuple:
    """두 파일을 읽어 Doc 짝으로 만든다. 모드를 정하지 못하면 SystemExit(2)."""
    po, pp = Path(orig), Path(polished)
    so, sp = po.suffix.lower(), pp.suffix.lower()
    if mode == "auto":
        if so != sp:
            print(f"입력 오류: 확장자가 다르다({so or '없음'} vs {sp or '없음'}). --mode md|html 를 준다.",
                  file=sys.stderr)
            raise SystemExit(2)
        mode = "html" if so in (".html", ".htm") else "md"
    texts = []
    for p in (po, pp):
        try:
            texts.append(p.read_text(encoding="utf-8"))
        except OSError as e:
            print(f"입력 오류: {p}: {e}", file=sys.stderr)
            raise SystemExit(2)
    is_html = mode == "html"
    return (Doc(orig, texts[0], is_html, prose_only),
            Doc(polished, texts[1], is_html, prose_only), mode)


def summarize(findings: list) -> dict:
    by_sev = {s: 0 for s in SEVERITIES}
    by_rule: dict = {}
    by_kind: dict = {}
    for f in findings:
        by_sev[f.severity] += 1
        by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    return {"total": len(findings), "by_severity": by_sev, "by_rule": by_rule,
            "by_kind": by_kind, "strict_fail": by_sev["S1"] > 0}


def _tail(summary: dict, stats: dict) -> str:
    s = summary["by_severity"]
    return (f"S1 {s['S1']} · S2 {s['S2']} · S3 {s['S3']}  |  길이 {stats['length_ratio']} · "
            f"문단 {stats['paragraph_ratio']} · 항목 {stats['list_ratio']} · "
            f"부정 짝 {stats['neg_pairs_orig']}→{stats['neg_pairs_polished']}")


def _where(f: Finding) -> str:
    """finding 이 가리키는 자리. 규칙별 묶음 줄 끝에 붙는다."""
    if f.side == "both" and f.line <= 1:
        return ""
    side = "orig" if f.side in ("orig", "both") else "polished"
    quoted = ' "' + f.excerpt + '"' if f.excerpt else ""
    return f" ({side} {f.line}행{quoted})"


def fmt_text(findings: list, summary: dict, stats: dict, od: Doc, pd: Doc) -> str:
    out = [f"{od.path} → {pd.path}"]
    for f in findings:
        out.append(f"[{f.rule} {RULE_NAMES[f.rule]} {f.severity}] {f.detail}{_where(f)}")
    out.append(_tail(summary, stats))
    return "\n".join(out)


def fmt_summary(findings: list, summary: dict, stats: dict, od: Doc, pd: Doc) -> str:
    out = [f"{od.path} → {pd.path}", "", "| 규칙 | 이름 | S1 | S2 | S3 | 계 |", "|---|---|---|---|---|---|"]
    per: dict = {}
    for f in findings:
        per.setdefault(f.rule, {s: 0 for s in SEVERITIES})[f.severity] += 1
    for rid in RULE_ORDER:
        c = per.get(rid, {s: 0 for s in SEVERITIES})
        out.append(f"| {rid} | {RULE_NAMES[rid]} | {c['S1']} | {c['S2']} | {c['S3']} | "
                   f"{c['S1'] + c['S2'] + c['S3']} |")
    out += ["", "| 지표 | 값 |", "|---|---|"]
    for k in ("length_ratio", "paragraph_ratio", "list_ratio", "neg_pairs_orig", "neg_pairs_polished"):
        out.append(f"| {k} | {stats[k]} |")
    out += ["", _tail(summary, stats)]
    return "\n".join(out)


def to_json(findings: list, summary: dict, stats: dict, od: Doc, pd: Doc, mode: str) -> dict:
    return {"tool": "check_fidelity", "mode": mode, "orig": od.path, "polished": pd.path,
            "findings": [f.as_dict() for f in findings], "summary": summary, "stats": stats,
            "semantic_review": semantic_packet(od, pd)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="check_fidelity.py", add_help=True,
                                description="원문과 윤문 결과를 대조해 뜻이 보존됐는지 본다(읽기 전용).")
    p.add_argument("orig", nargs="?", help="원문")
    p.add_argument("polished", nargs="?", help="윤문 결과")
    p.add_argument("--json", action="store_true", help="JSON 출력")
    p.add_argument("--summary", action="store_true", help="규칙별 요약 표")
    p.add_argument("--strict", action="store_true", help="S1 이 있으면 실패(exit 1)")
    p.add_argument("--mode", default="auto", choices=["md", "html", "auto"], help="입력 형식")
    p.add_argument("--prose-only", action="store_true", help="산문 블록만 견준다")
    return p


def main(argv: list | None = None) -> int:
    force_utf8_stdout()
    args = build_parser().parse_args(argv)
    if not args.orig or not args.polished:
        print("원문과 결과 두 파일이 필요하다: check_fidelity.py ORIG POLISHED", file=sys.stderr)
        return 2
    od, pd, mode = load_pair(args.orig, args.polished, args.mode, args.prose_only)
    findings, stats = compare(od, pd)
    summary = summarize(findings)
    if args.json:
        print(json.dumps(to_json(findings, summary, stats, od, pd, mode), ensure_ascii=False, indent=2))
    elif args.summary:
        print(fmt_summary(findings, summary, stats, od, pd))
    else:
        print(fmt_text(findings, summary, stats, od, pd))
    if args.strict and summary["strict_fail"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
