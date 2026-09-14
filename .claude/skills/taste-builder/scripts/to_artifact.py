#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""산출물 → claude.ai 코멘트용 아티팩트 파일.
HTML · 아티팩트는 <!DOCTYPE>/<html>/<head>/<body> 를 자체 공급하므로 <title>·<style>·본문만 남기고,
       다크 테마 토큰과 코멘트 안내 배너를 붙인다.
MD   · 본문은 그대로 두고 맨 위에 같은 안내를 인용문으로 붙인다.

  python to_artifact.py in.html out.artifact.html
  python to_artifact.py in.md   out.artifact.md
"""
import re
import sys
from pathlib import Path

DARK = """
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { --ink:#e8e8e8; --muted:#9a9a9a; --line:#333; --bg:#111; --soft:#1a1a1a; --verdict:#15202b; }
}
:root[data-theme="dark"] { --ink:#e8e8e8; --muted:#9a9a9a; --line:#333; --bg:#111; --soft:#1a1a1a; --verdict:#15202b; }
.taste-banner { background: var(--soft); border: 1px dashed var(--line); color: var(--muted); font-size: 13px;
  padding: 8px 12px; margin: 0 auto 8px; max-width: 880px; }
"""
# 코멘트는 취향 문서의 재료다. 가장 쓸모 있는 코멘트는 「내가 쓴다면 이렇게 쓴다」는 고친 문장이다.
GUIDE = ("이 문장을 직접 쓴다면 어떻게 쓰시겠어요? 걸리는 문장을 드래그해 고쳐 쓴 문장을 코멘트로 남겨 주세요. "
         "태그는 선택입니다. [고침] 내가 쓸 문장 · [싫] 걸리는 이유 · [좋] 그대로 둘 것 · [규칙] 늘 지킬 원칙.")
HOWTO = "우측 상단의 코멘트 모드 버튼을 켜야 드래그로 입력창이 뜨고, claude.ai에서 연 페이지에서만 됩니다."
BANNER = f'<div class="taste-banner">{GUIDE}<br>{HOWTO}</div>'
# 태그 경계까지 본다. "<head" 만 찾으면 본문의 <header> 를 오인한다.
FORBIDDEN = tuple(re.compile(p, re.I) for p in (r"<!doctype", r"<html[\s>]", r"<head[\s>]", r"<body[\s>]", r"</body>", r"</html>"))


def _grab(pattern, html, what):
    m = re.search(pattern, html, re.S | re.I)
    if not m:
        sys.exit(f"{what} 를 찾지 못함")
    return m.group(1)


def convert(html):
    title = _grab(r"<title>(.*?)</title>", html, "<title>").strip()
    style = _grab(r"<style>(.*?)</style>", html, "<style>")
    body = _grab(r"<body[^>]*>(.*)</body>", html, "<body>").strip()
    style = style.replace("background: #fff;", "background: var(--bg);")
    out = f"<title>{title}</title>\n<style>{style}\n{DARK}</style>\n{BANNER}\n{body}\n"
    for bad in FORBIDDEN:
        if bad.search(out):
            sys.exit(f"금지 태그 잔존: {bad.pattern}")
    return out


def convert_md(md):
    """마크다운은 아티팩트가 그대로 렌더한다. 안내만 인용문으로 앞에 붙인다."""
    return f"> {GUIDE}\n>\n> {HOWTO}\n\n{md.lstrip(chr(0xFEFF))}"


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        sys.exit("usage: to_artifact.py in.html|in.md out.artifact.html|out.artifact.md")
    src, dst = Path(argv[0]), Path(argv[1])
    is_md = src.suffix.lower() in (".md", ".markdown")
    if is_md != (dst.suffix.lower() == ".md"):
        sys.exit("입력과 출력의 형식이 다르다. md 는 .artifact.md, html 은 .artifact.html 로 쓴다")
    text = src.read_text(encoding="utf-8")
    out = convert_md(text) if is_md else convert(text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8", newline="\n")   # Windows 에서 CRLF 로 바뀌지 않게
    print(f"written {dst} {len(out.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
