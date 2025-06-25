import boto3
import os
import logging
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

class S3Service:
    """AWS S3 서비스 클래스"""
    
    def __init__(self):
        # AWS 자격 증명 설정 (환경변수에서 가져오거나 IAM Role 사용)
        self.bucket_name = "skala25a"
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'ap-northeast-2')
            )
            logger.info("S3 클라이언트 초기화 완료")
        except NoCredentialsError:
            logger.error("AWS 자격 증명을 찾을 수 없습니다")
            raise
    
    def download_audio_file(self, user_id: str, question_num: int, local_dir: str = "temp_audio") -> Optional[str]:
        """
        S3에서 음성 파일 다운로드
        
        Args:
            user_id: 사용자 ID
            question_num: 질문 번호 (8 또는 9)
            local_dir: 로컬 저장 디렉토리
            
        Returns:
            다운로드된 파일의 로컬 경로 또는 None
        """
        try:
            # S3 경로 생성
            s3_key = f"team12/interview_audio/{user_id}/{question_num}"
            
            # 로컬 디렉토리 생성
            os.makedirs(local_dir, exist_ok=True)
            
            # S3 객체 목록 가져오기 (파일 확장자를 모르기 때문)
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=s3_key
            )
            
            if 'Contents' not in response:
                logger.warning(f"S3에서 파일을 찾을 수 없습니다: {s3_key}")
                return None
            
            # 첫 번째 일치하는 파일 다운로드
            for obj in response['Contents']:
                s3_file_key = obj['Key']
                file_name = os.path.basename(s3_file_key)
                
                # 빈 파일명 스킵
                if not file_name:
                    continue
                
                local_file_path = os.path.join(local_dir, f"{user_id}_{question_num}_{file_name}")
                
                # 파일 다운로드
                self.s3_client.download_file(
                    self.bucket_name,
                    s3_file_key,
                    local_file_path
                )
                
                logger.info(f"S3 파일 다운로드 완료: {s3_file_key} -> {local_file_path}")
                return local_file_path
            
            logger.warning(f"유효한 파일을 찾을 수 없습니다: {s3_key}")
            return None
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logger.error(f"S3 버킷을 찾을 수 없습니다: {self.bucket_name}")
            elif error_code == 'NoSuchKey':
                logger.error(f"S3 객체를 찾을 수 없습니다: {s3_key}")
            else:
                logger.error(f"S3 다운로드 실패: {str(e)}")
            return None
            
        except Exception as e:
            logger.error(f"예상치 못한 오류 발생: {str(e)}")
            return None
    
    def cleanup_local_file(self, file_path: str):
        """로컬 임시 파일 정리"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"임시 파일 삭제: {file_path}")
        except Exception as e:
            logger.warning(f"임시 파일 삭제 실패: {str(e)}")
    
    def list_user_files(self, user_id: str) -> list:
        """특정 사용자의 모든 오디오 파일 목록 조회"""
        try:
            prefix = f"team12/interview_audio/{user_id}/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    # question_num 추출
                    parts = key.split('/')
                    if len(parts) >= 4:
                        try:
                            question_num = int(parts[3])
                            files.append({
                                'key': key,
                                'question_num': question_num,
                                'size': obj['Size'],
                                'last_modified': obj['LastModified']
                            })
                        except ValueError:
                            # question_num이 숫자가 아닌 경우 스킵
                            continue
            
            return files
            
        except Exception as e:
            logger.error(f"S3 파일 목록 조회 실패: {str(e)}")
            return []
    
    def list_all_users(self) -> list:
        """모든 사용자 ID 목록 조회"""
        try:
            prefix = "team12/interview_audio/"
            
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                Delimiter='/'
            )
            
            users = []
            if 'CommonPrefixes' in response:
                for common_prefix in response['CommonPrefixes']:
                    prefix_path = common_prefix['Prefix']
                    # team12/interview_audio/{user_id}/ 형태에서 user_id 추출
                    parts = prefix_path.rstrip('/').split('/')
                    if len(parts) >= 3:
                        user_id = parts[2]
                        if user_id and user_id not in users:
                            users.append(user_id)
            
            logger.info(f"발견된 사용자 수: {len(users)}명")
            return sorted(users)
            
        except Exception as e:
            logger.error(f"S3 사용자 목록 조회 실패: {str(e)}")
            return []
    
    def get_user_questions(self, user_id: str, question_numbers: list = [8, 9]) -> list:
        """특정 사용자의 지정된 질문 번호에 대한 파일 존재 여부 확인"""
        try:
            available_questions = []
            
            for question_num in question_numbers:
                # 정확한 S3 경로: team12/interview_audio/{user_id}/{question_num} (폴더가 아님)
                prefix = f"team12/interview_audio/{user_id}/{question_num}"
                
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    Prefix=prefix,
                    MaxKeys=1  # 존재 여부만 확인하므로 1개만
                )
                
                if 'Contents' in response and len(response['Contents']) > 0:
                    available_questions.append(question_num)
                    logger.info(f"사용자 {user_id}의 질문 {question_num} 파일 발견")
            
            return available_questions
            
        except Exception as e:
            logger.error(f"S3 사용자 질문 조회 실패: {str(e)}")
            return [] 