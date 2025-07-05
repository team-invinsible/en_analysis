# ----------------------------------------------------------------------------------------------------
# 작성목적 : API 요청 기반 실시간 영어 능력 분석
# 작성일 : 2025-06-27

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-27 | API 서버로 재구성 | 영상 분석 서버 구조를 적용하여 API 기반 실시간 처리 방식으로 재작성 | 구동빈
# ----------------------------------------------------------------------------------------------------

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
import os
import tempfile
import shutil
from datetime import datetime

# --- 경로 설정 및 모듈 임포트 ---
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

load_dotenv()

from utils.s3_handler import S3Handler
# 'EnglishAnalyzer'의 실제 위치에 따라 경로를 맞춰야 합니다.
from services.english_analyzer import EnglishAnalyzer

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Pydantic 모델 정의 ---
class AnalysisPayload(BaseModel):
    s3ObjectKey: str

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    message: str
    user_id: str
    question_num: int

# --- FastAPI 애플리케이션 생성 ---
app = FastAPI(
    title="영어 능력 분석 API",
    description="메인 서버로부터 S3 Object Key를 받아 영어 능력 분석을 수행합니다."
)

# --- 유틸리티 함수 ---
def parse_s3_key(s3_key: str) -> tuple[str, str]:
    """
    S3 Object Key에서 user_id와 question_num을 추출합니다.
    예상 키 형식: 'team12/interview_audio/{user_id}/{question_num}/{filename}'
    """
    try:
        parts = Path(s3_key).parts
        # 경로 구조 예: ('team12', 'interview_audio', '2', '2', 'TalkFile.wav') 또는 ('team12', 'interview_video', '2', '2', 'video.webm')
        if len(parts) < 4 or parts[0].lower() != 'team12' or parts[1].lower() not in ['interview_audio', 'interview_video']:
             raise ValueError("잘못된 S3 키 구조")
        
        user_id = parts[2]
        question_num = parts[3]
        
        return user_id, question_num
    except (IndexError, ValueError) as e:
        logger.error(f"S3 키 형식 분석 실패: {s3_key}. 예상 형식: 'team12/interview_audio(또는 interview_video)/{{user_id}}/{{question_num}}/filename' - {e}")
        raise ValueError(f"잘못된 S3 키 형식입니다: {s3_key}")

# --- 분석 처리 함수 ---
async def run_analysis(s3_key: str):
    """S3 키를 받아 영어 분석을 실행하는 함수"""
    logger.info(f"Received S3 key for analysis: {s3_key}")
    s3_handler = S3Handler()
    
    # s3_key에서 정보 파싱
    try:
        # "team12/interview_audio/{user_id}/{question_num}/{filename}" 또는 "team12/interview_video/{user_id}/{question_num}/{filename}"
        parts = s3_key.split('/')
        if len(parts) < 5 or parts[0] != 'team12' or parts[1] not in ['interview_audio', 'interview_video']:
            raise ValueError(f"잘못된 S3 키 형식: {s3_key}")
        user_id = parts[2]
        question_num = int(parts[3])
        filename = parts[4]
        logger.info(f"Parsed info: user_id={user_id}, question_num={question_num}, filename={filename}")
    except (IndexError, ValueError) as e:
        logger.error(f"Failed to parse S3 key '{s3_key}'. Error: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"S3 키 형식 파싱 실패: {e}")

    # 분석을 위한 임시 작업 디렉토리 생성
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        try:
            # 1. S3에서 파일 다운로드
            logger.info(f"Downloading {s3_key} from S3 to {temp_dir_path}...")
            local_audio_path = await s3_handler.download_file(s3_key, str(temp_dir_path))
            
            if not local_audio_path:
                logger.error(f"Failed to download file from S3 for key: {s3_key}")
                raise HTTPException(status_code=404, detail="S3에서 파일 다운로드 실패")
            
            logger.info(f"File downloaded successfully to: {local_audio_path}")
            
            # 2. 리팩토링된 Analyzer를 사용하여 분석 실행
            logger.info("Initializing EnglishAnalyzer...")
            # Analyzer에 user_id, question_num과 함께 작업 디렉토리(base_path)를 전달
            analyzer = EnglishAnalyzer(
                user_id=user_id, 
                question_num=question_num, 
                base_path=str(temp_dir_path)
            )
            
            logger.info(f"Starting analysis for {local_audio_path}...")
            # 다운로드한 파일 경로를 analyze 메서드에 전달
            analysis_result = await analyzer.analyze(local_audio_path)
            
            logger.info(f"Successfully completed analysis for S3 key: {s3_key}")
            
            # 분석이 실제로 완료되었는지 확인
            if analysis_result is None:
                logger.info(f"Analysis completed successfully for user {user_id}, question {question_num}")
                return {
                    "analysis_id": f"{user_id}_{question_num}",
                    "status": "completed",
                    "message": "영어 분석이 성공적으로 완료되었습니다.",
                    "user_id": user_id,
                    "question_num": question_num
                }
            else:
                logger.error(f"Analysis returned unexpected result: {analysis_result}")
                raise HTTPException(status_code=500, detail="분석 완료 상태 확인 실패")

        except Exception as e:
            logger.error(f"An error occurred during the analysis for S3 key '{s3_key}'. Error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"분석 처리 중 오류 발생: {e}")
        finally:
            logger.info(f"Cleaning up temporary directory: {temp_dir_path}")
            # 'with' 구문이 끝나면 temp_dir은 자동으로 삭제됩니다.

# --- API 엔드포인트 ---
@app.post("/analysis/english", response_model=AnalysisResponse)
async def request_english_analysis(
    request: AnalysisPayload,
):
    """영어 면접 답변에 대한 분석을 요청하는 엔드포인트 (s3ObjectKey 사용)"""
    logger.info(f"Received english analysis request for S3 key: {request.s3ObjectKey}")
    return await run_analysis(request.s3ObjectKey)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "English Analysis API is running."}

# --- 서버 실행 ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003) 