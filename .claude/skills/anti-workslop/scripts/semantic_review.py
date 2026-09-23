"""Risk routing and hash-bound evidence validation; never calls a model."""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
import json
import re

POLARITY = re.compile(r"않|없|못|아니|경우|다면|라면|이면|조건|제외|예외|이상|이하|초과|미만")
MODAL = re.compile(r"검토|예정|추정|가능|확정|완료|반드시|계획|전망|예측|보류|중단|했|였|었")


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


PROTECTED = ('frontmatter', 'quote', 'code', 'table', 'exempt')
# 짝지은 단위 사이에서 이 넷 가운데 하나라도 달라질 때만 위험이다. 순서는 _signals 와 같다.
REASON_OF = ('수치·단위·날짜가 있는 변경', '부정이 있는 변경',
             '조건이 있는 변경', '확정 수준·시제 변경')
RESHAPED = 0.9      # 표지가 든 짝이 이보다 덜 닮았으면 표지가 같아도 검토를 청한다


@dataclass
class Unit:
    """비교 단위 하나. 산문은 문장, 나머지는 블록."""
    kind: str
    text: str
    line_start: int
    line_end: int
    sec_key: tuple      # 절 식별자(표제 글, 같은 글 가운데 몇째). 두 문서 사이에서 절을 맞춘다
    head_line: int      # 그 절 표제의 행(없으면 1)
    sec_end: int        # 그 절의 마지막 행
    raw: str


def units(doc):
    """문서를 비교 단위 목록으로 편다. 산문 블록만 문장으로 쪼갠다."""
    from check_ai_tells import split_sentences
    segs = doc.segs
    if not segs:
        return []
    seen = Counter()
    out, key, head_line, sec_end = [], ('', 0), 1, segs[-1].line_end
    for i, s in enumerate(segs):
        if s.kind == 'heading':
            name = re.sub(r"\s+", " ", s.text).strip()
            seen[name] += 1
            key, head_line = (name, seen[name]), s.line_start
            sec_end = next((segs[k].line_start - 1 for k in range(i + 1, len(segs))
                            if segs[k].kind == 'heading'), segs[-1].line_end)
        if s.kind == 'prose':
            for x in (split_sentences(s.text) or [s.text]):
                if x.strip():
                    out.append(Unit('prose', x.strip(), s.line_start, s.line_end, key, head_line, sec_end, s.raw))
        else:
            out.append(Unit(s.kind, s.text, s.line_start, s.line_end, key, head_line, sec_end, s.raw))
    return out


def _norm(t):
    return re.sub(r"\s+", " ", t).strip()


def _grams(t):
    return {t[i:i + 2] for i in range(len(t) - 1)} or ({t} if t else set())


def _signals(text):
    """이 단위가 품은 의미 표지. 짝 사이에서 이것이 달라질 때만 위험으로 올린다."""
    from check_ai_tells import mask
    from check_fidelity import blank_status, extract_numbers, extract_polarity
    masked = mask(blank_status(text))
    neg, cond = extract_polarity(masked)
    return (Counter(it.key for it in extract_numbers(masked)),
            Counter(it.key[1] for it in neg),
            Counter(it.key[2] for it in cond),
            Counter(MODAL.findall(masked)))


def _pair_units(old, new):
    """(짝, 짝 없는 원문 인덱스, 짝 없는 결과 인덱스). 정규화 동일 → 유사도 순으로 맞춘다."""
    def key(u):
        return u.kind, (u.raw if u.kind in PROTECTED else _norm(u.text))
    buckets = defaultdict(deque)
    for j, u in enumerate(new):
        buckets[key(u)].append(j)
    used_o, used_p, pairs, ratio = set(), set(), [], {}
    for i, u in enumerate(old):
        if buckets[key(u)]:
            j = buckets[key(u)].popleft()
            pairs.append((i, j)); used_o.add(i); used_p.add(j); ratio[(i, j)] = 1.0
    cands = []
    for i, a in enumerate(old):
        if i in used_o or a.kind in PROTECTED:
            continue
        ga = _grams(_norm(a.text))
        for j, b in enumerate(new):
            if j in used_p or b.kind != a.kind or b.kind in PROTECTED:
                continue
            gb = _grams(_norm(b.text))
            if not ga or not gb or len(ga & gb) / len(ga | gb) < .3:
                continue                    # 값싼 걸러내기. 긴 문서의 O(n²) 비교를 줄인다
            r = SequenceMatcher(None, a.text, b.text, autojunk=False).ratio()
            if r >= .55:
                cands.append((-r, i, j))
    for r, i, j in sorted(cands):
        if i not in used_o and j not in used_p:
            pairs.append((i, j)); used_o.add(i); used_p.add(j); ratio[(i, j)] = -r
    return (sorted(pairs), ratio,
            [i for i in range(len(old)) if i not in used_o],
            [j for j in range(len(new)) if j not in used_p])


