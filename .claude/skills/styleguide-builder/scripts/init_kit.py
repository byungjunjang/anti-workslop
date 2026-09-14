# -*- coding: utf-8 -*-
"""
init_kit.py — styleguides/<slug>/ 키트를 만든다 (kit.json + profile.json).

  python -X utf8 init_kit.py --out styleguides/jangpm --slug jangpm --author 장병준 --display 장피엠 \
      --site blog.nocodecamp.kr [--profile assets/profiles/jangpm.profile.json] [--genre blog] [--force]

- 이미 있는 키트는 --force 없이는 덮어쓰지 않는다 (멱등).
- profile 을 지정하지 않으면 assets/profile.default.json 을 복사하고 저자 정보만 채운다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import KIT_SCHEMA, SKILL_DIR, SKILL_VERSION, dump_json_sorted, force_utf8_stdout, read_json  # noqa: E402


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--author", required=True, help="실명 (보존 규칙에 쓰임)")
    ap.add_argument("--display", default=None, help="표시명 (파일명·제목에 쓰임). 기본 = author")
    ap.add_argument("--site", default="")
    ap.add_argument("--genre", default="blog", choices=["blog"])
    ap.add_argument("--profile", default=None, help="시작 프로파일 JSON (기본 assets/profile.default.json)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    out = Path(a.out).resolve()
    if (out / "kit.json").exists() and not a.force:
        print(f"[skip] 이미 키트가 있습니다: {out}  (--force 로 덮어쓰기)")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    (out / "corpus").mkdir(exist_ok=True)

    display = a.display or a.author
    profile = read_json(Path(a.profile) if a.profile else SKILL_DIR / "assets" / "profile.default.json")
    profile.update({"author": a.author, "display": display, "site": a.site, "genre": a.genre, "slug": a.slug})
    dump_json_sorted(profile, out / "profile.json")

    meta = {
        "schema_version": KIT_SCHEMA, "slug": a.slug, "author": a.author, "display": display, "site": a.site,
        "genre": a.genre, "skill_version": SKILL_VERSION, "created_by": "styleguide-builder",
        "paths": {
            "corpus": "corpus", "stats": "stats.json", "stats_md": "stats.md", "targets": "targets.json",
            "profile": "profile.json", "reading_pack": "reading-pack.md", "worksheet": "reading-worksheet.md",
            "guideline": f"{display} 글쓰기 문체 가이드라인.md", "verification": "verification.json",
            "profile_report": "docs/style-profile.md",
        },
    }
    dump_json_sorted(meta, out / "kit.json")
    print(f"[done] kit: {out}  (slug={a.slug}, author={a.author}, display={display})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
