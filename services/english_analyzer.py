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
from models.schemas import EvalCategory
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
            # 8, 9번 질문만 처리
            if question_num not in [8, 9]:
                logger.warning(f"영어 분석은 8, 9번 질문만 지원합니다. 입력된 질문 번호: {question_num}")
                return
            
            # 데이터베이스 관리자 초기화
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            print(f"\n🎯 [영어 분석 시작] 사용자: {user_id}, 질문: {question_num}")
            print("=" * 60)
            logger.info(f"사용자 {user_id}, 질문 {question_num} 분석 시작")
            
            # 1. S3에서 오디오 파일 다운로드
            print("📥 단계 1/9: S3에서 음성 파일 다운로드 중...")
            audio_file_path = await self._download_audio_from_s3(user_id, question_num)
            print(f"✅ S3 다운로드 완료: {Path(audio_file_path).name}")
            
            # 2. 오디오 파일 변환 (webm -> wav)
            print("\n🎵 단계 2/9: 음성 파일 형식 변환 (webm → wav)...")
            wav_file_path = await self._convert_audio_to_wav(audio_file_path, user_id, question_num)
            print(f"✅ 파일 변환 완료: {Path(wav_file_path).name}")
            
            # 3. PLSPP MFA 분석 실행
            print("\n🔬 단계 3/9: PLSPP MFA 음성 분석 실행 중...")
            print("   - 음성 세그멘테이션 및 정렬")
            print("   - 발음 특성 추출")
            print("   - CSV 결과 파일 생성")
            await self._run_plspp_analysis(wav_file_path, user_id, question_num)
            print("✅ PLSPP MFA 분석 완료")
            
            # 4. 유창성 평가 실행
            print("\n📊 단계 4/9: 영어 유창성 평가 실행 중...")
            print("   - 말 속도 분석")
            print("   - 휴지 패턴 분석")
            print("   - 강세 정확도 평가")
            print("   - 발음 정확도 평가")
            fluency_scores = await self._run_fluency_evaluation(user_id, question_num)
            print(f"✅ 유창성 평가 완료 (최종 점수: {fluency_scores.get('final_score', 0):.2f}/30)")
            
            # 5. STT 텍스트 추출 및 CEFR 문법 평가
            print("\n🤖 단계 5/9: CEFR 영어 문법 평가 실행 중...")
            print("   - STT 텍스트 분석")
            print("   - 문법 구조 평가")
            print("   - CEFR 레벨 판정")
            cefr_scores = await self._run_cefr_evaluation(user_id, question_num)
            print(f"✅ CEFR 평가 완료 (레벨: {cefr_scores.get('cefr_level', 'N/A')}, 점수: {cefr_scores.get('cefr_score', 0)}/70)")
            
            # 6. STT 텍스트 추출
            print("\n📝 단계 6/9: STT 텍스트 추출 중...")
            text_content = await self._extract_stt_text(user_id, question_num)
            print("✅ STT 텍스트 추출 완료")
            
            # 7. GPT 분석 (요약, 키워드 추출) - 병렬 처리
            print("\n🧠 단계 7/9: GPT 분석 실행 중...")
            ans_summary, fluency_keywords, grammar_keywords = await self._run_gpt_analysis(
                text_content, fluency_scores, cefr_scores
            )
            print("✅ GPT 분석 완료")
            
            # 8. 새로운 테이블 구조로 저장
            print("\n💾 단계 8/9: 새 테이블 구조로 결과 저장 중...")
            await self._save_to_new_tables(user_id, question_num, ans_summary, 
                                          fluency_scores, cefr_scores, 
                                          fluency_keywords, grammar_keywords)
            print("✅ 새 테이블 구조 저장 완료")
            
            # 9. MongoDB에 상세 결과 저장
            print("\n🗃️ 단계 9/9: MongoDB에 상세 분석 결과 저장 중...")
            await self._save_to_mongodb(user_id, question_num, fluency_scores, cefr_scores, 
                                      text_content, ans_summary, fluency_keywords, grammar_keywords)
            print("✅ MongoDB 저장 완료")
            
            # 임시 파일 정리
            await self._cleanup_temp_files(user_id, question_num)
            
            print("\n" + "=" * 60)
            print(f"🎉 [분석 완료] 사용자 {user_id}, 질문 {question_num} 분석이 성공적으로 완료되었습니다!")
            print(f"📈 영어 유창성 점수: {fluency_scores.get('final_score', 0):.2f}/30")
            print(f"📝 영어 문법 점수: {cefr_scores.get('cefr_score', 0)}/70")
            print(f"🏆 총점: {fluency_scores.get('final_score', 0) + cefr_scores.get('cefr_score', 0)}/100")
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
            
            # 이미 WAV 파일인 경우 표준화된 이름으로 심볼릭 링크 생성
            if audio_file_path.lower().endswith('.wav'):
                converted_file = audio_file_path
                print(f"   ✅ WAV 파일 원본 사용 (복사 안함)")
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
        """PLSPP MFA 분석 실행 (최적화된 버전)"""
        try:
            script_path = self.plspp_dir / "plspp_mfa.sh"
            
            print(f"   - 스크립트 경로: {script_path}")
            print(f"   - 작업 디렉터리: {self.plspp_dir}")
            
            # 기본 환경 변수 사용
            env = os.environ.copy()
            
            # 기존 CSV 파일들 삭제 (매번 새로 분석)
            csv_files = [
                self.plspp_dir / "stressTable.csv",
                self.plspp_dir / "pauseTable.csv", 
                self.plspp_dir / "speakers.csv",
                self.plspp_dir / "nbWords_perSpeaker.csv"
            ]
            
            for csv_file in csv_files:
                if csv_file.exists():
                    csv_file.unlink()
                    print(f"   🗑️ 기존 CSV 파일 삭제: {csv_file.name}")
            
            # plspp/audio 폴더 안의 모든 파일들만 삭제 (폴더는 유지)
            audio_dir = self.plspp_dir / "audio"
            if audio_dir.exists():
                import glob
                audio_files = glob.glob(str(audio_dir / "*"))
                for audio_file in audio_files:
                    try:
                        os.remove(audio_file)
                        print(f"   🗑️ 기존 오디오 파일 삭제: {os.path.basename(audio_file)}")
                    except Exception as e:
                        print(f"   ⚠️ 파일 삭제 실패: {audio_file} - {e}")
                if audio_files:
                    print(f"   🗑️ audio 폴더 내 파일들 삭제 완료 ({len(audio_files)}개 파일)")
            
            print("   🔄 새로운 PLSPP 분석 시작")
            
            # MFA 분석 실행
            print(f"   - 실행 명령: cd '{self.plspp_dir}' && bash plspp_mfa.sh")
            
            process = await asyncio.create_subprocess_shell(
                f"cd '{self.plspp_dir}' && bash plspp_mfa.sh",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print("   ✅ PLSPP MFA 스크립트 실행 성공")
                logger.info("PLSPP MFA 분석 완료")
            else:
                error_output = stderr.decode('utf-8', errors='ignore')
                print(f"   ⚠️ PLSPP MFA 스크립트 실행 경고: {process.returncode}")
                if error_output:
                    print(f"   오류 상세: {error_output[:200]}...")  # 처음 200자만 표시
                logger.warning(f"PLSPP MFA 실행 경고: {process.returncode}")
            
        except Exception as e:
            print(f"   ❌ PLSPP MFA 분석 실패: {str(e)}")
            logger.error(f"PLSPP MFA 분석 실패: {str(e)}")
            raise
    
    async def _run_optimized_mfa_only(self, wav_file_path: str, user_id: str, question_num: int):
        """MFA만 실행하는 경량화된 버전 (실험적)"""
        try:
            # 필요한 경우에만 사용할 수 있는 경량화 버전
            import subprocess
            
            audio_dir = self.plspp_dir / "audio"
            text_dir = self.plspp_dir / "text" 
            tgmfa_dir = self.plspp_dir / "tgmfa"
            
            # 디렉터리 생성
            for dir_path in [audio_dir, text_dir, tgmfa_dir]:
                dir_path.mkdir(exist_ok=True)
            
            # 간단한 텍스트 파일 생성 (STT 결과가 있다면 활용)
            text_file = text_dir / f"{user_id}_{question_num}.txt"
            if not text_file.exists():
                # 기본 텍스트 또는 STT 결과 사용
                with open(text_file, 'w') as f:
                    f.write("Hello world this is a test")
            
            # MFA만 실행 (최적화된 파라미터)
            cmd = [
                "mfa", "align",
                str(audio_dir), "english_us_arpa", "english_us_arpa", str(tgmfa_dir),
                "--clean", "--num_jobs", "4", "--beam", "10"
            ]
            
            env = os.environ.copy()
            env.update({
                'MKL_NUM_THREADS': '4',
                'OMP_NUM_THREADS': '4'
            })
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("   ✅ 경량화된 MFA 분석 완료")
                return True
            else:
                print(f"   ❌ 경량화된 MFA 실패: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ 경량화된 MFA 분석 오류: {str(e)}")
            return False
    
    async def _run_fluency_evaluation(self, user_id: str, question_num: int) -> Dict:
        """유창성 평가 실행 - 특정 사용자/질문에 대해서만"""
        try:
            print(f"   - 유창성 평가 시작 (사용자 {user_id}, 질문 {question_num})")
            
            # FluencyEvaluator를 직접 import하고 사용
            from fluency_evaluator import FluencyEvaluator
            
            # 평가 시스템 초기화
            evaluator = FluencyEvaluator()
            
            # 특정 사용자/질문에 해당하는 화자만 평가
            result = evaluator.evaluate_specific_speaker(user_id, question_num, verbose=True)
            
            if result and result.get('final_score', 0) > 0:
                fluency_scores = {
                    'pause_score': result.get('pause_score', 0),
                    'speed_score': result.get('speed_score', 0),
                    'f0_score': result.get('f0_score', 0),
                    'duration_score': result.get('duration_score', 0),
                    'stress_accuracy_score': result.get('stress_accuracy_score', 0),
                    'pronunciation_raw_score': result.get('pronunciation_raw_score', 0),
                    'final_score': result.get('final_score', 0)
                }
                matched_speaker = result.get('matched_speaker_id', 'unknown')
                print(f"   ✅ 유창성 평가 완료: {fluency_scores['final_score']}/30점 (화자: {matched_speaker})")
                logger.info(f"유창성 평가 완료: 사용자 {user_id}, 질문 {question_num}, 화자 {matched_speaker}")
                return fluency_scores
            else:
                print(f"   ⚠️ 사용자 {user_id}, 질문 {question_num}에 대한 유창성 데이터가 없습니다")
                logger.warning(f"유창성 평가 데이터 없음: 사용자 {user_id}, 질문 {question_num}")
            
            # 데이터 없음 - 0점 반환
            return {
                'pause_score': 0.0,
                'speed_score': 0.0,
                'f0_score': 0.0,
                'duration_score': 0.0,
                'stress_accuracy_score': 0.0,
                'pronunciation_raw_score': 0.0,
                'final_score': 0.0
            }
            
        except Exception as e:
            print(f"   ❌ 유창성 평가 실패: {str(e)}")
            logger.error(f"유창성 평가 실패: {str(e)}")
            # 분석 실패 - 0점 반환
            return {
                'pause_score': 0.0,
                'speed_score': 0.0,
                'f0_score': 0.0,
                'duration_score': 0.0,
                'stress_accuracy_score': 0.0,
                'pronunciation_raw_score': 0.0,
                'final_score': 0.0
            }
    
    async def _run_cefr_evaluation(self, user_id: str, question_num: int) -> Dict:
        """CEFR 평가 실행"""
        try:
            # {user_id}_{question_num} 패턴으로 시작하는 모든 텍스트 파일 찾기
            import glob
            pattern = str(self.text_dir / f"{user_id}_{question_num}*.txt")
            matching_files = glob.glob(pattern)
            
            text_file = None
            if matching_files:
                # 가장 첫 번째 매칭 파일 사용
                text_file = Path(matching_files[0])
                print(f"   📄 텍스트 파일 발견: {text_file.name}")
            else:
                # 기본 텍스트 파일 사용
                text_file = self.text_dir / "2_8_en_j.txt"
                print(f"   ⚠️ 기본 텍스트 파일 사용: {text_file.name}")
                
            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    text_content = f.read().strip()
                
                # GPT로 CEFR 평가
                cefr_result = await self.gpt_service.evaluate_cefr(text_content)
                print(f"   ✅ CEFR 평가 완료: {cefr_result.get('cefr_level', 'N/A')}")
                return cefr_result
            else:
                logger.warning("STT 텍스트 파일을 찾을 수 없습니다.")
                
        except Exception as e:
            print(f"   ❌ CEFR 평가 실패: {str(e)}")
            logger.error(f"CEFR 평가 실패: {str(e)}")
        
        # 데이터 없음 - 0점 반환
        return {
            'content_score': 0,
            'communicative_achievement_score': 0,
            'organisation_score': 0,
            'language_score': 0,
            'average_score': 0.0,
            'cefr_level': 'A1',
            'cefr_score': 0
        }
    
    async def _extract_stt_text(self, user_id: str, question_num: int) -> str:
        """STT 텍스트 추출"""
        try:
            # {user_id}_{question_num} 패턴으로 시작하는 모든 텍스트 파일 찾기
            import glob
            pattern = str(self.text_dir / f"{user_id}_{question_num}*.txt")
            matching_files = glob.glob(pattern)
            
            text_file = None
            if matching_files:
                # 가장 첫 번째 매칭 파일 사용
                text_file = Path(matching_files[0])
            else:
                # 기본 텍스트 파일 사용
                text_file = self.text_dir / "2_8_en_j.txt"
                
            if text_file.exists():
                with open(text_file, 'r', encoding='utf-8') as f:
                    text_content = f.read().strip()
                return text_content
            else:
                logger.warning("STT 텍스트 파일을 찾을 수 없습니다.")
                return "텍스트를 찾을 수 없습니다."
                
        except Exception as e:
            logger.error(f"STT 텍스트 추출 실패: {str(e)}")
            return "텍스트 추출 중 오류가 발생했습니다."
    
    async def _run_gpt_analysis(self, text_content: str, fluency_scores: Dict, cefr_scores: Dict) -> tuple:
        """GPT 분석 실행 (요약, 키워드 추출) - 병렬 처리"""
        try:
            print("   - GPT 분석 병렬 실행 중...")
            
            # 모든 GPT 호출을 동시에 실행
            tasks = [
                self.gpt_service.generate_answer_summary(text_content),
                self.gpt_service.analyze_fluency_keywords(text_content, fluency_scores),
                self.gpt_service.analyze_grammar_keywords(text_content, cefr_scores)
            ]
            
            # 병렬 실행 후 결과 수집
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            ans_summary = results[0] if not isinstance(results[0], Exception) else "분석 실패"
            fluency_keywords = results[1] if not isinstance(results[1], Exception) else {"strength_keywords": "오류", "weakness_keywords": "오류"}
            grammar_keywords = results[2] if not isinstance(results[2], Exception) else {"strength_keywords": "오류", "weakness_keywords": "오류"}
            
            print("   ✅ GPT 분석 병렬 처리 완료")
            return ans_summary, fluency_keywords, grammar_keywords
            
        except Exception as e:
            logger.error(f"GPT 분석 실패: {str(e)}")
            return "분석 실패", {"strength_keywords": "오류", "weakness_keywords": "오류"}, {"strength_keywords": "오류", "weakness_keywords": "오류"}
    
    async def _save_to_new_tables(self, user_id: str, question_num: int, ans_summary: str,
                                 fluency_scores: Dict, cefr_scores: Dict, 
                                 fluency_keywords: Dict, grammar_keywords: Dict):
        """새로운 테이블 구조로 저장"""
        try:
            # 1. answer_score 테이블에 저장
            await self.db_manager.save_answer_score(user_id, question_num, ans_summary)
            
            # 2. answer_category_result 테이블에 영어 유창성 결과 저장
            await self.db_manager.save_answer_category_result(
                user_id, question_num, 
                EvalCategory.ENGLISH_FLUENCY,
                fluency_scores.get('final_score', 0),
                fluency_keywords.get('strength_keywords', ''),
                fluency_keywords.get('weakness_keywords', '')
            )
            
            # 3. answer_category_result 테이블에 영어 문법 결과 저장
            await self.db_manager.save_answer_category_result(
                user_id, question_num,
                EvalCategory.ENGLISH_GRAMMAR,
                cefr_scores.get('cefr_score', 0),
                grammar_keywords.get('strength_keywords', ''),
                grammar_keywords.get('weakness_keywords', '')
            )
            
            logger.info(f"새 테이블 구조 저장 완료: 사용자 {user_id}, 질문 {question_num}")
            
        except Exception as e:
            logger.error(f"새 테이블 구조 저장 실패: {str(e)}")
            raise
    
    async def _save_to_mongodb(self, user_id: str, question_num: int, fluency_scores: Dict, cefr_scores: Dict,
                              text_content: str, ans_summary: str, fluency_keywords: Dict, grammar_keywords: Dict):
        """MongoDB에 상세 결과 저장"""
        try:
            # 총점 계산 (유창성 30점 + 문법 70점)
            total_score = fluency_scores.get('final_score', 0) + cefr_scores.get('cefr_score', 0)
            
            analysis_data = {
                "userId": user_id,
                "question_num": question_num,
                "pause_score": fluency_scores.get('pause_score', 0),
                "speed_score": fluency_scores.get('speed_score', 0),
                "f0_score": fluency_scores.get('f0_score', 0),
                "duration_score": fluency_scores.get('duration_score', 0),
                "stress_accuracy_score": fluency_scores.get('stress_accuracy_score', 0),
                "pronunciation_raw_score": fluency_scores.get('pronunciation_raw_score', 0),
                "final_score": fluency_scores.get('final_score', 0),
                "content_score": cefr_scores.get('content_score', 0),
                "communicative_achievement_score": cefr_scores.get('communicative_achievement_score', 0),
                "organisation_score": cefr_scores.get('organisation_score', 0),
                "language_score": cefr_scores.get('language_score', 0),
                "average_score": cefr_scores.get('average_score', 0),
                "cefr_level": cefr_scores.get('cefr_level', 'B1'),
                "cefr_score": cefr_scores.get('cefr_score', 0),
                "total_score": total_score,
                "text_content": text_content,
                "ans_summary": ans_summary,
                "fluency_keywords": fluency_keywords,
                "grammar_keywords": grammar_keywords
            }
            
            await self.db_manager.save_to_mongodb(analysis_data)
            logger.info(f"MongoDB 저장 완료: 사용자 {user_id}, 질문 {question_num}")
            
        except Exception as e:
            logger.error(f"MongoDB 저장 실패: {str(e)}")
            raise
    
    async def _cleanup_temp_files(self, user_id: str, question_num: int):
        """임시 파일 정리"""
        try:
            # 결과 JSON 파일 삭제
            result_file = self.project_root / f"fluency_evaluation_results_{user_id}_{question_num}.json"
            if result_file.exists():
                result_file.unlink()
                
            logger.info("임시 파일 정리 완료")
            
        except Exception as e:
            logger.warning(f"임시 파일 정리 실패: {str(e)}")
    
    async def get_analysis_result(self, user_id: str, question_num: int) -> Optional[Dict]:
        """분석 결과 조회"""
        try:
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            result = await self.db_manager.get_from_mongodb(user_id, question_num)
            return result
            
        except Exception as e:
            logger.error(f"분석 결과 조회 실패: {str(e)}")
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
    
    async def prepare_audio_file(self, user_id: str, question_num: int):
        """오디오 파일 다운로드 및 변환"""
        try:
            # 1. S3에서 오디오 파일 다운로드
            audio_file_path = await self._download_audio_from_s3(user_id, question_num)
            
            # 2. 오디오 파일 변환 (webm -> wav)
            wav_file_path = await self._convert_audio_to_wav(audio_file_path, user_id, question_num)
            
            logger.info(f"오디오 파일 준비 완료: {user_id}_{question_num}")
            
        except Exception as e:
            logger.error(f"오디오 파일 준비 실패: {user_id}_{question_num} - {str(e)}")
            raise
    
    async def run_batch_plspp_analysis(self):
        """모든 오디오 파일에 대해 PLSPP MFA 배치 분석"""
        try:
            print("   - 모든 오디오 파일에 대한 PLSPP MFA 분석 시작")
            print("   - 음성 세그멘테이션 및 정렬")
            print("   - 발음 특성 추출")
            print("   - CSV 결과 파일 생성")
            
            # 기존 CSV 파일들 삭제
            csv_files = [
                self.plspp_dir / "stressTable.csv",
                self.plspp_dir / "pauseTable.csv", 
                self.plspp_dir / "speakers.csv",
                self.plspp_dir / "nbWords_perSpeaker.csv"
            ]
            
            for csv_file in csv_files:
                if csv_file.exists():
                    csv_file.unlink()
                    print(f"   🗑️ 기존 CSV 파일 삭제: {csv_file.name}")
            
            
            
            # 기본 환경 변수 사용
            env = os.environ.copy()
            
            # PLSPP MFA 스크립트 실행 (출력 스트림 변경)
            print(f"   - 스크립트 경로: {self.plspp_dir / 'plspp_mfa.sh'}")
            print(f"   - 작업 디렉터리: {self.plspp_dir}")
            print(f"   - 실행 명령: cd '{self.plspp_dir}' && bash plspp_mfa.sh")
            
            # 출력을 터미널로 직접 보내기 (파이프 대신)
            process = await asyncio.create_subprocess_shell(
                f"cd '{self.plspp_dir}' && bash plspp_mfa.sh",
                stdout=None,  # 터미널로 직접 출력
                stderr=None,  # 터미널로 직접 출력
                env=env
            )
            
            # 프로세스 완료까지 대기
            await process.wait()
            
            if process.returncode == 0:
                print("   ✅ PLSPP MFA 배치 분석 성공")
                logger.info("PLSPP MFA 배치 분석 완료")
                
                # CSV 파일이 실제로 생성되었는지 확인
                csv_files = [
                    self.plspp_dir / "stressTable.csv",
                    self.plspp_dir / "pauseTable.csv", 
                    self.plspp_dir / "speakers.csv",
                    self.plspp_dir / "nbWords_perSpeaker.csv"
                ]
                
                missing_files = [f for f in csv_files if not f.exists()]
                if missing_files:
                    logger.warning(f"일부 CSV 파일이 생성되지 않음: {[f.name for f in missing_files]}")
                else:
                    print("   ✅ 모든 CSV 파일 생성 확인")
                    
            else:
                logger.error(f"PLSPP MFA 배치 분석 실패: {process.returncode}")
                raise Exception(f"PLSPP MFA 배치 분석 실패: {process.returncode}")
                
        except Exception as e:
            logger.error(f"PLSPP MFA 배치 분석 실패: {str(e)}")
            raise
    
    async def analyze_individual_result(self, user_id: str, question_num: int):
        """개별 사용자/질문에 대한 분석 및 저장"""
        try:
            # 데이터베이스 관리자 초기화
            if self.db_manager is None:
                self.db_manager = await get_db_manager()
            
            # 4. 유창성 평가 실행 (CSV 데이터 기반)
            fluency_scores = await self._run_fluency_evaluation(user_id, question_num)
            
            # 5. STT 텍스트 추출 및 CEFR 문법 평가
            cefr_scores = await self._run_cefr_evaluation(user_id, question_num)
            
            # 6. STT 텍스트 추출
            text_content = await self._extract_stt_text(user_id, question_num)
            
            # 7. GPT 분석 (요약, 키워드 추출)
            ans_summary, fluency_keywords, grammar_keywords = await self._run_gpt_analysis(
                text_content, fluency_scores, cefr_scores
            )
            
            # 8. 새로운 테이블 구조로 저장
            await self._save_to_new_tables(user_id, question_num, ans_summary, 
                                          fluency_scores, cefr_scores, 
                                          fluency_keywords, grammar_keywords)
            
            # 9. MongoDB에 상세 결과 저장
            await self._save_to_mongodb(user_id, question_num, fluency_scores, cefr_scores, 
                                      text_content, ans_summary, fluency_keywords, grammar_keywords)
            
            # 총점 계산
            total_score = fluency_scores.get('final_score', 0) + cefr_scores.get('cefr_score', 0)
            print(f"     ✅ 완료 - 유창성: {fluency_scores.get('final_score', 0)}/30, "
                  f"문법: {cefr_scores.get('cefr_score', 0)}/70, 총점: {total_score}/100")
            
            logger.info(f"개별 분석 완료: 사용자 {user_id}, 질문 {question_num}")
            
        except Exception as e:
            logger.error(f"개별 분석 실패: 사용자 {user_id}, 질문 {question_num} - {str(e)}")
            raise 