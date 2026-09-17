#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""코멘트 raw 스냅샷 → taste/cases/cases.jsonl 병합, 또는 --map 으로 케이스 필드 갱신.

  python ingest_comments.py --raw raw.json [--ledger cases.jsonl]
  python ingest_comments.py --map T-0001=W-01,W-02 T-0003=W-02 [--status 반영] [--note "..."] [--ledger cases.jsonl]

원장은 추가 전용이다. --map 은 rule_ids / status / note 만 바꾼다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TAGS = {"[싫]": "지적", "[좋]": "칭찬", "[고침]": "고침", "[규칙]": "규칙", "[질문]": "질문"}
PROJECT_ROOT = Path(__file__).resolve().parents[4]  # scripts → taste-builder → skills → .claude → 프로젝트 루트
DEFAULT_LEDGER = PROJECT_ROOT / "taste" / "cases" / "cases.jsonl"


def parse_tag(text):
    t = text.lstrip()
    for tag, kind in TAGS.items():
        if t.startswith(tag):
            return kind, t[len(tag):].strip()
    return None, None


def source_ref(src):
    """중복 제거 키의 앞자리. 아티팩트는 URL, 대화는 source_ref. 옛 케이스에는 source_ref 가 없다."""
    return src.get("artifact_url") or src.get("source_ref", "")


def load_ledger(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def save_ledger(path, cases):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:  # Windows 에서도 LF (저장소 eol=lf)
        f.write("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))


def next_id(cases):
    mx = 0
    for c in cases:
        m = re.fullmatch(r"T-(\d+)", c["case_id"])
        if m:
            mx = max(mx, int(m.group(1)))
    return f"T-{mx + 1:04d}"


def ingest(raw_path, ledger_path):
    raw_path, ledger_path = Path(raw_path), Path(ledger_path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cases = load_ledger(ledger_path)
    seen = {(source_ref(c["source"]), c["source"]["thread_id"]) for c in cases}
    new, dup = [], 0
    doc = raw.get("doc", {})
    origin = raw.get("origin", "artifact")        # artifact = 코멘트 수집, chat = 대화에서 들은 취향
    ref = source_ref(raw)
    for th in raw["threads"]:
        key = (ref, th["thread_id"])
        if key in seen:
            dup += 1
            continue
        texts = [c["text"] for c in th.get("comments", []) if c.get("author") == "user"]
        first = texts[0] if texts else ""
        kind, rest = parse_tag(first)
        if kind:
            kind_source, rewrite = "tagged", (rest if kind == "고침" else "")
        else:
            kind, kind_source, rewrite = th.get("kind_hint") or "미분류", "inferred", th.get("rewrite", "")
        anchor = th.get("anchor", {})
        case = {
            "case_id": next_id(cases + new),
            "date": raw.get("collected_at", "")[:10],
            "origin": origin,
            "source": {"artifact_url": raw.get("artifact_url", ""), "source_ref": ref,
                       "artifact_title": raw.get("artifact_title", ""),
                       "version": doc.get("version", ""), "thread_id": th["thread_id"], "raw_file": raw_path.name},
            "doc": {"project": doc.get("project", ""), "genre": doc.get("genre", ""),
                    "base_guideline": doc.get("base_guideline", "none"), "section": anchor.get("section") or "전체"},
            "anchor": {"quote": anchor.get("quote", ""), "context": anchor.get("context", "")},
            "comment": texts,
            "kind": kind, "kind_source": kind_source, "rewrite": rewrite,
            "rule_ids": [], "status": "신규", "note": "",
        }
        new.append(case)
        seen.add(key)
    save_ledger(ledger_path, cases + new)
    return new, dup


def apply_map(ledger_path, mappings, status, note):
    cases = load_ledger(ledger_path)
    by_id = {c["case_id"]: c for c in cases}
    for m in mappings:
        cid, _, rules = m.partition("=")
        if cid not in by_id:
            sys.exit(f"unknown case {cid}")
        by_id[cid]["rule_ids"] = [r for r in rules.split(",") if r]
        if status:
            by_id[cid]["status"] = status
        if note is not None:
            by_id[cid]["note"] = note
    save_ledger(ledger_path, cases)
    return len(mappings)


def main(argv=None):
    p = argparse.ArgumentParser(description="taste-builder ingest")
    p.add_argument("--raw")
    p.add_argument("--map", nargs="+")
    p.add_argument("--status")
    p.add_argument("--note")
    p.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    a = p.parse_args(argv)
    if a.raw:
        new, dup = ingest(a.raw, a.ledger)
        ids = f"{new[0]['case_id']}..{new[-1]['case_id']}" if new else "-"
        print(f"new={len(new)} dup={dup} ids={ids}")
    elif a.map:
        print(f"mapped={apply_map(a.ledger, a.map, a.status, a.note)}")
    else:
        p.error("--raw 또는 --map 중 하나가 필요")
    return 0


if __name__ == "__main__":
    sys.exit(main())
