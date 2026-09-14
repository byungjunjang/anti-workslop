# -*- coding: utf-8 -*-
"""
derive_targets.py — stats.json 에서 targets.json 을 도출한다.

  python -X utf8 derive_targets.py --kit styleguides/<slug> [--print-diff] [--no-overrides]

규칙 종류
  envelope : hard/soft 범위 = 글별 최소~최대 + 여유 (kind 별 여유: pct 3 / len 3 / spp 0.3 / ratio 0.05, 글이 8편 미만이면 2배)
  policy   : profile.policy_rules 의 고정 상한. 코퍼스가 어기면 글별 최대값까지 넓히고 _flags 에 기록
  boolean  : 모든 글이 만족하면 hard, 75% 이상이면 soft, 아니면 규칙 제외(+flag)
  override : profile.target_overrides (마지막에 덮어씀, source=override 로 표시)
불변식: 모든 hard 규칙은 원문 글별 값을 전부 포함해야 한다. 아니면 exit 1.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import assert_snapshot, dump_json_sorted, force_utf8_stdout, load_kit  # noqa: E402

# (metric, label, kind, direction, default_level, unit)   — §11-1 표 순서
RULE_SPEC = [
    ("len_mean", "평균 문장 길이", "len", "both", "hard", "자"),
    ("pct_xlong_gt100", "100자 초과 문장", "pct", "max", "hard", "%"),
    ("pct_short_le35", "35자 이하 문장", "pct", "both", "soft", "%"),
    ("pct_long_gt70", "70자 초과 문장", "pct", "both", "soft", "%"),
    ("sent_per_para_mean", "문단당 문장", "spp", "both", "hard", ""),
    ("pct_para_1", "1문장 문단", "pct", "max", "soft", "%"),
    ("pct_hapsyo", "합쇼체", "pct", "both", "hard", "%"),
    ("pct_haeyo", "해요체", "pct", "both", "soft", "%"),
    ("pct_haera", "해라체(-다.) 본문", "pct", "max", "hard", "%"),
    ("consecutive_haeyo", "해요체 연속", "count", "max", "soft", "회"),
    ("pct_question", "의문문", "pct", "max", "soft", "%"),
    ("pct_conj_start", "문두 접속부사", "pct", "both", "hard", "%"),
    ("conj_comma_bad", "접속부사 뒤 쉼표", "count", "max", "hard", "회"),
    ("conj_consecutive", "접속부사 연속 문장", "count", "max", "soft", "회"),
    ("commas_per_sent", "문장당 쉼표", "ratio", "both", "hard", ""),
    ("pct_sent_no_comma", "쉼표 없는 문장", "pct", "min", "soft", "%"),
    ("pct_list_or_go_comma", "나열·'-고,' 쉼표 비중", "pct", "min", "soft", "%"),
    ("comma_after_subject", "주어 뒤 쉼표", "count", "max", "soft", "회"),
    ("ye_reul_deureo", "'예를 들어' 류", "count", "max", "hard", "회"),
    ("yeoreobun_dangsin", "여러분/당신", "count", "max", "hard", "회"),
    ("sensory_total", "감각 묘사어", "count", "max", "hard", "회"),
    ("banned_total", "금지 표현", "count", "max", "hard", "회"),
    ("nonpref_total", "비선호 표기", "count", "max", "soft", "회"),
    ("pct_contrast", "대조 구문(아니라/보다는/말고)", "pct", "max", "soft", "%"),
    ("opening_ok", "시작=이력·질문·정의", "bool", "eq", "soft", ""),
    ("closing_is_call_or_outlook", "끝 = 권유·전망·감사", "bool", "eq", "hard", ""),
    ("closing_is_summary", "끝 = 요약 문단", "bool", "eq", "hard", ""),
    ("ai_bullet_bold", "불릿 안 볼드 소제목", "count", "max", "hard", "개"),
]
COUNT_LIKE = {"count", "bool"}


def derive_value(m: dict, metric: str):
    if metric == "sensory_total": return sum(m.get("sensory", {}).values())
    if metric == "banned_total": return sum(m.get("banned", {}).values())
    if metric == "nonpref_total": return sum(m.get("nonpreferred_spelling", {}).values())
    if metric == "opening_ok": return m.get("opening_type") in ("이력/인사", "질문", "정의")
    return m.get(metric)


def _pad(kind: str, width: float, small: bool) -> float:
    base = {"pct": 3.0, "len": 3.0, "spp": 0.3, "ratio": 0.05, "count": 1}[kind]
    p = max(base, 0.1 * width)
    return p * 2 if small else p


def _round(kind: str, v: float, up: bool):
    f = math.ceil if up else math.floor
    if kind in ("pct", "len"): return int(f(v))
    if kind == "spp": return round(f(v * 10) / 10, 1)
    if kind == "ratio": return round(f(v * 20) / 20, 2)
    return int(f(v))


def _rec(kind: str, v):
    if kind in ("pct", "len"): return int(round(v))
    if kind == "spp": return round(v, 1)
    if kind == "ratio": return round(v, 2)
    return v


def _text(kind, direction, unit, lo, hi, rec, note=""):
    n = f" ({note})" if note else ""
    if direction == "both":
        return f"{lo}~{hi}{unit} (권장 {rec}){n}"
    if direction == "max":
        return f"{hi}{unit} 이하 (권장 {rec}){n}"
    if direction == "min":
        return f"{lo}{unit} 이상 (권장 {rec}){n}"
    return ""


def derive(stats: dict, profile: dict, use_overrides: bool = True) -> dict:
    per = {k: v for k, v in stats["per_post"].items() if not v.get("error")}
    n_posts = len(per)
    small = n_posts < 8
    overall = stats["overall"]
    policy = profile.get("policy_rules", {})
    overrides = profile.get("target_overrides", {}) if use_overrides else {}
    allowed = profile.get("conj_comma_allowed", [])
    rules, flags = [], []
    for metric, label, kind, direction, level, unit in RULE_SPEC:
        vals = [derive_value(m, metric) for m in per.values()]
        rule = {"metric": metric, "label": label, "kind": kind, "level": level}
        if kind == "bool":
            trues = sum(1 for v in vals if v)
            want = metric != "closing_is_summary"           # summary 는 False 가 목표
            share = (trues if want else n_posts - trues) / n_posts if n_posts else 0
            if share >= 1.0:
                rule["level"] = "hard" if level == "hard" else "soft"
            elif share >= 0.75:
                rule["level"] = "soft"
                if level == "hard":
                    flags.append({"metric": metric, "action": "hard→soft", "observed": f"{trues}/{n_posts} true"})
            else:
                flags.append({"metric": metric, "action": "규칙 제외", "observed": f"{trues}/{n_posts} true"})
                continue
            rule.update({"equals": want, "target_text": "예" if want else "아니오", "source": "boolean",
                         "envelope": {"true": trues, "n": n_posts}, "recommended": "예" if want else "아니오"})
        else:
            env_lo, env_hi = (min(vals), max(vals)) if vals else (0, 0)
            if kind == "count":
                # 횟수 규칙의 권장값은 코퍼스 합계가 아니라 글 한 편의 중앙값
                rec = int(statistics.median(vals)) if vals else 0
            else:
                rec = _rec(kind, overall.get(metric) if metric in overall else derive_value(overall, metric))
            rule["envelope"] = {"min": env_lo, "max": env_hi}
            rule["recommended"] = rec
            if metric in policy:
                pol = policy[metric]
                hi = pol.get("max")
                rule["level"] = pol.get("level", level)
                rule["source"] = "policy"
                if hi is not None and env_hi > hi:
                    flags.append({"metric": metric, "policy_max": hi, "observed_max": env_hi, "action": f"상한을 {env_hi}로 넓힘"})
                    hi = int(env_hi)
                note = "·".join(allowed) + " 제외" if metric == "conj_comma_bad" and allowed else ""
                rule["max"] = hi
                rule["target_text"] = _text(kind, "max", unit, None, hi, rec, note)
            else:
                pad = _pad(kind, env_hi - env_lo, small)
                lo = _round(kind, env_lo - pad, up=False) if direction in ("both", "min") else None
                hi = _round(kind, env_hi + pad, up=True) if direction in ("both", "max") else None
                if kind == "pct":
                    lo = max(0, lo) if lo is not None else None
                    hi = min(100, hi) if hi is not None else None
                if lo is not None and lo < 0: lo = 0
                rule["source"] = "envelope"
                if lo is not None: rule["min"] = lo
                if hi is not None: rule["max"] = hi
                rule["target_text"] = _text(kind, direction, unit, lo, hi, rec)
        if metric in overrides:
            ov = overrides[metric]
            rule["_before_override"] = {k: rule.get(k) for k in ("min", "max", "level", "target_text")}
            rule.update(ov)
            rule["source"] = "override"
            if "target_text" not in ov:
                rule["target_text"] = _text(kind, direction if kind != "bool" else "", unit, rule.get("min"), rule.get("max"), rule.get("recommended"))
        rules.append(rule)

    # 불변식: hard 는 envelope 를 포함해야 한다
    violations = []
    for r in rules:
        if r["level"] != "hard" or r["kind"] == "bool":
            continue
        e = r["envelope"]
        if "min" in r and e["min"] < r["min"]: violations.append(f"{r['metric']}: min {r['min']} > 관측 최소 {e['min']}")
        if "max" in r and e["max"] > r["max"]: violations.append(f"{r['metric']}: max {r['max']} < 관측 최대 {e['max']}")
    return {"corpus_sha256": stats["corpus_sha256"], "n_posts": n_posts, "rules": rules, "_flags": flags, "_violations": violations}


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--print-diff", action="store_true")
    ap.add_argument("--no-overrides", action="store_true")
    a = ap.parse_args()
    kit = load_kit(a.kit)
    assert_snapshot(kit, need_stats=True)
    stats, profile = kit.stats(), kit.profile()
    tg = derive(stats, profile, use_overrides=not a.no_overrides)
    if a.print_diff:
        print("| metric | level | envelope | 결과 | source |"); print("|---|---|---|---|---|")
        for r in tg["rules"]:
            e = r["envelope"]
            env = f"{e.get('min')}~{e.get('max')}" if "min" in e else f"{e.get('true')}/{e.get('n')}"
            print(f"| {r['metric']} | {r['level']} | {env} | {r['target_text']} | {r['source']} |")
        for f in tg["_flags"]:
            print(f"[flag] {f}")
    if tg["_violations"]:
        for v in tg["_violations"]:
            print(f"[violation] {v}")
        print("규칙이 저자보다 엄격합니다. target_overrides 를 확인하세요.")
        return 1
    dump_json_sorted(tg, kit.targets_json)
    print(f"[done] targets.json  rules={len(tg['rules'])} flags={len(tg['_flags'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
