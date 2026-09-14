from src import db


def _make_conn(tmp_path):
    conn = db.get_connection(tmp_path / "test.db")
    db.init_schema(conn)
    return conn


def test_upsert_suppliers_and_save_prices(tmp_path):
    conn = _make_conn(tmp_path)
    suppliers = [
        {"name": "A공급처", "delivery_fee": 1000, "min_order_amount": 10000},
        {"name": "B공급처", "delivery_fee": 2000, "min_order_amount": 20000},
    ]
    db.upsert_suppliers(conn, suppliers)

    rows = [
        {"supplier_name": "A공급처", "item_name": "양파", "unit": "kg", "price": 1500, "regday": "2026-09-14"},
        {"supplier_name": "B공급처", "item_name": "양파", "unit": "kg", "price": 1600, "regday": "2026-09-14"},
    ]
    db.save_supplier_prices(conn, rows)

    result = db.get_supplier_prices(conn, "2026-09-14")
    assert len(result) == 2
    names = {r["supplier_name"] for r in result}
    assert names == {"A공급처", "B공급처"}


def test_save_supplier_prices_upserts_on_conflict(tmp_path):
    conn = _make_conn(tmp_path)
    db.upsert_suppliers(conn, [{"name": "A공급처", "delivery_fee": 1000, "min_order_amount": 10000}])

    row = {"supplier_name": "A공급처", "item_name": "양파", "unit": "kg", "price": 1500, "regday": "2026-09-14"}
    db.save_supplier_prices(conn, [row])
    db.save_supplier_prices(conn, [{**row, "price": 1700}])

    result = db.get_supplier_prices(conn, "2026-09-14")
    assert len(result) == 1
    assert result[0]["price"] == 1700


def test_upsert_suppliers_updates_existing(tmp_path):
    conn = _make_conn(tmp_path)
    db.upsert_suppliers(conn, [{"name": "A공급처", "delivery_fee": 1000, "min_order_amount": 10000}])
    db.upsert_suppliers(conn, [{"name": "A공급처", "delivery_fee": 9999, "min_order_amount": 88888}])

    supplier_id = db.get_supplier_id(conn, "A공급처")
    row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    assert row["delivery_fee"] == 9999
    assert row["min_order_amount"] == 88888
