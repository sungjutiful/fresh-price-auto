"""쿠팡(로켓프레시 등)에서 최적 발주 조합을 장바구니에 자동으로 담고,
결제 직전 화면에서 멈춰서 사장님이 최종 확인 후 직접 결제 버튼을 누르게
하는 반자동 브라우저 도우미.

**반드시 사장님 개인 컴퓨터에서 직접 실행해야 합니다.** 원격 서버(이 코드를
만든 개발 환경 포함)에서는 실행할 수 없습니다 — 사장님의 실제 쿠팡 로그인
세션이 있는 브라우저가 필요하기 때문입니다.

동작 방식:
  1. 사장님 컴퓨터의 크롬 브라우저를 직접 띄웁니다 (화면에 보임, headless 아님).
  2. 처음 실행할 땐 사장님이 직접 쿠팡에 로그인해야 합니다 (딱 한 번만).
     로그인 세션은 이 폴더 안(.browser_profile/)에 저장되어, 다음부터는
     자동으로 로그인된 상태로 시작합니다.
  3. 필요한 품목을 하나씩 검색해서 장바구니에 담습니다.
  4. 장바구니 화면에서 멈춥니다. **결제 버튼은 이 스크립트가 절대 자동으로
     누르지 않습니다** — 상품/수량/가격 확인과 최종 결제는 항상 사장님이
     직접 합니다.

사용법:
    cd browser_agent
    pip install -r requirements.txt
    playwright install chromium

    python coupang_order_assistant.py --need 양파=60 --need 대파=40
    python coupang_order_assistant.py --need 양파=60 --debug   # 단계별 스크린샷 저장

알아둘 점:
  - 개발 환경(샌드박스)에서 coupang.com 접속 자체가 막혀 있어, 아래 화면
    선택자(selector)는 실제 화면으로 라이브 검증하지 못했습니다. 실제 화면
    구조가 다르면 특정 단계에서 멈출 수 있는데, --debug 옵션을 쓰면
    debug_screenshots/ 폴더에 각 단계 스크린샷이 남으니 그걸 보고 어디가
    다른지 알려주면 바로 고칠 수 있습니다.
  - 쿠팡을 포함한 대부분의 쇼핑몰은 이용약관상 자동화 도구 사용을 금지하고
    있을 수 있습니다. 이 스크립트는 "사장님 본인 계정에서, 사람이 최종
    결제를 직접 승인하는" 개인 편의 도구로 쓰는 것을 전제로 합니다.
    대량/상시 자동화, 타인 계정, 재판매 목적 등으로는 쓰지 마세요.
  - 쿠팡은 kg 단위 낱개 판매가 아니라 정해진 중량의 팩(1kg, 3kg 등) 단위로
    팝니다. 그래서 정확한 kg 환산·수량 자동 조절은 하지 않고, 검색된 상품을
    장바구니에 담아두기만 합니다 — 실제 상품/수량/가격은 장바구니 화면에서
    사장님이 직접 최종 확인해야 합니다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PROFILE_DIR = Path(__file__).resolve().parent / ".browser_profile"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "debug_screenshots"
COUPANG_HOME = "https://www.coupang.com"


def _debug_shot(page, name: str, debug: bool) -> None:
    if not debug:
        return
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  [디버그] 스크린샷 저장: {path}")


def ensure_logged_in(page, debug: bool) -> None:
    """로그인 여부를 화면 텍스트로 자동 판단하지 않는다. 실제 쿠팡 화면 구조를
    라이브로 검증하지 못한 상태라, 자동 판단이 틀리면 로그인 안 된 채로 조용히
    진행하다가 애매하게 실패할 수 있다. 그래서 항상 사람이 눈으로 직접 보고
    확인하게 한다 (한 번 로그인해두면 세션이 저장되어 매번 로그인할 필요는 없다)."""
    page.goto(COUPANG_HOME)
    _debug_shot(page, "00_home", debug)
    print("\n브라우저 창을 확인해주세요.")
    print("쿠팡에 로그인되어 있지 않다면 지금 직접 로그인해주세요 (다음부터는 자동으로 유지됩니다).")
    input("로그인 상태 확인 완료 후 이 터미널에서 Enter를 눌러주세요 >> ")


def search_and_add_to_cart(page, item_name: str, quantity_kg: float, debug: bool) -> bool:
    """품목을 검색해서 첫 번째 상품 페이지를 열고 장바구니에 담는다.

    실제 필요한 kg과 상품 팩 단위가 다르므로, 수량을 자동으로 맞추지 않고
    "일단 장바구니에 담아두는" 것까지만 자동화한다. 정확한 수량/상품 선택은
    장바구니 화면에서 사람이 직접 확인/수정한다.
    """
    print(f"'{item_name}' 검색 중... (필요 수량: {quantity_kg:g}kg — 실제 팩 수량은 담은 뒤 직접 확인해주세요)")
    page.goto(f"{COUPANG_HOME}/np/search?component=&q={item_name}")
    _debug_shot(page, f"search_{item_name}", debug)

    try:
        first_result = page.locator("a[href*='/vp/products/']").first
        first_result.wait_for(timeout=8000)
    except PlaywrightTimeoutError:
        print(f"  [실패] '{item_name}' 검색 결과를 찾지 못했습니다. 화면 구조가 바뀐 것 같습니다.")
        return False

    first_result.click()
    _debug_shot(page, f"product_{item_name}", debug)

    # 상품명을 화면에 출력해서, 사람이 터미널만 보고도 엉뚱한 상품이 담기는 건 아닌지 눈치챌 수 있게 한다.
    try:
        title = page.locator("h1, h2").first.inner_text(timeout=3000)
        print(f"  상품 페이지 확인: {title.strip()[:60]}")
    except PlaywrightTimeoutError:
        pass

    try:
        add_to_cart_button = page.get_by_role("button", name="장바구니 담기")
        add_to_cart_button.wait_for(timeout=8000)
        add_to_cart_button.click()
    except PlaywrightTimeoutError:
        print(f"  [실패] '{item_name}' 장바구니 담기 버튼을 찾지 못했습니다.")
        return False

    _debug_shot(page, f"added_{item_name}", debug)
    print(f"  '{item_name}' 장바구니에 담았습니다.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="쿠팡 발주 반자동 도우미 (장바구니까지 자동, 결제는 직접)")
    parser.add_argument(
        "--need", action="append", required=True, metavar="품목=수량",
        help="예: --need 양파=60 (단위: kg, 참고용). 여러 번 지정 가능",
    )
    parser.add_argument("--debug", action="store_true", help="각 단계 스크린샷을 debug_screenshots/에 저장")
    args = parser.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.cli_utils import parse_kv_pairs  # noqa: E402  (메인 프로젝트 파싱 유틸 재사용)

    needs = parse_kv_pairs(args.need, "양파=60")

    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False, viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        ensure_logged_in(page, args.debug)

        failed = []
        for item_name, quantity in needs.items():
            ok = search_and_add_to_cart(page, item_name, quantity, args.debug)
            if not ok:
                failed.append(item_name)

        page.goto(f"{COUPANG_HOME}/np/cart")
        _debug_shot(page, "cart", args.debug)

        print("\n" + "=" * 60)
        print("장바구니 화면을 열었습니다.")
        if failed:
            print(f"자동으로 담지 못한 품목: {', '.join(failed)} — 직접 검색해서 담아주세요.")
        print("상품/수량/가격을 반드시 직접 확인하고, 결제는 사장님이 브라우저에서")
        print("직접 눌러주세요. 이 스크립트는 결제 버튼을 자동으로 누르지 않습니다.")
        print("=" * 60)

        input("\n확인이 끝나면 Enter를 눌러 종료하세요 (또는 브라우저를 직접 닫아도 됩니다) >> ")
        context.close()


if __name__ == "__main__":
    main()
