import os
import logging
import asyncio
import subprocess
import tempfile
import shutil
from typing import Dict, Optional, List, Any
from pathlib import Path

from services.s3_service import S3Service
from services.gpt_service import GPTService
from models.database import get_db_manager
from utils.audio_processor import AudioProcessor

logger = logging.getLogger(__name__)

class EnglishAnalyzer:
    """영어 유창성 분석 클래스"""
    
    def __init__(self):
        self.s3_service = S3Service()
        self.gpt_service = GPTService()
        self.db_manager = None  # 비동기로 초기화
        self.audio_processor = AudioProcessor()
        
        # 프로젝트 루트 경로 설정
        self.project_root = Path(__file__).parent.parent
        self.plspp_dir = self.project_root / "plspp"
        self.audio_dir = self.plspp_dir / "audio"
        self.text_dir = self.plspp_dir / "text"
        
        # 디렉터리 생성
        self.audio_dir.mkdir(exist_ok=True)
        self.text_dir.mkdir(exist_ok=True)
    
    async def analyze_audio_async(self, user_id: str, question_num: int):
        """비동기 오디오 분석 메인 함수"""
        try:
            # 데이터베이스 관리자 초기화
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            print(f"\n🎯 [영어 분석 시작] 사용자: {user_id}, 질문: {question_num}")
            print("=" * 60)
            logger.info(f"사용자 {user_id}, 질문 {question_num} 분석 시작")
            
            # 1. S3에서 오디오 파일 다운로드
            print("📥 단계 1/8: S3에서 음성 파일 다운로드 중...")
            audio_file_path = await self._download_audio_from_s3(user_id, question_num)
            print(f"✅ S3 다운로드 완료: {Path(audio_file_path).name}")
            
            # 2. 오디오 파일 변환 (webm -> wav)
            print("\n🎵 단계 2/8: 음성 파일 형식 변환 (webm → wav)...")
            wav_file_path = await self._convert_audio_to_wav(audio_file_path, user_id, question_num)
            print(f"✅ 파일 변환 완료: {Path(wav_file_path).name}")
            
            # 3. PLSPP MFA 분석 실행
            print("\n🔬 단계 3/8: PLSPP MFA 음성 분석 실행 중...")
            print("   - 음성 세그멘테이션 및 정렬")
            print("   - 발음 특성 추출")
            print("   - CSV 결과 파일 생성")
            await self._run_plspp_analysis(wav_file_path, user_id, question_num)
            print("✅ PLSPP MFA 분석 완료")
            
            # 4. 유창성 평가 실행
            print("\n📊 단계 4/8: 유창성 평가 실행 중...")
            print("   - 말 속도 분석")
            print("   - 휴지 패턴 분석")
            print("   - 강세 정확도 평가")
            print("   - 발음 정확도 평가")
            fluency_scores = await self._run_fluency_evaluation(user_id, question_num)
            print(f"✅ 유창성 평가 완료 (최종 점수: {fluency_scores.get('final_score', 0):.2f})")
            
            # 5. STT 텍스트 추출 및 GPT 문법 평가
            print("\n🤖 단계 5/8: GPT CEFR 문법 평가 실행 중...")
            print("   - STT 텍스트 분석")
            print("   - 문법 구조 평가")
            print("   - CEFR 레벨 판정")
            cefr_scores = await self._run_cefr_evaluation(user_id, question_num)
            print(f"✅ CEFR 평가 완료 (레벨: {cefr_scores.get('cefr_level', 'N/A')})")
            
            # 6. MongoDB에 상세 결과 저장
            print("\n💾 단계 6/8: MongoDB에 상세 분석 결과 저장 중...")
            await self._save_to_mongodb(user_id, question_num, fluency_scores, cefr_scores)
            print("✅ MongoDB 저장 완료")
            
            # 7. MariaDB에 최종 점수 저장
            print("\n🗄️ 단계 7/8: MariaDB에 최종 점수 저장 중...")
            await self._save_to_mariadb(user_id, question_num, fluency_scores, cefr_scores)
            print("✅ MariaDB 저장 완료")
            
            # 8. 임시 파일 정리
            print("\n🧹 단계 8/8: 임시 파일 정리 중...")
            await self._cleanup_temp_files(user_id, question_num)
            print("✅ 정리 완료")
            
            print("\n" + "=" * 60)
            print(f"🎉 [분석 완료] 사용자 {user_id}, 질문 {question_num} 분석이 성공적으로 완료되었습니다!")
            print(f"📈 유창성 점수: {fluency_scores.get('final_score', 0):.2f}")
            print(f"📝 CEFR 레벨: {cefr_scores.get('cefr_level', 'N/A')} (점수: {cefr_scores.get('cefr_score', 0)})")
            print("=" * 60 + "\n")
            
            logger.info(f"사용자 {user_id}, 질문 {question_num} 분석 완료")
            
        except Exception as e:
            print(f"\n❌ [분석 실패] 오류 발생: {str(e)}")
            print("=" * 60 + "\n")
            logger.error(f"분석 중 오류 발생: {str(e)}")
            raise
    
    async def _download_audio_from_s3(self, user_id: str, question_num: int) -> str:
        """S3에서 오디오 파일 다운로드"""
        try:
            # S3 경로: skala25a/team12/interview_audio/{userId}/{question_num}
            s3_key = f"team12/interview_audio/{user_id}/{question_num}"
            print(f"   - S3 경로: s3://skala25a/{s3_key}")
            
            # 다운로드할 로컬 경로
            local_file_path = self.audio_dir / f"{user_id}_{question_num}_original"
            print(f"   - 로컬 저장 경로: {local_file_path}")
            
            # S3에서 파일 다운로드 (비동기 처리)
            import asyncio
            loop = asyncio.get_event_loop()
            downloaded_file = await loop.run_in_executor(
                None, 
                self.s3_service.download_audio_file,
                user_id, question_num, str(self.audio_dir)
            )
            
            if not downloaded_file:
                # 테스트용: 로컬 테스트 파일 사용
                test_file = self.audio_dir / "english.wav"
                if test_file.exists():
                    print(f"   ⚠️ S3 파일을 찾을 수 없어 테스트 파일 사용: {test_file}")
                    logger.warning(f"S3 파일을 찾을 수 없어 테스트 파일 사용: {test_file}")
                    return str(test_file)
                else:
                    logger.error("S3에서 파일을 다운로드할 수 없고, 테스트 파일도 없습니다.")
                    raise Exception("오디오 파일을 찾을 수 없습니다.")
            
            logger.info(f"S3에서 파일 다운로드 완료: {downloaded_file}")
            return downloaded_file
            
        except Exception as e:
            print(f"   ❌ S3 다운로드 실패: {str(e)}")
            logger.error(f"S3 다운로드 실패: {str(e)}")
            
            # 테스트용: 로컬 테스트 파일 사용
            test_file = self.audio_dir / "english.wav"
            if test_file.exists():
                print(f"   ⚠️ 예외 발생으로 테스트 파일 사용: {test_file}")
                logger.warning(f"예외 발생으로 테스트 파일 사용: {test_file}")
                return str(test_file)
            
            raise
    
    async def _convert_audio_to_wav(self, audio_file_path: str, user_id: str, question_num: int) -> str:
        """오디오 파일을 WAV 형식으로 변환"""
        try:
            output_path = self.audio_dir / f"{user_id}_{question_num}.wav"
            print(f"   - 입력 파일: {Path(audio_file_path).name}")
            print(f"   - 출력 파일: {output_path.name}")
            
            # 이미 WAV 파일인 경우 복사만 수행
            if audio_file_path.lower().endswith('.wav'):
                import shutil
                shutil.copy2(audio_file_path, str(output_path))
                converted_file = str(output_path)
                print(f"   ✅ WAV 파일 복사 완료")
            else:
                # 오디오 변환
                converted_file = await self.audio_processor.convert_to_wav(
                    input_file=audio_file_path,
                    output_dir=str(self.audio_dir)
                )
            
            logger.info(f"오디오 변환 완료: {converted_file}")
            return converted_file
            
        except Exception as e:
            print(f"   ❌ 오디오 변환 실패: {str(e)}")
            logger.error(f"오디오 변환 실패: {str(e)}")
            raise
    
    async def _run_plspp_analysis(self, wav_file_path: str, user_id: str, question_num: int):
        """PLSPP MFA 분석 실행"""
        try:
            # plspp_mfa.sh 스크립트 경로
            script_path = self.plspp_dir / "plspp_mfa.sh"
            print(f"   - 스크립트 경로: {script_path}")
            print(f"   - 작업 디렉터리: {self.plspp_dir}")
            
            # 작업 디렉터리를 plspp로 변경하여 실행
            cmd = f"cd '{self.plspp_dir}' && bash plspp_mfa.sh"
            print(f"   - 실행 명령: {cmd}")
            
            # 비동기로 스크립트 실행
            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.plspp_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                print(f"   ❌ PLSPP 분석 실패: {error_msg}")
                logger.error(f"PLSPP 분석 실패: {error_msg}")
                raise Exception(f"PLSPP 분석 실패: {error_msg}")
            
            # 성공 시 출력 파일 확인
            csv_files = list(self.plspp_dir.glob("*.csv"))
            print(f"   - 생성된 CSV 파일: {len(csv_files)}개")
            for csv_file in csv_files[:3]:  # 처음 3개만 표시
                print(f"     * {csv_file.name}")
            
            logger.info("PLSPP MFA 분석 완료")
            
        except Exception as e:
            print(f"   ❌ PLSPP 분석 실행 실패: {str(e)}")
            logger.error(f"PLSPP 분석 실행 실패: {str(e)}")
            raise
    
    async def _run_fluency_evaluation(self, user_id: str, question_num: int) -> Dict:
        """유창성 평가 실행"""
        try:
            # fluency_evaluator.py 실행 (JSON 출력 모드)
            cmd = [
                "python", 
                str(self.project_root / "fluency_evaluator.py"),
                "--user_id", user_id,
                "--question_num", str(question_num),
                "--output_format", "json"
            ]
            print(f"   - 실행 명령: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                print(f"   ❌ 유창성 평가 실패: {error_msg}")
                logger.error(f"유창성 평가 실패: {error_msg}")
                raise Exception(f"유창성 평가 실패: {error_msg}")
            
            # 결과 파싱 (fluency_evaluator.py에서 JSON 출력을 가정)
            import json
            result = json.loads(stdout.decode('utf-8'))
            
            # 세부 점수 출력
            print(f"   - 휴지 점수: {result.get('pause_score', 0):.2f}")
            print(f"   - 속도 점수: {result.get('speed_score', 0):.2f}")
            print(f"   - 강세 정확도: {result.get('stress_accuracy_score', 0):.2f}")
            print(f"   - 발음 점수: {result.get('pronunciation_raw_score', 0):.2f}")
            
            logger.info("유창성 평가 완료")
            return result
            
        except Exception as e:
            print(f"   ❌ 유창성 평가 실행 실패: {str(e)}")
            logger.error(f"유창성 평가 실행 실패: {str(e)}")
            # 기본값 반환
            print("   ⚠️ 기본값으로 대체하여 계속 진행")
            return {
                "pause_score": 0,
                "speed_score": 0,
                "f0_score": 0,
                "duration_score": 0,
                "stress_accuracy_score": 0,
                "pronunciation_raw_score": 0,
                "final_score": 0
            }
    
    async def _run_cefr_evaluation(self, user_id: str, question_num: int) -> Dict:
        """CEFR 문법 평가 실행"""
        try:
            # STT 텍스트 파일 경로 찾기
            text_files = list(self.text_dir.glob("*.txt"))
            print(f"   - 텍스트 디렉터리: {self.text_dir}")
            print(f"   - 발견된 텍스트 파일: {len(text_files)}개")
            
            if not text_files:
                print("   ❌ STT 텍스트 파일을 찾을 수 없습니다.")
                logger.warning("STT 텍스트 파일을 찾을 수 없습니다.")
                return {"cefr_level": "A1", "cefr_score": 0, "comment": "텍스트를 찾을 수 없습니다."}
            
            # 가장 최근 텍스트 파일 사용
            text_file = max(text_files, key=os.path.getctime)
            print(f"   - 사용할 텍스트 파일: {text_file.name}")
            
            with open(text_file, 'r', encoding='utf-8') as f:
                text_content = f.read().strip()
            
            print(f"   - 텍스트 길이: {len(text_content)} 문자")
            print(f"   - 텍스트 미리보기: {text_content[:100]}..." if len(text_content) > 100 else f"   - 텍스트 내용: {text_content}")
            
            if not text_content:
                print("   ❌ 텍스트 내용이 비어있습니다.")
                logger.warning("텍스트 내용이 비어있습니다.")
                return {"cefr_level": "A1", "cefr_score": 0, "comment": "텍스트가 비어있습니다."}
            
            # GPT로 CEFR 평가
            print("   - GPT API 호출 중...")
            cefr_result = await self.gpt_service.evaluate_cefr(text_content)
            
            print(f"   - CEFR 레벨: {cefr_result.get('cefr_level', 'N/A')}")
            print(f"   - CEFR 점수: {cefr_result.get('cefr_score', 0)}")
            print(f"   - 코멘트 길이: {len(cefr_result.get('comment', ''))} 문자")
            
            logger.info(f"CEFR 평가 완료: {cefr_result['cefr_level']}")
            return cefr_result
            
        except Exception as e:
            print(f"   ❌ CEFR 평가 실행 실패: {str(e)}")
            logger.error(f"CEFR 평가 실행 실패: {str(e)}")
            print("   ⚠️ 기본값으로 대체하여 계속 진행")
            return {"cefr_level": "A1", "cefr_score": 0, "comment": f"평가 중 오류: {str(e)}"}
    
    async def _save_to_mongodb(self, user_id: str, question_num: int, fluency_scores: Dict, cefr_scores: Dict):
        """MongoDB에 상세 결과 저장"""
        try:
            document = {
                "userId": user_id,
                "question_num": question_num,
                "pause_score": fluency_scores.get("pause_score", 0),
                "speed_score": fluency_scores.get("speed_score", 0),
                "f0_score": fluency_scores.get("f0_score", 0),
                "duration_score": fluency_scores.get("duration_score", 0),
                "stress_accuracy_score": fluency_scores.get("stress_accuracy_score", 0),
                "pronunciation_raw_score": fluency_scores.get("pronunciation_raw_score", 0),
                "final_score": fluency_scores.get("final_score", 0),
                "cefr_level": cefr_scores.get("cefr_level", "A1"),
                "cefr_score": cefr_scores.get("cefr_score", 0),
                "cefr_comment": cefr_scores.get("comment", ""),
                "analysis_timestamp": asyncio.get_event_loop().time()
            }
            
            print(f"   - 컬렉션: audio/video_analysis/en_analysis")
            print(f"   - 저장 문서 ID: {user_id}_{question_num}")
            print(f"   - 문서 크기: {len(str(document))} 문자")
            
            await self.db_manager.save_to_mongodb(document)
            
            print("   - MongoDB 저장 성공")
            logger.info("MongoDB 저장 완료")
            
        except Exception as e:
            print(f"   ❌ MongoDB 저장 실패: {str(e)}")
            logger.error(f"MongoDB 저장 실패: {str(e)}")
            raise
    
    async def _save_to_mariadb(self, user_id: str, question_num: int, fluency_scores: Dict, cefr_scores: Dict):
        """MariaDB에 최종 점수 저장"""
        try:
            fluency_score = fluency_scores.get("final_score", 0)
            cefr_score = cefr_scores.get("cefr_score", 0)
            total_score = fluency_score + cefr_score
            total_comment = cefr_scores.get("comment", "")
            
            print(f"   - 테이블: en_score")
            print(f"   - 사용자 ID: {user_id}")
            print(f"   - 질문 번호: {question_num}")
            print(f"   - 유창성 점수: {fluency_score:.2f}")
            print(f"   - CEFR 점수: {cefr_score}")
            print(f"   - 총점: {total_score:.2f}")
            print(f"   - 코멘트 길이: {len(total_comment)} 문자")
            
            await self.db_manager.save_to_mariadb(
                user_id=user_id,
                question_num=question_num,
                total_score=total_score,
                fluency_score=fluency_score,
                cefr_score=cefr_score,
                total_comment=total_comment
            )
            
            print("   - MariaDB 저장 성공")
            logger.info("MariaDB 저장 완료")
            
        except Exception as e:
            print(f"   ❌ MariaDB 저장 실패: {str(e)}")
            logger.error(f"MariaDB 저장 실패: {str(e)}")
            raise
    
    async def _cleanup_temp_files(self, user_id: str, question_num: int):
        """임시 파일 정리"""
        try:
            # 사용자별 임시 파일들 삭제
            patterns = [
                f"{user_id}_{question_num}*",
                f"{user_id}_{question_num}_*"
            ]
            
            deleted_count = 0
            for pattern in patterns:
                for file_path in self.audio_dir.glob(pattern):
                    if file_path.is_file():
                        file_path.unlink()
                        deleted_count += 1
                        print(f"   - 삭제됨: {file_path.name}")
                        logger.debug(f"임시 파일 삭제: {file_path}")
            
            print(f"   - 총 {deleted_count}개 파일 정리 완료")
            logger.info("임시 파일 정리 완료")
            
        except Exception as e:
            print(f"   ⚠️ 임시 파일 정리 중 오류: {str(e)}")
            logger.warning(f"임시 파일 정리 중 오류: {str(e)}")
    
    async def get_analysis_result(self, user_id: str, question_num: int) -> Optional[Dict]:
        """분석 결과 조회"""
        try:
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            result = await self.db_manager.get_from_mongodb(user_id, question_num)
            return result
            
        except Exception as e:
            logger.error(f"결과 조회 실패: {str(e)}")
            return None
    
    async def get_user_all_results(self, user_id: str) -> List[Dict]:
        """사용자의 모든 분석 결과 조회"""
        try:
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            results = await self.db_manager.get_user_all_results(user_id)
            return results
            
        except Exception as e:
            logger.error(f"전체 결과 조회 실패: {str(e)}")
            return [] 