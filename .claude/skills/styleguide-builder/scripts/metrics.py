# -*- coding: utf-8 -*-
"""
metrics.py — 한국어 산문 문체 지표 (표준 라이브러리만 사용, 순수 함수).

- split_sentences(text): 약어(ex., a.k.a)·소수점·날짜·URL·"A." 를 보호한 뒤 문장 분할  [selftest 로 동작 고정]
- classify_ending(sentence): 합쇼체 / 해요체 / 죠 / 해라체 / 기타 + 세부 형태             [selftest 로 동작 고정]
- blocks_from_markdown(text): 마크다운·플레인 텍스트 → 블록 리스트 (표·이미지·주석·코드 제외)
- analyze_blocks(blocks, profile=None, with_rhythms=False): 지표 dict

profile(dict) 키: lexicon_watchlist, spelling_variant_table, spelling_pairs, banned, sensory, intensifiers,
conj_comma_allowed. 없으면 DEFAULT_PROFILE 값을 쓴다.
같은 입력·같은 profile 이면 항상 같은 출력을 낸다(시간·난수 없음).
"""
from __future__ import annotations

import re
import statistics as st
from collections import Counter

# ---------------------------------------------------------------------------
# 문장 분할 (동작 고정 — 바꾸면 모든 수치가 이동한다)
# ---------------------------------------------------------------------------
_PROTECT = ""   # 사용자 영역 문자: 약어·소수점의 마침표를 임시 치환
_ABBR = re.compile(r"\b(ex|Ex|a\.k\.a|A\.K\.A|e\.g|i\.e|etc|vs|cf|approx|No)\.")
_DECIMAL = re.compile(r"(\d)\.(?=\d)")
_INITIAL = re.compile(r"(?<![A-Za-z])([A-Z])\.(?=\s)")           # "A. 라이브 강의"
_URL = re.compile(r"(https?://\S+|[\w-]+\.(?:com|kr|io|dev|net|org|co|ai|me)\S*)")
_TERMINAL = re.compile(r"[.!?…]+[\"”’')\]]*(?=\s|$)")
_CLOSERS = ".!?…\"”’')] \t~^;:_"


def _protect(t: str) -> str:
    t = _ABBR.sub(lambda m: m.group(0).replace(".", _PROTECT), t)
    t = _URL.sub(lambda m: m.group(0).replace(".", _PROTECT), t)
    t = _DECIMAL.sub(lambda m: m.group(1) + _PROTECT, t)
    t = _INITIAL.sub(lambda m: m.group(1) + _PROTECT, t)
    return t


def split_sentences(text: str) -> list[str]:
    t = _protect(re.sub(r"\s+", " ", text.strip()))
    out, start = [], 0
    for m in _TERMINAL.finditer(t):
        seg = t[start : m.end()].strip()
        if seg:
            out.append(seg)
        start = m.end()
    tail = t[start:].strip()
    if tail:
        out.append(tail)
    return [s.replace(_PROTECT, ".") for s in out if len(s.replace(_PROTECT, ".")) >= 2]


def is_label(sentence: str) -> bool:
    """구두점 없이 끝나는 20자 이하 조각('[노션의 장점]', 'A. 라이브 강의')은 문장이 아니라 소표제로 본다."""
    return len(sentence) <= 20 and not re.search(r"[.!?…]", sentence)


# ---------------------------------------------------------------------------
# 종결어미 (동작 고정)
# ---------------------------------------------------------------------------
_HAEYO_SUB = ["는데요", "거든요", "더군요", "군요", "네요", "고요", "까요", "세요", "데요", "게요", "죠", "지요",
              "해요", "에요", "예요", "어요", "아요", "래요"]


def _is_emoji(ch: str) -> bool:
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0xFE00 <= o <= 0xFE0F or o == 0x200D or o == 0x2B07


def _core(sentence: str) -> str:
    """문장 끝의 구두점·따옴표·괄호·이모지·'ㅎㅎ'를 벗겨 어미만 남긴다. 한글은 건드리지 않는다."""
    s = sentence.rstrip()
    while s and (s[-1] in _CLOSERS or _is_emoji(s[-1]) or s[-1] in "ㅎㅋ"):
        s = s[:-1]
    return s


