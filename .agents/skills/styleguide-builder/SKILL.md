---
name: styleguide-builder
description: 한 저자의 한국어 블로그나 로컬 Markdown 글에서 문체 가이드와 검사 키트를 만들거나 갱신한다. "내 문체 가이드 만들어줘", "코퍼스 갱신"에 사용한다. 보고서 가이드 생성이나 초고 하나의 윤문에는 사용하지 않는다.
---

# styleguide-builder — Codex

먼저 프로젝트 루트의 `AGENTS.md`와 `.claude/skills/styleguide-builder/SKILL.md`를 읽고 따른다. 기존 스크립트와 자료를 공유하며 복사본을 만들지 않는다.

- 이 파일에서 세 단계 위가 프로젝트 루트다. 명령은 루트에서 실행한다.
- 본체의 상대 `references/`, `assets/`, `scripts/`, `tests/` 경로는 `.claude/skills/styleguide-builder/` 기준이다. `$S`와 `$K`는 본체가 정의한 경로로 설정한다.
- 숫자는 기존 분석·렌더 스크립트로 계산한다. 완성 가이드라인을 직접 고치지 말고 워크시트·프로파일·템플릿을 수정한 후 재렌더한다.
- HTML 수집에 필요한 Python 패키지가 없으면 해당 기능에 필요한 의존성만 설치한다. 로컬 Markdown 처리에 웹 수집용 패키지를 요구하지 않는다.
- 웹 수집은 사용자가 지정한 소스 범위에서 수행하고, 네트워크 제한이 있으면 확보된 로컬 자료로 진행 가능한 부분을 처리한다. 가져오지 못한 글을 읽었다고 하지 않는다.
- 본체가 정한 분할 읽기는 현재 세션의 서브에이전트 도구가 있고 위임이 허용될 때만 사용한다. 그렇지 않으면 같은 읽기 절차를 순차 수행한다.
- 검증을 통과한 키트만 기존 `register_guide.py`로 등록한다. 공용 등록부는 `.claude/skills/anti-workslop/references/base-guidelines.json`이다.
