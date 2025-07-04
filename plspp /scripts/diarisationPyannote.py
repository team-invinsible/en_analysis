###############
#
# diarisationPyannote.py
#
# Runs Pyannote.audio speaker diarisation on each wav file from and input directory
# and generates a list of time segments with the corresponding speaker, one text file per wav file
# Format of output:
#       start=0.2s stop=1.5s speaker_A
#       start=1.8s stop=3.9s speaker_B
#       start=4.2s stop=5.7s speaker_A
#       ...
#
# Arguments: 
    # 1. path to wav files directory
    # 2. path to output pyannote files
    # 3. Hugging face token to be allowed to use the pretrained model
#
# S. Coulange 2022-2023

import os, sys
import datetime

inputDir = sys.argv[1]
outputDir = sys.argv[2]
auth_token = sys.argv[3]

now = datetime.datetime.now()
print("Begin: ",str(now))

# instantiate pretrained speaker diarization pipeline
print("Loading Pyannote (this usually takes a while)...")
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization",
                                    use_auth_token = auth_token)

print('OK.')

for fi in os.listdir(inputDir):
    print('Traitement de '+fi+' ...')

    # apply pretrained pipeline
    diarization = pipeline(inputDir+fi)
    print('OK.')

    # print the result
    with open(outputDir+fi+'.pyannote', 'w') as outf:
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            print(f"start={turn.start:.1f}\tstop={turn.end:.1f}\tspeaker_{speaker}")
            outf.write("{};{};{}\n".format(turn.start,turn.end,speaker))

print("THE END!!")

now = datetime.datetime.now()
print("End: ",str(now))

