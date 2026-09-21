# -*- coding: utf-8 -*-
"""anti-workslop 인수 테스트. python tests/run_acceptance.py — 가이드라인 경로·검사 스크립트 존재, SKILL.md 형식."""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
ROOT = SKILL.parents[2]  # anti-workslop 프로젝트 루트

CHECK = ".claude/skills/anti-workslop/scripts/check_ai_tells.py"
FIX = ".claude/skills/anti-workslop/tests/fixtures"
FID = ".claude/skills/anti-workslop/scripts/check_fidelity.py"
PRINCIPLES = ROOT / "principles"
BRIEF = SKILL / "references" / "subagent.md"
SKILL_DOCS = (SKILL / "SKILL.md", SKILL / "references" / "modes.md", BRIEF, PRINCIPLES / "invariants.md")


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-X", "utf8", *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd or ROOT)


def test_skill_doc():
    md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert md.startswith("---\nname: anti-workslop\n"), md[:60]
    assert "description:" in md.splitlines()[2]
    assert len(md.splitlines()) <= 150, len(md.splitlines())
    for h in ("## Step 1", "## Step 5", "애매하면", "taste-builder", "base-guidelines.json",
              "## 모드", "불변식", "재작성본", "두 문장", "기권", "수정 없음", "뺀 것",
              "check_all", "check_fidelity", "references/modes.md", "principles/invariants.md", "principles/ai-tells-ko.md",
              "references/subagent.md", "스타일가이드", "우선권", "## Step 2. 서브에이전트", "## Step 3. 검수", "## Step 4. notes",
              "사람이 판단할 것", "전달 파일", "--hint", "--bundle", "작업 기록", "--taste-skip",
              "SendMessage", "불변식 셋", "자기 대조"):
        assert h in md, h
    assert "## Step 3. 재작성" not in md and "읽는 것 다섯" not in md, "재작성 절은 브리프로 옮겼다"
    assert "references/ai-tells-ko.md" not in md and "references/invariants.md" not in md
    for bad in ("계약", "게이트"):
        for p in SKILL_DOCS:
            assert bad not in p.read_text(encoding="utf-8"), (bad, p.name)
    print("PASS test_skill_doc")


def test_modes_doc():
    md = (SKILL / "references" / "modes.md").read_text(encoding="utf-8")
    assert "취향 0건, 가이드 hard 1건, 원칙 S1 2건, 사람 판단 3건" in md
    assert "Step 2" in md and "표시 규칙" in md
    assert "## 범위 질문" not in md and "## 윤문 뒤" in md, "범위 질문은 2026-09-17 에 없앴다"
    assert "작성자 확인" in md and "③ 사람이 판단할 것의 반영" not in md, "윤문 뒤 절이 옛 ③ 반영 절차다"
    assert "뼈대 출처" in md and "템플릿" in md, "구조 진단표에 뼈대 출처 칸이 없다"
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "문장만" not in skill and "뼈대까지" not in skill, "SKILL.md 에 범위 질문이 남아 있다"
    cases = (SKILL / "tests" / "evals" / "cases.md").read_text(encoding="utf-8")
    assert "11-diagnose-isolation" in cases and "12-review-layer-counts" in cases
    assert "17-no-scope-question" in cases and "18-skeleton-template" in cases
    print("PASS test_modes_doc")


def test_base_guidelines_common():
    bg = json.loads((SKILL / "references" / "base-guidelines.json").read_text(encoding="utf-8"))
    for k, cmd in bg["_checks_common"].items():
        script = re.search(r"(\S+\.py)", cmd).group(1)
        assert (ROOT / script).exists(), (k, script)
        assert "{file}" in cmd, k
    assert "{orig}" in bg["_checks_common"]["fidelity"] and "{genre}" in bg["_checks_common"]["ai_tells"]
    assert "check_taste.py" in bg["_checks_common"]["taste"], bg["_checks_common"]
    assert bg["_check_order"] == ["genre", "ai_tells", "taste", "fidelity"]
    # 가이드는 기본 둘 + 사용자가 register_guide.py 로 등록한 것. 표마다 등록된 이름이 빠짐없이 있어야 한다.
    names = [k for k in bg if not k.startswith("_")]
    assert bg["_builtin"] == ["장피엠", "개조식"] and set(bg["_builtin"]) <= set(names), bg.get("_builtin")
    assert {k: bg["_genre_of"][k] for k in bg["_builtin"]} == {"장피엠": "줄글", "개조식": "개조식"}
    assert {k: bg["_checker_kind"][k] for k in bg["_builtin"]} == {"장피엠": "style", "개조식": "report"}
    for table in ("_genre_of", "_checker_kind", "_checks", "_checks_short", "_pack_sections", "_s14_blocks"):
        assert set(bg[table]) == set(names), (table, set(bg[table]) ^ set(names))
    assert set(bg["_checker_kind"].values()) <= {"style", "report"}, bg["_checker_kind"]
    # 짧은 줄글(공백 제외 800자 이하)은 비율·불리언 규칙을 빼고 센다. 개조식은 짧은 글 구분이 없다(1쪽≈900자가 표준 분량).
    assert "--subset counts" in bg["_checks_short"]["장피엠"]["md"], bg["_checks_short"]
    assert bg["_checks_short"]["개조식"]["md"] == bg["_checks"]["개조식"]["md"]
    assert bg["_short_chars"] == 800
    assert "check_all.py" in bg["_check_all"] and "{guide}" in bg["_check_all"] and "{orig}" in bg["_check_all"], bg.get("_check_all")
    for s in ("check_all", "--bundle", "--hint"):
        assert s in (SKILL / "SKILL.md").read_text(encoding="utf-8"), s
    assert "--bundle" in BRIEF.read_text(encoding="utf-8")
    assert bg["_pack_sections"]["장피엠"] == ["8", "11-2", "14"] and "11-3" in bg["_pack_sections"]["개조식"], bg["_pack_sections"]
    assert "AI 티" in bg["_s14_blocks"]["장피엠"] and "표기" in bg["_s14_blocks"]["개조식"], bg["_s14_blocks"]
    for p in (SKILL / "references" / "modes.md", BRIEF,
              PRINCIPLES / "invariants.md", PRINCIPLES / "ai-tells-ko.md",
              SKILL / "tests" / "evals" / "cases.md"):
        assert p.exists(), p
    for gone in ("ai-tells-ko.md", "invariants.md", "diagnose.md"):
        assert not (SKILL / "references" / gone).exists(), gone
    cases = (SKILL / "tests" / "evals" / "cases.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^\| \d\d-", cases, re.M)) >= 6 and cases.count("should-abstain") >= 2
    for f in ("timeline.md", "explore-memo.md", "quoted-law.md"):      # 수동 eval 06·09·10 입력
        assert (SKILL / "tests" / "fixtures" / f).exists(), f
        assert f"`{f}`" in cases, f
    print("PASS test_base_guidelines_common")


def test_skill_docs_no_s3():
    r = run(CHECK, "--genre", "all", "--json",
            ".claude/skills/anti-workslop/SKILL.md", ".claude/skills/anti-workslop/references/modes.md",
            ".claude/skills/anti-workslop/references/subagent.md", "principles/invariants.md")
    for d in json.loads(r.stdout):
        assert d["summary"]["total"] == 0, (d["file"], d["findings"][:3])
    print("PASS test_skill_docs_no_s3")


def test_base_guidelines_resolve():
    bg = json.loads((SKILL / "references" / "base-guidelines.json").read_text(encoding="utf-8"))
    assert set(bg) >= {"장피엠", "개조식"}
    for k, cands in bg.items():
        if k.startswith("_"):
            continue
        assert isinstance(cands, list) and any((ROOT / c).exists() for c in cands), (k, cands)
    for k, by_ext in bg["_checks"].items():
        for ext, cmd in by_ext.items():
            script = re.search(r"(\S+\.py)", cmd).group(1)
            assert (ROOT / script).exists(), (k, ext, script)
    print("PASS test_base_guidelines_resolve")


def test_ai_tells_table_shape():
    """규칙표·설명표 행 수 == 머리의 '규칙 수', ID 유일, 두 표 ID 집합 동일, regex 컴파일, \\b 없음."""
    import re
    md = (PRINCIPLES / "ai-tells-ko.md").read_text(encoding="utf-8")
    declared = int(re.search(r"^규칙 수: (\d+)$", md, re.M).group(1))

    def rows(section_heading):
        body = md.split(section_heading, 1)[1]
        out = []
        for line in body.splitlines()[1:]:
            if line.startswith("## "):
                break
            if line.startswith("| AT-"):
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
                out.append(cells)
        return out

    rules = rows("## 2. 규칙표")
    notes = rows("## 3. 설명표")
    assert len(rules) == declared, (len(rules), declared)
    ids = [r[0] for r in rules]
    assert len(ids) == len(set(ids)), "중복 ID"
    assert set(ids) == {n[0] for n in notes}, set(ids) ^ {n[0] for n in notes}
    for r in rules:
        rid, _, _, sev, det, scope, genre, pat, exc, thr = r[:10]
        assert sev in ("S1", "S2", "S3"), rid
        assert det in ("regex", "literal", "density", "structure", "human", "위임"), rid
        assert genre in ("공통", "줄글", "개조식"), rid
        assert set(scope.split(",")) <= {"prose", "list", "heading", "table"}, rid
        if det in ("regex", "density", "structure") and pat.startswith("`"):
            src = pat.strip("`").replace("\\|", "|")
            if det == "structure":
                src = src.split(" :: ", 1)[1] if " :: " in src else ""
            assert "\\b" not in src, rid
            if src:
                re.compile(src, re.M)
        if exc.startswith("`"):
            re.compile(exc.strip("`").replace("\\|", "|"))
        if det in ("density", "structure") and sev in ("S2", "S3"):
            assert thr, ("임계값 필수", rid)
    print("PASS test_ai_tells_table_shape")


