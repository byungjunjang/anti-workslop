# -*- coding: utf-8 -*-
"""parse_ko.py — 한국어 개조식 보고서 코퍼스를 항목(불릿) 단위로 파싱한다.

입력: corpus/text/*.txt (PyMuPDF로 추출한 텍스트, <<<PAGE n>>> 구분자 포함)
출력: corpus/items_ko.jsonl  — 항목 1건 = 1행
      corpus/docs_ko.json    — 문서(호) 단위 요약(표·그림 수, 항목 수, 소제목 수 등)
      corpus/titles_ko.json  — NABO Focus 1~100호 제목 목록(목차에서 추출)

실행: python -X utf8 parse_ko.py
표준 라이브러리만 사용한다.

파싱 규칙(요약)
- 불릿 기호로 계층을 판정한다. NABO: ≐/▪(1단) · -/‑(2단) · •/・(3단). 국립국어원 예시: □(1단) · ○(2단) · -(3단).
- 기호 없는 줄은 직전 항목의 이어지는 줄로 본다. 단 표 캡션·각주·주석(※ *)·숫자만 있는 줄·쪽 번호는 항목을 끝낸다.
- 15자 이하의 짧은 한글 줄은 '옆제목(소제목)' 후보로 따로 모은다(근사치).
- 종결 유형은 마지막 어절의 꼬리로 분류한다(각주 번호·문장부호 제거 후).
"""
import json, re, os
from collections import Counter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 키트 루트 (scripts/ 의 부모)
TEXT = os.path.join(HERE, "corpus", "text")
OUT = os.path.join(HERE, "corpus")

HANGUL = re.compile(r"[가-힣]")
CAPTION = re.compile(r"^(\[표|\[그림|그림\s*\d|표\s*\d|\(단위|자료\s*:|자료:|주\s*:|주:|출처|※\s*자료)")
FOOTNOTE = re.compile(r"^\d{1,2}\)\s")
NOTE = re.compile(r"^[※\*]\s*")
NUMERIC_LINE = re.compile(r"^[\d\s,\.\-–△▲+%()~’'\/:]+$")
TABLE_HEAD = {"구분", "주요 내용", "주요내용", "비고", "일자", "내용", "구 분", "합계", "계", "연도"}
PAGE_MARK = re.compile(r"^(포커스|\d{1,3})$")

SYMBOLS = {
    "nabo": {1: re.compile(r"^[≐▪]\s*"), 2: re.compile(r"^(‑‑|‑|-|–)\s*(?![\d△▲])"), 3: re.compile(r"^[•・·]\s*")},
    "nikl": {1: re.compile(r"^□\s*"), 2: re.compile(r"^○\s*"), 3: re.compile(r"^-\s*(?![\d△▲])")},
}

CONNECTIVES = ["다만", "그러나", "또한", "한편", "특히", "아울러", "이에", "따라서", "반면", "향후", "이후", "그동안",
               "최근", "우선", "먼저", "이를 위해", "나아가", "즉", "그 외", "그외", "이와 같은", "이러한", "상기"]
CONN_RE = re.compile(r"^(" + "|".join(re.escape(c) for c in CONNECTIVES) + r")[\s,]")
PAREN_HEAD = re.compile(r"^[\(（]([^\)）]{1,14})[\)）]")
NUM_RE = re.compile(r"\d[\d,\.]*")

MIEUM = set("함음임됨짐림옴줌봄뿜씀")
NOUN_EXCEPT_MIEUM = {"책임", "위임", "수임", "모임", "믿음", "도움", "결함", "손실", "수입", "신임"}


def read_pages(path):
    t = open(path, encoding="utf-8").read()
    parts = t.split("<<<PAGE ")
    pages = {}
    for x in parts[1:]:
        n, body = x.split(">>>", 1)
        pages[int(n.strip())] = body
    return pages


def strip_tail(text):
    """각주 번호와 꼬리 문장부호를 떼어 마지막 토큰 판단용 문자열을 만든다."""
    s = re.sub(r"\s+", " ", text.strip())
    while re.search(r"[가-힣)\]”’\.]\d{1,2}\)$", s):
        s = re.sub(r"\d{1,2}\)$", "", s).rstrip()
    return s.rstrip(" .。,;:")


