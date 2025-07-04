###############
#
# myWhisperxTG.py
#
# For each wav file from input_folder, run WhisperX for speech recognition
# and word-level time alignment. Output format: TextGrid files.
#
# Arguments:
#   - path to input directory containing the audio files
#   - path to output directory for exporting TextGrid files
#
# Adapted from https://github.com/m-bain/whisperX
# S. Coulange 2022-2024


import whisperx, sys, os, wave, contextlib, re
import signal
import subprocess

input_folder = sys.argv[1] # "audio/"
output_folder = sys.argv[2] # "whisperx/"

# CPU 환경에 맞는 설정
device = "cpu"
batch_size = 1  # CPU에서는 작은 배치 사이즈 사용
compute_type = "int8"  # CPU에서는 int8 사용
modelname = "base.en"  
# Praat 실행 파일 경로
PRAAT_PATH = "/Applications/Praat.app/Contents/MacOS/Praat"

# 출력 디렉토리가 없으면 생성
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

def run_praat_script(script_path, *args):
    """Praat 스크립트를 실행하는 함수"""
    cmd = [PRAAT_PATH, "--run", script_path] + list(args)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Praat 스크립트 실행 중 오류 발생: {e}")
        print(f"오류 출력: {e.stderr}")
        return False

class timeout:
    def __init__(self, seconds=300, error_message='Timeout'):  # CPU에서는 타임아웃 시간 증가
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


print("Loading WhisperX model...")
# transcribe with original whisper
model = whisperx.load_model(modelname, device, compute_type=compute_type)
print("Model loaded successfully!")


for input_file in os.listdir(input_folder):
    if not input_file.endswith('.wav'):  # wav 파일만 처리
        continue
        
    print(f"Processing {input_file}...")
    result = ""
    try:
        with timeout(seconds=300):  # CPU에서는 타임아웃 시간 증가
            result = model.transcribe(input_folder+input_file, batch_size=batch_size)
    except TimeoutError:
        print(f"TIMEOUT for {input_file}!")
        with open("bugsWhisperX.txt", "a") as f:
            f.write(f"{input_file}\n")
        continue
    except Exception as e:
        print(f"Error processing {input_file}: {str(e)}")
        with open("bugsWhisperX.txt", "a") as f:
            f.write(f"{input_file} - Error: {str(e)}\n")
        continue

    try:
        # load alignment model and metadata
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)

        # align whisper output
        result_aligned = whisperx.align(result["segments"], model_a, metadata, input_folder+input_file, device)

        segs=[]
        for seg in result_aligned["word_segments"]:
            if 'start' in seg:
                segs.append([seg['start'], seg['end'], seg['word']])
                print(seg)
            else:
                print("Skip:",seg)

        print("\tGenerating the list of intervals...")
        intervals = []
        for indx, seg in enumerate(segs):
            if indx==0 and seg[0]>0: 
                intervals.append([0, seg[0], "<p:>"])
                intervals.append(seg)
            elif seg[0]>segs[indx-1][1]:
                intervals.append([segs[indx-1][1], seg[0], "<p:>"])
                intervals.append(seg)
            else:
                intervals.append(seg)

        print('\tGet corresponding wav file duration...')
        fname = input_folder + input_file
        with contextlib.closing(wave.open(fname,'r')) as f:
            frames = f.getnframes()
            rate = f.getframerate()
            duration = frames / float(rate)
            print(duration)

        print('\tGenerating TextGrid file...')

        if len(intervals)>0 and intervals[-1][1]<duration:
            intervals.append([intervals[-1][1], duration, "<p:>"])

        output_file = os.path.join(output_folder, input_file.replace('.wav','.TextGrid'))
        with open(output_file, 'w') as outf:
            outf.write('''File type = "ooTextFile"
Object class = "TextGrid"

xmin = 0 
xmax = {}
tiers? <exists> 
size = 1
item []:\n'''.format(duration))

            outf.write('''    item [1]:
        class = "IntervalTier"
        name = "WOR"
        xmin = 0
        xmax = {}
        intervals: size = {}\n'''.format(duration, len(intervals)))
            for i,seg in enumerate(intervals):
                outf.write('''        intervals [{}]:
            xmin = {}
            xmax = {}
            text = "{}"\n'''.format(i+1,seg[0],seg[1],re.sub(r'\.|,|\.\.\.|;|!|\?|…|"','',seg[2].lower())))
                
        print(f"Successfully processed {input_file}")
        
    except Exception as e:
        print(f"Error in post-processing {input_file}: {str(e)}")
        with open("bugsWhisperX.txt", "a") as f:
            f.write(f"{input_file} - Post-processing Error: {str(e)}\n")
        continue

print("Done.")

# Praat 스크립트 실행
print("음절 분석 실행 중...")
syllable_script = os.path.join(os.path.dirname(__file__), "SyllableNucleiv3_DeJongAll2021.praat")

# 모든 WAV 파일에 대해 한 번에 Praat 스크립트 실행
wav_pattern = os.path.join(input_folder, "*.wav")
if run_praat_script(syllable_script, wav_pattern, "None", "-25", "2", "0.3", "yes", "English", "1.00", "TextGrid(s) only", "OverWriteData", "yes"):
    print("음절 분석 완료")
else:
    print("음절 분석 실패")
