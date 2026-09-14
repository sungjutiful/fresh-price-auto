"""MVP에서 다루는 가상 공급처 정의.

실제 업체 API가 없어서, 배송비/최소주문금액이 서로 다른 5개의 가상 공급처를
하드코딩한다. 품목별 가격은 여기서 정하지 않고, KAMIS 시세를 기준값으로 매일
랜덤 시뮬레이션한다 (src/supplier_simulator.py 참고).
"""

SUPPLIERS = [
    {"name": "농협직거래마트", "delivery_fee": 3000, "min_order_amount": 30000},
    {"name": "청과유통센터", "delivery_fee": 5000, "min_order_amount": 50000},
    {"name": "산지직송마켓", "delivery_fee": 0, "min_order_amount": 100000},
    {"name": "새벽배송푸드", "delivery_fee": 4000, "min_order_amount": 20000},
    {"name": "도매유통상회", "delivery_fee": 2000, "min_order_amount": 80000},
]
