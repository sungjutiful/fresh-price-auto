"""1단계: KAMIS API로 오늘의 양파/대파 소매·도매 평균가 가져오기.

사용법:
    python fetch_today_prices.py
    python fetch_today_prices.py --regday 2024-01-15
    python fetch_today_prices.py --raw   # 원본 JSON 응답도 함께 출력
"""
import argparse
import json
from datetime import date

import requests
from dotenv import load_dotenv

from config.items import TARGET_ITEM_NAMES, VEGETABLE_CATEGORY_CODE
from src.kamis_client import KamisApiError, KamisClient


def main() -> None:
    parser = argparse.ArgumentParser(description="KAMIS 오늘의 시세 조회")
    parser.add_argument("--regday", default=None, help="조회일 (YYYY-MM-DD), 기본값: 오늘")
    parser.add_argument("--raw", action="store_true", help="원본 JSON 응답도 출력")
    args = parser.parse_args()

    load_dotenv()

    regday = args.regday or date.today().isoformat()

    try:
        client = KamisClient()
        results = client.get_today_prices(
            item_names=TARGET_ITEM_NAMES,
            regday=regday,
            category_code=VEGETABLE_CATEGORY_CODE,
        )
    except (RuntimeError, KamisApiError) as exc:
        print(f"[에러] {exc}")
        raise SystemExit(1)
    except requests.exceptions.RequestException as exc:
        print(f"[에러] KAMIS 서버 호출에 실패했습니다: {exc}")
        print("네트워크 연결 또는 방화벽/프록시 설정을 확인해주세요.")
        raise SystemExit(1)

    print(f"KAMIS 시세 조회 결과 ({regday})")
    for label, items in results.items():
        print(f"\n=== {label} 평균가 ===")
        if not items:
            print("  조회된 품목이 없습니다.")
            continue
        for item in items:
            price_text = f"{item.price:,.0f}원" if item.price is not None else "가격 정보 없음"
            unit_text = f" / {item.unit}" if item.unit else ""
            print(f"  {item.display_name:12s} {price_text}{unit_text}")

    if args.raw:
        print("\n--- RAW RESPONSE (마지막 호출분) ---")
        print(json.dumps(client.last_raw_response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
