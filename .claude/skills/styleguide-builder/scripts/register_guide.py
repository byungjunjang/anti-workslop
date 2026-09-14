# -*- coding: utf-8 -*-
"""
register_guide.py — 검증을 통과한 키트를 anti-workslop 가이드로 등록한다.

  python -X utf8 register_guide.py --kit styleguides/<slug> [--name <가이드 이름>]
  python -X utf8 register_guide.py --remove <가이드 이름>

등록하면 anti-workslop 에서 `check_all.py --guide <이름>` 으로 진단·검수·윤문할 수 있고,
`--hint` 의 레이어 줄에 이름이 나온다. 쓰는 곳은 .claude/skills/anti-workslop/references/base-guidelines.json 하나다.

- 이름 기본값은 kit.json 의 display(표시명). 가이드 파일이 없거나 verification.json 이 통과가 아니면 거부한다.
- 같은 설정으로 이미 있으면 [skip] (멱등). 다른 설정으로 있으면 거부한다(--remove 뒤 다시).
- 기본 가이드(_builtin)는 지우지 않는다.
- 이 스킬이 만드는 키트는 전부 블로그형 줄글이라 장르·읽기 묶음 절·§14 블록이 같다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]   # scripts → styleguide-builder → skills → .claude → 프로젝트 루트
BASE = ROOT / ".claude" / "skills" / "anti-workslop" / "references" / "base-guidelines.json"

# 블로그 템플릿(assets/templates/blog.template.md) §14 가운데 윤문에 쓰는 블록. 장피엠 기본 가이드와 같다.
BLOG_S14 = ["작업", "보존", "문장", "종결", "접속", "어휘", "금지", "AI 티"]
BLOG_PACK = ["8", "11-2", "14"]
STYLE = "python -X utf8 .claude/skills/styleguide-builder/scripts/check_style.py --kit {kit} {extra}--json {{file}}"
HTML = "python -X utf8 .claude/skills/anti-workslop/scripts/check_html.py --guide {name} {extra}{{file}}"


class RegisterError(Exception):
    pass


def entry(name: str, kit: str, guide: str) -> dict:
    """표 이름 → 이 가이드의 값. 최상위 키(가이드 경로 목록)는 이름 자체다."""
    return {
        name: [guide],
        "_checks": {"md": STYLE.format(kit=kit, extra=""), "html": HTML.format(name=name, extra="")},
        "_checks_short": {"md": STYLE.format(kit=kit, extra="--subset counts "),
                          "html": HTML.format(name=name, extra="--short ")},
        "_checker_kind": "style",
        "_genre_of": "줄글",
        "_pack_sections": list(BLOG_PACK),
        "_s14_blocks": list(BLOG_S14),
    }


def _current(bg: dict, name: str) -> dict:
    return {t: (bg.get(name) if t == name else bg.get(t, {}).get(name))
            for t in entry(name, "", "")}


def register(bg: dict, name: str, kit: str, guide: str) -> tuple[dict, bool]:
    """(새 bg, 바뀌었는가). bg 는 고치지 않는다."""
    if not name or name.startswith("_") or name == "없음":
        raise RegisterError(f"쓸 수 없는 이름이다: {name!r}")
    want = entry(name, kit, guide)
    if name in bg:
        if _current(bg, name) == want:
            return bg, False
        raise RegisterError(f"{name!r} 는 이미 다른 설정으로 등록돼 있다. --remove {name} 뒤 다시 등록한다")
    out: dict = {}
    placed = False
    for k, v in bg.items():
        if not placed and k.startswith("_"):
            out[name] = want[name]
            placed = True
        out[k] = json.loads(json.dumps(v, ensure_ascii=False))
    if not placed:
        out[name] = want[name]
    for table, value in want.items():
        if table != name:
            out.setdefault(table, {})[name] = value
    return out, True


def remove(bg: dict, name: str) -> dict:
    if name in bg.get("_builtin", []):
        raise RegisterError(f"{name!r} 는 저장소 기본 가이드라 지우지 않는다")
    if name.startswith("_") or name not in bg:
        raise RegisterError(f"등록된 가이드가 아니다: {name!r}")
    out = {k: json.loads(json.dumps(v, ensure_ascii=False)) for k, v in bg.items() if k != name}
    for table in entry(name, "", ""):
        if table != name and isinstance(out.get(table), dict):
            out[table].pop(name, None)
    return out


def kit_info(root: Path, kit: str) -> tuple[str, str]:
    """(표시명, 루트 기준 가이드 경로). 등록할 수 없는 키트면 RegisterError."""
    kdir = root / kit
    meta_p = kdir / "kit.json"
    if not meta_p.exists():
        raise RegisterError(f"kit.json 이 없다: {kit}")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    if meta.get("created_by") != "styleguide-builder":
        raise RegisterError(f"styleguide-builder 가 만든 키트가 아니다: {kit} (손으로 만든 키트는 base-guidelines.json 에 직접 적는다)")
    guide = meta.get("paths", {}).get("guideline") or f"{meta['display']} 글쓰기 문체 가이드라인.md"
    if not (kdir / guide).exists():
        raise RegisterError(f"가이드 파일이 없다: {kit}/{guide} (render_guideline.py 를 먼저)")
    ver_p = kdir / meta.get("paths", {}).get("verification", "verification.json")
    ver = json.loads(ver_p.read_text(encoding="utf-8")) if ver_p.exists() else {}
    if ver.get("passed") is not True:
        raise RegisterError(f"검증을 통과하지 않았다: {kit} (verify_guideline.py --kit {kit} --report 를 먼저)")
    return meta["display"], f"{kit}/{guide}"


def save(bg: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(bg, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="키트를 anti-workslop 가이드로 등록하거나 등록을 뺀다")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--kit", help="styleguides/<slug> (프로젝트 루트 기준)")
    g.add_argument("--remove", metavar="NAME", help="등록을 뺄 가이드 이름")
    ap.add_argument("--name", default=None, help="가이드 이름(기본 kit.json 의 display)")
    ap.add_argument("--base", default=str(BASE), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    base = Path(a.base)
    bg = json.loads(base.read_text(encoding="utf-8"))
    try:
        if a.remove:
            save(remove(bg, a.remove), base)
            print(f"[removed] {a.remove}")
            return 0
        kit = Path(a.kit).as_posix().rstrip("/")
        display, guide = kit_info(ROOT, kit)
        name = a.name or display
        new, changed = register(bg, name, kit, guide)
    except RegisterError as e:
        print(f"[거부] {e}", file=sys.stderr)
        return 1
    if not changed:
        print(f"[skip] 이미 등록: {name}")
        return 0
    save(new, base)
    print(f"[done] 가이드 등록: {name} ({guide})")
    print(f"       anti-workslop 에서 --guide {name} 로 윤문한다. README 표에 올리려면 styleguides/README.md 에 한 행을 더한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
