# -*- coding: utf-8 -*-
"""fetch_sources.py — corpus/sources.json 에 적힌 참고 문헌을 다시 내려받아 corpus/text/ 에 텍스트로 추출한다.

사용법:
    python -X utf8 fetch_sources.py            # 자동 수집 가능한 항목만 내려받고 텍스트 추출
    python -X utf8 fetch_sources.py --verify   # 내려받은 파일의 sha256 을 corpus/raw_hashes.json 과 대조 (텍스트는 건드리지 않음)
    python -X utf8 fetch_sources.py --only nabo_focus_082

의존성: PyMuPDF(fitz). 없으면 `pip install pymupdf`.
자동 수집이 막힌 항목(access != "auto")은 sources.json 의 "manual" 안내대로 사람이 내려받아
corpus/raw/ 에 두면 이 스크립트가 텍스트만 추출한다.
"""
import argparse, hashlib, json, os, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 키트 루트 (scripts/ 의 부모)
RAW = os.path.join(HERE, "corpus", "raw")
TEXT = os.path.join(HERE, "corpus", "text")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def download(url, dest, referer=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **({"Referer": referer} if referer else {})})
    data = urllib.request.urlopen(req, timeout=60).read()
    open(dest, "wb").write(data)
    return data


def page_filter(pages):
    """sources.json 의 pages 가 정수 목록이면 그 쪽만 추출한다. '4쪽' 같은 설명 문자열은 필터가 아니다(전체 추출).
    (원래 코드는 문자열도 set() 으로 감싸 모든 쪽을 건너뛰어 빈 텍스트를 만들었다 — 82호 텍스트가 비어 있던 원인.)"""
    if isinstance(pages, list) and all(isinstance(x, int) for x in pages) and pages:
        return set(pages)
    return None


def is_pdf(path):
    return open(path, "rb").read(5) == b"%PDF-"


def pdf_to_text(path, out, pages=None):
    import fitz
    doc = fitz.open(path)
    parts = []
    for i, p in enumerate(doc):
        if pages and (i + 1) not in pages:
            continue
        parts.append(f"\n<<<PAGE {i + 1}>>>\n" + p.get_text("text"))
    open(out, "w", encoding="utf-8").write("".join(parts))
    return len(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    src = json.load(open(os.path.join(HERE, "corpus", "sources.json"), encoding="utf-8"))
    hashes = json.load(open(os.path.join(HERE, "corpus", "raw_hashes.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "corpus", "raw_hashes.json")) else {}
    os.makedirs(RAW, exist_ok=True); os.makedirs(TEXT, exist_ok=True)
    for s in src["sources"]:
        sid = s["id"]
        if a.only and sid != a.only:
            continue
        raw = os.path.join(RAW, s.get("raw_file", sid + ".pdf")) if s.get("raw_file") else None
        if s["access"] == "auto" and s.get("download_url") and raw:
            if not os.path.exists(raw):
                try:
                    print(f"[get] {sid} <- {s['download_url']}")
                    download(s["download_url"], raw, s.get("referer"))
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[fail] {sid}: {e}"); continue
            if raw.endswith(".pdf") and not is_pdf(raw):
                print(f"[warn] {sid}: PDF가 아니다(차단 페이지일 수 있음). 파일을 지우고 브라우저로 받아 corpus/raw/ 에 둔다.")
                continue
            if a.verify and sid in hashes:
                d = hashlib.sha256(open(raw, "rb").read()).hexdigest()
                print(f"[{'ok' if d == hashes[sid]['sha256'] else 'CHANGED'}] {sid} sha256={d[:16]}")
            if raw.endswith(".pdf") and s.get("text_file") and not a.verify:  # --verify 는 해시만 대조하고 텍스트를 덮어쓰지 않는다
                n = pdf_to_text(raw, os.path.join(TEXT, s["text_file"]), page_filter(s.get("pages")))
                print(f"[text] {sid}: {n} pages -> {s['text_file']}")
        elif s["access"] == "auto" and s.get("download_url") and s.get("text_file") and (s.get("download_kind") == "text" or s["download_url"].endswith((".md", ".txt"))):
            out = os.path.join(TEXT, s["text_file"])
            if not os.path.exists(out):
                download(s["download_url"], out); print(f"[text] {sid} -> {s['text_file']}")
            else:
                print(f"[skip] {sid}: 이미 있음 -> {s['text_file']}")
        else:
            if raw and os.path.exists(raw) and raw.endswith(".pdf") and s.get("text_file") and not a.verify:
                n = pdf_to_text(raw, os.path.join(TEXT, s["text_file"]), page_filter(s.get("pages")))
                print(f"[text] {sid}: {n} pages -> {s['text_file']} (수동 확보본)")
            else:
                print(f"[manual] {sid}: {s.get('manual', '수동 확보 필요')}")
    print("done. 다음: python -X utf8 parse_ko.py && python -X utf8 analyze_corpus.py")


if __name__ == "__main__":
    main()
