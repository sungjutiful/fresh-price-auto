"""배송비·최소주문금액까지 반영한 실질 최저가 발주 조합 계산.

품목별로 "어느 공급처에서 살지"를 정하는 문제로 본다 (한 품목의 수량을 여러
공급처에 나눠 사는 것까지는 다루지 않는다 — MVP 범위). 공급처 수를 S, 품목
수를 N이라 하면 가능한 조합은 S^N개인데, 식당이 하루에 발주하는 품목 수는
많아야 10~20개 수준이라 완전탐색으로도 충분히 빠르다.

여러 품목을 한 공급처에서 묶어 사는 게 나은지, 나눠 사는 게 나은지는
find_best_single_supplier_plan(묶음 전용)과 find_cheapest_plan(분할 허용,
전체 탐색)을 각각 구해서 compare_bundle_vs_split으로 비교한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any


class NoFeasiblePlanError(RuntimeError):
    """모든 조합이 불가능할 때(품목을 파는 곳이 없거나 최소주문금액 미달) 발생."""


@dataclass(frozen=True)
class SupplierCatalog:
    """하루치 공급처 가격 데이터.

    suppliers: {supplier_name: {"delivery_fee": int, "min_order_amount": int,
                                 "prices": {item_name: unit_price}}}
    """

    suppliers: dict[str, dict[str, Any]]

    @classmethod
    def from_rows(cls, supplier_defs: list[dict], price_rows: list[dict]) -> "SupplierCatalog":
        suppliers = {
            s["name"]: {
                "delivery_fee": s["delivery_fee"],
                "min_order_amount": s["min_order_amount"],
                "prices": {},
            }
            for s in supplier_defs
        }
        for row in price_rows:
            name = row["supplier_name"]
            if name in suppliers:
                suppliers[name]["prices"][row["item_name"]] = row["price"]
        return cls(suppliers)

    def suppliers_for_item(self, item_name: str) -> list[str]:
        return [name for name, info in self.suppliers.items() if item_name in info["prices"]]


@dataclass
class OrderPlan:
    assignment: dict[str, str]  # item_name -> supplier_name
    items_cost: float  # 품목 가격 합계 (배송비 제외)
    delivery_cost: float  # 사용된 공급처들의 배송비 합계
    total_cost: float
    supplier_breakdown: dict[str, dict] = field(default_factory=dict)

    @property
    def is_split(self) -> bool:
        return len(set(self.assignment.values())) > 1


@dataclass
class ComparisonResult:
    bundle_plan: OrderPlan | None  # 한 공급처에서 전부 사는 최적안 (불가능하면 None)
    best_plan: OrderPlan  # 분할까지 허용한 전체 탐색 최적안


def _build_supplier_breakdown(
    catalog: SupplierCatalog, needs: dict[str, float], per_supplier: dict[str, list[str]]
) -> tuple[dict[str, dict], float, float]:
    supplier_breakdown: dict[str, dict] = {}
    items_cost = 0.0
    delivery_cost = 0.0
    for supplier_name, item_list in per_supplier.items():
        info = catalog.suppliers[supplier_name]
        item_costs = {item: needs[item] * info["prices"][item] for item in item_list}
        subtotal = sum(item_costs.values())
        items_cost += subtotal
        delivery_cost += info["delivery_fee"]
        supplier_breakdown[supplier_name] = {
            "items": item_costs,
            "subtotal": subtotal,
            "delivery_fee": info["delivery_fee"],
            "min_order_amount": info["min_order_amount"],
        }
    return supplier_breakdown, items_cost, delivery_cost


def _plan_sort_key(plan: OrderPlan) -> tuple[float, int]:
    # 비용이 같으면 공급처 수가 적은(단순한) 조합을 우선한다.
    return (plan.total_cost, len(set(plan.assignment.values())))


def find_cheapest_plan(needs: dict[str, float], catalog: SupplierCatalog) -> OrderPlan:
    """모든 공급처 배정 조합을 탐색해 실질 비용이 가장 낮은 조합을 찾는다 (분할 허용)."""
    if not needs:
        raise ValueError("needs가 비어 있습니다.")

    item_names = list(needs.keys())
    options_per_item: list[list[str]] = []
    for item_name in item_names:
        suppliers = catalog.suppliers_for_item(item_name)
        if not suppliers:
            raise NoFeasiblePlanError(f"'{item_name}'을(를) 판매하는 공급처가 없습니다.")
        options_per_item.append(suppliers)

    best: OrderPlan | None = None

    for combo in product(*options_per_item):
        assignment = dict(zip(item_names, combo))

        per_supplier: dict[str, list[str]] = {}
        for item_name, supplier_name in assignment.items():
            per_supplier.setdefault(supplier_name, []).append(item_name)

        if any(
            sum(needs[i] * catalog.suppliers[s]["prices"][i] for i in items) < catalog.suppliers[s]["min_order_amount"]
            for s, items in per_supplier.items()
        ):
            continue  # 이 조합에 쓰인 공급처 중 최소주문금액 미달인 곳이 있음

        supplier_breakdown, items_cost, delivery_cost = _build_supplier_breakdown(catalog, needs, per_supplier)
        candidate = OrderPlan(
            assignment=assignment,
            items_cost=items_cost,
            delivery_cost=delivery_cost,
            total_cost=items_cost + delivery_cost,
            supplier_breakdown=supplier_breakdown,
        )

        if best is None or _plan_sort_key(candidate) < _plan_sort_key(best):
            best = candidate

    if best is None:
        raise NoFeasiblePlanError(
            "모든 조합이 최소주문금액을 만족하지 못합니다. 수량을 늘리거나 다른 공급처를 확인하세요."
        )
    return best


def find_best_single_supplier_plan(needs: dict[str, float], catalog: SupplierCatalog) -> OrderPlan | None:
    """모든 품목을 한 공급처에서만 사는 경우 중 가장 저렴한 곳을 찾는다. 불가능하면 None."""
    best: OrderPlan | None = None
    for supplier_name, info in catalog.suppliers.items():
        if not all(item in info["prices"] for item in needs):
            continue
        per_supplier = {supplier_name: list(needs.keys())}
        subtotal = sum(needs[i] * info["prices"][i] for i in needs)
        if subtotal < info["min_order_amount"]:
            continue
        supplier_breakdown, items_cost, delivery_cost = _build_supplier_breakdown(catalog, needs, per_supplier)
        candidate = OrderPlan(
            assignment={item: supplier_name for item in needs},
            items_cost=items_cost,
            delivery_cost=delivery_cost,
            total_cost=items_cost + delivery_cost,
            supplier_breakdown=supplier_breakdown,
        )
        if best is None or candidate.total_cost < best.total_cost:
            best = candidate
    return best


def compare_bundle_vs_split(needs: dict[str, float], catalog: SupplierCatalog) -> ComparisonResult:
    """묶음 구매 최적안과, 분할까지 허용한 전체 최적안을 함께 계산한다."""
    best_plan = find_cheapest_plan(needs, catalog)
    bundle_plan = find_best_single_supplier_plan(needs, catalog)
    return ComparisonResult(bundle_plan=bundle_plan, best_plan=best_plan)
