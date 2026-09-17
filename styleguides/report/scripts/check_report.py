# -*- coding: utf-8 -*-
"""check_report.py — 보고서 초안을 「개조식 보고서 작성 가이드라인.md」 §11-2 점검표에 맞춰 기계적으로 검사한다.
아래 H/S 번호는 이 스크립트 고유 번호이며 가이드라인 §11-2 번호와의 대응은 키트 README 에 있다.

사용법:
    python -X utf8 check_report.py 초안.md                # 개조식(불릿) 보고서 기본 검사
    python -X utf8 check_report.py 초안.md --mode prose   # 서술형 보고서(문장 단위) 검사
    python -X utf8 check_report.py 초안.md --limit 4000   # 분량 상한(공백 제외 글자 수) 지정

검사 항목(개조식 모드)
  H1  제목: 1줄·40자 이하·동작성/판단 명사로 끝남, '~동향'·'~현황'만으로 끝나는 포괄 제목 경고
  H2  첫 3줄(개요) 안에 결론·요청·수치가 있는가(두괄식)
  H3  항목 계층 3단 이하
  H4  항목 길이: 공백 제외 90자 초과 경고(2줄 안에 끝내기), 120자 초과는 오류. 따옴표 인용은 빼고 센다
  H5  종결: '-다/-습니다/-요' 문장 종결이 섞이면 경고(개조식은 체언·-ㅁ·'필요'로 끝냄)
  H6  근거 항목(2·3단)의 숫자 포함 비율 50% 미만이면 경고
  H7  접속부사로 시작하는 항목 15% 초과 경고
  H8  한 상위 항목 아래 하위 항목이 1개뿐이면 경고(둘 이상이 아니면 나누지 않는다)
  S1  애매·과장 표현, 번역투, 군더더기, 한자어·외래어 노출 수 집계(soft)
  S2  날짜·시간·금액 표기 규범(2024. 12. 10. / 15:20 / 만 단위)
  S3  분량: 공백 제외 글자 수와 상한 비교
표준 라이브러리만 사용한다. 수치 기준은 stats.md(NABO Focus 100호 통계)에서 왔다.
"""
import re, sys, argparse

BULLET = re.compile(r"^(\s*)([□○◦▪■●•・·\-‑–—\*※]|\d+[\.\)]|[가-힣][\.\)]|\(\d+\)|[①-⑳])\s*(.*)$")
CONNECTIVES = ["다만", "그러나", "또한", "한편", "특히", "아울러", "이에", "따라서", "반면", "향후", "이후", "그동안",
               "최근", "우선", "먼저", "이를 위해", "나아가", "즉", "그 외", "이와 같은", "이러한", "상기", "그리고", "하지만"]
CONN_RE = re.compile(r"^(" + "|".join(re.escape(c) for c in CONNECTIVES) + r")[\s,]")
VAGUE = ["대체로", "대부분", "많은", "어느 정도", "상당한", "상당히", "다양한", "적극적으로", "적극", "지속적으로", "원활", "제고", "효율적", "체계적", "종합적",
         "면밀히", "철저히", "만전", "최선을 다", "가일층", "강력히", "획기적", "극심한", "쇄도"]
TRANSLATIONESE = [r"에 있어서?", r"을 필요로", r"를 필요로", r"에 의해", r"에 의한", r"시키[다고며]", r"되어지", r"되어졌", r"함으로써", r"에 다름 아니", r"가지고 있", r"~로부터"]
FILLER = [r"에 대하여", r"에 대한", r"을 통하여", r"를 통하여", r"의 경우", r"에 관하여", r"함에 있어", r"하는 것이 필요", r"라고 할 수 있"]
HARD_HANJA = ["금번", "동법", "동년", "당해", "익일", "상기", "제반", "차기", "적의 조치", "요망", "필한", "소명하", "기일 엄수", "귀 기관", "본 건", "만전을 기", "가일층", "경주하", "시현", "제고를 위"]
TITLE_ACTION_TAILS = ("방안", "계획", "결과", "현황", "분석", "검토", "대책", "보고", "시사점", "과제", "전망", "영향", "쟁점", "동향", "점검", "추진", "개선", "제안", "건의", "요청", "실적", "평가", "전략", "안", "내용", "경과", "필요", "요망", "추진")
CONCLUSION_MARKERS = ["필요", "건의", "요청", "결론", "판단", "전망", "제안", "요망", "추진", "결정", "확정", "의결", "검토", "시사", "바람", "권고", "예정", "계획"]


