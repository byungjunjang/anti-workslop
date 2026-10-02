# -*- coding: utf-8 -*-
"""check_all.py — 네 검사기를 한 번에 돌려 짧게 낸다 (읽기 전용).

  python -X utf8 check_all.py --guide <가이드>|없음 FILE                   # 진단: 장르·원칙·취향. finding 한 줄씩
  python -X utf8 check_all.py --guide … --orig ORIG FILE                   # 검수: 넷 다. 막는 항목만 + 판정 한 줄. exit 1 = FAIL
  python -X utf8 check_all.py --guide … --orig ORIG --taste-skip W-01 FILE # 사용자가 빼라고 한 취향 [규칙]은 보이되 막지 않음
  python -X utf8 check_all.py --guide … --pack FILE                        # 읽기 묶음: 가이드 §8·§11-2·§14(윤문 블록), 원칙 human 행·§4, 취향 §0~§6
  python -X utf8 check_all.py --guide … --bundle FILE                      # 서브에이전트가 읽을 것 전부: 브리프 + 읽기 묶음 + 진단
  python -X utf8 check_all.py --guide 없음 --hint FILE                     # 힌트·용도·레이어 세 줄 + 「가이드: <이름>|묻는다 · <이유>」 + 고른 가이드의 「사전 검사:」 줄(물을 때는 없다)
  python -X utf8 check_all.py --guide <가이드> --hint FILE                 # 고르지 않고 그 가이드로. 사용자가 가이드를 지정했거나 질문에 답한 뒤
  python -X utf8 check_all.py --guide … --prompt --record REC [--clean] FILE   # 윤문 담당의 한 장 프롬프트(P5). 진단 끝 「사전 검사:」 줄이 깨끗이면 --clean

가이드 이름은 base-guidelines.json 의 밑줄 없는 최상위 키다(기본 셋 + register_guide.py 로 등록한 것).
명령은 같은 파일에서 읽는다(_checks · _checks_short · _checks_common · _checker_kind · _pack_sections · _s14_blocks). 짧은 글 판정은
스스로 한다(줄글이고 공백 제외 _short_chars 이하면 장르 명령을 _checks_short 로). 검사기 종료 코드는 보지 않고
출력만 읽는다. 검사기가 exit 2 를 내거나 죽으면 그 stderr 를 흘리고 exit 2.

검수의 FAIL 조건은 넷이다. 장르 hard > 0, 원칙 S1 > 0 또는 S2 finding > 0, 취향 [규칙] > 0(사용자가 뺀 것 제외), 대조 S1 > 0.
마지막 줄은 `판정: PASS|FAIL · …` 이고 그 위에 조건부로 두 줄이 온다. 둘 다 판정과 종료 코드를 바꾸지 않는다.
  빠진 것: 수치 N · 인용 N · 부정 N · 자리표시자 N · 링크 N · 각주 N     # check_fidelity 의 summary.dropped. 전부 0 이면 없다
  경고: 많이 줄었다 · 글자 <비율> · 항목 <비율>                          # 결과 ÷ 원문 이 SHRINK_WARN 미만일 때. 원문에 항목이 없으면 항목 부분은 없다
"""
from __future__ import annotations
import argparse, json, re, shlex, subprocess, sys, tempfile, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]
BASE = SKILL_DIR / "references" / "base-guidelines.json"
BRIEF = SKILL_DIR / "references" / "subagent.md"
REPORT_TITLES = ROOT / "styleguides" / "report" / "title-claims.md"
TASTE_MD = ROOT / "taste" / "writing-taste.md"
sys.path.insert(0, str(HERE))
from check_ai_tells import (RULES_MD, TRAILER_MARK, explain_human, force_utf8_stdout, is_label,   # noqa: E402
                            load_rules, normalize_text, segment_html, segment_markdown,
                            split_sentences, strip_trailer)
from check_fidelity import DROP_KINDS, RULE_NAMES                                              # noqa: E402

# 읽기 묶음에 싣는 가이드 절의 기본값. 가이드마다 base-guidelines.json 의 _pack_sections 가 우선한다.
# §0(읽는 법)과 자동 계측 표(장피엠 §11-1·개조식 §11-2)는 검사기가 대신하므로 싣지 않는다.
PACK_SECTIONS = ("8", "14")
HINT_MIN = 3                    # 이보다 문장·항목이 적으면 장르를 고르지 않는다(애매)
HINT_NOMINAL = 0.6              # 개조식 판정에 필요한 명사형 종결 항목 비율
HINT_PROSE_RATIO = 4            # 줄글 판정: 명사형 항목 × 이 값 ≤ 산문 문장 수
SHRINK_WARN = 0.6               # 검수 경고: 공백 제외 글자 수나 목록 항목 수가 원문의 이 비율 미만이면 「많이 줄었다」. 손볼 수 있는 기본값


