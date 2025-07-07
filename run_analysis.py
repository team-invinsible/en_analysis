# ----------------------------------------------------------------------------------------------------
# 작성목적 : API 요청 기반 실시간 영어 능력 분석
# 작성일 : 2025-06-27

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-27 | API 서버로 재구성 | 영상 분석 서버 구조를 적용하여 API 기반 실시간 처리 방식으로 재작성 | 구동빈
# 2025-07-06 | Redis 연결 추가 | Redis 연결 추가 | 이주형
# 2025-07-07 | 영어 분석 서버 구조 재작성 | 영어 분석 서버 구조를 적용하여 API 기반 실시간 처리 방식으로 재작성 | 이주형
# ----------------------------------------------------------------------------------------------------

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import sys
from pathlib import Path
from dotenv import load_dotenv
import logging
import os
import tempfile
import shutil

import uuid
# import redis.asyncio as redis  # Redis 비활성화
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import aiomysql
import pymysql

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

# --- Redis 설정 (비활성화) ---
# REDIS_URL = os.getenv("REDIS_URL", "redis://admin:Skala25a!23$@ac55000eca8b749a6b916f7a04c4c1c2-9f9c8ea7fa9b0e7a.elb.ap-northeast-2.amazonaws.com:6379")
# redis_client = None

# --- MariaDB 설정 ---
MARIADB_CONFIG = {
    "host": os.getenv("MARIADB_HOST", "localhost"),
    "port": int(os.getenv("MARIADB_PORT", "3306")),
    "user": os.getenv("MARIADB_USER", "root"),
    "password": os.getenv("MARIADB_PASSWORD", ""),
    "db": os.getenv("MARIADB_DATABASE", "ai_interview"),
    "charset": "utf8mb4"
}
db_pool = None

# --- Job 상태 상수 ---
class JobStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# --- Pydantic 모델 정의 ---
class AnalysisPayload(BaseModel):
    s3ObjectKey: str

class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str
    message: str

class JobSubmitRequest(BaseModel):
    s3ObjectKey: str

class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str
    estimated_time: int

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

# --- FastAPI 애플리케이션 생성 ---
app = FastAPI(
    title="영어 능력 분석 API",
    description="메인 서버로부터 S3 Object Key를 받아 영어 능력 분석을 수행합니다."
)

@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작시 MariaDB 연결 초기화"""
    global db_pool
    try:
        # MariaDB 연결 풀 생성
        db_pool = await aiomysql.create_pool(**MARIADB_CONFIG, maxsize=10, minsize=1)
        logger.info("✅ MariaDB 연결 풀 생성 완료")
        
        # job_status 테이블 생성 (없을 경우)
        await create_job_tables()
        
    except Exception as e:
        logger.error(f"❌ MariaDB 연결 실패: {str(e)}")
        db_pool = None
        
    # Redis 연결 시도 (주석 처리)
    # global redis_client
    # try:
    #     redis_client = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    #     await redis_client.ping()
    #     logger.info("✅ Redis 연결 완료")
    # except Exception as e:
    #     logger.error(f"❌ Redis 연결 실패: {str(e)}")
    #     redis_client = None

@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료시 MariaDB 연결 종료"""
    global db_pool
    if db_pool:
        db_pool.close()
        await db_pool.wait_closed()
        logger.info("✅ MariaDB 연결 풀 종료 완료")
        
    # Redis 연결 종료 (주석 처리)
    # global redis_client
    # if redis_client:
    #     await redis_client.close()
    #     logger.info("✅ Redis 연결 종료 완료")

# --- 유틸리티 함수 ---
def parse_s3_key(s3_key: str) -> tuple[str, str]:
    """
    S3 Object Key에서 user_id와 question_num을 추출합니다.
    예상 키 형식: 'team12/interview_audio/{user_id}/{question_num}/{filename}'
    """
    try:
        parts = Path(s3_key).parts
        # 경로 구조 예: ('team12', 'interview_audio', '2', '2', 'TalkFile.wav')
        if len(parts) < 4 or parts[0].lower() != 'team12' or parts[1].lower() != 'interview_audio':
             raise ValueError("잘못된 S3 키 구조")
        
        user_id = parts[2]
        question_num = parts[3]
        
        return user_id, question_num
    except (IndexError, ValueError) as e:
        logger.error(f"S3 키 형식 분석 실패: {s3_key}. 예상 형식: 'team12/interview_audio/{{user_id}}/{{question_num}}/filename' - {e}")
        raise ValueError(f"잘못된 S3 키 형식입니다: {s3_key}")