def classify_ending(sentence: str) -> tuple[str, str]:
    """(대분류, 세부형태). 대분류: 합쇼체 / 해요체 / 죠 / 해라체 / 기타"""
    c = _core(sentence)
    if not c:
        return "기타", ""
    if c.endswith("니다"):
        for suf in ["겠습니다", "것입니다", "겁니다", "였습니다", "었습니다", "았습니다", "있습니다", "없습니다",
                    "입니다", "합니다", "됩니다", "습니다", "ㅂ니다"]:
            if c.endswith(suf):
                return "합쇼체", suf
        return "합쇼체", "니다"
    if c.endswith("십시오"):
        return "합쇼체", "십시오"
    if c.endswith("죠") or c.endswith("지요"):
        return "죠", "죠"
    if c.endswith("요"):
        for suf in _HAEYO_SUB:
            if c.endswith(suf):
                return "해요체", suf
        return "해요체", "요"
    if c.endswith("다"):
        return "해라체", "다"
    if c.endswith("까") or c.endswith("나") or c.endswith("냐"):
        return "해라체", "의문"
    return "기타", ""


# ---------------------------------------------------------------------------
# 사전
# ---------------------------------------------------------------------------
CONJ = ["그러나", "하지만", "그런데", "그래서", "따라서", "또한", "그리고", "즉", "물론", "다만", "한편", "반면에", "반면",
        "오히려", "예를 들어", "예를 들면", "결국", "그럼에도", "그렇다면", "그러면", "왜냐하면", "게다가", "더불어",
        "특히", "사실", "우선", "먼저", "마지막으로", "참고로", "아무튼", "어쨌든", "그러므로", "그렇기 때문에",
        "그렇지만", "실제로", "반대로", "대신", "더해서", "다시 말해", "요약하면", "정리하면", "결론적으로", "아울러"]
CONJ_RE = re.compile(r"^(" + "|".join(re.escape(c) for c in sorted(CONJ, key=len, reverse=True)) + r")(?=[\s,])")
_CONJ_ANY = {c: re.compile(r"(?<![가-힣])" + re.escape(c) + r"(?![가-힣])") for c in CONJ}

DEFAULT_PROFILE = {
    "lexicon_watchlist": ["경험", "수익", "실행", "검증", "전문성", "포지셔닝", "피드백"],
    "spelling_variant_table": {"컨텐츠": "콘텐츠", "타겟": "타깃", "셋팅": "세팅", "런칭": "론칭", "팬더믹": "팬데믹",
                               "트랜드": "트렌드", "왠만": "웬만"},
    "spelling_pairs": {},
    "banned": ["한편", "그러므로", "게다가", "더불어", "아울러", "요약하면", "정리하면", "결론적으로", "마지막으로", "에 있어",
               "함으로써", "알아보겠습니다", "살펴보겠습니다", "핵심 포인트", "이 글에서는"],
    "sensory": ["반짝", "부드러", "따뜻", "차가운", "향기", "눈부", "설레", "아름다", "빛나는", "싱그러", "포근", "은은", "찬란"],
    "intensifiers": ["정말", "매우", "아주", "꽤", "무척", "굉장히", "너무", "엄청", "상당히"],
    "conj_comma_allowed": ["다만", "더해서", "즉", "반면", "반면에"],
}


def _prof(profile: dict | None, key: str):
    if profile and key in profile and profile[key] is not None:
        return profile[key]
    return DEFAULT_PROFILE[key]


_COMMA_CLASSES = [
    ("접속부사 뒤", re.compile(r"^(그리고|또한|그러나|하지만|그래서|따라서|물론|다만|즉|결국|반면에|반면|더해서|우선|먼저|특히|사실|오히려|그렇다면|예를 들어|참고로|또|한편|게다가)$")),
    ("-고,", re.compile(r"고$")), ("-며,", re.compile(r"며$")), ("-지만,", re.compile(r"지만$")),
    ("-면,", re.compile(r"면$")), ("-니,", re.compile(r"니$")), ("-데,", re.compile(r"데$")),
    ("-서,", re.compile(r"서$")), ("-나,", re.compile(r"나$")), ("-도,", re.compile(r"도$")),
    ("주어/주제어 뒤", re.compile(r"(은|는|이|가)$")),
    ("명사 나열", re.compile(r"[가-힣A-Za-z0-9)\]]$")),
]


