# -*- coding: utf-8 -*-
"""
analyze_corpus.py — 코퍼스 문체 통계 (stats.json / stats.md).

  python -X utf8 analyze_corpus.py --kit styleguides/<slug> [--exclude-boilerplate]
  python -X utf8 analyze_corpus.py --md-dir DIR [--recursive] --out DIR       # 키트 없이 빠른 통계

- 출력에 타임스탬프가 없다. 같은 posts.json·profile.json·metrics.py 면 바이트 단위로 같다.
- stats.json 에 corpus_sha256 / profile_sha256 / metrics_sha256 을 기록해 뒤 단계가 입력 변경을 잡아낸다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import (SKILL_DIR, dump_json_sorted, force_utf8_stdout, load_kit, metrics_sha256, read_json,  # noqa: E402
                    sha256_file, sha256_text, write_text)
from metrics import analyze_blocks  # noqa: E402


def _pctl(values: list, q: float):
    if not values:
        return 0
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo))


def compute(posts: list[dict], profile: dict, exclude_boilerplate: bool) -> dict:
    def body(p):
        return [b for b in p["blocks"] if not (exclude_boilerplate and b.get("boilerplate"))]

    per_post, all_blocks = {}, []
    for p in posts:
        blocks = body(p)
        m = analyze_blocks(blocks, profile, with_rhythms=True)
        m["title"] = p.get("title", ""); m["pubDate"] = p.get("pubDate", "")
        per_post[p["slug"]] = m
        all_blocks += blocks + [{"tag": "hr", "text": "---"}]
    overall = analyze_blocks(all_blocks, profile)
    for k in ("opening_type", "opening_sentence", "closing_sentence", "closing_is_call_or_outlook", "closing_is_summary", "has_lesson_section"):
        overall.pop(k, None)
    overall["opening_types"] = {}
    for m in per_post.values():
        if m.get("error"):
            continue
        overall["opening_types"][m["opening_type"]] = overall["opening_types"].get(m["opening_type"], 0) + 1
    ok = [m for m in per_post.values() if not m.get("error")]
    overall["closing_call_or_outlook_posts"] = sum(1 for m in ok if m["closing_is_call_or_outlook"])
    overall["closing_summary_posts"] = sum(1 for m in ok if m["closing_is_summary"])
    overall["lesson_section_posts"] = sum(1 for m in ok if m["has_lesson_section"])
    chars = [m["post_chars"] for m in ok]
    overall["post_chars_p10"], overall["post_chars_p25"], overall["post_chars_p50"] = _pctl(chars, .10), _pctl(chars, .25), _pctl(chars, .50)
    overall["post_chars_p75"], overall["post_chars_p90"] = _pctl(chars, .75), _pctl(chars, .90)
    overall["post_chars_min"], overall["post_chars_max"] = (min(chars), max(chars)) if chars else (0, 0)
    dates = sorted(p["pubDate"] for p in posts if p.get("pubDate"))
    n_exact = sum(1 for p in posts for b in p["blocks"] if b.get("boilerplate") == "exact")
    n_tail = sum(1 for p in posts for b in p["blocks"] if b.get("boilerplate") == "tail")
    return {
        "n_posts": len(posts), "date_range": [dates[0], dates[-1]] if dates else ["", ""],
        "boilerplate": {"exact_blocks": n_exact, "tail_blocks": n_tail, "excluded": exclude_boilerplate},
        "overall": overall, "per_post": per_post,
    }


def _variants_text(v: dict) -> str:
    return ", ".join(f"{k}: {x['a_count']},{x['b_count']} → {x['preferred']}" for k, x in v.items())


def render_md(stats: dict) -> str:
    o, n = stats["overall"], stats["n_posts"]
    j = lambda d, unit="": ", ".join(f"{k} {v}{unit}" for k, v in d.items())
    md = [
        "# 코퍼스 문체 통계 (자동 생성 — 손으로 고치지 말 것)", "",
        f"- 코퍼스: {n}편 ({stats['date_range'][0]} ~ {stats['date_range'][1]}), sha256 `{stats['corpus_sha256'][:16]}…`",
        f"- 본문 문장 {o['n_sentences']} / 문단 {o['n_paragraphs']} / 글자 {o['chars']} (소표제 조각 {o['n_labels_excluded']}개 제외)",
        f"- 글 길이(본문 글자): 최소 {o['post_chars_min']} / p10 {o['post_chars_p10']} / p25 {o['post_chars_p25']} / 중앙 {o['post_chars_p50']} / p75 {o['post_chars_p75']} / p90 {o['post_chars_p90']} / 최대 {o['post_chars_max']}",
        f"- 반복 블록: exact {stats['boilerplate']['exact_blocks']} / tail {stats['boilerplate']['tail_blocks']} (집계에서 제외: {stats['boilerplate']['excluded']})", "",
        "## 문장 길이", "", "| 지표 | 값 |", "|---|---|",
        f"| 평균 / 중앙값 / 표준편차 / 최장 | {o['len_mean']} / {o['len_median']} / {o['len_sd']} / {o['len_max']} |",
        f"| 평균 어절 | {o['words_mean']} |",
        f"| ≤35자 / 36~70 / >70 / >100 | {o['pct_short_le35']}% / {o['pct_mid_36_70']}% / {o['pct_long_gt70']}% / {o['pct_xlong_gt100']}% |",
        f"| 길이 구간 분포 | {j(o['len_bins_pct'], '%')} |",
        f"| 문단당 문장 평균 / 중앙값 / 3~4문장 비율 / 1문장 비율 | {o['sent_per_para_mean']} / {o['sent_per_para_median']} / {o['pct_para_3_4']}% / {o['pct_para_1']}% |",
        f"| 문단 첫 문장 / 끝 문장 평균 길이 | {o['para_first_len']} / {o['para_last_len']} |",
        f"| 길이 전이 (S≤30, M, L>70) | {j(o['transitions_pct'], '%')} |",
        f"| 문단 길이 패턴 상위 | {j(o['para_patterns_top'])} |",
        f"| 90자 이상 장문 다음 문장: 평균 / 40자 이하 비율 / 표본 | {o['after_long_next_mean']} / {o['after_long_pct_le40']}% / {o['after_long_n']} |",
        f"| 괄호가 있는 문단 | {o['pct_para_with_paren']}% |", "",
        "## 종결어미", "", "| 지표 | 값 |", "|---|---|",
        f"| 합쇼체 / 해요체 / -죠 / 해라체 / 기타 | {o['pct_hapsyo']}% / {o['pct_haeyo']}% / {o['pct_jyo']}% / {o['pct_haera']}% / {o['pct_other_ending']}% |",
        f"| 의문문 | {o['pct_question']}% |",
        f"| '~생각합니다' / '~것 같습니다' / '~것입니다' 종결 | {o['pct_saenggak']}% / {o['pct_geot_gatda']}% / {o['pct_geot_ipnida']}% |",
        f"| 해요체 연속 (문단 내) | {o['consecutive_haeyo']}회 |",
        f"| 문두 '저/제' 문장 / '내·나' 포함 문장 / 한 문장 안 혼용 | {o['pct_first_person_author_start']}% / {o['pct_generic_first_person']}% / {o['mixed_first_person']} |", "",
        "세부: " + ", ".join(f"{k} {v}" for k, v in list(o["ending_detail"].items())[:20]), "",
        "## 접속부사·쉼표", "", "| 지표 | 값 |", "|---|---|",
        f"| 문두 접속부사 문장 | {o['pct_conj_start']}% |",
        f"| 문두 접속부사 상위 | {j(o['conj_top'])} |",
        f"| 접속부사 전체 빈도(문장 어디든) | {j(dict(list(o['conj_total'].items())[:16]))} |",
        f"| 접속부사 뒤 쉼표(허용 제외) / 접속부사 연속 | {o['conj_comma_bad']} / {o['conj_consecutive']} |",
        f"| 문장당 / 문단당 쉼표 | {o['commas_per_sent']} / {o['commas_per_para']} |",
        f"| 쉼표 없는 문장 / 2개 이상 | {o['pct_sent_no_comma']}% / {o['pct_sent_2plus_comma']}% |",
        f"| 쉼표 위치 | {j(o['comma_position_pct'], '%')} |",
        f"| 나열+'-고,' 비중 / 주어 뒤 쉼표 | {o['pct_list_or_go_comma']}% / {o['comma_after_subject']} |",
        f"| 괄호 / 슬래시 / 영문 병기 / 느낌표 / 이모티콘 | {o['parens']} / {o['slashes']} / {o['eng_gloss']} / {o['exclaim']} / {o['emoticons']} |", "",
        "## 어휘·구문", "", "| 지표 | 값 |", "|---|---|",
        f"| '예를 들어' 류 | {o['ye_reul_deureo']} |",
        f"| 여러분/당신 | {o['yeoreobun_dangsin']} |",
        f"| 감각어 | {o['sensory'] or 0} |",
        f"| 금지어 | {o['banned'] or 0} |",
        f"| 비선호 표기(profile.spelling_pairs) | {o['nonpreferred_spelling'] or 0} |",
        f"| 표기 변이 (저자형/표준형: 저자형 수, 표준형 수 → 선호) | {_variants_text(o['spelling_variants'])} |",
        f"| 강조 부사 | {j(o['intensifiers'])} |",
        f"| 대조 구문 (아니라/아닌/보다는/말고) | {o['contrast_constructions']} ({o['pct_contrast']}%) |",
        f"| '통해' | {o['tonghae']} ({o['pct_tonghae']}%) |",
        f"| 숫자 포함 문장 / 과거형 문장 | {o['pct_numeric_sent']}% / {o['pct_past']}% |",
        f"| 어휘 빈도(watchlist) | {j(o['lexicon'])} |", "",
        "## 구조", "", "| 지표 | 값 |", "|---|---|",
        f"| 시작 유형(자동 분류) | {o['opening_types']} |",
        f"| 권유/전망으로 끝나는 글 / 요약으로 끝나는 글 / 느낀 점 섹션 있는 글 | {o['closing_call_or_outlook_posts']} / {o['closing_summary_posts']} / {o['lesson_section_posts']} (총 {n}) |",
        f"| 표제 | 총 {o['heading_forms']['total']}: 명사구 {o['heading_forms']['noun']}({o['heading_forms']['noun_pct']}%), -다 {o['heading_forms']['da']}({o['heading_forms']['da_pct']}%), 청유·명령 {o['heading_forms']['imperative']}({o['heading_forms']['imperative_pct']}%), 의문 {o['heading_forms']['question']}({o['heading_forms']['question_pct']}%), 번호 {o['heading_forms']['numbered']}({o['heading_forms']['numbered_pct']}%) |", "",
        "## 글별", "", "| 글 | 날짜 | 문장 | 글자 | 평균 | 합쇼 | 해요 | 접속 | 쉼표/문장 | 시작 | 끝=권유 |", "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for slug, m in stats["per_post"].items():
        if m.get("error"):
            md.append(f"| {slug} | | 0 | | | | | | | {m['error']} | |"); continue
        md.append(f"| {slug} | {m['pubDate']} | {m['n_sentences']} | {m['post_chars']} | {m['len_mean']} | {m['pct_hapsyo']}% | {m['pct_haeyo']}% | {m['pct_conj_start']}% | {m['commas_per_sent']} | {m['opening_type']} | {'O' if m['closing_is_call_or_outlook'] else 'X'} |")
    return "\n".join(md) + "\n"


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit")
    ap.add_argument("--md-dir"); ap.add_argument("--recursive", action="store_true"); ap.add_argument("--out")
    ap.add_argument("--exclude-boilerplate", action="store_true")
    a = ap.parse_args()

    if a.kit:
        kit = load_kit(a.kit)
        if not kit.posts_json.exists():
            raise SystemExit("corpus/posts.json 이 없습니다. collect.py 를 먼저 실행하세요.")
        posts, profile = kit.posts(), kit.profile()
        corpus_sha, profile_sha = sha256_file(kit.posts_json), sha256_file(kit.profile_json)
        out_json, out_md = kit.stats_json, kit.stats_md
    elif a.md_dir:
        from collect import detect_boilerplate, load_md_dir
        posts = load_md_dir(Path(a.md_dir).resolve(), a.recursive)
        detect_boilerplate(posts)
        profile = read_json(SKILL_DIR / "assets" / "profile.default.json")
        import json
        corpus_sha = sha256_text(json.dumps(posts, ensure_ascii=False, sort_keys=True))
        profile_sha = sha256_file(SKILL_DIR / "assets" / "profile.default.json")
        out = Path(a.out or ".").resolve(); out.mkdir(parents=True, exist_ok=True)
        out_json, out_md = out / "stats.json", out / "stats.md"
    else:
        raise SystemExit("--kit 또는 --md-dir 이 필요합니다.")

    stats = compute(posts, profile, a.exclude_boilerplate)
    stats.update({"corpus_sha256": corpus_sha, "profile_sha256": profile_sha, "metrics_sha256": metrics_sha256()})
    dump_json_sorted(stats, out_json)
    write_text(out_md, render_md(stats))
    o = stats["overall"]
    print(f"[done] {out_json.name} / {out_md.name}  (posts={stats['n_posts']}, sentences={o['n_sentences']}, mean={o['len_mean']}, hapsyo={o['pct_hapsyo']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
