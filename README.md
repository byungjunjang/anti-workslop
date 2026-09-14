# anti-workslop

AI 가 쓴 한국어 문서에서 AI 티를 빼고 문체와 취향에 맞게 다듬는 파이프라인이다. 규칙은 문서에 두고 검사는 코드가 하며 사람 판단은 서브에이전트 하나가 맡는다.

## 세 레이어

| 레이어 | 무엇 | 어디 | 누가 만든다 |
|---|---|---|---|
| 원칙 | 누구에게나 AI 티인 것 66규칙과 고칠 때 깨지 않는 불변식 넷 | `principles/` | 손으로. `ai-tells-ko.md` §5 절차 |
| 스타일가이드 | 한 저자·한 장르의 문체. 기본은 줄글 장피엠, 보고서 개조식이고 내 가이드를 등록할 수 있다 | `styleguides/` | styleguide-builder(jangpm·내 가이드), 손 큐레이션(report) |
| 취향 | 쓰는 사람 각자가 싫어하고 좋아하는 것. 저장소에는 없고 각자 쌓는다 | `taste/` | taste-builder(아티팩트 코멘트에서 증류) |

우선권 · 사용자 지시 > 불변식 > 취향 [규칙]·[경향] > 가이드 hard > 취향 [관찰] > 가이드 soft > 원칙 S1 > S2 > S3.

## 처음 쓰는 분께

원칙은 누구에게나 같지만 문체와 취향은 사람마다 다르다. 저장소에 든 가이드 둘은 출발점이고, 오래 쓸수록 내 가이드와 내 취향으로 바꾸는 편이 결과가 좋다.

1. **바로 써 보기.** Claude Code 에서 이 폴더를 열고 「이 글 윤문해줘」라고 한다. 줄글은 장피엠 가이드(이 저장소 저자의 블로그 문체), 보고서는 개조식 가이드(공공 기관 보고서 문체)로 고친다. 취향 문서가 없어도 돈다.
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

## 세 스킬 (`.claude/skills/`)

| 스킬 | 하는 일 | 트리거 예 |
|---|---|---|
| `anti-workslop` | 세 레이어로 윤문·검토·구조 진단. 탐지와 재작성은 서브에이전트 1회, 검수는 검사기 넷 | 「윤문해줘」「검토만」「결론이 어디 있는지 봐줘」 |
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
