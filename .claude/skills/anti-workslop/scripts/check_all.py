# -*- coding: utf-8 -*-
"""check_all.py — 네 검사기를 한 번에 돌려 짧게 낸다 (읽기 전용).

  python -X utf8 check_all.py --guide <가이드>|없음 FILE                   # 진단: 장르·원칙·취향. finding 한 줄씩
  python -X utf8 check_all.py --guide … --orig ORIG FILE                   # 검수: 넷 다. 막는 항목만 + 판정 한 줄. exit 1 = FAIL
  python -X utf8 check_all.py --guide … --orig ORIG --taste-skip W-01 FILE # 사용자가 빼라고 한 취향 [규칙]은 보이되 막지 않음
  python -X utf8 check_all.py --guide … --pack FILE                        # 읽기 묶음: 가이드 §8·§11-2·§14(윤문 블록), 원칙 human 행·§4, 취향 §0~§6
  python -X utf8 check_all.py --guide … --bundle FILE                      # 서브에이전트가 읽을 것 전부: 브리프 + 읽기 묶음 + 진단
  python -X utf8 check_all.py --guide 없음 --hint FILE                     # 장르 힌트(줄글·개조식·애매) + 레이어 한 줄(장르별 등록 가이드·취향 상태)

가이드 이름은 base-guidelines.json 의 밑줄 없는 최상위 키다(기본 둘 + register_guide.py 로 등록한 것).
명령은 같은 파일에서 읽는다(_checks · _checks_short · _checks_common · _checker_kind · _pack_sections · _s14_blocks). 짧은 글 판정은
스스로 한다(줄글이고 공백 제외 _short_chars 이하면 장르 명령을 _checks_short 로). 검사기 종료 코드는 보지 않고
출력만 읽는다. 검사기가 exit 2 를 내거나 죽으면 그 stderr 를 흘리고 exit 2.
"""
from __future__ import annotations
import argparse, json, re, shlex, subprocess, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ROOT = SKILL_DIR.parents[2]
BASE = SKILL_DIR / "references" / "base-guidelines.json"
BRIEF = SKILL_DIR / "references" / "subagent.md"
REPORT_TITLES = ROOT / "styleguides" / "report" / "title-claims.md"
TASTE_MD = ROOT / "taste" / "writing-taste.md"
sys.path.insert(0, str(HERE))
from check_ai_tells import (RULES_MD, explain_human, force_utf8_stdout, is_label, load_rules,   # noqa: E402
                            normalize_text, segment_html, segment_markdown, split_sentences)
from check_fidelity import RULE_NAMES                                                          # noqa: E402

