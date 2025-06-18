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

# .env 파일 로드
load_dotenv()

# 프로젝트 루트를 파이썬 패스에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.english_analyzer import EnglishAnalyzer
from services.s3_service import S3Service
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    parser = argparse.ArgumentParser(description='영어 유창성 분석 실행')
    parser.add_argument('--user_id', help='사용자 ID (미입력시 모든 사용자 분석)')
    parser.add_argument('--question_num', type=int, choices=[8, 9], 
                      help='질문 번호 (8 또는 9만 가능, 미입력시 8,9번 모두 분석)')
    
    args = parser.parse_args()
    
    # 필수 환경 변수 확인
    required_env_vars = [
        'MARIADB_HOST',
        'MARIADB_USER', 
        'MARIADB_PASSWORD',
        'MARIADB_DATABASE',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'OPENAI_API_KEY'
    ]
    
    # MongoDB URI 체크 (MONGODB_URI 또는 MONGODB_URL 중 하나만 있으면 됨)
    if not (os.getenv('MONGODB_URI') or os.getenv('MONGODB_URL')):
        required_env_vars.append('MONGODB_URI')
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ 다음 환경 변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
        print("   .env 파일을 확인해주세요.")
        return 1
    
    try:
        print(f"\n🚀 영어 분석 스크립트 시작")
        print(f"   작업 디렉터리: {os.getcwd()}")
        
        # 분석기 및 S3 서비스 생성
        analyzer = EnglishAnalyzer()
        s3_service = S3Service()
        
        # 사용자 목록 결정
        if args.user_id:
            user_ids = [args.user_id]
            print(f"   지정된 사용자 ID: {args.user_id}")
        else:
            print("   📋 S3에서 모든 사용자 목록 가져오는 중...")
            user_ids = s3_service.list_all_users()
            if not user_ids:
                print("   ❌ S3에서 사용자를 찾을 수 없습니다.")
                return 1
            print(f"   발견된 사용자: {len(user_ids)}명 - {', '.join(user_ids)}")
        
        # 질문 번호 결정
        if args.question_num:
            question_nums = [args.question_num]
            print(f"   지정된 질문 번호: {args.question_num}")
        else:
            question_nums = [8, 9]
            print(f"   분석할 질문 번호: {', '.join(map(str, question_nums))}")
        
        # 전체 분석 작업 목록 생성
        analysis_tasks = []
        for user_id in user_ids:
            available_questions = s3_service.get_user_questions(user_id, question_nums)
            for question_num in available_questions:
                analysis_tasks.append((user_id, question_num))
        
        if not analysis_tasks:
            print("   ❌ 분석할 데이터를 찾을 수 없습니다.")
            return 1
        
        print(f"\n📊 총 {len(analysis_tasks)}개의 분석 작업을 시작합니다:")
        for i, (user_id, question_num) in enumerate(analysis_tasks, 1):
            print(f"   {i}. 사용자 {user_id}, 질문 {question_num}")
        
        # 순차적으로 분석 실행
        successful_count = 0
        failed_count = 0
        
        for i, (user_id, question_num) in enumerate(analysis_tasks, 1):
            print(f"\n🔄 [{i}/{len(analysis_tasks)}] 사용자 {user_id}, 질문 {question_num} 분석 시작...")
            
            try:
                await analyzer.analyze_audio_async(user_id, question_num)
                successful_count += 1
                print(f"✅ [{i}/{len(analysis_tasks)}] 완료: 사용자 {user_id}, 질문 {question_num}")
                
            except Exception as e:
                failed_count += 1
                print(f"❌ [{i}/{len(analysis_tasks)}] 실패: 사용자 {user_id}, 질문 {question_num} - {str(e)}")
                # 개별 실패는 로그만 남기고 계속 진행
                continue
        
        # 최종 결과 요약
        print(f"\n{'='*60}")
        print(f"🎉 전체 분석 완료!")
        print(f"   성공: {successful_count}개")
        print(f"   실패: {failed_count}개")
        print(f"   총계: {len(analysis_tasks)}개")
        print(f"{'='*60}")
        
        return 0 if failed_count == 0 else 1
        
    except KeyboardInterrupt:
        print("\n⏹️  사용자에 의해 중단되었습니다.")
        return 1
        
    except Exception as e:
        print(f"\n❌ 분석 중 오류가 발생했습니다: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 