"""3단계: 필요한 품목/수량을 입력하면 배송비·최소주문금액까지 반영한 실질
최저가 발주 조합을 계산한다. 한 공급처에서 몰아 사는 것(묶음)과 여러
공급처에 나눠 사는 것(분할)을 비교해서 더 저렴한 쪽을 추천한다.

사용법:
    python find_lowest_price.py --need 양파=5 --need 대파=3
    python find_lowest_price.py --need 양파=5 --need 대파=3 --regday 2026-09-14

미리 simulate_supplier_prices.py로 해당 날짜의 공급처 가격을 만들어둬야 한다.
"""
import argparse
from datetime import date

from config.suppliers import SUPPLIERS
from src import db
from src.order_optimizer import NoFeasiblePlanError, OrderPlan, SupplierCatalog, compare_bundle_vs_split


def _parse_needs(pairs: list[str]) -> dict[str, float]:
    needs = {}
    for pair in pairs:
        name, _, qty = pair.partition("=")
        if not name or not qty:
            raise SystemExit(f"--need 형식이 잘못됐습니다 (예: 양파=5): {pair}")
        needs[name.strip()] = float(qty)
    return needs


def _print_plan(title: str, plan: OrderPlan) -> None:
    print(f"[{title}] 총 {plan.total_cost:,.0f}원  (품목 {plan.items_cost:,.0f}원 + 배송비 {plan.delivery_cost:,.0f}원)")
    for supplier_name, info in plan.supplier_breakdown.items():
        items_text = ", ".join(f"{name} {cost:,.0f}원" for name, cost in info["items"].items())
        print(
            f"  - {supplier_name}: {items_text}  "
            f"(소계 {info['subtotal']:,.0f}원 / 최소주문 {info['min_order_amount']:,.0f}원, "
            f"배송비 {info['delivery_fee']:,.0f}원)"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="실질 최저가 발주 조합 계산")
    parser.add_argument(
        "--need", action="append", required=True, metavar="품목=수량",
        help="예: --need 양파=5 (단위: kg). 여러 번 지정 가능",
    )
    parser.add_argument("--regday", default=None, help="기준일 (YYYY-MM-DD), 기본값: 오늘")
    args = parser.parse_args()

    needs = _parse_needs(args.need)
    regday = args.regday or date.today().isoformat()

    conn = db.get_connection()
    db.init_schema(conn)
    price_rows = [dict(row) for row in db.get_supplier_prices(conn, regday)]

    if not price_rows:
        print(f"[에러] {regday} 기준 저장된 공급처 가격이 없습니다. 먼저 simulate_supplier_prices.py를 실행하세요.")
        raise SystemExit(1)

    catalog = SupplierCatalog.from_rows(SUPPLIERS, price_rows)

    try:
        result = compare_bundle_vs_split(needs, catalog)
    except NoFeasiblePlanError as exc:
        print(f"[에러] {exc}")
        raise SystemExit(1)

    print(f"필요 품목 ({regday}): " + ", ".join(f"{name} {qty:g}kg" for name, qty in needs.items()))
    print()

    if result.bundle_plan is not None:
        _print_plan("묶음 구매 (한 공급처)", result.bundle_plan)
    else:
        print("[묶음 구매] 모든 품목을 한 공급처에서 최소주문금액 이상으로 살 수 있는 곳이 없습니다.")
    print()
    _print_plan("전체 최적 조합", result.best_plan)
    print()

    if result.best_plan.is_split:
        if result.bundle_plan is None:
            print("=> 나눠서 사는 것을 추천합니다 (묶음으로는 주문이 불가능합니다).")
        else:
            saved = result.bundle_plan.total_cost - result.best_plan.total_cost
            print(f"=> 나눠서 사는 것을 추천합니다. 묶음 대비 {saved:,.0f}원 절약.")
    else:
        print("=> 한 공급처에서 묶어서 사는 것이 가장 저렴합니다.")


if __name__ == "__main__":
    main()
