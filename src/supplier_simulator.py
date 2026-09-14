"""가상 공급처의 매일 품목 가격 시뮬레이션.

KAMIS 시세를 기준값으로 삼아 공급처별로 ±10~15% 범위에서 랜덤 변동시킨다.
같은 (날짜, 공급처, 품목) 조합에는 항상 같은 결과가 나오도록 결정론적 시드를
써서, 하루에 여러 번 조회해도 "오늘의 가격"이 흔들리지 않고 날짜가 바뀌면
자연스럽게 새 값으로 바뀌게 한다.

파이썬 내장 hash()는 프로세스마다 랜덤하게 시드가 바뀌어서(해시 시드 랜덤화)
재현 가능한 시드로 쓸 수 없다. 그래서 hashlib로 직접 계산한다.
"""
from __future__ import annotations

import hashlib
import random

MIN_VARIATION = 0.10
MAX_VARIATION = 0.15


def _daily_seed(regday: str, supplier_name: str, item_name: str) -> int:
    key = f"{regday}|{supplier_name}|{item_name}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest(), 16) % (2**32)


def simulate_price(base_price: float, regday: str, supplier_name: str, item_name: str) -> int:
    """기준가에서 ±10~15% 범위로 변동된 가격(원 단위 정수)을 계산한다."""
    rng = random.Random(_daily_seed(regday, supplier_name, item_name))
    magnitude = rng.uniform(MIN_VARIATION, MAX_VARIATION)
    direction = rng.choice((-1, 1))
    return round(base_price * (1 + direction * magnitude))


def generate_daily_prices(
    base_prices: dict[str, float],
    suppliers: list[dict],
    regday: str,
    unit: str = "kg",
) -> list[dict]:
    """공급처 x 품목 조합별 오늘의 시뮬레이션 가격 목록을 만든다.

    반환값: [{"supplier_name", "item_name", "unit", "price", "regday"}, ...]
    """
    rows = []
    for supplier in suppliers:
        for item_name, base_price in base_prices.items():
            price = simulate_price(base_price, regday, supplier["name"], item_name)
            rows.append(
                {
                    "supplier_name": supplier["name"],
                    "item_name": item_name,
                    "unit": unit,
                    "price": price,
                    "regday": regday,
                }
            )
    return rows
