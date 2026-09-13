"""kamis.or.kr에 실제로 접속하지 않고, 응답 파싱 로직만 검증하는 테스트.

개발 환경에서 kamis.or.kr로의 아웃바운드 접속이 막혀 있어 실제 API 호출은
직접 검증하지 못했다. 대신 요청 URL이 올바르게 만들어지는지, 그리고 우리가
가정한 형태의 JSON 응답을 정상적으로 파싱하는지를 mock으로 확인한다.
실제 API 키로 처음 실행했을 때 응답 필드명이 다르면 이 테스트의 FAKE_RESPONSE도
같이 맞춰서 고치면 된다.
"""
from unittest.mock import MagicMock, patch

from src.kamis_client import (
    KamisClient,
    KamisCredentials,
    PRODUCT_CLS_RETAIL,
    PRODUCT_CLS_WHOLESALE,
)

FAKE_RESPONSE = {
    "condition": [{"p_regday": "2024-01-15"}],
    "data": {
        "error_code": "000",
        "item": [
            {"item_name": "양파", "unit": "kg", "price": "1,850"},
            {"item_name": "대파", "unit": "kg", "price": "2,300"},
            {"item_name": "배추", "unit": "포기", "price": "3,000"},
        ],
    },
}


def _make_mock_response(json_data):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_data
    return mock_resp


def test_get_daily_category_prices_parses_known_fields():
    client = KamisClient(credentials=KamisCredentials(cert_key="k", cert_id="i"))

    with patch("src.kamis_client.requests.get", return_value=_make_mock_response(FAKE_RESPONSE)) as mock_get:
        items = client.get_daily_category_prices(
            category_code="200",
            product_cls_code=PRODUCT_CLS_RETAIL,
            regday="2024-01-15",
        )

    assert mock_get.call_count == 1
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["action"] == "dailyPriceByCategoryList"
    assert called_params["p_item_category_code"] == "200"
    assert called_params["p_product_cls_code"] == PRODUCT_CLS_RETAIL
    assert called_params["p_returntype"] == "json"

    assert len(items) == 3
    onion = next(i for i in items if i.item_name == "양파")
    assert onion.price == 1850.0
    assert onion.unit == "kg"


def test_get_today_prices_filters_by_name_and_groups_by_cls():
    client = KamisClient(credentials=KamisCredentials(cert_key="k", cert_id="i"))

    with patch("src.kamis_client.requests.get", return_value=_make_mock_response(FAKE_RESPONSE)):
        result = client.get_today_prices(item_names=["양파", "대파"], regday="2024-01-15")

    assert set(result.keys()) == {"소매", "도매"}
    for label, items in result.items():
        names = {i.item_name for i in items}
        assert names == {"양파", "대파"}  # 배추는 걸러져야 함


def test_error_code_raises():
    from src.kamis_client import KamisApiError

    error_response = {"data": {"error_code": "600", "message": "인증 실패"}}
    client = KamisClient(credentials=KamisCredentials(cert_key="k", cert_id="i"))

    with patch("src.kamis_client.requests.get", return_value=_make_mock_response(error_response)):
        try:
            client.get_daily_category_prices(category_code="200", product_cls_code=PRODUCT_CLS_WHOLESALE)
            assert False, "KamisApiError가 발생해야 함"
        except KamisApiError:
            pass
