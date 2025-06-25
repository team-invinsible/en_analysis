from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class AnalysisRequest(BaseModel):
    """영어 유창성 분석 요청 스키마"""
    user_id: str = Field(..., description="사용자 ID")
    question_num: int = Field(..., description="질문 번호 (8 또는 9만 허용)")

class AnalysisResponse(BaseModel):
    """영어 유창성 분석 응답 스키마"""
    user_id: str
    question_num: int
    status: str
    message: str

class FluencyScores(BaseModel):
    """유창성 점수 모델"""
    pause_score: float = Field(..., description="휴지 패턴 점수")
    speed_score: float = Field(..., description="발화 속도 점수") 
    f0_score: float = Field(..., description="억양 패턴 점수")
    duration_score: float = Field(..., description="음성 지속시간 점수")
    stress_accuracy_score: float = Field(..., description="강세 정확도 점수")
    pronunciation_raw_score: float = Field(..., description="발음 원시 점수")
    final_score: float = Field(..., description="최종 유창성 점수 (30점 만점)")

class CEFRScores(BaseModel):
    """CEFR 평가 점수 모델"""
    content_score: int = Field(..., description="내용 점수 (0-5)")
    communicative_achievement_score: int = Field(..., description="의사소통 성취 점수 (0-5)")
    organisation_score: int = Field(..., description="구성 점수 (0-5)")
    language_score: int = Field(..., description="언어 점수 (0-5)")
    average_score: float = Field(..., description="평균 점수")
    cefr_level: str = Field(..., description="CEFR 등급")
    cefr_score: int = Field(..., description="CEFR 점수 (0-70)")

class AnswerScore(BaseModel):
    """답변 평가 모델"""
    ans_score_id: int = Field(..., description="답변 평가 ID")
    intv_ans_id: int = Field(..., description="면접 답변 ID")
    ans_summary: Optional[str] = Field(None, description="답변 요약")
    eval_comment: Optional[str] = Field(None, description="답변 평가")
    eval_summary: Optional[str] = Field(None, description="전체 평가 요약")
    incomplete_answer: bool = Field(False, description="미완료 여부")
    insufficient_content: bool = Field(False, description="내용 부족 여부")
    suspected_copying: bool = Field(False, description="커닝 의심 여부")
    suspected_impersonation: bool = Field(False, description="대리 시험 의심 여부")

class AnswerCategoryResult(BaseModel):
    """답변 항목별 평가 결과 모델"""
    ans_cat_result_id: int = Field(..., description="답변 항목별 평가 ID")
    eval_cat_cd: str = Field(..., description="평가 항목 코드")
    ans_score_id: int = Field(..., description="답변 평가 ID")
    ans_cat_score: Optional[float] = Field(None, description="항목별 점수")
    strength_keyword: Optional[str] = Field(None, description="강점 키워드")
    weakness_keyword: Optional[str] = Field(None, description="약점 키워드")

class AnalysisResult(BaseModel):
    """분석 결과 종합 모델"""
    user_id: str
    question_num: int
    fluency_scores: FluencyScores
    cefr_scores: CEFRScores
    total_score: int = Field(..., description="총 점수 (fluency + cefr)")
    analysis_date: datetime
    text_content: str = Field(..., description="분석된 텍스트 내용")
    ans_summary: Optional[str] = Field(None, description="답변 요약")
    fluency_keywords: Optional[Dict[str, str]] = Field(None, description="유창성 강점/약점 키워드")
    grammar_keywords: Optional[Dict[str, str]] = Field(None, description="문법 강점/약점 키워드")

class MongoAnalysisDocument(BaseModel):
    """MongoDB 저장용 문서 모델"""
    userId: str
    question_num: int
    pause_score: float
    speed_score: float
    f0_score: float
    duration_score: float
    stress_accuracy_score: float
    pronunciation_raw_score: float
    final_score: float
    content_score: int
    communicative_achievement_score: int
    organisation_score: int
    language_score: int
    average_score: float
    cefr_level: str
    cefr_score: int
    total_score: int
    analysis_date: datetime
    text_content: str
    ans_summary: Optional[str] = None
    fluency_keywords: Optional[Dict[str, str]] = None
    grammar_keywords: Optional[Dict[str, str]] = None

# 평가 카테고리 상수
class EvalCategory:
    ENGLISH_FLUENCY = "ENGLISH_FLUENCY"  # 영어 유창성 (30점 만점)
    ENGLISH_GRAMMAR = "ENGLISH_GRAMMAR"  # 영어 문법 (70점 만점) 