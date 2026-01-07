# 📈 Deep-Ensemble Stock Scanner v3.0
## 프로젝트 헌법 (Constitution)

> All Zero-shot Foundation Models Edition

---

## 제1장 총칙

### 제1조 (목적)
본 프로젝트는 기존 다수의 프로젝트에서 산출된 유망 종목(CSV)을 취합하여, 3가지 Zero-shot Foundation Model과 3가지 시간(단/중/장기) 관점을 결합한 앙상블 시스템을 통해 최종 BEST 15 종목을 선정함을 목적으로 한다.

### 제2조 (핵심 원칙)
1. **No Training**: 사전학습 및 파인튜닝 없이 Zero-shot 추론만 수행한다
2. **Model Diversity**: 서로 다른 아키텍처의 Foundation Model 3종을 활용한다
3. **Multi-Horizon**: 단기(5일)/중기(20일)/장기(60일) 예측을 병행한다
4. **Risk-Adjusted**: 수익률과 모델 일치도를 모두 반영하여 스코어링한다

### 제3조 (하드웨어 제약)
1. 기준 환경: NVIDIA RTX 3050 Ti Laptop (4GB VRAM)
2. 총 추론 VRAM: 1GB 미만으로 설계
3. OOM(Out Of Memory) 없이 안정적 구동 보장

---

## 제2장 모델 구성

### 제4조 (선정 모델)

| 순서 | 모델명 | 개발사 | 파라미터 | VRAM | 역할 |
|:----:|--------|--------|:--------:|:----:|------|
| 1 | Chronos-Bolt-Small | Amazon | 48M | ~0.5GB | Trend 예측 |
| 2 | TTM (Tiny Time Mixer) | IBM | <1M | ~0.1GB | Multi-scale |
| 3 | Moirai-Small | Salesforce | 14M | ~0.3GB | 확률 예측 |

### 제5조 (모델별 특성)

#### 5.1 Chronos-Bolt-Small
- 아키텍처: T5 기반 Encoder-Decoder
- 예측 방식: 패치 분할 → 직접 멀티스텝 예측
- 특징: 원본 Chronos 대비 250배 속도, 20배 메모리 효율
- 출력: 확률 분포 (분위수)
- HuggingFace: `amazon/chronos-bolt-small`

#### 5.2 TTM (Tiny Time Mixer)
- 아키텍처: Pure MLP (Transformer 아님)
- 예측 방식: Adaptive Patching
- 특징: NeurIPS 2024, CPU 실행 가능, 벤치마크 최상위
- 출력: Point Forecast
- HuggingFace: `ibm-granite/granite-timeseries-ttm-r2`
- 주의: 입력 데이터 Standard Scaling 필수

#### 5.3 Moirai-Small
- 아키텍처: Transformer Encoder
- 예측 방식: Any-variate Attention + Masked Prediction
- 특징: ICML 2024 Oral, 다변량 지원
- 출력: 샘플 분포 (불확실성 추정)
- HuggingFace: `Salesforce/moirai-1.0-R-small`

### 제6조 (앙상블 가중치)
- Chronos-Bolt: 40%
- TTM: 35%
- Moirai: 25%

---

## 제3장 데이터 파이프라인

### 제7조 (데이터 수집 소스)

| 우선순위 | 소스 | 용도 |
|:--------:|------|------|
| 1 | pykrx | 한국 종목 OHLCV (메인) |
| 2 | FinanceDataReader | 한국 종목 (백업) |
| 3 | yfinance | 매크로 지표 |

### 제8조 (수집 데이터)
1. 필수: OHLCV (시가, 고가, 저가, 종가, 거래량)
2. 수집 기간: 최근 150 거래일 (버퍼 포함)
3. 선택: KOSPI, USD/KRW, VIX

### 제9조 (전처리 규칙)
1. 종목 OHLCV 결측: 해당일 제거
2. 매크로 지표 결측: Forward Fill
3. TTM용 정규화: Standard Scaling (채널별 독립)
4. Chronos/Moirai: 내부 자동 정규화 사용

