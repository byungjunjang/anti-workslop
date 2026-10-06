# SlopMonster에서 검토한 한국어 패턴

근거: https://github.com/ItsssssJack/SlopMonster/blob/main/tools/deslop.py 및 prompts/cleanse.txt (2026-09-17 확인). 한국어 대응은 이 프로젝트의 편집 판단이며 영어 단어의 직역 금지 목록이 아니다.

| 영어 패턴 | 한국어 처리 | 이유 |
|---|---|---|
| unlock potential, unparalleled experience, seamless experience | AT-67, S3, 2회/문서 | 추상 홍보 구문 반복을 안내한다. 경험·여정·활용·혁신 단어 자체는 금지하지 않는다 |
| here's the thing / throat clearing | AT-10의 말씀드릴게요 활용형 보완 | 기존 심각도·밀도 유지 |
| imagine / opener | AT-11의 떠올려 볼까요 활용형 보완 | 교육·회상 질문 한 번은 수정 강제가 아니다 |
| not just X but Y | AT-01·44 유지 | 실제 부정과 대조 보존을 우선 |
| punctuation cadence | AT-18·19·20 유지 | 영어 세미콜론·하이픈 임계는 한국어에 이식하지 않음 |
| three-item rhythm | AT-04·42·66 및 아래 문맥 대조 | 정확히 셋이라는 이유로 목록을 바꾸지 않음 |
| invented proof | 불변식·AT-25·의미 위험 구간 검토 | 수치와 고객 명사가 붙었다고 허위로 판정하지 않음 |

리듬 검토 예: 「빠르고, 쉽고, 강력하다」가 절마다 반복되면 근거 없는 평가어인지 LLM이 대조한다. 「수집, 분석, 보고」는 실제 단계일 수 있으므로 보존한다. 교육용 삼단계 설명, 서비스 목록, 인용은 개수만으로 고치지 않는다. 원문에 없는 넷째 항목을 만들거나 하나를 삭제하지 않는다. 이 문맥 예는 AT-66의 판정 질문을 보완하는 참고이며 새 자동 실패 조건이 아니다.

새 패턴은 정상 대조군과 양성 사례로 함께 검증한다. 검사 통과가 좋은 글의 증명은 아니다.
