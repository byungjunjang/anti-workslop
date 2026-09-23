# anti-workslop

한국어 글에서 AI 티를 줄이고, 장르·저자 문체·개인 취향에 맞게 퇴고합니다. 자동 검사와 독립 의미 검토를 구분해 결과와 미결을 알려줍니다.

## 실제 글의 전후 사례

장피엠 가이드와 현재 개인 취향으로 최근 포스트 세 편을 퇴고했습니다. 사용자 품질 평가는 아직 받지 않았으며, 실패와 미결도 함께 보여줍니다. **확인 필요인 퇴고본은 게시용 완성본이 아닙니다.**

### 산업별 기업 AX 사례

자동 검사 **실패** · 의미 검토 **확인 필요**.

**전**

> 기능은 만들었는데 일은 안 바뀐 상태입니다. 낯설지 않은 장면일 겁니다. 그렇다면 잘 굴러가는 곳들은 무엇을 다르게 했을까요?

**후**

> 기능을 만드는 데까지는 갔지만 현장의 일은 안 바뀐 상태입니다. AI를 도입한 뒤 업무가 달라진 기업들은 무엇을 다르게 했을까요?

변경 이유: 설명 예고를 줄이고 질문의 대상을 업무가 달라진 기업으로 명시했습니다.

### Claude Cowork 마케팅 시스템

자동 검사 **통과** · 의미 검토 **독립 검토 완료**.

**전**

> 컨텍스트 셋업(0~1단계)에서 시작해 자동화와 배포(5~6단계)까지, 한 칸씩 따라 오르시면 됩니다.

**후**

> 컨텍스트를 준비하는 0~1단계부터 자동화와 배포를 다루는 5~6단계까지 작업 방식을 차례로 확장합니다.

변경 이유: 사다리 비유를 작업 순서로 풀고 단계 숫자는 보존했습니다.

### 메타프롬프팅으로 나만의 스킬 만들기

자동 검사 **실패** · 의미 검토 **확인 필요**.

**전**

> 이 글은 그린코끼리 AI의 「클로드 AI 업무 자동화 3단계」 영상을 '메타 프롬프팅' 렌즈로 다시 풀어낸 것입니다.

**후**

> 이 글은 그린코끼리 AI의 「클로드 AI 업무 자동화 3단계」 영상을 '메타 프롬프팅' 관점에서 재해석한 글입니다.

변경 이유: '렌즈'라는 은유를 '관점'으로 바꿔 표현을 직접적으로 다듬었습니다.

## 코드와 LLM의 작업 절차

[전체 흐름](docs/pipeline-review-2026-09-21_fable/workflow/01-overview.svg) · [검수·수정 흐름](docs/pipeline-review-2026-09-21_fable/workflow/02-review-loop.svg) · [실행 기록과 단계별 피드백](docs/pipeline-review-2026-09-21_fable/workflow/README.md)

## 처음 쓰는 분께

원칙은 누구에게나 같지만 문체와 취향은 사람마다 다르다. 저장소에 든 가이드 둘은 출발점이고, 오래 쓸수록 내 가이드와 내 취향으로 바꾸는 편이 결과가 좋다.

1. **바로 써 보기.** Claude Code 또는 Codex 에서 이 폴더를 열고 「이 글 윤문해줘」라고 한다. 줄글은 장피엠 가이드(이 저장소 저자의 블로그 문체), 보고서는 개조식 가이드(공공 기관 보고서 문체)로 고친다. 취향 문서가 없어도 돈다.
2. **내 문체 가이드 만들기.** 내가 쓴 글 다섯 편 이상을 모은다. 블로그 주소나 로컬 `.md` 폴더면 된다. 「내 블로그 문체 가이드 만들어줘」로 styleguide-builder 를 돌리고, 검증이 끝나면 `register_guide.py` 로 등록한다. 그 뒤 줄글은 내 가이드로 고친다. 지금은 블로그형 줄글만 만든다.
3. **내 취향 쌓기.** AI 결과물 하나를 「코멘트 달 수 있게 올려줘」로 올린다. 읽다가 걸리는 문장마다 「내가 쓴다면 이렇게 쓴다」를 코멘트로 단다. 「코멘트 반영해줘」로 모으면 `taste/writing-taste.md` 에 규칙이 생긴다. 같은 방향의 코멘트가 모일수록 규칙이 단단해지고 다음 윤문에 들어간다.
4. **다른 프로젝트에서 부르기.** 스킬은 이 폴더 안에서만 보인다. 어디서든 쓰려면 `~/.claude/skills/anti-workslop/SKILL.md` 에 경로만 알려 주는 진입 스킬을 둔다.

