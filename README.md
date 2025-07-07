# 영어 발음 및 유창성 분석 시스템

Montreal Forced Aligner(MFA)와 PLSPP v2 파이프라인을 활용한 영어 면접 답변 자동 평가 시스템입니다.

## 기술 스택

- **프레임워크**: [FastAPI](https://fastapi.tiangolo.com/)
- **언어**: [Python 3.10](https://www.python.org/)
- **데이터베이스**: [MongoDB](https://www.mongodb.com/), [MariaDB](https://mariadb.org/)
- **음성 처리**: [WhisperX](https://github.com/m-bain/whisperX), [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner)
- **언어 분석**: [OpenAI GPT](https://openai.com/), [Spacy](https://spacy.io/)
- **클라우드 스토리지**: [AWS S3](https://aws.amazon.com/s3/)
- **음성학 분석**: [Praat](https://www.fon.hum.uva.nl/praat/)
- **패키지 관리**: [Conda](https://conda.io/)

## 프로젝트 구조

```
en_analysis/
├── main.py                      # FastAPI 메인 애플리케이션
├── run_analysis.py              # 배치 분석 실행 스크립트
├── fluency_evaluator.py         # 유창성 평가 엔진
├── environment.yml              # Conda 환경 설정
├── requirements.txt             # Python 패키지 의존성
├── plspp_mfa.sh                # PLSPP MFA 파이프라인 실행 스크립트
│
├── models/                      # 데이터 모델 및 데이터베이스 연결
│   ├── database.py             # MongoDB/MariaDB 연결 관리
│   └── schemas.py              # Pydantic 데이터 스키마
│
├── services/                    # 비즈니스 로직 서비스
│   ├── english_analyzer.py     # 영어 분석 메인 로직
│   ├── gpt_service.py          # GPT API 및 프롬프트 관리
│   └── s3_service.py           # AWS S3 파일 관리
│
├── utils/                       # 유틸리티 함수
│   ├── audio_processor.py      # 오디오 파일 처리
│   └── s3_handler.py           # S3 파일 핸들러
│
├── prompts/                     # GPT 프롬프트 템플릿 (YAML)
│   ├── summary.yaml            # 답변 요약 프롬프트
│   ├── fluency_analysis.yaml   # 유창성 분석 프롬프트
│   ├── cefr_evaluation.yaml    # CEFR 평가 프롬프트
│   └── grammar_analysis.yaml   # 문법 분석 프롬프트
│
├── scripts/                     # PLSPP 분석 스크립트
│   ├── diarisationPyannote.py  # 화자 분리
│   ├── myWhisperxTG.py         # WhisperX TextGrid 변환
│   ├── stressAnalysis_mfa.py   # MFA 기반 강세 분석
│   ├── pausesAnalysis.py       # 휴지 패턴 분석
│   └── plsppWeb/               # 웹 기반 PLSPP 도구
│
├── plspp/                       # PLSPP 파이프라인 데이터
│   ├── audio/                  # 오디오 파일 저장소
│   ├── text/                   # 텍스트 파일 저장소
│   ├── CMU/                    # CMU 발음 사전
│   └── scripts/                # PLSPP 분석 스크립트
│
├── test_plspp/                  # 테스트용 PLSPP 환경
└── text/                        # 텍스트 샘플 파일
```

## 주요 패턴 및 아키텍처

### API 서비스 패턴

API 서비스는 `services/` 디렉토리에서 관리됩니다:

- **english_analyzer.py**: 영어 분석 파이프라인 통합 관리
- **gpt_service.py**: OpenAI GPT API 호출 및 YAML 프롬프트 처리
- **s3_service.py**: AWS S3 파일 업로드/다운로드 관리

```python
# 영어 분석 서비스 사용 예시
from services.english_analyzer import EnglishAnalyzer

analyzer = EnglishAnalyzer()
result = await analyzer.analyze_audio(user_id="1", question_num=8)
```

### 데이터베이스 연결 패턴

데이터베이스 연결은 `models/database.py`에서 관리되며, MongoDB와 MariaDB를 동시 지원합니다:

```python
# 데이터베이스 관리자 사용 예시
from models.database import get_db_manager

db_manager = await get_db_manager()
await db_manager.save_to_mongodb(analysis_data)
await db_manager.save_answer_score(user_id, question_num, summary)
```

### 오디오 처리 파이프라인

오디오 처리는 다음 단계로 구성됩니다:

1. **전처리**: webm → wav 변환 (16kHz, mono)
2. **음성 인식**: WhisperX를 통한 정밀 STT
3. **강제 정렬**: MFA를 통한 음소 레벨 정렬
4. **특징 추출**: PLSPP를 통한 음성학적 특징 분석

### 분석 결과 구조

분석 결과는 다음과 같이 구조화됩니다:

- **유창성 분석**: 휴지 패턴, 발화 속도, 억양, 강세 정확도
- **문법 분석**: CEFR 기준 Content, Communicative Achievement, Organisation, Language
- **메타데이터**: 분석 시간, 파일 정보, 처리 통계

## 평가 시스템

### 영어 유창성 평가 (30점 만점)

음성학적 특징을 기반으로 한 정량적 평가:

- **휴지 패턴 분석**: 문법적 위치별 휴지 분포 평가
- **발화 속도 측정**: 음절/단어 당 발화 속도 계산
- **억양 패턴 분석**: F0 최소/최대/표준편차 측정
- **강세 정확도**: CMU 사전 기반 어휘 강세 패턴 비교
- **음성 지속시간**: 세그먼트별 정밀 타이밍 분석

### 영어 문법 평가 (70점 만점)

CEFR 기준을 적용한 언어 능력 평가:

- **Content (내용)**: 주제 관련성, 내용 발전성, 명확성
- **Communicative Achievement (의사소통 성취)**: 목적 달성도, 적절한 톤
- **Organisation (구성)**: 논리적 일관성, 구조적 연결성
- **Language (언어)**: 문법 정확성, 어휘 다양성, 문장 구조

### GPT 기반 언어 분석

YAML 프롬프트를 활용한 체계적 분석:

```python
# GPT 서비스 사용 예시
from services.gpt_service import GPTService

gpt_service = GPTService()
summary = await gpt_service.generate_summary(transcription)
fluency_analysis = await gpt_service.analyze_fluency(transcription, plspp_results)
```

## 개발 가이드

### 시스템 요구사항

```bash
# macOS
brew install praat ffmpeg sox

# Ubuntu/Debian
sudo apt-get install praat ffmpeg sox libsndfile1-dev portaudio19-dev

# CentOS/RHEL
sudo yum install praat ffmpeg sox libsndfile-devel portaudio-devel
```

### 환경 설정

```bash
# 1. Conda 환경 생성
conda env create -f environment.yml
conda activate english-fluency-pipeline

# 2. 언어 모델 다운로드
python -c "import spacy; nlp = spacy.load('en_core_web_md')"

# 3. MFA 설치 확인
mfa version
```

### 환경 변수 설정

`.env` 파일 생성:

```env
# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# 데이터베이스
MONGODB_URI=mongodb://localhost:27017
MARIADB_HOST=localhost
MARIADB_PORT=3306
MARIADB_USER=root
MARIADB_PASSWORD=your_password
MARIADB_DATABASE=audio

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=ap-northeast-2

# 성능 최적화
OMP_NUM_THREADS=4
MKL_NUM_THREADS=4
NUMBA_NUM_THREADS=4
```

### 새로운 분석 모듈 추가

새로운 분석 기능을 추가하려면:

1. `services/` 디렉토리에 서비스 모듈 생성
2. `models/schemas.py`에 데이터 스키마 정의
3. `prompts/` 디렉토리에 GPT 프롬프트 추가
4. `main.py`에 API 엔드포인트 등록

### 새로운 프롬프트 추가

GPT 프롬프트를 추가하려면:

1. `prompts/` 디렉토리에 YAML 파일 생성
2. 프롬프트 구조 정의 (system, user, parameters)
3. `services/gpt_service.py`에서 프롬프트 로딩 함수 추가

## 스크립트

```bash
# 개발 서버 실행
python main.py

# 배치 분석 실행 (모든 사용자)
python run_analysis.py

# 프로덕션 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4

# PLSPP 파이프라인 직접 실행
bash plspp_mfa.sh

# 테스트 실행
python -m pytest tests/
```

## 사용 방법

### 배치 분석 모드 (권장)

대량 데이터 처리를 위한 최적화된 배치 분석:

```bash
conda activate english-fluency-pipeline
python run_analysis.py
```

**특징:**
- S3에서 모든 사용자 자동 탐지
- 3단계 배치 처리로 성능 최적화
- 실시간 진행상황 모니터링
- MFA 한 번 실행으로 모든 사용자 처리

### API 서버 모드

실시간 개별 분석을 위한 RESTful API:

```bash
# 서버 실행
python main.py

# 영어 분석 요청
curl -X POST "http://localhost:8001/analyze/english" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "2", "question_num": 8}'

# 분석 상태 확인
curl "http://localhost:8001/analyze/status/2/8"

# 사용자 전체 결과 조회
curl "http://localhost:8001/analyze/results/2"
```

## 데이터베이스 구조

### answer_score 테이블

답변 평가 기본 정보 저장:

```sql
CREATE TABLE answer_score (
    ANS_SCORE_ID BIGINT PRIMARY KEY NOT NULL,
    INTV_ANS_ID BIGINT NOT NULL,
    ANS_SUMMARY TEXT NULL,
    EVAL_SUMMARY TEXT NULL,
    INCOMPLETE_ANSWER BOOLEAN NULL DEFAULT FALSE,
    INSUFFICIENT_CONTENT BOOLEAN NULL DEFAULT FALSE,
    SUSPECTED_COPYING BOOLEAN NULL DEFAULT FALSE,
    SUSPECTED_IMPERSONATION BOOLEAN NULL DEFAULT FALSE,
    RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### answer_category_result 테이블

항목별 평가 결과 저장:

```sql
CREATE TABLE answer_category_result (
    ANS_CAT_RESULT_ID BIGINT PRIMARY KEY NOT NULL,
    EVAL_CAT_CD VARCHAR(20) NOT NULL,
    ANS_SCORE_ID BIGINT NOT NULL,
    ANS_CAT_SCORE DOUBLE NULL,
    STRENGTH_KEYWORD TEXT NULL,
    WEAKNESS_KEYWORD TEXT NULL,
    RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ANS_SCORE_ID) REFERENCES answer_score(ANS_SCORE_ID)
);
```

### ID 생성 규칙

- **ANS_SCORE_ID**: `{user_id}0{question_num}` (예: 사용자 2, 질문 8 → 208)
- **ANS_CAT_RESULT_ID**: 
  - 영어 유창성: `{user_id}0{question_num}6` (예: 2086)
  - 영어 문법: `{user_id}0{question_num}7` (예: 2087)

### 평가 카테고리 코드

- `ENGLISH_FLUENCY`: 영어 유창성 (30점 만점)
- `ENGLISH_GRAMMAR`: 영어 문법 (70점 만점)

## 성능 최적화

### 병렬 처리 최적화

- **멀티프로세싱**: CPU 코어별 작업 분산
- **GPU 가속**: CUDA 지원 시 자동 활용
- **비동기 I/O**: S3 다운로드 및 데이터베이스 작업 병렬화

### 환경 변수 튜닝

```bash
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export NUMBA_NUM_THREADS=4
export MALLOC_MMAP_THRESHOLD_=131072
export MALLOC_TRIM_THRESHOLD_=131072
```

### 캐싱 전략

- **분석 결과 캐싱**: 중복 분석 방지
- **모델 캐싱**: AI 모델 메모리 상주
- **임시 파일 정리**: 디스크 공간 효율화

## 문제 해결

### MFA 설치 문제

```bash
conda config --add channels conda-forge
conda install montreal-forced-aligner
```

### Praat 경로 설정

```bash
# macOS
export PRAAT_PATH="/Applications/Praat.app/Contents/MacOS/Praat"

# Linux
which praat
```

### GPU 메모리 최적화

```python
# WhisperX 설정 조정
batch_size = 8
compute_type = "int8"
```

### 로그 확인

```bash
# 분석 로그 확인
tail -f logs/analysis.log

# MFA 로그 확인
ls -la ~/.local/share/montreal-forced-aligner/
```

## 기술 문서

### PLSPP MFA 파이프라인

Montreal Forced Aligner와 PLSPP v2를 통합한 고정밀 음성 분석 파이프라인:

1. **음성 전처리**: WhisperX ASR 및 세그멘테이션
2. **MFA 정렬**: 음소 레벨 강제 정렬 (10ms 정밀도)
3. **특징 추출**: Praat 기반 음성학적 특징 분석
4. **구문 분석**: Spacy 및 Berkeley Parser를 통한 언어학적 분석

### 출력 파일 구조

- `stressTable.csv`: 강세 패턴 분석 결과
- `pauseTable.csv`: 휴지 패턴 분석 결과
- `shape/`: TextGrid 형태의 상세 분석 데이터

## 참고 문헌

- McAuliffe et al. (2017). Montreal Forced Aligner
- Bain et al. (2023). WhisperX: Time-Accurate Speech Transcription
- Kitaev & Klein (2018). Constituency Parsing with a Self-Attentive Encoder
