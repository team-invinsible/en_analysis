# 영어 발음 분석 파이프라인

한국어 화자의 영어 발음을 분석하고 평가하는 자동화 시스템입니다. 음성학적 특징을 추출하여 유창성을 측정하고 개선점을 제공합니다.

## 주요 기능

- **음성 분석**: F0(피치), 지속시간, 강세, 휴지 패턴 분석
- **유창성 평가**: 한국어 화자에 특화된 평가 기준 적용
- **자동화 파이프라인**: 음성 파일부터 결과까지 원스톱 처리
- **상세 피드백**: 화자별 맞춤형 개선 제안

## 환경 설정

### 1. Conda 환경 생성

```bash
# Python 3.10.12 환경 생성
conda create -n english-pipeline python=3.10.12

# 환경 활성화
conda activate english-pipeline
```

### 2. 시스템 의존성 설치

#### macOS (Homebrew)
```bash
# FFmpeg 설치
brew install ffmpeg

# Praat 설치 
# https://www.fon.hum.uva.nl/praat/ 에서 다운로드
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### 3. Python 패키지 설치

#### 기본 패키지
```bash
# Conda 기본 패키지
conda install -c conda-forge pip pycparser cffi cython

# Montreal Forced Aligner
conda install -c conda-forge montreal-forced-aligner

# Python 의존성
pip install -r plspp/requirements.txt
```

#### 추가 패키지
```bash
# 자연어 처리
pip install nltk spacy
python -m spacy download en_core_web_md

# 음성 분석
pip install librosa praat-parselmouth

# 기타 도구
pip install whisperx praat-textgrids benepar seaborn==0.12.2
```

### 4. MFA 모델 다운로드

```bash
# 음향 모델 및 사전
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
```

### 5. CMU 발음 사전 설정

```bash
cd plspp
wget https://raw.githubusercontent.com/Alexir/CMUdict/master/cmudict-0.7b
mkdir -p CMU
mv cmudict-0.7b CMU/
```

## 프로젝트 구조

```
english-pipeline/
├── main.py                    # FastAPI 웹 서버 메인
├── run_analysis.py           # 분석 실행 스크립트
├── fluency_evaluator.py      # 유창성 평가 모듈
├── models/                   # 데이터 모델
│   ├── __init__.py
│   ├── database.py          # 데이터베이스 설정
│   └── schemas.py           # Pydantic 스키마
├── services/                 # 비즈니스 로직
│   ├── __init__.py
│   ├── english_analyzer.py  # 영어 분석 서비스
│   ├── gpt_service.py       # GPT API 서비스
│   └── s3_service.py        # AWS S3 서비스
├── utils/                    # 유틸리티 함수
│   ├── __init__.py
│   └── audio_processor.py   # 오디오 처리
├── plspp/                    # 음성 분석 파이프라인
│   ├── audio/               # 입력 음성 파일
│   ├── text/                # 텍스트 파일
│   ├── scripts/             # 분석 스크립트
│   │   ├── diarisationPyannote.py
│   │   ├── myWhisperxTG.py
│   │   ├── pausesAnalysis.py
│   │   ├── stressAnalysis_mfa.py
│   │   └── ...
│   ├── CMU/                 # CMU 발음 사전
│   ├── plspp_mfa.sh        # MFA 파이프라인 스크립트
│   ├── requirements.txt     # Python 의존성
│   ├── speakers.csv         # 화자 정보
│   ├── stressTable.csv      # 강세 분석 결과
│   └── pauseTable.csv       # 휴지 분석 결과
└── README.md
```

## 실행 방법

### 1. 웹 서버 실행 (권장)

```bash
# FastAPI 서버 시작
python main.py

# 브라우저에서 접속
# http://localhost:8000
```

### 2. 분석 스크립트 직접 실행

#### 음성 파일 준비
```bash
# MP3를 WAV로 변환 (필요시)
cd plspp
bash mp3towav.sh
```

#### 전체 파이프라인 실행
```bash
# MFA 기반 음성 분석
bash plspp_mfa.sh

# 또는 개별 분석 실행
python run_analysis.py
```

### 3. 개별 모듈 실행

#### 유창성 평가만 실행
```bash
python fluency_evaluator.py
```

#### 특정 분석 스크립트 실행
```bash
cd plspp/scripts
python stressAnalysis_mfa.py
python pausesAnalysis.py
```

## 데이터 형식

### 입력 데이터
- **음성 파일**: WAV 형식 (16kHz, 모노 권장)
- **텍스트 파일**: 발화 내용 (UTF-8 인코딩)

### 출력 데이터

#### CSV 파일 구조
```csv
spk,file,word,phoneme,startTime,endTime,F0mean,F0sd,F0max,F0min,sylldur,sylldB,expectedStressPosition,observedStressPosition
korean1,korean1.TextGrid,about,ə,0.5,0.7,120.5,15.2,140.0,100.0,0.2,65.2,1,1
```

#### 주요 출력 파일
- **stressTable.csv**: 강세 패턴 분석 결과
- **pauseTable.csv**: 휴지 패턴 분석 결과
- **fluency_evaluation_results_*.json**: 유창성 평가 결과

## 평가 항목

### 가중치 기반 종합 평가
1. **Pause (40%)**: 발화 유창성과 구조적 휴지 패턴
2. **F0/Pitch (30%)**: 강세 인식의 핵심 음향 단서
3. **Duration (15%)**: 강세 음절의 시간적 특성
4. **Stress Accuracy (10%)**: 강세 위치의 정확성
5. **Intensity (5%)**: 음성 강도 및 명료도

### 점수 체계
- **0-100점 척도**
- **한국어 화자 특화 기준**
- **세부 항목별 피드백 제공**

## 문제 해결

### 일반적인 오류

#### MFA 설치 문제
```bash
# Conda 채널 추가
conda config --add channels conda-forge
conda install montreal-forced-aligner
```

#### 음성 파일 인식 오류
```bash
# FFmpeg으로 포맷 변환
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

#### 의존성 충돌
```bash
# 환경 초기화 후 재설치
conda deactivate
conda remove -n english-pipeline --all
# 위의 설치 과정 반복
```