# --- MariaDB Job 테이블 생성 ---
async def create_job_tables():
    """업무 상태 및 결과 관리를 위한 테이블 생성"""
    if not db_pool:
        logger.warning("MariaDB 풀이 없습니다. 테이블을 생성할 수 없습니다.")
        return
        
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # job_status 테이블 생성
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS job_status (
                        job_id VARCHAR(36) PRIMARY KEY,
                        status VARCHAR(20) NOT NULL,
                        progress INT DEFAULT 0,
                        message TEXT,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                """)
                
                # job_result 테이블 생성
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS job_result (
                        job_id VARCHAR(36) PRIMARY KEY,
                        result JSON,
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (job_id) REFERENCES job_status(job_id) ON DELETE CASCADE
                    )
                """)
                
                await conn.commit()
                logger.info("✅ Job 테이블 생성 완료")
                
    except Exception as e:
        logger.error(f"❌ Job 테이블 생성 실패: {str(e)}")

# --- MariaDB Job 관리 함수 ---
async def set_job_status(job_id: str, status: str, progress: int = 0, message: str = "", error_message: str = None):
    """MariaDB에 Job 상태 저장"""
    if not db_pool:
        logger.warning("MariaDB 풀이 없습니다. Job 상태를 저장할 수 없습니다.")
        return
    
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 기존 레코드 확인
                await cursor.execute(
                    "SELECT job_id FROM job_status WHERE job_id = %s",
                    (job_id,)
                )
                existing = await cursor.fetchone()
                
                if existing:
                    # 업데이트
                    await cursor.execute("""
                        UPDATE job_status 
                        SET status = %s, progress = %s, message = %s, error_message = %s, updated_at = NOW()
                        WHERE job_id = %s
                    """, (status, progress, message, error_message, job_id))
                else:
                    # 삽입
                    await cursor.execute("""
                        INSERT INTO job_status (job_id, status, progress, message, error_message)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (job_id, status, progress, message, error_message))
                
                await conn.commit()
                
                # 상태 확인을 위한 조회
                await cursor.execute(
                    "SELECT status, progress FROM job_status WHERE job_id = %s",
                    (job_id,)
                )
                verify_result = await cursor.fetchone()
                if verify_result:
                    logger.info(f"Job {job_id} 상태 업데이트 확인: {verify_result[0]} ({verify_result[1]}%)")
                else:
                    logger.warning(f"Job {job_id} 상태 확인 실패: 레코드를 찾을 수 없음")
                
    except Exception as e:
        logger.error(f"Job 상태 저장 실패 {job_id}: {str(e)}")

async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """MariaDB에서 Job 상태 조회"""
    if not db_pool:
        return None
        
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM job_status WHERE job_id = %s",
                    (job_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    # datetime 객체를 문자열로 변환
                    if result.get('created_at'):
                        result['created_at'] = result['created_at'].isoformat()
                    if result.get('updated_at'):
                        result['updated_at'] = result['updated_at'].isoformat()
                    return result
                return None
                
    except Exception as e:
        logger.error(f"Job 상태 조회 실패 {job_id}: {str(e)}")
        return None

async def set_job_result(job_id: str, result: Dict[str, Any]):
    """MariaDB에 Job 결과 저장"""
    if not db_pool:
        logger.warning("MariaDB 풀이 없습니다. Job 결과를 저장할 수 없습니다.")
        return
        
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # 기존 결과 확인
                await cursor.execute(
                    "SELECT job_id FROM job_result WHERE job_id = %s",
                    (job_id,)
                )
                existing = await cursor.fetchone()
                
                if existing:
                    # 업데이트
                    await cursor.execute(
                        "UPDATE job_result SET result = %s, completed_at = NOW() WHERE job_id = %s",
                        (json.dumps(result), job_id)
                    )
                else:
                    # 삽입
                    await cursor.execute(
                        "INSERT INTO job_result (job_id, result) VALUES (%s, %s)",
                        (job_id, json.dumps(result))
                    )
                
                await conn.commit()
                logger.info(f"Job {job_id} 결과 저장 완료")
                
    except Exception as e:
        logger.error(f"Job 결과 저장 실패 {job_id}: {str(e)}")

async def get_job_result(job_id: str) -> Optional[Dict[str, Any]]:
    """MariaDB에서 Job 결과 조회"""
    if not db_pool:
        return None
        
    try:
        async with db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(
                    "SELECT * FROM job_result WHERE job_id = %s",
                    (job_id,)
                )
                result = await cursor.fetchone()
                
                if result:
                    # JSON 문자열을 딕셔너리로 변환
                    if result.get('result'):
                        result['result'] = json.loads(result['result'])
                    
                    # datetime 객체를 문자열로 변환
                    if result.get('completed_at'):
                        result['completed_at'] = result['completed_at'].isoformat()
                    
                    return result
                return None
                
    except Exception as e:
        logger.error(f"Job 결과 조회 실패 {job_id}: {str(e)}")
        return None

# --- 백그라운드 처리 함수 ---
async def process_english_analysis_from_s3(background_tasks: BackgroundTasks, s3_key: str):
    """S3 키를 받아 영어 분석을 비동기적으로 처리하는 함수"""
    background_tasks.add_task(run_analysis_in_background, s3_key)
    return {"message": "English analysis has been started in the background."}

async def run_analysis_in_background(s3_key: str, job_id: str = None):
    """백그라운드에서 실제 분석을 실행하는 함수"""
    logger.info(f"Received S3 key for analysis: {s3_key}")
    s3_handler = S3Handler()
    
    # Job ID가 없으면 생성
    if not job_id:
        job_id = str(uuid.uuid4())
    
    try:
        # Job 시작 상태 설정
        await set_job_status(job_id, JobStatus.PROCESSING, 0, "분석 시작")
        
        # s3_key에서 정보 파싱
        try:
            # "team12/interview_audio/{user_id}/{question_num}/{filename}"
            parts = s3_key.split('/')
            user_id = parts[2]
            question_num = int(parts[3])
            filename = parts[4]
            logger.info(f"Parsed info: user_id={user_id}, question_num={question_num}, filename={filename}")
        except (IndexError, ValueError) as e:
            error_msg = f"Failed to parse S3 key '{s3_key}'. Error: {e}"
            logger.error(error_msg, exc_info=True)
            await set_job_status(job_id, JobStatus.FAILED, 0, "S3 키 파싱 실패", error_msg)
            return

        # 분석을 위한 임시 작업 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            try:
                # 1. S3에서 파일 다운로드 (10% 진행률)
                await set_job_status(job_id, JobStatus.PROCESSING, 10, "S3에서 파일 다운로드 중")
                logger.info(f"Downloading {s3_key} from S3 to {temp_dir_path}...")
                local_audio_path = await s3_handler.download_file(s3_key, str(temp_dir_path))
                
                if not local_audio_path:
                    error_msg = f"Failed to download file from S3 for key: {s3_key}"
                    logger.error(error_msg)
                    await set_job_status(job_id, JobStatus.FAILED, 10, "S3 다운로드 실패", error_msg)
                    return
                
                logger.info(f"File downloaded successfully to: {local_audio_path}")
                
                # 2. 분석기 초기화 (30% 진행률)
                await set_job_status(job_id, JobStatus.PROCESSING, 30, "분석기 초기화 중")
                logger.info("Initializing EnglishAnalyzer...")
                analyzer = EnglishAnalyzer(
                    user_id=user_id, 
                    question_num=question_num, 
                    base_path=str(temp_dir_path)
                )
                
                # 3. 분석 실행 (50% 진행률)
                await set_job_status(job_id, JobStatus.PROCESSING, 50, "영어 분석 처리 중")
                logger.info(f"Starting analysis for {local_audio_path}...")
                await analyzer.analyze(local_audio_path)
                
                # 4. 분석 완료 (90% 진행률)
                await set_job_status(job_id, JobStatus.PROCESSING, 90, "분석 완료, 결과 저장 중")
                
                # 5. 결과 데이터 구성 (실제 분석 결과를 가져와야 함)
                result_data = {
                    "user_id": user_id,
                    "question_num": question_num,
                    "s3_key": s3_key,
                    "analysis_completed": True,
                    "completed_at": datetime.now().isoformat(),
                    "message": "영어 분석이 성공적으로 완료되었습니다."
                }
                
                # 6. 결과 저장 및 완료 처리 (100% 진행률)
                await set_job_result(job_id, result_data)
                await set_job_status(job_id, JobStatus.COMPLETED, 100, "분석 완료")
                
                logger.info(f"Successfully completed analysis for S3 key: {s3_key}, Job ID: {job_id}")

            except Exception as e:
                error_msg = f"An error occurred during the analysis for S3 key '{s3_key}'. Error: {e}"
                logger.error(error_msg, exc_info=True)
                await set_job_status(job_id, JobStatus.FAILED, 0, "분석 중 오류 발생", error_msg)
            finally:
                logger.info(f"Cleaning up temporary directory: {temp_dir_path}")
                # 'with' 구문이 끝나면 temp_dir은 자동으로 삭제됩니다.
    
    except Exception as e:
        error_msg = f"Critical error in analysis job {job_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        await set_job_status(job_id, JobStatus.FAILED, 0, "분석 작업 실패", error_msg)

# --- API 엔드포인트 ---
@app.post("/analysis/english")
async def request_english_analysis(
    request: AnalysisPayload,
    background_tasks: BackgroundTasks,
):
    """영어 면접 답변에 대한 분석을 요청하는 엔드포인트 (s3ObjectKey 사용)"""
    logger.info(f"Received english analysis request for S3 key: {request.s3ObjectKey}")
    return await process_english_analysis_from_s3(background_tasks, request.s3ObjectKey)

@app.post("/analysis/english/submit", response_model=JobSubmitResponse, status_code=202)
async def submit_english_analysis_job(
    request: JobSubmitRequest,
    background_tasks: BackgroundTasks
):
    """영어 분석 Job 제출 - 즉시 Job ID 반환"""
    try:
        # Job ID 생성
        job_id = str(uuid.uuid4())
        
        logger.info(f"영어 분석 Job 제출: {job_id}, S3 키: {request.s3ObjectKey}")
        
        # Job 초기 상태 설정
        await set_job_status(job_id, JobStatus.PENDING, 0, "분석 대기 중")
        
        # 백그라운드에서 분석 처리
        background_tasks.add_task(run_analysis_in_background, request.s3ObjectKey, job_id)
        
        return JobSubmitResponse(
            job_id=job_id,
            status=JobStatus.PENDING,
            message="영어 분석 작업이 성공적으로 제출되었습니다.",
            estimated_time=300  # 5분 예상
        )
        
    except Exception as e:
        logger.error(f"영어 분석 Job 제출 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Job 제출 중 오류가 발생했습니다: {str(e)}"
        )

@app.get("/analysis/english/status/{job_id}", response_model=JobStatusResponse)
async def get_english_analysis_job_status(job_id: str):
    """영어 분석 Job 상태 조회"""
    try:
        logger.info(f"영어 분석 Job 상태 조회: {job_id}")
        
        # Job 상태 조회
        job_status_data = await get_job_status(job_id)
        if not job_status_data:
            raise HTTPException(
                status_code=404,
                detail=f"Job ID {job_id}를 찾을 수 없습니다."
            )
        
        # Job 결과 조회 (완료된 경우)
        job_result_data = None
        if job_status_data.get("status") == JobStatus.COMPLETED:
            job_result_data = await get_job_result(job_id)
        
        # 응답 데이터 구성
        response_data = {
            "job_id": job_id,
            "status": job_status_data.get("status", JobStatus.PENDING),
            "progress": job_status_data.get("progress", 0),
            "created_at": datetime.fromisoformat(job_status_data.get("updated_at", datetime.now().isoformat())),
            "updated_at": datetime.fromisoformat(job_status_data.get("updated_at", datetime.now().isoformat()))
        }
        
        # 완료 시간 설정
        if job_status_data.get("status") == JobStatus.COMPLETED and job_result_data:
            if "completed_at" in job_result_data:
                response_data["completed_at"] = datetime.fromisoformat(job_result_data["completed_at"])
            
            # 결과 포함
            if "result" in job_result_data:
                response_data["result"] = job_result_data["result"]
        
        # 오류 메시지 설정
        if job_status_data.get("status") == JobStatus.FAILED:
            response_data["error_message"] = job_status_data.get("error_message", "알 수 없는 오류")
        
        return JobStatusResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"영어 분석 Job 상태 조회 실패: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Job 상태 조회 중 오류가 발생했습니다: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "English Analysis API is running."}

# --- 서버 실행 ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003) 