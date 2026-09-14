"""KAMIS 응답 파싱 로직 검증 테스트.

여기 담긴 FAKE_RESPONSE 구조는 실제 KAMIS API(action=dailyPriceByCategoryList,
category_code=200)를 발급받은 키로 호출해서 확인한 실제 응답 형태를 그대로
반영한 것이다 (가격은 dpr1 필드, "대파"/"쪽파" 구분은 item_name이 아니라
kind_name에 있음, 등급별로 여러 행이 나올 수 있음 등).
"""
from unittest.mock import MagicMock, patch

from src.kamis_client import (
    KamisClient,
    KamisCredentials,
    PRODUCT_CLS_RETAIL,
    PRODUCT_CLS_WHOLESALE,
)

FAKE_RESPONSE = {
    "condition": [{"p_regday": "2026-09-14"}],
    "data": {
        "error_code": "000",
        "item": [
            {"item_name": "양파", "kind_name": "양파(1kg)", "unit": "1kg", "dpr1": "1,847", "rank_code": "04"},
            {"item_name": "파", "kind_name": "대파(1kg)", "unit": "1kg", "dpr1": "2,760", "rank_code": "04"},
            {"item_name": "파", "kind_name": "쪽파(1kg)", "unit": "1kg", "dpr1": "11,874", "rank_code": "04"},
            {"item_name": "무", "kind_name": "고랭지(1개)", "unit": "1개", "dpr1": "2,113", "rank_code": "04"},
            {"item_name": "무", "kind_name": "고랭지(1개)", "unit": "1개", "dpr1": "1,904", "rank_code": "05"},
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
            regday="2026-09-14",
        )

    assert mock_get.call_count == 1
    called_params = mock_get.call_args.kwargs["params"]
    assert called_params["action"] == "dailyPriceByCategoryList"
    assert called_params["p_item_category_code"] == "200"
    assert called_params["p_product_cls_code"] == PRODUCT_CLS_RETAIL
    assert called_params["p_returntype"] == "json"

    assert len(items) == 5
    onion = next(i for i in items if i.item_name == "양파")
    assert onion.price == 1847.0
    assert onion.unit == "1kg"


def test_get_today_prices_matches_daepa_via_kind_name_not_jjokpa():
    """'대파'는 item_name이 아니라 kind_name에 있어서, kind_name까지 봐야 찾을 수 있다.
    같은 item_name('파')을 쓰는 '쪽파'는 걸러져야 한다."""
    client = KamisClient(credentials=KamisCredentials(cert_key="k", cert_id="i"))

    with patch("src.kamis_client.requests.get", return_value=_make_mock_response(FAKE_RESPONSE)):
        result = client.get_today_prices(item_names=["양파", "대파"], regday="2026-09-14")

    assert set(result.keys()) == {"소매", "도매"}
    for items in result.values():
        display_names = {i.display_name for i in items}
        assert display_names == {"양파(1kg)", "대파(1kg)"}  # 쪽파, 무는 제외되어야 함


def test_get_today_prices_prefers_grade_04_when_duplicated():
    client = KamisClient(credentials=KamisCredentials(cert_key="k", cert_id="i"))

    with patch("src.kamis_client.requests.get", return_value=_make_mock_response(FAKE_RESPONSE)):
        result = client.get_today_prices(item_names=["무"], regday="2026-09-14")

    for items in result.values():
        assert len(items) == 1
        assert items[0].rank_code == "04"
        assert items[0].price == 2113.0


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
