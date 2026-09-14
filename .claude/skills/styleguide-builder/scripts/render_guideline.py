# -*- coding: utf-8 -*-
"""
render_guideline.py — 템플릿 + stats/targets/profile + 워크시트 → 가이드라인 (유일한 생성 경로).

  python -X utf8 render_guideline.py --kit styleguides/<slug> --version 2026-09-07 [--template PATH] [--out PATH] [--allow-todo]

슬롯 문법 ({{...}})
  {{n:KEY}}            stats.overall 값 (점 표기로 중첩: heading_forms.noun_pct)
  {{int:KEY}}          반올림 정수            {{k:KEY}} 천 단위 쉼표     {{hund:KEY}} 백 단위 반올림+쉼표 ("약 1,500")
  {{one_in:KEY}}       비율 → "N" 또는 "20~25" (…문장에 1개)   {{fraction:KEY}} 비율 → 절반/3분의 2/4분의 3
  {{ratio:KEY1/KEY2}}  두 비율의 비 → "4분의 1" 같은 분수 표현
  {{t:METRIC.field}}   targets 규칙: rec | range(target_text) | min | max | level | minmax("45~65")
  {{p:KEY}}            profile 값 (목록은 '·' 로 연결)        {{p:KEY|, }} 구분자 지정
  {{len:default}} {{len:valid}}  글 길이 기본값 (profile.length_defaults 없으면 코퍼스 p25~p75 / min~max 를 500 단위로)
  {{v:version}} {{v:corpus_sha8}} {{v:n_posts}} {{v:date_from}} {{v:date_to}} {{v:n_sentences_hund}}
  {{q:SLOT}}           워크시트 `## slot:SLOT` 본문 (HTML 주석 제거). 한 줄 안에 있으면 줄바꿈을 공백으로
  {{table:3|4_2|5_1|7_2|11_1}}   생성 표        {{conjfreq:N}} {{lexfreq:N}}   빈도 나열
  {{rhythm:slug:pN}}   문단 길이 흐름 "36 → 37 → 66 → 10 → 82자"
  {{count:post_structure.도입=이력·경험}}   워크시트 표에서 열 값이 같은 행 수
채워지지 않은 슬롯이 있으면 --allow-todo 없이는 exit 1 (미충족 슬롯 목록 출력).
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import (SKILL_DIR, SKILL_VERSION, assert_snapshot, dump_json_sorted, force_utf8_stdout, load_kit,  # noqa: E402
                    read_text, sha256_file, sha256_text, write_text)

SLOT_RE = re.compile(r"\{\{([a-z_]+):([^{}]*?)\}\}")
TABLE_11_1_METRICS = None  # 전체 규칙


# ---------------------------------------------------------------------------
def parse_worksheet(text: str) -> dict[str, str]:
    slots, cur, buf = {}, None, []
    for line in text.replace("\r\n", "\n").split("\n"):
        m = re.match(r"^##\s+slot:([A-Za-z0-9_]+)\s*$", line)
        if m:
            if cur is not None:
                slots[cur] = "\n".join(buf).strip()
            cur, buf = m.group(1), []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        slots[cur] = "\n".join(buf).strip()
    out = {}
    for k, v in slots.items():
        v = re.sub(r"<!--.*?-->", "", v, flags=re.S).strip()
        out[k] = v
    return out


def parse_table(md: str) -> list[dict]:
    rows, header = [], None
    for line in md.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if header is None:
            header = cells; continue
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


# ---------------------------------------------------------------------------
def _get(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(dotted)
    return cur


def _num(v) -> str:
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else f"{v:g}"
    return str(v)


def one_in(pct: float) -> str:
    if not pct:
        return "0"
    n = 100.0 / pct
    if n < 20:
        return str(int(round(n)))
    lo, hi = int(math.floor(n / 5) * 5), int(math.ceil(n / 5) * 5)
    return f"{lo}" if lo == hi else f"{lo}~{hi}"


def fraction(pct: float) -> str:
    table = [(85, "6분의 5"), (78, "5분의 4"), (72, "4분의 3"), (64, "3분의 2"), (57, "5분의 3"), (47, "절반"),
             (37, "5분의 2"), (30, "3분의 1"), (22, "4분의 1"), (17, "5분의 1"), (0, None)]
    for th, name in table:
        if pct >= th:
            return name if name else f"{int(round(pct))}%"
    return f"{int(round(pct))}%"


def nice500(x: float, up: bool) -> int:
    f = math.ceil if up else math.floor
    return int(f(x / 500.0) * 500)


def fmt_k(v) -> str:
    return f"{int(round(v)):,}"


# ---------------------------------------------------------------------------
class Renderer:
    def __init__(self, kit, version: str, allow_todo: bool):
        self.kit, self.version, self.allow_todo = kit, version, allow_todo
        self.stats, self.targets, self.profile = kit.stats(), kit.targets(), kit.profile()
        self.o = self.stats["overall"]
        self.rules = {r["metric"]: r for r in self.targets["rules"]}
        self.slots = parse_worksheet(read_text(kit.worksheet)) if kit.worksheet.exists() else {}
        self.missing: list[str] = []
        self.used_slots: set[str] = set()
        self.excluded_rules: set[str] = set()

    # --- 도우미 ---
    def rule(self, metric: str) -> dict:
        if metric not in self.rules:
            raise KeyError(f"targets 에 규칙이 없음: {metric}")
        return self.rules[metric]

    def t(self, spec: str) -> str:
        metric, field = spec.split(".", 1)
        if metric not in self.rules:
            # derive 가 코퍼스 사정으로 규칙을 제외한 경우(불리언 규칙 등). 문서는 깨지지 않게 완화 표기로 채운다.
            self.excluded_rules.add(metric)
            return "soft" if field == "level" else "(규칙 제외)"
        r = self.rule(metric)
        if field == "rec": return _num(r.get("recommended", ""))
        if field == "range": return r.get("target_text", "")
        if field == "min": return _num(r.get("min", ""))
        if field == "max": return _num(r.get("max", ""))
        if field == "level": return r.get("level", "")
        if field == "minmax": return f"{_num(r.get('min', ''))}~{_num(r.get('max', ''))}"
        raise KeyError(f"t:{spec}")

    def lengths(self, which: str) -> str:
        ld = self.profile.get("length_defaults")
        if ld and which in ld:
            lo, hi = ld[which]
        elif which == "default":
            lo, hi = nice500(self.o["post_chars_p25"], False), nice500(self.o["post_chars_p75"], True)
        else:
            lo, hi = nice500(self.o["post_chars_min"], False), nice500(self.o["post_chars_max"], True)
        return f"{lo:,}~{hi:,}"

    def v(self, key: str) -> str:
        if key == "version": return self.version
        if key == "corpus_sha8": return self.stats["corpus_sha256"][:8]
        if key == "n_posts": return str(self.stats["n_posts"])
        if key == "date_from": return self.stats["date_range"][0][:7].replace("-", ".")
        if key == "date_to": return self.stats["date_range"][1][:7].replace("-", ".")
        if key == "n_sentences_hund": return f"{int(round(self.o['n_sentences'] / 100.0) * 100):,}"
        if key == "skill_version": return SKILL_VERSION
        raise KeyError(f"v:{key}")

    def table(self, name: str) -> str:
        o, R = self.o, self.rule
        if name == "11_1":
            rows = ["| 항목 | 기준 | 등급 |", "|---|---|---|"]
            for r in self.targets["rules"]:
                rows.append(f"| {r['label']} | {r['target_text']} | {r['level']} |")
            return "\n".join(rows)
        if name == "3":
            s, l = R("pct_short_le35"), R("pct_long_gt70")
            return "\n".join([
                "| 항목 | 권장 | 허용 범위 | 등급 |", "|---|---|---|---|",
                f"| 평균 문장 길이 (공백 포함) | {self.t('len_mean.rec')}자, 약 {int(round(o['words_mean']))}어절 | {self.t('len_mean.minmax')}자 | {R('len_mean')['level']} |",
                f"| 100자 넘는 문장 | {self.t('pct_xlong_gt100.rec')}% | {self.t('pct_xlong_gt100.max')}% 이하 | {R('pct_xlong_gt100')['level']} |",
                f"| 35자 이하 / 70자 초과 문장 | {_num(s['recommended'])}% / {_num(l['recommended'])}% | 각 {_num(min(s['min'], l['min']))}~{_num(max(s['max'], l['max']))}% | {s['level']} |",
                f"| 문단당 문장 수 | {self.t('sent_per_para_mean.rec')}개 안팎 | 평균 {self.t('sent_per_para_mean.minmax')} | {R('sent_per_para_mean')['level']} |",
                f"| 한 문장짜리 문단 | {self.t('pct_para_1.rec')}% | {self.t('pct_para_1.max')}% 이하 | {R('pct_para_1')['level']} |",
            ])
        if name == "4_2":
            return "\n".join([
                "| 항목 | 권장 | 허용 범위 | 등급 |", "|---|---|---|---|",
                f"| 문장당 쉼표 | {self.t('commas_per_sent.rec')}개 | {self.t('commas_per_sent.minmax')} | {R('commas_per_sent')['level']} |",
                f"| 쉼표 없는 문장 | {self.t('pct_sent_no_comma.rec')}% | {self.t('pct_sent_no_comma.min')}% 이상 | {R('pct_sent_no_comma')['level']} |",
                f"| 쉼표 2개 이상인 문장 | {_num(o['pct_sent_2plus_comma'])}% | | (참고) |",
                f"| 문단당 쉼표 | {_num(o['commas_per_para'])}개 | | (참고) |",
            ])
        if name == "5_1":
            return "\n".join([
                "| 종결 | 권장 | 허용 범위 | 등급 |", "|---|---|---|---|",
                f"| 합쇼체 (-습니다/-입니다/-겁니다) | {self.t('pct_hapsyo.rec')}% | {self.t('pct_hapsyo.minmax')}% | {R('pct_hapsyo')['level']} |",
                f"| 해요체 (-고요/-는데요/-네요/-세요/-까요) | {self.t('pct_haeyo.rec')}% | {self.t('pct_haeyo.minmax')}% | {R('pct_haeyo')['level']} |",
                f"| -죠/-지요 | {_num(o['pct_jyo'])}% | | (참고) |",
                f"| 해라체 (-다.) 본문 | 0 (인용문·소제목 제외) | {self.t('pct_haera.max')}% 이하 | {R('pct_haera')['level']} |",
                f"| 의문문 | {self.t('pct_question.rec')}% | {self.t('pct_question.max')}% 이하 | {R('pct_question')['level']} |",
                f"| 해요체 두 문장 연속 | {self.t('consecutive_haeyo.rec')}회 | {self.t('consecutive_haeyo.max')}회 이하 | {R('consecutive_haeyo')['level']} |",
            ])
        if name == "7_2":
            rows = ["| 쓴다 | 쓰지 않는다 |", "|---|---|"]
            n = 0
            for k, v in o["spelling_variants"].items():
                if v["preferred"] == v["a"]:
                    rows.append(f"| {v['a']} | {v['b']} |"); n += 1
                elif v["preferred"] == v["b"]:
                    rows.append(f"| {v['b']} | {v['a']} |"); n += 1
            if n == 0:
                return "(코퍼스에서 한쪽으로 굳은 표기 변이가 관찰되지 않았다. 표준 표기를 쓴다.)"
            return "\n".join(rows)
        raise KeyError(f"table:{name}")

    def conjfreq(self, n: int) -> str:
        items = list(self.o["conj_total"].items())[:n]
        return ", ".join(f"{k} {v}" for k, v in items)

    def lexfreq(self, n: int) -> str:
        # profile.lexicon_report 가 있으면 그 단어들을 그 순서로, 없으면 watchlist 상위 n개
        report = self.profile.get("lexicon_report") or []
        if report:
            return ", ".join(f"{w} {self.o['lexicon'].get(w, 0)}" for w in report)
        items = list(self.o["lexicon"].items())[:n]
        return ", ".join(f"{k} {v}" for k, v in items)

    def rhythm(self, spec: str) -> str:
        slug, pn = spec.rsplit(":", 1)
        seq = self.stats["per_post"][slug]["para_rhythms"][int(pn.lstrip("p"))]
        return " → ".join(str(x) for x in seq) + "자"

    def count(self, spec: str) -> str:
        slot, cond = spec.split(".", 1)
        col, val = cond.split("=", 1)
        rows = parse_table(self.slots.get(slot, ""))
        return str(sum(1 for r in rows if r.get(col, "").strip() == val.strip()))

    def q(self, slot: str, inline: bool) -> str:
        self.used_slots.add(slot)
        body = self.slots.get(slot, "")
        if not body:
            self.missing.append(slot)
            return f"[TODO:{slot}]"
        # 워크시트 본문 안의 숫자 슬롯({{rhythm:…}}, {{n:…}}, {{t:…}} 등)도 채운다. q 중첩은 금지.
        body = "\n".join(self.render_line(l, allow_q=False) for l in body.split("\n"))
        return re.sub(r"\s*\n\s*", " ", body) if inline else body

    def p(self, spec: str) -> str:
        key, sep = (spec.split("|", 1) + ["·"])[:2] if "|" in spec else (spec, "·")
        v = self.profile.get(key, "")
        if isinstance(v, list):
            return sep.join(str(x) for x in v)
        if isinstance(v, dict):
            return sep.join(f"{k}" for k in v)
        return str(v)

    # --- 본 렌더 ---
    def render_line(self, line: str, allow_q: bool = True) -> str:
        alone = SLOT_RE.fullmatch(line.strip()) is not None

        def sub(m):
            kind, arg = m.group(1), m.group(2)
            if kind == "q" and not allow_q:
                raise SystemExit(f"워크시트 안에서는 q 슬롯을 쓸 수 없습니다: {{{{q:{arg}}}}}")
            try:
                if kind == "n": return _num(_get(self.o, arg))
                if kind == "int": return str(int(round(float(_get(self.o, arg)))))
                if kind == "k": return fmt_k(_get(self.o, arg))
                if kind == "hund": return f"{int(round(float(_get(self.o, arg)) / 100.0) * 100):,}"
                if kind == "one_in": return one_in(float(_get(self.o, arg)))
                if kind == "fraction": return fraction(float(_get(self.o, arg)))
                if kind == "ratio":
                    a, b = arg.split("/")
                    va, vb = float(_get(self.o, a)), float(_get(self.o, b))
                    return fraction(100.0 * va / vb) if vb else "0"
                if kind == "t": return self.t(arg)
                if kind == "p": return self.p(arg)
                if kind == "len": return self.lengths(arg)
                if kind == "v": return self.v(arg)
                if kind == "q": return self.q(arg, inline=not alone)
                if kind == "table": return self.table(arg)
                if kind == "conjfreq": return self.conjfreq(int(arg))
                if kind == "lexfreq": return self.lexfreq(int(arg))
                if kind == "rhythm": return self.rhythm(arg)
                if kind == "count": return self.count(arg)
            except KeyError as e:
                raise SystemExit(f"슬롯을 채울 수 없습니다: {{{{{kind}:{arg}}}}} → {e}")
            raise SystemExit(f"알 수 없는 슬롯 종류: {kind}")
        return SLOT_RE.sub(sub, line)

    def render(self, template: str) -> str:
        return "\n".join(self.render_line(l) for l in template.replace("\r\n", "\n").split("\n"))


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    ap.add_argument("--version", required=True, help="문서에 적을 버전 문자열 (예: 2026-09-07)")
    ap.add_argument("--template", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--allow-todo", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    kit = load_kit(a.kit)
    assert_snapshot(kit, need_stats=True, need_targets=True)
    tpl_path = Path(a.template) if a.template else SKILL_DIR / "assets" / "templates" / f"{kit.meta.get('genre', 'blog')}.template.md"
    out_path = Path(a.out) if a.out else kit.guideline
    r = Renderer(kit, a.version, a.allow_todo)
    doc = r.render(read_text(tpl_path))
    if r.missing and not a.allow_todo:
        print("채워지지 않은 워크시트 슬롯:"); [print("  - " + s) for s in dict.fromkeys(r.missing)]
        print("reading-worksheet.md 의 해당 `## slot:` 절을 채운 뒤 다시 실행하세요. (--allow-todo 로 초안 확인 가능)")
        return 1
    unused = sorted(set(r.slots) - r.used_slots - {"post_structure", "profile_proposals", "policy_flag_notes"})
    write_text(out_path, doc if doc.endswith("\n") else doc + "\n")
    manifest = {
        "template": str(tpl_path.relative_to(SKILL_DIR)) if str(tpl_path).startswith(str(SKILL_DIR)) else str(tpl_path),
        "template_sha256": sha256_file(tpl_path), "worksheet_sha256": sha256_file(kit.worksheet) if kit.worksheet.exists() else "",
        "stats_sha256": sha256_file(kit.stats_json), "targets_sha256": sha256_file(kit.targets_json),
        "profile_sha256": sha256_file(kit.profile_json), "version": a.version, "output": out_path.name,
        "output_sha256": sha256_file(out_path), "skill_version": SKILL_VERSION, "allow_todo": a.allow_todo,
    }
    dump_json_sorted(manifest, kit.render_manifest)
    if not a.quiet:
        print(f"[done] {out_path}  ({len(doc)} chars, todo={len(set(r.missing))}, unused_slots={unused or 'none'})")
    if r.excluded_rules:
        print(f"[note] targets 에 없는 규칙을 완화 표기로 채움: {sorted(r.excluded_rules)} (derive _flags 참조)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