def classify_ending(text):
    s = strip_tail(text)
    if not s:
        return "기타", ""
    last = s[-1]
    if last in ")）]":
        return "괄호부연", s[-8:]
    if re.search(r"[\d%]$", s) or re.search(r"\d(원|명|건|개|호|년|월|일|p)$", s):
        return "수치", s[-6:]
    if not HANGUL.search(last):
        return "기타", s[-6:]
    if last == "다":
        return "종결어미(-다)", s[-4:]
    if s.endswith("필요"):
        return "필요", s[-4:]
    if s.endswith("요망") or s.endswith("바람"):
        return "요망/바람", s[-4:]
    if s.endswith("요"):
        return "종결어미(-요)", s[-4:]
    if s.endswith("중") or s.endswith("중임"):
        return "-중(진행)", s[-4:]
    if s.endswith("것") or s.endswith("것임"):
        return "-것", s[-4:]
    if s.endswith("등"):
        return "등(열거)", s[-4:]
    if s.endswith("필요"):
        return "필요", s[-4:]
    if s.endswith("요망") or s.endswith("바람"):
        return "요망/바람", s[-4:]
    if last in MIEUM and s[-2:] not in NOUN_EXCEPT_MIEUM:
        return "명사형어미(-ㅁ)", s[-4:]
    return "체언(명사구)", s[-4:]


