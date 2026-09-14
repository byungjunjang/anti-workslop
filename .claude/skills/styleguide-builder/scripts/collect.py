# -*- coding: utf-8 -*-
"""
collect.py — 한 저자의 글을 모아 corpus/ 를 만든다.

소스 (하나만):
  --sitemap URL      사이트맵(인덱스 포함)에서 글 URL 수집
  --rss URL          RSS <item><link> 에서 글 URL 수집
  --urls FILE        URL 목록 파일 (줄마다 하나)
  --md-dir DIR       로컬 .md/.txt 폴더 [--recursive]
출력:
  --kit DIR          키트 (corpus/ 위치와 noise_selectors 를 kit 에서 읽음)  또는  --out DIR

멱등:
  - corpus/urls.txt 가 있으면 사이트맵/RSS 를 다시 조회하지 않는다 (--discover 로 갱신)
  - corpus/html/<slug>.html 이 있으면 다시 내려받지 않는다 (--refresh 로 강제)
  - posts.json 은 항상 (발행일, slug) 순, 키 정렬. sources.json 에 fetch 시각을 넣지 않는다

옵션: --selector CSS (본문 컨테이너), --author NAME (다른 저자 글 제외), --include-pattern RE, --exclude-pattern RE,
      --since YYYY-MM-DD, --limit N, --sleep SEC (기본 1.0)
의존성: HTML 소스만 beautifulsoup4 (lxml 있으면 사용). --md-dir 은 표준 라이브러리만.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kitlib import dump_json_sorted, force_utf8_stdout, load_kit, sha256_file, sha256_text, write_text  # noqa: E402
from metrics import blocks_from_markdown  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (styleguide-builder collector)"}
CONTAINER_CHAIN = ["section.gh-content", ".post-content", ".entry-content", ".article-content", "article", "main"]
DEFAULT_NOISE = [".kg-bookmark-card", ".kg-card", ".kg-button-card", ".kg-callout-card", ".kg-signup-card", ".kg-cta-card"]


# ---------------------------------------------------------------------------
# 네트워크
# ---------------------------------------------------------------------------
def fetch(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _locs(xml: str) -> list[str]:
    return [u.strip() for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml)]


def discover_sitemap(url: str) -> list[str]:
    xml = fetch(url)
    if "<sitemapindex" in xml:
        urls = []
        for child in _locs(xml):
            try:
                urls += _locs(fetch(child))
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 하위 사이트맵 실패 {child}: {e}")
        return sorted(set(urls))
    return sorted(set(_locs(xml)))


def discover_rss(url: str) -> list[str]:
    xml = fetch(url)
    links = re.findall(r"<item>.*?<link>\s*([^<]+?)\s*</link>.*?</item>", xml, flags=re.S)
    if not links:
        links = re.findall(r"<entry>.*?<link[^>]*href=\"([^\"]+)\".*?</entry>", xml, flags=re.S)
    return sorted(set(l.strip() for l in links))


# ---------------------------------------------------------------------------
# HTML → 블록
# ---------------------------------------------------------------------------
def _parser() -> str:
    try:
        import lxml  # noqa: F401
        return "lxml"
    except ImportError:
        return "html.parser"


def _hangul_len(s: str) -> int:
    return sum(1 for ch in s if "가" <= ch <= "힣")


def pick_container(soup, selector: str | None):
    """본문 컨테이너 선택: 지정 selector → 관용 체인 → 한글 본문이 가장 많은 요소."""
    if selector:
        el = soup.select_one(selector)
        if el is not None:
            return el, f"selector:{selector}"
    for sel in CONTAINER_CHAIN:
        el = soup.select_one(sel)
        if el is not None and _hangul_len(el.get_text(" ")) >= 200:
            return el, f"chain:{sel}"
    best, best_score, best_size = None, 0, 10**9
    cands = soup.find_all(["article", "main", "section", "div"])
    scores = []
    for el in cands:
        score = 0
        for p in el.find_all("p"):
            if p.find_parent(["nav", "footer", "aside", "header"]):
                continue
            score += _hangul_len(p.get_text(" "))
        scores.append((score, el))
    if scores:
        mx = max(s for s, _ in scores)
        for score, el in scores:
            size = len(el.find_all())
            if score >= 0.9 * mx and size < best_size:
                best, best_score, best_size = el, score, size
    if best is None:
        best = soup.body or soup
        return best, "fallback:body"
    return best, "largest-hangul-block"


def _meta(soup, *selectors) -> str:
    for sel in selectors:
        el = soup.select_one(sel)
        if el is None:
            continue
        if el.name == "meta":
            v = el.get("content", "")
        else:
            v = el.get_text(" ", strip=True)
        if v:
            return v.strip()
    return ""


def extract_html(html: str, slug: str, url: str, selector: str | None, noise: list[str]) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, _parser())
    title = _meta(soup, "h1", 'meta[property="og:title"]', "title") or slug
    pub = _meta(soup, "time[datetime]", 'meta[property="article:published_time"]', 'meta[name="date"]')
    if soup.select_one("time[datetime]") is not None:
        pub = soup.select_one("time[datetime]").get("datetime", "")
    pub = pub[:10]
    author = _meta(soup, 'meta[name="author"]', 'meta[property="article:author"]', ".author-name", 'a[rel="author"]')
    tags = list(dict.fromkeys(a.get_text(strip=True) for a in soup.select('a[href*="/tag/"]')))
    excerpt = _meta(soup, ".article-excerpt", ".post-excerpt", 'meta[property="og:description"]')
    sec, strategy = pick_container(soup, selector)
    for tg in sec.find_all(["figure", "img", "script", "style", "iframe", "figcaption", "noscript", "nav", "footer"]):
        tg.decompose()
    for sel in noise:
        for tg in sec.select(sel):
            tg.decompose()
    blocks = []
    for el in sec.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote", "hr", "table"]):
        if el.name == "p" and el.find_parent(["blockquote", "li", "table"]):
            continue
        if el.name == "li" and el.find_parent(["table", "nav"]):
            continue
        if el.name == "hr":
            blocks.append({"tag": "hr", "text": "---"}); continue
        if el.name == "table":
            blocks.append({"tag": "table", "text": "[table]"}); continue
        txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()
        if txt:
            blocks.append({"tag": el.name, "text": txt})
    return {"slug": slug, "title": title, "pubDate": pub, "tags": tags, "excerpt": excerpt, "author": author,
            "url": url, "blocks": blocks, "container_strategy": strategy}


def slug_of(url: str) -> str:
    s = url.rstrip("/").split("/")[-1]
    s = re.sub(r"\.(html?|php)$", "", s)
    return re.sub(r"[^A-Za-z0-9가-힣._-]+", "-", s) or "post"


# ---------------------------------------------------------------------------
# 마크다운 폴더
# ---------------------------------------------------------------------------
def load_md_dir(d: Path, recursive: bool = False) -> list[dict]:
    files = sorted((d.rglob("*") if recursive else d.glob("*")))
    posts = []
    for f in files:
        if f.suffix.lower() not in (".md", ".txt") or not f.is_file():
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(d).with_suffix("")
        slug = "__".join(rel.parts)
        title, pub = rel.parts[-1], ""
        m = re.match(r"^---\n(.*?)\n---", raw, flags=re.S)
        if m:
            fm = m.group(1)
            t = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$", fm, flags=re.M)
            dt = re.search(r"^date:\s*[\"']?(\d{4}-\d{2}-\d{2})", fm, flags=re.M)
            if t: title = t.group(1)
            if dt: pub = dt.group(1)
        h1 = re.search(r"^#\s+(.+)$", raw, flags=re.M)
        if h1 and not m:
            title = h1.group(1).strip()
        if not pub:
            dm = re.search(r"(\d{4}-\d{2}-\d{2})", str(rel))
            pub = dm.group(1) if dm else ""
        blocks = blocks_from_markdown(raw)
        blocks = [b for b in blocks if not (b["tag"] == "h" and b["text"] == title and blocks.index(b) == 0)]
        posts.append({"slug": slug, "title": title, "pubDate": pub, "tags": [], "excerpt": "", "author": "",
                      "url": str(f), "blocks": blocks, "container_strategy": "markdown"})
    return posts


# ---------------------------------------------------------------------------
# 보일러플레이트 탐지 (보고만 하고 제거하지 않는다)
# ---------------------------------------------------------------------------
def detect_boilerplate(posts: list[dict]) -> dict:
    norm = lambda t: re.sub(r"\s+", " ", t).strip()
    seen: dict[str, set] = {}
    for p in posts:
        for b in p["blocks"]:
            if b["tag"] in ("p", "li", "h", "h2", "h3") and len(b["text"]) >= 20:
                seen.setdefault(norm(b["text"]), set()).add(p["slug"])
    n = len(posts)
    exact = {t: sorted(s) for t, s in seen.items() if len(s) >= 3 or (n and len(s) / n >= 0.3 and len(s) >= 2)}
    tail = {}
    for p in posts:
        idx_hr = [i for i, b in enumerate(p["blocks"]) if b["tag"] == "hr"]
        if idx_hr:
            last = idx_hr[-1]
            after = [i for i in range(last + 1, len(p["blocks"])) if p["blocks"][i]["tag"] != "hr"]
            if after and len(after) <= 6:
                tail[p["slug"]] = after
        for i, b in enumerate(p["blocks"]):
            flag = None
            if norm(b["text"]) in exact:
                flag = "exact"
            elif p["slug"] in tail and i in tail[p["slug"]]:
                flag = "tail"
            if flag:
                b["boilerplate"] = flag
            else:
                b.pop("boilerplate", None)
    return {"exact": [{"text": t, "slugs": s} for t, s in sorted(exact.items())], "tail": tail,
            "note": "블록은 코퍼스에 그대로 두었고 boilerplate 키로만 표시했다. 제외 여부는 analyze_corpus.py --exclude-boilerplate 로 정한다."}


# ---------------------------------------------------------------------------
def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--sitemap"); src.add_argument("--rss"); src.add_argument("--urls"); src.add_argument("--md-dir")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--kit"); ap.add_argument("--out")
    ap.add_argument("--selector"); ap.add_argument("--author")
    ap.add_argument("--include-pattern"); ap.add_argument("--exclude-pattern")
    ap.add_argument("--since"); ap.add_argument("--limit", type=int)
    ap.add_argument("--discover", action="store_true"); ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--sleep", type=float, default=1.0)
    a = ap.parse_args()

    noise = DEFAULT_NOISE
    if a.kit:
        kit = load_kit(a.kit)
        out = kit.corpus_dir
        noise = kit.profile().get("noise_selectors") or DEFAULT_NOISE
    elif a.out:
        out = Path(a.out).resolve()
    else:
        raise SystemExit("--kit 또는 --out 이 필요합니다.")
    out.mkdir(parents=True, exist_ok=True)

    if a.md_dir:
        posts = load_md_dir(Path(a.md_dir).resolve(), a.recursive)
        sources = {p["slug"]: {"path": p["url"], "strategy": "markdown"} for p in posts}
    else:
        urls_file = out / "urls.txt"
        if a.urls:
            urls = [u.strip() for u in Path(a.urls).read_text(encoding="utf-8").splitlines() if u.strip() and not u.startswith("#")]
            write_text(urls_file, "\n".join(urls) + "\n")
        elif a.discover or not urls_file.exists():
            if a.sitemap:
                urls = discover_sitemap(a.sitemap)
            elif a.rss:
                urls = discover_rss(a.rss)
            else:
                raise SystemExit("urls.txt 가 없고 --sitemap/--rss/--urls 도 없습니다.")
            write_text(urls_file, "\n".join(urls) + "\n")
            print(f"[discover] {len(urls)} urls -> {urls_file}")
        urls = [u.strip() for u in urls_file.read_text(encoding="utf-8").splitlines() if u.strip()]
        if a.include_pattern:
            urls = [u for u in urls if re.search(a.include_pattern, u)]
        if a.exclude_pattern:
            urls = [u for u in urls if not re.search(a.exclude_pattern, u)]
        html_dir = out / "html"; html_dir.mkdir(exist_ok=True)
        posts, sources, skipped = [], {}, []
        for i, url in enumerate(urls):
            slug = slug_of(url)
            cache = html_dir / f"{slug}.html"
            if a.refresh or not cache.exists():
                try:
                    html = fetch(url)
                except Exception as e:  # noqa: BLE001
                    print(f"[fail] {url}: {e}"); skipped.append({"url": url, "reason": str(e)}); continue
                cache.write_text(html, encoding="utf-8")
                print(f"[fetch] {slug}")
                if i < len(urls) - 1:
                    time.sleep(a.sleep)
            else:
                html = cache.read_text(encoding="utf-8")
            post = extract_html(html, slug, url, a.selector, noise)
            if a.author and post["author"] and a.author not in post["author"]:
                skipped.append({"url": url, "reason": f"author={post['author']}"}); continue
            if a.since and post["pubDate"] and post["pubDate"] < a.since:
                skipped.append({"url": url, "reason": f"before {a.since}"}); continue
            posts.append(post)
            sources[slug] = {"url": url, "html_sha256": sha256_text(html), "strategy": post["container_strategy"], "author": post["author"]}
        if skipped:
            dump_json_sorted(skipped, out / "skipped.json")
            print(f"[skip] {len(skipped)}건 → skipped.json")

    posts.sort(key=lambda p: (p["pubDate"], p["slug"]))
    if a.limit:
        posts = posts[: a.limit]
    boiler = detect_boilerplate(posts)
    dump_json_sorted(boiler, out / "boilerplate.json")
    posts_dir = out / "posts"; posts_dir.mkdir(exist_ok=True)
    for old in posts_dir.glob("*.md"):
        old.unlink()
    for p in posts:
        lines = [f"# {p['title']}", "", f"<!-- {p['pubDate']} | {', '.join(p['tags'])} | {p['slug']} -->", ""]
        if p["excerpt"]:
            lines += [f"> {p['excerpt']}", ""]
        for b in p["blocks"]:
            prefix = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "h": "## ", "li": "- ", "blockquote": "> ", "quote": "> "}.get(b["tag"], "")
            if b["tag"] == "table":
                continue
            lines += [prefix + b["text"], ""]
        write_text(posts_dir / f"{p['slug']}.md", "\n".join(lines).rstrip() + "\n")
    dump_json_sorted(posts, out / "posts.json")
    digest = sha256_file(out / "posts.json")
    write_text(out / "posts.sha256", digest + "\n")
    dump_json_sorted(sources, out / "sources.json")
    n_chars = sum(len(b["text"]) for p in posts for b in p["blocks"] if b["tag"] == "p")
    strategies = sorted(set(p["container_strategy"] for p in posts))
    print(f"[done] {len(posts)} posts, {n_chars} body chars, sha256={digest[:12]}, strategies={strategies}, "
          f"boilerplate exact={len(boiler['exact'])} tail={len(boiler['tail'])}")
    if len(posts) < 5:
        print("[warn] 글이 5편 미만입니다. envelope 기반 목표치가 불안정하므로 derive_targets.py 가 여유를 넓힙니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
