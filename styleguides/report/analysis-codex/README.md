# analysis-codex — Codex 독립 분석 기록 (축약본)

2026-09-07 에 Codex 가 공식 출처 15건을 확보해 문체를 측정한 기록이다. 정본 `../개조식 보고서 작성 가이드라인.md` 는 이 분석과 Claude 분석(`../scripts/`·`../corpus/`)을 사람이 병합해 썼다. 가이드를 쓰거나 검사하는 데 이 폴더는 필요 없다.

2026-09-14 에 원문 추출 텍스트(`text/`, 7.5MB)·페이지 이미지(`screenshots/`, 2.6MB)·실행 스크립트 셋(`analyze_style.py`·`collect_sources.py`·`validate_artifacts.py`)·`validation.json`·`requirements.txt` 를 트리에서 뺐다. 저장소 16MB 가운데 10MB 였고, gitignore 된 PDF(`sources/`)와 PyMuPDF 없이는 돌지 않는 것들이다. 전부 원본 저장소의 태그 `provenance/report-2026-09-07`(커밋 f6d98f6)에 그대로 있다. 배포본에는 이 태그가 없다.

## 남긴 것

| 파일 | 역할 |
|---|---|
| `manifest.json` | 출처 15건의 판본·URL·저장 경로·접근 상태·파일 해시 |
| `corpus_lock.json` | 원문 15개의 고정 해시와 추출기 버전(PyMuPDF 1.26.5) |
| `metrics.json` | 49표본(나보포커스 82호 항목 28 · 이슈와 논점 2522호 문장 21)의 길이 분포·끝맺음 요약 |
| `sample_selection.json` · `sample_metrics.csv` | 측정한 쪽·블록 번호와 표본별 길이·정규화 텍스트 해시 |
| `input_reference.md` | 사용자가 준 참고문헌 목록 원본 |

## 되살리기

원본 저장소에서만 된다.

```bash
git checkout provenance/report-2026-09-07 -- styleguides/report/analysis-codex
```

그 판의 README §6 대로 `collect_sources.py` 로 원문을 다시 받고 `analyze_style.py`·`validate_artifacts.py` 를 돌린다. 원문 15건의 출처·판본과 근거 ID(R01~R19)가 가이드 규칙에 어떻게 이어지는지도 그 판의 README §2·§4 에 있다.