def make_item(corpus, doc_id, level, lines, page):
    text = re.sub(r"\s+", " ", " ".join(l.strip() for l in lines)).strip()
    ending_class, ending_token = classify_ending(text)
    nospace = re.sub(r"\s", "", text)
    spaced = " " in text and (len(text.split()) >= max(2, len(nospace) // 12))
    return {
        "corpus": corpus, "doc": doc_id, "level": level, "page": page,
        "text": text, "n_chars": len(text), "n_chars_nospace": len(nospace),
        "n_eojeol": len(text.split()) if spaced else None,
        "n_lines": len(lines),
        "ending_class": ending_class, "ending_token": ending_token,
        "has_digit": bool(re.search(r"\d", text)), "n_numbers": len(NUM_RE.findall(text)),
        "paren_head": bool(PAREN_HEAD.match(text)),
        "connective": (CONN_RE.match(text).group(1) if CONN_RE.match(text) else None),
    }


def is_short_heading(line):
    s = line.strip()
    return 2 <= len(s) <= 15 and bool(HANGUL.search(s)) and not re.search(r"\d", s) and s not in TABLE_HEAD and not CAPTION.match(s)


def parse_doc(corpus, doc_id, pages, symbols):
    items, headings = [], []
    n_tables = n_figs = 0
    state = {"cur": None}

    def flush():
        if state["cur"] and state["cur"][1]:
            lvl, lines, pno = state["cur"]
            items.append(make_item(corpus, doc_id, lvl, lines, pno))
        state["cur"] = None

    for pno in sorted(pages):
        heading_buf = []

        def close_heading():
            if heading_buf:
                headings.append(" ".join(heading_buf))
                heading_buf.clear()

        for raw in pages[pno].split("\n"):
            line = raw.strip()
            if not line:
                flush(); close_heading(); continue
            if line.startswith("[표"):
                n_tables += 1
            if line.startswith("[그림") or re.match(r"^그림\s*\d", line):
                n_figs += 1
            lvl, body = None, ""
            for L, rx in symbols.items():
                m = rx.match(line)
                if m:
                    lvl, body = L, line[m.end():].strip()
                    break
            if lvl:
                flush(); close_heading()
                state["cur"] = (lvl, [body] if body else [], pno)
                continue
            if CAPTION.match(line) or FOOTNOTE.match(line) or NOTE.match(line) or PAGE_MARK.match(line) \
                    or NUMERIC_LINE.match(line) or line in TABLE_HEAD:
                flush(); close_heading(); continue
            cur = state["cur"]
            if cur is not None:
                if not cur[1] or len(line) >= 10 or (len(line) >= 3 and not is_short_heading(line)):
                    cur[1].append(line)
                    continue
                flush()
            if is_short_heading(line):
                heading_buf.append(line)
            else:
                close_heading()
        flush(); close_heading()
    return items, headings, n_tables, n_figs


def doc_summary(corpus, items, headings, nt, nf, extra):
    d = {"corpus": corpus, "n_items": len(items),
         "n_L1": sum(1 for x in items if x["level"] == 1), "n_L2": sum(1 for x in items if x["level"] == 2),
         "n_L3": sum(1 for x in items if x["level"] == 3), "n_tables": nt, "n_figures": nf,
         "n_headings_approx": len(headings), "headings_approx": headings[:40]}
    d.update(extra)
    return d


def parse_nabo_compilation():
    pages = read_pages(os.path.join(TEXT, "nabo_focus_100_compilation.txt"))
    toc_lines = []
    for p in (3, 4, 5, 6):
        toc_lines += [l.strip() for l in pages[p].split("\n") if l.strip()]
    titles, i = [], 0
    while i < len(toc_lines):
        m = re.match(r"^(\d{1,3})호$", toc_lines[i])
        if m:
            no, j, tl = int(m.group(1)), i + 1, []
            while j < len(toc_lines) and not re.match(r"^\d{1,3}$", toc_lines[j]) and not re.match(r"^\d{1,3}호$", toc_lines[j]):
                tl.append(toc_lines[j]); j += 1
            start = int(toc_lines[j]) if j < len(toc_lines) and re.match(r"^\d{1,3}$", toc_lines[j]) else None
            title = re.sub(r"[\x00-\x1f]", "", " ".join(tl))
            titles.append({"no": no, "title": re.sub(r"\s+", " ", title).strip(), "start_printed": start})
            i = j + 1
        else:
            i += 1
    OFFSET = 1  # 인쇄쪽 7 = PDF 8쪽
    all_items, doc_info = [], {}
    for k, t in enumerate(titles):
        if t["start_printed"] is None:
            continue
        s = t["start_printed"] + OFFSET
        nxt = titles[k + 1]["start_printed"] if k + 1 < len(titles) else None
        e = (nxt + OFFSET - 1) if nxt else max(pages)
        sub = {p: pages[p] for p in range(s, e + 1) if p in pages}
        doc_id = f"nabo_{t['no']:03d}"
        items, headings, nt, nf = parse_doc("nabo_compilation", doc_id, sub, SYMBOLS["nabo"])
        all_items += items
        doc_info[doc_id] = doc_summary("nabo_compilation", items, headings, nt, nf,
                                       {"no": t["no"], "title": t["title"], "pages": len(sub)})
    return all_items, doc_info, titles


def parse_nabo_standalone():
    all_items, doc_info = [], {}
    for fn, no in [("nabo_focus_082.txt", 82), ("nabo_focus_084.txt", 84), ("nabo_focus_085.txt", 85), ("nabo_focus_086.txt", 86)]:
        pages = read_pages(os.path.join(TEXT, fn))
        doc_id = f"nabo_sa_{no:03d}"
        items, headings, nt, nf = parse_doc("nabo_standalone", doc_id, pages, SYMBOLS["nabo"])
        all_items += items
        doc_info[doc_id] = doc_summary("nabo_standalone", items, headings, nt, nf, {"no": no, "pages": len(pages)})
    return all_items, doc_info


def parse_nikl_examples():
    pages = read_pages(os.path.join(TEXT, "nikl_public_language_2022_excerpts.txt"))
    all_items, doc_info = [], {}
    for p in [71, 73, 75, 77, 79, 81, 83, 85, 87, 89, 91, 93, 95]:
        if p not in pages:
            continue
        body = re.sub(r"[❶-❿⓫-⓴➀-➓]", "", pages[p])  # 교정 번호 기호 제거
        doc_id = f"nikl_p{p}"
        items, headings, nt, nf = parse_doc("nikl_examples", doc_id, {p: body}, SYMBOLS["nikl"])
        all_items += items
        doc_info[doc_id] = doc_summary("nikl_examples", items, headings, nt, nf, {"page": p})
    return all_items, doc_info


def main():
    items1, docs1, titles = parse_nabo_compilation()
    items2, docs2 = parse_nabo_standalone()
    items3, docs3 = parse_nikl_examples()
    items = items1 + items2 + items3
    with open(os.path.join(OUT, "items_ko.jsonl"), "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    docs = {**docs1, **docs2, **docs3}
    json.dump(docs, open(os.path.join(OUT, "docs_ko.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(titles, open(os.path.join(OUT, "titles_ko.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    c = Counter((it["corpus"], it["level"]) for it in items)
    print("items:", len(items), dict(sorted(c.items())))
    print("docs:", len(docs), "titles:", len(titles))


if __name__ == "__main__":
    main()
