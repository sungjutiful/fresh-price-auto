# fresh-price-auto

F&B(외식업) 사장님들이 매일 필요한 식재료(양파, 대파 등)를 최저가로 자동 발주할 수
있도록 돕는 MVP. 4단계로 나눠서 개발한다.

1. **[진행 중] KAMIS 시세 수집** — 매일 품목별 도매/소매 평균가 가져오기
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
KAMIS 시세 조회 결과 (2024-01-15)

=== 소매 평균가 ===
  양파     1,850원 / kg
  대파     2,300원 / kg

=== 도매 평균가 ===
  양파     1,200원 / kg
  대파     1,800원 / kg
```

### 구현 메모 / 알아둘 점

- 사용 API 액션: `dailyPriceByCategoryList` (일별 부류별 도소매가격정보). 특정 품목
  하나만 콕 집어 조회하는 파라미터가 없어서, 부류코드(채소류=200)로 그 부류의 전체
  품목을 받아온 뒤 품목명에 "양파"/"대파"가 포함된 행만 걸러낸다.
  (`config/items.py`에서 대상 품목/부류코드를 관리한다.)
- 조회 지역은 기본값 서울(`1101`)이며 `.env`의 `KAMIS_COUNTRY_CODE`로 바꿀 수 있다.
- **이 개발 환경(샌드박스)은 아웃바운드 네트워크가 방화벽으로 제한되어 있어
  `kamis.or.kr`에 접속할 수 없다.** 그래서 실제 API 키로 라이브 호출을 검증하지
  못했고, 대신 `tests/test_kamis_client.py`에서 KAMIS 응답 형태를 가정한 목(mock)
  데이터로 파싱 로직만 검증했다. 실제 키로 처음 실행했을 때 응답 JSON의 필드명이
  가정과 다르면 (예: 품목명/가격 키가 `item_name`/`price`가 아닌 경우)
  `src/kamis_client.py`의 `_NAME_KEYS` / `_PRICE_KEYS` 후보 목록만 실제 응답에
  맞게 고치면 된다. `--raw` 옵션으로 원본 응답을 확인할 수 있다.
- 인증 정보가 없으면 명확한 에러 메시지를 내고 종료한다 (`KamisCredentials.from_env`).

### 테스트

```bash
pip install pytest
python -m pytest tests/ -v
```
