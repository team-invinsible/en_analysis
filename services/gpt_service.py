import openai
import logging
import os
import yaml
import json
from typing import Dict, Optional, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class GPTService:
    """GPT API 서비스 클래스"""
    
    def __init__(self):
        # API 키 설정
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY가 설정되지 않았습니다. GPT 기능이 제한됩니다.")
        
        openai.api_key = api_key
        self.client = openai.OpenAI(api_key=api_key) if api_key else None
        
        # 프롬프트 파일 경로 설정
        self.project_root = Path(__file__).parent.parent
        self.prompts_dir = self.project_root / "prompts"
        self.prompts_dir.mkdir(exist_ok=True)
    
    def _load_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """YAML 프롬프트 파일 로드"""
        prompt_file = self.prompts_dir / f"{prompt_name}.yaml"
        
        if not prompt_file.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_data = yaml.safe_load(f)
        
        return prompt_data
    
    async def generate_answer_summary(self, text_content: str) -> str:
        """답변 요약 생성"""
        try:
            if not self.client:
                return "GPT API가 설정되지 않아 요약을 생성할 수 없습니다."
            
            # 프롬프트 로드
            prompt_data = self._load_prompt("summary")
            prompt = prompt_data["prompt_template"].format(text_content=text_content)
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 영어 면접 답변 분석 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info("답변 요약 생성 완료")
            return summary
            
        except Exception as e:
            logger.error(f"답변 요약 생성 실패: {str(e)}")
            return f"요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    async def analyze_fluency_keywords(self, text_content: str, fluency_scores: Dict) -> Dict[str, str]:
        """영어 유창성 강점/약점 키워드 분석"""
        try:
            if not self.client:
                return {
                    "strength_keywords": "자연스러운 발화, 적절한 속도",
                    "weakness_keywords": "개선 필요"
                }
            
            # 프롬프트 로드
            prompt_data = self._load_prompt("fluency_analysis")
            prompt = prompt_data["prompt_template"].format(
                text_content=text_content,
                pause_score=fluency_scores.get('pause_score', 0),
                speed_score=fluency_scores.get('speed_score', 0),
                f0_score=fluency_scores.get('f0_score', 0),
                duration_score=fluency_scores.get('duration_score', 0),
                stress_accuracy_score=fluency_scores.get('stress_accuracy_score', 0),
                pronunciation_score=fluency_scores.get('pronunciation_raw_score', 0),
                final_score=fluency_scores.get('final_score', 0)
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 영어 유창성 평가 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            try:
                # 먼저 JSON 마커 제거 시도
                json_text = self._extract_json_from_response(result_text)
                result = json.loads(json_text)
                logger.info("영어 유창성 키워드 분석 완료")
                return result
            except json.JSONDecodeError:
                logger.warning(f"GPT 응답을 JSON으로 파싱할 수 없습니다. 응답 내용: {result_text[:200]}...")
                # JSON이 아닌 응답에서 키워드 추출 시도
                return self._extract_keywords_from_text(result_text, "fluency")
            
        except Exception as e:
            logger.error(f"영어 유창성 키워드 분석 실패: {str(e)}")
            return {
                "strength_keywords": "분석 오류",
                "weakness_keywords": "분석 오류"
            }
    
    async def analyze_grammar_keywords(self, text_content: str, cefr_scores: Dict) -> Dict[str, str]:
        """영어 문법 강점/약점 키워드 분석"""
        try:
            if not self.client:
                return {
                    "strength_keywords": "문법 구조, 어휘 사용",
                    "weakness_keywords": "개선 필요"
                }
            
            # 프롬프트 로드
            prompt_data = self._load_prompt("grammar_analysis")
            prompt = prompt_data["prompt_template"].format(
                text_content=text_content,
                content_score=cefr_scores.get('content_score', 0),
                communicative_achievement_score=cefr_scores.get('communicative_achievement_score', 0),
                organisation_score=cefr_scores.get('organisation_score', 0),
                language_score=cefr_scores.get('language_score', 0),
                cefr_level=cefr_scores.get('cefr_level', 'N/A'),
                cefr_score=cefr_scores.get('cefr_score', 0)
            )
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 영어 문법 평가 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            try:
                # 먼저 JSON 마커 제거 시도
                json_text = self._extract_json_from_response(result_text)
                result = json.loads(json_text)
                logger.info("영어 문법 키워드 분석 완료")
                return result
            except json.JSONDecodeError:
                logger.warning(f"GPT 응답을 JSON으로 파싱할 수 없습니다. 응답 내용: {result_text[:200]}...")
                # JSON이 아닌 응답에서 키워드 추출 시도
                return self._extract_keywords_from_text(result_text, "grammar")
            
        except Exception as e:
            logger.error(f"영어 문법 키워드 분석 실패: {str(e)}")
            return {
                "strength_keywords": "분석 오류",
                "weakness_keywords": "분석 오류"
            }

    async def evaluate_cefr(self, text: str) -> Dict:
        """CEFR 기반 영어 문법 평가"""
        try:
            if not self.client:
                return {
                    'content_score': 0,
                    'communicative_achievement_score': 0,
                    'organisation_score': 0,
                    'language_score': 0,
                    'average_score': 0.0,
                    'cefr_level': 'A1',
                    'cefr_score': 0
                }

            # 프롬프트 로드
            prompt_data = self._load_prompt("cefr_evaluation")
            prompt = prompt_data["prompt_template"].format(text=text)

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "당신은 CEFR 평가 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # JSON 파싱
            try:
                # JSON 추출 시도
                json_text = self._extract_json_from_response(result_text)
                result = json.loads(json_text)
                logger.info(f"CEFR 평가 완료: {result.get('cefr_level', 'N/A')}")
                return result
            except json.JSONDecodeError as e:
                logger.warning(f"CEFR 평가 응답을 JSON으로 파싱할 수 없습니다.")
                logger.warning(f"원본 응답: {result_text[:500]}")
                logger.warning(f"추출된 JSON: {json_text[:200]}")
                logger.warning(f"JSON 오류: {str(e)}")
            return {
                    'content_score': 0,
                    'communicative_achievement_score': 0,
                    'organisation_score': 0,
                    'language_score': 0,
                    'average_score': 0.0,
                    'cefr_level': 'A1',
                    'cefr_score': 0
            }
            
        except Exception as e:
            logger.error(f"CEFR 평가 실패: {str(e)}")
            return {
                'content_score': 0,
                'communicative_achievement_score': 0,
                'organisation_score': 0,
                'language_score': 0,
                'average_score': 0.0,
                'cefr_level': 'A1',
                'cefr_score': 0
            }
    
    def _extract_json_from_response(self, text: str) -> str:
        """GPT 응답에서 JSON 부분만 추출하는 헬퍼 함수"""
        import re
        
        try:
            # 1. ```json...``` 패턴 찾기 (정규식 사용)
            json_pattern = r'```json\s*(.*?)\s*```'
            match = re.search(json_pattern, text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
                if json_text:
                    return json_text
            
            # 2. ```...``` 패턴에서 JSON 찾기
            code_pattern = r'```\s*(.*?)\s*```'
            match = re.search(code_pattern, text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
                if json_text.startswith("{") and json_text.endswith("}"):
                    return json_text
            
            # 3. 첫 번째 완전한 JSON 객체 찾기
            brace_count = 0
            start_idx = -1
            for i, char in enumerate(text):
                if char == '{':
                    if start_idx == -1:
                        start_idx = i
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0 and start_idx != -1:
                        json_text = text[start_idx:i+1]
                        return json_text
            
            # 4. 그대로 반환
            return text
            
        except Exception:
            return text
    
    def _extract_keywords_from_text(self, text: str, analysis_type: str) -> Dict[str, str]:
        """텍스트에서 키워드를 추출하는 헬퍼 함수"""
        try:
            # JSON 추출 시도
            json_text = self._extract_json_from_response(text)
            result = json.loads(json_text)
            return result
            
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 기본값 반환
            if analysis_type == "fluency":
                return {
                    "strength_keywords": "자연스러운 발화, 적절한 속도",
                    "weakness_keywords": "발음 정확도, 유창성 향상"
                }
            else:  # grammar
                return {
                    "strength_keywords": "문법 구조, 어휘 선택",
                    "weakness_keywords": "문법 정확성, 표현력 향상"
                }