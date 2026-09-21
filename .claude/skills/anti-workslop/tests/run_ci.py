"""Run in an isolated temporary checkout without personal taste or network."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
def main():
    with tempfile.TemporaryDirectory(prefix='anti-workslop-ci-') as tmp:
        target = Path(tmp) / 'repo'
        def ignore(path, names):
            skipped = {'.git', '__pycache__', '.pytest_cache', 'docs', 'examples'} & set(names)
            if Path(path) == ROOT / 'taste':
                skipped |= set(names) - {'README.md'}
            return skipped
        shutil.copytree(ROOT, target, ignore=ignore)
        env = {**os.environ, 'PYTHONUTF8': '1'}
        # 환경 검사를 먼저 돌린다. 의존성 누락이나 파서 의존은 긴 인수 테스트를
        # 기다릴 것 없이 바로 드러나야 한다.
        subprocess.run([sys.executable, '-X', 'utf8', '.claude/skills/anti-workslop/tests/test_environment.py'], cwd=target, env=env, check=True)
        for skill in ('anti-workslop', 'styleguide-builder', 'taste-builder'):
            subprocess.run([sys.executable, '-X', 'utf8', f'.claude/skills/{skill}/tests/run_acceptance.py'], cwd=target, env=env, check=True)
        subprocess.run([sys.executable, '-X', 'utf8', '.claude/skills/anti-workslop/tests/test_semantic_review.py'], cwd=target, env=env, check=True)
    print('CI suites passed without private taste')
if __name__ == '__main__':
    main()