def test_ai_tells_selftest():
    r = run(CHECK, "--selftest")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "규칙 67" in r.stdout, r.stdout
    print("PASS test_ai_tells_selftest")


def test_ai_tells_list_handshake():
    r = run(CHECK, "--list", "--genre", "줄글")
    first = r.stdout.splitlines()[0]
    assert first.startswith("ai-tells-ko 2026-09-17 · 규칙 67 ("), first
    assert "활성" in first and "--genre 줄글" in first, first
    assert r.returncode == 0
    print("PASS test_ai_tells_list_handshake")


def test_ai_tells_loader_rejects():
    """예외 셀 정규식에 \\b 를 넣은 사본은 로더가 거부한다(패턴 셀과 같은 대우)."""
    md = (PRINCIPLES / "ai-tells-ko.md").read_text(encoding="utf-8")
    old = r"`\d[:：]\d`"                # AT-19 예외 셀
    assert md.count(old) == 1, md.count(old)
    with tempfile.TemporaryDirectory() as d:
        broken = Path(d) / "ai-tells-ko.md"
        broken.write_text(md.replace(old, r"`\b\d[:：]\d`"), encoding="utf-8")
        r = run(CHECK, "--selftest", "--rules", str(broken))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "AT-19: 예외 정규식에 \\b 금지" in r.stderr, r.stdout + r.stderr
    print("PASS test_ai_tells_loader_rejects")


def test_ai_tells_exemptions():
    r = run(CHECK, "--genre", "줄글", "--json", f"{FIX}/exempt-sample.md")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    rules = [f["rule"] for f in d["findings"]]
    assert rules == ["AT-16"], rules          # 일반 표 셀의 대화 잔재만 잡힌다
    assert d["findings"][0]["line"] == 18, d["findings"][0]
    print("PASS test_ai_tells_exemptions")


def test_ai_tells_borrowed_controls():
    a = run(CHECK, "--genre", "줄글", "--strict", "--json", ".claude/skills/styleguide-builder/assets/samples/ai_draft.md")
    b = run(CHECK, "--genre", "개조식", "--strict", "--json", "styleguides/report/samples/bad_draft.md")
    assert a.returncode == 1 and b.returncode == 1, (a.returncode, b.returncode, a.stderr, b.stderr)
    for r in (a, b):
        d = json.loads(r.stdout)
        assert d["summary"]["strict_fail"] is True
        assert d["summary"]["by_severity"]["S1"] + d["summary"]["by_severity"]["S2"] >= 1
    print("PASS test_ai_tells_borrowed_controls")


def test_ai_tells_json_envelope():
    r = run(CHECK, "--genre", "줄글", "--json", ".claude/skills/styleguide-builder/assets/samples/ai_draft.md")
    d = json.loads(r.stdout)
    for k in ("tool", "rules_version", "genre", "rules_loaded", "rules_active", "file", "findings", "summary", "stats"):
        assert k in d, k
    assert d["rules_loaded"] == 67
    for f in d["findings"]:
        for k in ("rule", "severity", "line", "col", "excerpt", "detail"):
            assert k in f, (k, f)
    assert set(d["summary"]["skipped"]["human"]) == {"AT-24", "AT-25", "AT-33", "AT-60", "AT-61", "AT-65", "AT-66"}
    assert set(d["summary"]["skipped"]["위임"]) == {"AT-40", "AT-41", "AT-42"}
    print("PASS test_ai_tells_json_envelope")


def test_ai_tells_html_offsets():
    """segment_html 의 블랭킹이 길이를 보존해 행·열이 원문 자리와 같고, 발췌가 원문의 부분 문자열이다."""
    src = (SKILL / "tests" / "fixtures" / "html-sample.html").read_text(encoding="utf-8")
    r = run(CHECK, "--genre", "줄글", "--json", f"{FIX}/html-sample.html")
    assert r.returncode == 0, r.stderr
    d = json.loads(r.stdout)
    f = next(x for x in d["findings"] if x["rule"] == "AT-16")
    off = src.index("더 필요하시면")
    line = src[:off].count("\n") + 1
    col = off - (src.rfind("\n", 0, off) + 1) + 1
    assert (f["line"], f["col"]) == (line, col), (f, line, col)
    assert f["excerpt"] in src, f["excerpt"]
    # <code>·<table> 안의 '결론적으로'는 블랭킹되어 AT-07 이 뜨지 않는다
    assert d["summary"]["by_rule"].get("AT-07", 0) == 0, d["findings"]
    print("PASS test_ai_tells_html_offsets")


def test_ai_tells_html_nesting():
    """중첩 목록. 상위 li 는 하위 목록 앞뒤 텍스트를 모두 담고 하위 li 를 삼키지 않는다.
    <!-- style-exempt --> 바로 다음 요소는 안쪽까지 exempt 라 원칙 검사기가 세지 않는다."""
    sys.path.insert(0, str(SKILL / "scripts"))
    from check_ai_tells import segment_html
    src = (SKILL / "tests" / "fixtures" / "html-nested.html").read_text(encoding="utf-8")
    segs = [s for s in segment_html(src) if s.kind == "list"]
    top = segs[0]
    assert "시작함" in top.text and "재판단 필요" in top.text, top.text
    assert "원가율 38%" not in top.text, top.text
    assert top.depth == 0 and [s.depth for s in segs[1:3]] == [1, 1], [s.depth for s in segs]
    assert any(s.text == "원가율 38%로 목표 32%를 넘음" for s in segs), [s.text for s in segs]
    ex = (SKILL / "tests" / "fixtures" / "html-exempt.html").read_text(encoding="utf-8")
    kinds = {s.kind for s in segment_html(ex) if "논의가 부족" in s.text}
    assert kinds == {"exempt"}, kinds
    d = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/html-exempt.html").stdout)
    assert d["summary"]["by_rule"].get("AT-16", 0) == 0, d["findings"]
    print("PASS test_ai_tells_html_nesting")


def test_html_exempt_consumers():
    """면제 구역은 장르·원칙·힌트에서 빠지고, 불변식 검사기는 md 와 같이 계속 견준다."""
    ex = run(".claude/skills/anti-workslop/scripts/check_html.py", "--extract-only", f"{FIX}/html-exempt.html")
    assert "논의가 부족" not in ex.stdout and "보정" in ex.stdout, ex.stdout
    h = run(ALL, "--guide", "없음", "--hint", f"{FIX}/html-exempt.html")
    assert "문장 1 " in h.stdout, h.stdout                      # 면제 구역의 세 문장은 세지 않는다
    with tempfile.TemporaryDirectory() as d:
        src = (SKILL / "tests" / "fixtures" / "html-exempt.html").read_text(encoding="utf-8")
        o = _tmp_md(d, "o.html", src)
        p = _tmp_md(d, "p.html", src.replace("논의가 부족했다", "논의가 부족하지 않았다"))
        f = json.loads(run(FID, "--json", o, p).stdout)
        assert f["summary"]["by_rule"].get("F3", 0) > 0, f["summary"]   # 면제 구역의 부정이 바뀐 것은 잡는다
    print("PASS test_html_exempt_consumers")