# ---------------------------------------------------------------------------
# 실행
# ---------------------------------------------------------------------------
def load_bg() -> dict:
    return json.loads(BASE.read_text(encoding="utf-8"))


def guide_names(bg: dict) -> list:
    """등록된 가이드 이름. 밑줄로 시작하지 않는 최상위 키다."""
    return [k for k in bg if not k.startswith("_")]


def run_cmd(template: str, **subs: str) -> subprocess.CompletedProcess:
    cmd = template
    for k, v in subs.items():
        cmd = cmd.replace("{" + k + "}", v)
    argv = shlex.split(cmd, posix=True)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode not in (0, 1) or "Traceback" in (r.stderr or ""):
        sys.stderr.write(r.stderr or r.stdout)
        raise SystemExit(2)
    return r


def _json(r: subprocess.CompletedProcess, what: str):
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        print(f"[오류] {what} 출력이 JSON 이 아니다: {(r.stderr or r.stdout).strip().splitlines()[-1:]}", file=sys.stderr)
        raise SystemExit(2)
    return d[0] if isinstance(d, list) and d else d


# ---------------------------------------------------------------------------
# 검사기별 요약
# ---------------------------------------------------------------------------
def genre_lines(kind: str, r: subprocess.CompletedProcess, verify: bool) -> tuple[int, int, list]:
    """(hard, soft, 줄 목록). kind = _checker_kind[가이드]. style 은 check_style JSON, report 는 check_report 텍스트."""
    if kind == "style":
        d = _json(r, "check_style")
        if "error" in d:
            return 0, 0, [f"(장르 검사기 오류: {d['error']})"]
        rows = [x for x in d["rows"] if not x["ok"] and (x["level"] == "hard" or not verify)]
        lines = ["| 항목 | 값 | 목표 | 판정 |", "|---|---|---|---|"] if rows else []
        for x in rows:
            mark = "FAIL" if x["level"] == "hard" else "warn"
            lines.append(f"| {x['label']} | {x['value']} | {x['target']} | {mark} |")
        m = d["metrics"]
        if not verify:
            lines += [f"시작: [{m.get('opening_type', '')}] {str(m.get('opening_sentence', ''))[:80]}",
                      f"끝: …{str(m.get('closing_sentence', ''))[-80:]}"]
        return d["hard_fail"], d["soft_fail"], lines
    text = r.stdout
    hm = re.search(r"^\[반드시 고칠 것\]\s*(\d+)건", text, re.M)
    sm = re.search(r"^\[검토할 것\]\s*(\d+)건", text, re.M)
    hard, soft = (int(hm.group(1)) if hm else 0), (int(sm.group(1)) if sm else 0)
    if verify:
        sec = re.search(r"^\[반드시 고칠 것\][^\n]*\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
        lines = [l for l in (sec.group(1) if sec else "").splitlines() if l.strip()]
    else:
        lines = [l for l in text.strip("\n").splitlines()]
    return hard, soft, lines


def ai_lines(d: dict, verify: bool) -> tuple[int, int, int, int, list]:
    """(S1, S2 비강등, S3, 강등 수, 줄 목록)."""
    s1 = s2 = s3 = demoted = 0
    lines, infos = [], []
    for f in d["findings"]:
        if f.get("demoted"):
            demoted += 1
        if f["severity"] == "S1":
            s1 += 1
        elif f["severity"] == "S2" and not f.get("demoted"):
            s2 += 1
        elif f["severity"] == "S3":
            s3 += 1
        blocking = f["severity"] == "S1" or (f["severity"] == "S2" and not f.get("demoted"))
        if blocking:
            lines.append(f'{f["line"]}:{f["col"]}  [{f["rule"]} {f["severity"]}] {f["detail"]}  "{f["excerpt"]}"  → {f["fix"]}')
        elif not verify:
            infos.append(f'[info] {f["rule"]} {f["detail"]} {f["count"]}회/{f["unit"] or "문서"}  "{f["excerpt"]}"')
    return s1, s2, s3, demoted, lines + infos


def taste_lines(d: dict, verify: bool, skip: frozenset = frozenset()) -> tuple[dict, int, list, list]:
    """(등급별 수, 막는 [규칙] 수, human 목록, 줄 목록). 취향은 모든 문서에 댄다. 사용자가 빼라고 한 W-NN 만 호출자가 skip 으로 넘긴다."""
    g = d["summary"]["by_grade"]
    blocking = 0
    lines = []
    for f in d["findings"]:
        if verify and f["grade"] != "규칙":
            continue
        tail = ""
        if f["grade"] == "규칙":
            if f["rule"] in skip:
                tail = " · 사용자 지시로 뺌, 막지 않음"
            else:
                blocking += 1
        lines.append(f'{f["line"]}:{f["col"]}  [{f["rule"]} {f["grade"]}] {f["detail"]}  "{f["excerpt"]}"  (적용: {f["scope"]}){tail}')
    return g, blocking, d["summary"]["human"], lines


def fidelity_lines(d: dict) -> tuple[dict, dict, list]:
    s = d["summary"]["by_severity"]
    lines = []
    for f in d["findings"]:
        if f["severity"] != "S1":
            continue
        where = ""
        if f["excerpt"] or f["line"] > 1:
            side = "orig" if f["side"] in ("orig", "both") else "polished"
            where = f' ({side} {f["line"]}행 "{f["excerpt"]}")' if f["excerpt"] else f" ({side} {f['line']}행)"
        lines.append(f'[{f["rule"]} S1] {RULE_NAMES[f["rule"]]} · {f["detail"]}{where}')
    return s, d["stats"], lines


def dropped_line(d: dict) -> str:
    """'빠진 것: 수치 N · 인용 N · 부정 N · 자리표시자 N · 링크 N · 각주 N'. 전부 0 이면 빈 문자열. 판정에 쓰지 않는다."""
    dr = d["summary"].get("dropped", {})
    if not any(dr.get(k, 0) for k in DROP_KINDS):
        return ""
    return "빠진 것: " + " · ".join(f"{k} {dr.get(k, 0)}" for k in DROP_KINDS)


def shrink_line(st: dict) -> str:
    """'경고: 많이 줄었다 · 글자 0.45 · 항목 0.40'. 줄지 않았으면 빈 문자열. 판정에 쓰지 않는다.
    글자는 공백 제외 글자 수의 결과 ÷ 원문, 항목은 목록 항목 수의 결과 ÷ 원문이다. 원문에 항목이 없으면 항목은 보지도 적지도 않는다."""
    co, io = st.get("chars_orig", 0), st.get("list_items_orig", 0)
    chars = st.get("chars_polished", 0) / co if co else 1.0
    items = st.get("list_items_polished", 0) / io if io else None
    if chars >= SHRINK_WARN and (items is None or items >= SHRINK_WARN):
        return ""
    return f"경고: 많이 줄었다 · 글자 {chars:.2f}" + ("" if items is None else f" · 항목 {items:.2f}")


def _block(title: str, lines: list) -> list:
    return [f"## {title}"] + (lines if lines else ["(없음)"]) + [""]


# ---------------------------------------------------------------------------
# 읽기 묶음
# ---------------------------------------------------------------------------
def guide_path(bg: dict, guide: str) -> Path | None:
    for cand in bg.get(guide, []):
        p = ROOT / cand
        if p.exists():
            return p
    return None


def md_section(md: str, key: str) -> str:
    """'11' 은 `## 11.` 절 전체, '11-2' 는 `### 11-2.` 하위절(다음 ###/## 전까지)."""
    if "-" in key:
        m = re.search(rf"^(### {key}\.[^\n]*\n.*?)(?=^##+ |\Z)", md, re.M | re.S)
    else:
        m = re.search(rf"^(## {key}\.[^\n]*\n.*?)(?=^## |\Z)", md, re.M | re.S)
    return m.group(1).strip("\n") if m else ""


def keep_blocks(section: str, labels: list) -> str:
    """§14 압축 프롬프트에서 `[라벨]` 문단 가운데 labels 에 든 것만 남긴다. 라벨이 없는 문단(표제·울타리·머리말)은 둔다."""
    out = []
    for para in re.split(r"\n\s*\n", section):
        m = re.match(r"\s*\[([^\]]+)\]", para)
        if m and m.group(1) not in labels:
            continue
        out.append(para)
    return "\n\n".join(out)


# Q1(2026-09-22) · 분포 목표를 지시에서도 뺀다. 검수에서 빼도 §14 가 같은 수치를 지시하면
# 재작성이 그쪽으로 맞춘다(마케팅 사례 평균 37.4→55.2자, 합쇼체 51→86%).
_NUM_TARGET = re.compile(r"\d+(?:\.\d+)?\s?(?:자|%|문장)(?![가-힣])|\(\d+(?:\.\d+)?~\d+(?:\.\d+)?%?\)")
_NUM_PAREN = re.compile(r"\s*\(\d+(?:\.\d+)?%\)")       # 「(4%)」만. 「(1)」 같은 열거 표시는 둔다
_S14_LABEL = re.compile(r"^\s*(\[[^\]]+\]\s*)")


def strip_numeric(section: str) -> str:
    """§14 블록에서 분포 목표가 든 문장을 지운다. 목표가 없는 지시 문장은 남긴다.

    「평균 55자(43~65), 100자 초과 14% 이하.」는 통째로 빠지고 「주장으로 열고 …」는 남는다.
    블록 라벨([문장]·[종결])은 첫 문장이 빠져도 지키고, 표제·울타리·표 줄은 건드리지 않는다.
    """
    out = []
    for line in section.split("\n"):
        if not line.strip() or line.lstrip().startswith(("```", "#", "|")):
            out.append(line)
            continue
        m = _S14_LABEL.match(line)
        label, body = (m.group(1), line[m.end():]) if m else ("", line)
        kept = [s for s in re.split(r"(?<=[.])\s+", body) if not _NUM_TARGET.search(s)]
        rebuilt = " ".join(_NUM_PAREN.sub("", s) for s in kept).strip()
        if rebuilt:
            out.append((label + rebuilt).strip())
    return "\n".join(out)


def pack(bg: dict, guide: str, sections: tuple) -> str:
    out = [f"# 읽기 묶음 · {guide} ({bg['_genre_of'].get(guide, '공통')})", ""]
    # 문체 이름으로 보고서 여부를 추측하지 않는다. 본문을 읽는 담당이 판단한다.
    out += [REPORT_TITLES.read_text(encoding="utf-8").strip(), ""]
    gp = guide_path(bg, guide) if guide != "없음" else None
    if gp is not None:
        md = unicodedata.normalize("NFC", gp.read_text(encoding="utf-8").replace("\r\n", "\n"))
        for n in sections:
            body = md_section(md, n)
            if n == "14" and body:
                body = keep_blocks(body, bg.get("_s14_blocks", {}).get(guide, []))
                if bg.get("_genre_of", {}).get(guide) in bg.get("_s14_strip_numeric", []):
                    body = strip_numeric(body)
            out += [f"## 가이드 §{n}", "", body if body else "(없음)", ""]
    exp = bg.get("_examples", {}).get(guide)
    if exp and (ROOT / exp).exists():
        out += [f"## 예문 · {guide}", "",
                unicodedata.normalize("NFC", (ROOT / exp).read_text(encoding="utf-8")).strip(), ""]
    rules_md = unicodedata.normalize("NFC", RULES_MD.read_text(encoding="utf-8").replace("\r\n", "\n"))
    out += [explain_human(load_rules(), rules_md), ""]
    if TASTE_MD.exists():
        taste = unicodedata.normalize("NFC", TASTE_MD.read_text(encoding="utf-8").replace("\r\n", "\n"))
        cut = re.search(r"^## 7\.", taste, re.M)
        out += ["## 취향 §0~§6", "", (taste[:cut.start()] if cut else taste).strip("\n"), ""]
    else:
        out += ["## 취향 §0~§6", "", "(취향 문서 없음)", ""]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 장르 힌트 — 본 컨텍스트가 원문을 읽지 않고 가이드를 고르게 한다
# ---------------------------------------------------------------------------
_TAIL = re.compile(r"[^가-힣A-Za-z0-9]+$")      # 끝의 구두점·따옴표·괄호·이모지를 뗀다
_HAPSYO = re.compile(r"(?:니다|니까|십시오|시오)$")
_HAERA = re.compile(r"(?<!니)다$")


def _no_coda(ch: str) -> bool:
    """받침 없는 한글 음절인가. 해요체의 요 앞은 받침이 없다(해요·세요·네요·까요). 「필요」·「중요」는 받침이 있어 명사로 남는다."""
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 0


def _ending(s: str) -> str:
    t = _TAIL.sub("", s.strip())
    if _HAPSYO.search(t):
        return "합쇼"
    if t.endswith("죠") or (t.endswith("요") and len(t) >= 2 and _no_coda(t[-2])):
        return "해요"
    if _HAERA.search(t):
        return "해라"
    return "명사"


def hint(text: str, is_html: bool) -> str:
    """'힌트: 줄글|개조식|애매 · 문장 N (어체 비율) · 항목 M (명사형 %) · 공백 제외 K자'.
    줄글 = 산문 문장이 셋 이상이고 명사형 종결 항목이 문장의 1/4 이하. 개조식 = 항목이 셋 이상, 명사형 60% 이상, 산문 문장이 항목보다 적음.
    둘 다 아니면 애매(섞였거나 신호가 약함). 그때는 호출자가 사용자에게 묻는다."""
    segs = segment_html(text, None) if is_html else segment_markdown(text, None)
    sents = [s for seg in segs if seg.kind == "prose" for s in split_sentences(seg.text) if not is_label(s)]
    items = [seg.text for seg in segs if seg.kind == "list" and seg.text.strip()]
    end = {"합쇼": 0, "해요": 0, "해라": 0, "명사": 0}
    for s in sents:
        end[_ending(s)] += 1
    nominal = sum(1 for t in items if _ending(t) == "명사")
    P, L = len(sents), len(items)
    if P >= HINT_MIN and nominal * HINT_PROSE_RATIO <= P:
        genre = "줄글"
    elif L >= HINT_MIN and nominal / L >= HINT_NOMINAL and P < L:
        genre = "개조식"
    else:
        genre = "애매"
    pct = (lambda n, d: f"{100 * n // d}%" if d else "-")
    chars = len("".join(normalize_text(text).split()))
    return (f"힌트: {genre} · 문장 {P} (합쇼체 {pct(end['합쇼'], P)} · 해요체 {pct(end['해요'], P)} · 해라체 {pct(end['해라'], P)}) "
            f"· 항목 {L} (명사형 {pct(nominal, L)}) · 공백 제외 {chars:,}자")


# 용도 · 줄글을 업무(공지·메일·설명문)와 블로그로 가른다(2026-09-23 Q9). 신호마다 1점, 업무가 2 이상이고 블로그보다 많으면 업무.
_BIZ = (
    re.compile(r"^\s*안녕하(?:세요|십니까)[,.! ]*\S*.*(?:님|여러분)", re.M),          # 받는 사람을 부르는 인사
    re.compile(r"(?:안내|공지|알려|보내|회신|요청|전달)(?:해\s?)?드(?:립니다|리며|리니)"),  # 안내드립니다·보내드립니다
    re.compile(r"^\s*[-•·*]?\s*(?:일시|일정|장소|대상|기간|기한|방법|신청\s?\S*|준비물|문의\S*|참석\S*)\s*[:：]", re.M),
    re.compile(r"(?:감사합니다|고맙습니다)\.?\s*$", re.M),
    re.compile(r"첨부|회신|까지\s(?:제출|신청|회신)"),
    re.compile(r"드림\s*$", re.M),
    # 표·소제목으로 정리한 공지·안내(2026-09-23 판정 초안). 「일시:」 줄 대신 제목과 소제목에 신호가 있다
    re.compile(r"^#\s.*(?:안내|공지|알림|요청|모집)(?:\s*\S{0,6})?\s*$", re.M),
    re.compile(r"^#{2,}\s*(?:일정|문의\S*|신청\S*|대상|장소|기간|준비\s?사항|결제\s?\S*|요금|변경\s?\S*)\s*$", re.M),
    re.compile(r"(?:해|하여|해서)\s?주시기\s바랍니다|부탁드립니다"),
)
_BIZ_LABEL = _BIZ[2]
_BLOG_SLANG = re.compile(r"짜치|현타|뚝딱|ㅋㅋ|ㅎㅎ|솔직히|꿀팁|찐")
_BLOG_FIRST = re.compile(r"^(?:저는|제가|저도|저의|전)\s")


def purpose(text: str, is_html: bool) -> str:
    """'용도: 업무 N · 블로그 M → 업무|블로그|애매'. 줄글에서 장피엠(블로그)과 업무 가이드를 고르는 신호다."""
    segs = segment_html(text, None) if is_html else segment_markdown(text, None)
    sents = [s for seg in segs if seg.kind == "prose" for s in split_sentences(seg.text) if not is_label(s)]
    biz = sum(1 for p in _BIZ if p.search(text)) + (1 if len(_BIZ_LABEL.findall(text)) >= 2 else 0)
    haeyo = sum(1 for s in sents if _ending(s) == "해요") / max(1, len(sents))
    blog = (2 if haeyo >= 0.35 else 1 if haeyo >= 0.2 else 0) + (1 if _BLOG_SLANG.search(text) else 0) \
        + (1 if sum(1 for s in sents if _BLOG_FIRST.match(s.strip())) >= 2 else 0) \
        + (1 if sum(1 for s in sents if s.rstrip().endswith("?")) >= 3 else 0)
    verdict = "업무" if biz >= 2 and biz > blog else "블로그" if blog >= 2 and blog > biz else "애매"
    return f"용도: 업무 {biz} · 블로그 {blog} → {verdict}"


_TASTE_RULE = re.compile(r"^W-\d+ \[(규칙|경향|관찰)\] ", re.M)


def layers(bg: dict, taste_md: Path | None = None) -> str:
    """'레이어 · 줄글: 장피엠(기본), 홍길동 · 개조식: 개조식(기본) · 취향: 없음|<버전> (규칙 N · 경향 N · 관찰 N)'.
    본 컨텍스트가 JSON·취향 문서를 열지 않고 가이드를 고르고, 기본값뿐인지·취향이 비었는지 알게 한다."""
    taste_md = TASTE_MD if taste_md is None else taste_md
    builtin = set(bg.get("_builtin", []))
    by_genre: dict = {}
    for g in guide_names(bg):
        by_genre.setdefault(bg["_genre_of"].get(g, "공통"), []).append(g + ("(기본)" if g in builtin else ""))
    parts = [f"{genre}: {', '.join(names)}" for genre, names in by_genre.items()]
    if taste_md.exists():
        md = taste_md.read_text(encoding="utf-8")
        ver = re.search(r"^- 버전:\s*(\S+)", md, re.M)
        c = {k: 0 for k in ("규칙", "경향", "관찰")}
        for m in _TASTE_RULE.finditer(md):
            c[m.group(1)] += 1
        parts.append(f"취향: {ver.group(1) if ver else '?'} (규칙 {c['규칙']} · 경향 {c['경향']} · 관찰 {c['관찰']})")
    else:
        parts.append("취향: 없음")
    return "레이어 · " + " · ".join(parts)


# 가이드 고르기 — 힌트(장르)·용도·등록부로 정한다. 본 컨텍스트는 「가이드:」 줄만 읽는다
ASK = "묻는다"
ASK_AMBIGUOUS = "힌트 애매"
ASK_MANY = "등록 가이드 둘 이상"


def _genre_of_hint(line: str) -> str:
    """hint() 한 줄에서 장르(줄글·개조식·애매)."""
    return line.split(" · ", 1)[0].split(": ", 1)[1]


def _use_of_purpose(line: str) -> str:
    """purpose() 한 줄에서 판정(업무·블로그·애매)."""
    return line.rsplit("→ ", 1)[1]


def select_guide(bg: dict, genre: str, use: str) -> tuple[str | None, str]:
    """(가이드, "") 또는 (None, 묻는 이유). genre 는 힌트 줄의 장르, use 는 용도 줄의 판정이다.
    그 장르에 기본(_builtin)이 아닌 등록 가이드가 하나면 그것, 둘 이상이면 묻고, 없으면 기본을 쓴다.
    기본이 여럿인 장르(줄글)는 용도 판정과 이름이 같은 기본 가이드(업무)를, 그런 것이 없으면 그 장르의 첫 기본 가이드(장피엠)를 쓴다.
    힌트가 애매이면(그 장르에 가이드가 없으면) 묻는다."""
    genre_of, builtin = bg.get("_genre_of", {}), bg.get("_builtin", [])
    defaults = [g for g in builtin if genre_of.get(g) == genre]
    if not defaults:
        return None, ASK_AMBIGUOUS
    mine = [g for g in guide_names(bg) if genre_of.get(g) == genre and g not in builtin]
    if len(mine) >= 2:
        return None, ASK_MANY
    if mine:
        return mine[0], ""
    return (use if use in defaults else defaults[0]), ""


# ---------------------------------------------------------------------------
def build_parser(bg: dict | None = None) -> argparse.ArgumentParser:
    bg = load_bg() if bg is None else bg
    p = argparse.ArgumentParser(prog="check_all.py", add_help=True,
                                description="네 검사기를 한 번에 돌려 짧게 낸다(읽기 전용).")
    p.add_argument("file", help="검사할 파일(.md/.html)")
    p.add_argument("--guide", required=True, choices=guide_names(bg) + ["없음"],
                   help="가이드 이름(base-guidelines.json 에 등록된 것) 또는 없음")
    p.add_argument("--genre", default=None, choices=["줄글", "개조식", "공통"], help="원칙 검사기 장르(기본 _genre_of[가이드], 없음이면 공통)")
    p.add_argument("--orig", default=None, help="원본 경로. 주면 검수 단계(불변식 포함, 막는 항목만)")
    p.add_argument("--taste-skip", default="", help="사용자가 빼라고 한 취향 W-NN(쉼표로). 판정에서 뺀다")
    p.add_argument("--pack", action="store_true", help="읽기 묶음만 출력")
    p.add_argument("--bundle", action="store_true", help="브리프 + 읽기 묶음 + 진단을 한 번에 출력(서브에이전트용)")
    p.add_argument("--hint", action="store_true", help="힌트·용도·레이어 + 가이드 줄 + 사전 검사 줄만 출력")
    p.add_argument("--sections", default=None, help="--pack 에 실을 가이드 절(예: 8,11-2,14). 기본은 _pack_sections[가이드]")
    p.add_argument("--prompt", action="store_true", help="윤문 담당이 읽을 한 장 프롬프트를 출력(P5)")
    p.add_argument("--clean", action="store_true", help="--prompt 에 기권 줄을 싣는다(사전 검사가 깨끗할 때)")
    p.add_argument("--record", default=None, help="--prompt 에 적을 작업 기록 경로(스크래치패드)")
    return p


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    bg = load_bg()
    a = build_parser(bg).parse_args(argv)
    secs = tuple(x.strip() for x in (a.sections or "").split(",") if x.strip()) \
        or tuple(bg.get("_pack_sections", {}).get(a.guide, PACK_SECTIONS))
    if a.pack:
        print(pack(bg, a.guide, secs))
        return 0
    src = Path(a.file)
    if not src.exists():
        print(f"입력 오류: {a.file}: 파일이 없다", file=sys.stderr)
        return 2
    ext = "html" if src.suffix.lower() in (".html", ".htm") else "md"
    if a.prompt:
        if not a.record:
            print("입력 오류: --prompt 에는 --record <작업 기록 경로> 가 필요하다", file=sys.stderr)
            return 2
        from prompt import build_prompt          # 순환 import 를 피해 여기서만 부른다
        print(build_prompt(bg, a.guide, src, a.clean, a.record))
        return 0
    if a.hint:
        text = strip_trailer(src.read_text(encoding="utf-8"))
        h, u = hint(text, ext == "html"), purpose(text, ext == "html")
        print(h)
        print(u)
        print(layers(bg))
        guide, why = (a.guide, "") if a.guide != "없음" else select_guide(bg, _genre_of_hint(h), _use_of_purpose(u))
        if guide is None:
            print(f"가이드: {ASK} · {why}")
            return 0
        print(f"가이드: {guide}")
        # 사전 검사 · 고른 가이드로 돌린 진단의 마지막 줄이다. 본 컨텍스트가 진단을 따로 부르지 않게 한다
        rc, out = check(bg, guide, a.genre or bg["_genre_of"].get(guide, "공통"), src, ext)
        if rc != 0:
            return rc
        print(out.splitlines()[-1])
        return 0
    if a.bundle:
        # 서브에이전트가 읽을 것 전부. 원문은 Bash 출력 상한(30K자) 때문에 싣지 않고 따로 읽게 한다.
        print(BRIEF.read_text(encoding="utf-8").rstrip("\n"), "\n", sep="")
        print(pack(bg, a.guide, secs), "\n", sep="")
    rc, out = check(bg, a.guide, a.genre or bg["_genre_of"].get(a.guide, "공통"), src, ext, a.orig, a.taste_skip)
    if out:
        print(out)
    return rc


def check(bg: dict, guide: str, genre: str, src: Path, ext: str,
          orig: str | None = None, taste_skip: str = "") -> tuple[int, str]:
    """(종료 코드, 출력). orig 가 없으면 진단(마지막 줄 「사전 검사:」), 있으면 검수(마지막 줄 「판정:」).
    짧은 글 판정과 트레일러 떼기를 여기서 한다. --hint 의 사전 검사 줄은 이 진단의 마지막 줄이다."""
    verify = orig is not None
    # 작성자 확인 트레일러는 본문이 아니다. 네 검사기 모두 그것을 뗀 사본에 대고 돌린다.
    raw = src.read_text(encoding="utf-8")
    body = strip_trailer(raw)
    tmp = None
    if body != raw:
        tmp = Path(tempfile.mkdtemp(prefix="check_all-")) / src.name
        tmp.write_bytes(body.encode("utf-8"))
    file_posix = (tmp or src).as_posix()

    ai = _json(run_cmd(bg["_checks_common"]["ai_tells"], genre=genre, file=file_posix), "check_ai_tells")
    chars = ai["stats"].get("chars_nospace", 0)
    short = genre == "줄글" and chars <= bg["_short_chars"]
    out = [f"# check_all · {'검수' if verify else '진단'} · {guide} ({ext}) · 짧은 글 {'예' if short else '아니오'} "
           f"(공백 제외 {chars:,}자){' · 작성자 확인 트레일러 뗌' if tmp else ''}", ""]

    g_hard = g_soft = 0
    kind = bg.get("_checker_kind", {}).get(guide) if guide != "없음" else None
    # none · 장르 검사기가 없는 가이드(업무, 2026-09-23). 장르 단계를 건너뛰고 원칙·취향·불변식만 본다
    if guide != "없음" and kind != "none":
        if kind not in ("style", "report"):
            print(f"입력 오류: base-guidelines.json 의 _checker_kind 에 {guide!r} 가 없다. "
                  f"styleguide-builder 의 register_guide.py 로 등록한다", file=sys.stderr)
            return 2, ""
        table = bg["_checks_short"] if short else bg["_checks"]
        g_hard, g_soft, glines = genre_lines(kind, run_cmd(table[guide][ext], file=file_posix), verify)
        out += _block(f"장르 · {guide}{' (짧은 글 명령)' if short else ''} · hard {g_hard} / soft {g_soft}", glines)

    s1, s2, s3, demoted, alines = ai_lines(ai, verify)
    out += _block(f"원칙 · check_ai_tells --genre {genre} · S1 {s1} · S2 {s2} · S3 {s3} · 강등 {demoted}", alines)

    td = _json(run_cmd(bg["_checks_common"]["taste"], file=file_posix), "check_taste")
    skip = frozenset(x.strip() for x in taste_skip.split(",") if x.strip())
    g, t_block, human, tlines = taste_lines(td, verify, skip)
    skipped = f" (사용자 지시로 뺌 {g['규칙'] - t_block})" if g["규칙"] != t_block else ""
    state = " · 문서 없음" if td.get("doc_state") == "missing" else ""
    out += _block(f"취향 · check_taste{state} · 규칙 {g['규칙']}{skipped} · 경향 {g['경향']} · 관찰 {g['관찰']} · human: {', '.join(human) or '-'}", tlines)

    if not verify:
        pre = g_hard + s1 + s2 + t_block
        out.append(f"사전 검사: {'깨끗' if pre == 0 else f'막을 것 {pre}'} · 장르 hard {g_hard} · "
                   f"원칙 S1 {s1} / S2 {s2} · 취향 규칙 {t_block}")
        return 0, "\n".join(out).rstrip("\n")

    fd = _json(run_cmd(bg["_checks_common"]["fidelity"], orig=Path(orig).as_posix(), file=file_posix), "check_fidelity")
    fs, st, flines = fidelity_lines(fd)
    out += _block(f"불변식 · check_fidelity · S1 {fs['S1']} · S2 {fs['S2']} · 길이 {st['length_ratio']} · "
                  f"문단 {st['paragraph_ratio']} · 항목 {st['list_ratio']}", flines)
    # 아래 두 줄은 알리기만 한다. 판정과 종료 코드에 들어가지 않는다.
    out += [l for l in (dropped_line(fd), shrink_line(st)) if l]
    fail = g_hard > 0 or s1 > 0 or s2 > 0 or t_block > 0 or fs["S1"] > 0
    out.append(f"판정: {'FAIL' if fail else 'PASS'} · 장르 hard {g_hard} · 원칙 S1 {s1} / S2 {s2} · "
               f"취향 규칙 {t_block} · 불변식 S1 {fs['S1']}")
    return (1 if fail else 0), "\n".join(out)


if __name__ == "__main__":
    raise SystemExit(main())
