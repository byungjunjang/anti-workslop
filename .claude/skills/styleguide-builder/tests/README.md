# tests — styleguide-builder

## 실행

```bash
# 프로젝트 루트에서
python -X utf8 .claude/skills/styleguide-builder/tests/run_acceptance.py            # jangpm 종단 (네트워크 없음)
python -X utf8 .claude/skills/styleguide-builder/tests/run_smoke.py --md-dir "<내 글 폴더>" --recursive
python -X utf8 .claude/skills/styleguide-builder/scripts/selftest.py --kit styleguides/jangpm
```

`--keep` 을 주면 `tests/.acceptance/`, `tests/.smoke/` 산출물을 남긴다. 기본은 끝나면 삭제.

## 인수 기준 (run_acceptance.py)

1. verify_guideline 8항목 통과, selftest 8군 통과.
2. 핵심 수치 고정: 문장 1,504 / 평균 55.4자 / 합쇼체 86.2%.
3. 첨부 최종본(fixtures/exemplar.md)과 표제 목록 동일.
4. 최종본에만 있는 줄은 전부 `known_deviations.txt` 패턴에 설명된다(숫자 재계산, 인용 교정, 불일치 정리).

## 스모크 기준 (run_smoke.py)

다른 저자의 .md 폴더로: 크래시 없음, 표 셀이 문장으로 새지 않음, 모든 hard 규칙이 글별 값을 포함, 렌더(`--allow-todo`)에 템플릿 표제 전부 존재, 정성 슬롯은 `[TODO:]` 로 남음. 2026-09-07 기준 `learning-blog-writing/writing/posts` 17편으로 확인: 평균 33.2자, 합쇼체 63.8% — nocodecamp 와 전혀 다른 값이 나온다(도구가 특정 블로그에 묶여 있지 않다는 뜻).

## RED 기준선 — 스킬 없이 했을 때 실제로 일어난 실패

이 스킬은 2026-09-07 세션에서 같은 과제를 스킬 없이 수행하며 겪은 실패를 고정하려고 만들었다. 새 서브에이전트로 별도 RED 실행은 하지 않았고, 아래는 그 세션의 기록이다.

| 관찰된 실패 | 스킬의 대응 |
|---|---|
| 가이드라인의 숫자를 손으로 옮겨 적었고, 분할기 수정 후 값이 바뀌었는데(55.1→55.4, 문두 접속 20.4→17.5%) 문서가 따라오지 못함 | 모든 숫자는 render 슬롯. verify ② 재렌더 바이트 동일 |
| '통해' 빈도를 '통해'+'통해서'로 이중 계산(79 vs 실제 49) | 지표는 metrics.py 한 곳, stats.md 에서만 읽음 |
| 문장 분할기가 "ex.", "A.K.A", "22.07.28", "A." 에서 끊음 | 보호 분할기 + selftest [1] 고정 케이스 |
| 종결어미 정규식이 한글을 벗겨 합쇼체 0% 가 나왔는데 한동안 몰랐음 | selftest [2] 고정 케이스, [4] 원문 통과 검사 |
| 손으로 잡은 허용 범위가 저자 본인 글보다 엄격해 14편 중 6편 탈락 | derive_targets 가 글별 envelope 로 도출, hard 불변식 |
| 최종본 인용이 원문과 다름("우리는 내 제품의 포지셔닝…" 등) | 워크시트 원문 인용 + verify ⑥ 코퍼스 대조 |
| 도입 유형을 자동 분류(5/3/2/4)로 세거나 통독(6/3/4/1)으로 세는 두 값이 섞임 | 워크시트 post_structure 표 하나에서 render 가 셈 |
| 두 분석의 집계 방식이 다른 숫자(접속 48/42/39 vs 47/40/35)가 한 문서에 공존 | 집계 방식이 template-provenance.md 에 명시, 값은 한 소스 |

새 저자에 스킬을 적용할 때 RED 를 다시 재현하려면: 스킬 없이 서브에이전트에게 "이 블로그 문체 가이드라인을 만들어라"를 주고, 위 표의 항목이 재발하는지 기록한 뒤 스킬을 붙여 다시 실행한다.
