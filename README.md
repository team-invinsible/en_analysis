# 🎙️ 영어 유창성 평가 시스템 (PLSPP MFA Pipeline)

영어 면접 답변의 유창성과 문법을 자동으로 평가하는 AI 기반 시스템입니다.  
**Montreal Forced Aligner (MFA)**와 **PLSPP v2** 파이프라인을 활용한 고정밀 음성학적 분석을 제공합니다.

## 📋 주요 기능

### 🎯 평가 대상
- **질문 8, 9번**: 영어 면접 답변 (영어 유창성 전용 분석)
- **음성 파일**: S3에서 자동으로 다운로드하여 분석

### 🏆 평가 항목

#### 1. 영어 유창성 (30점 만점)
- **휴지 패턴 분석**: 문법적 위치별 휴지 분포
- **발화 속도 평가**: 음절/단어 당 발화 속도
- **억양 패턴 분석**: F0 최소/최대/표준편차 측정  
- **음성 지속시간 측정**: 세그먼트별 정밀 타이밍
- **강세 정확도 평가**: CMU 사전 기반 어휘 강세 패턴
- **발음 정확도 평가**: MFA 기반 음소 레벨 정렬

#### 2. 영어 문법 (70점 만점)
- **CEFR 기준 평가**
  - Content (내용): 관련성, 발전성, 명확성
  - Communicative Achievement (의사소통 성취): 목적 달성, 적절한 톤
  - Organisation (구성): 일관성, 논리적 구조, 연결성
  - Language (언어): 문법, 어휘, 문장 구조의 다양성과 정확성

### 🧠 GPT 분석 기능
- **답변 요약**: STT 결과를 한국어로 요약
- **강점/약점 키워드**: 유창성과 문법별 개선점 추출
- **YAML 프롬프트 관리**: 유연한 프롬프트 설정

## 🔧 시스템 요구사항

### 필수 시스템 의존성
```bash
# macOS
brew install praat ffmpeg sox

# Ubuntu/Debian
sudo apt-get update
sudo apt-get install praat ffmpeg sox libsndfile1-dev portaudio19-dev

# CentOS/RHEL
sudo yum install epel-release
sudo yum install praat ffmpeg sox libsndfile-devel portaudio-devel
```

### GPU 지원 (선택사항)
- **CUDA 11.8+** (WhisperX, PyAnnote 가속화)
- **8GB+ GPU 메모리** 권장

## 🚀 설치 및 실행

### 1. Conda 환경 설정 (권장)

```bash
# 1. 저장소 복제
git clone <repository-url>
cd en_analysis

# 2. Conda 환경 생성 및 활성화
conda env create -f environment.yml
conda activate english-fluency-pipeline

# 3. Spacy 언어 모델 다운로드 확인
python -c "import spacy; nlp = spacy.load('en_core_web_md'); print('✅ Spacy 모델 로드 성공')"

# 4. MFA 설치 확인
mfa version
```

### 2. 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# MongoDB
MONGODB_URI=mongodb://localhost:27017

# MariaDB
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=your_password
MARIADB_DATABASE=audio

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2

# 성능 최적화 (선택사항)
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
NUMBA_NUM_THREADS=4
```

### 3. 서버 실행

```bash
# 개발 모드
conda activate english-fluency-pipeline
python main.py

# 프로덕션 모드
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
```

서버가 http://localhost:8001 에서 실행됩니다.

### 4. 배치 분석 실행 (선택사항)

API 서버 대신 배치 모드로 모든 사용자의 분석을 한 번에 실행할 수 있습니다:

```bash
# 모든 사용자 자동 분석 (S3에서 사용자 목록 자동 탐지)
conda activate english-fluency-pipeline
python run_analysis.py

