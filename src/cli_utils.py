"""CLI 스크립트들이 공통으로 쓰는 "이름=값" 형태 인자 파싱 유틸."""
from __future__ import annotations


def parse_kv_pairs(pairs: list[str], example: str) -> dict[str, float]:
    """["양파=5", "대파=3"] -> {"양파": 5.0, "대파": 3.0}"""
    result: dict[str, float] = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        if not name or not value:
            raise SystemExit(f"형식이 잘못됐습니다 (예: {example}): {pair}")
        try:
            result[name.strip()] = float(value)
        except ValueError:
            raise SystemExit(f"숫자가 아닙니다 (예: {example}): {pair}")
    return result
