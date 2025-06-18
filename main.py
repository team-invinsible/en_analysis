from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, Optional, List
import logging
import asyncio
import uvicorn
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from services.english_analyzer import EnglishAnalyzer
from models.database import init_databases
from models.schemas import AnalysisRequest, AnalysisResponse

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 실행
    try:
        await init_databases()
        logger.info("데이터베이스 초기화 완료")
    except Exception as e:
        logger.warning(f"데이터베이스 초기화 실패, 일부 기능이 제한될 수 있습니다: {str(e)}")
        # 서버는 계속 실행 (데이터베이스 없이도 기본 기능 제공)
    
    yield
    
    # 종료 시 실행 (필요시 정리 작업)
    logger.info("서버 종료")

app = FastAPI(
    title="영어 유창성 평가 API",
    description="S3 음성 파일을 분석하여 영어 유창성과 문법을 평가하는 시스템",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "message": "영어 유창성 평가 API 서버",
        "version": "1.0.0",
        "status": "운영 중"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "english-fluency-api"}

@app.post("/analyze/english", response_model=AnalysisResponse)
async def analyze_english_fluency(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks
):
    """
    영어 유창성 분석 API
    
    S3에서 음성 파일을 다운로드하고 분석하여 유창성과 문법 점수를 계산합니다.
    question_num 8 또는 9인 경우만 처리합니다.
    """
    try:
        # question_num 검증
        if request.question_num not in [8, 9]:
            raise HTTPException(
                status_code=400,
                detail=f"영어 분석은 question_num이 8 또는 9인 경우만 가능합니다. 입력값: {request.question_num}"
            )
        
        # 분석기 초기화
        analyzer = EnglishAnalyzer()
        
        # 백그라운드에서 분석 수행
        background_tasks.add_task(
            analyzer.analyze_audio_async,
            request.user_id,
            request.question_num
        )
        
        return AnalysisResponse(
            user_id=request.user_id,
            question_num=request.question_num,
            status="분석 시작됨",
            message=f"사용자 {request.user_id}의 question {request.question_num} 분석이 시작되었습니다."
        )
        
    except Exception as e:
        logger.error(f"영어 분석 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=f"분석 중 오류가 발생했습니다: {str(e)}")

@app.get("/analyze/status/{user_id}/{question_num}")
async def get_analysis_status(user_id: str, question_num: int):
    """분석 상태 확인"""
    try:
        analyzer = EnglishAnalyzer()
        result = await analyzer.get_analysis_result(user_id, question_num)
        
        if result:
            return {
                "status": "completed",
                "result": result
            }
        else:
            return {
                "status": "processing or not found",
                "message": "분석이 진행 중이거나 결과를 찾을 수 없습니다."
            }
            
    except Exception as e:
        logger.error(f"상태 확인 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyze/results/{user_id}")
async def get_user_results(user_id: str):
    """특정 사용자의 모든 분석 결과 조회"""
    try:
        analyzer = EnglishAnalyzer()
        results = await analyzer.get_user_all_results(user_id)
        
        return {
            "user_id": user_id,
            "total_analyses": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"결과 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    ) 