def _expect(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _check_expected(exp, d):
    for rid, n in exp["by_rule"].items():
        assert d["summary"]["by_rule"].get(rid, 0) == n, (rid, d["summary"]["by_rule"].get(rid, 0), n)
    for rid in exp.get("zero", []):
        assert d["summary"]["by_rule"].get(rid, 0) == 0, rid
    for sev, n in exp.get("min_by_severity", {}).items():
        assert d["summary"]["by_severity"][sev] >= n, (sev, d["summary"]["by_severity"])
    if "strict_fail" in exp:
        assert d["summary"]["strict_fail"] is exp["strict_fail"]


def test_ai_tells_fixture_expected():
    for name in ("ai-draft-prose", "ai-draft-report"):
        exp = _expect(f"{FIX}/{name}.expected.json")
        r = run(CHECK, *exp["args"], "--json", f"{FIX}/{name}.md")
        _check_expected(exp, json.loads(r.stdout))
    print("PASS test_ai_tells_fixture_expected")


def test_ai_tells_borrowed_expected():
    for exp in _expect(f"{FIX}/borrowed.expected.json"):
        r = run(CHECK, *exp["args"], "--json", exp["file"])
        _check_expected(exp, json.loads(r.stdout))
    print("PASS test_ai_tells_borrowed_expected")


def test_ai_tells_clean_control():
    for genre in ("줄글", "개조식"):
        r = run(CHECK, "--genre", genre, "--strict", "--json", f"{FIX}/clean-control.md")
        d = json.loads(r.stdout)
        assert r.returncode == 0 and d["summary"]["by_severity"]["S1"] == 0 and d["summary"]["by_severity"]["S2"] == 0, (genre, d["findings"][:3])
        # 구분선 '---' 은 문단이 아니다. 본문 6문단 + 보고서 제목·개요 덩이 1 = 7 (고치기 전에는 8)
        assert d["stats"]["paragraphs"] == 7, d["stats"]
    print("PASS test_ai_tells_clean_control")


def test_ai_tells_self_application():
    paths = [p for p in (ROOT / FIX / "self-application.txt").read_text(encoding="utf-8").splitlines() if p.strip()]
    r = run(CHECK, "--genre", "all", "--strict", "--json", *paths)
    assert r.returncode == 0, r.stdout[-2000:]
    print("PASS test_ai_tells_self_application")


def test_ai_tells_demotion():
    """8문장 미만이면 문서 단위 S2 를 info 로 내려 strict 실패가 되지 않는다. --summary 는 활성 규칙 수만큼 행."""
    r = run(CHECK, "--genre", "줄글", "--strict", "--json", f"{FIX}/short-doc.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0, r.stdout[-2000:]
    assert d["stats"]["sentences"] < 8, d["stats"]
    assert "AT-18" in d["summary"]["demoted"], d["summary"]
    assert d["summary"]["strict_fail"] is False, d["summary"]
    s = run(CHECK, "--genre", "줄글", "--summary", f"{FIX}/short-doc.md")
    lines = s.stdout.splitlines()
    assert "| 규칙 |" in lines[0], lines[:2]
    assert sum(1 for x in lines if x.startswith("| AT-")) == d["rules_active"], d["rules_active"]
    print("PASS test_ai_tells_demotion")


def test_ai_tells_corpus_baseline():
    base = ROOT / FIX / "corpus-baseline.json"
    posts = sorted((ROOT / "styleguides/jangpm/corpus/posts").glob("*.md"))
    if not posts:
        print("SKIP test_ai_tells_corpus_baseline (코퍼스 없음)"); return
    exp = json.loads(base.read_text(encoding="utf-8"))
    r = run(CHECK, "--genre", "줄글", "--json", *[str(p) for p in posts])
    for d in json.loads(r.stdout):
        assert d["summary"]["by_severity"]["S1"] == 0, (d["file"], [f for f in d["findings"] if f["severity"] == "S1"][:3])
        for rid, n in d["summary"]["raw"].items():
            assert n <= exp["max_raw"].get(rid, 0), (d["file"], rid, n, exp["max_raw"].get(rid))
    print("PASS test_ai_tells_corpus_baseline")


def test_ai_tells_substitution_drift():
    b = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/drift-pair/before.md").stdout)
    a = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/drift-pair/after.md").stdout)
    assert a["summary"]["raw"].get("AT-43", 0) >= b["summary"]["raw"].get("AT-43", 0) > 0
    assert (a["summary"]["raw"].get("AT-01", 0) + a["summary"]["raw"].get("AT-13", 0)) >= 1
    print("PASS test_ai_tells_substitution_drift")


def test_report_guide_wiring():
    g = (ROOT / "styleguides/report/개조식 보고서 작성 가이드라인.md").read_text(encoding="utf-8")
    for s in ("서술형 어미 표기", "어체 혼용 금지", "principles/ai-tells-ko.md", "principles/invariants.md", "| S9 |", "[AI 티]"):
        assert s in g, s
    assert "references/ai-tells-ko.md" not in g
    r = run("styleguides/report/scripts/check_report.py", "styleguides/report/samples/bad_draft.md")
    assert r.returncode == 1, r.returncode      # 기존 검사기 동작 불변
    print("PASS test_report_guide_wiring")


def test_styleguides_readme():
    g = (ROOT / "styleguides/README.md").read_text(encoding="utf-8")
    for s in ("jangpm", "report", "styleguide-builder", "손 큐레이션", "principles/ai-tells-ko.md", "principles/invariants.md", "taste/"):
        assert s in g, s
    print("PASS test_styleguides_readme")


def test_jangpm_guide_wiring():
    g = (ROOT / "styleguides/jangpm/장피엠 글쓰기 문체 가이드라인.md").read_text(encoding="utf-8")
    t = (ROOT / ".claude/skills/styleguide-builder/assets/templates/blog.template.md").read_text(encoding="utf-8")
    for doc in (g, t):
        assert doc.count("principles/ai-tells-ko.md") == 2, doc.count("principles/ai-tells-ko.md")
        assert "principles/invariants.md" in doc
        assert "references/ai-tells-ko.md" not in doc
    print("PASS test_jangpm_guide_wiring")


def test_fidelity_ok():
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/orig.md", f"{FIX}/fidelity/ok.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["summary"]["by_severity"]["S1"] == 0, d["findings"]
    assert d["summary"]["by_severity"]["S2"] <= 3, d["findings"]
    print("PASS test_fidelity_ok")


def test_fidelity_drift():
    exp = _expect(f"{FIX}/fidelity/drift.expected.json")
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/orig.md", f"{FIX}/fidelity/drift.md")
    d = json.loads(r.stdout)
    assert r.returncode == 1
    _check_expected(exp, d)
    assert any(f["rule"] == "F1" and f["kind"] == "changed" for f in d["findings"])
    assert any(f["rule"] == "F3" and f["severity"] == "S1" for f in d["findings"])
    print("PASS test_fidelity_drift")


def test_fidelity_amount_forms():
    """자릿수 낱말만 바꾼 금액 표기(3천만 원 ↔ 3,000만 원)는 드리프트가 아니다."""
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/amounts-orig.md", f"{FIX}/fidelity/amounts-ok.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0, d["findings"]
    assert d["summary"]["by_severity"]["S1"] == 0, d["findings"]
    assert d["summary"]["by_rule"].get("F1", 0) == 0, d["findings"]
    print("PASS test_fidelity_amount_forms")


def test_fidelity_contrast_not_negation():
    """대조 용법(「A가 아니라 B」·「A도 아니고 B도 아닌 Z」)을 지운 것은 부정 삭제가 아니다."""
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/contrast-orig.md", f"{FIX}/fidelity/contrast-ok.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0, d["findings"]
    assert d["summary"]["by_severity"]["S1"] == 0, d["findings"]
    print("PASS test_fidelity_contrast_not_negation")


def test_fidelity_contrast_drift():
    """진짜 부정이 사라지면 F3 S1 이 뜬다. 뒤집기(확정되지 않았다 → 확정되었다)와
    양보절 삭제(정답은 아니지만 … → …) 둘 다. 뒤엣것은 대조형 셋만 빼는 규칙이 지킨다."""
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/contrast-orig.md", f"{FIX}/fidelity/contrast-drift.md")
    d = json.loads(r.stdout)
    assert r.returncode == 1, d["findings"]
    s1 = [f for f in d["findings"] if f["rule"] == "F3" and f["severity"] == "S1"]
    assert len(s1) >= 2, d["findings"]
    assert any("정답아니" in f["detail"] for f in s1), s1
    print("PASS test_fidelity_contrast_drift")


def test_fidelity_status_line_removal():
    """AT-39 가 지우라는 검수 상태 문자열(「검수 결과 수정 없음」)을 지운 것은 부정 소실이 아니다.
    두 검사기가 같은 자리에서 반대로 말해 실행마다 결과가 갈렸다(before-after.md §3-3·§6-4)."""
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/status-orig.md", f"{FIX}/fidelity/status-ok.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0, d["findings"]
    assert not [f for f in d["findings"] if f["rule"] == "F3"], d["findings"]
    print("PASS test_fidelity_status_line_removal")


def test_ai_tells_chars_nospace():
    """stats.chars_nospace 는 공백 제외 글자 수다. Step 1 의 짧은 글 판정(800자)이 이 값을 읽는다."""
    d = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/short-doc.md").stdout)
    src = (ROOT / FIX / "short-doc.md").read_text(encoding="utf-8")
    assert d["stats"]["chars_nospace"] == len("".join(src.split())), d["stats"]
    print("PASS test_ai_tells_chars_nospace")


def test_check_html_wrapper():
    """HTML 은 산문 블록을 md 로 뽑아 md 검사기에 넘긴다. 카운슬 템플릿 전용 검사기 둘은 사라졌고
    임계값은 md 검사기(targets.json·§11-2)와 같은 것 하나만 남는다."""
    for gone in ("check_jangpm.py", "check_report.py"):
        assert not (SKILL / "scripts" / gone).exists(), gone
    ex = run(".claude/skills/anti-workslop/scripts/check_html.py", "--extract-only", f"{FIX}/html-sample.html")
    assert ex.returncode == 0, ex.stderr
    assert "## HTML 오프셋 검사용" in ex.stdout and "- 목록 항목 하나" in ex.stdout, ex.stdout
    assert "결론적으로 표는" not in ex.stdout, ex.stdout           # 표는 검사 대상이 아니다
    j = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "장피엠", f"{FIX}/html-sample.html")
    assert j.returncode in (0, 1), j.stderr
    d = json.loads(j.stdout)
    d = d[0] if isinstance(d, list) else d
    assert "hard_fail" in d, d
    s = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "장피엠", "--short", f"{FIX}/html-sample.html")
    ds = json.loads(s.stdout)
    ds = ds[0] if isinstance(ds, list) else ds
    assert len(ds["rows"]) < len(d["rows"]), (len(ds["rows"]), len(d["rows"]))
    g = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "개조식", f"{FIX}/html-sample.html")
    assert "[반드시 고칠 것]" in g.stdout, g.stdout + g.stderr
    print("PASS test_check_html_wrapper")


def test_check_html_levels():
    """개조식은 □(1단)·○(2단)·들여쓴 -(3단)으로, 장피엠은 들여쓴 '- ' 로 뽑는다.
    층위가 살아야 H6(2·3단 숫자 비율)·H8(하위 1개)이 HTML 에서도 층위대로 센다."""
    r = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "개조식",
            "--extract-only", f"{FIX}/html-nested.html")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert lines[1].startswith("□ 10월 전 매장"), lines
    assert lines[2].startswith("○ 원가율 38%"), lines
    s = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "장피엠",
            "--extract-only", f"{FIX}/html-nested.html")
    sl = [l for l in s.stdout.splitlines() if l.strip()]
    assert sl[1].startswith("- 10월 전 매장") and sl[2].startswith("  - 원가율 38%"), sl
    print("PASS test_check_html_levels")


