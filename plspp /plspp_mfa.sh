#!/bin/bash
#
# Pipeline for extracting pause and lexical stress features from speech
# This is PLSPP v2, with MFA implementation for word and phoneme level alignment.
# INTEGRATED VERSION: Includes both stress analysis (MFA-based) and pause analysis
# Input: audio wav files in folder audio/, file name will be considered as speaker name (you can add "_<number>" at the end of files if you have multiple files from the same speaker)
#           example: jan2023-201_089-009_SPEAKER_00_0.wav (speaker A: jan2023-201_089-009_SPEAKER_00)
#                    jan2023-201_089-009_SPEAKER_00_1.wav (speaker A: jan2023-201_089-009_SPEAKER_00)
#                    jan2023-201_089-009_SPEAKER_00_2.wav (speaker A: jan2023-201_089-009_SPEAKER_00)
#                    jan2023-202_053-128_SPEAKER_01_1.wav (speaker B: jan2023-202_053-128_SPEAKER_01)
#                    jan2023-202_053-128_SPEAKER_01_3.wav (speaker B: jan2023-202_053-128_SPEAKER_01)
#
# Outputs:
#       - folder shape/ with one TextGrid file per sound file, with tiers of parts-of-speech (POS), words (WOR), phonemes (phones), syllable-nuclei (Nuclei), expected prosodic shape (ExpectedShape), observed prosodic shape (ObservedShape), observed shape on F0, intensity and duration (DetailedShapes)
#       - stressTable.csv table of stress pattern per speaker: list of all target words (plurisyllabic plain words with appropriate number of syllables detected) and details about their pronunciation (with F0min, F0max, F0sd)
#       - pauseTable.csv table of pauses per speaker: list of all word intersections (<p:> tags) with their duration and info about their syntactic position
#       - wordTable.csv table of all words with stress info when there is some. This file is needed for the detailed stress view on PLSPP visualisation tool
#       - segmentTable.csv some statistics for each audio file
#       - speakers.csv list of speakers
#       - other folders are temporary:
#           - whisperx/ : transcribed and word aligned sound files in TextGrid format
#           - syll/ : detection of syllable-nuclei as point tier in TextGrid format
#           - tg/ : combination of whisperx and syll files
#           - tgmfa/ : output from Montreal Forced Aligner (alignment at word and phoneme level of text/ and audio/ files)
#           - tgpos/ : tg files with parts-of-speech
#           - text/ : raw text file for each sound file (concatenation from whisperx files)
#           - benepar/ : constituency analysis of each text files
#        
#       - Sound files that couldn't be speech recognized by WhisperX are listed in bugsWhisperX.txt
#
# S. Coulange 2022-2024 sylvain.coulange@univ-grenoble-alpes.fr
# Modified for integrated analysis (stress + pause) 2024

echo "========================================================================"
echo "🚀 Starting INTEGRATED PLSPP Pipeline (MFA + Pause Analysis)!"
echo "This version combines MFA-based stress analysis with pause analysis"
echo "Check MFA outputs. If alignment is too poor, use PLSPP v1."
echo "========================================================================"

# 현재 스크립트의 디렉토리 경로 저장
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Praat 실행 파일 경로 설정
PRAAT_PATH="/Applications/Praat.app/Contents/MacOS/Praat"

# Praat 실행 파일 확인
if [ ! -x "$PRAAT_PATH" ]; then
    echo "Error: Praat executable not found or not executable at $PRAAT_PATH"
    echo "Please check if Praat is installed correctly"
    exit 1
fi

echo "Using Praat at: $PRAAT_PATH"
echo "Script directory: $SCRIPT_DIR"
echo ""

#### ASR AND WORD ALIGNMENT WITH WHISPERX
echo "📝 Speech recognition and word alignment..."
mkdir -p "$SCRIPT_DIR/whisperx"
python "$SCRIPT_DIR/scripts/myWhisperxTG.py" "$SCRIPT_DIR/audio/" "$SCRIPT_DIR/whisperx/" cuda 16 int8 base.en
# arguments: input_folder, output_folder, device, batch_size (reduce if low on GPU memory), compute_type (change to float16 if good GPU mem), model_name

# Get raw text from whisperx files
echo "📄 Get raw transcription files..."
mkdir -p "$SCRIPT_DIR/text"
python "$SCRIPT_DIR/scripts/textgrid2text.py" "$SCRIPT_DIR/whisperx/" "$SCRIPT_DIR/audio/"

#### SYLLABLE NUCLEI DETECTION
echo "🔍 Syllable nuclei detection..."
mkdir -p "$SCRIPT_DIR/syll"
"$PRAAT_PATH" "$SCRIPT_DIR/scripts/SyllableNucleiv3_DeJongAll2021.praat" "$SCRIPT_DIR/audio/*.wav" "Band pass (300..3300 Hz)" -25 2 0.3 "no" "English" 1.00 "TextGrid(s) only" "OverWriteData" "yes"
mv "$SCRIPT_DIR/audio/"*.TextGrid "$SCRIPT_DIR/syll/" 2>/dev/null || true

#### MFA word & phoneme alignment
echo "🎯 Word and phoneme alignment with MFA..."
mkdir -p "$SCRIPT_DIR/tgmfa"
mfa align "$SCRIPT_DIR/audio/" english_us_arpa english_us_arpa "$SCRIPT_DIR/tgmfa/" --clean # Add --beam 20 or --beam 50 (or 100) if needed
mv "$SCRIPT_DIR/audio/"*.txt "$SCRIPT_DIR/text/" 2>/dev/null || true

