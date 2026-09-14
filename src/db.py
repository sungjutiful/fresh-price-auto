"""SQLite 연결 및 스키마 관리.

DB 파일은 data/fresh_price_auto.db에 만든다 (.gitignore에 *.db 포함되어 있어
저장소에는 커밋되지 않고, 실행할 때마다 로컬에 생성/재사용된다).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "fresh_price_auto.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    delivery_fee INTEGER NOT NULL,
    min_order_amount INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id),
    item_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    price REAL NOT NULL,
    regday TEXT NOT NULL,
    UNIQUE(supplier_id, item_name, regday)
);
"""


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_suppliers(conn: sqlite3.Connection, suppliers: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO suppliers (name, delivery_fee, min_order_amount)
        VALUES (:name, :delivery_fee, :min_order_amount)
        ON CONFLICT(name) DO UPDATE SET
            delivery_fee = excluded.delivery_fee,
            min_order_amount = excluded.min_order_amount
        """,
        suppliers,
    )
    conn.commit()


def get_supplier_id(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM suppliers WHERE name = ?", (name,)).fetchone()
    if row is None:
        raise ValueError(f"공급처를 찾을 수 없습니다: {name}")
    return row["id"]


def save_supplier_prices(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """rows: [{"supplier_name", "item_name", "unit", "price", "regday"}, ...]"""
    conn.executemany(
        """
        INSERT INTO supplier_prices (supplier_id, item_name, unit, price, regday)
        VALUES (
            (SELECT id FROM suppliers WHERE name = :supplier_name),
            :item_name, :unit, :price, :regday
        )
        ON CONFLICT(supplier_id, item_name, regday) DO UPDATE SET
            price = excluded.price,
            unit = excluded.unit
        """,
        rows,
    )
    conn.commit()


def get_supplier_prices(conn: sqlite3.Connection, regday: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT s.name AS supplier_name, s.delivery_fee, s.min_order_amount,
               sp.item_name, sp.unit, sp.price, sp.regday
        FROM supplier_prices sp
        JOIN suppliers s ON s.id = sp.supplier_id
        WHERE sp.regday = ?
        ORDER BY s.name, sp.item_name
        """,
        (regday,),
    ).fetchall()
