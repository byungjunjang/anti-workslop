# -*- coding: utf-8 -*-
"""jev(TypeSafe System One) 관문. 키가 있을 때만 켜지고, 없으면 아무것도 바꾸지 않는다.

  POST {base}/v1/systemone  ·  Authorization: Bearer $TYPESAFE_API_KEY

객관식으로 답이 정해지는 자리에만 쓴다 — 장르·문서 유형 판정(check_all --hint)과 의미 위험
1차 판정(semantic_review --jev). 재작성·사람 판단·검수 통과 판정에는 쓰지 않는다. 호출이
실패하면 None 과 사유를 돌려주고 부른 쪽이 현행 경로로 간다. 표준 라이브러리만 쓴다.

키는 프로젝트 루트의 .env 에서 읽는다(.env.example 참고). 끄기 · ANTI_WORKSLOP_JEV=0.
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent          # scripts
SKILL_DIR = HERE.parent                         # anti-workslop
ROOT = SKILL_DIR.parents[2]                     # skills → .claude → 프로젝트 루트
DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_BASE = "https://api.typesafe.ai"
STATE_LIMIT = 8000          # 관계없는 내용이 길수록 정확도가 떨어진다(모델 문서). 앞부분만 보낸다
RETRY_ON = (429, 529)
_ENV_LOADED = False


def load_env(path: Path | None = None) -> None:
    """루트 .env 를 읽어 아직 없는 환경변수만 채운다. 파일이 없으면 조용히 지나간다."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    p = Path(path) if path else ROOT / ".env"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def enabled(part: str | None = None) -> bool:
    """키가 있고 꺼져 있지 않은가. part 는 gate(입력 판정) 또는 semantic(의미 1차 판정)."""
    load_env()
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return False
    if os.environ.get("ANTI_WORKSLOP_JEV", "1") == "0":
        return False
    if part and os.environ.get(f"ANTI_WORKSLOP_JEV_{part.upper()}", "1") == "0":
        return False
    return True


def model_name() -> str:
    return os.environ.get("TYPESAFE_DEFAULT_MODEL") or DEFAULT_MODEL


def choice(instructions, criteria: dict) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def noul(instructions, criteria: dict | None = None) -> dict:
    q = {"type": "noul", "instructions": instructions}
    if criteria:
        q["criteria"] = criteria
    return q


def system_one(state, questions: dict, model: str | None = None, timeout: float = 10.0):
    """(응답, 사유). 실패면 (None, 사유). 429·529·연결 오류만 두 번 재시도한다."""
    load_env()
    key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not key:
        return None, "키 없음"
    base = os.environ.get("TYPESAFE_BASE_URL", DEFAULT_BASE).rstrip("/")
    payload = json.dumps({"state": state, "model": model or model_name(), "questions": questions},
                         ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        req = urllib.request.Request(f"{base}/v1/systemone", data=payload, method="POST",
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8")), ""
        except urllib.error.HTTPError as e:
            if e.code in RETRY_ON and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return None, f"HTTP {e.code}"
        except json.JSONDecodeError:
            return None, "응답이 JSON 이 아니다"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            return None, f"연결 실패({type(e).__name__})"
    return None, "재시도 소진"


def head(text: str, limit: int = STATE_LIMIT) -> str:
    """앞부분만 보낸다. 문단 경계에서 자른다."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n", 0, limit)
    return text[:cut if cut > limit // 2 else limit]


GENRE_CRITERIA = {
    "줄글": {"what": "문장으로 이어지는 산문. 서술형 종결(-습니다·-다)로 끝난다",
           "not_for": "항목을 나열한 보고서", "examples": ["블로그 글", "설명문", "업무 메일"]},
    "개조식": {"what": "항목을 나열하고 대부분을 명사형(-함·-음·-필요)이나 명사로 끝낸다",
            "not_for": "문장이 이어지는 산문", "examples": ["공공기관 보고서", "회의 안건", "추진 현황"]},
    "섞임": {"what": "산문 문단과 명사형 항목 목록이 비슷한 비중으로 섞여 있다",
           "not_for": "한쪽이 뚜렷이 많은 글", "examples": ["산문 도입 뒤 개조식 본문이 이어지는 문서"]},
}
DOC_TYPE_CRITERIA = {
    "논설·설명": {"what": "주장이나 설명을 펴는 글", "not_for": "시각·순서대로 적은 기록",
              "examples": ["분석 보고", "제안서", "블로그 글"]},
    "시간순": {"what": "일어난 순서대로 적은 기록", "not_for": "주장을 펴는 글",
            "examples": ["회의록", "장애 타임라인", "절차서", "런북", "튜토리얼"]},
    "감사·사과문": {"what": "감사나 사과를 전하는 글", "not_for": "사실을 설명하는 글",
               "examples": ["사과문", "감사 인사"]},
    "인용·전재": {"what": "글의 대부분이 법령·계약·타인 글의 인용이다", "not_for": "인용이 일부인 글",
              "examples": ["조문 해설", "판례 전재"]},
    "표·코드만": {"what": "본문 산문이 거의 없고 표나 코드로 이루어져 있다", "not_for": "산문이 있는 글",
              "examples": ["수치 표", "설정 파일 모음"]},
}


def classify_input(text: str):
    """{'genre': (값, 확신), 'doc_type': (값, 확신)} 또는 실패 사유 문자열."""
    data, why = system_one(head(text), {
        "genre": choice("이 글은 어느 형식으로 쓰였는가?", GENRE_CRITERIA),
        "doc_type": choice("이 글은 어떤 종류의 문서인가?", DOC_TYPE_CRITERIA)})
    if data is None:
        return why
    try:
        a = data["answers"]
        return {k: (a[k]["choice"], float(a[k]["confidence"])) for k in ("genre", "doc_type")}
    except (KeyError, TypeError, ValueError):
        return "응답 형식"
