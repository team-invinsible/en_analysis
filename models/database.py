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
                'database': os.getenv("MARIADB_DATABASE", "english_analysis"),
                'charset': 'utf8mb4'
            }
            
            # 연결 테스트
            connection = pymysql.connect(**db_config)
            
            # en_score 테이블 생성 (존재하지 않는 경우)
            with connection.cursor() as cursor:
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS en_score (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    userId VARCHAR(255) NOT NULL,
                    question_num INT NOT NULL,
                    total_score INT NOT NULL,
                    fluency_score FLOAT NOT NULL,
                    cefr_score INT NOT NULL,
                    total_comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_question (userId, question_num)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """
                cursor.execute(create_table_sql)
                connection.commit()
                
                # 기존 테이블에 total_comment 컬럼이 없는 경우 추가
                try:
                    alter_table_sql = """
                    ALTER TABLE en_score 
                    ADD COLUMN total_comment TEXT
                    """
                    cursor.execute(alter_table_sql)
                    connection.commit()
                    logger.info("total_comment 컬럼 추가 완료")
                except pymysql.err.OperationalError as e:
                    if "Duplicate column name" in str(e):
                        logger.debug("total_comment 컬럼이 이미 존재합니다")
                    else:
                        raise
            
            connection.close()
            
            # 연결 풀은 실제 사용할 때 생성
            self.maria_config = db_config
            
            logger.info("MariaDB 연결 및 테이블 설정 완료")
            
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
    
    async def save_to_mariadb(self, user_id: str, question_num: int, total_score: int, fluency_score: float, cefr_score: int, total_comment: str = ""):
        """MariaDB에 최종 점수 저장"""
        try:
            connection = pymysql.connect(**self.maria_config)
            
            with connection.cursor() as cursor:
                # INSERT ON DUPLICATE KEY UPDATE 사용
                sql = """
                INSERT INTO en_score (userId, question_num, total_score, fluency_score, cefr_score, total_comment)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                total_score = VALUES(total_score),
                fluency_score = VALUES(fluency_score),
                cefr_score = VALUES(cefr_score),
                total_comment = VALUES(total_comment),
                updated_at = CURRENT_TIMESTAMP
                """
                
                cursor.execute(sql, (user_id, question_num, total_score, fluency_score, cefr_score, total_comment))
                connection.commit()
            
            connection.close()
            
            logger.info(f"MariaDB 저장 완료: userId={user_id}, question_num={question_num}, total_score={total_score}")
            
        except Exception as e:
            logger.error(f"MariaDB 저장 실패: {str(e)}")
            raise
    
    async def get_from_mariadb(self, user_id: str, question_num: int) -> Optional[dict]:
        """MariaDB에서 점수 조회"""
        try:
            connection = pymysql.connect(**self.maria_config)
            
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                sql = "SELECT * FROM en_score WHERE userId = %s AND question_num = %s"
                cursor.execute(sql, (user_id, question_num))
                result = cursor.fetchone()
            
            connection.close()
            return result
            
        except Exception as e:
            logger.error(f"MariaDB 조회 실패: {str(e)}")
            raise
    
    async def close_connections(self):
        """데이터베이스 연결 종료"""
        if self.mongo_client:
            self.mongo_client.close()
        logger.info("데이터베이스 연결 종료")

# 전역 데이터베이스 관리자 인스턴스
db_manager = DatabaseManager()

async def init_databases():
    """데이터베이스 초기화"""
    await db_manager.init_mongodb()
    await db_manager.init_mariadb()

async def get_db_manager() -> DatabaseManager:
    """데이터베이스 관리자 인스턴스 반환"""
    # 데이터베이스가 초기화되지 않았다면 초기화
    if db_manager.mongo_client is None:
        await db_manager.init_mongodb()
    if not hasattr(db_manager, 'maria_config') or db_manager.maria_config is None:
        await db_manager.init_mariadb()
    return db_manager 