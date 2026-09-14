# fresh-price-auto

F&B(외식업) 사장님들이 매일 필요한 식재료(양파, 대파 등)를 최저가로 자동 발주할 수
있도록 돕는 MVP. 4단계로 나눠서 개발한다.

1. **[완료] KAMIS 시세 수집** — 매일 품목별 도매/소매 평균가 가져오기
2. **[완료] 가상 공급처 데이터** — SQLite, KAMIS 시세 기준 ±10~15% 랜덤 변동
3. 최저가 비교 로직 (배송비/최소주문금액 반영, 묶음/분할 구매 비교)
4. 발주/결제 흐름 목업 (주문서 생성 → 승인 → 결제 완료 시뮬레이션, 이력 저장)

## 1단계: KAMIS 오늘의 시세 가져오기

### 준비

1. https://www.kamis.or.kr 에서 Open API 인증키(cert_key)와 아이디(cert_id)를 무료로 신청한다.
2. `.env.example`을 `.env`로 복사하고 발급받은 값을 채운다.

   ```bash
   cp .env.example .env
   ```

3. 의존성 설치

   ```bash
   pip install -r requirements.txt
   ```

### 실행

```bash
python fetch_today_prices.py
python fetch_today_prices.py --regday 2024-01-15   # 특정 날짜 조회
python fetch_today_prices.py --raw                 # 원본 JSON 응답도 함께 출력
```

출력 예시:

```
KAMIS 시세 조회 결과 (2026-09-14)

=== 소매 평균가 ===
  양파(1kg)      1,847원 / 1kg
  대파(1kg)      2,760원 / 1kg

=== 도매 평균가 ===
  양파(1kg)      ...원 / 1kg
  대파(1kg)      ...원 / 1kg
```

(위 소매 값은 실제 KAMIS API 호출로 확인된 값)

### 구현 메모 / 알아둘 점

- 사용 API 액션: `dailyPriceByCategoryList` (일별 부류별 도소매가격정보). 특정 품목
  하나만 콕 집어 조회하는 파라미터가 없어서, 부류코드(채소류=200)로 그 부류의 전체
  품목을 받아온 뒤 이름에 "양파"/"대파"가 포함된 행만 걸러낸다.
  (`config/items.py`에서 대상 품목/부류코드를 관리한다.)
- 실제 응답 확인 결과 알게 된 것 (검증 완료, 2026-09-14 실제 호출 기준):
  - 가격 필드는 `price`가 아니라 `dpr1`(당일가)이다.
  - "대파"/"쪽파"처럼 세부 품종명은 `item_name`이 아니라 `kind_name`에 들어있다
    (파 계열의 `item_name`은 그냥 "파"). 그래서 이름 매칭 시 `item_name`+`kind_name`을
    합쳐서 검색한다.
  - 같은 품목이 등급(상품/중품)별로 여러 행 나올 수 있어 상품(`rank_code="04"`) 행을
    우선 채택한다.
- 조회 지역은 기본값 서울(`1101`)이며 `.env`의 `KAMIS_COUNTRY_CODE`로 바꿀 수 있다.
- 이 개발 환경(샌드박스)은 아웃바운드 네트워크가 방화벽으로 제한되어 있어
  `kamis.or.kr`에 직접 접속은 못 하지만, 실제 발급받은 키로 호출한 응답을 전달받아
  그 구조 그대로 파싱 로직을 검증했다 (`tests/test_kamis_client.py`).
- 인증 정보가 없으면 명확한 에러 메시지를 내고 종료한다 (`KamisCredentials.from_env`).

## 2단계: 가상 공급처 가격 시뮬레이션

가상 공급처 5곳(`config/suppliers.py`)의 품목별 가격을, KAMIS 오늘 시세(도매
우선, 없으면 소매)를 기준값으로 삼아 ±10~15% 범위에서 랜덤 변동시켜 SQLite
(`data/fresh_price_auto.db`)에 저장한다.

### 실행

```bash
python simulate_supplier_prices.py
python simulate_supplier_prices.py --regday 2024-01-15

# KAMIS 호출 없이 기준값을 직접 지정하고 싶을 때 (오프라인 테스트/데모용)
python simulate_supplier_prices.py --base-price 양파=1847 --base-price 대파=2760
```

출력 예시:

```
기준값 (2026-09-14): 양파 1,847원, 대파 2,760원

공급처               배송비       최소주문금액           양파          대파
농협직거래마트        3,000원      30,000원        1,599       3,043
청과유통센터         5,000원      50,000원        1,651       3,122
산지직송마켓             0원     100,000원        2,062       2,399
새벽배송푸드         4,000원      20,000원        1,633       3,040
도매유통상회         2,000원      80,000원        2,066       2,423

10건 저장 완료 -> data/fresh_price_auto.db
```

### 구현 메모 / 알아둘 점

- 가격 변동은 `(날짜, 공급처명, 품목명)`으로 시드를 고정한 결정론적 랜덤이다.
  그래서 **같은 날 여러 번 실행해도 가격이 흔들리지 않고**, 날짜가 바뀌면
  자연스럽게 새 값이 나온다 (`src/supplier_simulator.py`). 파이썬 내장
  `hash()`는 프로세스마다 시드가 랜덤화되어 재현이 안 되기 때문에 `hashlib`로
  직접 시드를 계산했다.
- 배송비/최소주문금액은 공급처 단위로 고정값이고(`config/suppliers.py`),
  품목 가격만 매일 변동한다.
- DB 스키마는 `src/db.py`에 있고, `suppliers`/`supplier_prices` 두 테이블로
  구성된다. 같은 (공급처, 품목, 날짜) 조합으로 다시 실행하면 값을 덮어쓴다
  (upsert).
- DB 파일(`*.db`)은 `.gitignore`에 포함되어 저장소에는 커밋되지 않는다.

### 테스트

```bash
pip install pytest
python -m pytest tests/ -v
```
