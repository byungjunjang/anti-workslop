# -*- coding: utf-8 -*-
"""prompt.py — 윤문 담당이 읽는 한 장 프롬프트를 레이어 파일에서 조립한다 (P5, 2026-09-23).

check_all.py --prompt 가 부른다. 검사기를 돌리지 않고 원문 본문도 싣지 않는다(담당이 Read 한다).
원문에서는 말끝과 양식 여부만 센다. 블록 순서는 아래 build_prompt 가 정한다(2026-09-23 P5, 결정 기록 0007).
레이어 파일(취향·가이드·원칙)이 바뀌면 다음 호출에 그대로 반영된다. 길이를 코드로 자르지 않는다 —
넘치면 인수 테스트가 막고 사람이 prompt-core.md 를 줄인다.
2026-10-06 · 판정 질문 블록과 예문 블록을 뺐다. 판정 질문은 대부분 「먼저 잡는 것 셋」·「지우는 것」과 겹쳤고,
예문은 가이드의 말투를 남의 초안에 끌어와 원문 말끝을 따르라는 지시와 부딪혔다.
"""
from __future__ import annotations
import re
import unicodedata
from pathlib import Path

from check_all import ROOT, TASTE_MD, guide_path, is_form, main_ending, md_section, strip_numeric, strip_trailer

CORE = ROOT / "principles" / "prompt-core.md"
_W_LINE = re.compile(r"^W-\d+ \[(?:규칙|경향|관찰)\] .+$", re.M)
_S14_LABEL = re.compile(r"^\[([^\]]+)\]")

# 2026-10-06 · clean-writing 의 같은 절을 그대로 가져왔다. 사용자가 가장 거슬린다고 한 셋이라 맨 앞에 둔다.
FIRST3_HEAD = "## 먼저 잡는 것 셋"
FIRST3 = [
    FIRST3_HEAD,
    "이 셋이 가장 거슬린다. 글 전체에서 먼저 찾아 고친다.",
    "1. 비유로 말하기. 「~의 나침반」, 「~라는 엔진」, 「출발점으로 삼는다」처럼 다른 것에 빗대어 말한 문장. "
    "그것이 실제로 무엇이고 무슨 일이 일어나는지를 그대로 쓴다. 원문에 실제 내용이 없으면 문장을 뺀다.",
    "2. 돌려 말하기. 주장을 「~라고 볼 수도 있다」, 「~하는 측면이 있다」로 흐리거나, 할 말 앞에 설명을 깔아 늦게 꺼내는 문장. "
    "누가 무엇을 했는지, 무엇이 맞는지를 바로 쓴다. 원문이 실제로 불확실하다고 말한 것은 그 확정 수준을 그대로 둔다.",
    "3. 뻔한 말을 길게 하기. 회사·제품·사람 이름을 다른 것으로 바꿔 넣어도 그대로 통하는 문장, 읽는 사람이 이미 아는 배경 설명, "
    "앞에서 한 말의 되풀이. 뺀다. 이 글에만 있는 사실이 들어 있으면 그 사실만 남기고 줄인다.",
]

PRIORITY = ("우선권 · 사용자 지시 > 불변식 > 취향 [규칙] > 스타일가이드 hard > 원칙 AI 티 S1 > S2 > 자연스러움 > "
            "취향 [경향]·[관찰] > 스타일가이드 soft > 원칙 S3. 자연스러움 앞의 규칙은 검수가 막으니 반드시 지키고 "
            "그 안에서 가장 자연스럽게 쓴다. 뒤의 규칙이 자연스러움과 부딪히면 자연스러움을 따르고 트레일러에 적는다.")

LIST_KEEP = ("- 원문의 목록(불릿·번호)은 목록 모양으로 두고 항목 문장만 퇴고한다. 여러 항목을 한 문단이나 한 문장으로 합치지 않고, "
             "개수와 순서는 되도록 원문대로 둔다. 군더더기 항목은 뺄 수 있다.")
