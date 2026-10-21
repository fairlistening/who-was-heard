"""규칙 파일(preset) — 정리 규칙은 코드에 박지 않고 파일로 둔다.

규칙 자체가 판단이다. 그래서 파일로 드러내고, 보고서에 이름·버전·지문(sha256)·패턴 전체를 찍는다.
같은 자료 + 같은 규칙 파일 = 같은 결과. 다르면 규칙이 달랐다는 게 드러난다.

Rules are not hard-coded. They live in readable preset files; the report
prints the preset name, version, sha256 fingerprint and every pattern.
"""
from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.join(os.path.dirname(__file__), "presets")


def available():
    return sorted(f[:-5] for f in os.listdir(HERE) if f.endswith(".json"))


def load(name_or_path: str) -> dict:
    p = name_or_path if os.path.exists(name_or_path) else os.path.join(HERE, f"{name_or_path}.json")
    if not os.path.exists(p):
        raise FileNotFoundError(f"규칙 파일이 없습니다: {name_or_path} (있는 것: {', '.join(available())})")
    with open(p, "rb") as f:
        raw = f.read()
    d = json.loads(raw.decode("utf-8"))
    d["_sha256"] = hashlib.sha256(raw).hexdigest()[:12]
    d["_file"] = os.path.basename(p)
    return d


def describe(d: dict) -> str:
    return f"{d.get('name')} v{d.get('version')} · sha256 {d.get('_sha256')} · 패턴 {len(d.get('exclude_patterns', []))}개"