# H4 는 인용을 빼고 센다. 인용은 줄일 수 없고(불변식 F2) 가이드도 종결 규칙에서 인용문을 뺀다(§14 [종결]).
QUOTED = re.compile(r'"[^"\n]*"|“[^”]*”|「[^」]*」|『[^』]*』')


def strip_md(line):
    line = re.sub(r"^#+\s*", "", line)
    line = re.sub(r"\*\*|__|`", "", line)
    return line


def parse_items(lines):
    """불릿 항목 목록: (level, text, lineno). 들여쓰기 폭과 기호로 계층을 추정한다."""
    items = []
    stack = []  # indent widths
    for n, raw in enumerate(lines, 1):
        line = strip_md(raw.rstrip())
        if not line.strip():
            continue
        m = BULLET.match(line)
        if not m:
            # 이어지는 줄은 직전 항목에 붙인다
            if items and items[-1]["lineno_end"] == n - 1 and not re.match(r"^\s*(\[표|\[그림|자료|주:|※)", line):
                items[-1]["text"] += " " + line.strip()
                items[-1]["lineno_end"] = n
            continue
        indent = len(m.group(1).replace("\t", "  "))
        sym = m.group(2)
        # 계층: 기호 우선, 없으면 들여쓰기
        if sym in "□■":
            lvl = 1
        elif sym in "○●":
            lvl = 2
        elif sym in "-‑–—·・•◦":
            lvl = 3 if indent >= 2 else 2
        elif sym in "▪":
            lvl = 1
        elif sym in "*※":
            lvl = 4  # 참고 줄
        else:
            while stack and indent < stack[-1]:
                stack.pop()
            if not stack or indent > stack[-1]:
                stack.append(indent)
            lvl = len(stack)
        items.append({"level": lvl, "sym": sym, "text": m.group(3).strip(), "lineno": n, "lineno_end": n, "indent": indent})
    return items


def ending_of(text):
    s = re.sub(r"\s+", " ", text.strip())
    s = re.sub(r"\d{1,2}\)$", "", s).rstrip(" .。,;:")
    if not s:
        return "empty"
    if re.search(r"(필요|요망|바람|중요|주요|수요|소요|개요)$", s):
        return "noun_or_mieum"
    if re.search(r"(다|요|죠|습니다|입니다|됩니다|합니다)$", s):
        return "sentence"
    if s[-1] in ")）]":
        return "paren"
    if re.search(r"[\d%]$", s):
        return "number"
    return "noun_or_mieum"