### 제10조 (데이터 검증)
1. 최소 120 거래일 확보 필수
2. 최근 5일 내 거래 기록 존재 확인
3. 일일 변동률 ±30% 초과 시 플래그 기록

---

## 제4장 추론 아키텍처

### 제11조 (타임프레임 정의)

| 구분 | 입력 기간 | 예측 기간 | 가중치 | 목적 |
|:----:|:---------:|:---------:|:------:|------|
| 단기 | 20일 | 5일 | 50% | 모멘텀, 급등락 |
| 중기 | 60일 | 20일 | 30% | 월간 추세 |
| 장기 | 120일 | 60일 | 20% | 구조적 성장 |

### 제12조 (추론 실행 순서)

#### Phase 1: Chronos-Bolt
1. 모델 로드 (bfloat16)
2. 전체 종목 × 3개 호라이즌 추론
3. 결과 저장
4. 모델 언로드 & 메모리 정리

#### Phase 2: TTM
1. Short용 모델 로드 → 추론 → 언로드
2. Mid용 모델 로드 → 추론 → 언로드
3. Long용 모델 로드 → 추론 → 언로드
4. 메모리 정리

#### Phase 3: Moirai
1. 모델 로드
2. 전체 종목 × 3개 호라이즌 추론
3. 결과 저장
4. 최종 메모리 정리

### 제13조 (메모리 관리 의무)
모델 언로드 시 반드시 다음 절차 준수:
1. 모델 객체 삭제
2. Python garbage collection
3. CUDA 캐시 비우기
4. CUDA 동기화

---

## 제5장 스코어링 시스템

### 제14조 (수익률 산출)
```
raw_return = (예측가 - 현재가) / 현재가
```

### 제15조 (확률 예측 처리)
- Chronos-Bolt: 중앙값(50% 분위수) 사용
- Moirai: 샘플 분포의 중앙값 사용
- TTM: Point Forecast 직접 사용

### 제16조 (수익률 상한)
| 호라이즌 | 상한 |
|:--------:|:----:|
| 단기(5일) | ±30% |
| 중기(20일) | ±50% |
| 장기(60일) | ±100% |

### 제17조 (시간 정규화)
일간 수익률로 변환하여 비교 가능하게 함:
- 단기: raw_return ÷ 5
- 중기: raw_return ÷ 20
- 장기: raw_return ÷ 60

### 제18조 (모델 일치도)
1. 방향 일치도 (60%): 3개 모델 예측 방향 일치 여부
2. 크기 일치도 (40%): 변동계수(CV) 기반 산출
3. 범위: 0 ~ 1

### 제19조 (최종 스코어 공식)
```
가중 일간수익률 = (0.50 × 단기) + (0.30 × 중기) + (0.20 × 장기)

평균 일치도 = mean(단기일치도, 중기일치도, 장기일치도)

빈도 보너스 = log(1 + 중복추천횟수) × 0.02

최종점수 = 가중일간수익률 × (0.70 + 0.30 × 평균일치도) + 빈도보너스
```

---

## 제6장 필터링

### 제20조 (사전 필터)
- 종목코드 유효성 검사
- ETF, ETN, 스팩, 리츠 제외 (선택)
- 관리종목, 투자경고 제외

### 제21조 (데이터 필터)
- 최소 120 거래일 데이터 존재
- 최근 5일 내 거래 기록 존재
- 이상치 플래그 확인

### 제22조 (결과 필터)
- 최소 평균 거래량: 5만주
- 최소 평균 거래대금: 5억원
- 섹터 다변화: 동일 섹터 최대 3종목
- 최종 TOP 15 선정

---

## 제7장 출력

### 제23조 (메인 결과 CSV)
파일명: `ensemble_result_YYYYMMDD_HHMMSS.csv`

