"""MVP에서 다루는 식재료 품목 정의.

KAMIS 품목분류코드(item_category_code)는 부류 단위(예: 200=채소류)로만 지정하고,
실제 품목은 KAMIS 응답 안의 item_name을 이 파일의 이름으로 매칭해서 걸러낸다.
이렇게 하면 품목코드(item_code)를 몰라도/틀려도 이름 기준으로 동작한다.
"""

VEGETABLE_CATEGORY_CODE = "200"  # KAMIS 부류코드: 채소류

TARGET_ITEMS = [
    {"name": "양파", "category_code": VEGETABLE_CATEGORY_CODE},
    {"name": "대파", "category_code": VEGETABLE_CATEGORY_CODE},
]

TARGET_ITEM_NAMES = [item["name"] for item in TARGET_ITEMS]
