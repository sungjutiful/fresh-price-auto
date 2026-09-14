import pytest

from src.order_optimizer import (
    NoFeasiblePlanError,
    SupplierCatalog,
    compare_bundle_vs_split,
    find_best_single_supplier_plan,
    find_cheapest_plan,
)

SUPPLIER_DEFS = [
    {"name": "A", "delivery_fee": 1000, "min_order_amount": 0},
    {"name": "B", "delivery_fee": 500, "min_order_amount": 0},
    {"name": "C", "delivery_fee": 0, "min_order_amount": 0},
]


def _rows(*triples):
    """triples: (supplier_name, item_name, price)"""
    return [{"supplier_name": s, "item_name": i, "price": p} for s, i, p in triples]


def test_split_wins_when_cheaper_than_any_single_supplier():
    rows = _rows(
        ("A", "양파", 1000), ("A", "대파", 1000),
        ("B", "양파", 900), ("B", "대파", 2000),
        ("C", "양파", 2000), ("C", "대파", 900),
    )
    catalog = SupplierCatalog.from_rows(SUPPLIER_DEFS, rows)
    needs = {"양파": 1, "대파": 1}

    result = compare_bundle_vs_split(needs, catalog)

    # 묶음 최적(C): 양파2000+대파900+배송0 = 2900
    # 나눠사면: B양파900+배송500 + C대파900+배송0 = 2300 (더 저렴)
    assert result.bundle_plan.total_cost == 2900
    assert result.best_plan.total_cost == 2300
    assert result.best_plan.is_split
    assert result.best_plan.assignment == {"양파": "B", "대파": "C"}


def test_prefers_bundle_on_tie():
    # A에서 묶어사면 배송비 포함 2000원, B+C로 나눠사도 2000원으로 동일 -> 묶음(공급처 1개) 우선
    supplier_defs = [
        {"name": "A", "delivery_fee": 0, "min_order_amount": 0},
        {"name": "B", "delivery_fee": 0, "min_order_amount": 0},
        {"name": "C", "delivery_fee": 0, "min_order_amount": 0},
    ]
    rows = _rows(
        ("A", "양파", 1000), ("A", "대파", 1000),
        ("B", "양파", 1000), ("B", "대파", 1500),
        ("C", "양파", 1500), ("C", "대파", 1000),
    )
    catalog = SupplierCatalog.from_rows(supplier_defs, rows)
    needs = {"양파": 1, "대파": 1}

    plan = find_cheapest_plan(needs, catalog)

    assert plan.total_cost == 2000
    assert not plan.is_split


def test_min_order_amount_excludes_infeasible_supplier():
    supplier_defs = [
        {"name": "A", "delivery_fee": 0, "min_order_amount": 100000},  # 도달 불가능한 최소주문금액
        {"name": "B", "delivery_fee": 0, "min_order_amount": 0},
    ]
    rows = _rows(("A", "양파", 100), ("B", "양파", 200))
    catalog = SupplierCatalog.from_rows(supplier_defs, rows)

    plan = find_cheapest_plan({"양파": 1}, catalog)

    assert plan.assignment["양파"] == "B"


def test_no_supplier_sells_item_raises():
    catalog = SupplierCatalog.from_rows(SUPPLIER_DEFS, _rows(("A", "양파", 1000)))
    with pytest.raises(NoFeasiblePlanError):
        find_cheapest_plan({"대파": 1}, catalog)


def test_all_combos_infeasible_due_to_min_order_raises():
    supplier_defs = [{"name": "A", "delivery_fee": 0, "min_order_amount": 999999}]
    catalog = SupplierCatalog.from_rows(supplier_defs, _rows(("A", "양파", 1000)))
    with pytest.raises(NoFeasiblePlanError):
        find_cheapest_plan({"양파": 1}, catalog)


def test_find_best_single_supplier_plan_returns_none_when_no_supplier_has_everything():
    rows = _rows(("A", "양파", 1000), ("B", "대파", 1000))
    catalog = SupplierCatalog.from_rows(SUPPLIER_DEFS, rows)
    assert find_best_single_supplier_plan({"양파": 1, "대파": 1}, catalog) is None