| 컬럼 | 타입 | 설명 |
|------|:----:|------|
| rank | int | 순위 |
| code | str | 종목코드 |
| name | str | 종목명 |
| current_price | int | 현재가 |
| short_ret | float | 단기 수익률(%) |
| mid_ret | float | 중기 수익률(%) |
| long_ret | float | 장기 수익률(%) |
| daily_return | float | 일간 정규화 수익률(%) |
| agreement | float | 모델 일치도 |
| total_score | float | 최종 점수 |
| tag | str | 투자유형 태그 |
| freq_count | int | 중복추천 횟수 |

### 제24조 (투자유형 태깅)

| 태그 | 조건 |
|------|------|
| 🚀 단기급등형 | 단기 > 5% AND 단기 > 장기 |
| 📈 장기성장형 | 장기 > 15% AND 장기 > 단기×1.5 |
| ✅ 고확신형 | 일치도 > 0.85 |
| ⚖️ 균형형 | 단기 > 0 AND 장기 > 0 |
| ⚠️ 혼조형 | 그 외 |

---

## 제8장 에러 처리

### 제25조 (처리 원칙)

| 상황 | 처리 |
|------|------|
| 개별 종목 수집 실패 | 스킵 & 로그, 계속 |
| 개별 모델 추론 실패 | 해당 모델 제외, 나머지로 앙상블 |
| OOM 발생 | 메모리 정리 후 재시도 |
| 모든 모델 실패 | 해당 종목 제외, 계속 |
| 치명적 오류 | 프로그램 종료 & 리포트 |

### 제26조 (로그 레벨)
- DEBUG: 상세 디버깅
- INFO: 정상 진행
- WARNING: 스킵/재시도
- ERROR: 실패했지만 계속 가능
- CRITICAL: 프로그램 중단

---

## 제9장 프로젝트 구조

### 제27조 (디렉토리 구조)
```
deep-ensemble-scanner/
├── config/
│   └── config.yaml
├── src/
│   ├── data/
│   │   ├── collector.py
│   │   ├── preprocessor.py
│   │   └── candidate_pool.py
│   ├── models/
│   │   ├── base_wrapper.py
│   │   ├── chronos_wrapper.py
│   │   ├── ttm_wrapper.py
│   │   └── moirai_wrapper.py
│   ├── core/
│   │   ├── inference.py
│   │   ├── scorer.py
│   │   └── filters.py
│   └── utils/
│       ├── memory.py
│       ├── logger.py
│       └── reporter.py
├── scripts/
│   └── run_scanner.py
├── outputs/
├── logs/
├── cache/
├── requirements.txt
└── README.md
```

---

## 제10장 의존성

### 제28조 (필수 패키지)

**Core**
- torch >= 2.0.0
- numpy >= 1.24.0
- pandas >= 2.0.0
- pyyaml >= 6.0

**Data**
- pykrx >= 1.0.45
- finance-datareader >= 0.9.50

**Models**
- chronos-forecasting (GitHub)
- tsfm_public (TTM)
- uni2ts (Moirai)
- gluonts >= 0.14.0

**Utilities**
- tqdm >= 4.65.0
- rich >= 13.0.0
- scikit-learn >= 1.3.0

---

## 제11장 부칙

### 제29조 (면책조항)
1. 본 시스템은 투자 참고용이며, 실제 투자 결정은 사용자 책임이다
2. 과거 성과가 미래 수익을 보장하지 않는다
3. Foundation Model의 Zero-shot 예측은 금융 데이터에 특화되지 않았다
4. 반드시 분산 투자하고, 감당 가능한 금액만 투자해야 한다

### 제30조 (버전 이력)

| 버전 | 날짜 | 내용 |
|:----:|:----:|------|
| v3.0 | 2025-01-06 | All Zero-shot 조합 전면 개편 |
| v2.x | 2025-01-06 | 사전학습 방식 (폐기) |
| v1.0 | 2024-12 | 초기 버전 (미존재 모델) |

### 제31조 (시행일)
본 헌법은 공포한 날로부터 시행한다.

---

**문서 끝**
