"""KAMIS(한국농수산식품유통공사) Open API 클라이언트.

사용하는 액션: dailyPriceByCategoryList (일별 부류별 도소매가격정보)
  - 부류코드(item_category_code) 하나를 넘기면 그 부류에 속한 모든 품목의
    "당일 도매/소매 평균가"를 하루치로 돌려준다.
  - 특정 품목 하나만 콕 집어 조회하는 파라미터는 없어서, 응답에서 item_name이
    우리가 찾는 품목명(예: "양파")을 포함하는 행만 걸러내는 방식으로 사용한다.

주의: 이 코드는 KAMIS 공식 문서와 공개된 예제 URL/파라미터명을 교차 확인해서
작성했지만, 실제 응답 JSON의 필드명은 개발 환경에서 kamis.or.kr 접속이 막혀
있어 실제 호출로 검증하지 못했다. 그래서 파싱 로직은 흔히 쓰이는 필드명 후보를
여러 개 시도하도록 방어적으로 작성했고, --raw 옵션으로 원본 응답을 그대로 볼 수
있게 해뒀다. 실제 API 키로 처음 실행해보고 필드명이 다르면 _PRICE_KEYS /
_NAME_KEYS 후보 목록만 조정하면 된다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import requests

KAMIS_BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"

PRODUCT_CLS_RETAIL = "01"  # 소매
PRODUCT_CLS_WHOLESALE = "02"  # 도매

PRODUCT_CLS_LABELS = {
    PRODUCT_CLS_RETAIL: "소매",
    PRODUCT_CLS_WHOLESALE: "도매",
}

DEFAULT_COUNTRY_CODE = "1101"  # 서울

# 응답 JSON에서 품목명/가격을 찾을 때 시도해볼 후보 필드명들 (우선순위 순)
_NAME_KEYS = ("item_name", "itemname")
_PRICE_KEYS = ("price", "dpr1", "value")
_UNIT_KEYS = ("unit",)


class KamisApiError(RuntimeError):
    """KAMIS API가 정상 데이터를 돌려주지 않았을 때 발생시키는 예외."""


@dataclass(frozen=True)
class KamisCredentials:
    cert_key: str
    cert_id: str

    @classmethod
    def from_env(cls) -> "KamisCredentials":
        cert_key = os.getenv("KAMIS_CERT_KEY")
        cert_id = os.getenv("KAMIS_CERT_ID")
        if not cert_key or not cert_id:
            raise RuntimeError(
                "KAMIS_CERT_KEY / KAMIS_CERT_ID 환경변수가 설정되어 있지 않습니다. "
                ".env.example을 복사해 .env를 만들고 값을 채워주세요."
            )
        return cls(cert_key=cert_key, cert_id=cert_id)


@dataclass
class ItemPrice:
    item_name: str
    unit: str
    product_cls_code: str
    regday: str
    price: float | None
    raw: dict[str, Any] = field(repr=False)

    @property
    def product_cls_label(self) -> str:
        return PRODUCT_CLS_LABELS.get(self.product_cls_code, self.product_cls_code)


def _first_present(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in d and d[key] not in (None, ""):
            return d[key]
    return None


def _parse_price(raw_value: Any) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    text = str(raw_value).replace(",", "").strip()
    if not text or text in ("-", "0"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


class KamisClient:
    """KAMIS Open API 호출을 담당하는 얇은 래퍼."""

    def __init__(
        self,
        credentials: KamisCredentials | None = None,
        country_code: str | None = None,
        timeout: float = 10.0,
    ):
        self.credentials = credentials or KamisCredentials.from_env()
        self.country_code = country_code or os.getenv("KAMIS_COUNTRY_CODE", DEFAULT_COUNTRY_CODE)
        self.timeout = timeout
        self.last_raw_response: dict[str, Any] | None = None

    def _request(self, action: str, params: dict[str, str]) -> dict[str, Any]:
        query = {
            "action": action,
            "p_cert_key": self.credentials.cert_key,
            "p_cert_id": self.credentials.cert_id,
            "p_returntype": "json",
            **params,
        }
        response = requests.get(KAMIS_BASE_URL, params=query, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        self.last_raw_response = payload
        return payload

    def get_daily_category_prices(
        self,
        *,
        category_code: str,
        product_cls_code: str,
        regday: str | None = None,
        convert_kg_yn: str = "Y",
    ) -> list[ItemPrice]:
        """부류코드 하나에 속한 모든 품목의 당일 도매/소매 평균가를 가져온다."""
        regday = regday or date.today().isoformat()
        payload = self._request(
            "dailyPriceByCategoryList",
            {
                "p_product_cls_code": product_cls_code,
                "p_item_category_code": category_code,
                "p_country_code": self.country_code,
                "p_regday": regday,
                "p_convert_kg_yn": convert_kg_yn,
            },
        )

        data = payload.get("data")
        if not isinstance(data, dict):
            raise KamisApiError(f"예상치 못한 응답 형식입니다: {payload}")

        error_code = data.get("error_code")
        if error_code not in (None, "000"):
            raise KamisApiError(f"KAMIS API 에러 (error_code={error_code}): {payload}")

        items = data.get("item", [])
        if isinstance(items, dict):  # 품목이 1개면 dict로 오는 경우 대비
            items = [items]

        results: list[ItemPrice] = []
        for raw_item in items:
            name = _first_present(raw_item, _NAME_KEYS)
            if name is None:
                continue
            price = _parse_price(_first_present(raw_item, _PRICE_KEYS))
            unit = _first_present(raw_item, _UNIT_KEYS) or ""
            results.append(
                ItemPrice(
                    item_name=str(name).strip(),
                    unit=str(unit).strip(),
                    product_cls_code=product_cls_code,
                    regday=regday,
                    price=price,
                    raw=raw_item,
                )
            )
        return results

    def get_today_prices(
        self,
        item_names: list[str],
        regday: str | None = None,
        category_code: str = "200",
    ) -> dict[str, list[ItemPrice]]:
        """item_names에 이름이 포함되는 품목들의 당일 소매/도매 평균가를 조회한다.

        반환값: {"소매": [ItemPrice, ...], "도매": [ItemPrice, ...]}
        """
        result: dict[str, list[ItemPrice]] = {}
        for product_cls_code in (PRODUCT_CLS_RETAIL, PRODUCT_CLS_WHOLESALE):
            all_items = self.get_daily_category_prices(
                category_code=category_code,
                product_cls_code=product_cls_code,
                regday=regday,
            )
            matched = [
                item
                for item in all_items
                if any(name in item.item_name for name in item_names)
            ]
            result[PRODUCT_CLS_LABELS[product_cls_code]] = matched
        return result
