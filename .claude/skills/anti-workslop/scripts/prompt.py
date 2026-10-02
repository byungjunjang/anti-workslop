# -*- coding: utf-8 -*-
"""prompt.py — 윤문 담당이 읽는 한 장 프롬프트를 레이어 파일에서 조립한다 (P5, 2026-09-23).

check_all.py --prompt 가 부른다. 검사기를 돌리지 않고 원문 본문도 싣지 않는다(담당이 Read 한다).
블록 순서는 아래 build_prompt 가 정한다(2026-09-23 P5, 결정 기록 0007).
레이어 파일(취향·가이드·원칙)이 바뀌면 다음 호출에 그대로 반영된다. 길이를 코드로 자르지 않는다 —
넘치면 인수 테스트가 막고 사람이 prompt-core.md·예문 파일을 줄인다.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path

from check_ai_tells import load_rules
from check_all import ROOT, TASTE_MD, guide_path, md_section, strip_numeric

CORE = ROOT / "principles" / "prompt-core.md"
_W_LINE = re.compile(r"^W-\d+ \[(?:규칙|경향|관찰)\] .+$", re.M)
_S14_LABEL = re.compile(r"^\[([^\]]+)\]")

PRIORITY = ("우선권 · 사용자 지시 > 불변식 > 취향 [규칙] > 스타일가이드 hard > 원칙 AI 티 S1 > S2 > 자연스러움 > "
            "취향 [경향]·[관찰] > 스타일가이드 soft > 원칙 S3. 자연스러움 앞의 규칙은 검수가 막으니 반드시 지키고 "
            "그 안에서 가장 자연스럽게 쓴다. 뒤의 규칙이 자연스러움과 부딪히면 자연스러움을 따르고 트레일러에 적는다.")

WRITE = [
    "- 쓰기 전에 누가 읽고 읽은 뒤 무엇을 할지 정한다. 핵심 판단은 첫 문단에, 문단의 요점은 그 문단 첫 문장에 둔다(시간순 문서는 순서를 지킨다).",
    "- 자리를 땜질하지 말고 문단 단위로 다시 쓴다. 문단 순서·병합·분할은 스스로 정한다.",
    "- 길이는 묶지 않는다. 핵심이 아닌 문장은 빼도 된다. 뺀 문장은 작업 기록의 「뺀 것」에 적는다.",
    "- AT-66 에 걸리면 같은 문형의 제목을 그 절 본문의 사실로 바꾸고 결론의 재나열과 개수 예고를 지우되, 부정·조건 표지나 수치가 든 제목은 고르지 않는다.",
    "- 다 쓴 뒤 처음 읽는 독자로 한 번 읽고, 두 번 읽어야 뜻이 잡히는 문장만 고친다.",
]
RT01 = "- 보고서 제목·소제목에는 그 절의 핵심 판단을 담는다(RT-01). 본문에 결론이 없거나 제목에 부정·조건·수치가 있으면 원제목을 둔다."
# 2026-09-23 · 검사기 통과가 가이드상 깨끗함은 아니다(분포 규칙은 검사기가 세지 않는다). 기권 대조군에서 사용자는
# 기권한 판보다 [종결]에 걸린 문장만 고친 판을 골랐다. 그래서 기권이 기본이 아니라, 걸리는 곳만 고치고 없을 때만 기권한다.
ABSTAIN = ("검사기는 이 원문에서 막을 것을 찾지 못했다. 위 「쓰는 법」의 문단 단위 재작성을 적용하지 않는다. "
           "취향·가이드·판정 질문에 걸리는 문장만 고치고 나머지는 글자 그대로 둔다. "
           "걸리는 곳이 하나도 없을 때만 결과 파일 없이 `수정 없음: <이유 한 구>` 한 줄로 답한다.")
# 2026-10-02 · 되돌림 셋 가운데 둘이 원문부터 걸려 있던 항목이었다. 담당이 첫 결과에서 고치도록 원문 사전 검사의
# 막을 항목을 미리 싣는다. 프롬프트 예산(_prompt_budget)을 지키려고 글자 수로 끊는다.
FLAGS_HEAD = "## 원문에서 이미 걸린 곳 (함께 없앤다)"
FLAGS_BUDGET = 200


def flags_block(flags: list) -> list:
    out, used = [FLAGS_HEAD], 0
    for i, f in enumerate(flags):
        line = f"- {f}"
        if used + len(line) > FLAGS_BUDGET:
            out.append(f"- 외 {len(flags) - i}곳")
            break
        out.append(line)
        used += len(line) + 1
    return out


def _read(p: Path) -> str:
    return unicodedata.normalize("NFC", p.read_text(encoding="utf-8").replace("\r\n", "\n"))


def core_sections() -> tuple[str, str]:
    """prompt-core.md 의 (지키는 것, 지우는 것) 본문. 머리 주석은 싣지 않는다."""
    md = _read(CORE)
    keep = re.search(r"^## 지키는 것\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    drop = re.search(r"^## 지우는 것\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    return (keep.group(1).strip() if keep else ""), (drop.group(1).strip() if drop else "")


def taste_rules(taste_md: Path) -> list[str]:
    """취향 §0~§6 의 W 규칙을 「- W-NN [등급] 진술 (적용: 범위)」 한 줄씩. 근거·예·검출 꼬리는 뺀다."""
    if not taste_md.exists():
        return []
    md = _read(taste_md)
    cut = re.search(r"^## 7\.", md, re.M)
    out = []
    for m in _W_LINE.finditer(md[:cut.start()] if cut else md):
        head, _, rest = m.group(0).partition(" — 적용: ")
        scope = rest.split(" — ", 1)[0].split(" (", 1)[0].strip()
        out.append(f"- {head.strip()}" + (f" (적용: {scope})" if scope else ""))
    return out


def s14_lines(bg: dict, guide: str) -> list[str]:
    """가이드 §14 압축 블록에서 _prompt_s14_blocks 라벨 줄만. 줄글이면 분포 목표 문장을 뺀다(Q1)."""
    gp = guide_path(bg, guide) if guide != "없음" else None
    if gp is None:
        return []
    labels = bg.get("_prompt_s14_blocks", {}).get(guide) or \
        [x for x in bg.get("_s14_blocks", {}).get(guide, []) if x != "AI 티"]
    body = md_section(_read(gp), "14")
    lines = [l for l in body.split("\n") if (m := _S14_LABEL.match(l)) and m.group(1) in labels]
    text = "\n".join(lines)
    if bg.get("_genre_of", {}).get(guide) in bg.get("_s14_strip_numeric", []):
        text = strip_numeric(text)
    return [l for l in text.split("\n") if l.strip()]


def human_lines() -> list[str]:
    """원칙 설명표 human 행의 판정 질문. 검사기가 못 세고 읽어야 보이는 것."""
    return [f"- {r.id} · {r.question}" for r in load_rules().rules if r.detect == "human"]


def example_lines(bg: dict, guide: str) -> list[str]:
    """예문 파일의 「전 · / 후 ·」 줄과 완성 문단 마지막 단락. 머리말·해설은 싣지 않는다."""
    rel = bg.get("_examples", {}).get(guide)
    if not rel or not (ROOT / rel).exists():
        return []
    md = _read(ROOT / rel)
    out = [f"{k} · {v.strip()}" for k, v in re.findall(r"^(전|후) · (.+)$", md, re.M)]
    m = re.search(r"^## 완성 문단\n(.*)", md, re.M | re.S)
    if m:
        paras = [x.strip() for x in re.split(r"\n\s*\n", m.group(1)) if x.strip()]
        if paras:
            # 개조식 예문은 여러 줄 항목 블록이다. 첫 항목 앞에 머리말을 붙이면 목록 모양이 깨진다
            last = paras[-1]
            out += ["", "완성 문단 · " + last] if "\n" not in last else ["", "완성 문단 ·", last]
    return out


def output_block(guide: str, orig: Path, result: Path, record: str) -> list[str]:
    tag = guide if guide != "없음" else "가이드 없음"
    return [
        "## 출력",
        f"1. 원문 `{orig.as_posix()}` 을 Read 로 읽는다. 원문 파일은 고치지 않는다.",
        f"2. 결과를 `{result.as_posix()}` 에 쓴다. 본문만 쓰고 설명·변경 내역·작업 상태를 섞지 않는다. 원문이 마크다운이면 마크다운으로.",
        "3. 작성자만 채울 수 있는 것(본문에 근거가 없는 수치·귀속·일반론, 확신이 낮았던 수정 셋까지, 규칙끼리 부딪혀 한쪽을 고른 자리)이 있으면 결과 파일 끝에 아래 형식으로 붙인다. 없으면 붙이지 않는다.",
        "```text",
        "<!-- anti-workslop:작성자 확인 · 제출 전에 이 줄부터 끝까지 지운다 -->",
        "",
        "---",
        "",
        "## 작성자 확인",
        "",
        "- 근거 · <위치> · 「<인용>」 · <무엇이 없는지>",
        "- 확신 낮음 · <위치> · 「<원문>」 → 「<결과>」",
        "- 충돌 · <구간> · <이긴 규칙>을 따름",
        "```",
        f"4. 작업 기록을 `{record}` 에 쓴다. 빈 절은 (없음).",
        "```text",
        f"집계 · {tag} 기준: 고친 것 N건 (취향 N · 가이드 N · 원칙 N · 사람 판단 N), 뺀 문장 N · 짧은 글 예/아니오 (공백 제외 N자 → N자)",
        "",
        "## 고친 것",
        "<규칙 ID> · <위치>",
        "",
        "## 뺀 것",
        "<원문 인용 그대로> · <규칙 ID 또는 이유>",
        "```",
        f"규칙 ID 는 취향 W-NN, 가이드 {tag}[라벨](예: {tag}[금지]), 원칙과 사람 판단 AT-NN.",
        f"5. 다 쓰면 위 명령과 같은 `check_all.py` 로 검수를 돌린다 · `--guide {guide} --orig <원문> <결과>`. "
        "FAIL 이면 짚힌 자리만 고치고 한 번 더 돌린다. 그래도 FAIL 이면 더 고치지 않는다.",
        "6. 답은 세 줄 · 집계 줄 · 작업 기록 경로 · 트레일러 줄 수와 마지막 판정.",
    ]


def build_prompt(bg: dict, guide: str, orig: Path, flags: list, record: str,
                 taste_md: Path | None = None) -> str:
    """flags 는 원문 사전 검사에서 막을 항목의 요약 줄이다(check_all.check). 비어 있으면 원문이 깨끗한 것이다."""
    taste_md = TASTE_MD if taste_md is None else taste_md
    genre = bg.get("_genre_of", {}).get(guide, "공통")
    result = orig.with_name(orig.stem + ".taste" + orig.suffix)
    voice = f"이 사람의 취향과 {guide} 문체로" if guide != "없음" else "이 사람의 취향으로"
    keep, drop = core_sections()
    out = [f"당신은 한국어 글을 퇴고하는 편집자다. 원문은 AI 가 쓴 초안이다. AI 가 쓴 티를 지우고 {voice} "
           f"핵심이 곧장 전달되는 글로 다시 쓴다. 장르는 {genre}이다.", PRIORITY, "",
           "## 지키는 것 (어길 수 없다)", keep, ""]
    taste = taste_rules(taste_md)
    if taste:
        out += ["## 이 사람의 취향", *taste, ""]
    s14 = s14_lines(bg, guide)
    if s14:
        out += [f"## 가이드 · {guide}", *s14, ""]
    out += ["## 지우는 것 (AI 티)", drop, "",
            "## 읽어야 보이는 것 (판정 질문)", *human_lines(), ""]
    ex = example_lines(bg, guide)
    if ex:
        out += ["## 예문 · 문장을 세우는 법만 본다. 네 어절 이상 그대로 옮기지 않는다", *ex, ""]
    out += ["## 쓰는 법", *WRITE]
    if genre == "개조식":
        out.append(RT01)
    out.append("")
    if flags:
        out += [*flags_block(flags), ""]
    else:
        out += [ABSTAIN, ""]
    out += output_block(guide, orig, result, record)
    return "\n".join(out)