def _loc(us, idx):
    """위치와 함께 문맥(그 단위가 든 문단 원본)을 담는다.

    전면 재작성에서는 옆 문장에 있던 내용이 이 문장으로 옮겨 온다. 문장만 떼어 보면
    「더했다」로 보이므로, 검토하는 쪽이 문단을 함께 읽어야 한다.
    """
    if not idx:
        return None
    first, last = us[idx[0]], us[idx[-1]]
    return dict(line=first.line_start, end_line=max(us[i].line_end for i in idx),
                text='\n'.join(us[i].text for i in idx),
                context='\n'.join(dict.fromkeys(us[i].raw for i in idx)),
                section_start=first.head_line, section_end=last.sec_end)


def _by_section(us, idx):
    groups = defaultdict(list)
    for i in idx:
        groups[us[i].sec_key].append(i)
    return groups


def risks(od, pd):
    """짝지은 단위 사이의 차이와, 짝 없는 단위의 절 대조만 검토 요청으로 올린다.

    유사도는 문맥 대응 후보를 고를 뿐 의미 동등성을 증명하지 않는다. 짝이 없는 단위는
    같은 절끼리 한 건으로 묶어, 문단 병합·분할이 위험을 부풀리지 않게 한다.
    """
    old, new = units(od), units(pd)
    pairs, ratio, left_o, left_p = _pair_units(old, new)
    result = []

    def add(reasons, oi, pi):
        result.append(dict(reasons=reasons, orig=_loc(old, oi), polished=_loc(new, pi)))

    for i, j in pairs:
        a, b = old[i], new[j]
        if a.kind in PROTECTED:
            if a.raw != b.raw:
                add(['고정 구역 변경'], [i], [j])
            continue
        sa, sb = _signals(a.text), _signals(b.text)
        reasons = [REASON_OF[k] for k in range(4) if sa[k] != sb[k]]
        # 표지가 같아도 문장이 많이 달라졌으면 올린다. 표지의 다중집합은 같은데 붙는 대상이
        # 바뀌는 자리(「서울은 지원하지 않는다」→「부산은 지원하지 않는다」)를 코드가 가리지 못한다.
        if not reasons and ratio.get((i, j), 1.0) < RESHAPED and any(sa):
            reasons = ['표지가 있는 문장의 재작성']
        if reasons:
            add(reasons, [i], [j])
    for i in (x for x in left_o if old[x].kind in PROTECTED):
        add(['고정 구역 변경'], [i], [])
    for j in (x for x in left_p if new[x].kind in PROTECTED):
        add(['고정 구역 변경'], [], [j])
    go = _by_section(old, [i for i in left_o if old[i].kind not in PROTECTED])
    gp = _by_section(new, [j for j in left_p if new[j].kind not in PROTECTED])
    for key in sorted(set(go) | set(gp),
                      key=lambda k: (old[go[k][0]].line_start if k in go else 10 ** 9,
                                     new[gp[k][0]].line_start if k in gp else 10 ** 9)):
        add(['추가·삭제·대응 불명'], go.get(key, []), gp.get(key, []))
    result.sort(key=lambda r: ((r['orig'] or r['polished'])['line'], r['polished'] is None))
    for n, r in enumerate(result, 1):
        r['id'] = f'R{n:03}'
    return result


def packet(od, pd):
    return dict(schema_version=1, orig_sha256=file_hash(od.path),
                polished_sha256=file_hash(pd.path), risks=risks(od, pd))


