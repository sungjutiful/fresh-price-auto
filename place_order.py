"""4단계: 최저가 조합으로 주문서를 만들고 생성 -> 승인 -> 결제완료 흐름을
시뮬레이션한다. 실제 결제/발주 연동은 하지 않는 목업이다.

사용법:
    python place_order.py --need 양파=60 --need 대파=40
    python place_order.py --need 양파=60 --need 대파=40 --regday 2026-09-14

미리 simulate_supplier_prices.py로 해당 날짜의 공급처 가격을 만들어둬야 한다.
"""
import argparse
from datetime import date

from config.suppliers import SUPPLIERS
from src import db, order_service
from src.cli_utils import parse_kv_pairs
from src.order_optimizer import NoFeasiblePlanError, SupplierCatalog, compare_bundle_vs_split


def main() -> None:
    parser = argparse.ArgumentParser(description="최저가 조합으로 주문서 생성 -> 승인 -> 결제완료 시뮬레이션")
    parser.add_argument(
        "--need", action="append", required=True, metavar="품목=수량",
        help="예: --need 양파=60 (단위: kg). 여러 번 지정 가능",
    )
    parser.add_argument("--regday", default=None, help="기준일 (YYYY-MM-DD), 기본값: 오늘")
    args = parser.parse_args()

    needs = parse_kv_pairs(args.need, "양파=60")
    regday = args.regday or date.today().isoformat()

    conn = db.get_connection()
    db.init_schema(conn)
    order_service.init_schema(conn)

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

    plan = result.best_plan

    print(f"필요 품목 ({regday}): " + ", ".join(f"{name} {qty:g}kg" for name, qty in needs.items()))
    print(f"선택된 조합: 총 {plan.total_cost:,.0f}원 " + ("(분할 구매)" if plan.is_split else "(묶음 구매)"))
    for supplier_name, info in plan.supplier_breakdown.items():
        items_text = ", ".join(f"{name} {cost:,.0f}원" for name, cost in info["items"].items())
        print(f"  - {supplier_name}: {items_text} (배송비 {info['delivery_fee']:,.0f}원)")
    print()

    order_id = order_service.create_order(conn, regday, plan, needs)
    print(f"[1/3] 주문서 생성 완료 (주문번호 #{order_id}, 상태: {order_service.STATUS_CREATED})")

    order_service.approve_order(conn, order_id)
    print(f"[2/3] 주문 승인 완료 (상태: {order_service.STATUS_APPROVED})")

    order_service.pay_order(conn, order_id)
    print(f"[3/3] 결제 완료 (상태: {order_service.STATUS_PAID}) — 실제 결제는 이뤄지지 않은 목업입니다.")

    print(f"\n상세 내역 조회: python order_history.py --order-id {order_id}")


if __name__ == "__main__":
    main()