# 2026-10-06 · 사업계획서에서 원문에 없던 한 줄 요약을 문서 맨 위에 넣어 사용자가 나쁘게 봤다. 핵심은 기존 첫 문단 안으로 올린다.
WRITE = [
    "- 쓰기 전에 누가 읽고 읽은 뒤 무엇을 할지 정한다. 핵심 판단은 원문의 첫 문단 안으로 올리고, 문단의 요점은 그 문단 첫 문장에 둔다"
    "(시간순 문서는 순서를 지킨다). 원문에 없던 요약 줄·요약 문단을 문서 맨 위나 양식 구역 밖에 새로 만들지 않는다.",
    "- 산문 문단은 자리를 땜질하지 말고 문단 단위로 다시 쓴다. 문단 순서·병합·분할은 스스로 정한다.",
    # 2026-10-06 설계안 2 · 바로 위 줄이 목록까지 문단으로 다시 쓰게 했다(4차 평가 iter 24 → 7줄, ctx 13 → 7줄). 모양만 지키고 문장은 퇴고한다.
    LIST_KEEP,
    "- 길이는 묶지 않는다. 핵심이 아닌 문장은 빼도 된다. 뺀 문장은 작업 기록의 「뺀 것」에 적는다.",
    "- AT-66 에 걸리면 같은 문형의 제목을 그 절 본문의 사실로 바꾸고 결론의 재나열과 개수 예고를 지우되, 부정·조건 표지나 수치가 든 제목은 고르지 않는다.",
    "- 다 쓴 뒤 처음 읽는 독자로 한 번 읽고, 두 번 읽어야 뜻이 잡히는 문장만 고친다.",
]
RT01 = "- 보고서 제목·소제목에는 그 절의 핵심 판단을 담는다(RT-01). 본문에 결론이 없거나 제목에 부정·조건·수치가 있으면 원제목을 둔다."
# 2026-10-06 · 내부보고에서 서술 문단을 불릿으로 나눈 판(P2)을 사용자가 1등으로 골랐다. 이 판은 문단을 그대로 둬 적게 고쳤다.
REPORT_BULLETS = "- 서술 문단은 항목 하나에 정보 하나인 불릿으로 나눈다. 문단으로 이어 쓴 판단·근거·계획을 항목으로 세운다."
# 2026-10-06 · 양식 문서(check_all.is_form)는 소제목을 지킨 판(clean-writing)을 사용자가 1등으로 골랐다.
FORM_LINE = ("- 이 원문은 양식 문서다. 고정 소제목(□·■·◇·◦·① 로 시작하는 소제목, 「| 항목 | 내용 |」 표)의 문구·개수·순서와 "
             "굵은 글씨를 그대로 두고 구역 안 내용만 고친다.")
# 2026-10-06 · 장피엠 「문단 끝 해요체」를 따르다 해요체가 원문보다 늘었다. 원문에서 가장 많은 말끝 하나로 맞춘다.
ENDING_NAME = {"합쇼": "합쇼체(-습니다)다", "해요": "해요체(-요)다", "해라": "해라체(-다)다", "명사": "명사형(-음·-함)이다"}
ENDING = ("- 말끝 · 원문에서 가장 많은 말끝은 {}. 목록 밖 문장은 이 말끝 하나로 맞춘다. 인용 안은 맞추지 않는다. "
          "어체는 가이드보다 이 줄을 따른다.")
# 2026-09-23 · 검사기 통과가 가이드상 깨끗함은 아니다(분포 규칙은 검사기가 세지 않는다). 기권 대조군에서 사용자는
# 기권한 판보다 [종결]에 걸린 문장만 고친 판을 골랐다. 그래서 기권이 기본이 아니라, 걸리는 곳만 고치고 없을 때만 기권한다.
ABSTAIN = ("검사기는 이 원문에서 막을 것을 찾지 못했다. 위 「쓰는 법」의 문단 단위 재작성을 적용하지 않는다. "
           "취향·가이드·먼저 잡는 것 셋에 걸리는 문장만 고치고 나머지는 글자 그대로 둔다. "
           "걸리는 곳이 하나도 없을 때만 결과 파일 없이 `수정 없음: <이유 한 구>` 한 줄로 답한다.")
