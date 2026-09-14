# 파이프라인 계약

프로젝트 루트에서 실행한다. `S=.claude/skills/styleguide-builder/scripts`, `K=styleguides/<slug>`. Windows 는 항상 `python -X utf8`.

| 단계 | 명령 | 읽음 | 씀 | 멱등 |
|---|---|---|---|---|
| 0 | `python -X utf8 $S/init_kit.py --out $K --slug <slug> --author <실명> --display <표시명> --site <사이트> [--profile P]` | assets/profile.default.json | `$K/kit.json`, `$K/profile.json` | 기존 키트는 `--force` 없이 덮어쓰지 않음 |
| 1 | `python -X utf8 $S/collect.py --kit $K --sitemap URL` (또는 `--rss URL` / `--urls FILE` / `--md-dir DIR [--recursive]`) [`--selector CSS` `--author NAME` `--include-pattern RE` `--since YYYY-MM-DD`] | urls.txt, html 캐시 | `corpus/{urls.txt, html/, posts/, posts.json, posts.sha256, sources.json, boilerplate.json, skipped.json}` | urls.txt 있으면 재조회 안 함(`--discover`), html 있으면 재수집 안 함(`--refresh`). 출력은 (발행일, slug) 정렬 |
| 2a | `python -X utf8 $S/analyze_corpus.py --kit $K [--exclude-boilerplate]` | posts.json, profile.json, metrics.py | `stats.json`, `stats.md` | 타임스탬프 없음. 입력 해시 3종 기록 |
| 2b | `python -X utf8 $S/derive_targets.py --kit $K [--print-diff]` | stats.json, profile.json | `targets.json` | hard 가 envelope 를 못 담으면 exit 1 |
| 2c | `python -X utf8 $S/selftest.py --kit $K` | 전부 | (없음) | 8군 검사 |
| 3 | `python -X utf8 $S/extract_reading_pack.py --kit $K` | posts.json, stats.json | `reading-pack.md` (+ batch) | 결정적 |
| 3' | 에이전트가 `reading-worksheet.md` 작성 (템플릿: assets/reading-worksheet.template.md) | pack, posts | `reading-worksheet.md` | 유일한 정성 입력 |
| 3'' | profile.json 수정 후 2a→2b 재실행 | | | 한 번만 |
| 4 (선택) | `python -X utf8 $S/render_guideline.py --kit $K --version V --template assets/templates/profile-report.template.md --out $K/docs/style-profile.md` | 위 전부 | 프로파일 보고서 | |
| 5 | `python -X utf8 $S/render_guideline.py --kit $K --version <YYYY-MM-DD> [--allow-todo]` | template, worksheet, stats, targets, profile | `<표시명> 글쓰기 문체 가이드라인.md`, `render-manifest.json` | 같은 입력 → 같은 바이트 |
| 6 | `python -X utf8 $S/verify_guideline.py --kit $K --report` | 전부 | `verification.json` | 8항목, 실패 시 exit 1 |
| 검사 | `python -X utf8 $S/check_style.py --kit $K 초고.md [--strict] [--subset counts]` | targets, profile | (없음) | 읽기 전용 |

## 입력 고정(스냅샷)

`kitlib.assert_snapshot` 이 2b 이후 모든 단계에서 확인한다: `posts.json` 해시 == `posts.sha256` == `stats.corpus_sha256`, `profile.json` 해시 == `stats.profile_sha256`, `metrics.py` 해시 == `stats.metrics_sha256`, `targets.corpus_sha256` == 코퍼스. 하나라도 다르면 무엇을 다시 실행할지 한국어로 알리고 멈춘다.

## 수정 경로

| 고치고 싶은 것 | 손대는 파일 | 이후 |
|---|---|---|
| 정성 서술·예문 | reading-worksheet.md | 5 → 6 |
| 어휘·표기·금지어·주제어·분량 기본값 | profile.json | 2a → 2b → 5 → 6 |
| 규칙 상한·등급 | profile.json (policy_rules / target_overrides) | 2b → 5 → 6 |
| 고정 문구(스파인) | assets/templates/blog.template.md (모든 저자에 영향) | 5 → 6, template-provenance.md 에 기록 |
| 코퍼스 | collect (`--discover`/`--refresh`) | 2a → 2b → 3 → 워크시트 점검 → 5 → 6 |
| 완성본 직접 편집 | **하지 않는다** (verify ② 가 실패) | |

## 갱신 모드 (블로그에 글이 늘었을 때)

1. `collect.py --kit $K --discover` → 새 URL 이 urls.txt 에 추가되고 새 글만 내려받는다.
2. `analyze_corpus.py` → `derive_targets.py --print-diff` 로 범위 변화를 본다.
3. `extract_reading_pack.py` → 새 글의 Part A 를 읽고 워크시트 `post_structure` 에 행을 추가한다. 예문 슬롯은 필요할 때만 보강한다.
4. `render_guideline.py --version <새 날짜>` → `verify_guideline.py --report`.
5. 가이드라인 머리의 버전·코퍼스 해시가 바뀐다. 이전 판은 필요하면 따로 보관한다.

## 오류 표

| 증상 | 원인 | 조치 |
|---|---|---|
| `beautifulsoup4 가 필요합니다` | HTML 수집 의존성 없음 | `pip install beautifulsoup4 lxml` (md-dir 은 불필요) |
| collect 결과 `strategies=['largest-hangul-block']` 또는 본문이 짧음 | 컨테이너 자동 선택 실패 | 글 하나의 HTML 을 보고 `--selector CSS` 지정 |
| `[skip] … author=` | 다른 저자 글 제외됨 | 의도한 것인지 skipped.json 확인 |
| derive `[violation]` | hard 범위가 원문보다 좁음 | profile.target_overrides/policy_rules 확인, 보통은 정책 상한을 넓힌 flag 로 해결 |
| selftest [5] 실패 (대조군 통과) | 저자 문체가 AI 초고와 가까움 | 저자 맞춤 대조군 작성 후 profile.control_sample 지정, 또는 문턱 조정 + 기록 |
| render `채워지지 않은 워크시트 슬롯` | 슬롯 비어 있음 | 목록의 슬롯을 채운다. 초안 확인은 `--allow-todo` |
| verify ② 실패 | 완성본을 손으로 고쳤거나 워크시트 변경 후 렌더 안 함 | 워크시트만 고치고 다시 render |
| verify ⑥ 실패 | 인용이 원문과 다름 | reading-pack 에서 원문 그대로 다시 복사 |
| verify ⑦c 실패 | 변환 예시 '후' 문장이 횟수 규칙 위반 | 원문 문장으로 교체하거나 위반 표현 제거 |
| `입력이 변경되었습니다` | posts.json 이 바뀜 | collect 를 다시 돌리고 2a 부터 재실행 |
| n_posts < 5 | 코퍼스가 작음 | 범위가 넓어진다(여유 2배). 결과를 경향으로만 쓴다 |
