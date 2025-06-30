# ----------------------------------------------------------------------------------------------------
# 작성목적 : 영어(English) 분석 모의 서버
# 작성일 : 2025-06-25

# 변경사항 내역 (날짜 | 변경목적 | 변경내용 | 작성자 순으로 기입)
# 2025-06-25 | 최초 구현 | 영어 분석 API 요청을 수신하는 모의 서버 구현 | 구동빈
# ----------------------------------------------------------------------------------------------------

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

# --- Pydantic 모델 정의 ---
class AnalysisPayload(BaseModel):
    """모의 분석 서버가 수신할 요청 본문 모델"""
    s3ObjectKey: str

# --- FastAPI 애플리케이션 생성 ---
app = FastAPI()

# --- API 엔드포인트 정의 ---
@app.post("/analyze/english")
async def analyze_english(payload: AnalysisPayload):
    """
    AI-Interview 서버로부터 영어 능력 분석 요청을 받아 처리하는 엔드포인트입니다.
    수신한 s3ObjectKey를 출력하고, 성공 응답을 반환합니다.
    """
    print(f"Received English analysis request for s3ObjectKey: {payload.s3ObjectKey}")
    
    # 실제 분석 로직이 여기 들어갈 수 있습니다.
    return {
        "resultCode": "0000",
        "resultMessage": "English analysis request received and processing started.",
        "s3ObjectKey": payload.s3ObjectKey
    }

# --- 서버 실행 ---
if __name__ == "__main__":
    """
    터미널에서 `python scripts/mock_en_analysis_server.py` 명령으로 실행합니다.
    """
    uvicorn.run(app, host="0.0.0.0", port=8003) 