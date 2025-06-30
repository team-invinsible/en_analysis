# ----------------------------------------------------------------------------------------------------
# 작성목적 : AWS S3와 상호작용하기 위한 유틸리티 클래스
# 작성일 : 2025-06-27

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-27 | 최초 구현 | S3 파일 다운로드 기능 구현 | 구동빈
# ----------------------------------------------------------------------------------------------------

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class S3Handler:
    """AWS S3 버킷과의 상호작용을 관리하는 클래스"""

    def __init__(self, region_name='ap-northeast-2'):
        """
        S3 클라이언트를 초기화합니다.
        환경변수에서 AWS 자격 증명을 자동으로 로드합니다.
        (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        """
        try:
            self.s3_client = boto3.client('s3', region_name=region_name)
            self.bucket_name = os.getenv('S3_BUCKET_NAME', 'skala25a')
            if not self.bucket_name:
                raise ValueError("S3_BUCKET_NAME 환경변수가 설정되지 않았습니다.")
        except (NoCredentialsError, PartialCredentialsError):
            logger.error("AWS 자격 증명을 찾을 수 없습니다. 환경변수를 확인하세요.")
            raise
        except Exception as e:
            logger.error(f"S3 핸들러 초기화 중 오류 발생: {e}")
            raise

    async def download_file(self, s3_key: str, local_dir: str) -> str:
        """
        S3 버킷에서 파일을 다운로드하여 로컬 임시 디렉토리에 저장합니다.

        :param s3_key: 다운로드할 파일의 S3 Object Key
        :param local_dir: 파일을 저장할 로컬 디렉토리 경로
        :return: 다운로드된 파일의 전체 로컬 경로
        """
        file_name = Path(s3_key).name
        local_file_path = os.path.join(local_dir, file_name)

        logger.info(f"'{s3_key}' 파일을 S3에서 다운로드 시작 -> '{local_file_path}'")
        
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_file_path)
            logger.info(f"다운로드 완료: '{local_file_path}'")
            return local_file_path
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.error(f"S3에서 파일을 찾을 수 없습니다: s3://{self.bucket_name}/{s3_key}")
            else:
                logger.error(f"S3 파일 다운로드 중 오류 발생: {e}")
            raise
        except Exception as e:
            logger.error(f"예상치 못한 다운로드 오류: {e}")
            raise

    async def test_connection(self):
        """S3 버킷에 접근하여 연결을 테스트합니다."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 버킷 '{self.bucket_name}'에 성공적으로 연결되었습니다.")
            return True
        except ClientError as e:
            logger.error(f"S3 버킷 '{self.bucket_name}'에 접근할 수 없습니다: {e}")
            return False
        except Exception as e:
            logger.error(f"S3 연결 테스트 중 예상치 못한 오류 발생: {e}")
            return False 