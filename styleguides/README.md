# styleguides · 스타일가이드 레이어

anti-workslop 윤문의 세 레이어(원칙·스타일가이드·취향) 가운데 스타일가이드다. 한 저자 또는 한 장르의 문체를 14절 고정 구조의 가이드라인 한 파일로 적고, 검사기가 §11-1 표를 그대로 센다. anti-workslop은 두 키트를 같은 레이어로 읽는다. 어느 키트로 고칠지는 글의 종류가 정한다. 줄글은 jangpm, 보고서는 report. 개인의 보고서 선호는 가이드가 아니라 `taste/`에 쌓는다.

| slug | 저자 | 출처 | 정본 | 검사기 | 재생성 |
|---|---|---|---|---|---|
| `jangpm/` | 장피엠(개인 저자) | styleguide-builder 렌더. 템플릿·워크시트·통계에서 바이트 동일하게 다시 만든다 | `장피엠 글쓰기 문체 가이드라인.md` | `python -X utf8 .claude/skills/styleguide-builder/scripts/check_style.py --kit styleguides/jangpm 초고.md` | `render_guideline.py --kit styleguides/jangpm --version <날짜>` 뒤 `verify_guideline.py --report` |
| `report/` | 공공 기관 개조식 보고서(공공 저자) | 손 큐레이션. Claude·Codex 분석을 사람이 병합했고 렌더 파이프라인이 없다 | `개조식 보고서 작성 가이드라인.md` | `python -X utf8 styleguides/report/scripts/check_report.py 초안.md` | `report/README.md` 참조. 수치는 `analyze_corpus.py`로 다시 내고 표는 손으로 맞춘다 |

## 내 가이드 추가

두 키트는 기본값이다. 내 문체로 고치고 싶으면 내 글 다섯 편 이상으로 키트를 만들어 등록한다.

1. 「내 블로그 문체 가이드 만들어줘」로 styleguide-builder 를 돌린다. 코퍼스는 사이트맵·RSS·URL 목록·로컬 `.md` 폴더 가운데 하나다. 결과는 `styleguides/<slug>/` 에 생긴다.
2. 검증(`verify_guideline.py --report`)이 통과하면 `python -X utf8 .claude/skills/styleguide-builder/scripts/register_guide.py --kit styleguides/<slug>` 로 등록한다.
3. 등록한 가이드는 anti-workslop 장르 힌트의 레이어 줄에 나오고, 줄글 윤문은 그 가이드를 쓴다. 뺄 때는 `--remove <표시명>`.
4. 위 표에 한 행을 더한다.

styleguide-builder 는 블로그형 줄글만 만든다. 보고서형 가이드는 report 키트처럼 코퍼스 분석을 사람이 병합해 손으로 만들고 `base-guidelines.json` 에 직접 적는다.

## 공통 연결

두 가이드 모두 §8 마지막 행과 §14 [AI 티] 줄이 공용 AI 티 목록 `principles/ai-tells-ko.md`를 가리키고, §10 보존 규칙은 `principles/invariants.md`의 불변식과 이어진다. 가이드 고유 금지만 여기 두고 공용 목록은 원칙 레이어에 둔다. 가이드를 고칠 때 jangpm은 템플릿을 고쳐 재렌더하고, report는 정본을 직접 고친다.
