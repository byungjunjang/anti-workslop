# styleguides/report — 개조식 보고서 작성 가이드라인 키트

`개조식 보고서 작성 가이드라인.md`의 근거 자료와 검사 도구를 모아 둔 폴더다. `styleguides/jangpm/`과 달리 styleguide-builder가 만든 키트가 아니다. 2026-09-07에 Claude 분석(이 폴더의 `scripts/`·`corpus/`·`stats.md`)과 Codex 분석(`analysis-codex/`)을 사람이 병합해 가이드라인을 썼다. 병합본의 수치 표(§4-1 항목 길이, §5 종결 비율 등)는 `stats.md`에서 왔다. 렌더·verify 파이프라인은 없으므로 수치를 바꾸려면 `analyze_corpus.py`를 다시 돌리고 가이드라인의 표를 손으로 맞춘다.

## 구성

| 경로 | 역할 |
|---|---|
| `개조식 보고서 작성 가이드라인.md` | 정본. anti-workslop 스킬이 보고서 윤문의 기본 가이드로 읽는다 |
| `kit.json` | 키트 메타 |
| `corpus/sources.json` | 참고 문헌 25건의 URL·접근 상태·용도. `access`가 `auto`인 것만 스크립트가 받는다 |
| `corpus/raw_hashes.json` | 원본 PDF 13개의 sha256 |
| `corpus/raw/` | 원본 PDF. `*.pdf`는 gitignore라 저장소에 없다. `fetch_sources.py`로 다시 받는다 (2026-09-08 재수집: 13개 전부 해시 일치, 총 406MB) |
| `corpus/text/` | 추출 텍스트 22개. **고정 코퍼스**. 통계는 이 파일들에서 나온다 |
| `corpus/items_ko.jsonl`, `docs_ko.json`, `titles_ko.json` | `parse_ko.py` 산출. NABO Focus 합본 4,042항목 + 개별호 182항목 + 국립국어원 예시 191항목 |
| `stats.json`, `stats.md` | `analyze_corpus.py` 산출. 가이드라인 수치의 출처 |
| `scripts/` | `fetch_sources.py`, `parse_ko.py`, `analyze_corpus.py`, `check_report.py` |
| `samples/bad_draft.md` | 검사기 대조군. 검사하면 종료 코드 1이 나와야 정상 |
| `docs/style-profile.md` | Claude 분석본의 근거 보고서. 자료별 열람 범위·인용·분석 방법 |
| `analysis-codex/` | Codex의 독립 분석 축약본. 공식 출처 15건의 확보 기록(`manifest.json`, 해시), 표본 49단위 측정 결과, 사용자가 준 참고문헌 목록 원본(`input_reference.md`). 원문 추출 텍스트·스크린샷·스크립트(10MB)는 2026-09-14에 트리에서 빼고 원본 저장소의 태그 `provenance/report-2026-09-07`에 두었다 |

## 다시 만들기

프로젝트 루트에서 실행한다. 표준 라이브러리만 쓰고, `fetch_sources.py`의 텍스트 추출만 PyMuPDF(`pip install pymupdf`)가 필요하다.

```bash
python -X utf8 styleguides/report/scripts/parse_ko.py          # corpus/text → items_ko.jsonl, docs_ko.json, titles_ko.json
python -X utf8 styleguides/report/scripts/analyze_corpus.py    # → stats.json, stats.md
python -X utf8 styleguides/report/scripts/check_report.py 초안.md   # 초안 검사 (종료 코드 1 = 반드시 고칠 항목 있음)
```

같은 `corpus/text/`로 두 번 돌리면 items·docs·titles·stats가 바이트 단위로 같다(2026-09-08 확인).

원본 PDF가 필요할 때만:

```bash
python -X utf8 styleguides/report/scripts/fetch_sources.py            # 자동 수집 항목 내려받기 + 텍스트 추출
python -X utf8 styleguides/report/scripts/fetch_sources.py --verify   # sha256 대조만. 텍스트는 건드리지 않는다
```

