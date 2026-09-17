---
name: taste-builder
description: 사용자가 명시한 글쓰기 취향이나 제공한 코멘트를 취향 문서에 기록·반영하고 코멘트용 파일을 준비한다. "취향으로 기록해줘", "취향 문서 갱신", "코멘트 반영해줘", "코멘트 달 수 있게 올려줘"에 사용한다. 글 자체를 고치는 요청은 anti-workslop을 쓴다.
---

# taste-builder — Codex

먼저 프로젝트 루트의 `AGENTS.md`와 `.claude/skills/taste-builder/SKILL.md`를 읽는다. 데이터 스키마·병합·증류·검증은 본체를 따르고, Claude 전용 기능은 아래와 같이 처리한다.

## 경로와 데이터

이 파일에서 세 단계 위가 프로젝트 루트다. 명령은 루트에서 실행한다. 본체의 `references/`, `scripts/`, `tests/`는 `.claude/skills/taste-builder/` 기준이다. 기존 `taste/`를 그대로 사용하고 초기화로 덮어쓰지 않는다. 사용자 원문은 보존하고, 취향 저장은 명시적으로 요청했을 때만 한다.

## 발행과 수집

- `artifact-design`·`Artifact`가 실제 사용 가능한지 먼저 확인한다. Codex에 같은 기능이 있다고 가정하지 않는다.
- 발행 도구가 없으면 `python -X utf8 .claude/skills/taste-builder/scripts/to_artifact.py --local "<원본>" "<원본 폴더>/<원본명>.review.<확장자>"`로 로컬 검토 파일을 만들고 링크를 제공한다. Markdown 출력 확장자는 `.md`로 쓴다. HTML의 상대 리소스 경로를 유지하도록 원본과 같은 폴더에 별도 이름으로 저장한다. 로컬 파일에는 코멘트 입력·저장 기능이 없으며 원문 문장과 고칠 문장·이유를 대화로 보내도록 안내한다. `--local` 없는 기존 변환은 실제 Artifact 발행에만 사용한다.
- 로컬 파일 생성은 온라인 발행이 아니다. 가짜 URL이나 `published_at`을 만들지 않고 `taste/artifacts.json`에 발행 성공을 기록하지 않는다. 다른 서비스에 임의 업로드하지 않는다.
- URL에서 코멘트를 읽을 도구가 없으면 사용자가 제공한 코멘트 JSON이나 대화 내용을 입력으로 받는다. 확보하지 못한 코멘트·스레드는 추정해서 만들지 않는다.
- 기존 스키마의 Artifact 코멘트 JSON은 모드 B의 raw 저장 이후 절차를 따른다. 대화로 준 취향은 모드 C의 `origin: chat` 경로를 사용한다. `source_ref`에 해당 대화를 식별할 설명을 적고 사용자 문장은 그대로 저장한다.
- 스레드 답글·resolve는 실제 연결 도구와 사용자의 전송 지시가 있을 때만 실행한다. 도구가 없으면 로컬 반영 결과만 알린다.

병합 → 증류 → 원장 매핑 → `validate_taste.py` 검증 → changelog 기록까지 완료하고, 새 케이스가 없으면 기존 파일을 변경하지 않는다.