def check(text, mode="bullet", limit=None):
    lines = text.splitlines()
    report = {"hard": [], "soft": [], "info": []}
    nospace = re.sub(r"\s", "", text)
    body_chars = len(nospace)

    # 제목
    title = ""
    for l in lines:
        if l.strip():
            title = strip_md(l).strip(); break
    if title:
        tl = len(title.replace(" ", ""))
        if tl > 40:
            report["hard"].append(f"H1 제목이 {tl}자(공백 제외)로 길다. 40자 안에서 핵심 판단만 남긴다: '{title[:50]}'")
        if not title.endswith(TITLE_ACTION_TAILS):
            report["soft"].append(f"H1 제목 끝이 동작성·판단 명사(방안·결과·시사점·필요 등)가 아니다: '{title[-12:]}'")
        if re.search(r"(동향|현황)$", title) and len(title) < 14:
            report["soft"].append("H1 '~동향/~현황'만으로 끝나는 포괄 제목이다. 무엇이 어떻게 됐는지 구체적으로 적는다(예: '금속연맹, 전국 동시 시한부 파업 추진').")

    # 두괄식: 첫 3개 비어있지 않은 줄(제목 제외)
    head = [strip_md(l) for l in lines if l.strip()][1:4]
    head_txt = " ".join(head)
    if head and not (any(k in head_txt for k in CONCLUSION_MARKERS) or re.search(r"\d", head_txt)):
        report["hard"].append("H2 첫 3줄(개요)에 결론·요청·수치가 없다. 보고 목적과 요청(또는 핵심 판단)을 첫 문단에 둔다.")

    if mode == "bullet":
        items = parse_items(lines)
        if not items:
            report["info"].append("불릿 항목을 찾지 못했다. 개조식이 아니면 --mode prose 로 검사한다.")
        else:
            max_lvl = max(i["level"] for i in items if i["level"] < 4) if any(i["level"] < 4 for i in items) else 0
            if max_lvl > 3:
                report["hard"].append(f"H3 항목 계층이 {max_lvl}단이다. 3단(□ ○ -)까지만 쓰고 그 아래는 상위로 합치거나 별첨으로 보낸다.")
            for it in items:
                if it["level"] >= 4:
                    continue
                n = len(re.sub(r"\s", "", QUOTED.sub("", it["text"])))
                if n > 120:
                    report["hard"].append(f"H4 {it['lineno']}행 항목이 {n}자다(120자 초과). 두 항목으로 나누거나 수치·부연을 하위 항목으로 내린다: '{it['text'][:40]}…'")
                elif n > 90:
                    report["soft"].append(f"H4 {it['lineno']}행 항목이 {n}자다(90자 초과, 2줄 넘김). NABO 브리프 상위 10%가 77~88자다: '{it['text'][:40]}…'")
                e = ending_of(it["text"])
                if e == "sentence":
                    report["hard"].append(f"H5 {it['lineno']}행 항목이 문장 종결(-다/-습니다)로 끝난다. 체언·'-ㅁ'·'필요'로 바꾼다: '…{it['text'][-25:]}'")
            evid = [i for i in items if i["level"] in (2, 3)]
            if len(evid) >= 4:
                share = sum(1 for i in evid if re.search(r"\d", i["text"])) / len(evid)
                if share < 0.5:
                    report["soft"].append(f"H6 근거 항목(2·3단) 중 숫자가 있는 항목이 {share:.0%}다. NABO 브리프는 2단 60%, 3단 68%가 숫자를 담는다. 주장마다 수치·출처를 붙이거나 항목을 삭제한다.")
            top = [i for i in items if i["level"] < 4]
            if len(top) >= 5:
                cshare = sum(1 for i in top if CONN_RE.match(i["text"])) / len(top)
                if cshare > 0.15:
                    report["soft"].append(f"H7 접속부사로 시작하는 항목이 {cshare:.0%}다(기준 15%, NABO 4~7%). 접속부사는 논리가 꺾이는 자리(다만·반면·한편)에만 쓴다.")
            # 하위 항목 1개
            for idx, it in enumerate(top):
                if it["level"] >= 3:
                    continue
                kids = 0
                for j in range(idx + 1, len(top)):
                    if top[j]["level"] <= it["level"]:
                        break
                    if top[j]["level"] == it["level"] + 1:
                        kids += 1
                if kids == 1:
                    report["soft"].append(f"H8 {it['lineno']}행 항목 아래 하위 항목이 1개뿐이다. 상위 항목에 합치거나 둘 이상으로 나눈다.")
    else:
        # 서술형: 문장 길이
        sents = [s.strip() for s in re.split(r"(?<=[.!?다요])\s+", re.sub(r"\s+", " ", text)) if len(s.strip()) > 5]
        lens = [len(re.sub(r"\s", "", s)) for s in sents]
        eoj = [len(s.split()) for s in sents]
        if lens:
            avg = sum(lens) / len(lens); avge = sum(eoj) / len(eoj)
            long_share = sum(1 for x in eoj if x > 25) / len(eoj)
            report["info"].append(f"문장 {len(sents)}개, 평균 {avg:.0f}자·{avge:.1f}어절, 25어절 초과 {long_share:.0%}")
            if avge > 20:
                report["soft"].append("P1 평균 문장 길이가 20어절을 넘는다. 한 문장에 한 정보만 담고 나머지는 끊는다(공공언어 지침·DA Pam 15단어 기준).")
            for s in sents:
                if len(s.split()) > 35:
                    report["hard"].append(f"P2 35어절 초과 문장: '{s[:60]}…'")
        passive = len(re.findall(r"(되어지|시켜지|에 의해 .{0,12}(되|된|됨))", text))
        if passive:
            report["soft"].append(f"P3 이중 피동·'에 의해 ~되다' 구문 {passive}건. 능동으로 바꾼다.")

    # soft 어휘 검사
    for lst, label in ((VAGUE, "S1 애매·과장 표현"), (HARD_HANJA, "S1 어려운 한자어·권위적 표현")):
        found = {w: len(re.findall(re.escape(w), text)) for w in lst}
        found = {k: v for k, v in found.items() if v}
        if found:
            report["soft"].append(f"{label}: " + ", ".join(f"{k}×{v}" for k, v in sorted(found.items(), key=lambda x: -x[1])[:10]))
    for lst, label in ((TRANSLATIONESE, "S1 번역투"), (FILLER, "S1 군더더기")):
        found = {p: len(re.findall(p, text)) for p in lst}
        found = {k: v for k, v in found.items() if v}
        if found:
            report["soft"].append(f"{label}: " + ", ".join(f"'{k}'×{v}" for k, v in found.items()))
    latin = re.findall(r"\b[A-Z]{2,6}\b", text)
    if latin:
        glossed = [w for w in set(latin) if re.search(r"[가-힣]\s*\(" + re.escape(w) + r"\)", text)]
        bare = sorted(set(latin) - set(glossed))
        if bare:
            report["info"].append("S1 우리말 풀이 없이 쓴 로마자 약어: " + ", ".join(bare[:12]))

    # 표기 규범
    bad_dates = re.findall(r"\d{4}년\s*\d{1,2}월\s*\d{1,2}일", text)
    if bad_dates:
        report["soft"].append(f"S2 날짜 표기 {len(bad_dates)}건: '2024년 12월 10일' → '2024. 12. 10.'(행정업무운영 편람)")
    bad_dates2 = re.findall(r"\d{4}\.\d{1,2}\.\d{1,2}\.?(?!\d)", text)
    if bad_dates2:
        report["soft"].append(f"S2 날짜 마침표 뒤 띄어쓰기 {len(bad_dates2)}건: '2024.12.10.' → '2024. 12. 10.'")
    bad_time = re.findall(r"(오전|오후)\s*\d{1,2}시", text)
    if bad_time:
        report["soft"].append(f"S2 시간 표기 {len(bad_time)}건: '오후 3시 20분' → '15:20'")
    thousand = re.findall(r"\d{1,3}(?:,\d{3})*천\s*원", text)
    if thousand:
        report["soft"].append(f"S2 '천 원' 단위 {len(thousand)}건: 21,345천원 → 2,134만 5천 원")

    if limit:
        if body_chars > limit:
            report["hard"].append(f"S3 분량 {body_chars}자(공백 제외)가 상한 {limit}자를 넘는다. 상세·통계는 별첨으로 보낸다.")
        else:
            report["info"].append(f"S3 분량 {body_chars}자(공백 제외) / 상한 {limit}자")
    else:
        report["info"].append(f"S3 분량 {body_chars}자(공백 제외). 참고: 상황보고 1쪽≈900자, NABO 4쪽 브리프의 불릿 합계 중앙값≈1,900자(표·그림 제외)")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--mode", choices=["bullet", "prose"], default="bullet")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    text = open(a.path, encoding="utf-8").read()
    rep = check(text, a.mode, a.limit)
    for k, label in (("hard", "반드시 고칠 것"), ("soft", "검토할 것"), ("info", "참고")):
        print(f"\n[{label}] {len(rep[k])}건")
        for r in rep[k]:
            print(" -", r)
    sys.exit(1 if rep["hard"] else 0)


if __name__ == "__main__":
    main()
