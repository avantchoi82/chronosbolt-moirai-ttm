# 🛠️ Deep-Ensemble Stock Scanner v3.0
## 단계별 구현 가이드 (Implementation Guide)

---

## 개요

본 문서는 CONSTITUTION.md에 정의된 시스템을 단계별로 구현하기 위한 프롬프트와 리팩토링 가이드를 제공한다.

**구현 순서**
1. Phase 1: 프로젝트 기반 구축
2. Phase 2: 데이터 파이프라인
3. Phase 3: 모델 래퍼
4. Phase 4: 추론 엔진
5. Phase 5: 스코어링 & 필터링
6. Phase 6: 출력 & 리포팅
7. Phase 7: 통합 & 테스트

---

# Part 1: 단계별 구현 프롬프트

---

## Phase 1: 프로젝트 기반 구축

### Step 1.1: 디렉토리 구조 생성

**프롬프트:**
```
CONSTITUTION.md의 제27조에 따라 deep-ensemble-scanner 프로젝트 디렉토리 구조를 생성해줘.
- 모든 __init__.py 파일 포함
- .gitignore 파일 생성 (Python, cache, outputs 제외)
- 빈 README.md 생성
```

### Step 1.2: Config 시스템

**프롬프트:**
```
config/config.yaml 파일을 생성해줘.
CONSTITUTION.md의 제4조~제6조(모델), 제11조(호라이즌), 제16조(수익률 상한), 
제22조(필터) 설정을 모두 포함해야 해.

그리고 src/utils/config_loader.py를 만들어서:
- YAML 로드
- 설정값 검증
- 기본값 처리
기능을 구현해줘.
```

### Step 1.3: 로깅 시스템

**프롬프트:**
```
src/utils/logger.py를 구현해줘.
CONSTITUTION.md 제26조의 로그 레벨(DEBUG~CRITICAL)을 지원하고:
- 콘솔 출력 (Rich 포맷)
- 파일 출력 (logs/ 디렉토리)
- 타임스탬프 포함
```

### Step 1.4: 메모리 관리 유틸

**프롬프트:**
```
src/utils/memory.py를 구현해줘.
CONSTITUTION.md 제13조의 메모리 관리 의무사항을 함수로 만들어:
- unload_model(): 모델 삭제 + gc + CUDA 캐시 비우기 + 동기화
- get_gpu_memory(): 현재 VRAM 사용량 조회
- check_available_memory(): 가용 메모리 확인
```

---

## Phase 2: 데이터 파이프라인

### Step 2.1: Candidate Pool

**프롬프트:**
```
src/data/candidate_pool.py를 구현해줘.
CONSTITUTION.md 제20조(사전 필터)를 참고해서:
- 여러 CSV 경로에서 종목코드 추출
- 종목코드 컬럼 자동 탐지 (code, ticker, 종목코드 등)
- 중복 종목 빈도수 카운팅
- ETF/ETN/스팩/리츠 필터링 (선택적)
- 결과: {종목코드: 빈도수} 딕셔너리 반환
```

### Step 2.2: 데이터 수집기

**프롬프트:**
```
src/data/collector.py를 구현해줘.
CONSTITUTION.md 제7조~제8조를 참고해서:
- pykrx를 메인으로 사용
- 실패 시 FinanceDataReader로 폴백
- OHLCV 수집 (150 거래일)
- ThreadPoolExecutor로 병렬 수집
- 3회 재시도 후 스킵
- 캐싱 지원 (cache/ 디렉토리, 24시간 만료)
```

### Step 2.3: 전처리기

**프롬프트:**
```
src/data/preprocessor.py를 구현해줘.
CONSTITUTION.md 제9조~제10조를 참고해서:
- 결측치 처리 (종목: 제거, 매크로: Forward Fill)
- 데이터 검증 (120일 이상, 최근 5일 거래 존재)
- 이상치 플래그 (±30% 변동)
- TTM용 Standard Scaling 함수
- 역정규화 함수
```

