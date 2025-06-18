import openai
import os
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class GPTService:
    """OpenAI GPT API 서비스 클래스"""
    
    def __init__(self):
        # OpenAI API 키 설정
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다")
        
        # OpenAI 클라이언트 초기화 (proxies 매개변수 제거)
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # CEFR 점수 매핑
        self.cefr_score_mapping = {
            'C2': 70,
            'C1': 60,
            'B2': 50,
            'B1': 20,
            'A2': 10,
            'A1': 0,
            'A1 or below': 0
        }
        
        logger.info("GPT 서비스 초기화 완료")
    
    async def evaluate_cefr(self, text: str) -> Dict:
        """
        GPT를 사용하여 CEFR 기반 문법 평가 수행
        
        Args:
            text: 평가할 영어 텍스트
            
        Returns:
            평가 결과 딕셔너리
        """
        
        prompt = f"""다음 영어 텍스트를 CEFR(Common European Framework of Reference for Languages) 기준으로 평가해주세요. 4개 카테고리별로 0~5점으로 채점하되, 다음과 같이 점수를 매겨주세요:

- 5점 = CEFR C2 수준
- 4점 = C1 수준
- 3점 = B2 수준
- 2점 = B1 수준
- 1점 = A2 수준
- 0점 = A1 이하 수준

### CEFR 평가 카테고리:

1. **Content** (p.20–21): Is the content relevant, well-developed, and clearly expressed?
2. **Communicative Achievement** (p.12–14, 25): Does the text fulfill its communicative purpose with appropriate tone and register?
3. **Organisation** (p.31): Is the text coherent, logically structured, and well-connected using cohesive devices?
4. **Language** (p.27–29): Does the learner demonstrate control and variety of grammar, vocabulary, and sentence structures? Are there errors that hinder understanding?

---

After scoring, please:

- Provide each score (0–5) and corresponding CEFR level per category
- Calculate the average score across the four categories
- Map the final CEFR level according to this average:

| Average Score | CEFR Level |
|---------------|------------|
| 4.5–5.0       | C2 |
| 4.0–4.4       | C1 |
| 3.0–3.9       | B2 |
| 2.0–2.9       | B1 |
| 1.0–1.9       | A2 |
| 0–0.9         | A1 or below |

---

Text to evaluate:
---
{text}

다음 형식으로 응답해주세요 (한국어로 작성):

**개별 점수:**
- Content: [점수]/5 (CEFR 레벨)
- Communicative Achievement: [점수]/5 (CEFR 레벨)  
- Organisation: [점수]/5 (CEFR 레벨)
- Language: [점수]/5 (CEFR 레벨)

**종합 평가:**
- Average Score: [평균점수]
- Final CEFR Level: [레벨]

**상세 코멘트:**
[면접에서 발화한 내용에 대한 상세한 코멘트를 제공해주세요. 점수를 구체적으로 언급하고 과거형으로 작성해주세요 (300자 내외로 작성)]
"""
        
        try:
            response = await self._call_gpt_api(prompt)
            
            # GPT 응답 파싱
            parsed_result = self._parse_gpt_response(response)
            # 코멘트 추가
            parsed_result['comment'] = self._extract_comment_from_response(response)
            
            logger.info(f"CEFR 평가 완료: {parsed_result['cefr_level']}")
            return parsed_result
            
        except Exception as e:
            logger.error(f"CEFR 평가 실패: {str(e)}")
            # 기본값 반환
            default_result = {
                'content_score': 2,
                'communicative_achievement_score': 2,
                'organisation_score': 2,
                'language_score': 2,
                'average_score': 2.0,
                'cefr_level': 'B1',
                'cefr_score': 20
            }
            default_result['comment'] = f"GPT 평가 실패: {str(e)}"
            return default_result
    
    async def _call_gpt_api(self, prompt: str) -> str:
        """GPT API 호출"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": "당신은 CEFR 평가 전문가입니다. 공식적인 CEFR 기준에 따라 정확하고 상세한 영어 평가를 제공하며, 모든 응답은 한국어로 작성해주세요. 면접에서 발화한 내용에 대한 상세한 코멘트를 제공해주세요. 점수를 구체적으로 언급하고 과거형으로 작성해주세요 (300자 내외로 작성)"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=1000,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT API 호출 실패: {str(e)}")
            raise
    
    def _parse_gpt_response(self, response: str) -> Dict:
        """GPT 응답 파싱"""
        try:
            # 각 점수 추출
            content_match = re.search(r'Content:\s*(\d+)/5', response)
            comm_match = re.search(r'Communicative Achievement:\s*(\d+)/5', response)
            org_match = re.search(r'Organisation:\s*(\d+)/5', response)
            lang_match = re.search(r'Language:\s*(\d+)/5', response)
            
            # 평균 점수 추출
            avg_match = re.search(r'Average Score:\s*([\d.]+)', response)
            
            # CEFR 레벨 추출
            level_match = re.search(r'Final CEFR Level:\s*(C2|C1|B2|B1|A2|A1)', response)
            
            # 점수 추출 또는 기본값 설정
            content_score = int(content_match.group(1)) if content_match else 2
            comm_score = int(comm_match.group(1)) if comm_match else 2
            org_score = int(org_match.group(1)) if org_match else 2
            lang_score = int(lang_match.group(1)) if lang_match else 2
            
            # 평균 계산
            if avg_match:
                average_score = float(avg_match.group(1))
            else:
                average_score = (content_score + comm_score + org_score + lang_score) / 4
            
            # CEFR 레벨 결정
            if level_match:
                cefr_level = level_match.group(1)
            else:
                # 평균 점수로 레벨 결정
                if average_score >= 4.5:
                    cefr_level = 'C2'
                elif average_score >= 4.0:
                    cefr_level = 'C1'
                elif average_score >= 3.0:
                    cefr_level = 'B2'
                elif average_score >= 2.0:
                    cefr_level = 'B1'
                elif average_score >= 1.0:
                    cefr_level = 'A2'
                else:
                    cefr_level = 'A1'
            
            # CEFR 점수 매핑
            cefr_score = self.cefr_score_mapping.get(cefr_level, 20)
            
            return {
                'content_score': content_score,
                'communicative_achievement_score': comm_score,
                'organisation_score': org_score,
                'language_score': lang_score,
                'average_score': round(average_score, 2),
                'cefr_level': cefr_level,
                'cefr_score': cefr_score
            }
            
        except Exception as e:
            logger.error(f"GPT 응답 파싱 실패: {str(e)}")
            # 기본값 반환
            return {
                'content_score': 2,
                'communicative_achievement_score': 2,
                'organisation_score': 2,
                'language_score': 2,
                'average_score': 2.0,
                'cefr_level': 'B1',
                'cefr_score': 20
            }
    
    def _extract_comment_from_response(self, response: str) -> str:
        """GPT 응답에서 코멘트 추출"""
        try:
            # 한국어 상세 코멘트 섹션 찾기
            comment_patterns = [
                r'\*\*상세 코멘트:\*\*(.*?)(?:\n\n|\n$|$)',
                r'상세 코멘트:(.*?)(?:\n\n|\n$|$)',
                r'\*\*Brief Comment:\*\*(.*?)(?:\n\n|\n$|$)',
                r'Brief Comment:(.*?)(?:\n\n|\n$|$)'
            ]
            
            for pattern in comment_patterns:
                comment_match = re.search(pattern, response, re.DOTALL)
                if comment_match:
                    comment = comment_match.group(1).strip()
                    if len(comment) > 10:  # 의미있는 코멘트인지 확인
                        return comment
            
            # 패턴을 찾지 못한 경우 전체 응답에서 마지막 부분 추출
            lines = response.split('\n')
            comment_lines = []
            found_comment_section = False
            
            for line in lines:
                if '코멘트' in line or 'Comment' in line:
                    found_comment_section = True
                    continue
                if found_comment_section and line.strip():
                    comment_lines.append(line.strip())
            
            if comment_lines:
                return ' '.join(comment_lines)
            else:
                return "CEFR 평가가 완료되었습니다."
                
        except Exception as e:
            logger.warning(f"코멘트 추출 실패: {str(e)}")
            return "CEFR 평가가 완료되었습니다."
    
    async def generate_final_comment(self, fluency_score: float, cefr_level: str, total_score: int) -> str:
        """최종 평가 코멘트 생성"""
        
        prompt = f"""Based on the following English fluency assessment results, provide a comprehensive yet concise evaluation comment in Korean:

**Assessment Results:**
- 유창성 점수 (Fluency Score): {fluency_score}/40
- CEFR 등급: {cefr_level}
- 총점: {total_score}/110

Please provide:
1. Overall performance summary
2. Strengths identified
3. Areas for improvement
4. Specific recommendations for English learning

Keep the response under 200 words and write in Korean. Be constructive and encouraging while providing actionable feedback.
"""
        
        try:
            response = await self._call_gpt_api(prompt)
            return response
            
        except Exception as e:
            logger.error(f"코멘트 생성 실패: {str(e)}")
            return f"평가 완료: 유창성 {fluency_score}점, CEFR {cefr_level} 등급, 총점 {total_score}점을 받으셨습니다. 지속적인 연습을 통해 더 나은 결과를 얻으실 수 있습니다." 