# -*- coding: utf-8 -*-
"""
extract_reading_pack.py — 정성 통독을 '선택' 작업으로 바꾸는 후보 목록을 만든다 (reading-pack.md).

  python -X utf8 extract_reading_pack.py --kit styleguides/<slug> [--full-read 12] [--batch-size 10] [--cap 40]

Part A (모든 글): 제목·날짜·slug, 표제, 첫 문단, 마지막 본문 문단 2개, 구분선 뒤 꼬리 블록, 자동 도입 유형,
                 짧은 문장(≤15자)이 들어 있는 문단의 길이 흐름 "36 → 37 → 66 → 10 → 82"
Part B (전역 후보, 상한 cap): 단문≤20자(앞 문장과 함께), 괄호 문장, 대조, 비유 후보, 인용 후보, 이모티콘·느낌표 문장,
                 오탈자 후보, 해요체 세부(고요/는데요/네요/세요/까요), 문두 '저는' 문장, 표제 형태별 예
20편 초과면 reading-pack.batch-K.md 로 나누고, 전독 대상(최초 4·최근 4·최장 4)을 맨 위에 적는다.
출력은 결정적이다(정렬·상한 고정, 난수 없음).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import assert_snapshot, force_utf8_stdout, load_kit, write_text  # noqa: E402
from metrics import _core, classify_ending, is_label, split_sentences  # noqa: E402

HEAD = ("h", "h1", "h2", "h3", "h4")


def post_view(p: dict, m: dict) -> str:
    blocks = p["blocks"]
    hr_idx = [i for i, b in enumerate(blocks) if b["tag"] == "hr"]
    last_hr = hr_idx[-1] if hr_idx else len(blocks)
    body_ps = [(i, b["text"]) for i, b in enumerate(blocks) if b["tag"] == "p" and i < last_hr]
    tail = [b["text"] for b in blocks[last_hr + 1 :] if b["tag"] != "hr"]
    heads = [b["text"] for b in blocks if b["tag"] in HEAD]
    out = [f"### {p['title']}  ({p.get('pubDate','')}, slug `{p['slug']}`)", "",
           f"- 자동 도입 유형: {m.get('opening_type')} / 문장 {m.get('n_sentences')} / 평균 {m.get('len_mean')}자 / 합쇼체 {m.get('pct_hapsyo')}% / 해요체 {m.get('pct_haeyo')}%",
           f"- 표제: " + " | ".join(heads)[:600], ""]
    if body_ps:
        out += ["첫 문단:", "", "> " + body_ps[0][1], ""]
        if len(body_ps) >= 3:
            out += ["끝 문단 2개:", "", "> " + body_ps[-2][1], "", "> " + body_ps[-1][1], ""]
        elif len(body_ps) == 2:
            out += ["끝 문단:", "", "> " + body_ps[-1][1], ""]
    if tail:
        out += ["구분선 뒤 꼬리(CTA 등):", ""] + ["> " + t for t in tail] + [""]
    rhythms = m.get("para_rhythms") or []
    picks = []
    for k, seq in enumerate(rhythms):
        if 4 <= len(seq) <= 7 and any(l <= 15 for l in seq[1:]):
            picks.append((k, seq))
    if picks:
        out += ["짧은 문장이 낀 문단의 길이 흐름 (리듬 예 후보, {{rhythm:slug:pN}} 으로 인용):", ""]
        for k, seq in picks[:4]:
            out.append(f"- p{k}: " + " → ".join(str(x) for x in seq) + "자")
        out.append("")
    return "\n".join(out)


def global_candidates(posts: list[dict], cap: int) -> str:
    sents = []   # (slug, para_idx, prev, sent)
    for p in posts:
        pi = -1
        for b in p["blocks"]:
            if b["tag"] != "p":
                continue
            pi += 1
            ss = [s for s in split_sentences(b["text"]) if not is_label(s)]
            for j, s in enumerate(ss):
                sents.append((p["slug"], pi, ss[j - 1] if j else "", s))

    def take(pred, n=cap):
        out = []
        per_slug = Counter()
        for slug, pi, prev, s in sents:
            if pred(s) and per_slug[slug] < max(2, n // max(1, len(posts))) + 1:
                out.append((slug, pi, prev, s)); per_slug[slug] += 1
            if len(out) >= n:
                break
        return out

    def fmt(items, with_prev=False):
        return [f"- [{slug} p{pi}] " + (f"…{prev[-40:]} ‖ " if with_prev and prev else "") + s for slug, pi, prev, s in items] or ["- (없음)"]

    body = " ".join(s for _, _, _, s in sents)
    latin_tokens = Counter(re.findall(r"[A-Za-z][A-Za-z']{3,}", body))
    rare_latin = sorted(t for t, c in latin_tokens.items() if c == 1)
    typo_pat = re.compile(r"(되서|안되|왠만|할수 |될수 |수 밖에|않되|됬|뒷받짐|끌어드|자유료)")
    heads = [(p["slug"], b["text"]) for p in posts for b in p["blocks"] if b["tag"] in HEAD]

    def heads_by(pred, n=6):
        return [f"- [{s}] {h}" for s, h in heads if pred(h)][:n] or ["- (없음)"]

    parts = ["## Part B. 전역 후보 목록 (원문 그대로. 워크시트에 옮길 때 글자 하나 바꾸지 말 것)", ""]
    parts += ["### B1. 짧은 문장(≤20자)과 바로 앞 문장", ""] + fmt(take(lambda s: len(s) <= 20), with_prev=True) + [""]
    parts += ["### B2. 괄호가 든 문장", ""] + fmt(take(lambda s: "(" in s)) + [""]
    parts += ["### B3. 대조 구문 (아니라/아닌/보다는/말고)", ""] + fmt(take(lambda s: re.search(r"(아니라|아닌|보다는|\s말고)", s) is not None)) + [""]
    parts += ["### B4. 비유 후보 (같은/처럼/마치/비유/유사)", ""] + fmt(take(lambda s: re.search(r"(처럼|마치|비유|유사합니다|같은 것|것과 마찬가지|이치입니다)", s) is not None)) + [""]
    parts += ["### B5. 인용·권위 후보 (『』/“”/에 따르면/라고 말)", ""] + fmt(take(lambda s: re.search(r"(『|“|”|에 따르면|라고 말|아티클|책에서|저자)", s) is not None)) + [""]
    parts += ["### B6. 이모티콘·느낌표 문장", ""] + fmt(take(lambda s: re.search(r"(:\)|\^\^|ㅎㅎ|!|[\U0001F300-\U0001FAFF])", s) is not None)) + [""]
    parts += ["### B7. 해요체 세부 (문단 끝 톤 다운 예)", ""]
    for sub in ("고요", "는데요", "네요", "세요", "까요", "죠"):
        items = take(lambda s, sub=sub: _core(s).endswith(sub), n=3)
        parts += [f"- **-{sub}**"] + ["  " + x for x in fmt(items)]
    parts += [""]
    parts += ["### B8. 문두 '저는/제가' 문장 (이력·사례 위치 확인용)", ""] + fmt(take(lambda s: re.match(r"(저는|제가|저도|저의 경우)", s) is not None, n=12)) + [""]
    parts += ["### B9. '~기 때문입니다' 로 닫는 문장 (근거 후치)", ""] + fmt(take(lambda s: _core(s).endswith("때문입니다"), n=8)) + [""]
    parts += ["### B10. 표제 형태별 예", "", "- 의문형:"] + ["  " + x for x in heads_by(lambda h: h.rstrip().endswith("?"))]
    parts += ["- 청유·명령형:"] + ["  " + x for x in heads_by(lambda h: re.search(r"(세요|하자|보자|라)[.!]?$", h) is not None)]
    parts += ["- 평서 -다:"] + ["  " + x for x in heads_by(lambda h: re.search(r"다[.!]?$", h) is not None and not re.search(r"(세요|하자|보자|라)[.!]?$", h))]
    parts += ["- 명사구:"] + ["  " + x for x in heads_by(lambda h: not re.search(r"(\?|다[.!]?|세요|하자|보자|라[.!]?)$", h.rstrip()))]
    parts += [""]
    parts += ["### B11. 오탈자·비표준 표기 후보 (사람 지문. 규칙으로 복제하지 말 것)", "",
              "- 1회만 나온 로마자 토큰: " + ", ".join(rare_latin[:40])]
    parts += fmt(take(lambda s: typo_pat.search(s) is not None, n=10)) + [""]
    return "\n".join(parts)


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--full-read", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=10)
    ap.add_argument("--cap", type=int, default=40)
    a = ap.parse_args()
    kit = load_kit(a.kit)
    assert_snapshot(kit, need_stats=True)
    posts, stats = kit.posts(), kit.stats()
    per = stats["per_post"]
    n = len(posts)

    header = ["# 정성 통독 팩 (자동 생성)", "",
              f"- 코퍼스 {n}편, sha256 `{stats['corpus_sha256'][:12]}`. 이 파일은 후보 목록이다. 워크시트에는 여기서 고른 문장을 **원문 그대로** 옮긴다.",
              "- `[slug pN]` 은 글과 문단 번호다. 리듬 예는 `{{rhythm:slug:pN}}` 로 인용하면 render 가 길이를 계산한다.", ""]
    if n > 20:
        by_date = sorted(posts, key=lambda p: (p.get("pubDate", ""), p["slug"]))
        by_len = sorted(posts, key=lambda p: -per[p["slug"]].get("post_chars", 0))
        chosen = []
        for src in (by_date[:4], by_date[-4:], by_len[:4]):
            for p in src:
                if p["slug"] not in chosen:
                    chosen.append(p["slug"])
        chosen = chosen[: a.full_read]
        header += [f"- 글이 {n}편이라 전독 대상을 {len(chosen)}편으로 정했다(최초·최근·최장 각 4): " + ", ".join(chosen),
                   "  나머지는 Part A(첫·끝 문단, 표제)만 읽는다. 서브에이전트에 나눌 때는 batch 파일 하나씩 준다.", ""]

    parts_a = [post_view(p, per.get(p["slug"], {})) for p in posts]
    part_b = global_candidates(posts, a.cap)
    main_doc = "\n".join(header + ["## Part A. 글별 요약", ""] + parts_a + [part_b]) + "\n"
    write_text(kit.reading_pack, main_doc)
    print(f"[done] {kit.reading_pack.name} ({len(main_doc)} chars)")
    if n > 20:
        for k in range(0, n, a.batch_size):
            batch = parts_a[k : k + a.batch_size]
            path = kit.root / f"reading-pack.batch-{k // a.batch_size + 1}.md"
            write_text(path, "\n".join(header + [f"## Part A (batch {k // a.batch_size + 1})", ""] + batch) + "\n")
            print(f"[done] {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
