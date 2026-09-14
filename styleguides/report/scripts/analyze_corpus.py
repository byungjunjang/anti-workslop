# -*- coding: utf-8 -*-
"""analyze_corpus.py — 파싱된 코퍼스에서 문체 통계를 계산해 stats.json / stats.md 를 만든다.

입력: corpus/items_ko.jsonl, corpus/docs_ko.json, corpus/titles_ko.json (parse_ko.py 산출물)
      corpus/text/crs_in_focus_*.txt, churchill_brevity_1940.md, da_pam_600-67.txt, axios_smart_brevity_101.txt
출력: stats.json, stats.md (키트 루트)

실행: python -X utf8 analyze_corpus.py
표준 라이브러리만 사용한다.
"""
import json, os, re, statistics
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 키트 루트 (scripts/ 의 부모)
C = os.path.join(HERE, "corpus")
T = os.path.join(C, "text")


def pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 1)


def dist(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return {}
    return {"n": len(xs), "mean": round(statistics.mean(xs), 1), "median": q(xs, .5), "p25": q(xs, .25),
            "p75": q(xs, .75), "p90": q(xs, .9), "max": max(xs)}


# ---------------- 한국어 ----------------
def analyze_ko():
    items = [json.loads(l) for l in open(os.path.join(C, "items_ko.jsonl"), encoding="utf-8")]
    docs = json.load(open(os.path.join(C, "docs_ko.json"), encoding="utf-8"))
    titles = json.load(open(os.path.join(C, "titles_ko.json"), encoding="utf-8"))
    out = {"corpora": {}}
    for corpus in ["nabo_compilation", "nabo_standalone", "nikl_examples"]:
        its = [i for i in items if i["corpus"] == corpus]
        res = {"n_items": len(its), "levels": {}}
        for L in (1, 2, 3):
            li = [i for i in its if i["level"] == L]
            if not li:
                continue
            ec = Counter(i["ending_class"] for i in li)
            tails = Counter(i["ending_token"][-2:] for i in li if i["ending_class"] in ("체언(명사구)", "명사형어미(-ㅁ)", "필요", "-중(진행)"))
            conn = Counter(i["connective"] for i in li if i["connective"])
            res["levels"][f"L{L}"] = {
                "n": len(li),
                "chars_nospace": dist([i["n_chars_nospace"] for i in li]),
                "eojeol": dist([i["n_eojeol"] for i in li if i["n_eojeol"]]),
                "share_over_60chars": pct(sum(1 for i in li if i["n_chars_nospace"] > 60), len(li)),
                "share_over_90chars": pct(sum(1 for i in li if i["n_chars_nospace"] > 90), len(li)),
                "share_over_2lines": pct(sum(1 for i in li if i["n_lines"] > 2), len(li)),
                "ending_class_share": {k: pct(v, len(li)) for k, v in ec.most_common()},
                "ending_tail_top": tails.most_common(25),
                "share_has_digit": pct(sum(1 for i in li if i["has_digit"]), len(li)),
                "numbers_per_item": round(statistics.mean(i["n_numbers"] for i in li), 2),
                "share_paren_head": pct(sum(1 for i in li if i["paren_head"]), len(li)),
                "share_connective_start": pct(sum(1 for i in li if i["connective"]), len(li)),
                "connective_top": conn.most_common(12),
            }
        # 문서 단위
        ds = [d for d in docs.values() if d["corpus"] == corpus]
        if ds and corpus.startswith("nabo"):
            res["docs"] = {
                "n_docs": len(ds),
                "pages_per_doc": dist([d.get("pages") for d in ds]),
                "items_per_doc": dist([d["n_items"] for d in ds]),
                "L1_per_doc": dist([d["n_L1"] for d in ds]),
                "L2_per_L1": round(sum(d["n_L2"] for d in ds) / max(1, sum(d["n_L1"] for d in ds)), 2),
                "L3_per_L2": round(sum(d["n_L3"] for d in ds) / max(1, sum(d["n_L2"] for d in ds)), 2),
                "share_docs_using_L3": pct(sum(1 for d in ds if d["n_L3"] > 0), len(ds)),
                "tables_per_doc": dist([d["n_tables"] for d in ds]),
                "figures_per_doc": dist([d["n_figures"] for d in ds]),
                "share_docs_with_table_or_figure": pct(sum(1 for d in ds if d["n_tables"] + d["n_figures"] > 0), len(ds)),
            }
        out["corpora"][corpus] = res
    # 제목
    tl = [t["title"] for t in titles if t["title"]]
    endw = Counter()
    for t in tl:
        main = re.split(r"\s[-–—:]\s|\s-|–", t)[0].strip()
        endw[main.split()[-1][-2:] if main.split() else ""] += 1
    out["titles"] = {
        "n": len(tl),
        "chars": dist([len(t) for t in tl]),
        "chars_main_title": dist([len(re.split(r"\s[-–—:]\s|\s-|–", t)[0].strip()) for t in tl]),
        "share_with_subtitle": pct(sum(1 for t in tl if re.search(r"\s[-–—:]\s|\s-\s|–", t)), len(tl)),
        "share_with_및_과_and": pct(sum(1 for t in tl if re.search(r"\s및\s|과\s|와\s", t)), len(tl)),
        "share_with_year_or_number": pct(sum(1 for t in tl if re.search(r"\d", t)), len(tl)),
        "ending_word_top": endw.most_common(15),
        "examples": tl[:12],
    }
    return out


# ---------------- 영어 ----------------
WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def syllables(w):
    w = w.lower()
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def sentences(text):
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?<=[a-z0-9\)])\.(?=\s+[A-Z“\"(])", ".\n", text)
    text = re.sub(r"[!?](?=\s+[A-Z“\"(])", lambda m: m.group(0) + "\n", text)
    ss = [s.strip() for s in text.split("\n") if len(WORD.findall(s)) >= 3]
    return ss


def en_stats(text):
    ss = sentences(text)
    wps = [len(WORD.findall(s)) for s in ss]
    words = WORD.findall(text)
    longw = sum(1 for w in words if syllables(w) >= 3)
    passive = len(re.findall(r"\b(am|is|are|was|were|be|being|been)\s+(\w+ed|\w+en)\b", text, re.I))
    return {
        "n_words": len(words), "n_sentences": len(ss),
        "words_per_sentence": dist(wps),
        "share_sentences_over_25w": pct(sum(1 for x in wps if x > 25), len(wps)),
        "share_long_words_3syl": pct(longw, len(words)),
        "clarity_index_dapam": round((statistics.mean(wps) if wps else 0) + (100.0 * longw / len(words) if words else 0), 1),
        "passive_forms_per_100w": round(100.0 * passive / len(words), 2) if words else None,
    }


def analyze_en():
    out = {}
    # CRS In Focus
    crs = {}
    for fn in sorted(os.listdir(T)):
        if fn.startswith("crs_in_focus_"):
            txt = open(os.path.join(T, fn), encoding="utf-8").read()
            body = re.split(r"\bDisclaimer\b|\bMetadata\b|Revision History", txt)[0]
            # 미러 사이트(EveryCRSReport) 군더더기 줄 제거
            lines = [l for l in body.split("\n")
                     if not re.search(r"EveryCRSReport|Download PDF|link to page|Report Type|Raw Metadata|^\s*(HTML|PDF|·)\s*$", l)]
            body = "\n".join(lines)
            paras = [p.strip() for p in re.split(r"\n\s*\n", body) if len(WORD.findall(p)) >= 25]
            st = en_stats(re.sub(r"\s+", " ", body))
            st["n_paragraphs_25w+"] = len(paras)
            st["sentences_per_paragraph"] = dist([len(sentences(p)) for p in paras])
            heads = [l.strip() for l in body.split("\n") if 2 <= len(l.split()) <= 8 and not l.strip().endswith(".") and re.match(r"^[A-Z][A-Za-z0-9 ,’'\-:()/]+$", l.strip()) and not re.search(r"\b(CRS|Figure|Table|Source|Notes?)\b", l)]
            st["headings_approx"] = heads[:14]
            st["first_sentence"] = (sentences(paras[0])[0] if paras else "")[:220]
            crs[fn.replace("crs_in_focus_", "").replace(".txt", "")] = st
    out["crs_in_focus"] = crs
    # Churchill
    ch = open(os.path.join(T, "churchill_brevity_1940.md"), encoding="utf-8").read()
    ch_body = ch.split("# Brevity", 1)[-1]
    out["churchill_brevity"] = en_stats(ch_body)
    # DA Pam: 나쁜/좋은 예 대비
    da = open(os.path.join(T, "da_pam_600-67.txt"), encoding="utf-8").read()
    da = re.sub(r"\s+", " ", da)

    def between(a, b):
        m = re.search(re.escape(a) + r"(.*?)" + re.escape(b), da)
        return (a + m.group(1)) if m else ""
    pairs = {
        "fig3_1_poor": between("A microcomputer can help this office", "Figure 3-1"),
        "fig3_2_good": between("1. I request a microcomputer", "Figure 3-2"),
        "fig4_4_poor": between("1. Herewith is the Summary", "A. Number of sentences 6"),
        "fig4_5_good": between("Here is LTC Jone", "Total words"),
        "fig5_1_poor_memo": between("1. The purpose of this memorandum is to reply", "Figure 5-1"),
        "fig5_2_good_memo": between("1. Purpose. To answer this question", "Figure 5-2"),
        "fig5_3_poor_letter": between("1. It has recently come to my attention", "GERALD A. SANDERS"),
        "fig5_4_good_letter": between("1. I request to represent the Battalion", "Encl"),
        "fig5_5_poor_survey": between("I have examined all available evidence", "Figure 5-5"),
        "fig5_6_good_survey": between("I have investigated the evidence", "Figure 5-6"),
    }
    out["da_pam_examples"] = {k: en_stats(v) for k, v in pairs.items() if v}
    sb = open(os.path.join(T, "axios_smart_brevity_101.txt"), encoding="utf-8").read()
    out["smart_brevity_101"] = en_stats(sb)
    return out


def md_table(rows, header):
    s = "| " + " | ".join(header) + " |\n|" + "---|" * len(header) + "\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


def write_md(ko, en):
    L = []
    L.append("# 코퍼스 통계 (자동 생성: analyze_corpus.py)\n")
    L.append("숫자는 `parse_ko.py`가 자른 항목(불릿) 단위 통계다. 합본(NABO Focus 100호)은 PDF 텍스트 추출 시 띄어쓰기가 일부 사라져 **공백 제외 글자 수**만 신뢰하고, 어절 수는 띄어쓰기가 보존된 개별호 4건(82·84·85·86호)과 국립국어원 예시에서만 계산했다. 옆제목(소제목) 수는 표 셀이 섞여 과대 추정되므로 표에 넣지 않았다.\n")
    for corpus, res in ko["corpora"].items():
        L.append(f"\n## 한국어 · {corpus} (항목 {res['n_items']}건)\n")
        rows = []
        for lv, s in res["levels"].items():
            cs = s["chars_nospace"]; ej = s.get("eojeol") or {}
            rows.append([lv, s["n"], cs.get("mean"), cs.get("median"), cs.get("p25"), cs.get("p75"), cs.get("p90"),
                         ej.get("mean", "-"), s["share_over_60chars"], s["share_over_90chars"], s["share_over_2lines"],
                         s["share_has_digit"], s["numbers_per_item"], s["share_paren_head"], s["share_connective_start"]])
        L.append(md_table(rows, ["계층", "n", "글자 평균", "중앙값", "p25", "p75", "p90", "어절 평균", ">60자 %", ">90자 %", "3줄 이상 %", "숫자 포함 %", "항목당 숫자", "괄호머리 %", "접속부사 시작 %"]))
        L.append("\n종결 유형 비율(%)\n")
        classes = ["체언(명사구)", "명사형어미(-ㅁ)", "필요", "괄호부연", "수치", "등(열거)", "-중(진행)", "-것", "요망/바람", "종결어미(-다)", "종결어미(-요)", "기타"]
        rows = []
        for lv, s in res["levels"].items():
            rows.append([lv] + [s["ending_class_share"].get(c, 0) for c in classes])
        L.append(md_table(rows, ["계층"] + classes))
        L.append("\n체언·명사형 종결의 꼬리 2글자 상위(빈도)\n")
        for lv, s in res["levels"].items():
            L.append(f"- {lv}: " + ", ".join(f"{k}({v})" for k, v in s["ending_tail_top"][:18]))
        L.append("\n접속부사로 시작하는 항목 상위\n")
        for lv, s in res["levels"].items():
            L.append(f"- {lv}: " + ", ".join(f"{k}({v})" for k, v in s["connective_top"][:8]))
        if "docs" in res:
            d = res["docs"]
            L.append(f"\n문서 단위 (n={d['n_docs']})\n")
            L.append(md_table([[d["pages_per_doc"].get("median"), d["items_per_doc"].get("mean"), d["items_per_doc"].get("median"), d["L1_per_doc"].get("mean"), d["L1_per_doc"].get("median"), d["L2_per_L1"], d["L3_per_L2"], d["share_docs_using_L3"], d["tables_per_doc"].get("mean"), d["figures_per_doc"].get("mean"), d["share_docs_with_table_or_figure"]]],
                              ["쪽/호 중앙값", "항목/호 평균", "항목/호 중앙값", "1단/호 평균", "1단/호 중앙값", "2단÷1단", "3단÷2단", "3단 사용 호 %", "표/호", "그림/호", "표·그림 있는 호 %"]))
    t = ko["titles"]
    L.append(f"\n## NABO Focus 제목 100건\n")
    L.append(md_table([[t["chars"]["mean"], t["chars"]["median"], t["chars_main_title"]["mean"], t["share_with_subtitle"], t["share_with_및_과_and"], t["share_with_year_or_number"]]],
                      ["글자 평균(부제 포함)", "중앙값", "주제목 글자 평균", "부제 있는 %", "및·과·와 포함 %", "숫자 포함 %"]))
    L.append("- 주제목 끝 낱말 상위: " + ", ".join(f"{k}({v})" for k, v in t["ending_word_top"]))
    L.append("- 예: " + " / ".join(t["examples"][:8]))
    L.append("\n## 영어 브리프·지침 문장 통계\n")
    rows = []
    for k, s in en["crs_in_focus"].items():
        rows.append([f"CRS {k}", s["n_words"], s["n_sentences"], s["words_per_sentence"].get("mean"), s["words_per_sentence"].get("median"), s["share_sentences_over_25w"], s["share_long_words_3syl"], s["clarity_index_dapam"], s["passive_forms_per_100w"], s["sentences_per_paragraph"].get("mean")])
    s = en["churchill_brevity"]; rows.append(["Churchill Brevity 1940", s["n_words"], s["n_sentences"], s["words_per_sentence"].get("mean"), s["words_per_sentence"].get("median"), s["share_sentences_over_25w"], s["share_long_words_3syl"], s["clarity_index_dapam"], s["passive_forms_per_100w"], "-"])
    s = en["smart_brevity_101"]; rows.append(["Axios Smart Brevity 101", s["n_words"], s["n_sentences"], s["words_per_sentence"].get("mean"), s["words_per_sentence"].get("median"), s["share_sentences_over_25w"], s["share_long_words_3syl"], s["clarity_index_dapam"], s["passive_forms_per_100w"], "-"])
    for k, s in en["da_pam_examples"].items():
        rows.append([f"DA Pam {k}", s["n_words"], s["n_sentences"], s["words_per_sentence"].get("mean"), s["words_per_sentence"].get("median"), s["share_sentences_over_25w"], s["share_long_words_3syl"], s["clarity_index_dapam"], s["passive_forms_per_100w"], "-"])
    L.append(md_table(rows, ["문서", "단어", "문장", "단어/문장 평균", "중앙값", ">25단어 문장 %", "3음절+ 단어 %", "명료도 지수(DA Pam)", "수동태/100단어", "문장/문단"]))
    L.append("\n- 명료도 지수 = 평균 문장 단어 수 + 3음절 이상 단어 비율(%). DA Pam 600-67은 30을 목표로, 20 미만은 너무 끊기고 40 초과는 읽기 어렵다고 본다. 음절 수는 영어 모음군 휴리스틱이라 근사치다.")
    L.append("- CRS 첫 문장 예: " + " / ".join(f"[{k}] {s['first_sentence']}" for k, s in en["crs_in_focus"].items()))
    open(os.path.join(HERE, "stats.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ko = analyze_ko()
    en = analyze_en()
    json.dump({"ko": ko, "en": en}, open(os.path.join(HERE, "stats.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_md(ko, en)
    print("wrote stats.json, stats.md")


if __name__ == "__main__":
    main()
