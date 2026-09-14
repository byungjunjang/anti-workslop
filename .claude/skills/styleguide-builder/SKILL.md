---
name: styleguide-builder
description: |
  한 저자의 한국어 글 코퍼스(블로그 사이트맵/RSS/URL 목록/로컬 .md 폴더)에서 14개 절 고정 구조의 「글쓰기 문체 가이드라인」과
  검사 키트(corpus·stats·targets.json·check_style)를 재현 가능하게 만드는 스킬. 숫자는 스크립트만 쓰고, 에이전트는 정성
  워크시트만 채우며, 완성본은 재렌더 바이트 동일성으로 검증한다.
  Use when the user says "문체 가이드라인 만들어", "이 블로그 문체 분석해서 가이드라인", "저자 문체 프로파일", "문체 키트",
  "check_style 만들어", "author style guide", "style guideline from corpus", "/styleguide-builder", or wants an
  agent-usable writing-style spec for one author. Also for "코퍼스 갱신", "가이드라인 다시 만들어", "문체 가이드 버전 올려" on an
  existing styleguides/<slug>/. Not for 보고서·개조식 문서(별도 키트), not for checking a single draft (check_style 직접 실행).
metadata:
  author: byung
  version: 0.1.0
---

# Style Guide Builder

## Overview

anti-workslop 의 기본 줄글 가이드(장피엠)를 내 문체로 바꾸는 방법이 이 스킬이다. 내 글 코퍼스로 키트를 만들고 Step 7 에서 등록하면 윤문이 그 가이드를 쓴다.

산출물은 둘이다. (1) `styleguides/<slug>/<표시명> 글쓰기 문체 가이드라인.md` — 첨부 최종본과 같은 14개 절 구조. (2) 같은 폴더의 검사 키트 — `corpus/`, `stats.md`, `targets.json`, `profile.json`, 그리고 `check_style.py --kit`로 새 초고를 검사하는 능력.

두 원칙이 이 스킬의 전부다.
- **숫자는 render_guideline.py 만 적는다.** 가이드라인의 모든 수치는 stats.json / targets.json 에서 슬롯으로 채워진다. 손으로 숫자를 옮기지 않는다.
- **에이전트는 `reading-worksheet.md` 만 편집한다.** 완성본을 직접 고치면 verify ②(재렌더 바이트 동일)가 실패한다. 고칠 것은 워크시트·profile.json·(모든 저자에 영향을 주는) 템플릿뿐이다.

가이드라인의 고정 절(규칙 등급, 우선순위, 작업 종류, 보존·멱등성, 점검표 판정, 새 글 작성 순서, 회귀 검수 예시)은 코퍼스와 무관한 텍스트라 매번 그대로 복사된다. 저자별로 달라지는 것은 수치 표·예문·어휘·목소리뿐이다. 절별 출처는 `references/template-provenance.md`.

## When NOT to use

- 보고서·개조식·명사형 종결 문서: 지표가 다르다(별도 기준: 「개조식 보고서 작성 가이드라인」). 이 스킬은 산문형 블로그·설명문만 다룬다.
- 초고 하나를 검사만 할 때: `python -X utf8 <scripts>/check_style.py --kit styleguides/<slug> 초고.md`.
- 코퍼스가 4편 이하: envelope 가 무의미하다. 그래도 돌리면 여유를 2배로 잡고 경고한다. 결과는 경향으로만 쓴다.

## Paths

- 스킬 디렉터리: `.claude/skills/styleguide-builder/` (프로젝트 루트 기준). 아래에서 `$S` = `.claude/skills/styleguide-builder/scripts`, `$K` = `styleguides/<slug>`.
- 모든 명령은 프로젝트 루트에서 `python -X utf8 $S/<script>.py` 로 실행한다(Windows 한글 출력). 스크립트가 없으면 추측해서 짜지 말고 사용자에게 알린다.
- 의존성: 표준 라이브러리. HTML 수집만 `beautifulsoup4`(+`lxml` 선택). `--md-dir` 경로는 bs4 없이 동작.
- 단계별 입출력·멱등 계약·오류 표는 `references/pipeline.md`.

## Step 0: 입력 확정

| 입력 | 확인할 것 | 기본값 |
|---|---|---|
| 저자 실명 / 표시명 | 보존 규칙과 파일명에 쓰임 | 표시명 = 실명 |
| 코퍼스 소스 | 사이트맵 URL / RSS URL / URL 목록 파일 / 로컬 .md 폴더 | Ghost 블로그면 `https://<site>/sitemap-posts.xml` |
| 장르 | blog 만 지원 | blog |
| 화자 정책 | 저자 이력을 다른 화자에 이식 금지(기본). 예외가 있으면 profile.speaker_policy_note | 기본 |
| 출력 위치 | `styleguides/<slug>/` | slug = 사이트 이름 또는 저자 영문 |
| 기존 키트 | 이미 있으면 갱신 모드 | — |