# 또는 직접 실행
python3 run_analysis.py
```

**배치 분석 특징:**
- 🔍 **자동 탐지**: S3에서 모든 사용자와 질문 8, 9번 파일 자동 감지
- ⚡ **최적화된 처리**: 3단계 배치 처리로 성능 극대화
  1. 모든 오디오 파일 다운로드 및 변환
  2. PLSPP MFA 통합 분석 (한 번만 실행)
  3. 개별 사용자별 결과 분석 및 저장
- 📊 **진행 상황 표시**: 실시간 처리 현황 모니터링
- 🎯 **대량 처리**: 수십 명의 사용자 동시 처리 가능

## 🔬 PLSPP MFA 분석 파이프라인

### 분석 단계별 프로세스

#### 1. 음성 전처리
- **ASR**: WhisperX를 통한 고정밀 음성 인식
- **세그멘테이션**: 단어 레벨 시간 정렬
- **포맷 변환**: webm → wav (16kHz, mono)

#### 2. MFA 정렬
- **음소 레벨 정렬**: Montreal Forced Aligner
- **사전 기반**: CMU Pronunciation Dictionary
- **정확도**: 음소별 10ms 이내 정밀도

#### 3. 음성학적 특징 추출
- **음절핵 탐지**: Praat 기반 자동 탐지
- **F0 분석**: 최소/최대/표준편차 측정
- **강세 패턴**: 예상 vs 관찰된 강세 비교

#### 4. 구문 분석
- **POS 태깅**: Spacy 기반 품사 분석
- **구문 파싱**: Berkeley Neural Parser
- **휴지 분류**: 문법적 위치별 휴지 분석

### 출력 파일
- `stressTable.csv`: 강세 패턴 분석 결과
- `pauseTable.csv`: 휴지 패턴 분석 결과
- `shape/`: TextGrid 형태의 상세 분석 데이터

## 📡 사용 방법

### 🚀 방법 1: 배치 분석 (대량 처리 권장)

모든 사용자를 한 번에 분석하는 고효율 배치 모드:

```bash
# 1. Conda 환경 활성화
conda activate english-fluency-pipeline

# 2. 배치 분석 실행
python run_analysis.py
```

**출력 예시:**
```
🚀 영어 분석 스크립트 시작 (배치 처리 모드)
   📋 S3에서 모든 사용자 목록 가져오는 중...
   발견된 사용자: 5명 - 1, 2, 3, 4, 5
   분석할 질문 번호: 8, 9

📊 총 10개의 분석 작업을 배치 처리합니다:
   1. 사용자 1, 질문 8
   2. 사용자 1, 질문 9
   ...

🔄 1단계: 모든 오디오 파일 다운로드 및 변환 중...
🔬 2단계: PLSPP MFA 배치 분석 실행 중...
📊 3단계: 개별 분석 및 데이터베이스 저장 중...

🎉 모든 분석 작업이 완료되었습니다! (총 10개)
```

### 🌐 방법 2: API 서버 (개별 요청)

실시간 개별 분석이 필요한 경우:

#### API 서버 실행
```bash
conda activate english-fluency-pipeline
python main.py
```

#### 영어 유창성 분석 요청

```bash
curl -X POST "http://localhost:8001/analyze/english" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "2",
       "question_num": 8
     }'
```

#### 분석 상태 확인

```bash
curl "http://localhost:8001/analyze/status/2/8"
```

#### 사용자 전체 결과 조회

```bash
curl "http://localhost:8001/analyze/results/2"
```

### 📊 방법 비교

| 특징 | 배치 분석 | API 서버 |
|------|-----------|----------|
| **처리 속도** | ⚡ 매우 빠름 (MFA 1회 실행) | 🐌 상대적 느림 (개별 MFA) |
| **사용 사례** | 대량 데이터 일괄 처리 | 실시간 개별 요청 |
| **리소스 효율** | 🏆 최적 (배치 최적화) | 🔧 일반적 |
| **모니터링** | 📈 진행상황 실시간 표시 | 🔍 API 응답으로 확인 |
| **권장 상황** | 정기 분석, 초기 데이터 처리 | 온디맨드 분석, 웹 서비스 |

## 🗄️ 데이터베이스 구조

### 새로운 테이블 구조

#### 1. `answer_score` 테이블
답변 평가 기본 정보를 저장합니다.

```sql
CREATE TABLE answer_score (
    ANS_SCORE_ID BIGINT PRIMARY KEY NOT NULL,          -- 답변 평가 ID
    INTV_ANS_ID BIGINT NOT NULL,                       -- 면접 답변 ID
    ANS_SUMMARY TEXT NULL,                             -- 답변 요약
    EVAL_COMMENT TEXT NULL,                            -- 답변 평가
    EVAL_SUMMARY TEXT NULL,                            -- 전체 평가 요약
    INCOMPLETE_ANSWER BOOLEAN NULL DEFAULT FALSE,       -- 미완료 여부
    INSUFFICIENT_CONTENT BOOLEAN NULL DEFAULT FALSE,    -- 내용 부족 여부
    SUSPECTED_COPYING BOOLEAN NULL DEFAULT FALSE,       -- 커닝 의심 여부
    SUSPECTED_IMPERSONATION BOOLEAN NULL DEFAULT FALSE, -- 대리 시험 의심 여부
    RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,   -- 등록 일시
    UPD_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP -- 수정 일시
);
```

#### 2. `answer_category_result` 테이블
답변 항목별 평가 결과를 저장합니다.

```sql
CREATE TABLE answer_category_result (
    ANS_CAT_RESULT_ID BIGINT PRIMARY KEY NOT NULL,      -- 답변 항목별 평가 ID
    EVAL_CAT_CD VARCHAR(20) NOT NULL,                   -- 평가 항목 코드
    ANS_SCORE_ID BIGINT NOT NULL,                       -- 답변 평가 ID (외래키)
    ANS_CAT_SCORE DOUBLE NULL,                          -- 항목별 점수
    STRENGTH_KEYWORD TEXT NULL,                         -- 강점 키워드
    WEAKNESS_KEYWORD TEXT NULL,                         -- 약점 키워드
    RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,   -- 등록 일시
    FOREIGN KEY (ANS_SCORE_ID) REFERENCES answer_score(ANS_SCORE_ID)
);
```

### ID 생성 규칙
- **ANS_SCORE_ID**: `{user_id}0{question_num}` (예: 사용자 2, 질문 8 → 208)
- **INTV_ANS_ID**: `{user_id}0{question_num}` (예: 사용자 2, 질문 8 → 208)
- **ANS_CAT_RESULT_ID**: 
  - 영어 유창성: `{user_id}0{question_num}1` (예: 2081)
  - 영어 문법: `{user_id}0{question_num}2` (예: 2082)

### 평가 카테고리 코드
- `ENGLISH_FLUENCY`: 영어 유창성 (30점 만점)
- `ENGLISH_GRAMMAR`: 영어 문법 (70점 만점)

## ⚡ 성능 최적화

### 병렬 처리
- **멀티프로세싱**: CPU 코어별 작업 분산
- **GPU 가속**: CUDA 지원 시 자동 활용
- **비동기 I/O**: S3 다운로드 및 DB 작업 병렬화

### 캐싱 전략
- **분석 결과 캐싱**: 중복 분석 방지
- **모델 캐싱**: AI 모델 메모리 상주
- **임시 파일 정리**: 디스크 공간 효율화

### 환경 변수 튜닝
```bash
# CPU 최적화
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMBA_NUM_THREADS=4

