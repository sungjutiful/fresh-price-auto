from src.supplier_simulator import MAX_VARIATION, MIN_VARIATION, generate_daily_prices, simulate_price


def test_simulate_price_within_expected_range():
    base = 1000.0
    price = simulate_price(base, "2026-09-14", "농협직거래마트", "양파")
    lower = base * (1 - MAX_VARIATION)
    upper = base * (1 + MAX_VARIATION)
    assert lower <= price <= upper
    # 최소 변동폭(10%)보다 안쪽인 [990,1010] 구간에는 절대 들어가지 않아야 한다
    assert not (base * (1 - MIN_VARIATION) < price < base * (1 + MIN_VARIATION))


def test_simulate_price_is_deterministic_for_same_day():
    args = (1000.0, "2026-09-14", "농협직거래마트", "양파")
    assert simulate_price(*args) == simulate_price(*args)


def test_simulate_price_changes_across_days():
    p1 = simulate_price(1000.0, "2026-09-14", "농협직거래마트", "양파")
    p2 = simulate_price(1000.0, "2026-09-15", "농협직거래마트", "양파")
    assert p1 != p2


def test_simulate_price_differs_by_supplier():
    p1 = simulate_price(1000.0, "2026-09-14", "농협직거래마트", "양파")
    p2 = simulate_price(1000.0, "2026-09-14", "청과유통센터", "양파")
    assert p1 != p2


def test_generate_daily_prices_covers_all_supplier_item_combinations():
    suppliers = [{"name": "A", "delivery_fee": 0, "min_order_amount": 0}, {"name": "B", "delivery_fee": 0, "min_order_amount": 0}]
    base_prices = {"양파": 1000.0, "대파": 2000.0}

    rows = generate_daily_prices(base_prices, suppliers, "2026-09-14")

    assert len(rows) == 4
    pairs = {(r["supplier_name"], r["item_name"]) for r in rows}
    assert pairs == {("A", "양파"), ("A", "대파"), ("B", "양파"), ("B", "대파")}
    for row in rows:
        assert row["regday"] == "2026-09-14"
        assert row["price"] > 0
