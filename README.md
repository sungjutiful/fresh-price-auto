# fresh-price-auto

F&B(외식업) 사장님들이 매일 필요한 식재료(양파, 대파 등)를 최저가로 자동 발주할 수
있도록 돕는 MVP. 4단계로 나눠서 개발한다.

1. **[완료] KAMIS 시세 수집** — 매일 품목별 도매/소매 평균가 가져오기
2. 가상 공급처 데이터 (JSON/SQLite, KAMIS 시세 기준 ±10~15% 랜덤 변동)
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

### 테스트

```bash
pip install pytest
python -m pytest tests/ -v
```