---

## Phase 3: 모델 래퍼

### Step 3.1: 베이스 래퍼

**프롬프트:**
```
src/models/base_wrapper.py를 구현해줘.
모든 모델 래퍼의 공통 인터페이스 정의:
- load(): 모델 로드
- predict(data, horizon): 예측 수행
- unload(): 모델 언로드 (제13조 메모리 관리 호출)
- get_name(): 모델 이름 반환

ABC(Abstract Base Class) 사용해서 구현 강제해줘.
```

### Step 3.2: Chronos-Bolt 래퍼

**프롬프트:**
```
src/models/chronos_wrapper.py를 구현해줘.
CONSTITUTION.md 제5조 5.1을 참고:
- amazon/chronos-bolt-small 사용
- bfloat16 정밀도
- 확률 예측에서 중앙값 추출 (제15조)
- base_wrapper 상속
- 에러 발생 시 None 반환 (제25조)
```

### Step 3.3: TTM 래퍼

**프롬프트:**
```
src/models/ttm_wrapper.py를 구현해줘.
CONSTITUTION.md 제5조 5.2를 참고:
- ibm-granite/granite-timeseries-ttm-r2 사용
- get_model()로 context/prediction 길이에 맞는 모델 자동 선택
- 입력 데이터 Standard Scaling 적용 (제9조)
- Point Forecast 반환
- 호라이즌별로 별도 모델 로드/언로드 (제12조 Phase 2)
```

### Step 3.4: Moirai 래퍼

**프롬프트:**
```
src/models/moirai_wrapper.py를 구현해줘.
CONSTITUTION.md 제5조 5.3을 참고:
- Salesforce/moirai-1.0-R-small 사용
- GluonTS 데이터 형식 변환
- patch_size="auto"
- num_samples=100
- 샘플 분포에서 중앙값 추출 (제15조)
```

---

## Phase 4: 추론 엔진

### Step 4.1: 추론 오케스트레이터

**프롬프트:**
```
src/core/inference.py를 구현해줘.
CONSTITUTION.md 제12조의 추론 실행 순서를 따라:
- Phase 1: Chronos-Bolt (전체 호라이즌 한번에)
- Phase 2: TTM (호라이즌별 로드/언로드)
- Phase 3: Moirai (전체 호라이즌 한번에)

각 Phase 후 메모리 정리 필수.
결과는 {종목코드: {모델명: {호라이즌: 예측값}}} 형태로 저장.
tqdm으로 진행률 표시.
```

---

## Phase 5: 스코어링 & 필터링

### Step 5.1: 스코어러

**프롬프트:**
```
src/core/scorer.py를 구현해줘.
CONSTITUTION.md 제14조~제19조를 구현:
- calc_raw_return(): 원시 수익률 계산
- cap_return(): 수익률 상한 적용 (제16조)
- normalize_return(): 일간 정규화 (제17조)
- calc_agreement(): 모델 일치도 계산 (제18조)
- calc_final_score(): 최종 스코어 계산 (제19조)
- ensemble_returns(): 모델별 가중 평균 (제6조 가중치)
```

### Step 5.2: 필터

**프롬프트:**
```
src/core/filters.py를 구현해줘.
CONSTITUTION.md 제20조~제22조를 구현:
- filter_by_volume(): 거래량 필터
- filter_by_value(): 거래대금 필터
- filter_by_sector(): 섹터 다변화 필터
- select_top_n(): 상위 N개 선정
- assign_tag(): 투자유형 태깅 (제24조)
```

---

## Phase 6: 출력 & 리포팅

### Step 6.1: 리포터

**프롬프트:**
```
src/utils/reporter.py를 구현해줘.
CONSTITUTION.md 제23조~제24조를 참고:
- save_result_csv(): 결과 CSV 저장
- save_detail_log(): 상세 로그 CSV 저장
- print_terminal_report(): Rich 테이블로 터미널 출력
  - TOP 15 테이블
  - 실행 통계 (입력 종목 수, 필터 후, 소요시간)
```

