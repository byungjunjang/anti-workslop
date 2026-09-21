"""Risk routing and hash-bound evidence validation; never calls a model."""
from __future__ import annotations

from collections import defaultdict, deque
from difflib import SequenceMatcher
from hashlib import sha256
from pathlib import Path
import json
import re

POLARITY = re.compile(r"않|없|못|아니|경우|다면|라면|이면|조건|제외|예외|이상|이하|초과|미만")
MODAL = re.compile(r"검토|예정|추정|가능|확정|완료|반드시|계획|전망|예측|보류|중단|했|였|었")


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def risks(od, pd):
    """Match unchanged blocks globally first, then changed blocks within kind.

    Similarity selects context, never proves semantic equivalence. Unmatched
    blocks remain review requests, including splits and merges.
    """
    old, new = od.segs, pd.segs
    def key(s):
        if s.kind in ('frontmatter', 'quote', 'code', 'table', 'exempt'):
            return s.kind, s.raw
        return s.kind, re.sub(r"\s+", " ", s.text).strip()
    buckets = defaultdict(deque)
    for j, s in enumerate(new):
        buckets[key(s)].append(j)
    used_o, used_p = set(), set()
    for i, s in enumerate(old):
        if buckets[key(s)]:
            j = buckets[key(s)].popleft()
            used_o.add(i); used_p.add(j)
    candidates = []
    for i, a in enumerate(old):
        if i in used_o:
            continue
        for j, b in enumerate(new):
            if j not in used_p and a.kind == b.kind:
                ratio = SequenceMatcher(None, a.text, b.text, autojunk=False).ratio()
                if ratio >= .55:
                    candidates.append((-ratio, i, j))
    pairs = []
    for _, i, j in sorted(candidates):
        if i not in used_o and j not in used_p:
            pairs.append((i, j)); used_o.add(i); used_p.add(j)
    pairs += [(i, None) for i in range(len(old)) if i not in used_o]
    pairs += [(None, j) for j in range(len(new)) if j not in used_p]

    def location(segs, i):
        if i is None:
            return None
        s = segs[i]
        head = next((segs[k] for k in range(i, -1, -1) if segs[k].kind == 'heading'), None)
        end = next((segs[k].line_start - 1 for k in range(i + 1, len(segs)) if segs[k].kind == 'heading'), segs[-1].line_end)
        return dict(line=s.line_start, end_line=s.line_end, text=s.text,
                    section_start=head.line_start if head else 1, section_end=end)

    result = []
    for i, j in pairs:
        a, b = old[i] if i is not None else None, new[j] if j is not None else None
        text = '\n'.join(s.text for s in (a, b) if s)
        reasons = []
        if a is None or b is None:
            reasons.append('추가·삭제·대응 불명')
        if re.search(r'\d', text): reasons.append('수치·단위·날짜가 있는 변경')
        if POLARITY.search(text): reasons.append('부정·조건이 있는 변경')
        if MODAL.search(text): reasons.append('확정 수준·시제 검토')
        if any(s and s.kind in ('frontmatter', 'quote', 'code', 'table', 'exempt') for s in (a, b)):
            reasons.append('고정 구역 변경')
        if reasons:
            result.append(dict(id=f'R{len(result)+1:03}', reasons=reasons,
                               orig=location(old, i), polished=location(new, j)))
    return result


def packet(od, pd):
    return dict(schema_version=1, orig_sha256=file_hash(od.path),
                polished_sha256=file_hash(pd.path), risks=risks(od, pd))


def review_status(packet, record_path=None, concern=False):
    required = bool(packet['risks']) or concern
    if not required:
        return dict(status='자기 대조', required=False, issues=[])
    if not record_path:
        return dict(status='확인 필요', required=True, issues=['독립 검토 기록 없음'])
    try:
        record = json.loads(Path(record_path).read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema_version') != 1:
            raise ValueError('기록 형식 또는 버전')
        if any(record.get(k) != packet[k] for k in ('orig_sha256', 'polished_sha256')):
            raise ValueError('원문 또는 결과 변경: 검토 기록 만료')
        if record.get('independent') is not True or not record.get('reviewer'):
            raise ValueError('독립 검토 담당 정보 없음')
        items = record.get('items', [])
        expected = {r['id'] for r in packet['risks']} | ({'AUTHOR'} if concern else set())
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ValueError('항목 형식')
        ids = [x.get('id') for x in items]
        if len(ids) != len(set(ids)) or set(ids) != expected:
            raise ValueError('검토 대상 누락 또는 중복')
        issues = []
        for x in items:
            if x.get('verdict') not in ('보존 확인', '의미 변경', '판단 불가') or not isinstance(x.get('evidence'), str) or not x['evidence'].strip():
                issues.append(f"{x.get('id')}: 판정 또는 근거 없음")
            elif x['verdict'] != '보존 확인':
                issues.append(f"{x['id']}: {x['verdict']} — {x['evidence']}")
        return dict(status='확인 필요' if issues else '독립 검토 완료', required=True, issues=issues)
    except (OSError, ValueError, TypeError, KeyError) as e:
        return dict(status='확인 필요', required=True, issues=[str(e)])