def test_check_html_line_map():
    """장르 검사기가 보고하는 줄 번호는 추출 md 가 아니라 HTML 줄이다."""
    src = (SKILL / "tests" / "fixtures" / "html-nested.html").read_text(encoding="utf-8").splitlines()
    want = next(i for i, l in enumerate(src, 1) if "프로모션 할인과 배송비" in l)
    r = run(".claude/skills/anti-workslop/scripts/check_html.py", "--guide", "개조식", f"{FIX}/html-nested.html")
    nums = [int(x) for x in re.findall(r"H4 (\d+)행", r.stdout)]
    assert nums and want in nums, (nums, want, r.stdout)   # 인용 항목은 Task 6 뒤 빠지므로 긴 무인용 항목으로 본다
    print("PASS test_check_html_line_map")


def test_report_h4_excludes_quote():
    """인용이 든 항목은 인용을 빼고 센다. 인용 보존(F2)과 H4 가 부딪치지 않게 한다(가이드 §14 [종결] 선례)."""
    with tempfile.TemporaryDirectory() as d:
        quote = "가" * 150
        item = f'□ 마케팅팀장은 "{quote}"고 말함\n'
        plain = "□ " + "나" * 130 + "\n"
        q = _tmp_md(d, "q.md", item)
        p = _tmp_md(d, "p.md", plain)
        rq = run("styleguides/report/scripts/check_report.py", q)
        rp = run("styleguides/report/scripts/check_report.py", p)
    assert "H4" not in rq.stdout, rq.stdout
    assert "H4" in rp.stdout, rp.stdout
    print("PASS test_report_h4_excludes_quote")


def test_check_taste():
    """취향 검사기. W-NN 의 검출 필드(regex·literal·density)를 원칙 검사기 엔진으로 돌리고,
    human 은 건너뛰어 목록에 적는다. --strict 는 [규칙] 등급 finding 에만 실패한다."""
    doc = ("# writing-taste\n"
           "- 버전: 0.1 · 갱신: 2026-09-11 · 케이스: 9건 · 규칙 1 · 경향 2 · 관찰 1 · 보류 0\n\n"
           "## 3. 어휘·표기\n"
           "W-01 [규칙] \"달러당\"은 \"가격 대비 성능\"으로 쓴다 — 적용: 투자 분석 — 근거: T-0001, T-0002, T-0003, T-0004 (n=4)"
           " — 예: \"달러당 37배\" → \"가격 대비 성능 37배\" — 검출: regex `달러당` — 갱신 2026-09-11\n"
           "W-02 [경향] \"핵심 포인트\" 라벨을 쓰지 않는다 — 적용: 전체 — 근거: T-0005, T-0006 (n=2)"
           " — 예: \"핵심 포인트: 속도\" → \"속도가 중요합니다\" — 검출: literal `핵심 포인트` — 갱신 2026-09-11\n\n"
           "## 6. 하지 않는 것\n"
           "W-03 [관찰] 비유 대신 직접 말한다 — 적용: 전체 — 근거: T-0007 (n=1) — 예: 전 → 후 — 검출: human — 갱신 2026-09-11\n"
           "W-04 [경향] 이항 대구는 문단당 하나까지 — 적용: 전체 — 근거: T-0008, T-0009 (n=2) — 예: 전 → 후"
           " — 검출: density 2/문단 `아니라` — 갱신 2026-09-11\n")
    with tempfile.TemporaryDirectory() as d:
        taste = _tmp_md(d, "taste.md", doc)
        hit = _tmp_md(d, "hit.md", "달러당 37배는 높다. 핵심 포인트: 속도. 문제는 도구가 아니라 습관이고 속도가 아니라 방향이다.\n")
        clean = _tmp_md(d, "clean.md", "가격 대비 성능이 높다. 속도가 중요합니다.\n")
        r = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--doc", taste, "--strict", "--json", hit)
        c = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--doc", taste, "--strict", "--json", clean)
    assert r.returncode == 1, r.stdout + r.stderr
    h = json.loads(r.stdout)
    assert h["rules_loaded"] == 4 and h["summary"]["human"] == ["W-03"], h["summary"]
    grades = {f["rule"]: f["grade"] for f in h["findings"]}
    assert grades == {"W-01": "규칙", "W-02": "경향", "W-04": "경향"}, grades
    assert h["summary"]["by_grade"] == {"규칙": 1, "경향": 2, "관찰": 0}, h["summary"]
    assert h["summary"]["strict_fail"] is True
    for f in h["findings"]:
        for k in ("rule", "grade", "line", "col", "excerpt", "detail", "scope"):
            assert k in f, (k, f)
    assert c.returncode == 0, c.stdout + c.stderr
    k = json.loads(c.stdout)
    assert k["summary"]["total"] == 0 and k["summary"]["strict_fail"] is False, k["summary"]
    live = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--list")
    assert live.returncode == 0 and live.stdout.startswith("writing-taste "), live.stdout + live.stderr
    # 취향 문서가 없는 것은 오류가 아니다. 공개본을 받은 사람은 빈 상태에서 시작한다(2026-09-14).
    with tempfile.TemporaryDirectory() as d:
        none = f"{d}/none.md"
        clean = _tmp_md(d, "clean.md", "가격 대비 성능이 높다.\n")
        ls = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--doc", none, "--list")
        js = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--doc", none, "--strict", "--json", clean)
    assert ls.returncode == 0 and ls.stdout.startswith("writing-taste 없음 · 규칙 0"), ls.stdout + ls.stderr
    m = json.loads(js.stdout)
    assert js.returncode == 0 and m["doc_state"] == "missing" and m["summary"]["total"] == 0, js.stdout + js.stderr
    print("PASS test_check_taste")


def test_ai_tells_explain_human():
    """--explain human 은 설명표의 human 행과 §4 표만 낸다. 진단이 규칙 파일 전문(30K자) 대신 이것을 읽는다."""
    r = run(CHECK, "--explain", "human")
    assert r.returncode == 0, r.stderr
    human = set(re.findall(r"^(AT-\d\d)\s+S\d\s+human\s", run(CHECK, "--list", "--genre", "all").stdout, re.M))
    rows = set(re.findall(r"^\| (AT-\d\d) \|", r.stdout, re.M))
    assert rows == human, (rows, human)
    assert "바꾸지 않는 것" in r.stdout and "| 정당한 용법 |" in r.stdout, r.stdout[:300]
    assert len(r.stdout) < 6000, len(r.stdout)
    print("PASS test_ai_tells_explain_human")


ALL = ".claude/skills/anti-workslop/scripts/check_all.py"


def test_check_all_pack():
    """--pack 은 서브에이전트가 읽을 묶음 하나다. 가이드 §8·사람이 보는 §11 하위절·§14 윤문 블록, 원칙 human 행과 §4, 취향 §0~§6.
    §0(읽는 법)·자동 계측 표·§14 의 새 글 전용 블록은 싣지 않는다(2026-09-14 경량화). 가이드 전문을 열지 않으므로 다른 절은 없다."""
    r = run(ALL, "--guide", "장피엠", "--pack", f"{FIX}/ai-draft-prose.md")
    assert r.returncode == 0, r.stderr
    for s in ("## 가이드 §8", "## 가이드 §11-2", "### 11-2.", "## 가이드 §14", "[AI 티]",
              "| AT-24 |", "바꾸지 않는 것", "## 취향 §0~§6"):
        assert s in r.stdout, s
    # 취향 칸은 사용자 문서가 있으면 그 §0~§6, 없으면 한 줄 표시다.
    has_taste = (ROOT / "taste" / "writing-taste.md").exists()
    assert ("## 0. 우선순위와 적용 범위" in r.stdout) if has_taste else ("(취향 문서 없음)" in r.stdout), r.stdout[-400:]
    for s in ("## 가이드 §0", "### 11-1.", "[목소리]", "[구조]", "[예시]", "[감정]", "[작업]", "[보존]",
              "## 3. 문장 길이와 호흡", "### 7-1.", "## 7. 보류·모순"):
        assert s not in r.stdout, s
    assert len(r.stdout) - len((ROOT / "styleguides/report/title-claims.md").read_text(encoding="utf-8")) < 9500, len(r.stdout)
    g = run(ALL, "--guide", "개조식", "--pack", f"{FIX}/ai-draft-report.md")
    assert g.returncode == 0, g.stderr
    for s in ("### 11-1.", "### 11-3.", "[항목]", "[표기]"):
        assert s in g.stdout, s
    for s in ("### 11-2.", "### 11-4.", "[작성 조건]", "[구조]", "[분량]", "[출력]", "### 3-1", "[작업]", "[보존]"):
        assert s not in g.stdout, s
    print("PASS test_check_all_pack")