# 메모리 최적화
export MALLOC_MMAP_THRESHOLD_=131072
export MALLOC_TRIM_THRESHOLD_=131072
```

## 🔧 문제 해결

### 일반적인 문제

#### MFA 설치 오류
```bash
# conda-forge 채널 우선순위 설정
conda config --add channels conda-forge
conda install montreal-forced-aligner
```

#### Praat 경로 문제
```bash
# macOS
export PRAAT_PATH="/Applications/Praat.app/Contents/MacOS/Praat"

# Linux
sudo apt-get install praat
which praat
```

#### GPU 메모리 부족
```python
# WhisperX 배치 크기 조정
batch_size = 8  # 기본값 16에서 감소
compute_type = "int8"  # float16에서 변경
```

### 로그 확인
```bash
# 분석 로그
tail -f logs/analysis.log

# MFA 로그
ls -la ~/.local/share/montreal-forced-aligner/
```

## 📁 프로젝트 구조

```
en_analysis/
├── main.py                    # FastAPI 메인 애플리케이션
├── run_analysis.py            # 배치 분석 실행 스크립트
├── environment.yml            # Conda 환경 설정
├── plspp_mfa.sh              # PLSPP MFA 파이프라인 스크립트
├── models/
│   ├── database.py           # 데이터베이스 연결 및 테이블 구조
│   └── schemas.py            # Pydantic 스키마 정의
├── services/
│   ├── english_analyzer.py   # 영어 분석 메인 로직 (성능 최적화)
│   ├── gpt_service.py        # GPT API 및 YAML 프롬프트 관리
│   └── s3_service.py         # S3 파일 다운로드
├── utils/
│   └── audio_processor.py    # 오디오 파일 처리
├── prompts/                   # YAML 프롬프트 파일들
│   ├── summary.yaml          # 답변 요약 프롬프트
│   ├── fluency_analysis.yaml # 유창성 분석 프롬프트
│   ├── cefr_evaluation.yaml  # CEFR 평가 프롬프트
│   └── grammar_analysis.yaml # 문법 분석 프롬프트
├── scripts/                   # PLSPP 분석 스크립트들
├── CMU/                      # CMU 발음 사전
└── audio/                    # 임시 오디오 파일 저장소
```

## 📖 참고 문헌

- **Montreal Forced Aligner**: McAuliffe et al. (2017)
- **PLSPP**: Prosodic and Lexical Stress Pattern Pipeline
- **WhisperX**: Bain et al. (2023)
- **Berkeley Neural Parser**: Kitaev & Klein (2018)



**🎯 핵심 기술**: Montreal Forced Aligner, PLSPP v2, WhisperX, PyAnnote, FastAPI, GPT-4  
**🔬 분석 정밀도**: 음소 레벨 10ms 이내, F0/강세/휴지 패턴 종합 분석
