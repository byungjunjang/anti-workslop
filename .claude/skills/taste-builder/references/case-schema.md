# 케이스 스키마

## raw 스냅샷 (`taste/cases/raw/<YYYY-MM-DD>-<slug>.json`)

에이전트가 `Artifact action: comments` 결과를 옮겨 적는다. 코멘트 `text`는 원문 그대로.

| 필드 | 내용 |
|---|---|
| `artifact_url`, `artifact_title` | 발행 정보. `taste/artifacts.json`에서 복사 |
| `source_file` | 원본 HTML 절대 경로 |
| `collected_at` | ISO 8601, 시간대 포함 |
| `doc.project` / `doc.genre` / `doc.base_guideline` / `doc.version` | artifacts.json의 값 |
| `threads[]` | 스레드마다 아래 |
| `threads[].thread_id` | Artifact 스레드 id. 중복 제거 키(URL과 조합) |
| `threads[].anchor.quote` | 사용자가 선택한 텍스트. Artifact 결과에 있으면 그대로, 없으면 코멘트가 가리키는 문장을 원본에서 찾아 적고 `note`에 "앵커 추정"이라 쓴다 |
| `threads[].anchor.section` | 원본 HTML에서 인용이 속한 섹션 경로 (예: `의장 판정 > 권고`). 못 찾으면 `전체` |
| `threads[].anchor.context` | 원본에서 인용 앞뒤 60자. 없으면 빈 문자열 |
| `threads[].comments[]` | `{author: "user"|"claude", text, at}`. 사용자 코멘트만 케이스가 된다 |
| `threads[].activated` | 사용자가 Send to Claude로 활성화했는지 |
| `threads[].kind_hint` | 태그 없는 코멘트에 에이전트가 붙이는 분류 (`지적`·`칭찬`·`고침`·`규칙`·`질문`). 선택 |
| `threads[].rewrite` | 태그 없는 코멘트에서 고친 문장을 읽어낼 수 있을 때. 선택 |

## 케이스 (`taste/cases/cases.jsonl` 한 줄)

| 필드 | 값 | 채우는 주체 |
|---|---|---|
| `case_id` | `T-0001` 순번 | ingest |
| `date` | 수집일 | ingest |
| `source` | `{artifact_url, artifact_title, version, thread_id, raw_file}` | ingest |
| `doc` | `{project, genre, base_guideline, section}` | ingest |
| `anchor` | `{quote, context}` | ingest |
| `comment` | 사용자 코멘트 문자열 배열 (항상 배열) | ingest |
| `kind` | `지적`·`칭찬`·`고침`·`규칙`·`질문`·`미분류` | 태그면 ingest, 아니면 kind_hint |
| `kind_source` | `tagged`·`inferred` | ingest |
| `rewrite` | `[고침]` 뒤 문장 또는 raw의 rewrite | ingest |
| `rule_ids` | 규칙 ID 배열 | 에이전트 (`--map`) |
| `status` | `신규`·`반영`·`보류` | 에이전트 (`--map --status`) |
| `note` | 에이전트 해석 메모 | 에이전트 (`--map --note`) |

원장은 추가 전용. `rule_ids`·`status`·`note` 외의 필드는 바꾸지 않는다. `미분류` 케이스는 증류 단계에서 에이전트가 `--map --note "분류: 지적(추정)"`으로 해석을 남기되 `kind` 자체는 바꾸지 않는다.

## Artifact comments 결과 필드 (첫 collect 때 확인해 채운다)

| Artifact 결과 | raw 필드 |
|---|---|
| `Thread <id>` 행의 id | `thread_id` |
| `[on text]` 행 (사용자가 드래그한 텍스트) | `anchor.quote` |
| `[location]` 행 (가장 가까운 소제목) | `anchor.section` |
| `[the user, sent to you — <시각>]` 속성 행 + 들여쓴 본문 행 · `[Claude (via the user) — <시각>]` | `comments[]` (author `user` / `claude`) |
| 상태 행의 `Claude: activated` | `activated` |
| (없음 — 시각은 분 단위, 시간대 표기 없음. 2026-09-11 첫 수집에서 확인) | `at` 에 `:00Z` 를 붙여 기록 |