---

## Phase 7: 통합 & 테스트

### Step 7.1: 메인 스크립트

**프롬프트:**
```
scripts/run_scanner.py를 구현해줘.
전체 파이프라인 통합:
1. Config 로드
2. Candidate Pool 생성
3. 데이터 수집 & 전처리
4. 3개 모델 순차 추론 (Phase 1~3)
5. 스코어링
6. 필터링
7. 결과 출력

CLI 옵션:
- --config: 설정 파일 경로 (필수)
- --top: 상위 N개 (기본 15)
- --only-chronos: Chronos만 사용
- --dry-run: 데이터 수집만 테스트
- --verbose: 상세 로그
```

### Step 7.2: 테스트

**프롬프트:**
```
다음 테스트를 수행해줘:
1. 종목 5개로 dry-run 테스트
2. Chronos만 사용해서 빠른 테스트
3. 전체 파이프라인 테스트 (종목 10개)
4. 메모리 사용량 모니터링

각 테스트 후 문제점 리포트해줘.
```

---

# Part 2: 리팩토링 가이드

---

## 리팩토링 원칙

### 원칙 1: 단일 책임
- 각 모듈은 하나의 책임만 가진다
- 함수는 20줄 이내 권장
- 클래스는 200줄 이내 권장

### 원칙 2: 의존성 최소화
- 순환 의존성 금지
- 인터페이스(ABC)를 통한 느슨한 결합

### 원칙 3: 테스트 용이성
- 외부 의존성은 주입 가능하게
- 하드코딩 금지 (Config 사용)

---

## 모듈별 리팩토링 체크리스트

### Data 모듈

**candidate_pool.py**
```
□ CSV 파싱 로직이 10줄 이상이면 별도 함수로 분리
□ 종목코드 검증 로직을 validator.py로 분리 고려
□ 캐싱이 필요하면 decorator 패턴 사용
```

**collector.py**
```
□ pykrx/fdr 로직이 중복되면 추상화
□ 재시도 로직을 decorator로 분리
□ 캐시 로직을 별도 cache.py로 분리
```

**preprocessor.py**
```
□ 스케일러 종류 추가 시 Strategy 패턴 고려
□ 검증 로직이 복잡해지면 DataValidator 클래스 분리
```

### Models 모듈

**래퍼 공통**
```
□ 모델 로드 시간이 길면 lazy loading 적용
□ 예측 결과 캐싱 고려
□ 배치 처리 최적화
```

**chronos_wrapper.py**
```
□ 분위수 추출 로직이 복잡해지면 별도 함수
□ 다른 Chronos 변형 지원 시 Factory 패턴
```

**ttm_wrapper.py**
```
□ 모델 선택 로직이 복잡해지면 ModelSelector 클래스 분리
□ 스케일링 로직을 preprocessor와 통합 고려
```

**moirai_wrapper.py**
```
□ GluonTS 변환 로직을 data/converters.py로 분리 고려
□ 샘플 수 동적 조절 로직 추가 시 별도 함수
```

### Core 모듈

**inference.py**
```
□ Phase별 로직이 유사하면 템플릿 메소드 패턴
□ 진행률 표시 로직 분리
□ 결과 저장 형식이 변경되면 ResultStore 클래스
```

**scorer.py**
```
□ 스코어링 방식 추가 시 Strategy 패턴
□ 수식이 복잡해지면 Formula 클래스 분리
□ 가중치 동적 조절 시 WeightManager 클래스
```

**filters.py**
```
□ 필터 종류 추가 시 Chain of Responsibility 패턴
□ 필터 조건이 Config에서 동적 로드되게
□ 복합 필터 지원 시 Composite 패턴
```

### Utils 모듈

