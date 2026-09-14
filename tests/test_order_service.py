import pytest

from src import db, order_service
from src.order_optimizer import OrderPlan


def _make_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.db")
    db.init_schema(conn)
    order_service.init_schema(conn)
    return conn


def _sample_plan() -> OrderPlan:
    return OrderPlan(
        assignment={"양파": "A", "대파": "B"},
        items_cost=3000,
        delivery_cost=1500,
        total_cost=4500,
        supplier_breakdown={
            "A": {"items": {"양파": 1000}, "subtotal": 1000, "delivery_fee": 1000, "min_order_amount": 0},
            "B": {"items": {"대파": 2000}, "subtotal": 2000, "delivery_fee": 500, "min_order_amount": 0},
        },
    )


def test_create_order_persists_suppliers_and_items(tmp_path):
    conn = _make_conn(tmp_path)
    order_id = order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})

    detail = order_service.get_order(conn, order_id)
    assert detail["order"]["status"] == order_service.STATUS_CREATED
    assert detail["order"]["total_cost"] == 4500
    assert {s["supplier_name"] for s in detail["suppliers"]} == {"A", "B"}
    assert {i["item_name"] for i in detail["items"]} == {"양파", "대파"}


def test_full_flow_created_to_paid(tmp_path):
    conn = _make_conn(tmp_path)
    order_id = order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})

    order_service.approve_order(conn, order_id)
    order_service.pay_order(conn, order_id)

    detail = order_service.get_order(conn, order_id)
    assert detail["order"]["status"] == order_service.STATUS_PAID
    assert detail["order"]["approved_at"] is not None
    assert detail["order"]["paid_at"] is not None


def test_cannot_pay_before_approval(tmp_path):
    conn = _make_conn(tmp_path)
    order_id = order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})

    with pytest.raises(order_service.InvalidTransitionError):
        order_service.pay_order(conn, order_id)


def test_cannot_approve_twice(tmp_path):
    conn = _make_conn(tmp_path)
    order_id = order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})
    order_service.approve_order(conn, order_id)

    with pytest.raises(order_service.InvalidTransitionError):
        order_service.approve_order(conn, order_id)


def test_cannot_approve_after_paid(tmp_path):
    conn = _make_conn(tmp_path)
    order_id = order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})
    order_service.approve_order(conn, order_id)
    order_service.pay_order(conn, order_id)

    with pytest.raises(order_service.InvalidTransitionError):
        order_service.approve_order(conn, order_id)


def test_list_orders_filters_by_regday(tmp_path):
    conn = _make_conn(tmp_path)
    order_service.create_order(conn, "2026-09-14", _sample_plan(), {"양파": 1, "대파": 1})
    order_service.create_order(conn, "2026-09-15", _sample_plan(), {"양파": 1, "대파": 1})

    assert len(order_service.list_orders(conn)) == 2
    assert len(order_service.list_orders(conn, "2026-09-14")) == 1


def test_get_order_missing_raises(tmp_path):
    conn = _make_conn(tmp_path)
    with pytest.raises(ValueError):
        order_service.get_order(conn, 999)
