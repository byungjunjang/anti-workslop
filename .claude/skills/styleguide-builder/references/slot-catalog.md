# 슬롯 카탈로그 — blog.template.md

출처 기호: **S** stats.json(overall) · **T** targets.json 규칙 · **P** profile.json · **W** 워크시트 `## slot:` · **R** 렌더 도우미.
W 슬롯은 에이전트가 쓰는 유일한 부분이다. 형식(표/목록/한 줄)을 지키지 않으면 렌더 결과의 마크다운이 깨진다.

## 숫자·메타 슬롯 (에이전트가 손대지 않음)

| 절 | 슬롯 | 출처 | 뜻 |
|---|---|---|---|
| 머리 | `{{p:display}}` `{{p:author}}` `{{p:site}}` `{{p:slug}}` | P | 표시명·실명·사이트·키트 이름 |
| 머리 | `{{v:n_posts}}` `{{v:date_from}}` `{{v:date_to}}` `{{v:n_sentences_hund}}` `{{v:corpus_sha8}}` `{{v:version}}` `{{v:skill_version}}` | S/R | 편수, 기간(YYYY.MM), 문장 수(백 단위), 코퍼스 해시, 문서 버전 |
| §0, §14 | `{{t:len_mean.rec}}` | T | 권장 평균 길이 |
| §1-2, §1-3 | `{{len:default}}` `{{len:valid}}` | P/R | 기본 분량(p25~p75), 유효 분량(min~max), 500 단위. profile.length_defaults 로 고정 가능 |
| §1-3, §7-1, §13 | `{{p:topic_words\|·}}` | P | 원래 소재 어휘(주제 바뀌면 억지로 넣지 않을 말) |
| §3 | `{{table:3}}` | T+S | 문장 길이 표 5행 |
| §3 규칙 6 | `{{int:para_first_len}}` `{{int:para_last_len}}` | S | 문단 첫·끝 문장 평균 |
| §4-1 | `{{conjfreq:8}}` | S.conj_total | 접속부사 전체 빈도 상위 8 |
| §4-1 | `{{one_in:pct_conj_start}}` `{{int:pct_conj_start}}` `{{t:pct_conj_start.minmax}}` `{{t:conj_consecutive.level}}` `{{t:conj_consecutive.range}}` | S/T | 문두 접속부사 빈도·허용 |
| §4-1, §14 | `{{p:conj_comma_allowed\|·}}` | P | 쉼표 허용 접속부사 |
| §4-2 | `{{table:4_2}}` `{{fraction:pct_list_or_go_comma}}` `{{t:pct_list_or_go_comma.level}}` | T/S | 쉼표 표, 나열·-고 비중 |
| §4-3 | `{{int:pct_para_with_paren}}` | S | 괄호 있는 문단 비율 |
| §5-1 | `{{table:5_1}}` | T/S | 종결 비율 표 |
| §5-3 | `{{one_in:pct_first_person_author_start}}` `{{int:pct_generic_first_person}}` `{{t:yeoreobun_dangsin.max}}` | S/T | 인칭 빈도 |
| §6-1 | `{{count:post_structure.도입=이력·경험}}` 등 4개 | W→R | 워크시트 표에서 도입 값을 센다 |
| §6-4 | `{{int:heading_forms.noun_pct}}` `…da_pct` `…imperative_pct` `…question_pct` `{{n:heading_forms.total}}` | S | 표제 형태 비율 |
| §6-5 | `{{t:closing_is_call_or_outlook.level}}` | T | 끝 규칙 등급 |
| §7-1 | `{{lexfreq:7}}` | S+P.lexicon_report | 참고 어휘 빈도(프로파일 지정 단어, 없으면 상위 7) |
| §7-2 | `{{table:7_2}}` | S.spelling_variants | 저자형≥2회이고 표준형의 3배 이상이면 행 생성 |
| §7-3 | `{{one_in:pct_tonghae}}` | S | '통해' 빈도 |
| §7-4, §8 | `{{t:sensory_total.level}}` `{{t:banned_total.level}}` `{{t:banned_total.max}}` `{{t:conj_comma_bad.level}}` `{{t:comma_after_subject.level}}` `{{t:yeoreobun_dangsin.level}}` | T | 등급·상한 |
| §7-5, §14 | `{{int:pct_contrast}}` `{{t:pct_contrast.max}}` `{{t:pct_contrast.level}}` | S/T | 대조 구문 |
| §7-6 | `{{t:ye_reul_deureo.max}}` `{{one_in:pct_numeric_sent}}` | T/S | 예시 표지·숫자 문장 |
| §10-1, §14 | `{{p:author}}` | P | 화자 보호 |
| §11-1 | `{{table:11_1}}` | T | 규칙 전체 표(라벨·기준·등급, targets 순서) |
| §14 | `{{t:*.rec}}` `{{t:*.minmax}}` `{{int:pct_saenggak}}` `{{int:pct_geot_ipnida}}` | T/S | 압축 프롬프트 숫자 |

## 워크시트 슬롯 (에이전트가 채움)

