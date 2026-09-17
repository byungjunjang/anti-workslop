# -*- coding: utf-8 -*-
"""taste-builder 인수 테스트. pytest 없이 실행: python tests/run_acceptance.py"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
FIX = HERE / "fixtures"
TMP = HERE / ".tmp"
PY = sys.executable


def run(*args):
    p = subprocess.run([PY, *map(str, args)], capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def reset_tmp():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir()


def test_ingest_new_and_dup():
    reset_tmp()
    ledger = TMP / "cases.jsonl"
    code, out, err = run(SCRIPTS / "ingest_comments.py", "--raw", FIX / "comments.sample.json", "--ledger", ledger)
    assert code == 0, err
    assert out == "new=5 dup=0 ids=T-0001..T-0005", out
    cases = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    assert [c["case_id"] for c in cases] == ["T-0001", "T-0002", "T-0003", "T-0004", "T-0005"]
    assert cases[0]["kind"] == "지적" and cases[0]["kind_source"] == "tagged"
    assert cases[1]["kind"] == "규칙"
    assert cases[2]["kind"] == "고침" and cases[2]["rewrite"] == "숫자가 없습니다."
    assert cases[3]["kind"] == "칭찬" and cases[3]["kind_source"] == "inferred"
    assert cases[4]["kind"] == "미분류" and cases[4]["doc"]["section"] == "전체"
    assert cases[0]["comment"] == ["[싫] 대구가 너무 자주 나와요"]  # 원문 보존
    assert cases[0]["status"] == "신규" and cases[0]["rule_ids"] == []
    code, out, _ = run(SCRIPTS / "ingest_comments.py", "--raw", FIX / "comments.sample.json", "--ledger", ledger)
    assert out == "new=0 dup=5 ids=-", out
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 5
    print("PASS test_ingest_new_and_dup")


def test_ingest_chat_origin():
    """대화에서 나온 취향 신호도 같은 원장에 쌓인다. 아티팩트 URL 대신 source_ref 가 중복 제거 키다."""
    TMP.mkdir(exist_ok=True)
    ledger = TMP / "chat-cases.jsonl"      # 앞 테스트의 원장을 건드리지 않는다
    code, out, err = run(SCRIPTS / "ingest_comments.py", "--raw", FIX / "chat.sample.json", "--ledger", ledger)
    assert code == 0, err
    assert out == "new=2 dup=0 ids=T-0001..T-0002", out
    cases = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()]
    assert [c["origin"] for c in cases] == ["chat", "chat"], cases
    assert cases[0]["source"]["source_ref"].startswith("대화 2026-09-16"), cases[0]["source"]
    assert cases[0]["source"]["artifact_url"] == "" and cases[0]["kind"] == "규칙"
    assert cases[0]["comment"] == ["[규칙] 개요 상자에 계기·범위는 넣지 않는다"]   # 원문 보존
    assert cases[1]["kind"] == "칭찬" and cases[1]["doc"]["section"] == "전체"
    code, out, _ = run(SCRIPTS / "ingest_comments.py", "--raw", FIX / "chat.sample.json", "--ledger", ledger)
    assert out == "new=0 dup=2 ids=-", out
    code, out, err = run(SCRIPTS / "ingest_comments.py", "--raw", FIX / "comments.sample.json", "--ledger", ledger)
    assert code == 0 and out == "new=5 dup=0 ids=T-0003..T-0007", out    # 아티팩트 경로는 그대로
    arts = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()][2:]
    assert {c["origin"] for c in arts} == {"artifact"}, arts
    print("PASS test_ingest_chat_origin")


def test_map():
    ledger = TMP / "cases.jsonl"
    code, out, err = run(SCRIPTS / "ingest_comments.py", "--map", "T-0001=W-01", "T-0002=W-01", "T-0003=W-02",
                         "--status", "반영", "--ledger", ledger)
    assert code == 0, err
    assert out == "mapped=3", out
    cases = {json.loads(l)["case_id"]: json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()}
    assert cases["T-0001"]["rule_ids"] == ["W-01"] and cases["T-0001"]["status"] == "반영"
    assert cases["T-0004"]["status"] == "신규"
    code, out, err = run(SCRIPTS / "ingest_comments.py", "--map", "T-0099=W-01", "--ledger", ledger)
    assert code == 1 and "T-0099" in err
    print("PASS test_map")


def test_validate_pass_and_fail():
    ledger = TMP / "cases.jsonl"  # test_map 이후 상태: T-0001,T-0002→W-01, T-0003→W-02, 나머지 신규
    code, out, err = run(SCRIPTS / "validate_taste.py", "--doc", FIX / "writing-taste.sample.md", "--ledger", ledger)
    assert code == 0, err
    assert out == "OK rules=2 cases=5", out
    code, out, err = run(SCRIPTS / "validate_taste.py", "--doc", FIX / "writing-taste.broken.md", "--ledger", ledger)
    assert code == 1
    assert "T-0099" in err and "n=" in err and "W-01" in err, err
    for e in ("E10", "E11", "E12"):
        assert e in err, (e, err)
    print("PASS test_validate_pass_and_fail")


def test_to_artifact():
    src = TMP / "report.min.html"
    src.write_text(
        '<!DOCTYPE html>\n<html lang="ko"><head><meta charset="utf-8"><title>샘플 리포트</title>\n'
        '<style>:root{--bg:#fff;--ink:#111;} body{background:var(--bg);} .reco{background: #fff;}</style></head>\n'
        '<body><div class="wrap"><header><h1>제목</h1></header><p>본문</p></div></body></html>\n', encoding="utf-8")
    out = TMP / "report.artifact.html"
    code, stdout, err = run(SCRIPTS / "to_artifact.py", src, out)
    assert code == 0, err
    html = out.read_text(encoding="utf-8")
    import re as _re
    for bad in (r"<!doctype", r"<html[\s>]", r"<head[\s>]", r"<body[\s>]", r"</body>", r"</html>"):
        assert not _re.search(bad, html, _re.I), bad
    assert html.startswith("<title>샘플 리포트</title>")
    assert "prefers-color-scheme: dark" in html and ':root[data-theme="dark"]' in html
    assert "background: var(--bg);" in html and "background: #fff;" not in html
    assert 'class="taste-banner"' in html and "[고침]" in html
    assert '<div class="wrap"><header><h1>제목</h1></header><p>본문</p></div>' in html  # <header> 는 살아남아야 한다
    assert "직접 쓴다면" in html and "\r\n" not in out.read_bytes().decode("utf-8")   # 코멘트 요청은 「내가 쓴다면」
    # AI 산출물은 md 인 경우가 많다. 본문은 그대로 두고 안내만 인용문으로 앞에 붙인다.
    md_src = TMP / "draft.md"
    md_src.write_text("# 제목\n\n본문 문장입니다.\n", encoding="utf-8", newline="\n")
    md_out = TMP / "draft.artifact.md"
    code, _, err = run(SCRIPTS / "to_artifact.py", md_src, md_out)
    assert code == 0, err
    md = md_out.read_text(encoding="utf-8")
    assert md.startswith("> 이 문장을 직접 쓴다면") and "[고침]" in md and md.endswith("# 제목\n\n본문 문장입니다.\n"), md
    code, _, err = run(SCRIPTS / "to_artifact.py", md_src, TMP / "draft.artifact.html")
    assert code != 0 and "형식이 다르다" in err, err
    print("PASS test_to_artifact")


def test_default_ledger():
    """--ledger 없이 부르면 두 스크립트 모두 프로젝트 루트의 taste/cases/cases.jsonl 을 읽어야 한다.
    parents[3] 은 .claude/ 라서 validate 는 모든 케이스가 E2·E9 로 떴고(SKILL.md Step 6), ingest 는 .claude/taste/ 에
    새 원장을 만들어 T-0001 부터 다시 매겼다(2026-09-11 두 번째 collect). SKILL.md Step 3·5·6 이 --ledger 없이 부른다.
    원장 파일의 존재는 보지 않는다. 처음 쓰는 사람에게는 아직 없다."""
    sys.path.insert(0, str(SCRIPTS))
    import ingest_comments
    import init_taste
    import validate_taste
    root = SKILL.parents[2]
    for mod in (ingest_comments, validate_taste, init_taste):
        assert mod.PROJECT_ROOT == root, (mod.__name__, mod.PROJECT_ROOT, root)
    for mod in (ingest_comments, validate_taste):
        assert Path(mod.DEFAULT_LEDGER) == root / "taste" / "cases" / "cases.jsonl", mod.__name__
    assert not (root / ".claude" / "taste").exists(), "잘못된 경로에 원장이 생겼다"
    print("PASS test_default_ledger")


def test_init_taste():
    """처음 쓰는 사람은 빈 취향 폴더에서 시작한다. 없는 파일만 만들고, 다시 돌리면 건드리지 않는다.
    만든 문서는 빈 원장과 함께 validate 를 통과해야 collect 첫 회차가 막히지 않는다."""
    root = TMP / "fresh"
    if root.exists():
        shutil.rmtree(root)
    code, out, err = run(SCRIPTS / "init_taste.py", "--root", root, "--date", "2026-09-14")
    assert code == 0, err
    assert out.count("[created]") == 4 and "[skip]" not in out, out
    doc = root / "taste" / "writing-taste.md"
    text = doc.read_bytes().decode("utf-8")
    assert "{{DATE}}" not in text and "갱신: 2026-09-14" in text and "\r\n" not in text, text[:200]
    assert json.loads((root / "taste" / "artifacts.json").read_text(encoding="utf-8")) == []
    assert (root / "taste" / "cases" / "raw" / ".gitkeep").exists()
    assert "| 날짜 | 스냅샷 |" in (root / "taste" / "changelog.md").read_text(encoding="utf-8")
    doc.write_text(text + "\n", encoding="utf-8", newline="\n")          # 사용자가 고친 문서는 다시 돌려도 그대로다
    code, out, _ = run(SCRIPTS / "init_taste.py", "--root", root)
    assert out.count("[skip]") == 4 and doc.read_text(encoding="utf-8") == text + "\n", out
    code, out, err = run(SCRIPTS / "validate_taste.py", "--doc", doc, "--ledger", root / "taste" / "cases" / "cases.jsonl")
    assert code == 0 and out == "OK rules=0 cases=0", (out, err)
    print("PASS test_init_taste")


def test_validate_missing_doc():
    """취향 문서가 없으면 traceback 이 아니라 E0 한 줄과 만드는 방법을 낸다."""
    code, out, err = run(SCRIPTS / "validate_taste.py", "--doc", TMP / "none.md", "--ledger", TMP / "none.jsonl")
    assert code == 1 and err.startswith("E0 취향 문서 없음") and "init_taste.py" in err and "Traceback" not in err, err
    print("PASS test_validate_missing_doc")


def test_skill_docs():
    skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert skill_md.startswith("---\nname: taste-builder\n"), skill_md[:60]
    assert "description:" in skill_md.splitlines()[2]
    for h in ("## Step 1", "collect", "publish", "anti-workslop", "ingest_comments.py", "validate_taste.py", "to_artifact.py", "artifacts.json"):
        assert h in skill_md, h
    for f in ("case-schema.md", "distill-guide.md", "taste-template.md"):
        assert (SKILL / "references" / f).exists(), f
    for f in ("distill-guide.md", "taste-template.md"):
        assert "검출" in (SKILL / "references" / f).read_text(encoding="utf-8"), f
    print("PASS test_skill_docs")


if __name__ == "__main__":
    test_ingest_new_and_dup()
    test_map()
    test_ingest_chat_origin()
    test_validate_pass_and_fail()
    test_to_artifact()
    test_default_ledger()
    test_init_taste()
    test_validate_missing_doc()
    test_skill_docs()
    print("ALL PASS")