def _load(path, packet):
    """기록 하나를 {ID: (판정, 근거, 담당 종류)} 로 편다. 형식·해시·중복을 여기서 본다.

    v2 는 보존을 preserved 에 ID 만 적고 items 에는 의미 변경·판단 불가만 둔다(근거 필수).
    v1(모든 ID 에 판정과 근거)도 그대로 받는다 — 09-17 기록이 v1 이다.
    """
    record = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(record, dict) or record.get('schema_version') not in (1, 2):
        raise ValueError('기록 형식 또는 버전')
    if any(record.get(k) != packet[k] for k in ('orig_sha256', 'polished_sha256')):
        raise ValueError('원문 또는 결과 변경: 검토 기록 만료')
    if record.get('independent') is not True or not record.get('reviewer'):
        raise ValueError('독립 검토 담당 정보 없음')
    v2 = record['schema_version'] == 2
    method = record.get('method') or 'llm'
    items = record.get('items', [])
    preserved = record.get('preserved', []) if v2 else []
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise ValueError('항목 형식')
    if not isinstance(preserved, list) or len(preserved) != len(set(preserved)):
        raise ValueError('보존 목록 형식 또는 중복')
    out = {rid: ('보존 확인', '', method) for rid in preserved}
    allowed = ('보존 확인', '의미 변경', '판단 불가') if not v2 else ('의미 변경', '판단 불가')
    for x in items:
        rid, verdict, evidence = x.get('id'), x.get('verdict'), x.get('evidence')
        if rid in out:
            raise ValueError(f'{rid}: 보존 목록과 항목에 함께 있다')
        if verdict not in allowed or not isinstance(evidence, str) or not evidence.strip():
            out[rid] = ('판단 불가', f'{rid}: 판정 또는 근거 없음', method)
        else:
            out[rid] = (verdict, evidence, method)
    if len(out) != len(preserved) + len(items):
        raise ValueError('검토 대상 중복')
    return out


def review_status(packet, record_paths=None, concern=False):
    """여러 기록을 순서대로 합쳐 본다. 뒤 기록이 같은 ID 를 덮는다(jev 1차 위에 독립 담당)."""
    required = bool(packet['risks']) or concern
    counts = dict(preserved=0, changed=0, unsure=0, by_method={})
    if not required:
        return dict(status='자기 대조', required=False, issues=[], counts=counts)
    paths = [record_paths] if isinstance(record_paths, (str, Path)) else list(record_paths or [])
    if not paths:
        return dict(status='확인 필요', required=True, issues=['독립 검토 기록 없음'], counts=counts)
    merged = {}
    try:
        for p in paths:
            merged.update(_load(p, packet))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        return dict(status='확인 필요', required=True, issues=[str(e)], counts=counts)
    expected = {r['id'] for r in packet['risks']} | ({'AUTHOR'} if concern else set())
    if set(merged) != expected:
        missing = ', '.join(sorted(expected - set(merged))[:5]) or '-'
        extra = ', '.join(sorted(set(merged) - expected)[:5]) or '-'
        return dict(status='확인 필요', required=True, counts=counts,
                    issues=[f'검토 대상 누락 또는 초과 (빠짐 {missing} · 남음 {extra})'])
    issues = []
    for rid, (verdict, evidence, method) in sorted(merged.items()):
        counts['by_method'][method] = counts['by_method'].get(method, 0) + 1
        if verdict == '보존 확인':
            counts['preserved'] += 1
        elif verdict == '의미 변경':
            counts['changed'] += 1
            issues.append(f'{rid}: 의미 변경 — {evidence}')
        else:
            counts['unsure'] += 1
            issues.append(f'{rid}: 판단 불가 — {evidence}' if evidence else f'{rid}: 판단 불가')
    return dict(status='확인 필요' if issues else '독립 검토 완료', required=True,
                issues=issues, counts=counts)


