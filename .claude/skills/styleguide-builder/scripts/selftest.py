# -*- coding: utf-8 -*-
"""
selftest.py — 키트와 도구의 재현성·로버스트·멱등성을 검증한다.

  python -X utf8 selftest.py --kit styleguides/<slug>

  [1] 문장 분할기 고정 케이스      [2] 종결어미 분류 고정 케이스
  [3] 스냅샷 해시 (posts/stats/targets/profile/metrics 일치)
  [4] 원문 모든 글이 hard 규칙 통과 (규칙이 저자보다 엄격하지 않음)
  [5] 대조군(profile.control_sample)이 hard 규칙을 N개 이상 실패 (규칙이 무력하지 않음)
  [6] analyze_corpus 재실행 → stats.json 바이트 동일   [7] derive_targets 재실행 → targets.json 바이트 동일
  [8] 마크다운 표·이미지·주석·'+ ' 접두어 처리 픽스처
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_style import evaluate  # noqa: E402
from kitlib import SKILL_DIR, assert_snapshot, force_utf8_stdout, load_kit, resolve_skill_path  # noqa: E402
from metrics import analyze_blocks, blocks_from_markdown, classify_ending, split_sentences  # noqa: E402

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def t_splitter() -> None:
    print("[1] 문장 분할")
    cases = {
        "노션 (ex. 구글 독스) 일을 하고, 여러 앱을 씁니다. 레고와 유사합니다. (A.K.A 나모웹에디터)": 3,
        "ChatGPT 사이트 ( chat.openai.com )에서 대화를 나눕니다. 월 3.5만원이 듭니다.": 2,
        "이게 뭘까요? 80년대 비디오 믹서입니다. 복잡해 보이죠? 함께 배워요!": 4,
        "A. 라이브 강의": 1,
        "결제 비용은 글 하나당 57원, 호스팅은 월 약 3만 5천원이 들었습니다.": 1,
        "\"업무적 활용도는 매우 높지만, 배우기는 무척 쉽다.\" 랜딩페이지는 알아두지 않으면 손해겠죠?": 2,
    }
    for text, n in cases.items():
        got = split_sentences(text)
        check(len(got) == n, f"{n}문장 기대, {len(got)}문장: {text[:40]}…")


def t_endings() -> None:
    print("[2] 종결어미")
    cases = [("저는 PM입니다.", "합쇼체"), ("성과를 내왔었고요.", "해요체"), ("복잡해 보이죠?", "죠"),
             ("어떻게 성장해야할까요?", "해요체"), ("함께 배워요!", "해요체"), ("덕분입니다 :)", "합쇼체"),
             ("되어 있을 것입니다.💪", "합쇼체"), ("시작해보시길 바랍니다.", "합쇼체"), ("조언도 했다.", "해라체"),
             ("(매우 좋은 리더시네요.)", "해요체"), ("낮은 전문성으로도요.", "해요체"), ("정말 편리합니다ㅎㅎ", "합쇼체"),
             ("기다리겠습니다🙇🏻‍♂️", "합쇼체")]
    for s, exp in cases:
        got = classify_ending(s)[0]
        check(got == exp, f"{s!r} → {got} (기대 {exp})")


def t_markdown() -> None:
    print("[8] 마크다운 픽스처")
    fx = SKILL_DIR / "tests" / "fixtures" / "md_with_tables"
    for f in sorted(fx.glob("*.md")):
        blocks = blocks_from_markdown(f.read_text(encoding="utf-8"))
        n_tab = sum(1 for b in blocks if b["tag"] == "table")
        texts = " ".join(b["text"] for b in blocks if b["tag"] != "table")
        check(n_tab >= 1, f"{f.name}: 표 블록 감지 ({n_tab})")
        check("|" not in texts, f"{f.name}: 표 셀이 문장으로 새지 않음")
        check("![" not in texts and "<!--" not in texts, f"{f.name}: 이미지·주석 제외")
        m = analyze_blocks(blocks)
        check(m["n_sentences"] > 0, f"{f.name}: 본문 문장 {m['n_sentences']}")
    b = blocks_from_markdown("+ 노코드에 대한 관심이 생기셨나요?\n\n커뮤니티를 운영하고 있습니다.")
    check(all(x["tag"] == "p" for x in b), "'+ ' 접두어는 목록이 아니라 문단")


def t_snapshot(kit) -> None:
    print("[3] 스냅샷")
    try:
        assert_snapshot(kit, need_stats=True, need_targets=True)
        check(True, "posts/stats/targets/profile/metrics 해시 일치")
    except SystemExit as e:
        check(False, str(e))


def t_self_consistency(kit) -> None:
    print("[4] 원문 전부 hard 통과")
    rules, profile = kit.targets()["rules"], kit.profile()
    for p in kit.posts():
        m = analyze_blocks(p["blocks"], profile)
        if m.get("error"):
            check(False, f"{p['slug']}: {m['error']}"); continue
        rows = evaluate(m, rules)
        hard = [f"{r['label']}={r['value']}" for r in rows if not r["ok"] and r["level"] == "hard"]
        check(not hard, f"{p['slug']}: {hard or 'pass'}")


def t_control(kit) -> None:
    print("[5] 대조군은 실패해야 한다")
    profile = kit.profile()
    path = Path(resolve_skill_path(profile.get("control_sample", "${SKILL_DIR}/assets/samples/ai_draft.md")))
    need = int(profile.get("control_min_hard_fails", 5))
    rows = evaluate(analyze_blocks(blocks_from_markdown(path.read_text(encoding="utf-8")), profile), kit.targets()["rules"])
    hard = sum(1 for r in rows if not r["ok"] and r["level"] == "hard")
    check(hard >= need, f"{path.name}: hard 실패 {hard}개 (≥{need} 기대)")


def t_idempotent(kit) -> None:
    print("[6][7] 멱등성")
    for script, target in (("analyze_corpus.py", kit.stats_json), ("derive_targets.py", kit.targets_json)):
        before = target.read_bytes()
        subprocess.run([sys.executable, "-X", "utf8", str(HERE / script), "--kit", str(kit.root)], check=True, capture_output=True)
        check(before == target.read_bytes(), f"{script} 재실행 후 {target.name} 바이트 동일")


def main() -> int:
    force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", required=True)
    a = ap.parse_args()
    kit = load_kit(a.kit)
    t_splitter(); t_endings(); t_markdown()
    t_snapshot(kit); t_self_consistency(kit); t_control(kit); t_idempotent(kit)
    print()
    if FAILS:
        print(f"실패 {len(FAILS)}건"); return 1
    print("모두 통과"); return 0


if __name__ == "__main__":
    sys.exit(main())
