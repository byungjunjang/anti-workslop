#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""빈 취향 폴더를 만든다. 취향은 쓰는 사람마다 다르므로 저장소에는 기본 취향이 없고, 여기서 빈 문서로 시작한다.

  python -X utf8 .claude/skills/taste-builder/scripts/init_taste.py [--root 프로젝트 루트]

없는 파일만 만든다. 있으면 [skip] 을 내고 건드리지 않는다(멱등).
  taste/writing-taste.md   references/taste-template.md 의 {{DATE}} 를 오늘로
  taste/cases/raw/.gitkeep
  taste/artifacts.json     []
  taste/changelog.md       표 머리만
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[4]   # scripts → taste-builder → skills → .claude → 프로젝트 루트
TEMPLATE = HERE.parents[1] / "references" / "taste-template.md"
CHANGELOG_HEAD = (
    "# writing-taste changelog\n\n"
    "한 갱신에 한 항목. 최신이 위.\n\n"
    "| 날짜 | 스냅샷 | 케이스 +신규/중복 | 규칙 변동 (신설/승격/강등/보류) | 버전 |\n"
    "|---|---|---|---|---|\n"
)


def files(today: str) -> dict:
    return {
        Path("taste/writing-taste.md"): TEMPLATE.read_text(encoding="utf-8").replace("{{DATE}}", today),
        Path("taste/cases/raw/.gitkeep"): "",
        Path("taste/artifacts.json"): "[]\n",
        Path("taste/changelog.md"): CHANGELOG_HEAD,
    }


def init(root: Path, today: str) -> list:
    """(동작, 경로) 목록. 동작은 created 또는 skip."""
    out = []
    for rel, body in files(today).items():
        p = root / rel
        if p.exists():
            out.append(("skip", rel))
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        out.append(("created", rel))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="빈 취향 폴더(taste/)를 만든다")
    p.add_argument("--root", default=str(PROJECT_ROOT), help="프로젝트 루트(기본: 이 스크립트에서 네 단계 위)")
    p.add_argument("--date", default=dt.date.today().isoformat(), help="문서 머리의 갱신일(기본: 오늘)")
    a = p.parse_args(argv)
    for action, rel in init(Path(a.root), a.date):
        print(f"[skip] 이미 있다: {rel.as_posix()}" if action == "skip" else f"[created] {rel.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
