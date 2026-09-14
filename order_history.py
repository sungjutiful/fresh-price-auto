"""저장된 발주 내역을 조회한다.

사용법:
    python order_history.py                       # 전체 주문 목록
    python order_history.py --regday 2026-09-14    # 특정 날짜 주문 목록
    python order_history.py --order-id 3           # 특정 주문 상세
"""
import argparse

from src import db, order_service


def _print_summary(order: dict) -> None:
    print(
        f"#{order['id']:<4} {order['regday']}  {order['status']:6s}  "
        f"총 {order['total_cost']:>10,.0f}원  생성 {order['created_at']}"
    )


def _print_detail(detail: dict) -> None:
    order = detail["order"]
    print(f"주문 #{order['id']} ({order['regday']}) - 상태: {order['status']}")
    print(f"  생성: {order['created_at']}")
    if order["approved_at"]:
        print(f"  승인: {order['approved_at']}")
    if order["paid_at"]:
        print(f"  결제: {order['paid_at']}")
    print(
        f"  총액: {order['total_cost']:,.0f}원 "
        f"(품목 {order['items_cost']:,.0f}원 + 배송비 {order['delivery_cost']:,.0f}원)"
    )
    print()
    for supplier in detail["suppliers"]:
        items = [i for i in detail["items"] if i["supplier_name"] == supplier["supplier_name"]]
        items_text = ", ".join(
            f"{i['item_name']} {i['quantity']:g}kg x {i['unit_price']:,.0f}원 = {i['line_cost']:,.0f}원"
            for i in items
        )
        print(f"  - {supplier['supplier_name']}: {items_text} (배송비 {supplier['delivery_fee']:,.0f}원)")


def main() -> None:
    parser = argparse.ArgumentParser(description="발주 내역 조회")
    parser.add_argument("--regday", default=None, help="특정 날짜의 주문만 보기")
    parser.add_argument("--order-id", type=int, default=None, help="특정 주문 상세 보기")
    args = parser.parse_args()

    conn = db.get_connection()
    db.init_schema(conn)
    order_service.init_schema(conn)

    if args.order_id is not None:
        try:
            detail = order_service.get_order(conn, args.order_id)
        except ValueError as exc:
            print(f"[에러] {exc}")
            raise SystemExit(1)
        _print_detail(detail)
        return

    orders = order_service.list_orders(conn, args.regday)
    if not orders:
        print("저장된 주문 내역이 없습니다.")
        return
    for order in orders:
        _print_summary(order)


if __name__ == "__main__":
    main()