```markdown
---
name: anti-workslop
description: 한국어 문서 윤문·퇴고·AI 티 제거·검토는 anti-workslop 파이프라인으로 한다. 트리거 · "윤문해줘", "퇴고해줘", "AI 티 없애줘", "검토만", "/anti-workslop".
---
본체는 `<이 폴더 경로>/.claude/skills/anti-workslop/SKILL.md` 다. 그 파일을 읽고 따르며, 상대 경로 명령은 `<이 폴더 경로>` 에서 돌린다. 원칙·스타일가이드·취향은 그 폴더의 것을 쓴다.
```

`taste/` 에는 내 코멘트와 원문 인용이 쌓인다. 고객 문서를 다룬다면 이 폴더를 공개 저장소에 올리지 않는다. 배포본의 `.gitignore` 가 기본으로 막아 둔다.

## Codex에서 사용하기

Codex에서 이 프로젝트 폴더를 열고 새 작업을 시작한다. `AGENTS.md`에 프로젝트 지침이 있고, `.agents/skills/`에 세 스킬의 Codex 진입점이 있다. 명령 대신 다음처럼 요청하면 된다.

- 「이 파일을 내 취향에 맞게 윤문해줘」
- 「이 보고서는 고치지 말고 검토만 해줘」
- 「내 글 폴더로 문체 가이드 만들어줘」
- 「이 표현은 다음부터 쓰지 않도록 취향으로 기록해줘」