# ---------------------------------------------------------------------------
# jev 1차 판정 — 객관식으로 답이 정해지는 자리만 맡긴다. 원고를 고치지 않는다.
# ---------------------------------------------------------------------------
KEEP = 0.9          # 이 확신 이상으로 「보존」이라 할 때만 자동 해소한다
NOUL_KEEP = 0.1     # 절 단위는 「빠뜨림·더함 없음」 확률이 이만큼 높을 때만 해소한다
CHANGE = NOUL_CHANGE = None   # jev 는 의미 변경을 선언하지 않는다(아래 _ask_one 주석)

# 기준은 「표현이 같은가」가 아니라 「주장이 같은 강도로 남았는가」다(principles/invariants.md §3).
# 이 글은 전면 재작성을 허용하므로 문장 합치기·나누기, 생략된 주어 되살리기, 표현 바꾸기는
# 모두 보존이다. 2026-09-22 첫 측정에서 「표현이 달라졌는가」로 물었다가 정상 재작성을 전부
# 변경으로 읽어 오탐 22건이 났다.
VERDICT_CRITERIA = {
    "보존": {"what": "결과가 원문과 같은 사실·주장을 같은 강도로 말한다. 표현·어순·문장 경계가 달라도 보존이다",
           "not_for": "원문과 어긋나는 사실을 말하거나, 원문에 없는 사실을 더했거나, 원문의 사실을 빠뜨린 경우",
           "examples": ["두 문장을 한 문장으로 합쳤다", "생략된 주어를 앞 문맥에서 되살려 적었다",
                        "「그건 A 때문입니다」를 「A면 B가 된다」로 바꿔 적었다",
                        "수식어를 덜어내고 같은 사실만 남겼다",
                        "옆 문장에 있던 내용이 이 문장으로 옮겨 왔고 원문 문맥에 그대로 있다"]},
    "변경": {"what": "결과가 원문과 어긋나는 사실을 말하거나, 원문에 없는 사실을 더했거나, 원문이 말한 사실을 빠뜨렸다",
           "not_for": "같은 사실을 다르게 표현한 경우",
           "examples": ["10억 → 20억", "검토 중 → 확정", "하지 않는다 → 한다",
                        "서울에 적용되던 말이 부산에 붙었다", "원문에 없던 수치·출처를 더했다"]},
    "판단_불가": {"what": "주어진 문맥만으로는 같은 사실인지 정할 수 없다",
              "not_for": "판정할 수 있는 경우",
              "examples": ["가리키는 대상이 주어진 문맥 밖에 있다"]},
}
SECTION_NOUL = ("결과 절은 원문 절이 말한 사실이나 주장 가운데 하나라도 빠뜨렸거나, "
                "원문 절에 없던 사실을 새로 더했는가?",
                {"true": {"what": "원문의 사실·주장이 결과에서 사라졌거나, 원문에 없던 사실이 결과에 생겼다",
                          "examples": ["원문의 수치나 사례가 결과에 없다", "원문에 없던 출처·주장이 결과에 있다"]},
                 "false": {"what": "같은 사실과 주장이 순서·분량·표현만 달리해 남아 있다",
                           "examples": ["여러 문단을 하나로 합쳤다", "설명을 줄여 적었다",
                                        "질문형 도입을 평서문으로 바꿨다", "자리표시자만 더했다"]}})