def _comma_class(word: str) -> str:
    for name, rx in _COMMA_CLASSES:
        if rx.search(word):
            return name
    return "기타"


# ---------------------------------------------------------------------------
# 블록 파서 (마크다운 / 플레인)
# ---------------------------------------------------------------------------
_MD_INLINE = [
    (re.compile(r"!\[[^\]]*\]\([^)]*\)"), ""),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"`([^`]*)`"), r"\1"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"\1"),
    (re.compile(r"__([^_]+)__"), r"\1"),
    (re.compile(r"(?<!\w)\*([^*]+)\*(?!\w)"), r"\1"),
    (re.compile(r"<[^>]+>"), ""),
]


def _strip_inline(s: str) -> str:
    for rx, rep in _MD_INLINE:
        s = rx.sub(rep, s)
    return re.sub(r"\s+", " ", s).strip()


def blocks_from_markdown(text: str) -> list[dict]:
    """반환: [{'tag': 'h'|'p'|'li'|'quote'|'hr'|'table', 'text': str}].
    코드 블록·YAML 헤더·HTML 주석·이미지 전용 줄은 버리고, 표 줄은 'table' 블록 하나로 묶는다(문장 통계 제외)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[0].strip() == "---":            # front matter
        try:
            end = lines.index("---", 1)
            lines = lines[end + 1 :]
        except ValueError:
            pass
    blocks, buf, in_code, in_comment, in_table = [], [], False, False, False

    def flush():
        if buf:
            t = _strip_inline(" ".join(buf))
            if t:
                blocks.append({"tag": "p", "text": t})
            buf.clear()

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if in_comment:
            if "-->" in s:
                in_comment = False
            continue
        if s.startswith("<!--"):
            flush()
            if "-->" not in s:
                in_comment = True
            continue
        if s.startswith("```") or s.startswith("~~~"):
            in_code = not in_code
            flush()
            continue
        if in_code:
            continue
        if s.startswith("|"):
            flush()
            if not in_table:
                blocks.append({"tag": "table", "text": "[table]"})
                in_table = True
            continue
        in_table = False
        if not s:
            flush()
            continue
        if re.match(r"^!\[[^\]]*\]\([^)]*\)\s*$", s):      # 이미지 전용 줄
            flush()
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})\s*$", s):
            flush(); blocks.append({"tag": "hr", "text": "---"}); continue
        m = re.match(r"^#{1,6}\s+(.*)$", s)
        if m:
            flush(); blocks.append({"tag": "h", "text": _strip_inline(m.group(1))}); continue
        # '+ ' 는 한국어 글에서 문단 접두어(추신)로 쓰이므로 목록 표지로 보지 않는다
        m = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", s)
        if m:
            flush(); blocks.append({"tag": "li", "text": _strip_inline(m.group(1))}); continue
        m = re.match(r"^>\s?(.*)$", s)
        if m:
            flush(); blocks.append({"tag": "quote", "text": _strip_inline(m.group(1))}); continue
        buf.append(s)
    flush()
    return [b for b in blocks if b["text"]]


# ---------------------------------------------------------------------------
# 지표 계산
# ---------------------------------------------------------------------------
def _pct(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


_HEAD_TAGS = ("h", "h1", "h2", "h3", "h4")


def analyze_blocks(blocks: list[dict], profile: dict | None = None, with_rhythms: bool = False) -> dict:
    paras = [b["text"] for b in blocks if b["tag"] == "p"]
    heads = [b["text"] for b in blocks if b["tag"] in _HEAD_TAGS]
    lis = [b["text"] for b in blocks if b["tag"] == "li"]
    n_tables = sum(1 for b in blocks if b["tag"] == "table")

    para_sents: list[list[str]] = []
    labels = 0
    for p in paras:
        ss = split_sentences(p)
        kept = [s for s in ss if not is_label(s)]
        labels += len(ss) - len(kept)
        if kept:
            para_sents.append(kept)
    sents = [s for ss in para_sents for s in ss]
    N = len(sents)
    if N == 0:
        return {"n_sentences": 0, "error": "본문 문장이 없습니다."}

    lens = [len(s) for s in sents]
    body = " ".join(sents)

    # 종결어미
    ending_major, ending_sub = Counter(), Counter()
    for s in sents:
        maj, sub = classify_ending(s)
        ending_major[maj] += 1
        ending_sub[(maj, sub)] += 1
    questions = sum(1 for s in sents if s.rstrip().endswith("?"))
    consecutive_haeyo = 0
    for ss in para_sents:
        prev = None
        for s in ss:
            maj = classify_ending(s)[0]
            if maj in ("해요체", "죠") and prev in ("해요체", "죠"):
                consecutive_haeyo += 1
            prev = maj

    # 접속부사
    allowed = set(_prof(profile, "conj_comma_allowed"))
    conj_start = Counter()
    conj_comma_bad = 0
    conj_consecutive = 0
    for ss in para_sents:
        prev_conj = False
        for s in ss:
            m = CONJ_RE.match(s)
            if m:
                conj_start[m.group(1)] += 1
                if s[m.end() : m.end() + 1] == "," and m.group(1) not in allowed:
                    conj_comma_bad += 1
                if prev_conj:
                    conj_consecutive += 1
                prev_conj = True
            else:
                prev_conj = False
    conj_total = {c: len(rx.findall(body)) for c, rx in _CONJ_ANY.items()}
    conj_total = {k: v for k, v in sorted(conj_total.items(), key=lambda kv: (-kv[1], kv[0])) if v}

    # 쉼표
    commas_sent = [s.count(",") for s in sents]
    commas_para = [sum(s.count(",") for s in ss) for ss in para_sents]
    comma_pos = Counter()
    for s in sents:
        for m in re.finditer(r"(\S+),", s):
            comma_pos[_comma_class(m.group(1))] += 1
    total_commas = sum(comma_pos.values())

    # 문단 구조
    spp = [len(ss) for ss in para_sents]
    firsts = [len(ss[0]) for ss in para_sents]
    lasts = [len(ss[-1]) for ss in para_sents if len(ss) >= 2]
    paras_with_paren = sum(1 for ss in para_sents if any("(" in s for s in ss))

    # 길이 전이·문단 패턴·장문 뒤 문장
    def cat(l): return "S" if l <= 30 else ("M" if l <= 70 else "L")
    trans = Counter()
    patterns = Counter()
    after_long = []
    for ss in para_sents:
        for a, b in zip(ss, ss[1:]):
            trans[cat(len(a)) + cat(len(b))] += 1
            if len(a) >= 90:
                after_long.append(len(b))
        if len(ss) >= 3:
            patterns["".join(cat(len(x)) for x in ss)] += 1
    ntrans = sum(trans.values())
    bins = [(0, 20), (21, 35), (36, 50), (51, 70), (71, 100), (101, 10**6)]
    len_bins = {f"{a}~{b if b < 10**6 else ''}": _pct(sum(1 for l in lens if a <= l <= b), N) for a, b in bins}

    # 어휘·구문
    def cnt(pat): return len(re.findall(pat, body))
    sensory = {w: cnt(re.escape(w)) for w in _prof(profile, "sensory") if cnt(re.escape(w))}
    banned = {w: cnt(re.escape(w)) for w in _prof(profile, "banned") if cnt(re.escape(w))}
    nonpref = {w: cnt(re.escape(w)) for w in _prof(profile, "spelling_pairs") if cnt(re.escape(w))}
    intens = {w: cnt(re.escape(w)) for w in _prof(profile, "intensifiers") if cnt(re.escape(w))}
    variants = {}
    for a, b in _prof(profile, "spelling_variant_table").items():
        ca, cb = cnt(re.escape(a)), cnt(re.escape(b))
        if ca == 0 and cb == 0:
            continue
        pref = a if (ca >= 2 and ca >= 3 * cb) else (b if (cb >= 2 and cb >= 3 * ca) else "혼용")
        variants[f"{a}/{b}"] = {"a": a, "b": b, "a_count": ca, "b_count": cb, "preferred": pref}
    contrast = cnt(r"(이|가|것이) (아니라|아닌)") + cnt(r"보다는") + cnt(r"\s말고")
    eng_gloss = cnt(r"[가-힣]+\s?\([A-Za-z][A-Za-z .\-]+\)")
    first_person_author = sum(1 for s in sents if re.match(r"(저는|제가|저도|저 역시|저희|저의)", s))
    _generic_rx = re.compile(r"(^|\s)(내|나|나만의|나를|내가|나 자신)(\s|가|를|은|는|도|만|에)")
    first_person_generic = sum(1 for s in sents if _generic_rx.search(s))
    mixed_first_person = sum(1 for s in sents if _generic_rx.search(s) and re.search(r"(저는|제가|저도|제 )", s))
    lexicon = {w: cnt(re.escape(w)) for w in _prof(profile, "lexicon_watchlist")}
    lexicon = {k: v for k, v in sorted(lexicon.items(), key=lambda kv: (-kv[1], kv[0])) if v}
    numeric = sum(1 for s in sents if re.search(r"\d", s))
    past = sum(1 for s in sents if re.search(r"(었|았|였|했)(습니다|고요|네요|죠|는데요|거든요|어요)$", _core(s)))

    # 시작·끝
    first_para = para_sents[0][0] if para_sents else ""
    if re.match(r"(저는|제가|저희|안녕하세요)", first_para) or (re.search(r"(안녕하세요|입니다\.$)", first_para) and re.match(r"(저|제)", first_para)):
        opening = "이력/인사"
    elif "?" in first_para:
        opening = "질문"
    elif re.search(r"(은|는) .*(입니다|말합니다)\.?$", first_para):
        opening = "정의"
    else:
        opening = "배경/기타"
    last_sent = para_sents[-1][-1] if para_sents else ""
    last_core = _core(last_sent)
    closing_ok = bool(re.search(
        r"(세요|바랍니다|바라겠습니다|좋겠습니다|좋겠네요|것입니다|겁니다|생각합니다|확신합니다|기대합니다|겠습니다|드립니다|"
        r"덕분입니다|감사합니다|싶네요|싶습니다|싶어요|드림|배워요|주세요|해요|까요|할까요)$", last_core)) or last_sent.rstrip().endswith("!")
    closing_summary = bool(re.match(r"(요약하면|정리하면|결론적으로|마지막으로|정리하자면)", last_sent)) or any(
        re.match(r"(요약하면|정리하면|결론적으로|정리하자면)", ss[0]) for ss in para_sents[-2:])

    # 표제
    h_q = sum(1 for h in heads if h.rstrip().endswith("?"))
    h_imp = sum(1 for h in heads if re.search(r"(세요|하자|보자|라)[.!]?$", h))
    h_da = sum(1 for h in heads if re.search(r"다[.!]?$", h) and not re.search(r"(세요|하자|보자|라)[.!]?$", h))
    h_num = sum(1 for h in heads if re.match(r"\(?\d", h))
    h_noun = len(heads) - h_q - h_imp - h_da
    nh = len(heads)

    # AI 티 서식
    bullet_bold = sum(1 for b in blocks if b["tag"] == "li" and re.match(r"^\*\*|^[^:]{1,25}:\s", b["text"]))
    one_sentence_paras = sum(1 for n in spp if n == 1)

    out = {
        "n_sentences": N, "n_paragraphs": len(para_sents), "n_headings": nh, "n_list_items": len(lis), "n_tables": n_tables,
        "n_labels_excluded": labels, "chars": sum(lens), "post_chars": sum(len(p) for p in paras),
        "len_mean": round(st.mean(lens), 1), "len_median": st.median(lens), "len_sd": round(st.pstdev(lens), 1) if N > 1 else 0,
        "len_max": max(lens), "words_mean": round(st.mean(len(s.split()) for s in sents), 1),
        "pct_short_le35": _pct(sum(1 for l in lens if l <= 35), N),
        "pct_mid_36_70": _pct(sum(1 for l in lens if 36 <= l <= 70), N),
        "pct_long_gt70": _pct(sum(1 for l in lens if l > 70), N),
        "pct_xlong_gt100": _pct(sum(1 for l in lens if l > 100), N),
        "sent_per_para_mean": round(st.mean(spp), 2), "sent_per_para_median": st.median(spp),
        "pct_para_3_4": _pct(sum(1 for n in spp if 3 <= n <= 4), len(spp)),
        "pct_para_1": _pct(one_sentence_paras, len(spp)),
        "pct_para_with_paren": _pct(paras_with_paren, len(spp)),
        "para_first_len": round(st.mean(firsts), 1), "para_last_len": round(st.mean(lasts), 1) if lasts else 0,
        "transitions_pct": {k: _pct(v, ntrans) for k, v in sorted(trans.items())},
        "len_bins_pct": len_bins,
        "para_patterns_top": dict(patterns.most_common(8)),
        "after_long_next_mean": round(st.mean(after_long), 1) if after_long else 0,
        "after_long_pct_le40": _pct(sum(1 for l in after_long if l <= 40), len(after_long)),
        "after_long_n": len(after_long),
        "pct_hapsyo": _pct(ending_major["합쇼체"], N), "pct_haeyo": _pct(ending_major["해요체"], N),
        "pct_jyo": _pct(ending_major["죠"], N), "pct_haera": _pct(ending_major["해라체"], N),
        "pct_other_ending": _pct(ending_major["기타"], N), "pct_question": _pct(questions, N),
        "ending_detail": {f"{k[0]}:{k[1]}": v for k, v in sorted(ending_sub.items(), key=lambda kv: (-kv[1], kv[0]))},
        "consecutive_haeyo": consecutive_haeyo,
        "pct_saenggak": _pct(sum(1 for s in sents if re.search(r"생각합니다$", _core(s))), N),
        "pct_geot_gatda": _pct(sum(1 for s in sents if re.search(r"것 같습니다$", _core(s))), N),
        "pct_geot_ipnida": _pct(sum(1 for s in sents if re.search(r"(것입니다|겁니다)$", _core(s))), N),
        "pct_conj_start": _pct(sum(conj_start.values()), N),
        "conj_top": dict(conj_start.most_common(12)),
        "conj_total": conj_total,
        "conj_comma_bad": conj_comma_bad, "conj_consecutive": conj_consecutive,
        "commas_per_sent": round(st.mean(commas_sent), 2), "commas_per_para": round(st.mean(commas_para), 2),
        "pct_sent_no_comma": _pct(sum(1 for c in commas_sent if c == 0), N),
        "pct_sent_2plus_comma": _pct(sum(1 for c in commas_sent if c >= 2), N),
        "comma_position_pct": {k: _pct(v, total_commas) for k, v in comma_pos.most_common()},
        "comma_after_subject": comma_pos.get("주어/주제어 뒤", 0),
        "pct_list_or_go_comma": _pct(comma_pos.get("명사 나열", 0) + comma_pos.get("-고,", 0), total_commas),
        "parens": body.count("("), "slashes": cnt(r"[가-힣A-Za-z]/[가-힣A-Za-z]"), "eng_gloss": eng_gloss,
        "exclaim": cnt(r"!"), "emoticons": cnt(r":\)|\^\^|ㅎㅎ|ㅋㅋ|[\U0001F300-\U0001FAFF]"),
        "ye_reul_deureo": cnt(r"예를 들어|예를 들면|예컨대|가령"),
        "yeoreobun_dangsin": cnt(r"여러분|당신"),
        "sensory": sensory, "banned": banned, "nonpreferred_spelling": nonpref, "intensifiers": intens,
        "spelling_variants": variants,
        "contrast_constructions": contrast, "pct_contrast": _pct(contrast, N),
        "tonghae": cnt(r"통해"), "pct_tonghae": _pct(cnt(r"통해"), N),
        "pct_first_person_author_start": _pct(first_person_author, N),
        "pct_generic_first_person": _pct(first_person_generic, N),
        "mixed_first_person": mixed_first_person,
        "lexicon": lexicon,
        "pct_numeric_sent": _pct(numeric, N), "pct_past": _pct(past, N),
        "opening_type": opening, "opening_sentence": first_para[:160],
        "closing_sentence": last_sent[-160:], "closing_is_call_or_outlook": closing_ok, "closing_is_summary": closing_summary,
        "heading_forms": {"total": nh, "question": h_q, "imperative": h_imp, "da": h_da, "noun": h_noun, "numbered": h_num,
                          "question_pct": _pct(h_q, nh), "imperative_pct": _pct(h_imp, nh), "da_pct": _pct(h_da, nh),
                          "noun_pct": _pct(h_noun, nh), "numbered_pct": _pct(h_num, nh)},
        "has_lesson_section": any(re.search(r"(느낀 점|배운 점|배운 것|느낀 것)", h) for h in heads),
        "ai_bullet_bold": bullet_bold,
    }
    if with_rhythms:
        out["para_rhythms"] = [[len(s) for s in ss] for ss in para_sents]
    return out