직접 선택하려면 `$anti-workslop`, `$styleguide-builder`, `$taste-builder`를 사용한다. 스킬이 목록에 보이지 않으면 Codex를 다시 시작한다. 프로젝트 지침은 새 작업에서 확인한다. [공식 스킬 안내](https://learn.chatgpt.com/docs/build-skills) · [AGENTS.md 안내](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

Codex와 Claude Code는 `.claude/skills/`의 Python 구현, `principles/`, `styleguides/`, `taste/`를 공유한다. `.agents/skills/`에는 진입 지침만 두므로 구현을 두 벌로 관리하지 않는다. 다른 프로젝트에 진입 스킬을 따로 설치할 때는 Codex의 `~/.agents/skills/anti-workslop/SKILL.md`에서 이 프로젝트의 `.agents/skills/anti-workslop/SKILL.md`를 가리킨다. 현재 설정은 이 프로젝트 범위다.

Python이 필요하며 기본 검사에는 추가 패키지가 없다. 블로그 HTML 을 수집하는 `styleguide-builder` 는 `beautifulsoup4` 와 `lxml` 을 쓰므로 클론한 뒤 한 번 설치한다.

```bash
pip install -r requirements.txt
```

`lxml` 은 선택이 아니다. 없으면 `html.parser` 로 조용히 넘어가는데, 같은 원문에서 문장 수가 달라진다. 모델 지정이나 별도 MCP 서버 설정 없이 시작할 수 있다.

### jev 관문 (선택)

장르·문서 유형 판정과 의미 위험 1차 판정은 [TypeSafe](https://docs.typesafe.ai) 의 jev 로 돌릴 수 있다. `.env.example` 을 `.env` 로 복사하고 `TYPESAFE_API_KEY` 를 넣으면 켜진다. **키가 없으면 지금까지와 똑같이 돈다** — 두 판정을 코드 힌트와 LLM 담당이 그대로 맡는다. 추가 설치는 없다(표준 라이브러리로 부른다).

켜면 원문 앞부분(최대 8,000자)과 의미가 달라졌을 수 있는 문장 쌍이 TypeSafe 로 전송된다. 외부로 내보낼 수 없는 문서는 `ANTI_WORKSLOP_JEV=0` 으로 끈다. jev 는 원고를 고치지 않고 객관식 판정만 하며, 재작성·사람 판단·검수 통과 판정에는 쓰지 않는다. 호출이 실패하면 그 사실을 한 줄로 남기고 현행 경로로 간다.

Claude 전용 아티팩트 도구가 없는 Codex 환경에서는 `to_artifact.py --local`로 원본과 같은 폴더에 `.review.html` 또는 `.review.md` 파일을 만들고 대화로 받은 피드백을 취향에 반영한다. 로컬 HTML은 문서 구조와 리소스 참조를 유지한다. 로컬 파일에는 온라인 코멘트 기능이 없으며, 온라인 발행·코멘트 수집은 연결된 도구가 있어야 한다. superpowers 플러그인은 명시적으로 요청했을 때만 사용한다.

## 세 레이어

| 레이어 | 무엇 | 어디 | 누가 만든다 |
|---|---|---|---|
| 원칙 | 누구에게나 AI 티인 것 67규칙과 고칠 때 깨지 않는 불변식 셋(새 사실 금지·고정 구역 보존·의미 보존) | `principles/` | 손으로. `ai-tells-ko.md` §5 절차 |
| 스타일가이드 | 한 저자·한 장르의 문체. 기본은 줄글 장피엠, 보고서 개조식이고 내 가이드를 등록할 수 있다 | `styleguides/` | styleguide-builder(jangpm·내 가이드), 손 큐레이션(report) |
| 취향 | 쓰는 사람 각자가 싫어하고 좋아하는 것. 저장소에는 없고 각자 쌓는다 | `taste/` | taste-builder(아티팩트 코멘트에서 증류) |

우선권 · 사용자 지시 > 불변식 > 취향 [규칙]·[경향] > 가이드 hard > 취향 [관찰] > 가이드 soft > 원칙 S1 > S2 > S3.

## 세 스킬 (`.claude/skills/`, Codex 진입점 `.agents/skills/`)

| 스킬 | 하는 일 | 트리거 예 |
|---|---|---|
| `anti-workslop` | 세 레이어로 윤문·검토·구조 진단. 탐지·재작성 담당 1명, 검사기 넷, 위험 문서만 독립 의미 검토 | 「윤문해줘」「검토만」「결론이 어디 있는지 봐줘」 |
| `styleguide-builder` | 코퍼스에서 문체 가이드라인 키트를 만들고 렌더·검증한다 | 「이 블로그 문체 가이드 만들어줘」 |
| `taste-builder` | 산출물을 코멘트용 아티팩트로 발행하고 코멘트를 취향 규칙으로 증류한다 | 「코멘트 달 수 있게 올려줘」「taste 갱신」 |

## 실행

프로젝트 루트에서 `python -X utf8` 로 돌린다. 표준 라이브러리만 쓴다.

- 검수 한 번에 · `python -X utf8 .claude/skills/anti-workslop/scripts/check_all.py --guide 장피엠 --orig 원문.md 결과.md`
- 장르 힌트 · `python -X utf8 .claude/skills/anti-workslop/scripts/check_all.py --guide 없음 --hint 원문.md`
- 테스트 · `python -X utf8 .claude/skills/anti-workslop/tests/run_acceptance.py`. styleguide-builder·taste-builder 도 같은 자리에 `tests/run_acceptance.py` 가 있다
- 스킬 문서와 가이드는 원칙 검사기로 S3 까지 0 이어야 한다. 테스트가 본다(`tests/fixtures/self-application.txt`)

## 기록

설계·계획·전후 측정 기록은 원본 저장소에만 있고 배포본에는 없다. 개조식 가이드의 근거 자료는 `styleguides/report/README.md` 에 있다.

## 변경 시 검사

```bash
python -X utf8 .claude/skills/anti-workslop/tests/run_ci.py
```

개인 취향을 제외한 임시 복사본에서 세 스킬 인수 테스트와 의미 검토 회귀 테스트를 돌립니다. 외부 모델을 호출하지 않고 네트워크도 쓰지 않습니다. 일반 원고의 문체를 이유로 배포를 막지 않습니다.

맨 앞에서 환경 검사부터 봅니다. 서드파티 import 가 `requirements` 에 선언돼 있는지 소스만 읽어 확인하고, 제어문자가 섞인 원문을 `lxml` 과 `html.parser` 양쪽으로 뽑아 결과가 같은지 봅니다. 개발기에 패키지가 깔려 있어서 통과하는 일을 막으려는 것입니다.

**OS 마다 한 번씩 돌려 보십시오.** `lxml` 이 묶는 libxml2 는 플랫폼마다 판이 달라서, 같은 원문이 Windows 와 Linux 에서 다른 문장 수로 갈린 적이 있습니다(2026-09-21).