def test_fidelity_footnotes():
    """F9 각주. humanize-korean finalizer 15항의 「각주 원위치·개수 보존」에서 가져왔다(2026-09-14).
    참조·정의가 사라지거나 생기면 S1, 순서만 바뀌면 S2, ※ 주석 수가 다르면 S2. 어미만 바뀐 판은 F9 0."""
    with tempfile.TemporaryDirectory() as d:
        o = _tmp_md(d, "o.md", "첫 주장이다.[^1] 둘째 주장이다.[^2]\n\n※ 기준일은 3월이다.\n\n[^1]: 출처 하나\n[^2]: 출처 둘\n")
        same = _tmp_md(d, "s.md", "첫 주장입니다.[^1] 둘째 주장입니다.[^2]\n\n※ 기준일은 3월입니다.\n\n[^1]: 출처 하나\n[^2]: 출처 둘\n")
        lost = _tmp_md(d, "l.md", "첫 주장입니다. 둘째 주장입니다.[^2]\n\n[^2]: 출처 둘\n")
        swapped = _tmp_md(d, "w.md", "둘째 주장입니다.[^2] 첫 주장입니다.[^1]\n\n※ 기준일은 3월입니다.\n\n[^1]: 출처 하나\n[^2]: 출처 둘\n")
        a = json.loads(run(FID, "--json", o, same).stdout)
        assert a["summary"]["by_rule"].get("F9", 0) == 0, [f for f in a["findings"] if f["rule"] == "F9"]
        b = [f for f in json.loads(run(FID, "--json", o, lost).stdout)["findings"] if f["rule"] == "F9"]
        assert sum(1 for f in b if f["severity"] == "S1" and f["kind"] == "missing") == 2, b     # 참조 [^1] 과 정의 [^1]:
        assert any("※" in f["detail"] and f["severity"] == "S2" for f in b), b
        c = [f for f in json.loads(run(FID, "--json", o, swapped).stdout)["findings"] if f["rule"] == "F9"]
        assert c and all(f["severity"] == "S2" for f in c) and "순서" in c[0]["detail"], c
    print("PASS test_fidelity_footnotes")


def test_fidelity_negation_equivalents():
    """개조식 명사형 치환은 뜻이 같다(F3 S1 아님). 같은 표지가 여럿이면 실제로 바뀐 자리를 지목한다."""
    with tempfile.TemporaryDirectory() as d:
        orig = ("- 공급사 두 곳 중 한 곳은 물량을 보장할 수 없음\n"
                "- 재구매율은 아직 확인되지 않았음\n"
                "- 지방 수요는 잴 수 없음\n")
        same = ("- 공급사 두 곳 중 한 곳은 물량 보장 불가\n"
                "- 재구매율은 미확인\n"
                "- 지방 수요는 잴 수 없음\n")
        drift = ("- 공급사 두 곳 중 한 곳은 물량을 보장할 수 없음\n"
                 "- 재구매율은 아직 확인되지 않았음\n"
                 "- 지방 수요는 4주 뒤 집계\n")
        level = ("- 공급사 두 곳 중 한 곳은 물량을 보장할 수 없음\n"
                 "- 재구매율은 미정\n"
                 "- 지방 수요는 잴 수 없음\n")
        o = _tmp_md(d, "o.md", orig)
        a = json.loads(run(FID, "--json", o, _tmp_md(d, "a.md", same)).stdout)
        f3 = [f for f in a["findings"] if f["rule"] == "F3" and f["severity"] == "S1"]
        assert not f3, f3
        b = json.loads(run(FID, "--json", o, _tmp_md(d, "b.md", drift)).stdout)
        s1 = [f for f in b["findings"] if f["rule"] == "F3" and f["severity"] == "S1"]
        assert len(s1) == 1 and s1[0]["line"] == 3, s1        # 바꾸지 않은 1행이 아니라 3행
        c = json.loads(run(FID, "--json", o, _tmp_md(d, "c.md", level)).stdout)
        s1c = [f for f in c["findings"] if f["rule"] == "F3" and f["severity"] == "S1"]
        assert len(s1c) == 1 and s1c[0]["line"] == 2, s1c     # 「확인되지 않음 → 미정」은 확정 수준이 바뀐다
        assert "미정" in s1c[0]["detail"], s1c                 # 어디로 옮겨 갔는지 결과 쪽 자리를 함께 낸다
    print("PASS test_fidelity_negation_equivalents")


def test_check_all_hint():
    """--hint 는 원문을 열지 않고 가이드를 고르게 하는 한 줄이다. 산문이 이어지면 줄글, 명사형 종결 항목이 대세면 개조식,
    섞였거나 셋 미만이면 애매(호출자가 묻는다). 항목 끝의 이모지는 종결 판정에서 뗀다."""
    r = run(ALL, "--guide", "없음", "--hint", f"{FIX}/ai-draft-prose.md")
    assert r.stdout.startswith("힌트: 줄글 ·") and "합쇼체 9" in r.stdout and "공백 제외 752자" in r.stdout, r.stdout
    r = run(ALL, "--guide", "없음", "--hint", f"{FIX}/ai-draft-report.md")
    assert r.stdout.startswith("힌트: 개조식 ·") and "항목 21" in r.stdout, r.stdout
    r = run(ALL, "--guide", "없음", "--hint", f"{FIX}/three-lessons.md")
    assert r.stdout.startswith("힌트: 줄글 ·") and "해라체 100%" in r.stdout, r.stdout     # 해라체 산문도 줄글
    r = run(ALL, "--guide", "없음", "--hint", f"{FIX}/clean-control.md")
    assert r.stdout.startswith("힌트: 애매 ·"), r.stdout                                    # 줄글 + 개조식이 섞인 픽스처
    with tempfile.TemporaryDirectory() as d:
        para = "첫 문장은 산문입니다. 둘째 문장도 산문입니다. 셋째 문장까지 산문입니다.\n\n"
        mixed = para * 3 + "".join(f"- 항목 {i} 검토 필요\n" for i in range(6))       # 산문 9문장 + 명사형 항목 6
        assert run(ALL, "--guide", "없음", "--hint", _tmp_md(d, "m.md", mixed)).stdout.startswith("힌트: 애매 ·")
        report = para + "".join(f"- 항목 {i} 검토 필요\n" for i in range(6))         # 산문 3문장 + 명사형 항목 6 → 항목이 대세
        assert run(ALL, "--guide", "없음", "--hint", _tmp_md(d, "r.md", report)).stdout.startswith("힌트: 개조식 ·")
        table = "| 항목 | 값 |\n|---|---|\n| a | 1 |\n| b | 2 |\n"
        assert run(ALL, "--guide", "없음", "--hint", _tmp_md(d, "t.md", table)).stdout.startswith("힌트: 애매 ·")
        emoji = "".join(f"○ 항목 {i} 을 완료하였음 ✅\n" for i in range(4))
        assert "명사형 100%" in run(ALL, "--guide", "없음", "--hint", _tmp_md(d, "e.md", emoji)).stdout
    print("PASS test_check_all_hint")


def test_check_all_bundle():
    """--bundle 은 서브에이전트가 읽을 것 전부를 한 번에 낸다: 브리프 → 읽기 묶음 → 진단. 원문은 싣지 않는다(따로 Read).
    Bash 출력 상한(30K자) 안이어야 한다."""
    r = run(ALL, "--guide", "장피엠", "--bundle", f"{FIX}/ai-draft-prose.md")
    assert r.returncode == 0, r.stderr
    i = [r.stdout.find(s) for s in ("# 서브에이전트 브리프", "# 읽기 묶음 ·", "# check_all · 진단 ·")]
    assert i[0] == 0 and i[0] < i[1] < i[2], i
    assert "현대 사회에서 업무 자동화는 매우 중요합니다. 이 글에서는" not in r.stdout[:i[2]], "원문이 묶음에 섞였다"
    assert len(r.stdout) < 30000, len(r.stdout)
    print("PASS test_check_all_bundle")