# 읽기 묶음에 싣는 가이드 절의 기본값. 가이드마다 base-guidelines.json 의 _pack_sections 가 우선한다.
# §0(읽는 법)과 자동 계측 표(장피엠 §11-1·개조식 §11-2)는 검사기가 대신하므로 싣지 않는다.
PACK_SECTIONS = ("8", "14")
HINT_MIN = 3                    # 이보다 문장·항목이 적으면 장르를 고르지 않는다(애매)
HINT_NOMINAL = 0.6              # 개조식 판정에 필요한 명사형 종결 항목 비율
HINT_PROSE_RATIO = 4            # 줄글 판정: 명사형 항목 × 이 값 ≤ 산문 문장 수


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
            out += [f"## 가이드 §{n}", "", body if body else "(없음)", ""]
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
    p.add_argument("--semantic-review", help="독립 검토 JSON 기록")
    p.add_argument("--author-concern", action="store_true", help="재작성 담당이 의미 보존에 의문을 남김")
    p.add_argument("--taste-skip", default="", help="사용자가 빼라고 한 취향 W-NN(쉼표로). 판정에서 뺀다")
    p.add_argument("--pack", action="store_true", help="읽기 묶음만 출력")
    p.add_argument("--bundle", action="store_true", help="브리프 + 읽기 묶음 + 진단을 한 번에 출력(서브에이전트용)")
    p.add_argument("--hint", action="store_true", help="장르 힌트 한 줄만 출력")
    p.add_argument("--sections", default=None, help="--pack 에 실을 가이드 절(예: 8,11-2,14). 기본은 _pack_sections[가이드]")
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
    if a.hint:
        print(hint(src.read_text(encoding="utf-8"), ext == "html"))
        print(layers(bg))
        return 0
    genre = a.genre or bg["_genre_of"].get(a.guide, "공통")
    verify = a.orig is not None
    file_posix = src.as_posix()
    if a.bundle:
        # 서브에이전트가 읽을 것 전부. 원문은 Bash 출력 상한(30K자) 때문에 싣지 않고 따로 읽게 한다.
        print(BRIEF.read_text(encoding="utf-8").rstrip("\n"), "\n", sep="")
        print(pack(bg, a.guide, secs), "\n", sep="")

    ai = _json(run_cmd(bg["_checks_common"]["ai_tells"], genre=genre, file=file_posix), "check_ai_tells")
    chars = ai["stats"].get("chars_nospace", 0)
    short = genre == "줄글" and chars <= bg["_short_chars"]
    out = [f"# check_all · {'검수' if verify else '진단'} · {a.guide} ({ext}) · 짧은 글 {'예' if short else '아니오'} (공백 제외 {chars:,}자)", ""]

    g_hard = g_soft = 0
    if a.guide != "없음":
        kind = bg.get("_checker_kind", {}).get(a.guide)
        if kind not in ("style", "report"):
            print(f"입력 오류: base-guidelines.json 의 _checker_kind 에 {a.guide!r} 가 없다. "
                  f"styleguide-builder 의 register_guide.py 로 등록한다", file=sys.stderr)
            return 2
        table = bg["_checks_short"] if short else bg["_checks"]
        g_hard, g_soft, glines = genre_lines(kind, run_cmd(table[a.guide][ext], file=file_posix), verify)
        out += _block(f"장르 · {a.guide}{' (짧은 글 명령)' if short else ''} · hard {g_hard} / soft {g_soft}", glines)

    s1, s2, s3, demoted, alines = ai_lines(ai, verify)
    out += _block(f"원칙 · check_ai_tells --genre {genre} · S1 {s1} · S2 {s2} · S3 {s3} · 강등 {demoted}", alines)

    td = _json(run_cmd(bg["_checks_common"]["taste"], file=file_posix), "check_taste")
    skip = frozenset(x.strip() for x in a.taste_skip.split(",") if x.strip())
    g, t_block, human, tlines = taste_lines(td, verify, skip)
    skipped = f" (사용자 지시로 뺌 {g['규칙'] - t_block})" if g["규칙"] != t_block else ""
    state = " · 문서 없음" if td.get("doc_state") == "missing" else ""
    out += _block(f"취향 · check_taste{state} · 규칙 {g['규칙']}{skipped} · 경향 {g['경향']} · 관찰 {g['관찰']} · human: {', '.join(human) or '-'}", tlines)

    if not verify:
        print("\n".join(out).rstrip("\n"))
        return 0

    fd = _json(run_cmd(bg["_checks_common"]["fidelity"], orig=Path(a.orig).as_posix(), file=file_posix), "check_fidelity")
    fs, st, flines = fidelity_lines(fd)
    out += _block(f"불변식 · check_fidelity · S1 {fs['S1']} · S2 {fs['S2']} · 길이 {st['length_ratio']} · "
                  f"문단 {st['paragraph_ratio']} · 항목 {st['list_ratio']}", flines)
    from semantic_review import review_status
    semantic = review_status(fd["semantic_review"], a.semantic_review, a.author_concern)
    out += [f"의미 검토: {semantic['status']} · 위험 구간 {len(fd['semantic_review']['risks'])}개"]
    out += [f"작성자 확인: {item}" for item in semantic['issues']]
    out += ["자동 판정은 문맥의 의미 보존을 보증하지 않습니다."]
    fail = g_hard > 0 or s1 > 0 or s2 > 0 or t_block > 0 or fs["S1"] > 0
    out.append(f"판정: {'FAIL' if fail else 'PASS'} · 장르 hard {g_hard} · 원칙 S1 {s1} / S2 {s2} · 취향 규칙 {t_block} · 불변식 S1 {fs['S1']}")
    print("\n".join(out))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