**주의.** `fetch_sources.py`를 `--verify` 없이 돌리면 `corpus/text/`를 다시 추출해 덮어쓴다. 2026-09-08에 전체 재추출을 해 보니 12개 파일이 커밋본과 달라졌다(특히 합본 텍스트가 크게 줄었다). 그러면 통계가 가이드라인과 어긋난다. 재추출 뒤에는 `git diff corpus/text`를 보고 커밋본으로 되돌리거나, 바꿀 이유가 있으면 가이드라인 수치를 함께 갱신한다. 대통령비서실 매뉴얼(2005)은 자동 수집이 막혀 있어 `sources.json`의 `manual` 안내대로 사람이 확보한다. 추출 텍스트는 `corpus/text/bh_manual_2005.txt`에 이미 있다.

## 검사기와 가이드라인 §11-2의 대응

`check_report.py`는 병합 전 Claude 분석본의 점검표 번호를 쓴다. 가이드라인 §11-2와의 대응은 아래와 같다.

| check_report.py | 가이드라인 §11-2 | 내용 |
|---|---|---|
| H1 | H1 | 제목 1줄·40자·판단 낱말로 끝남 |
| H2 | H2 | 첫 3줄에 결론·요청·수치 |
| H3 | H3 | 계층 3단 이하 |
| H4 | H4 | 항목 120자 초과 오류, 90자 초과 경고 |
| H5 | H5 | 개조식 항목 끝의 '-다/-습니다' |
| H6 | S2 | 2·3단 항목의 숫자 포함 50% |
| H7 | S3 | 접속부사로 시작하는 항목 15% |
| H8 | S4 | 하위 항목이 1개뿐인 상위 항목 |
| S1 | S6 | 애매·과장·번역투·군더더기·한자어 |
| S2 | S7 | 날짜·시간·금액 표기 |
| S3 | H7 | 분량 |
| 없음 | H6 | 마지막 옆제목이 건의·시사점이고 요청 항목에 주체·행동·기한 |
| 없음 | S1 | 항목 길이 25~70자, 중앙값 45~55자 |
| 없음 | S5 | 3단이 '필요'로 끝나는 항목 |
| 없음 | S8 | 표·그림 캡션·출처·요약 항목 |
| 없음 | S9 | AI 티 공용 목록 (anti-workslop check_ai_tells.py) |

빠진 네 항목은 사람이 본다. HTML 리포트는 anti-workslop 의 `check_html.py`가 산문 블록을 md 로 뽑아 이 검사기에 넘긴다.

## 수치의 한계

- NABO 합본은 PDF 글꼴 특성으로 일부 호의 띄어쓰기가 사라졌다. 그래서 **공백 제외 글자 수**를 기준 수치로 쓰고, 어절 수는 띄어쓰기가 살아 있는 개별호 4건(82·84·85·86호)과 국립국어원 예시에서만 냈다.
- 파서는 표 셀·각주·캡션을 항목에서 제외하지만, 쪽 경계에서 잘린 항목과 표 안 문장이 섞이는 오류가 약간 있다(무작위 30건 검토에서 2건). 옆제목 수는 표 셀이 섞여 과대 추정되므로 통계표에서 뺐다.
- 영어 문장 분리는 마침표 뒤 대문자 규칙이라 약어·URL이 있으면 틀린다. CRS 미러 HTML 4건은 PDF 1건보다 정확도가 낮다.
- 명료도 지수의 음절 수는 모음군 휴리스틱이다.

## 이력

- 2026-09-07: `reportkit-fable/`(Claude)와 `analysis/report-writing-20260907/`(Codex)로 병렬 분석. 두 가이드 초안을 병합해 정본 작성.
- 2026-09-08: 첫 정리에서 두 폴더를 지웠다가 사용자 요청으로 커밋 `c00fa4c`에서 되살려 이 배치로 옮겼다. 스크립트 경로를 `scripts/` 기준으로 고치고, `--verify`가 텍스트를 덮어쓰지 않게 바꿨다. 원본 PDF는 다시 받아 해시를 대조했다. 되살린 커밋에서는 `nabo_focus_082.txt`가 비어 있어 개별호 항목 182건 중 57건이 재현되지 않았는데, 원인은 `sources.json`의 `pages: "4쪽"` 문자열을 쪽 필터로 읽어 모든 쪽을 건너뛰던 `fetch_sources.py` 버그였다. 고치고 82호를 다시 추출하자 items·docs·titles·stats 다섯 파일이 커밋본과 바이트 단위로 같아졌다.
