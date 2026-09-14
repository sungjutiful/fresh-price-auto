"""2단계: 가상 공급처별 오늘의 품목 가격 시뮬레이션.

KAMIS에서 오늘의 시세(도매 우선, 없으면 소매)를 기준값으로 가져와서, 가상
공급처 5곳의 품목별 가격을 ±10~15% 범위에서 랜덤 변동시켜 SQLite에 저장한다.

사용법:
    python simulate_supplier_prices.py
    python simulate_supplier_prices.py --regday 2024-01-15
    # KAMIS 호출 없이 기준값을 직접 지정 (오프라인 테스트/데모용)
    python simulate_supplier_prices.py --base-price 양파=1847 --base-price 대파=2760
"""
import argparse

import requests
from dotenv import load_dotenv

from config.items import TARGET_ITEM_NAMES, VEGETABLE_CATEGORY_CODE
from config.suppliers import SUPPLIERS
from src import db
from src.kamis_client import KamisApiError, KamisClient
from src.supplier_simulator import generate_daily_prices
from datetime import date


def _parse_base_price_args(pairs: list[str]) -> dict[str, float]:
    result = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        if not name or not value:
            raise SystemExit(f"--base-price 형식이 잘못됐습니다 (예: 양파=1847): {pair}")
        result[name.strip()] = float(value)
    return result


def get_base_prices_from_kamis(regday: str) -> dict[str, float]:
    """KAMIS에서 오늘 시세를 가져와 품목별 기준값을 정한다 (도매 우선, 없으면 소매)."""
    client = KamisClient()
    results = client.get_today_prices(
        item_names=TARGET_ITEM_NAMES,
        regday=regday,
        category_code=VEGETABLE_CATEGORY_CODE,
    )

    def _target_name(item) -> str | None:
        haystack = f"{item.item_name}{item.kind_name}"
        return next((name for name in TARGET_ITEM_NAMES if name in haystack), None)

    base_prices: dict[str, float] = {}
    for item in results.get("도매", []):
        name = _target_name(item)
        if name and item.price is not None:
            base_prices[name] = item.price
    for item in results.get("소매", []):
        name = _target_name(item)
        if name and name not in base_prices and item.price is not None:
            base_prices[name] = item.price
    return base_prices


def main() -> None:
    parser = argparse.ArgumentParser(description="가상 공급처 오늘의 가격 시뮬레이션")
    parser.add_argument("--regday", default=None, help="기준일 (YYYY-MM-DD), 기본값: 오늘")
    parser.add_argument(
        "--base-price",
        action="append",
        default=[],
        metavar="품목=가격",
        help="KAMIS 호출 대신 기준값을 직접 지정 (예: --base-price 양파=1847). 여러 번 지정 가능",
    )
    args = parser.parse_args()

    load_dotenv()
    regday = args.regday or date.today().isoformat()

    if args.base_price:
        base_prices = _parse_base_price_args(args.base_price)
    else:
        try:
            base_prices = get_base_prices_from_kamis(regday)
        except (RuntimeError, KamisApiError) as exc:
            print(f"[에러] {exc}")
            raise SystemExit(1)
        except requests.exceptions.RequestException as exc:
            print(f"[에러] KAMIS 서버 호출에 실패했습니다: {exc}")
            print("네트워크 문제로 KAMIS를 못 부르면 --base-price 옵션으로 직접 값을 넣어서 테스트할 수 있습니다.")
            print("예: python simulate_supplier_prices.py --base-price 양파=1847 --base-price 대파=2760")
            raise SystemExit(1)

    if not base_prices:
        print("[에러] 기준값을 하나도 구하지 못했습니다 (KAMIS에 해당 품목 가격이 없거나 --base-price 미지정).")
        raise SystemExit(1)

    rows = generate_daily_prices(base_prices, SUPPLIERS, regday)

    conn = db.get_connection()
    db.init_schema(conn)
    db.upsert_suppliers(conn, SUPPLIERS)
    db.save_supplier_prices(conn, rows)

    print(f"기준값 ({regday}): " + ", ".join(f"{name} {price:,.0f}원" for name, price in base_prices.items()))
    print()
    print(f"{'공급처':12s} {'배송비':>8s} {'최소주문금액':>12s}   " + "  ".join(f"{n:>10s}" for n in base_prices))
    for supplier in SUPPLIERS:
        prices = [r["price"] for r in rows if r["supplier_name"] == supplier["name"]]
        price_text = "  ".join(f"{p:>10,.0f}" for p in prices)
        print(
            f"{supplier['name']:12s} {supplier['delivery_fee']:>7,.0f}원 "
            f"{supplier['min_order_amount']:>11,.0f}원   {price_text}"
        )

    print(f"\n{len(rows)}건 저장 완료 -> {db.DB_PATH}")


if __name__ == "__main__":
    main()
