#!/usr/bin/env python3
"""
영어 유창성 분석 실행 스크립트

사용법:
    python run_analysis.py --user_id test_user --question_num 8
    python run_analysis.py --user_id test_user --question_num 9
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 파이썬 패스에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.english_analyzer import EnglishAnalyzer
from services.s3_service import S3Service

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def analyze_single_task(user_id: str, question_num: int, task_num: int, total_tasks: int):
    """단일 분석 작업 실행"""
    print(f"\n🔄 [{task_num}/{total_tasks}] 사용자 {user_id}, 질문 {question_num} 분석 시작...")
    
    analyzer = EnglishAnalyzer()
    try:
        await analyzer.analyze_audio_async(user_id, question_num)
        print(f"✅ [{task_num}/{total_tasks}] 사용자 {user_id}, 질문 {question_num} 분석 완료!")
    except Exception as e:
        print(f"❌ [{task_num}/{total_tasks}] 사용자 {user_id}, 질문 {question_num} 분석 실패: {str(e)}")

async def main():
    """메인 실행 함수 - 배치 처리 최적화"""
    try:
        print("\n🚀 영어 분석 스크립트 시작 (배치 처리 모드)")
        print(f"   작업 디렉터리: {Path.cwd()}")
        
        # S3 서비스 초기화
        s3_service = S3Service()
        
        # S3에서 사용자 목록 가져오기
        print("   📋 S3에서 모든 사용자 목록 가져오는 중...")
        users = s3_service.list_all_users()
        print(f"   발견된 사용자: {len(users)}명 - {', '.join(map(str, users))}")
        
        # 분석할 질문 번호
        questions = [8, 9]
        print(f"   분석할 질문 번호: {', '.join(map(str, questions))}")
        
        # 분석 작업 목록 생성
        task_details = []
        
        for user_id in users:
            # 사용자가 가진 질문 파일들 확인
            available_questions = s3_service.get_user_questions(user_id, questions)
            for question_num in available_questions:
                task_details.append((user_id, question_num))
        
        if not task_details:
            print("   ⚠️ 분석할 파일이 없습니다.")
            return
        
        print(f"\n📊 총 {len(task_details)}개의 분석 작업을 배치 처리합니다:")
        for i, (user_id, question_num) in enumerate(task_details, 1):
            print(f"   {i}. 사용자 {user_id}, 질문 {question_num}")
        
        # 영어 분석기 초기화
        analyzer = EnglishAnalyzer()
        
        # 1단계: 모든 오디오 파일 다운로드 및 변환
        print(f"\n🔄 1단계: 모든 오디오 파일 다운로드 및 변환 중...")
        for i, (user_id, question_num) in enumerate(task_details, 1):
            print(f"   [{i}/{len(task_details)}] 사용자 {user_id}, 질문 {question_num} 파일 준비 중...")
            await analyzer.prepare_audio_file(user_id, question_num)
        
        # 2단계: PLSPP MFA 배치 분석 (한 번만 실행)
        print(f"\n🔬 2단계: PLSPP MFA 배치 분석 실행 중...")
        await analyzer.run_batch_plspp_analysis()
        
        # 3단계: 각 사용자/질문별 개별 분석 및 저장
        print(f"\n📊 3단계: 개별 분석 및 데이터베이스 저장 중...")
        for i, (user_id, question_num) in enumerate(task_details, 1):
            print(f"   [{i}/{len(task_details)}] 사용자 {user_id}, 질문 {question_num} 분석 중...")
            await analyzer.analyze_individual_result(user_id, question_num)
        
        print(f"\n🎉 모든 분석 작업이 완료되었습니다! (총 {len(task_details)}개)")
        
    except Exception as e:
        print(f"\n❌ 분석 실행 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main()) 