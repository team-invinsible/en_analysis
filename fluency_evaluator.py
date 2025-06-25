import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import glob
import os
import re
import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime

class FluencyEvaluator:
    def __init__(self, plspp_dir="plspp"):
        self.plspp_dir = plspp_dir
        self.stress_data = []
        self.pause_data = []
        self.load_data()
    
    def load_data(self):
        """PLSPP 파이프라인에서 생성된 데이터를 로드합니다."""
        # stressTable.csv 로드
        stress_file = os.path.join(self.plspp_dir, "stressTable.csv")
        if os.path.exists(stress_file):
            with open(stress_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                self.stress_data = list(reader)
        
        # pauseTable.csv 로드  
        pause_file = os.path.join(self.plspp_dir, "pauseTable.csv")
        if os.path.exists(pause_file):
            with open(pause_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                self.pause_data = list(reader)
        


    def get_speaker_ids(self) -> List[str]:
        """데이터에서 모든 화자 ID를 추출합니다."""
        speaker_ids = set()
        
        for row in self.stress_data:
            if 'spk' in row and row['spk']:
                speaker_ids.add(row['spk'])
        
        for row in self.pause_data:
            if 'spk' in row and row['spk']:
                speaker_ids.add(row['spk'])
        
        return sorted(list(speaker_ids))

    def calculate_pause_score(self, speaker_id: str = None):
        """
        Pause 평가 (20% = 20점)
        평균 멈춤 시간 기준:
        - 0.7초 이하: 20점
        - 0.7~1.5초: 10점
        - 1.5초 이상: 5점
        - 멈춤 지속시간 1.5초이상 1번마다 -2점
        """
        # 화자별 데이터 필터링
        pause_data = self.pause_data
        if speaker_id:
            pause_data = [row for row in self.pause_data if row.get('spk') == speaker_id]
        
        if not pause_data:
            return 0
        
        # 0.5초 이상 멈춤만 의미있는 멈춤으로 간주 (기존 1.5초에서 완화)
        significant_pauses = []
        for pause in pause_data:
            try:
                duration = float(pause['duration'])
                if duration >= 0.5:  # 0.5초 이상만 실제 멈춤으로 간주
                    significant_pauses.append(duration)
            except (ValueError, KeyError):
                continue
        
        if not significant_pauses:
            return 20  # 의미있는 멈춤이 없으면 만점
        
        avg_pause = statistics.mean(significant_pauses)
        
        # 기본 점수 계산
        if avg_pause <= 0.7:
            base_score = 20
        elif avg_pause <= 1.5:
            base_score = 10
        else:
            base_score = 5
        
        # 1.5초 이상 멈춤 횟수에 따른 감점 적용
        long_pauses = [p for p in significant_pauses if p >= 1.5]
        penalty = len(long_pauses) * 2  # 1번마다 -2점
        
        final_score = max(0, base_score - penalty)  # 최소 0점
        return final_score
       

    def calculate_speed_score(self, speaker_id: str = None):
        """
        Speed 평가 (20% = 20점)
        1분당 음절수(SPM) 기준:
        - 260 이상: 20점 (원어민 속도급)
        - 230 ~ 259: 17점 (매우 유창)
        - 200 ~ 229: 15점 (유창)
        - 170 ~ 199: 12점 (준수)
        - 140 ~ 169: 10점 (기본 이상)
        - 110 ~ 139: 7점 (느린 편)
        - 100 ~ 109: 5점 (느림)
        - 100 미만: 0점 (매우 느림)
        """
        # 화자별 데이터 필터링
        stress_data = self.stress_data
        if speaker_id:
            stress_data = [row for row in self.stress_data if row.get('spk') == speaker_id]
        
        if not stress_data:
            return 0
        
        try:
            # 실제 발화 시간 계산 (pause 시간 제외, 각 발화 구간의 실제 시간만 합산)
            total_duration_seconds = 0
            for row in stress_data:
                try:
                    start_time = float(row['startTime'])
                    end_time = float(row['endTime'])
                    duration = end_time - start_time
                    total_duration_seconds += duration
                except (ValueError, KeyError):
                    continue
            
            if total_duration_seconds <= 0:
                return 0
            
            total_duration_minutes = total_duration_seconds / 60.0
            
            # 음절 수 계산 (lenSyllxpos 컬럼 사용)
            total_syllables = 0
            for row in stress_data:
                try:
                    syllables = int(row['lenSyllxpos'])
                    total_syllables += syllables
                except (ValueError, KeyError):
                    continue
            
            if total_duration_minutes <= 0:
                return 0
            
            spm = total_syllables / total_duration_minutes
            
            if spm >= 260:
                return 20  # 원어민 속도급
            elif spm >= 230:
                return 17  # 매우 유창
            elif spm >= 200:
                return 15  # 유창
            elif spm >= 170:
                return 12  # 준수
            elif spm >= 140:
                return 10  # 기본 이상
            elif spm >= 110:
                return 7   # 느린 편
            elif spm >= 100:
                return 5   # 느림
            else:
                return 0   # 매우 느림
                
        except (ValueError, KeyError):
            return 0

    def calculate_f0_score(self, speaker_id: str = None):
        """
        F0 평가 (30% = 30점)
        강세 음절 F0 - 비강세 음절 F0 차이를 ST(Semitone) 기준으로 평가:
        - ≤ 0 ST → 0점
        - 0~0.5 ST → 10점
        - 0.5~1.0 ST → 20점
        - ≥ 1.0 ST → 30점
        
        ST 계산 공식: ST = 12 * log2(f1/f2)
        """
        # 화자별 데이터 필터링
        stress_data = self.stress_data
        if speaker_id:
            stress_data = [row for row in self.stress_data if row.get('spk') == speaker_id]
        
        if not stress_data:
            return 0
        
        stressed_f0_values = []
        unstressed_f0_values = []
        
        for row in stress_data:
            try:
                # expectedIsObserved가 1이면 강세를 정확히 발음한 것
                expected_stress_pos = int(row['expectedStressPosition'])
                
                # syllF0 파싱 (리스트 형태로 저장됨)
                f0_values_str = row['syllF0'].strip('[]')
                f0_values = [float(x.strip()) for x in f0_values_str.split(',')]
                
                for i, f0 in enumerate(f0_values):
                    if f0 > 0:  # 0 이상인 값만 사용
                        if i + 1 == expected_stress_pos:  # 강세 음절
                            stressed_f0_values.append(f0)
                        else:  # 비강세 음절
                            unstressed_f0_values.append(f0)
                        
            except (ValueError, KeyError, IndexError):
                continue
        
        if not stressed_f0_values or not unstressed_f0_values:
            return 0
        
        avg_stressed_f0 = statistics.mean(stressed_f0_values)
        avg_unstressed_f0 = statistics.mean(unstressed_f0_values)
        
        # ST(Semitone) 차이 계산: ST = 12 * log2(f1/f2)
        if avg_unstressed_f0 <= 0:
            return 0
        
        st_difference = 12 * math.log2(avg_stressed_f0 / avg_unstressed_f0)
        
        # ST 기준 평가
        if st_difference <= 0:
            return 0   # ≤ 0 ST
        elif st_difference <= 0.5:
            return 10  # 0~0.5 ST
        elif st_difference <= 1.0:
            return 20  # 0.5~1.0 ST
        else:
            return 30  # ≥ 1.0 ST

    def calculate_duration_score(self, speaker_id: str = None):
        """
        Duration 평가 (15% = 15점)
        전체 강세 비교 중 강세 음절이 비강세 음절보다 1.2배 이상 긴 비율 (기존 1.5배에서 완화):
        - 80-100% → 15점
        - 60-80% → 10점
        - 40-60% → 5점
        - 그 이하→ 0점
        """
        # 화자별 데이터 필터링
        stress_data = self.stress_data
        if speaker_id:
            stress_data = [row for row in self.stress_data if row.get('spk') == speaker_id]
        
        if not stress_data:
            return 0
        
        correct_duration_words = 0
        total_words = 0
        
        for row in stress_data: 
            try:
                expected_stress_pos = int(row['expectedStressPosition'])
                
                # sylldur 파싱 (음절별 지속시간)
                dur_values_str = row['sylldur'].strip('[]')
                dur_values = [float(x.strip()) for x in dur_values_str.split(',')]
                
                if len(dur_values) < 2:  # 최소 2음절 이상이어야 비교 가능
                    continue
                
                stressed_dur = dur_values[expected_stress_pos - 1]  # 1-based to 0-based
                
                # 비강세 음절들의 평균 지속시간
                unstressed_durs = []
                for i, dur in enumerate(dur_values):
                    if i + 1 != expected_stress_pos:  # 강세 음절이 아닌 경우
                        unstressed_durs.append(dur)
                
                if unstressed_durs:
                    avg_unstressed_dur = statistics.mean(unstressed_durs)
                    if avg_unstressed_dur > 0:
                        duration_ratio = stressed_dur / avg_unstressed_dur
                        if duration_ratio >= 1.2:  # 1.5배에서 1.2배로 완화
                            correct_duration_words += 1
                
                total_words += 1
                
            except (ValueError, KeyError, IndexError):
                continue
        
        if total_words == 0:
            return 0
        
        correct_percentage = (correct_duration_words / total_words) * 100
        
        # 새로운 평가 기준 적용
        if correct_percentage >= 80:
            return 15  # 80-100%
        elif correct_percentage >= 60:
            return 10  # 60-80%
        elif correct_percentage >= 40:
            return 5   # 40-60%
        else:
            return 0   # 그 이하

    def calculate_stress_accuracy_score(self, speaker_id: str = None):
        """
        StressAccuracy 평가 (15% = 15점)
        정확한 강세 발음 비율:
        - 70% 이상: 15점
        - 55% 이상: 10점
        - 40% 이상: 5점
        - 그 이하: 0점
        """
        # 화자별 데이터 필터링
        stress_data = self.stress_data
        if speaker_id:
            stress_data = [row for row in self.stress_data if row.get('spk') == speaker_id]
        
        if not stress_data:
            return 0
        
        correct_stress = 0
        total_words = 0
        
        for row in stress_data:
            try:
                is_correct = int(row['expectedIsObserved'])
                if is_correct == 1:
                    correct_stress += 1
                total_words += 1
            except (ValueError, KeyError):
                continue
        
        if total_words == 0:
            return 0
        
        accuracy_percentage = (correct_stress / total_words) * 100
        
        if accuracy_percentage >= 70:
            return 15
        elif accuracy_percentage >= 55:
            return 10
        elif accuracy_percentage >= 40:
            return 5
        else:
            return 0

    def convert_model_score_to_bracket(self, raw_score):
        """
        모델 점수를 브라켓 시스템으로 변환
        25 이상 -> 30점 (최우수)
        20 이상 -> 26점 (우수) 
        15 이상 -> 21점 (보통)
        10 이상 -> 15점 (미흡)
        5 이상 -> 10점 (부족)
        0 이상 -> 0점 (미달)
        """
        if raw_score >= 25:
            return 30, "최우수"
        elif raw_score >= 20:
            return 26, "우수"
        elif raw_score >= 15:
            return 21, "보통"
        elif raw_score >= 10:
            return 15, "미흡"
        elif raw_score >= 5:
            return 10, "부족"
        else:
            return 0, "미달"

    def convert_pronunciation_score_to_bracket(self, raw_score):
        """
        발음/유창성 점수를 브라켓 시스템으로 변환
        25 이상 -> 30점 (최우수)
        20 이상 -> 26점 (우수) 
        15 이상 -> 21점 (보통)
        10 이상 -> 15점 (미흡)
        5 이상 -> 10점 (부족)
        0 이상 -> 0점 (미달)
        """
        if raw_score >= 25:
            return 30, "최우수"
        elif raw_score >= 20:
            return 26, "우수"
        elif raw_score >= 15:
            return 21, "보통"
        elif raw_score >= 10:
            return 15, "미흡"
        elif raw_score >= 5:
            return 10, "부족"
        else:
            return 0, "미달"

    def evaluate_speaker(self, speaker_id: str = None):
        """화자별 영어 유창성 평가"""
        # 모델 점수 계산 (고정값 85% -> 30점)
        model_score, model_grade = self.convert_model_score_to_bracket(85)
        
        # 각 영역별 점수 계산
        pause_score = self.calculate_pause_score(speaker_id)
        speed_score = self.calculate_speed_score(speaker_id)
        f0_score = self.calculate_f0_score(speaker_id)
        duration_score = self.calculate_duration_score(speaker_id)
        stress_accuracy_score = self.calculate_stress_accuracy_score(speaker_id)
        
        # 발음/유창성 원점수 (100점 만점)
        pronunciation_raw_score = pause_score + speed_score + f0_score + duration_score + stress_accuracy_score
        
        # 발음/유창성 점수를 30점 만점으로 환산
        pronunciation_30_score = pronunciation_raw_score * 0.3
        
        # 발음/유창성 점수를 브라켓 시스템으로 변환
        pronunciation_final_score, pronunciation_grade = self.convert_pronunciation_score_to_bracket(pronunciation_30_score)
        
        # 최종 점수는 발음/유창성 브라켓 점수만 (30점 만점)
        final_score = pronunciation_final_score
        
        return {
            'speaker_id': speaker_id or 'all',
            'model_score': model_score,
            'model_grade': model_grade,
            'pause_score': pause_score,
            'speed_score': speed_score,
            'f0_score': f0_score,
            'duration_score': duration_score,
            'stress_accuracy_score': stress_accuracy_score,
            'pronunciation_raw_score': pronunciation_raw_score,
            'pronunciation_30_score': pronunciation_30_score,
            'pronunciation_final_score': pronunciation_final_score,
            'pronunciation_grade': pronunciation_grade,
            'final_score': final_score
        }

    def evaluate_all_speakers(self, verbose=True):
        """모든 화자 평가"""
        speaker_ids = self.get_speaker_ids()
        results = []
        
        if verbose:
            print(f"=== 발견된 화자 수: {len(speaker_ids)}명 ===")
            print(f"화자 목록: {', '.join(speaker_ids)}")
        
        for speaker_id in speaker_ids:
            result = self.evaluate_speaker(speaker_id)
            results.append(result)
            
            if verbose:
                print(f"\n=== 화자 {speaker_id} 영어 유창성 평가 결과 ===")
                
                print(f"\n=== 발음/유창성/비언어적 요소 평가 (100점 만점 → 30점 환산) ===")
                print(f"Pause (20%): {result['pause_score']}/20점")
                print(f"Speed (20%): {result['speed_score']}/20점")
                print(f"F0 (30%): {result['f0_score']}/30점")
                print(f"Duration (15%): {result['duration_score']}/15점")
                print(f"StressAccuracy (15%): {result['stress_accuracy_score']}/15점")
                print(f"발음/유창성 원점수: {result['pronunciation_raw_score']}/100점")
                print(f"발음/유창성 환산점수 (×0.3): {result['pronunciation_30_score']:.1f}/30점")
                print(f"발음/유창성 최종점수: {result['pronunciation_30_score']:.1f} → {result['pronunciation_grade']} → {result['pronunciation_final_score']}/30점")
                
                print(f"\n=== 화자 {speaker_id} 최종 점수: {result['final_score']}/30점 ===")
                print("=" * 60)
        
        # 전체 평균 계산
        if results and verbose:
            avg_final_score = sum(r['final_score'] for r in results) / len(results)
            print(f"\n=== 전체 화자 평균 점수: {avg_final_score:.1f}/30점 ===")
        
        return results

    def evaluate_specific_speaker(self, user_id: str, question_num: int, verbose=False):
        """특정 사용자/질문에 해당하는 화자만 평가"""
        speaker_ids = self.get_speaker_ids()
        target_speaker = None
        
        # 1차: 정확한 매치 시도
        exact_match = f"{user_id}_{question_num}"
        if exact_match in speaker_ids:
            target_speaker = exact_match
        
        # 2차: prefix로 시작하는 화자 찾기 (와일드카드 개념)
        if not target_speaker:
            prefix = f"{user_id}_{question_num}"
            for speaker_id in speaker_ids:
                if speaker_id.startswith(prefix):
                    target_speaker = speaker_id
                    break
        
        if target_speaker:
            if verbose:
                print(f"   📊 화자 {target_speaker} 개별 평가 중...")
            result = self.evaluate_speaker(target_speaker)
            result['matched_speaker_id'] = target_speaker
            return result
        else:
            if verbose:
                print(f"   ⚠️ 사용자 {user_id}, 질문 {question_num}에 해당하는 화자를 찾을 수 없습니다")
                print(f"   📋 전체 화자 목록: {', '.join(speaker_ids)}")
            
            # 화자를 찾지 못한 경우 기본값 반환
            return {
                'speaker_id': f"{user_id}_{question_num}",
                'matched_speaker_id': None,
                'pause_score': 0,
                'speed_score': 0,
                'f0_score': 0,
                'duration_score': 0,
                'stress_accuracy_score': 0,
                'pronunciation_raw_score': 0,
                'pronunciation_30_score': 0,
                'pronunciation_final_score': 0,
                'pronunciation_grade': "미달",
                'final_score': 0
            }

    def save_results_to_json(self, results_list: List[Dict], output_file: str = None):
        """
        평가 결과를 DB 저장에 편한 JSON 형식으로 저장합니다.
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"fluency_evaluation_results_{timestamp}.json"
        
        current_time = datetime.now()
        
        # DB 저장에 편한 플랫한 구조로 변환
        db_ready_records = []
        
        for result in results_list:
            record = {
                # 메타 정보
                "evaluation_id": f"eval_{current_time.strftime('%Y%m%d_%H%M%S')}_{result['speaker_id']}",
                "evaluation_timestamp": current_time.isoformat(),
                "evaluation_system": "PLSPP_Integration",
                "evaluation_version": "1.0",
                
                # 화자 정보
                "speaker_id": result['speaker_id'],
                
                # 세부 점수 (100점 만점 기준)
                "pause_score": result['pause_score'],
                "pause_max_score": 20,
                "speed_score": result['speed_score'], 
                "speed_max_score": 20,
                "f0_score": result['f0_score'],
                "f0_max_score": 30,
                "duration_score": result['duration_score'],
                "duration_max_score": 15,
                "stress_accuracy_score": result['stress_accuracy_score'],
                "stress_accuracy_max_score": 15,
                
                # 원점수 및 환산점수
                "pronunciation_raw_score": result['pronunciation_raw_score'],
                "pronunciation_raw_max_score": 100,
                "pronunciation_converted_score": round(result['pronunciation_30_score'], 2),
                "pronunciation_converted_max_score": 30,
                
                # 브라켓 시스템 적용 후 최종 점수
                "final_score": result['pronunciation_final_score'],
                "final_max_score": 30,
                "final_grade": result['pronunciation_grade'],
                
                # 등급 정보 (DB 인덱싱 용이)
                "grade_numeric": self._grade_to_numeric(result['pronunciation_grade'])
            }
            
            db_ready_records.append(record)
        
        # 전체 통계 정보도 별도로 추가
        if len(results_list) > 1:
            avg_score = sum(r['final_score'] for r in results_list) / len(results_list)
            summary_record = {
                "evaluation_id": f"summary_{current_time.strftime('%Y%m%d_%H%M%S')}",
                "evaluation_timestamp": current_time.isoformat(),
                "evaluation_system": "PLSPP_Integration",
                "evaluation_version": "1.0",
                "speaker_id": "SUMMARY",
                "total_speakers": len(results_list),
                "average_score": round(avg_score, 2),
                "max_score": max(r['final_score'] for r in results_list),
                "min_score": min(r['final_score'] for r in results_list),
                "score_range": max(r['final_score'] for r in results_list) - min(r['final_score'] for r in results_list),
                "excellent_count": sum(1 for r in results_list if r['pronunciation_grade'] == "최우수"),
                "good_count": sum(1 for r in results_list if r['pronunciation_grade'] == "우수"),
                "average_count": sum(1 for r in results_list if r['pronunciation_grade'] == "보통"),
                "poor_count": sum(1 for r in results_list if r['pronunciation_grade'] == "미흡"),
                "insufficient_count": sum(1 for r in results_list if r['pronunciation_grade'] == "부족"),
                "fail_count": sum(1 for r in results_list if r['pronunciation_grade'] == "미달")
            }
            db_ready_records.append(summary_record)
        
        # JSON 파일로 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(db_ready_records, f, ensure_ascii=False, indent=2)
        
        print(f"DB 저장용 평가 결과가 {output_file}에 저장되었습니다.")
        print(f"총 {len(db_ready_records)}개 레코드 (화자: {len(results_list)}명, 요약: 1건)")
        return output_file
    
    def _grade_to_numeric(self, grade: str) -> int:
        """등급을 숫자로 변환 (DB 정렬/필터링 용이)"""
        grade_map = {
            "최우수": 6,
            "우수": 5, 
            "보통": 4,
            "미흡": 3,
            "부족": 2,
            "미달": 1
        }
        return grade_map.get(grade, 0)


if __name__ == "__main__":
    # 예시 사용법
    evaluator = FluencyEvaluator()
    
    # 모든 화자 평가 (출력 포함)
    all_results = evaluator.evaluate_all_speakers()
    
    # JSON 파일로 저장
    saved_file = evaluator.save_results_to_json(all_results)
    print(f"\n상세 결과는 {saved_file}에서 확인할 수 있습니다.") 