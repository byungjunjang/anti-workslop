#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""산출물 → claude.ai 코멘트용 아티팩트 파일.
HTML · 아티팩트는 <!DOCTYPE>/<html>/<head>/<body> 를 자체 공급하므로 <title>·<style>·본문만 남기고,
       다크 테마 토큰과 코멘트 안내 배너를 붙인다.
MD   · 본문은 그대로 두고 맨 위에 같은 안내를 인용문으로 붙인다.

  python to_artifact.py in.html out.artifact.html
  python to_artifact.py in.md   out.artifact.md
  python to_artifact.py --local in.html out.review.html  # 원본과 같은 폴더
"""
import argparse
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
LOCAL_GUIDE = ("이 문장을 직접 쓴다면 어떻게 쓰시겠어요? 원문 문장과 고쳐 쓸 문장 또는 이유를 대화에 보내 주세요. "
               "태그는 선택입니다. [고침] 내가 쓸 문장 · [싫] 걸리는 이유 · [좋] 그대로 둘 것 · [규칙] 늘 지킬 원칙.")
LOCAL_HOWTO = "로컬 검토 파일입니다. 이 파일에는 코멘트 입력·저장 기능이 없습니다."
LOCAL_BANNER = f'<div class="taste-banner">{LOCAL_GUIDE}<br>{LOCAL_HOWTO}</div>'
LOCAL_STYLE = """<style>
.taste-banner { background: #f5f5f5; border: 1px dashed #aaa; color: #333;
  font: 13px/1.6 sans-serif; padding: 8px 12px; margin: 8px auto; max-width: 880px; }
</style>"""
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


def convert_local(html):
    """로컬 HTML은 문서 외곽·속성·리소스를 유지하고 안내만 추가한다."""
    head = re.search(r"</head\s*>", html, re.I)
    body = re.search(r"<body\b[^>]*>", html, re.I)
    if not head or not body:
        sys.exit("로컬 HTML에는 <head>와 <body>가 필요합니다")
    # 삽입 위치를 원문 기준으로 고정해 본문이나 기존 스타일을 재직렬화하지 않는다.
    for offset, addition in sorted(((head.start(), LOCAL_STYLE), (body.end(), LOCAL_BANNER)), reverse=True):
        html = html[:offset] + addition + html[offset:]
    return html


def convert_md(md, local=False):
    """마크다운은 아티팩트가 그대로 렌더한다. 안내만 인용문으로 앞에 붙인다."""
    guide, howto = (LOCAL_GUIDE, LOCAL_HOWTO) if local else (GUIDE, HOWTO)
    return f"> {guide}\n>\n> {howto}\n\n{md.lstrip(chr(0xFEFF))}"


def main(argv=None):
    parser = argparse.ArgumentParser(description="코멘트용 아티팩트 또는 로컬 검토 파일 생성")
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--local", action="store_true", help="대화로 피드백을 받는 로컬 검토 파일")
    args = parser.parse_args(argv)
    src, dst = args.src, args.dst
    if src.resolve() == dst.resolve() or (dst.exists() and src.samefile(dst)):
        sys.exit("원본과 출력 경로가 같다. 원본은 덮어쓰지 않는다")
    is_md = src.suffix.lower() in (".md", ".markdown")
    if is_md != (dst.suffix.lower() == ".md"):
        sys.exit("입력과 출력의 형식이 다르다. md 는 .artifact.md, html 은 .artifact.html 로 쓴다")
    text = src.read_text(encoding="utf-8")
    out = convert_md(text, local=args.local) if is_md else (convert_local(text) if args.local else convert(text))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8", newline="\n")   # Windows 에서 CRLF 로 바뀌지 않게
    print(f"written {dst} {len(out.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
