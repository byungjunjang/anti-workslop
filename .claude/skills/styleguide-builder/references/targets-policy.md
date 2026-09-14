# targets.json 도출 정책 (derive_targets.py)

목표: **저자 본인의 글이 전부 통과하고, 전형적인 AI 초고는 떨어지는** 규칙 집합을 코퍼스에서 자동으로 만든다. 손으로 범위를 잡지 않는다.

## 규칙 종류

| source | 대상 | 범위 계산 |
|---|---|---|
| envelope | 비율·평균 지표 (len_mean, pct_*, sent_per_para_mean, commas_per_sent, consecutive_haeyo, conj_consecutive) | 글별 값의 최소~최대에 여유를 더하고 바깥으로 반올림. 방향이 `max`면 상한만, `min`이면 하한만 |
| policy | AI 티 지표 (conj_comma_bad, comma_after_subject, ye_reul_deureo, yeoreobun_dangsin, sensory_total, banned_total, nonpref_total, ai_bullet_bold) | profile.policy_rules 의 고정 상한. 글별 최대가 상한을 넘으면 그 값까지 넓히고 `_flags`에 기록 |
| boolean | opening_ok, closing_is_call_or_outlook, closing_is_summary | 모든 글이 만족 → hard, 75% 이상 → soft, 미만 → 규칙 제외 + flag |
| override | profile.target_overrides | 마지막에 덮어쓴다. `_before_override`에 원래 값을 남긴다. 저자 기준을 바꾸는 일이므로 이유를 `policy_flag_notes`에 적는다 |

## 여유(pad)

| kind | 기본 여유 | 반올림 |
|---|---|---|
| pct | max(3, 폭의 10%) | 정수, 0~100 클립 |
| len (평균 길이) | max(3, 폭의 10%) | 정수 |
| spp (문단당 문장) | max(0.3, 폭의 10%) | 0.1 |
| ratio (쉼표/문장) | max(0.05, 폭의 10%) | 0.05 |
| count | 글별 최대 + 1 | 정수 |

글이 8편 미만이면 여유를 2배로 한다(envelope가 불안정하므로). 5편 미만이면 collect 단계에서 경고한다.

## 권장값(recommended)

- 비율·평균: 코퍼스 합산값(overall)을 반올림.
- 횟수: **글별 중앙값** (합산 총계가 아니다. "여러분 7회"는 14편 합계이지 한 글의 권장이 아니다).
- 불리언: "예"/"아니오".

## 등급(level)

RULE_SPEC 의 기본 등급을 쓴다. hard = 문체의 뼈대(평균 길이, 초장문 비율, 문단당 문장, 합쇼체, 해라체, 문두 접속부사, 접속부사 뒤 쉼표, 문장당 쉼표, 예를 들어, 여러분/당신, 감각어, 금지어, 끝 규칙, 불릿 볼드). 나머지는 soft. policy_rules 에 level 이 있으면 그것을 쓴다.

## 불변식

모든 hard 규칙은 글별 값을 전부 포함해야 한다. 아니면 derive 가 exit 1 로 멈춘다("규칙이 저자보다 엄격합니다"). selftest [4]도 같은 것을 다시 확인한다.

## 대조군

profile.control_sample(기본 `assets/samples/ai_draft.md`)이 hard 규칙을 `control_min_hard_fails`(기본 5)개 이상 실패해야 한다. 어떤 저자의 코퍼스가 AI 초고와 비슷해서 실패 수가 모자라면 (1) 그 저자에 맞는 대조군을 새로 써서 profile.control_sample 로 지정하거나 (2) 문턱을 낮추고 이유를 적는다. 규칙을 억지로 좁혀서 맞추지 않는다.

## _flags 처리

`_flags`는 도출 과정에서 정책·기본 등급을 코퍼스에 맞게 바꾼 기록이다. 워크시트 `policy_flag_notes`에 항목마다 어떻게 받아들였는지 적는다. 예: `opening_ok 규칙 제외 (10/14)` → "도입 유형은 §6-1 수동 분류로 판정한다".

## targets 를 손으로 고치고 싶을 때

targets.json 을 직접 편집하지 않는다(재실행하면 사라진다). profile.json 의 `policy_rules`(상한·등급) 또는 `target_overrides`(특정 규칙 min/max/level) 를 바꾸고 derive 를 다시 돌린다.