| 절 | 슬롯 | 형식 | 증거 |
|---|---|---|---|
| §6-1 | `post_structure` | 표 `slug \| 도입 \| 전개 \| 마무리`, 글마다 1행. 도입 값은 이력·경험 / 질문 / 정의·배경 / 결론·주장 중 하나 | 통독 판단 |
| §2 | `voice_one_liner` | 한 문장 (볼드는 템플릿이 붙임) | 통독 판단 |
| §2 | `voice_bullets` | 불릿 4개 | 통독 판단 |
| §2 | `writing_principles` | 번호 목록 5개, 각 **원칙.** 설명 | 기본값을 저자에 맞게 수정 |
| §3-3 | `long_sentence_example` | 큰따옴표 인용 1개 | 원문 |
| §3-4 | `short_roles` | 들여쓰기 3칸 `- 역할: 예문` 3~6줄 | 원문(B1) |
| §3-6 | `para_closing_endings` | 한 줄, 형태 2~3개 | 관찰 |
| §3 리듬 | `rhythm_quote` | 인용 블록(> …) 해설 1줄 + 원문 문단 | 원문 |
| §3 리듬 | `rhythm_examples` | 한 문단. `{{rhythm:slug:pN}}` 2개 + 기능 해설 | Part A 리듬 후보 |
| §4-1 | `conj_role_table` | 표 `역할 \| 쓰는 말 \| 쓰지 않는 말` | stats 접속부사 빈도 |
| §4-1 | `conj_note` | 한 문장 (숫자는 `{{n:conj_total.단어}}`) | stats |
| §4-1 | `conj_patterns` | 불릿 2~3개, 패턴은 작은따옴표 | 원문·관찰 |
| §4-2 | `comma_insert_exception` | 한 문장 | 원문 또는 "관찰되지 않았다" |
| §4-2 | `slash_examples` | 한 줄 | 원문 |
| §4-3 | `paren_uses` | 표 `용도 \| 예` | 원문(B2) |
| §4-4 | `punct_table` | 표 `부호 \| 용법` | 관찰 |
| §5-2 | `haeyo_examples` | 들여쓰기 3칸 `- \`-어미.\` 쓰임: 예문` | 원문(B7) |
| §5-2 | `ending_function_table` | 표 `기능 \| 종결` (빈도는 슬롯으로) | stats·원문 |
| §5-2 | `heading_da_example` | 큰따옴표 1개 | 표제(B10) |
| §5-3 | `mixed_person_example` | 큰따옴표 1개 | 원문(B8) |
| §5-3 | `reader_address` | 한두 문장 | 원문 |
| §6-1 | `opening_examples_experience/question/definition/claim` | 큰따옴표, " / " 구분 | Part A 첫 문단 |
| §6-2 | `body_order` | 번호 목록 6~8단계 | 통독·기본값 수정 |
| §6-4 | `heading_examples` | 큰따옴표, ", " 구분 | 표제(B10) |
| §6-5 | `closing_examples` | 들여쓰기 2칸 `- "예문"` 3~4줄 | Part A 끝 문단 |
| §6-6 | `question_position_example` `failure_examples` | 큰따옴표 | 원문 |
| §7-1 | `lexicon_table` | 표 `계열 \| 어휘`, 첫 세 줄이 주제 어휘 | stats lexicon·통독 |
| §7-2 | `gloss_examples` `tool_names` | 한 줄 | 원문(B2) |
| §7-3 | `habit_expressions` | 불릿 2~3개, 작은따옴표 | stats·관찰 |
| §7-4 | `emotion_examples` | 큰따옴표, ", " 구분 | 원문 |
| §7-5 | `contrast_pairs` | 불릿(들여쓰기 포함), 명사쌍 + 원문 예 1개 | 원문(B3) |
| §7-6 | `example_methods` | 번호 목록 4~7개 `**방식** — 예` | 원문(B4·B5) |
| §9 | `conversion_examples` | 표 `전 \| 후` 3~4행. '후'는 되도록 원문 문장 | 원문 (verify 가 counts 규칙으로 검사) |
| §9 | `conversion_commentary` | 한 문단 | — |
| §11-2 | `visual_checklist_extra` | `- [ ] …` 2~4줄 | 통독 판단 |
| §14 | `voice_short` `conj_short` `structure_short` `lexicon_short` | 각 한 줄 | 위 슬롯의 요약 |
| (검증) | `policy_flag_notes` | 불릿. targets `_flags` 마다 처리 내용 | derive 출력 |
| (검증) | `profile_proposals` | 불릿 또는 "반영 완료" | 통독 판단 |

인용 규칙: 큰따옴표 안 12자 이상은 verify ⑥이 코퍼스와 대조한다(공백·따옴표 무시, `…`로 나뉜 조각은 각각). 패턴·변수 표현은 작은따옴표로 쓴다. 인용 무결성 검사에서 제외되는 슬롯: `conversion_examples`, `voice_*`, `body_order`, `*_short`, `policy_flag_notes`, `profile_proposals`.
