import motor.motor_asyncio
import pymysql
import asyncio
from typing import Optional
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    """데이터베이스 연결 관리자"""
    
    def __init__(self):
        # MongoDB 설정
        self.mongo_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self.mongo_db = None
        self.en_analysis_collection = None
        
        # MariaDB 설정
        self.maria_pool = None
        self.maria_config = None
        
    async def init_mongodb(self):
        """MongoDB 연결 초기화"""
        try:
            # MongoDB 연결 문자열 (환경변수에서 가져오거나 기본값 사용)
            mongo_url = os.getenv("MONGODB_URI", os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
            
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            
            # 연결 테스트
            await self.mongo_client.admin.command('ping')
            
            # 데이터베이스 및 컬렉션 설정
            self.mongo_db = self.mongo_client.audio
            self.en_analysis_collection = self.mongo_db.video_analysis.en_analysis
            
            logger.info("MongoDB 연결 성공")
            
        except Exception as e:
            logger.error(f"MongoDB 연결 실패: {str(e)}")
            raise
    
    async def init_mariadb(self):
        """MariaDB 연결 초기화"""
        try:
            # MariaDB 연결 설정 (환경변수에서 가져오거나 기본값 사용)
            db_config = {
                'host': os.getenv("MARIADB_HOST", "localhost"),
                'port': int(os.getenv("MARIADB_PORT", "3306")),
                'user': os.getenv("MARIADB_USER", "root"),
                'password': os.getenv("MARIADB_PASSWORD", ""),
                'database': os.getenv("MARIADB_DATABASE", "audio"),
                'charset': 'utf8mb4'
            }
            
            # 연결 테스트
            connection = pymysql.connect(**db_config)
            
            # 새로운 테이블 구조 생성
            with connection.cursor() as cursor:
                # answer_score 테이블 생성
                create_answer_score_table = """
                CREATE TABLE IF NOT EXISTS answer_score (
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
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                cursor.execute(create_answer_score_table)
                
                # answer_category_result 테이블 생성
                create_answer_category_result_table = """
                CREATE TABLE IF NOT EXISTS answer_category_result (
                    ANS_CAT_RESULT_ID BIGINT PRIMARY KEY NOT NULL,
                    EVAL_CAT_CD VARCHAR(20) NOT NULL,
                    ANS_SCORE_ID BIGINT NOT NULL,
                    ANS_CAT_SCORE DOUBLE NULL,
                    STRENGTH_KEYWORD TEXT NULL,
                    WEAKNESS_KEYWORD TEXT NULL,
                    RGS_DTM TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (ANS_SCORE_ID) REFERENCES answer_score(ANS_SCORE_ID)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                cursor.execute(create_answer_category_result_table)
                
                connection.commit()
                
            connection.close()
            
            # 연결 풀은 실제 사용할 때 생성
            self.maria_config = db_config
            
            logger.info("MariaDB 연결 및 새 테이블 구조 설정 완료")
            
        except Exception as e:
            logger.error(f"MariaDB 연결 실패: {str(e)}")
            raise
    
    async def save_to_mongodb(self, analysis_data: dict):
        """MongoDB에 분석 결과 저장"""
        try:
            # ID 설정 (userId_questionNum 형식)
            document_id = f"{analysis_data['userId']}_{analysis_data['question_num']}"
            analysis_data["_id"] = document_id
            
            # 현재 시간 추가
            analysis_data["analysis_date"] = datetime.utcnow()
            
            logger.debug(f"MongoDB 저장 시도: {document_id}, 데이터 크기: {len(str(analysis_data))} 문자")
            
            result = await self.en_analysis_collection.replace_one(
                {"_id": document_id},
                analysis_data,
                upsert=True
            )
            
            logger.info(f"MongoDB 저장 완료: userId={analysis_data['userId']}, question_num={analysis_data['question_num']}, _id={document_id}")
            return result
            
        except Exception as e:
            logger.error(f"MongoDB 저장 실패: {str(e)}")
            raise
    
    async def save_answer_score(self, user_id: str, question_num: int, ans_summary: str):
        """answer_score 테이블에 저장"""
        try:
            connection = pymysql.connect(**self.maria_config)
            
            # ID 생성: {user_id}0{question_num}
            ans_score_id = int(f"{user_id}0{question_num}")
            intv_ans_id = int(f"{user_id}0{question_num}")
            
            with connection.cursor() as cursor:
                sql = """
                INSERT INTO answer_score (ANS_SCORE_ID, INTV_ANS_ID, ANS_SUMMARY)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                ANS_SUMMARY = VALUES(ANS_SUMMARY),
                UPD_DTM = CURRENT_TIMESTAMP
                """
                
                cursor.execute(sql, (ans_score_id, intv_ans_id, ans_summary))
                connection.commit()
            
            connection.close()
            
            logger.info(f"answer_score 저장 완료: ANS_SCORE_ID={ans_score_id}")
            
        except Exception as e:
            logger.error(f"answer_score 저장 실패: {str(e)}")
            raise
    
    async def save_answer_category_result(self, user_id: str, question_num: int, 
                                        eval_cat_cd: str, score: float, 
                                        strength_keyword: str, weakness_keyword: str):
        """answer_category_result 테이블에 저장"""
        try:
            connection = pymysql.connect(**self.maria_config)
            
            # ID 생성
            ans_cat_result_id = int(f"{user_id}0{question_num}")
            ans_score_id = int(f"{user_id}0{question_num}")
            
            # 카테고리별로 고유한 ID 생성 (영어 유창성: 6, 영어 문법: 7)
            category_suffix = "6" if eval_cat_cd == "ENGLISH_FLUENCY" else "7"
            ans_cat_result_id = int(f"{user_id}0{question_num}{category_suffix}")
            
            with connection.cursor() as cursor:
                sql = """
                INSERT INTO answer_category_result 
                (ANS_CAT_RESULT_ID, EVAL_CAT_CD, ANS_SCORE_ID, ANS_CAT_SCORE, STRENGTH_KEYWORD, WEAKNESS_KEYWORD)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                ANS_CAT_SCORE = VALUES(ANS_CAT_SCORE),
                STRENGTH_KEYWORD = VALUES(STRENGTH_KEYWORD),
                WEAKNESS_KEYWORD = VALUES(WEAKNESS_KEYWORD)
                """
                
                cursor.execute(sql, (ans_cat_result_id, eval_cat_cd, ans_score_id, 
                                   score, strength_keyword, weakness_keyword))
                connection.commit()
            
            connection.close()
            
            logger.info(f"answer_category_result 저장 완료: ANS_CAT_RESULT_ID={ans_cat_result_id}, EVAL_CAT_CD={eval_cat_cd}")
            
        except Exception as e:
            logger.error(f"answer_category_result 저장 실패: {str(e)}")
            raise

    async def get_from_mongodb(self, user_id: str, question_num: int) -> Optional[dict]:
        """MongoDB에서 분석 결과 조회"""
        try:
            result = await self.en_analysis_collection.find_one({
                "userId": user_id,
                "question_num": question_num
            })
            return result
            
        except Exception as e:
            logger.error(f"MongoDB 조회 실패: {str(e)}")
            raise
    
    async def get_user_all_results(self, user_id: str) -> list:
        """특정 사용자의 모든 분석 결과 조회"""
        try:
            cursor = self.en_analysis_collection.find({"userId": user_id})
            results = await cursor.to_list(length=None)
            return results
            
        except Exception as e:
            logger.error(f"MongoDB 전체 결과 조회 실패: {str(e)}")
            raise

    async def close(self):
        """데이터베이스 연결 종료"""
        if self.mongo_client:
            self.mongo_client.close()

# 전역 데이터베이스 관리자 인스턴스
_db_manager = None

async def init_databases():
    """데이터베이스 초기화"""
    global _db_manager
    _db_manager = DatabaseManager()
    await _db_manager.init_mongodb()
    await _db_manager.init_mariadb()

async def get_db_manager() -> DatabaseManager:
    """데이터베이스 관리자 인스턴스 반환"""
    global _db_manager
    if _db_manager is None:
        await init_databases()
    return _db_manager 