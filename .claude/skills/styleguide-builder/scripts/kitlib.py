# -*- coding: utf-8 -*-
"""
kitlib.py — styleguide-builder 스크립트 공통 유틸.

- Kit: styleguides/<slug>/ 의 경로·메타 (kit.json)
- sha256_bytes / sha256_file / sha256_text
- dump_json_sorted: 키 정렬·들여쓰기 1·ensure_ascii=False·끝 개행 → 같은 객체는 항상 같은 바이트
- assert_snapshot: posts.json 해시가 posts.sha256·stats.json 과 일치하는지, metrics.py 가 바뀌지 않았는지
- force_utf8_stdout: Windows 콘솔에서 한글 출력 보장
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_VERSION = "0.1.0"
KIT_SCHEMA = 1


def force_utf8_stdout() -> None:
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        try:
            if stream.encoding and stream.encoding.lower().replace("-", "") != "utf8":
                setattr(sys, name, io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))
        except Exception:  # pragma: no cover
            pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(t: str) -> str:
    return sha256_bytes(t.encode("utf-8"))


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def dump_json_sorted(obj, path: Path) -> str:
    text = json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:   # Windows 에서도 LF 고정 → 해시가 텍스트와 일치
        f.write(text)
    return text


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def resolve_skill_path(value: str) -> str:
    """profile 안의 '${SKILL_DIR}/…' 를 실제 경로로."""
    return value.replace("${SKILL_DIR}", str(SKILL_DIR)) if isinstance(value, str) else value


@dataclass
class Kit:
    root: Path
    meta: dict = field(default_factory=dict)

    @property
    def slug(self) -> str: return self.meta.get("slug", self.root.name)
    @property
    def corpus_dir(self) -> Path: return self.root / self.meta["paths"]["corpus"]
    @property
    def posts_json(self) -> Path: return self.corpus_dir / "posts.json"
    @property
    def posts_sha(self) -> Path: return self.corpus_dir / "posts.sha256"
    @property
    def stats_json(self) -> Path: return self.root / self.meta["paths"]["stats"]
    @property
    def stats_md(self) -> Path: return self.root / self.meta["paths"]["stats_md"]
    @property
    def targets_json(self) -> Path: return self.root / self.meta["paths"]["targets"]
    @property
    def profile_json(self) -> Path: return self.root / self.meta["paths"]["profile"]
    @property
    def reading_pack(self) -> Path: return self.root / self.meta["paths"]["reading_pack"]
    @property
    def worksheet(self) -> Path: return self.root / self.meta["paths"]["worksheet"]
    @property
    def guideline(self) -> Path: return self.root / self.meta["paths"]["guideline"]
    @property
    def verification(self) -> Path: return self.root / self.meta["paths"]["verification"]
    @property
    def render_manifest(self) -> Path: return self.root / "render-manifest.json"

    def profile(self) -> dict:
        return read_json(self.profile_json)

    def stats(self) -> dict:
        return read_json(self.stats_json)

    def targets(self) -> dict:
        return read_json(self.targets_json)

    def posts(self) -> list:
        return read_json(self.posts_json)


def load_kit(kit_dir: str | Path) -> Kit:
    root = Path(kit_dir).resolve()
    meta_path = root / "kit.json"
    if not meta_path.exists():
        raise SystemExit(f"kit.json 이 없습니다: {root}\n먼저 init_kit.py 로 키트를 만드세요.")
    meta = read_json(meta_path)
    if meta.get("schema_version") != KIT_SCHEMA:
        raise SystemExit(f"kit.json schema_version 이 {KIT_SCHEMA} 가 아닙니다: {meta.get('schema_version')}")
    return Kit(root=root, meta=meta)


def metrics_sha256() -> str:
    return sha256_file(SCRIPTS_DIR / "metrics.py")


def assert_snapshot(kit: Kit, need_stats: bool = True, need_targets: bool = False) -> dict:
    """입력 고정 확인. 실패하면 SystemExit 로 이유를 한국어로 알린다."""
    if not kit.posts_json.exists():
        raise SystemExit("corpus/posts.json 이 없습니다. collect.py 를 먼저 실행하세요.")
    digest = sha256_file(kit.posts_json)
    if kit.posts_sha.exists():
        recorded = kit.posts_sha.read_text(encoding="utf-8").strip()
        if recorded != digest:
            raise SystemExit("입력이 변경되었습니다: corpus/posts.json 해시가 posts.sha256 과 다릅니다. collect.py 를 다시 실행하세요.")
    info = {"corpus_sha256": digest, "metrics_sha256": metrics_sha256()}
    if need_stats:
        if not kit.stats_json.exists():
            raise SystemExit("stats.json 이 없습니다. analyze_corpus.py 를 실행하세요.")
        st = kit.stats()
        if st.get("corpus_sha256") != digest:
            raise SystemExit("stats.json 이 현재 코퍼스로 계산된 것이 아닙니다. analyze_corpus.py 를 다시 실행하세요.")
        if st.get("metrics_sha256") != info["metrics_sha256"]:
            raise SystemExit("지표 코드(metrics.py)가 바뀌었습니다. analyze_corpus.py 를 다시 실행하세요.")
        if st.get("profile_sha256") != sha256_file(kit.profile_json):
            raise SystemExit("profile.json 이 바뀌었습니다. analyze_corpus.py 를 다시 실행하세요.")
    if need_targets:
        if not kit.targets_json.exists():
            raise SystemExit("targets.json 이 없습니다. derive_targets.py 를 실행하세요.")
        tg = kit.targets()
        if tg.get("corpus_sha256") != digest:
            raise SystemExit("targets.json 이 현재 코퍼스로 계산된 것이 아닙니다. derive_targets.py 를 다시 실행하세요.")
    return info