def test_skill_budget():
    """경량화 예산(2026-09-14). SKILL.md 는 본 컨텍스트가 매번 읽고, 브리프·묶음은 서브에이전트가 읽는다.
    넘으면 무엇을 뺄지 다시 본다. 실측 · SKILL.md 8,732 → 6.8K자·111줄, 브리프 3,914 → 3.9K자(재작성 규칙 포함), 묶음 11,074 → 8.4K자.
    2026-09-17 자율 재작성으로 브리프 ≤ 6.0K자(자기 대조·작업 기록 형식이 늘었다)."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert len(skill) <= 7500 and skill.count("\n") <= 120, (len(skill), skill.count("\n"))
    assert len(BRIEF.read_text(encoding="utf-8")) <= 6000
    p = run(ALL, "--guide", "장피엠", "--pack", f"{FIX}/ai-draft-prose.md").stdout
    title_rule = (ROOT / "styleguides/report/title-claims.md").read_text(encoding="utf-8")
    assert len(title_rule) <= 1300, len(title_rule)  # RT-01 입력 예산, 기존 묶음 한도는 유지
    assert len(p) - len(title_rule) <= 9000, len(p)
    print("PASS test_skill_budget")


def test_brief_write_rules():
    """브리프는 호출 수로 재작성을 죄지 않는다. 큰 원문은 절 단위로 나눠 이어 붙이고, 면제 구역은 손대지 않는다.
    자리만 고치던 「cp 뒤 Edit」 방식은 전면 재작성(2026-09-17)에 맞지 않아 없앴다."""
    b = BRIEF.read_text(encoding="utf-8")
    assert "도구 호출 상한은 6회다" not in b, "호출 상한 문장이 남아 있다"
    for s in ("1만 자", "3,000자", "style-exempt", "바뀐 줄", "자기 대조", "더한 것", "뺀 것", "작성자 확인"):
        assert s in b, s
    for gone in ("고칠 것 목록의 자리만", "확신이 있어도 ③에만", "cp 로 복사"):
        assert gone not in b, gone
    assert len(b) <= 6000, len(b)
    print("PASS test_brief_write_rules")


def test_check_all_diagnose():
    """--orig 없이 부르면 진단 단계다. 장르·원칙·취향 검사기를 한 번에 돌려 finding 을 한 줄씩 낸다.
    짧은 글 판정(줄글 800자 이하)을 스스로 하고 장르 명령을 _checks_short 로 바꾼다."""
    r = run(ALL, "--guide", "장피엠", f"{FIX}/ai-draft-prose.md")
    assert r.returncode == 0, r.stderr
    for s in ("## 장르", "## 원칙", "## 취향", "짧은 글 예", "AT-07", "human"):
        assert s in r.stdout, (s, r.stdout[:500])
    assert "판정:" not in r.stdout
    assert "hard" in r.stdout and "[info]" in r.stdout, r.stdout[:800]
    d = run(ALL, "--guide", "개조식", f"{FIX}/ai-draft-report.md")
    assert d.returncode == 0 and "[반드시 고칠 것]" in d.stdout and "짧은 글 아니오" in d.stdout, d.stdout[:300]
    n = run(ALL, "--guide", "없음", f"{FIX}/ai-draft-prose.md")
    assert n.returncode == 0 and "## 장르" not in n.stdout and "## 원칙" in n.stdout, n.stdout[:300]
    print("PASS test_check_all_diagnose")


def test_check_all_verify():
    """--orig 가 있으면 검수 단계다. 막는 항목(장르 hard·원칙 S1·S2·취향 [규칙]·불변식 S1)만 내고 판정 한 줄로 끝난다.
    exit 1 = FAIL, 0 = PASS. 본 컨텍스트가 바퀴당 읽는 양이 JSON 넷(26K자)에서 이것 하나로 준다."""
    f = run(ALL, "--guide", "장피엠", "--orig", f"{FIX}/fidelity/orig.md", f"{FIX}/fidelity/drift.md")
    assert f.returncode == 1, f.stdout + f.stderr
    assert "판정: FAIL" in f.stdout and re.search(r"^\[F[13] ", f.stdout, re.M), f.stdout
    assert "[info]" not in f.stdout and len(f.stdout) < 4000, len(f.stdout)
    p = run(ALL, "--guide", "장피엠", "--orig", f"{FIX}/abstain/already-clean.md", f"{FIX}/abstain/already-clean.md")
    assert p.returncode == 0 and "판정: PASS" in p.stdout, p.stdout + p.stderr
    print("PASS test_check_all_verify")


def test_fidelity_identical():
    r = run(FID, "--strict", "--json", f"{FIX}/fidelity/orig.md", f"{FIX}/fidelity/orig.md")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["summary"]["total"] == 0 and d["stats"]["length_ratio"] == 1.0
    print("PASS test_fidelity_identical")


def test_fidelity_structure_free():
    """자율 재작성(2026-09-17). 표제 순서·문단 수·길이는 불변식이 아니다. 표제를 뒤집고 길이를 두 배로 늘려도
    S1 0 이고 길이 비율은 통계로만 남는다. 숫자·부정은 그대로 S1 이다. --length-max 옵션은 없다."""
    with tempfile.TemporaryDirectory() as d:
        o = _tmp_md(d, "o.md", "# 보고\n\n## 원인\n\n납기가 12% 늦었다. 아직 확정되지 않았다.\n\n## 대책\n\n담당자를 정한다.\n")
        p = _tmp_md(d, "p.md", "# 보고\n\n## 대책\n\n담당자를 정한다. 담당자는 이번 주 안에 정해 두는 편이 낫다. "
                               "그래야 다음 단계가 이어진다.\n\n## 원인\n\n납기가 12% 늦었다. 아직 확정되지 않았다. "
                               "이 값은 잠정치라 바뀔 수 있다.\n")
        r = run(FID, "--strict", "--json", o, p)
        d1 = json.loads(r.stdout)
        assert r.returncode == 0 and d1["summary"]["by_severity"]["S1"] == 0, d1["findings"]
        assert all(f["severity"] == "S3" for f in d1["findings"] if f["rule"] in ("F4", "F5")), d1["findings"]
        assert "F6" not in d1["summary"]["by_rule"] and d1["stats"]["length_ratio"] > 1.5, d1["stats"]
        assert run(FID, "--length-max", "2", o, p).returncode == 2, "--length-max 옵션이 남아 있다"
        bad = _tmp_md(d, "bad.md", "# 보고\n\n## 원인\n\n납기가 15% 늦었다. 확정되었다.\n\n## 대책\n\n담당자를 정한다.\n")
        d2 = json.loads(run(FID, "--strict", "--json", o, bad).stdout)
        assert d2["summary"]["by_severity"]["S1"] >= 2, d2["findings"]
    print("PASS test_fidelity_structure_free")


def test_abstain_fixture():
    """기권 픽스처는 검사기 넷을 모두 통과한다. 장르 검사기가 빠져 있어 잘린 글이 통과했었다."""
    g = run(".claude/skills/styleguide-builder/scripts/check_style.py", "--kit", "styleguides/jangpm",
            "--strict", f"{FIX}/abstain/already-clean.md")
    a = run(CHECK, "--genre", "줄글", "--strict", f"{FIX}/abstain/already-clean.md")
    t = run(".claude/skills/anti-workslop/scripts/check_taste.py", "--strict", "--json", f"{FIX}/abstain/already-clean.md")
    f = run(FID, "--strict", "--json", f"{FIX}/abstain/already-clean.md", f"{FIX}/abstain/already-clean.md")
    assert g.returncode == 0, g.stdout[-2000:] + g.stderr[-2000:]
    assert t.returncode == 0 and json.loads(t.stdout)["summary"]["by_grade"]["규칙"] == 0, t.stdout[-500:]
    assert a.returncode == 0 and f.returncode == 0 and json.loads(f.stdout)["summary"]["total"] == 0
    print("PASS test_abstain_fixture")


def test_compare_polish():
    r = run(".claude/skills/anti-workslop/tests/compare_polish.py", "--genre", "줄글",
            "--orig", f"{FIX}/fidelity/orig.md", f"ok={FIX}/fidelity/ok.md", f"drift={FIX}/fidelity/drift.md", "--json")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    assert [x["label"] for x in rows] == ["원문", "ok", "drift"]
    assert rows[2]["fidelity_s1"] > rows[1]["fidelity_s1"]
    for x in rows:
        for k in ("genre_hard", "genre_soft", "ai_s1", "ai_s2", "ai_s3", "taste_rule", "taste_lean", "length_ratio"):
            assert k in x, k
    print("PASS test_compare_polish")


def test_compare_polish_bad_path():
    """없는 경로는 exit 2 와 한 줄 오류다. 자식 검사기의 JSON 아닌 출력으로 죽지 않는다."""
    r = run(".claude/skills/anti-workslop/tests/compare_polish.py", "--genre", "줄글",
            "--orig", f"{FIX}/fidelity/orig.md", f"x={FIX}/fidelity/does-not-exist.md", "--json")
    assert r.returncode == 2, (r.returncode, r.stderr[-300:])
    assert "Traceback" not in r.stderr, r.stderr[-500:]
    print("PASS test_compare_polish_bad_path")


def _tmp_md(d, name, text):
    p = Path(d) / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_ai_tells_loader_rejects_structure_key():
    """모르는 structure 키는 로더 오류(exit 2)다. 키 목록은 검출기 레지스트리에서 나온다."""
    md = (PRINCIPLES / "ai-tells-ko.md").read_text(encoding="utf-8")
    old = "| `emoji` | | |"                # AT-35 패턴·예외·임계값 셀
    assert md.count(old) == 1, md.count(old)
    with tempfile.TemporaryDirectory() as d:
        broken = Path(d) / "ai-tells-ko.md"
        broken.write_text(md.replace(old, "| `emojix` | | |"), encoding="utf-8")
        r = run(CHECK, "--selftest", "--rules", str(broken))
    assert r.returncode == 2, r.stdout + r.stderr
    assert "모르는 structure 키" in r.stderr, r.stderr
    print("PASS test_ai_tells_loader_rejects_structure_key")


def test_ai_tells_segmenter_edges():
    """헤더만 있는 표는 문단이 아니다. Setext 표제는 표제다. --genre all 은 같은 이모지를 한 번만 보고한다.
    굵은 라벨 목록은 문장 라벨 하나가 끼어도 나머지 연속 구간을 본다. 표현 자체를 말하는 문장은 AT-31 예외다."""
    with tempfile.TemporaryDirectory() as d:
        header_only = _tmp_md(d, "h.md", "| 항목 | 값 |\n|---|---|\n")
        setext = _tmp_md(d, "s.md", "도입 검토 결과\n===\n\n첫 문단이다. 둘째 문장도 있다.\n")
        emoji = _tmp_md(d, "e.md", "□ 현황\n\n  ○ 참여 확대 ✅ 🚀 ✨\n  ○ 예산 집행\n")
        labels = _tmp_md(d, "l.md", "- **시간 절약**: 시간을 절약합니다.\n- **오류 감소**: 오류를 줄입니다.\n"
                                    "- **생산성 향상**: 생산성이 향상됩니다.\n- **끝났다.** 이제 마무리합니다.\n"
                                    "- **비용 절감**: 비용을 절감합니다.\n")
        topic = _tmp_md(d, "p.md", "'발견되어진다'는 표현은 이중 피동이라 피합니다.\n")
        h = json.loads(run(CHECK, "--genre", "개조식", "--json", header_only).stdout)
        s = json.loads(run(CHECK, "--genre", "줄글", "--json", setext).stdout)
        e = json.loads(run(CHECK, "--genre", "all", "--json", emoji).stdout)
        l = json.loads(run(CHECK, "--genre", "개조식", "--json", labels).stdout)
        t = json.loads(run(CHECK, "--genre", "줄글", "--json", topic).stdout)
    assert h["stats"]["paragraphs"] == 0 and h["summary"]["total"] == 0, h["stats"]
    assert s["stats"]["headings"] == 1 and s["stats"]["paragraphs"] == 1, s["stats"]
    assert e["summary"]["by_rule"].get("AT-35", 0) == 3 and "AT-59" not in e["summary"]["by_rule"], e["summary"]
    assert l["summary"]["by_rule"].get("AT-34", 0) == 1, l["summary"]
    assert "AT-31" not in t["summary"]["by_rule"], t["summary"]
    print("PASS test_ai_tells_segmenter_edges")


def test_ai_tells_finding_units():
    """finding 의 unit 은 문장·문단·문서 셋 중 하나다. structure 규칙의 자·%·항 임계 단위가 새면 안 된다."""
    d = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/ai-draft-prose.md").stdout)
    units = {f["unit"] for f in d["findings"]}
    assert units and units <= {"문장", "문단", "문서"}, units
    assert any(f["rule"] in ("AT-04", "AT-05", "AT-14", "AT-34", "AT-36", "AT-38", "AT-45", "AT-46")
               for f in d["findings"]), "structure finding 없음"
    print("PASS test_ai_tells_finding_units")


def test_diagnose_human_rules():
    """사람 판단 규칙 목록 두 곳(subagent.md 단계 3·③ 규칙 ID)이 규칙표의 human 집합과 같다.
    규칙표에 human 행을 더하고 목록을 빠뜨리면 서브에이전트가 그 규칙을 보지 않는다. SKILL.md 는 목록을 들지 않는다."""
    out = run(CHECK, "--list", "--genre", "all").stdout
    human = set(re.findall(r"^(AT-\d\d)\s+S\d\s+human\s", out, re.M))
    assert human, out[:300]
    lines = BRIEF.read_text(encoding="utf-8").splitlines()
    spots = {"단계 2": next(l for l in lines if l.startswith("2. 사람 판단.")),
             "③ 규칙 ID": next(l for l in lines if "③의 규칙 ID는" in l)}
    for where, line in spots.items():
        assert set(re.findall(r"AT-\d\d", line)) == human, (where, sorted(human))
    assert "사람 판단 규칙(원칙 AT-" not in (SKILL / "SKILL.md").read_text(encoding="utf-8")
    print("PASS test_diagnose_human_rules")


def test_priority_chain_sync():
    """우선권 체인 세 곳(SKILL.md 공통, subagent.md 단계 4, 취향 문서 머리)이 같은 순서다.
    브리프가 취향 [관찰]을 가이드 hard 위에 두었던 어긋남(2026-09-14)을 다시 만들지 않는다.
    취향 문서 머리의 정본은 taste-builder 템플릿이다. 실물 문서는 사용자마다 있을 수도 없을 수도 있어 있을 때만 본다."""
    def chain(text: str, rx: str) -> list:
        m = re.search(rx, text, re.M)
        assert m, rx
        names = {"스타일가이드": "가이드", "기본 가이드라인": "가이드", "이 문서": "취향", "원칙 AI 티": "원칙"}
        out = []
        for part in m.group(1).split(" > "):
            part = part.strip()
            for k, v in names.items():
                part = part.replace(k, v)
            out.append(part)
        return out
    skill = chain((SKILL / "SKILL.md").read_text(encoding="utf-8"), r"^- 우선권 · (.+?)\. ")
    diag = chain(BRIEF.read_text(encoding="utf-8"), r"우선권 체인\((.+?)\)")
    assert diag == skill, (diag, skill)
    cut = next(i for i, p in enumerate(skill) if p.startswith("원칙"))
    docs = [ROOT / ".claude" / "skills" / "taste-builder" / "references" / "taste-template.md",
            ROOT / "taste" / "writing-taste.md"]
    for doc in (p for p in docs if p.exists()):
        taste = chain(doc.read_text(encoding="utf-8"), r"^- 우선순위: (.+?)\. ")
        assert taste[:cut] == skill[:cut] and taste[cut].startswith("원칙"), (doc, taste, skill)
    assert docs[0].exists(), docs[0]
    print("PASS test_priority_chain_sync")


def test_ai_tells_no_ai_slop_ko():
    """no-ai-slop 재점검(2026-09-11)에서 들여온 한국어 형태. 양성 픽스처는 잡고,
    장피엠 문체·수치 예외·FAQ 줄로 된 대조군은 다섯 규칙의 원시 매치도 없다."""
    exp = _expect(f"{FIX}/no-ai-slop-ko.expected.json")
    d = json.loads(run(CHECK, *exp["args"], "--json", f"{FIX}/no-ai-slop-ko.md").stdout)
    _check_expected(exp, d)
    k = json.loads(run(CHECK, "--genre", "줄글", "--json", f"{FIX}/no-ai-slop-ko-keep.md").stdout)
    for rid in ("AT-09", "AT-10", "AT-62", "AT-63", "AT-64"):
        assert k["summary"]["raw"].get(rid, 0) == 0, (rid, k["summary"]["raw"])
    print("PASS test_ai_tells_no_ai_slop_ko")


def test_at66_wiring():
    """세 가지 교훈형(AT-66)은 ③에 오지만 재작성이 정해진 조작으로 고친다. 브리프 단계 6 의 두 번째 예외와
    불변식 2 가 그 근거를 적는다. 하나라도 빠지면 재작성이 ③이라며 손대지 않거나 구조를 제멋대로 바꾼다."""
    b = BRIEF.read_text(encoding="utf-8")
    at66 = next(l for l in b.splitlines() if "AT-66 은 같은 문형의 제목" in l)
    assert "그 절 본문" in at66 and "부정·조건 표지" in at66, at66[-300:]   # 부정이 든 제목을 고르면 check_fidelity F3 S1 로 되돌려진다
    for s in ("불변식 셋", "판정법 다섯", "[근거 필요: …]", "[사례 필요: …]", "[마무리 필요: 권유·전망]", "고정 구역"):
        assert s in b, s
    inv = (PRINCIPLES / "invariants.md").read_text(encoding="utf-8")
    assert "## 4. 길이 예산" not in inv and "110%" not in inv, "길이 예산이 남아 있다(2026-09-17 삭제)"
    inv2 = inv.split("## 2. 고정 구역 보존", 1)[1].split("## 3.", 1)[0]
    assert "AT-66" in inv2 and "그 절 본문에 이미 있는 것만" in inv2 and "부정·조건 표지" in inv2, inv2[:300]
    inv1 = inv.split("## 1. 새 사실 금지", 1)[1].split("## 2.", 1)[0]
    assert "연결 문장" in inv1 and "풀이" in inv1 and "더한 것" in inv1, inv1[:300]
    print("PASS test_at66_wiring")


def test_ai_tells_hortative_setup():
    """AT-11 수사 설정은 청유형(「떠올려 보자」·「생각해 봅시다」)도 잡고, 어미가 이어지는 「생각해 보자면」은 두지 않는다.
    GPT 초안(2026-09-11)이 쓴 형태이고 사람 코퍼스(장피엠·보고서)에는 0건이었다."""
    with tempfile.TemporaryDirectory() as d:
        p = _tmp_md(d, "h.md", "동네 공방을 만든 창업자를 떠올려 보자. 첫 고객이 어디서 왔는지 생각해 봅시다. "
                               "생각해 보자면 답은 가까이 있었다.\n")
        r = json.loads(run(CHECK, "--genre", "줄글", "--json", p).stdout)
    assert r["summary"]["raw"].get("AT-11", 0) == 2, r["summary"]["raw"]
    print("PASS test_ai_tells_hortative_setup")


def test_guides_defer_to_invariants():
    """가이드 §10·§14 [작업]·[보존]은 가이드를 시스템 프롬프트로 쓰거나 손으로 편집할 때의 규칙이다. anti-workslop 윤문은
    그 자리를 불변식 셋이 대신하므로 묶음에 싣지 않고, 가이드 §10 은 불변식 셋을 가리킨다(2026-09-17).
    두 블록이 묶음에 남으면 「문단 순서 유지 · 문제 자리만 고친다」가 재작성을 다시 묶는다."""
    bg = json.loads((SKILL / "references" / "base-guidelines.json").read_text(encoding="utf-8"))
    for g, blocks in bg["_s14_blocks"].items():
        assert "작업" not in blocks and "보존" not in blocks, (g, blocks)
    sys.path.insert(0, str(ROOT / ".claude" / "skills" / "styleguide-builder" / "scripts"))
    import register_guide as rg
    assert "작업" not in rg.BLOG_S14 and "보존" not in rg.BLOG_S14, rg.BLOG_S14
    assert "이 윤문에서는 불변식 셋이 그 자리를 대신한다" in BRIEF.read_text(encoding="utf-8")
    line = "anti-workslop 윤문은 이 절 대신 `principles/invariants.md`의 불변식 셋을 따른다."
    for p in (ROOT / ".claude" / "skills" / "styleguide-builder" / "assets" / "templates" / "blog.template.md",
              ROOT / "styleguides" / "jangpm" / "장피엠 글쓰기 문체 가이드라인.md",
              ROOT / "styleguides" / "report" / "개조식 보고서 작성 가이드라인.md"):
        t = p.read_text(encoding="utf-8")
        assert line in t and "불변식 넷" not in t, p
    print("PASS test_guides_defer_to_invariants")


def test_check_all_taste_skip():
    """검수 판정은 취향 [규칙] finding 을 막되, 호출자가 적용 범위 밖이라 넘긴 W-NN 은 줄에만 남기고 막지 않는다.
    취향 검사기는 문서 종류를 몰라 범위를 판단할 수 없다(2026-09-14)."""
    sys.path.insert(0, str(SKILL / "scripts"))
    import check_all
    f = {"line": 3, "col": 1, "detail": "d", "excerpt": "달러당", "scope": "투자 분석"}
    d = {"summary": {"by_grade": {"규칙": 2, "경향": 1, "관찰": 0}, "human": ["W-03"]},
         "findings": [dict(f, rule="W-01", grade="규칙"), dict(f, rule="W-05", grade="규칙"), dict(f, rule="W-02", grade="경향")]}
    g, block, human, lines = check_all.taste_lines(d, True, frozenset({"W-01"}))
    assert block == 1 and g["규칙"] == 2 and human == ["W-03"], (block, g)
    assert len(lines) == 2 and "막지 않음" in lines[0] and "막지 않음" not in lines[1], lines
    assert check_all.taste_lines(d, True)[1] == 2
    r = run(".claude/skills/anti-workslop/scripts/check_all.py", "--guide", "장피엠", "--orig", f"{FIX}/clean-control.md",
            "--taste-skip", "W-01,W-02", f"{FIX}/clean-control.md")
    assert r.returncode in (0, 1) and "판정:" in r.stdout, r.stdout[-500:] + r.stderr[-500:]
    print("PASS test_check_all_taste_skip")


def test_taste_scope_is_provenance():
    """취향의 「적용: …」은 규칙이 나온 장르일 뿐이고 anti-workslop 은 모든 문서에 댄다(2026-09-17).
    범위 판단을 호출자에게 맡기던 문구가 남으면 W-01·W-02 가 투자 분석 밖에서 다시 빠진다."""
    tb = ROOT / ".claude" / "skills" / "taste-builder" / "references"
    for p in (tb / "taste-template.md", tb / "distill-guide.md", SKILL / "references" / "base-guidelines.json",
              SKILL / "scripts" / "check_all.py", SKILL / "scripts" / "check_taste.py", BRIEF, SKILL / "SKILL.md"):
        assert "범위에 드는 문서에만" not in p.read_text(encoding="utf-8"), p
        assert "적용 범위 밖" not in p.read_text(encoding="utf-8"), p
    assert "모든 문서에 센다" in (tb / "taste-template.md").read_text(encoding="utf-8")
    assert "출처" in (tb / "distill-guide.md").read_text(encoding="utf-8").split("## 5.", 1)[1].split("## 6.", 1)[0]
    print("PASS test_taste_scope_is_provenance")


def test_registered_guide():
    """사용자가 styleguide-builder 로 만든 가이드는 등록하면 기본 가이드와 같은 길(진단·묶음·힌트)로 돈다(2026-09-14 공개 준비).
    등록 템플릿이 기본 장피엠 설정을 그대로 재현해야 한다. 어긋나면 사용자 가이드만 다른 명령으로 검사된다."""
    sys.path.insert(0, str(ROOT / ".claude" / "skills" / "styleguide-builder" / "scripts"))
    import register_guide as rg
    base = SKILL / "references" / "base-guidelines.json"
    bg = json.loads(base.read_text(encoding="utf-8"))
    _, changed = rg.register(bg, "장피엠", "styleguides/jangpm", bg["장피엠"][0])
    assert changed is False, "등록 템플릿이 기본 장피엠 설정과 다르다"
    assert rg.BLOG_S14 == bg["_s14_blocks"]["장피엠"] and rg.BLOG_PACK == bg["_pack_sections"]["장피엠"]
    for name in ("장피엠", "개조식"):
        try:
            rg.remove(bg, name)
            raise AssertionError(f"기본 가이드 {name} 가 지워졌다")
        except rg.RegisterError:
            pass
    reg = ".claude/skills/styleguide-builder/scripts/register_guide.py"
    scripts = (SKILL / "scripts").as_posix()
    prose = f"{FIX}/ai-draft-prose.md"
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "bg.json"
        tmp.write_text(base.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        r = run(reg, "--kit", "styleguides/jangpm", "--name", "테스트가이드", "--base", str(tmp))
        assert r.returncode == 0 and "[done]" in r.stdout, r.stdout + r.stderr
        assert "[skip]" in run(reg, "--kit", "styleguides/jangpm", "--name", "테스트가이드", "--base", str(tmp)).stdout
        new = json.loads(tmp.read_text(encoding="utf-8"))
        assert list(new)[:3] == ["장피엠", "개조식", "테스트가이드"] and new["_checker_kind"]["테스트가이드"] == "style"
        code = ("import sys; from pathlib import Path; sys.path.insert(0, %r); import check_all; "
                "check_all.BASE = Path(%r); sys.exit(check_all.main(sys.argv[1:]))" % (scripts, str(tmp)))
        h = run("-c", code, "--guide", "없음", "--hint", prose)
        assert "줄글: 장피엠(기본), 테스트가이드" in h.stdout.splitlines()[1], h.stdout + h.stderr
        p = run("-c", code, "--guide", "테스트가이드", "--pack", prose)
        assert p.returncode == 0 and "# 읽기 묶음 · 테스트가이드 (줄글)" in p.stdout and "## 가이드 §11-2" in p.stdout, p.stderr
        g = run("-c", code, "--guide", "테스트가이드", prose)
        assert g.returncode == 0 and "## 장르 · 테스트가이드" in g.stdout and "hard" in g.stdout, g.stdout[:300] + g.stderr
        assert run(reg, "--remove", "개조식", "--base", str(tmp)).returncode == 1
        assert run(reg, "--remove", "테스트가이드", "--base", str(tmp)).returncode == 0
        assert json.loads(tmp.read_text(encoding="utf-8")) == bg, "등록을 빼면 원래대로 돌아와야 한다"
    assert run(ALL, "--guide", "등록안된가이드", prose).returncode == 2
    print("PASS test_registered_guide")


def test_ai_tells_at43_substitutes():
    """AT-43 은 금지 평가어를 피한 대체어(견고·탁월·체계적·뛰어난…)도 센다. 09-11 재점검에서 이 말들로 쓴 문단이
    0건으로 통과했다(2026-09-14 보강). 명사가 붙지 않은 「명확하게 적는다」는 세지 않는다."""
    with tempfile.TemporaryDirectory() as d:
        p = _tmp_md(d, "a.md", "견고한 구조를 갖췄습니다. 탁월한 분석이 뒤를 받칩니다. 체계적인 접근으로 풀었습니다. "
                               "뛰어난 설계가 돋보입니다. 목표는 명확하게 적습니다.\n")
        r = json.loads(run(CHECK, "--genre", "줄글", "--json", p).stdout)
    assert r["summary"]["raw"].get("AT-43", 0) == 4, r["summary"]["raw"]
    print("PASS test_ai_tells_at43_substitutes")


if __name__ == "__main__":
    from test_report_titles import test_report_titles
    test_report_titles()
    test_skill_doc()
    test_modes_doc()
    test_base_guidelines_resolve()
    test_base_guidelines_common()
    test_skill_docs_no_s3()
    test_ai_tells_table_shape()
    test_ai_tells_selftest()
    test_ai_tells_list_handshake()
    test_ai_tells_loader_rejects()
    test_ai_tells_exemptions()
    test_ai_tells_borrowed_controls()
    test_ai_tells_json_envelope()
    test_ai_tells_html_offsets()
    test_ai_tells_html_nesting()
    test_html_exempt_consumers()
    test_ai_tells_fixture_expected()
    test_ai_tells_borrowed_expected()
    test_ai_tells_clean_control()
    test_ai_tells_self_application()
    test_ai_tells_demotion()
    test_ai_tells_corpus_baseline()
    test_ai_tells_substitution_drift()
    test_report_guide_wiring()
    test_styleguides_readme()
    test_jangpm_guide_wiring()
    test_fidelity_ok()
    test_fidelity_drift()
    test_fidelity_amount_forms()
    test_fidelity_contrast_not_negation()
    test_fidelity_contrast_drift()
    test_fidelity_status_line_removal()
    test_ai_tells_chars_nospace()
    test_check_html_wrapper()
    test_check_html_levels()
    test_check_html_line_map()
    test_report_h4_excludes_quote()
    test_check_taste()
    test_ai_tells_explain_human()
    test_check_all_pack()
    test_check_all_diagnose()
    test_check_all_verify()
    test_fidelity_identical()
    test_fidelity_structure_free()
    test_abstain_fixture()
    test_compare_polish()
    test_compare_polish_bad_path()
    test_ai_tells_loader_rejects_structure_key()
    test_ai_tells_segmenter_edges()
    test_ai_tells_finding_units()
    test_diagnose_human_rules()
    test_priority_chain_sync()
    test_ai_tells_at43_substitutes()
    test_guides_defer_to_invariants()
    test_check_all_taste_skip()
    test_taste_scope_is_provenance()
    test_registered_guide()
    test_fidelity_footnotes()
    test_fidelity_negation_equivalents()
    test_check_all_hint()
    test_check_all_bundle()
    test_skill_budget()
    test_brief_write_rules()
    test_ai_tells_no_ai_slop_ko()
    test_at66_wiring()
    test_ai_tells_hortative_setup()
    print("ALL PASS")
