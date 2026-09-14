# 기권(abstain) 픽스처

검사기 수준 기권 = 장르 검사기 hard 0, `check_ai_tells --strict` 0건, `check_fidelity a a` 0건·비율 1.0.
SKILL 수준 '수정 없음' 응답은 `tests/evals/cases.md` 05번 수동 케이스.

- `already-clean.md` — 장피엠 코퍼스 원문(`styleguides/jangpm/corpus/posts/work-automation.md`) **전문**
  3,096자다. 잘라 쓰지 않는다. 앞부분만 떼면 마무리 문단이 빠져 장피엠 §6-5(끝은 권유·전망·감사)를
  만족하지 못하고, 합쇼체 비율도 기준 아래로 내려가 장르 검사기가 hard 2 를 낸다. 손대지 않은 사람
  글이므로 AI 티 검사에서 한 건도 나오지 않아야 하고, 자기 자신과 대조하면 모든 다중집합이 같아
  finding 0 · length_ratio 1.0 이 나와야 한다.

```
python -X utf8 .claude/skills/styleguide-builder/scripts/check_style.py --kit styleguides/jangpm --strict \
    .claude/skills/anti-workslop/tests/fixtures/abstain/already-clean.md
python -X utf8 .claude/skills/anti-workslop/scripts/check_ai_tells.py --genre 줄글 --strict \
    .claude/skills/anti-workslop/tests/fixtures/abstain/already-clean.md
python -X utf8 .claude/skills/anti-workslop/scripts/check_fidelity.py --strict \
    .claude/skills/anti-workslop/tests/fixtures/abstain/already-clean.md \
    .claude/skills/anti-workslop/tests/fixtures/abstain/already-clean.md
```

셋 다 exit 0 이면 기권이 옳은 판단이다. 고칠 것이 없는 글에 손대면 그 자체가 드리프트다.
