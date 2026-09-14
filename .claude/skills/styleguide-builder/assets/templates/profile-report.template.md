# {{p:display}} 문체 프로파일 (자동 생성)

- 코퍼스: {{p:site}} {{v:n_posts}}편 ({{v:date_from}} ~ {{v:date_to}}), 본문 {{k:n_sentences}}문장 / {{k:n_paragraphs}}문단 / {{k:chars}}자. sha256 `{{v:corpus_sha8}}`. 버전 {{v:version}}.
- 이 문서의 숫자는 `stats.md`와 같다. 해석은 `{{p:display}} 글쓰기 문체 가이드라인.md`에 있다.

## 1. 문장 길이 및 호흡

| 지표 | 값 |
|---|---|
| 평균 문장 길이 | {{n:len_mean}}자 (중앙값 {{n:len_median}}, 표준편차 {{n:len_sd}}, {{n:words_mean}}어절) |
| 단문(≤35) : 중문(36~70) : 장문(>70) | {{n:pct_short_le35}}% : {{n:pct_mid_36_70}}% : {{n:pct_long_gt70}}% |
| 100자 초과 | {{n:pct_xlong_gt100}}% |
| 문단당 문장 | 평균 {{n:sent_per_para_mean}} / 중앙값 {{n:sent_per_para_median}} / 3~4문장 문단 {{n:pct_para_3_4}}% / 1문장 문단 {{n:pct_para_1}}% |
| 문단 첫 문장 → 끝 문장 평균 길이 | {{n:para_first_len}}자 → {{n:para_last_len}}자 |
| 90자 이상 장문 다음 문장 | 평균 {{n:after_long_next_mean}}자, 40자 이하로 떨어지는 비율 {{n:after_long_pct_le40}}% (표본 {{n:after_long_n}}) |

허용 범위(targets): 평균 {{t:len_mean.range}}, 100자 초과 {{t:pct_xlong_gt100.range}}, 문단당 문장 {{t:sent_per_para_mean.range}}.

## 2. 접속 부사 및 부호

| 지표 | 값 |
|---|---|
| 문두 접속부사 문장 | {{n:pct_conj_start}}% ({{one_in:pct_conj_start}}문장에 1개, 허용 {{t:pct_conj_start.minmax}}%) |
| 접속부사 전체 빈도 | {{conjfreq:12}} |
| 접속부사 뒤 쉼표(허용 제외) / 접속부사 연속 | {{n:conj_comma_bad}} / {{n:conj_consecutive}} |
| 문장당 / 문단당 쉼표 | {{n:commas_per_sent}} / {{n:commas_per_para}} |
| 쉼표 없는 문장 / 2개 이상 | {{n:pct_sent_no_comma}}% / {{n:pct_sent_2plus_comma}}% |
| 나열·'-고,' 쉼표 비중 / 주어 뒤 쉼표 | {{n:pct_list_or_go_comma}}% / {{n:comma_after_subject}} |
| 괄호 있는 문단 / 괄호 수 / 슬래시 / 영문 병기 / 느낌표 / 이모티콘 | {{n:pct_para_with_paren}}% / {{n:parens}} / {{n:slashes}} / {{n:eng_gloss}} / {{n:exclaim}} / {{n:emoticons}} |

## 3. 종결어미

| 지표 | 값 |
|---|---|
| 합쇼체 / 해요체 / -죠 / 해라체 / 기타 | {{n:pct_hapsyo}}% / {{n:pct_haeyo}}% / {{n:pct_jyo}}% / {{n:pct_haera}}% / {{n:pct_other_ending}}% |
| 의문문 | {{n:pct_question}}% |
| '~생각합니다' / '~것 같습니다' / '~것입니다' 종결 | {{n:pct_saenggak}}% / {{n:pct_geot_gatda}}% / {{n:pct_geot_ipnida}}% |
| 해요체 연속 | {{n:consecutive_haeyo}}회 |
| 문두 '저/제' / '내·나' 포함 / 한 문장 혼용 | {{n:pct_first_person_author_start}}% / {{n:pct_generic_first_person}}% / {{n:mixed_first_person}} |
| 과거형 문장 | {{n:pct_past}}% |

## 4. 정보 배열

| 지표 | 값 |
|---|---|
| 시작 유형(자동 분류) | {{n:opening_types}} |
| 권유·전망·감사로 끝나는 글 / 요약으로 끝나는 글 / 느낀 점 섹션 있는 글 | {{n:closing_call_or_outlook_posts}} / {{n:closing_summary_posts}} / {{n:lesson_section_posts}} (총 {{v:n_posts}}) |
| 표제 형태 | 명사구 {{n:heading_forms.noun_pct}}%, -다 {{n:heading_forms.da_pct}}%, 청유·명령 {{n:heading_forms.imperative_pct}}%, 의문 {{n:heading_forms.question_pct}}%, 번호 {{n:heading_forms.numbered_pct}}% (총 {{n:heading_forms.total}}) |
| 글 길이(본문 글자) | p10 {{k:post_chars_p10}} / 중앙 {{k:post_chars_p50}} / p90 {{k:post_chars_p90}} |

## 5. 어휘 및 구조

| 지표 | 값 |
|---|---|
| 어휘 빈도(watchlist) | {{lexfreq:20}} |
| 강조 부사 | {{n:intensifiers}} |
| 대조 구문 | {{n:contrast_constructions}} ({{n:pct_contrast}}%) |
| '통해' | {{n:tonghae}} ({{n:pct_tonghae}}%) |
| 숫자 포함 문장 | {{n:pct_numeric_sent}}% |
| '예를 들어' 류 / 여러분·당신 / 감각어 / 금지어 | {{n:ye_reul_deureo}} / {{n:yeoreobun_dangsin}} / {{n:sensory}} / {{n:banned}} |
| 표기 변이 | {{n:spelling_variants}} |
