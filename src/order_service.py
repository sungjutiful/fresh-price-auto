"""주문서 생성 -> 승인 -> 결제완료 흐름을 시뮬레이션하고 SQLite에 저장한다.

실제 결제/발주 연동은 하지 않는 목업이다. 상태는 정해진 순서로만 전이할 수
있고(생성 -> 승인 -> 결제완료), 순서를 건너뛰거나 되돌리면 InvalidTransitionError
가 발생한다.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from src.order_optimizer import OrderPlan

STATUS_CREATED = "생성"
STATUS_APPROVED = "승인"
STATUS_PAID = "결제완료"

_NEXT_STATUS = {STATUS_CREATED: STATUS_APPROVED, STATUS_APPROVED: STATUS_PAID}

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    regday TEXT NOT NULL,
    status TEXT NOT NULL,
    items_cost REAL NOT NULL,
    delivery_cost REAL NOT NULL,
    total_cost REAL NOT NULL,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    paid_at TEXT
);

CREATE TABLE IF NOT EXISTS order_suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    supplier_name TEXT NOT NULL,
    subtotal REAL NOT NULL,
    delivery_fee REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id),
    supplier_name TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    line_cost REAL NOT NULL
);
"""


class InvalidTransitionError(RuntimeError):
    """생성 -> 승인 -> 결제완료 순서를 벗어난 상태 전이를 시도했을 때 발생."""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_order(
    conn: sqlite3.Connection,
    regday: str,
    plan: OrderPlan,
    needs: dict[str, float],
) -> int:
    """최저가 조합(OrderPlan)으로 '생성' 상태의 주문서를 만든다."""
    cursor = conn.execute(
        """
        INSERT INTO orders (regday, status, items_cost, delivery_cost, total_cost, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (regday, STATUS_CREATED, plan.items_cost, plan.delivery_cost, plan.total_cost, _now()),
    )
    order_id = cursor.lastrowid

    for supplier_name, info in plan.supplier_breakdown.items():
        conn.execute(
            "INSERT INTO order_suppliers (order_id, supplier_name, subtotal, delivery_fee) VALUES (?, ?, ?, ?)",
            (order_id, supplier_name, info["subtotal"], info["delivery_fee"]),
        )
        for item_name, line_cost in info["items"].items():
            quantity = needs[item_name]
            unit_price = line_cost / quantity if quantity else 0.0
            conn.execute(
                """
                INSERT INTO order_items (order_id, supplier_name, item_name, quantity, unit_price, line_cost)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (order_id, supplier_name, item_name, quantity, unit_price, line_cost),
            )

    conn.commit()
    return order_id


def _get_status(conn: sqlite3.Connection, order_id: int) -> str:
    row = conn.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise ValueError(f"주문을 찾을 수 없습니다: {order_id}")
    return row["status"]


def _advance(conn: sqlite3.Connection, order_id: int, expected_current: str, timestamp_column: str) -> None:
    current = _get_status(conn, order_id)
    if current != expected_current:
        raise InvalidTransitionError(
            f"'{expected_current}' 상태의 주문만 다음 단계로 진행할 수 있습니다 (현재 상태: {current})."
        )
    next_status = _NEXT_STATUS[expected_current]
    conn.execute(
        f"UPDATE orders SET status = ?, {timestamp_column} = ? WHERE id = ?",
        (next_status, _now(), order_id),
    )
    conn.commit()


def approve_order(conn: sqlite3.Connection, order_id: int) -> None:
    _advance(conn, order_id, STATUS_CREATED, "approved_at")


def pay_order(conn: sqlite3.Connection, order_id: int) -> None:
    _advance(conn, order_id, STATUS_APPROVED, "paid_at")


def get_order(conn: sqlite3.Connection, order_id: int) -> dict:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise ValueError(f"주문을 찾을 수 없습니다: {order_id}")
    suppliers = conn.execute(
        "SELECT * FROM order_suppliers WHERE order_id = ? ORDER BY supplier_name", (order_id,)
    ).fetchall()
    items = conn.execute(
        "SELECT * FROM order_items WHERE order_id = ? ORDER BY supplier_name, item_name", (order_id,)
    ).fetchall()
    return {
        "order": dict(order),
        "suppliers": [dict(row) for row in suppliers],
        "items": [dict(row) for row in items],
    }


def list_orders(conn: sqlite3.Connection, regday: str | None = None) -> list[dict]:
    if regday:
        rows = conn.execute("SELECT * FROM orders WHERE regday = ? ORDER BY id", (regday,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
    return [dict(row) for row in rows]