# 2026-10-02 · 되돌림 셋 가운데 둘이 원문부터 걸려 있던 항목이었다. 담당이 첫 결과에서 고치도록 원문 사전 검사의
# 막을 항목을 미리 싣는다. 프롬프트 예산(_prompt_budget)을 지키려고 글자 수로 끊는다.
FLAGS_HEAD = "## 원문에서 이미 걸린 곳 (함께 없앤다)"
# 2026-10-06 · 200 → 160. 「지키는 것」 3 에 질문·가정·정도어 단서를 더할 자리를 냈다(0017). 나머지 걸린 곳은 검수가 잡는다.
FLAGS_BUDGET = 160


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
    """가이드 §14 압축 블록에서 _prompt_s14_blocks 라벨 줄만. 줄글이면 분포 목표 문장을 뺀다(Q1).
    _prompt_s14_drop 의 표지어가 든 문장도 뺀다(2026-10-06, 말끝은 build_prompt 의 ENDING 줄이 정한다)."""
    gp = guide_path(bg, guide) if guide != "없음" else None
    if gp is None:
        return []
    labels = bg.get("_prompt_s14_blocks", {}).get(guide) or \
        [x for x in bg.get("_s14_blocks", {}).get(guide, []) if x != "AI 티"]
    drop = bg.get("_prompt_s14_drop", {}).get(guide, [])
    body = md_section(_read(gp), "14")
    lines = []
    for l in body.split("\n"):
        if not ((m := _S14_LABEL.match(l)) and m.group(1) in labels):
            continue
        if drop:
            kept = [s for s in re.split(r"(?<=[.])\s+", l[m.end():].strip()) if not any(w in s for w in drop)]
            l = f"[{m.group(1)}] " + " ".join(kept)
        lines.append(l)
    text = "\n".join(lines)
    if bg.get("_genre_of", {}).get(guide) in bg.get("_s14_strip_numeric", []):
        text = strip_numeric(text)
    return [l for l in text.split("\n") if l.strip()]


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
    # 원문 본문은 싣지 않고 말끝과 양식 여부만 센다
    text = strip_trailer(orig.read_text(encoding="utf-8"))
    is_html = orig.suffix.lower() in (".html", ".htm")
    ending, form = main_ending(text, is_html), is_form(text)
    out = [f"당신은 한국어 글을 퇴고하는 편집자다. 원문은 AI 가 쓴 초안이다. AI 가 쓴 티를 지우고 {voice} "
           f"핵심이 곧장 전달되는 글로 다시 쓴다. 장르는 {genre}이다.", "", *FIRST3, "", PRIORITY, "",
           "## 지키는 것 (어길 수 없다)", keep, ""]
    taste = taste_rules(taste_md)
    if taste:
        out += ["## 이 사람의 취향", *taste, ""]
    s14 = s14_lines(bg, guide)
    if s14:
        out += [f"## 가이드 · {guide}", *s14, ""]
    out += ["## 지우는 것 (AI 티)", drop, "",
            "## 쓰는 법", *WRITE]
    if ending:
        out.append(ENDING.format(ENDING_NAME[ending]))
    if form:
        out.append(FORM_LINE)
    if genre == "개조식":
        out += [REPORT_BULLETS] + ([] if form else [RT01])
    out.append("")
    if flags:
        out += [*flags_block(flags), ""]
    elif genre != "개조식":          # 개조식은 깨끗해도 서술 문단을 불릿으로 나눈다(2026-10-06)
        out += [ABSTAIN, ""]
    out += output_block(guide, orig, result, record)
    return "\n".join(out)
