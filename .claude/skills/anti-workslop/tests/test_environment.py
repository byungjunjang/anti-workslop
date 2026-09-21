# -*- coding: utf-8 -*-
"""환경 탓에 로컬만 통과하는 실패를 막는다.

2026-09-21 에 두 번 연달아 CI 가 깨졌다. 둘 다 로컬에서는 통과했다.

  1. collect.py 가 bs4 를 쓰는데 requirements.txt 가 없었다. 개발기에는 이미
     깔려 있어 통과했고, 맨 파이썬인 CI 에서만 ModuleNotFoundError 로 죽었다.
  2. 원문에 섞인 U+0008 을 lxml 은 묶인 libxml2 판에 따라 지우기도 남기기도
     해서, 같은 버전인데 Windows 는 184 문장, Linux 는 183 문장이 나왔다.

두 가지 모두 "무엇이 깔려 있는가"에 기대지 않고 잡아야 한다. 아래 테스트는
설치 상태와 무관하게 소스만 읽어 판정하므로, 개발기에서도 똑같이 실패한다.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".acceptance", "node_modules", "docs", "examples"}

# import 이름과 배포판 이름이 다른 것들
DIST_ALIAS = {"bs4": "beautifulsoup4", "yaml": "pyyaml", "PIL": "pillow", "dotenv": "python-dotenv", "fitz": "pymupdf"}


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def py_files() -> list[Path]:
    out = []
    for p in ROOT.rglob("*.py"):
        if not SKIP_DIRS.isdisjoint(p.relative_to(ROOT).parts):
            continue
        out.append(p)
    return out


def local_module_names(files: list[Path]) -> set[str]:
    """저장소 안에서 해결되는 이름. 스크립트가 sys.path 를 조작해 서로를 부른다."""
    names = {f.stem for f in files}
    for f in files:
        names.update(part for part in f.relative_to(ROOT).parts[:-1])
    return names


def imported_roots(files: list[Path]) -> dict[str, list[str]]:
    """최상위 import 이름 -> 그걸 쓰는 파일들."""
    found: dict[str, list[str]] = {}
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            raise AssertionError(f"{f.relative_to(ROOT)} 구문 오류: {e}") from e
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:  # 상대 import 는 로컬
                    continue
                roots = [(node.module or "").split(".")[0]]
            else:
                continue
            for r in roots:
                if r:
                    found.setdefault(r, []).append(str(f.relative_to(ROOT)))
    return found


def declared() -> set[str]:
    """requirements.txt 는 CI 가 설치하는 것, -optional 은 사람이 손으로 돌리는 도구용."""
    out = set()
    for name in ("requirements.txt", "requirements-optional.txt"):
        req = ROOT / name
        if not req.exists():
            continue
        for line in req.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            out.add(norm(re.split(r"[<>=!~\[]", line)[0]))
    return out


class DependencyDeclaration(unittest.TestCase):
    def test_third_party_imports_are_declared(self):
        files = py_files()
        self.assertTrue(files, "스캔할 파이썬 파일이 없다 — 경로 기준이 틀렸다")
        local = local_module_names(files)
        have = declared()
        missing = {}
        for root, users in sorted(imported_roots(files).items()):
            if root in sys.stdlib_module_names or root in local:
                continue
            if norm(DIST_ALIAS.get(root, root)) in have:
                continue
            missing[root] = sorted(set(users))[:3]
        self.assertEqual(
            missing, {},
            "requirements.txt 에 없는 서드파티 import 가 있다. 개발기에 깔려 있어도 "
            "CI 는 맨 파이썬이라 ModuleNotFoundError 로 죽는다: " + repr(missing))


class ParserIndependence(unittest.TestCase):
    """같은 원문이면 어떤 파서를 잡든 같은 결과가 나와야 한다."""

    def setUp(self):
        scripts = ROOT / ".claude" / "skills" / "styleguide-builder" / "scripts"
        sys.path.insert(0, str(scripts))
        self.addCleanup(lambda: sys.path.remove(str(scripts)))
        import collect
        self.collect = collect

    def test_strip_control_keeps_layout_whitespace(self):
        s = self.collect.strip_control("가\x08나\x00다\x1f라\x7f마\t바\n사\r아")
        self.assertEqual(s, "가나다라마\t바\n사\r아")

    def test_control_char_does_not_change_extraction(self):
        html = "<article><p>앞 문장입니다.\x08 뒤 문장입니다.</p></article>"
        outs = {}
        for parser in ("html.parser", "lxml"):
            try:
                __import__("lxml") if parser == "lxml" else None
            except ImportError:
                continue
            orig = self.collect._parser
            self.collect._parser = lambda p=parser: p
            try:
                outs[parser] = self.collect.extract_html(html, "s", "u", "article", [])["blocks"]
            finally:
                self.collect._parser = orig
        self.assertTrue(outs)
        for parser, blocks in outs.items():
            text = " ".join(b["text"] for b in blocks)
            self.assertNotIn("\x08", text, f"{parser}: 제어문자가 본문에 남았다")
            self.assertIn("앞 문장입니다. 뒤 문장입니다.", text, f"{parser}: 문장이 붙어버렸다")
        self.assertEqual(len(set(map(repr, outs.values()))), 1, f"파서별 결과가 다르다: {outs}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