막히는 질문만 한다: 소스에 접근할 수 없을 때, 저자가 여럿 섞여 있을 때, 장르가 blog 가 아닐 때. 나머지는 기본값으로 진행하고 Step 7 에서 알린다.

## Step 1: 수집

```bash
python -X utf8 $S/init_kit.py --out $K --slug <slug> --author <실명> --display <표시명> --site <사이트>
python -X utf8 $S/collect.py --kit $K --sitemap <URL>        # 또는 --rss URL | --urls FILE | --md-dir DIR --recursive
```

- 출력의 `strategies` 를 본다. `largest-hangul-block` 이나 본문 글자 수가 비정상이면 HTML 하나를 열어 `--selector CSS` 를 지정하고 `--refresh` 없이 다시 실행한다(캐시 재사용).
- 다른 저자 글이 섞이면 `--author 이름`. `skipped.json` 을 확인한다.
- `boilerplate.json` 의 exact/tail 블록(CTA 등)을 훑는다. 기본은 **코퍼스에 포함**(저자의 마무리 습관이므로). 광고성 반복이 명백하면 `analyze_corpus.py --exclude-boilerplate`.
- 글이 5편 미만이면 경고를 그대로 사용자에게 전달한다.

## Step 2: 정량

```bash
python -X utf8 $S/analyze_corpus.py --kit $K
python -X utf8 $S/derive_targets.py --kit $K --print-diff
python -X utf8 $S/selftest.py --kit $K
```

- `stats.md` 를 읽는다. 접속부사·종결어미·표기 변이·어휘 빈도가 통독의 지도다.
- `--print-diff` 의 `[flag]` 를 적어 둔다(워크시트 `policy_flag_notes` 에 처리 내용을 쓴다). 정책은 `references/targets-policy.md`.
- selftest [5](대조군 실패 ≥5) 가 실패하면 저자 문체가 AI 초고와 가깝다는 뜻이다. 규칙을 좁히지 말고 저자 맞춤 대조군을 써서 `profile.control_sample` 로 지정하거나 문턱을 낮추고 기록한다.

## Step 3: 정성 통독

```bash
python -X utf8 $S/extract_reading_pack.py --kit $K
cp .claude/skills/styleguide-builder/assets/reading-worksheet.template.md $K/reading-worksheet.md
```

- `reading-pack.md` Part A(글별 첫·끝 문단, 표제, 리듬 후보)는 전부 읽는다. 전독 대상 글(20편 이하면 전부, 초과면 pack 머리의 목록)은 `corpus/posts/<slug>.md` 로 읽는다.
- 워크시트를 채운다. 슬롯 형식·증거 유형은 `references/slot-catalog.md`, 고르는 기준은 `references/reading-guide.md`. 인용은 **원문 그대로**, 숫자는 슬롯(`{{n:…}}`, `{{one_in:…}}`, `{{rhythm:slug:pN}}`)으로만.
- `post_structure` 표(글마다 도입 유형: 이력·경험 / 질문 / 정의·배경 / 결론·주장)를 먼저 채운다. §6-1 편수가 여기서 나온다.
- `profile_proposals` 에 적은 topic_words·lexicon_report·spelling_pairs·banned 를 `profile.json` 에 반영하고 Step 2 를 한 번 다시 돌린다.
- 20편 초과면 `reading-pack.batch-K.md` 를 서브에이전트에 나눠 인용 후보만 받는다(`reading-guide.md` 분할 규칙).

## Step 4: 프로파일 보고서 (선택)

```bash
mkdir -p $K/docs && python -X utf8 $S/render_guideline.py --kit $K --version <YYYY-MM-DD> \
  --template .claude/skills/styleguide-builder/assets/templates/profile-report.template.md --out $K/docs/style-profile.md
```

5개 지표(문장 길이·호흡 / 접속·부호 / 종결어미 / 정보 배열 / 어휘·구조)의 숫자만 담은 보고서. 사용자가 분석 근거를 따로 원할 때만.

## Step 5: 렌더

```bash
python -X utf8 $S/render_guideline.py --kit $K --version <YYYY-MM-DD>
```

채워지지 않은 슬롯이 있으면 목록을 내고 exit 1 이다. 그 슬롯을 워크시트에 채우고 다시 실행한다. 초안을 먼저 보고 싶으면 `--allow-todo`. 렌더 후 완성본을 읽어 마크다운이 깨진 곳(표 열 수, 들여쓰기)을 찾으면 **워크시트의 해당 슬롯을** 고친다.

## Step 6: 검증

```bash
python -X utf8 $S/verify_guideline.py --kit $K --report
```