**reporter.py**
```
□ 출력 형식 추가 시 (JSON, HTML) Factory 패턴
□ 테이블 포맷팅 로직 분리
□ 차트 생성 추가 시 visualization.py 분리
```

---

## 성능 최적화 리팩토링

### 메모리 최적화
```
□ 대용량 DataFrame은 사용 후 즉시 del
□ 불필요한 복사 방지 (inplace=True 활용)
□ Generator 사용 고려 (대량 종목 처리 시)
```

### 속도 최적화
```
□ 데이터 수집 병렬화 수준 조정 (8~16 workers)
□ 모델 추론 배치 크기 최적화
□ 캐시 적중률 모니터링 및 개선
```

### GPU 최적화
```
□ torch.no_grad() 컨텍스트 사용 확인
□ 불필요한 GPU-CPU 전송 최소화
□ Mixed Precision (float16/bfloat16) 적용 확인
```

---

## 확장성 리팩토링

### 새 모델 추가 시
```
1. base_wrapper.py 상속
2. load(), predict(), unload() 구현
3. config.yaml에 모델 설정 추가
4. inference.py의 Phase에 추가
5. scorer.py의 가중치 조정
```

### 새 호라이즌 추가 시
```
1. config.yaml의 horizons에 추가
2. 제11조 타임프레임 정의 업데이트
3. scorer.py의 가중치 조정
4. TTM은 해당 길이 모델 존재 여부 확인
```

### 새 필터 추가 시
```
1. filters.py에 filter_by_xxx() 함수 추가
2. config.yaml에 필터 설정 추가
3. run_scanner.py의 필터 체인에 추가
```

---

## 코드 품질 체크리스트

### 구현 완료 후 확인
```
□ 모든 함수에 docstring 작성
□ 타입 힌트 추가 (Python 3.10+ 스타일)
□ 예외 처리 누락 없음
□ 로깅 적절히 배치
□ 매직 넘버 없음 (Config 또는 상수 사용)
□ 하드코딩된 경로 없음
```

### 리팩토링 완료 후 확인
```
□ 순환 import 없음
□ 사용하지 않는 import 제거
□ 중복 코드 없음
□ 함수/클래스 크기 적절
□ 네이밍 일관성
□ 주석이 코드와 일치
```

---

## 트러블슈팅 가이드

### OOM 발생 시
```
1. batch_size를 1로 줄이기
2. 모델 언로드 후 메모리 정리 확인
3. 데이터 타입 확인 (float32 → float16)
4. 한 번에 처리하는 종목 수 줄이기
```

### 모델 로드 실패 시
```
1. 패키지 버전 확인
2. HuggingFace 캐시 삭제 후 재시도
3. 네트워크 연결 확인
4. 디스크 공간 확인
```

### 데이터 수집 실패 시
```
1. API 제한 확인 (pykrx rate limit)
2. 종목코드 형식 확인
3. 날짜 범위 확인
4. 백업 소스로 전환
```

### 예측값 이상 시
```
1. 입력 데이터 스케일 확인 (특히 TTM)
2. NaN/Inf 값 존재 여부
3. 데이터 길이가 모델 요구사항 충족하는지
4. 역정규화 올바른지
```

---

## 버전 관리

### 커밋 메시지 컨벤션
```
feat: 새 기능 추가
fix: 버그 수정
refactor: 리팩토링
docs: 문서 수정
test: 테스트 추가/수정
chore: 기타 (설정, 빌드 등)
```

### 브랜치 전략
```
main: 안정 버전
develop: 개발 버전
feature/xxx: 기능 개발
fix/xxx: 버그 수정
```

---

## 최종 체크리스트

### 배포 전 확인
```
□ 모든 Phase 테스트 완료
□ 메모리 누수 없음 확인
□ 에러 처리 모두 동작
□ 로그 출력 적절
□ README.md 업데이트
□ requirements.txt 최신화
□ config.yaml 예제 포함
```

---

**문서 끝**