def _ask_one(risk):
    """위험 하나를 jev 에 묻는다. (판정, 근거)."""
    import jev_gate
    o, p = risk["orig"], risk["polished"]
    if o and p and "추가·삭제·대응 불명" not in risk["reasons"]:
        # 차이 신호(reasons)는 싣지 않는다. 「무엇이 달라졌다」는 말이 변경 쪽으로 답을 끈다.
        # 문맥(그 문장이 든 문단)을 함께 준다. 옆 문장에서 옮겨 온 내용을 새 사실로 읽지 않게.
        state = {"원문 문맥": o.get("context", o["text"]), "원문 문장": o["text"],
                 "결과 문맥": p.get("context", p["text"]), "결과 문장": p["text"]}
        data, why = jev_gate.system_one(state, {"verdict": jev_gate.choice(
            "결과 문장이 말하는 사실이 원문 문맥에 있는 사실과 같은가? "
            "문맥 안에서 옆 문장으로 옮겨 간 내용은 그대로 있는 것으로 본다.", VERDICT_CRITERIA)})
        if data is None:
            return "판단 불가", f"jev 실패({why})"
        try:
            a = data["answers"]["verdict"]
            v, c = a["choice"], float(a["confidence"])
        except (KeyError, TypeError, ValueError):
            return "판단 불가", "jev 응답 형식"
        if v == "보존" and c >= KEEP:
            return "보존 확인", ""
        # 변경은 jev 가 정하지 않는다. 2026-09-22 측정에서 09-17 검토가 보존이라 한 쌍에
        # 변경 8건을 냈다. 그 판정이 되돌림으로 가면 멀쩡한 문장을 되돌리게 된다.
        return "판단 불가", f"jev {v} {c:.2f} · 자동 해소 아님, 사람이 본다"
    state = {"원문 절": o["text"] if o else "(없음)", "결과 절": p["text"] if p else "(없음)"}
    data, why = jev_gate.system_one(state, {"verdict": jev_gate.noul(*SECTION_NOUL)})
    if data is None:
        return "판단 불가", f"jev 실패({why})"
    try:
        n = float(data["answers"]["verdict"]["noul"])
    except (KeyError, TypeError, ValueError):
        return "판단 불가", "jev 응답 형식"
    if n <= NOUL_KEEP:
        return "보존 확인", ""
    return "판단 불가", f"jev noul {n:.2f} · 자동 해소 아님, 사람이 본다"


def judge(pack, workers: int = 8):
    """위험 전부를 jev 에 병렬로 묻고 v2 기록을 만든다."""
    from concurrent.futures import ThreadPoolExecutor
    import jev_gate
    with ThreadPoolExecutor(max_workers=workers) as ex:
        verdicts = list(ex.map(_ask_one, pack["risks"]))
    preserved, items = [], []
    for r, (v, e) in zip(pack["risks"], verdicts):
        if v == "보존 확인":
            preserved.append(r["id"])
        else:
            items.append({"id": r["id"], "verdict": v, "evidence": e})
    return {"schema_version": 2, "orig_sha256": pack["orig_sha256"],
            "polished_sha256": pack["polished_sha256"], "independent": True,
            "reviewer": jev_gate.model_name(), "method": "jev",
            "preserved": preserved, "items": items}


def main(argv=None):
    import argparse
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_ai_tells import force_utf8_stdout
    from check_fidelity import load_pair
    import jev_gate
    ap = argparse.ArgumentParser(
        prog="semantic_review.py",
        description="위험 구간을 jev 로 1차 판정한다(읽기 전용, 원고를 고치지 않는다).")
    ap.add_argument("--jev", nargs=2, metavar=("ORIG", "POLISHED"), required=True)
    ap.add_argument("-o", "--out", required=True, help="v2 기록을 쓸 경로")
    a = ap.parse_args(argv)
    force_utf8_stdout()
    from check_ai_tells import strip_trailer
    import tempfile
    polished = Path(a.jev[1])
    raw = polished.read_text(encoding="utf-8")
    body = strip_trailer(raw)
    if body != raw:          # 작성자 확인 트레일러는 대조 대상이 아니다
        tmp = Path(tempfile.mkdtemp(prefix="semantic-")) / polished.name
        tmp.write_bytes(body.encode("utf-8"))
        polished = tmp
    od, pd, _ = load_pair(a.jev[0], str(polished), "auto", False)
    pack = packet(od, pd)
    if not pack["risks"]:
        print("의미 위험 0개 · jev 호출 없음")
        return 0
    if not jev_gate.enabled("semantic"):
        print(f"jev 없음 → 위험 {len(pack['risks'])}개 전부 독립 담당")
        return 0
    rec = judge(pack)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes((json.dumps(rec, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    changed = [x["id"] for x in rec["items"] if x["verdict"] == "의미 변경"]
    unsure = [x["id"] for x in rec["items"] if x["verdict"] == "판단 불가"]
    print(f"jev 보존 {len(rec['preserved'])} · 변경 {len(changed)} · 판단 불가 {len(unsure)}")
    if changed:
        print("의미 변경 · " + ", ".join(changed))
    print("독립 담당 대상 · " + (", ".join(unsure) if unsure else "없음"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