8항목: 스냅샷 해시 → 재렌더 바이트 동일 → 표제 1회·순서 → 잔여 슬롯 없음 → §11-1 == targets → 워크시트 인용이 코퍼스에 존재 → check_style(원문 전부 hard 통과, 대조군 실패, 변환 예시 '후' 문장 counts 통과) → selftest. 실패 항목만 워크시트·profile 을 고쳐 Step 5 부터 반복한다. 세 번 반복해도 남으면 사용자에게 어떤 항목이 왜 남는지 보고한다.

## Step 7: 전달

- 파일: 가이드라인 경로, `stats.md`, `targets.json`, `verification.json`, (선택) `docs/style-profile.md`.
- 한 문단으로: 편수·기간·문장 수, `_flags` 처리, 기본값으로 정한 것(소스·slug·보일러플레이트 포함 여부), 저자 문체의 두드러진 세 가지.
- 사용법: `python -X utf8 $S/check_style.py --kit $K 초고.md --strict`, 800자 이하 글은 `--subset counts`.
- 가이드라인 §14 블록이 시스템 프롬프트에 붙일 압축본이라는 것을 알린다.
- 등록: `python -X utf8 $S/register_guide.py --kit $K`. 검증을 통과한 키트만 받는다. 등록하면 anti-workslop 에서 `--guide <표시명>` 으로 윤문하고, 장르 힌트의 레이어 줄에 이름이 나온다. 뺄 때는 `--remove <표시명>`. `styleguides/README.md` 표에 한 행을 더하라고 알린다.

## 갱신 모드 (기존 키트, 글이 늘었을 때)

`collect.py --kit $K --discover` → `analyze_corpus.py` → `derive_targets.py --print-diff`(범위 변화 확인) → `extract_reading_pack.py` → 새 글 Part A 를 읽고 워크시트 `post_structure` 에 행 추가, 예문은 필요할 때만 보강 → `render_guideline.py --version <새 날짜>` → `verify_guideline.py --report`. 숫자를 손으로 고치지 않는다.

## Output

| 산출물 | 경로 |
|---|---|
| 가이드라인 | `styleguides/<slug>/<표시명> 글쓰기 문체 가이드라인.md` |
| 통계 | `styleguides/<slug>/stats.md`, `stats.json` |
| 목표치·프로파일 | `styleguides/<slug>/targets.json`, `profile.json` |
| 코퍼스 | `styleguides/<slug>/corpus/` (urls.txt, html/, posts/, posts.json, posts.sha256, sources.json, boilerplate.json) |
| 정성 입력 | `styleguides/<slug>/reading-pack.md`, `reading-worksheet.md` |
| 검증 기록 | `styleguides/<slug>/verification.json`, `render-manifest.json` |
| 등록 | `.claude/skills/anti-workslop/references/base-guidelines.json` 에 그 가이드의 행 |
| (선택) 프로파일 보고서 | `styleguides/<slug>/docs/style-profile.md` |

## Error Handling

| 상황 | 조치 |
|---|---|
| `beautifulsoup4 가 필요합니다` | `pip install beautifulsoup4 lxml` 안내. md 폴더 소스면 불필요 |
| 컨테이너 미검출 / 본문이 짧음 | HTML 하나 열어 `--selector` 지정 |
| RSS 가 요약본만 제공 | RSS 는 링크 수집용. 글 본문은 각 링크를 내려받는다 |
| derive `[violation]` | hard 범위가 저자보다 엄격. profile.policy_rules 상한 확인, 보통 flag 로 자동 해결 |
| selftest [5] 대조군 통과 | 저자 맞춤 대조군 작성 → profile.control_sample |
| render 미충족 슬롯 | 워크시트 채우기. `--allow-todo` 로 초안 확인 |
| verify ② 실패 | 완성본 직접 편집 금지. 워크시트 고치고 재렌더 |
| verify ⑥ 인용 미발견 | reading-pack 에서 원문 그대로 다시 복사 |
| verify ⑦c | 변환 예시 '후' 문장을 원문 문장으로 교체 |
| `입력이 변경되었습니다` | collect 재실행 후 Step 2 부터 |
| genre ≠ blog | 이 스킬 범위 밖. 사용자에게 알린다 |

## References

- `references/pipeline.md` — 명령 순서·입출력 계약·멱등성·갱신 모드·오류 표
- `references/slot-catalog.md` — 템플릿 슬롯 전수(출처·형식·증거)
- `references/reading-guide.md` — 정성 통독 요령, 서브에이전트 분할
- `references/targets-policy.md` — 목표치 도출 정책, _flags, 대조군
- `references/template-provenance.md` — 절별 출처, 통합본 불일치 정리, 템플릿 버전
- `assets/templates/blog.template.md`, `assets/reading-worksheet.template.md`, `assets/profile.default.json`, `assets/profiles/jangpm.profile.json`, `assets/samples/ai_draft.md`
- `tests/README.md` — 인수·스모크 기준, RED 기준선
