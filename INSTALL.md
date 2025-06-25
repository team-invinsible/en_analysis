# 영어 발음 분석 파이프라인 설치 가이드

본 문서는 영어 발음 분석 파이프라인 프로젝트의 환경 설정 방법을 안내합니다.

## 시스템 요구사항

- **Python**: 3.10.12 (권장)
- **운영체제**: macOS, Linux (Ubuntu/Debian)
- **메모리**: 최소 8GB RAM (16GB 권장)
- **저장공간**: 최소 5GB 여유 공간

## 방법 1: Conda 환경 사용 (권장)

### 1.1 Conda 설치

```bash
# Miniconda 다운로드 및 설치 (macOS)
brew install --cask miniconda

# 또는 Linux의 경우
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

### 1.2 환경 생성 및 활성화

```bash
# environment.yml을 사용한 환경 생성
conda env create -f environment.yml

# 환경 활성화
conda activate english-pipeline
```

### 1.3 추가 모델 다운로드

```bash
# Spacy 영어 모델 다운로드
python -m spacy download en_core_web_md
```

### 1.4 CMU 발음 사전 설정

```bash
cd plspp
mkdir -p CMU
wget https://raw.githubusercontent.com/Alexir/CMUdict/master/cmudict-0.7b -O CMU/cmudict-0.7b
```

## 방법 2: pip 직접 설치

### 2.1 Python 가상환경 생성

```bash
python3.10 -m venv env
source env/bin/activate  # macOS/Linux
# 또는 Windows의 경우: env\Scripts\activate
```

### 2.2 시스템 의존성 설치

#### macOS
```bash
brew install ffmpeg
```

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install ffmpeg
```

### 2.3 Python 패키지 설치

```bash
# Montreal Forced Aligner (중요)
# 반드시 conda로 설치해야 함
conda install -c conda-forge montreal-forced-aligner

# Python 의존성
pip install -r requirements.txt

# Spacy 모델
python -m spacy download en_core_web_md
```

## 환경 변수 설정

`.env` 파일 생성:

```bash
# OpenAI API (선택사항)
OPENAI_API_KEY=your_openai_api_key

# AWS 설정 (선택사항)  
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=your_region

# 데이터베이스 설정 (선택사항)
MONGODB_URL=mongodb://localhost:27017
MYSQL_HOST=localhost
MYSQL_USER=your_user
MYSQL_PASSWORD=your_password
```

## 설치 확인

```bash
# 환경 활성화
conda activate english-pipeline

# 웹 서버 실행 테스트
python main.py

# 브라우저에서 접속
# http://localhost:8000
```

## 문제 해결

### MFA 설치 문제
```bash
# Conda 채널 추가
conda config --add channels conda-forge
conda install montreal-forced-aligner
```

### 음성 파일 인식 오류
```bash
# FFmpeg으로 포맷 변환
ffmpeg -i input.mp3 -ar 16000 -ac 1 output.wav
```

### 의존성 충돌
```bash
# 환경 초기화 후 재설치
conda deactivate
conda remove -n english-pipeline --all
conda env create -f environment.yml
```

## 주요 라이브러리 설명

### 필수 라이브러리
- **FastAPI**: 웹 API 서버
- **Montreal Forced Aligner**: 음성 강제 정렬 (conda 설치 필수)
- **WhisperX**: 음성 인식 및 정렬
- **PyAnnote**: 화자 분리
- **Praat-Parselmouth**: 음성 분석
- **Spacy**: 자연어 처리

### 선택적 라이브러리
- **OpenAI**: GPT API (유창성 평가 개선용)
- **Boto3**: AWS S3 (음성 파일 저장용)
- **MongoDB/MySQL**: 데이터 저장용

## 최소 설치 (테스트용)

빠른 테스트를 위한 최소 설치:

```bash
# 핵심 패키지만 설치
pip install fastapi uvicorn pydantic
pip install praat-parselmouth librosa soundfile
pip install spacy
python -m spacy download en_core_web_md

# MFA 설치 (conda 필수)
conda install -c conda-forge montreal-forced-aligner
```