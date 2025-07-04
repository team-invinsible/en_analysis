###############
#
# wav2vec2Aligner.py
#
# For each wav file from input_folder, run Wav2Vec2.0 from WhisperX 
# to align corresponding txt transcripts.
# Output format: TextGrid files.
#
# Arguments:
#   - path to input directory containing the audio files
#   - path to input directory containing the text files (same name with audio files)
#   - path to output directory for exporting TextGrid files
#   - Device to use
#   - Batch size
#   - Compute type
#   - Model of Whisper to use
#
# Adapted from https://github.com/m-bain/whisperX
# S. Coulange 2024


import whisperx, sys, os, wave, contextlib, re
import signal

audio_folder = sys.argv[1] # "audio/"
text_folder = sys.argv[2] # "text/"
output_folder = sys.argv[3] # "whisperx/"
device = sys.argv[4] # "cuda" 
batch_size = int(sys.argv[5]) #16 # reduce if low on GPU mem
compute_type = sys.argv[6] # "int8" # change to "float16" if good GPU mem (better accuracy)
modelname = sys.argv[7] # "base.en"



# load alignment model and metadata
model_a, metadata = whisperx.load_align_model(language_code="en", device=device)


for input_file in os.listdir(audio_folder):
    print(f"Processing {input_file}...")

    if input_file.replace(".wav",".txt") not in os.listdir(text_folder):
        print("Missing text file", input_file.replace(".wav",".txt"))
        continue
    
    transcript_path = os.path.join(text_folder, input_file.replace(".wav",".txt"))

    # Load corresponding text to align
    with open(transcript_path, "r") as f:
        transcript = f.read().strip()

    # align whisper output
    result_aligned = whisperx.align(transcript, model_a, metadata, audio_folder+input_file, device)

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
            # if xmin > precedent_xmax : create an empty interval
            intervals.append([segs[indx-1][1], seg[0], "<p:>"])
            intervals.append(seg)

        else:
            intervals.append(seg)

    print('\tGet corresponding wav file duration...')
    # Because we need to add an empty interval at the end of the file
    fname = audio_folder + input_file
    with contextlib.closing(wave.open(fname,'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
        print(duration)

    print('\tGenerating TextGrid file...')

    if len(intervals)>0 and intervals[-1][1]<duration:
        intervals.append([intervals[-1][1], duration, "<p:>"])

    with open(output_folder+input_file.replace('.wav','.TextGrid'), 'w') as outf:
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


print("Done.")
