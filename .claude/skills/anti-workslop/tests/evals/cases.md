# 모드 eval 케이스

픽스처는 `tests/fixtures/`에서 중립 경로로 복사해 돌린다(경로가 테스트임을 누설하지 않게).

러너는 없다. 새 세션을 열어 아래 입력·요청을 그대로 주고, 응답이 기대 칸을 만족하는지 사람이 본다. 결과 기록에는 실행한 모델을 적는다(본 컨텍스트와 서브에이전트가 다르면 둘 다). 입력 파일은 전부 `tests/fixtures/`에 있다(06 `timeline.md`, 09 `explore-memo.md`, 10 `quoted-law.md`는 2026-09-09, 13 `no-ai-slop-ko.md`, 14·15 `three-lessons.md`, 16 `three-stages-gpt.md`는 2026-09-11 추가).

| id | 범주 | 입력·요청 | 기대 |
|---|---|---|---|
| 01-offer-on-shared-draft | should-offer | `ai-draft-prose.md` + "이거 어때?" | 두 문장(증상+질문). 고친 문장·규칙 목록 없음. 모드·스킬 언급 없음 |
| 02-detect-only | should-detect-only | 같은 초안 + "AI 티 검사만" | 발견 목록 5칸·3계층, 고친 문장 0, AI 작성 여부 언급 0, 점수 0, 끝에 윤문 제안 한 줄 |
| 03-edit-prose | should-edit | 같은 초안 + "장피엠 문체로 윤문해줘" | `.taste.md`+notes 네 절(적용 기록·검수·미결·진단 반환문), S1 0·hard 0·fidelity S1 0, 잠언 마무리 삭제(대체 잠언 없음) |
| 04-edit-report | should-edit | `ai-draft-report.md` + "다듬어줘" | 됐다→되었다(서술형 구역 안만), 어체 혼용 해소, 인용문 어미 불변, H 0 |
| 05-abstain-clean | should-abstain | `abstain/already-clean.md` + "윤문해줘" | "수정 없음: 네 검사기 통과". 파일 미저장 |
| 06-abstain-timeline | should-abstain | `timeline.md`(장애 타임라인) + "구조 진단해줘" | 시간순이 맞는 문서라는 한 줄, 재구성·진단표 없음, 문장 윤문만 제안 |
| 07-fact-preservation | fact-preservation | `fidelity/orig.md` + "다듬어줘" | check_fidelity S1 0, 확정 수준 불변, 산술 결과 추가 없음 |
| 08-keep-concrete-contrast | should-keep | "사업가가 아닌 메이커" 구체 명사쌍 + 근거 문장이 있는 글 + "윤문해줘" | 대구 유지, notes 진단 반환문의 둘 것 절에 "§7-5 정당 용법" |
| 09-absent-conclusion | edge | `explore-memo.md`(탐색 메모) + "결론이 뭔지 봐줘" | "하나의 결론을 지지하지 않음" + 미결 질문. 결론 날조 없음 |
| 10-quoted-block | should-abstain-partial | `quoted-law.md`(가상 규정 인용 블록 + 해설) + "다듬어줘" | 인용 블록 바이트 불변, 해설만 수정 |
| 11-diagnose-isolation | process | `ai-draft-prose.md` + "윤문해줘" | 본 컨텍스트는 `check_all --hint` 로 가이드를 고르고 Agent 도구로 서브에이전트 1회 호출, 원문·가이드 전문·규칙표·브리프·전달 파일·§14·취향을 읽지 않음(도구 호출 6회 + 수정 바퀴 이내), 서브에이전트는 원문과 `check_all --bundle` 출력만 읽고 가이드 전문을 열지 않음(도구 호출 6회 이내), `.taste.md` 는 서브에이전트가 씀, notes 네 절 가운데 진단 반환문이 전달 파일 그대로 |
| 12-review-layer-counts | should-detect-only | `ai-draft-report.md` + "검토만" | 첫 줄이 「개조식 기준으로 검토: 취향 N건, 가이드 hard N건, 원칙 S1 N건, 사람 판단 N건」, 발견 다섯 칸·세 계층 유지, ③에 AT-24·25·33·60·61 또는 §11-2 항목 |
| 13-portability-human | should-detect-only | `no-ai-slop-ko.md` + "검토만" | ①에 AT-09·10·62·63·64, ③에 AT-61(「좋은 팀은 도구보다 사람을 먼저 봅니다」·「고객 경험이 곧 경쟁력입니다」)과 이 대상만의 사실 확인. 고친 문장 0, 새 사실 0 |
| 14-paragraph-moral | should-detect-only | `three-lessons.md`(스타일 지시 없이 쓴 Claude 초안) + "검토만" | ③에 AT-65(「규칙은 단순했지만 효과는 확실했다.」·「공식 교육보다 동료의 성공 사례가 훨씬 강력한 동기가 됐다.」)와 AT-66(같은 문형의 세 제목 · 결론 재나열), 고친 문장 0 |
| 15-three-lessons-edit | should-edit | `three-lessons.md` + "장피엠 문체로 윤문해줘" | 절 셋과 순서 유지, 제목 하나 이상이 그 절 본문의 사실로 바뀜, 결론 재나열 삭제, 새 사실 0(check_fidelity S1 0), AT-65 교훈 문장은 고치지 않고 진단 반환문 ③에 남음 |
| 16-three-stages-gpt | should-detect-only | `three-stages-gpt.md`(스타일 지시 없이 쓴 GPT 초안) + "검토만" | ③에 AT-66(세 단계 굵은 도입 · 결론 재나열), 고친 문장 0 |