echo "🔗 Merging transcription, MFA alignement and syllable files..."
mkdir -p "$SCRIPT_DIR/tg"
"$PRAAT_PATH" "$SCRIPT_DIR/scripts/Merge_tiers_of_different_TextGrids.praat" "$SCRIPT_DIR/tgmfa/" "$SCRIPT_DIR/syll/" '1-1,words/1-2,phones/2-1,Nuclei' "$SCRIPT_DIR/tg/"
# arguments: input_folderA, input_folderB, target tiers, output_folder

#### SYNTACTIC ANALYSIS WITH SPACY
echo "🔤 Syntactic analysis..."
mkdir -p "$SCRIPT_DIR/tgpos"
python "$SCRIPT_DIR/scripts/spacyTextgrid_v2.py" "$SCRIPT_DIR/tg/" "$SCRIPT_DIR/tgpos/" 'en_core_web_md' 'words'
# arguments: input_folder, output_folder, model_name, words_tier_name

#### LEXICAL STRESS ANALYSIS (MFA-based with detailed features)
echo "💪 Lexical stress pattern analysis (MFA-based)..."
mkdir -p "$SCRIPT_DIR/shape"
python "$SCRIPT_DIR/scripts/stressAnalysis_mfa.py" "$SCRIPT_DIR/tgpos/" "$SCRIPT_DIR/audio/" "$SCRIPT_DIR/shape/" "$SCRIPT_DIR/CMU/cmudict-0.7b"
# arguments: textgrid_folder, audio_folder, output_folder, path_to_CMU_dictionary

# #### ADDITIONAL TABLES GENERATION - 불필요한 파일 생성 제거 (fluency_evaluator.py에서 미사용)
# echo "📊 Computing additional tables (word table, segment table)..."
# python "$SCRIPT_DIR/scripts/extra_statsPerSegment_stress.py" "$SCRIPT_DIR/shape/" "$SCRIPT_DIR/stressTable.csv" "$SCRIPT_DIR/wordTable.csv" "$SCRIPT_DIR/segmentTable.csv"

#### PAUSE ANALYSIS (Previously commented out, now activated)
echo "⏸️  Pause pattern analysis..."
mkdir -p "$SCRIPT_DIR/benepar"

# Make constituency analysis from text files with Berkeley Neural Parser
echo "🌳 Creating constituency analysis..."
python "$SCRIPT_DIR/scripts/text2benepar.py" "$SCRIPT_DIR/text/" "$SCRIPT_DIR/benepar/" 'benepar_en3' 'en_core_web_md'
# arguments: input_folder, output_folder, benepar_model_name, spacy_model_name

# Run pause analysis
echo "📏 Running pause analysis..."
cd "$SCRIPT_DIR"
python "$SCRIPT_DIR/scripts/pausesAnalysis.py" "$SCRIPT_DIR/shape/" "$SCRIPT_DIR/benepar/"
# Move pauseTable.csv to the correct location if it was created elsewhere
if [ -f "pauseTable.csv" ]; then
    echo "✅ pauseTable.csv created successfully"
elif [ -f "$SCRIPT_DIR/scripts/pauseTable.csv" ]; then
    mv "$SCRIPT_DIR/scripts/pauseTable.csv" "$SCRIPT_DIR/pauseTable.csv"
    echo "✅ pauseTable.csv moved to project root"
else
    echo "⚠️  pauseTable.csv not found - checking for creation issues"
fi

#### VERIFY REQUIRED FILES FOR FLUENCY EVALUATION
echo "🔍 필수 분석 파일 확인 중..."

# 최종 분석에 필요한 파일들 확인
if [ -f "$SCRIPT_DIR/stressTable.csv" ] && [ -f "$SCRIPT_DIR/pauseTable.csv" ]; then
    echo "✅ 필수 파일 생성 확인됨 (stressTable.csv, pauseTable.csv)"
    
    # 중간 처리 폴더들 삭제 (fluency_evaluator.py에서 미사용)
    echo "🗑️  중간 처리 폴더 삭제 중..."
    rm -rf "$SCRIPT_DIR/whisperx" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/syll" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/tg" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/tgmfa" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/tgpos" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/benepar" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/shape" 2>/dev/null || true
    rm -rf "$SCRIPT_DIR/visualization" 2>/dev/null || true
    
    echo "✅ 중간 파일 정리 완료"
else
    echo "⚠️  필수 파일이 생성되지 않아 정리를 건너뜁니다"
fi

#### FINAL SUMMARY
echo ""
echo "========================================================================"
echo "✅ INTEGRATED PLSPP Pipeline completed successfully!"
echo ""
echo "📂 Generated outputs:"
echo "   📊 stressTable.csv    - Detailed stress analysis (with F0min/max/sd)"
echo "   ⏸️  pauseTable.csv     - Pause pattern analysis"
echo ""
echo "📝 Note: 중간 처리 폴더들 정리됨 (fluency_evaluator.py 최적화)"
echo "   • whisperx/, syll/, tg/, tgmfa/, tgpos/, text/, benepar/, shape/, visualization/"
echo ""
echo "🔬 Analysis features included:"
echo "   • MFA-based phoneme-level alignment (high accuracy)"
echo "   • Detailed F0 analysis (F0min, F0max, F0sd)"
echo "   • Comprehensive stress pattern detection"
echo "   • Syntactic pause analysis with constituency parsing"
echo "   • Complete prosodic feature extraction"
echo "========================================================================"

echo "Done!"