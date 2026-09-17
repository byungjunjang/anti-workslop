"""RT-01 전달 경로와 의미 보존 방어 회귀. 의미의 적절성은 eval 기록에서 별도 판단한다."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import check_all


def test_report_titles():
    rule = check_all.REPORT_TITLES.read_text(encoding="utf-8").strip()
    bg = check_all.load_bg()
    # 문체와 무관하게 정확한 규칙 전문을 전달: 기본 둘, 없음, 사용자 등록 가이드.
    bg["회귀가이드"] = bg["장피엠"]
    bg["_genre_of"]["회귀가이드"] = "줄글"
    for guide in ("장피엠", "개조식", "없음", "회귀가이드"):
        packed = check_all.pack(bg, guide, ())
        assert packed.count(rule) == 1, guide
    brief = check_all.BRIEF.read_text(encoding="utf-8")
    for token in ("RT-01", "자동 검사 통과만으로", "수정 전 제목", "수정 후 제목", "본문 근거", "확정 수준", "첫 문장 반복", "고친 제목 없이"):
        assert token in brief, token
    # 실제 CLI도 Markdown/HTML에서 브리프 + 규칙을 함께 전달한다.
    with tempfile.TemporaryDirectory() as td:
        for ext, content in (("md", "# 검토 방향\n\n시범 적용을 권고합니다.\n"),
                             ("html", "<h1>검토 방향</h1><p>시범 적용을 권고합니다.</p>")):
            source = Path(td) / ("원문." + ext)
            source.write_text(content, encoding="utf-8")
            r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "check_all.py"),
                                "--guide", "없음", "--bundle", str(source)],
                               cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
            assert r.returncode == 0, r.stderr
            assert rule in r.stdout and r.stdout.startswith("# 서브에이전트 브리프"), ext
        # 제목의 기존 조건 경고(S2)·부정/수치 차단(S1)을 유지한다. 조건 의미는 담당이 반드시 대조한다.
        before = Path(td) / "before.md"
        after = Path(td) / "after.md"
        for original, changed, severity, code in (("예산을 확보한 경우에만 시행", "시행", "S2", 0),
                                                  ("확대하지 않습니다", "확대합니다", "S1", 1),
                                                  ("지원 한도 20억 원", "지원 한도 30억 원", "S1", 1)):
            before.write_text("# " + original + "\n\n검토를 진행합니다.\n", encoding="utf-8")
            after.write_text("# " + changed + "\n\n검토를 진행합니다.\n", encoding="utf-8")
            r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "check_fidelity.py"),
                                "--strict", "--json", str(before), str(after)], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            data = json.loads(r.stdout)
            assert r.returncode == code and data["summary"]["by_severity"].get(severity, 0) > 0, data
    print("PASS test_report_titles (전달 경로·의미 보존 방어, 의미 판단은 별도 eval)")


if __name__ == "__main__":
    test_report_titles()
