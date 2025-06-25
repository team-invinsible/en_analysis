import subprocess
import os
import logging
from typing import Optional
import tempfile
import shutil

logger = logging.getLogger(__name__)

class AudioProcessor:
    """오디오 파일 처리 클래스"""
    
    def __init__(self):
        # FFmpeg 경로 확인
        self.ffmpeg_path = self._find_ffmpeg()
        if not self.ffmpeg_path:
            logger.warning("FFmpeg을 찾을 수 없습니다. webm -> wav 변환이 제한될 수 있습니다.")
    
    def _find_ffmpeg(self) -> Optional[str]:
        """시스템에서 FFmpeg 실행 파일 경로 찾기"""
        possible_paths = [
            'ffmpeg',  # PATH에 있는 경우
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg'  # macOS Homebrew
        ]
        
        for path in possible_paths:
            if shutil.which(path):
                return path
        
        return None
    
    async def convert_to_wav(self, input_file: str, output_dir: str) -> Optional[str]:
        """
        오디오 파일을 WAV 형식으로 변환
        
        Args:
            input_file: 입력 파일 경로
            output_dir: 출력 디렉토리
            
        Returns:
            변환된 WAV 파일 경로 또는 None
        """
        try:
            # 이미 WAV 파일인 경우 원본 파일 그대로 사용
            if input_file.lower().endswith('.wav'):
                logger.info(f"WAV 파일 원본 사용: {input_file}")
                return input_file
            
            # FFmpeg이 없는 경우 변환 불가
            if not self.ffmpeg_path:
                logger.error("FFmpeg이 없어 파일 변환을 할 수 없습니다")
                return None
            
            # 출력 파일명 생성
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(output_dir, f"{base_name}.wav")
            
            # FFmpeg 명령어 구성
            cmd = [
                self.ffmpeg_path,
                '-i', input_file,
                '-acodec', 'pcm_s16le',  # 16-bit PCM
                '-ar', '16000',          # 16kHz 샘플링 레이트
                '-ac', '1',              # 모노 채널
                '-y',                    # 기존 파일 덮어쓰기
                output_file
            ]
            
            # FFmpeg 실행
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5분 타임아웃
            )
            
            if result.returncode == 0:
                logger.info(f"오디오 변환 완료: {input_file} -> {output_file}")
                return output_file
            else:
                logger.error(f"FFmpeg 변환 실패: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error("오디오 변환 시간 초과")
            return None
        except Exception as e:
            logger.error(f"오디오 변환 중 오류 발생: {str(e)}")
            return None
    
    def validate_audio_file(self, file_path: str) -> bool:
        """오디오 파일 유효성 검사"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"파일이 존재하지 않습니다: {file_path}")
                return False
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                logger.error(f"파일 크기가 0입니다: {file_path}")
                return False
            
            # 파일 확장자 확인
            valid_extensions = ['.wav', '.mp3', '.m4a', '.webm', '.ogg', '.flac']
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext not in valid_extensions:
                logger.warning(f"지원되지 않는 파일 형식: {file_ext}")
                return False
            
            logger.info(f"오디오 파일 유효성 검사 통과: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"파일 유효성 검사 중 오류: {str(e)}")
            return False
    
    def prepare_audio_for_analysis(self, input_file: str, user_id: str, question_num: int) -> Optional[str]:
        """
        분석을 위한 오디오 파일 준비
        
        Args:
            input_file: 입력 파일 경로
            user_id: 사용자 ID
            question_num: 질문 번호
            
        Returns:
            준비된 WAV 파일 경로 또는 None
        """
        try:
            # 임시 작업 디렉토리 생성
            temp_dir = tempfile.mkdtemp(prefix=f"audio_analysis_{user_id}_{question_num}_")
            
            # 오디오 디렉토리 생성 (plspp 스크립트가 audio/ 디렉토리를 기대함)
            audio_dir = os.path.join(temp_dir, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            
            # 파일 유효성 검사
            if not self.validate_audio_file(input_file):
                return None
            
            # WAV로 변환
            import asyncio
            wav_file = asyncio.run(self.convert_to_wav(input_file, audio_dir))
            
            if not wav_file:
                logger.error("WAV 변환 실패")
                self.cleanup_temp_directory(temp_dir)
                return None
            
            # 파일명을 분석에 적합하게 변경 (speaker 정보 포함)
            final_name = f"{user_id}_q{question_num}.wav"
            final_path = os.path.join(audio_dir, final_name)
            
            if wav_file != final_path:
                shutil.move(wav_file, final_path)
            
            logger.info(f"분석용 오디오 파일 준비 완료: {final_path}")
            return temp_dir  # 작업 디렉토리 반환
            
        except Exception as e:
            logger.error(f"오디오 파일 준비 중 오류: {str(e)}")
            if 'temp_dir' in locals():
                self.cleanup_temp_directory(temp_dir)
            return None
    
    def cleanup_temp_directory(self, temp_dir: str):
        """임시 디렉토리 정리"""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"임시 디렉토리 삭제: {temp_dir}")
        except Exception as e:
            logger.warning(f"임시 디렉토리 삭제 실패: {str(e)}")
    
    def get_audio_duration(self, file_path: str) -> Optional[float]:
        """오디오 파일 길이 확인 (FFprobe 사용)"""
        try:
            if not self.ffmpeg_path:
                return None
            
            # FFprobe 경로 추정
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg', 'ffprobe')
            
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.warning(f"오디오 길이 확인 실패: {result.stderr}")
                return None
                
        except Exception as e:
            logger.warning(f"오디오 길이 확인 중 오류: {str(e)}")
            return None 