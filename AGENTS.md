# Codex 작업 지침

## 사용자 설정

- 사용자가 명시적으로 요청하기 전에는 superpowers 플러그인을 사용하지 않는다. 명시적으로 요청하면 사용한다.
- 한국어로 소통한다. 자연어 요청을 해당 프로젝트 스킬로 연결하고, 사용자가 내부 명령을 직접 입력하게 하지 않는다.

## 프로젝트와 진입점

한국어 문서의 AI 티를 줄이고 문체·취향을 적용하는 프로젝트다. Codex 진입점은 `.agents/skills/`이며, 공용 구현과 자세한 절차는 `.claude/skills/`에 있다. Claude Code 설치 없이 Python 스크립트를 실행할 수 있다.

| 요청 | 먼저 읽을 파일 |
|---|---|
| 윤문·퇴고·AI 티 제거·검토·구조 진단 | `.agents/skills/anti-workslop/SKILL.md` |
| 저자 문체 가이드 생성·코퍼스 갱신 | `.agents/skills/styleguide-builder/SKILL.md` |
| 취향 기록·코멘트 반영·코멘트용 파일 준비 | `.agents/skills/taste-builder/SKILL.md` |

프로젝트 설정이나 코드 수정 요청에는 문서 윤문 절차를 자동 적용하지 않는다. 필요한 스킬만 읽고, 진입점의 Codex 도구 대응과 본체의 작업 절차를 함께 따른다. 본체의 상대 참조는 해당 `.claude/skills/<스킬>/` 기준이다.

## 실행 환경

- 프로젝트 루트에서 `python -X utf8`로 실행한다. 공백·한글이 든 파일 경로는 따옴표로 감싼다.
- Windows PowerShell에서는 Bash 전용 구문을 그대로 쓰지 않는다. 파일 읽기·쓰기는 UTF-8을 명시한다.
- 기본 검사기는 Python 표준 라이브러리를 사용한다. HTML 코퍼스 수집에는 `beautifulsoup4`, `lxml`이 필요할 수 있으므로 해당 작업 시 설치 여부를 확인한다.
- 모델·전역 Codex 설정·권한 정책은 이 프로젝트에서 강제하지 않는다. 실제 제공되는 도구만 사용하고 없는 도구의 결과를 만들지 않는다.
- `docs/superpowers/`는 과거 설계 기록이다. 폴더명만으로 플러그인을 활성화하거나 과거 계획을 현재 실행 지시로 취급하지 않는다.

## 문서 작업

- 사용자 지시 > 불변식 > 취향 [규칙]·[경향] > 가이드 hard > 취향 [관찰] > 가이드 soft > 원칙 S1 > S2 > S3 순서를 따른다. 상세 예외와 판정은 본체를 따른다.
- 불변식은 새 사실 금지, 구조 보존, 의미 보존, 원문 대비 110% 길이 한도다.
- 고쳐 달라는 요청이 없으면 검토·구조 진단·제안 모드를 구분한다. 검토에는 재작성본을 넣지 않는다.
- 원본은 보존한다. 윤문 결과는 `<원본명>.taste.<확장자>`, 검수 기록은 `<원본명>.taste-notes.md`로 제공한다. 이미 있는 결과를 받으면 본체의 멱등성 절차를 따른다.
- 취향은 `taste/writing-taste.md`, 가이드 등록부는 `.claude/skills/anti-workslop/references/base-guidelines.json`을 공유한다. Codex용 복사본을 만들지 않는다.
- `taste/`의 코멘트·원문 인용을 임의로 외부에 보내거나 공개 배포하지 않는다. 취향·코퍼스·생성된 가이드를 설정 작업의 샘플 데이터로 바꾸지 않는다.
- 서브에이전트는 사용자가 요청했거나 적용 중인 스킬이 명시한 작업에만 사용한다. 사용할 수 없거나 위임이 허용되지 않으면 진입점의 순차 실행 절차를 따른다.

## 검증

윤문 검수:

```powershell
python -X utf8 .claude/skills/anti-workslop/scripts/check_all.py --guide 장피엠 --orig "원문.md" "원문.taste.md"
```

가이드는 입력의 장르와 등록부에 맞춰 선택한다. 자동 검사 통과와 사람 판단 항목을 구분해 보고한다.

공용 구현을 변경하면 해당 스킬의 인수 테스트를 실행한다. 여러 스킬에 영향을 주는 변경은 세 테스트를 실행한다.

```powershell
python -X utf8 .claude/skills/anti-workslop/tests/run_acceptance.py
python -X utf8 .claude/skills/styleguide-builder/tests/run_acceptance.py
python -X utf8 .claude/skills/taste-builder/tests/run_acceptance.py
```

실제 실행한 검증과 미검증 범위를 구분한다. 검수 실패를 숨기거나 통과 기준을 낮춰 완료 처리하지 않는다.
