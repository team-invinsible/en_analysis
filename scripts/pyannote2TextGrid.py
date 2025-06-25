# pyannote2TextGrid
#
# Input: raw output from Pyannote-audio2.0 (speaker diarization) 
# Output: Textgrid file with one tier per speaker
#
# Consecutive segments of the same speaker will be merged if silence between is less than minPause seconds (see below)
#
# input format = "start_time;end_time;speaker" :
    # 1.3921875;7.079062500000001;SPEAKER_00
    # 10.251562500000002;10.724062500000002;SPEAKER_00
    # 10.9603125;10.994062500000002;SPEAKER_00
    # 12.411562500000002;17.7440625;SPEAKER_00
    # 19.0603125;35.378437500000004;SPEAKER_01
    # 35.800312500000004;42.449062500000004;SPEAKER_01
    # 42.870937500000004;47.8490625;SPEAKER_01
    # 49.0978125;49.99218750000001;SPEAKER_01
    # 49.99218750000001;50.025937500000005;SPEAKER_00
    # 50.751562500000006;51.5446875;SPEAKER_00
#


import sys, os, wave, contextlib

input_folder = sys.argv[1] # pyannote output files
audio_folder = sys.argv[2] # wav files
output_folder = input_folder

# Cut the segment if silence longer than:
minPause = float(sys.argv[3]) # (in seconds) 1 is a good start.


for inputFile in os.listdir(input_folder):
    
    print("Processing",inputFile,"...")

    segs = {}
    with open(input_folder + inputFile,'r') as inf:
        for line in inf:
            line = line.strip()
            l = line.split(';')
            if len(l)==3:
                xmin, xmax, text = l

                if text not in segs.keys(): 
                    # Init new speaker
                    segs[text] = [] 

                if len(segs[text])==0: 
                    segs[text].append([xmin, xmax, text])
                else:
                    # If distance with precedent segment > minPause, make a new segment
                    if float(xmin)-float(segs[text][-1][1]) > minPause:
                        segs[text].append([xmin, xmax, text])
                    # else, update xmax from last segment
                    else:
                        segs[text][-1][1] = xmax

    # Add empty segments between each speech segment
    newSegs = {}

    for loc in segs.keys():
        newSegs[loc] = [[0,0,""]]
        for seg in segs[loc]:
            newSegs[loc][-1][1] = seg[0]
            newSegs[loc].append(seg)
            newSegs[loc].append([seg[1], seg[1], ""])


    fname = inputFile.replace('.pyannote','')

    with contextlib.closing(wave.open(audio_folder + fname,'r')) as f:
        frames = f.getnframes()
        rate = f.getframerate()
        duration = frames / float(rate)
        print(duration)

    for loc in segs.keys():
        newSegs[loc][-1][1] = duration

    with open(output_folder + inputFile + '.TextGrid', 'w') as outf:
        outf.write('''File type = "ooTextFile"
    Object class = "TextGrid"

    xmin = 0 
    xmax = {}
    tiers? <exists> 
    size = {}
    item []:\n'''.format(duration, len(segs.keys())))

        for x,loc in enumerate(newSegs.keys()):
            outf.write('''    item [{}]:
                class = "IntervalTier"
                name = "{}"
                xmin = 0
                xmax = {}
                intervals: size = {}\n'''.format(x, loc, duration, len(newSegs[loc])))
            for i,seg in enumerate(newSegs[loc]):
                outf.write('''        intervals [{}]:
                    xmin = {}
                    xmax = {}
                    text = "{}"\n'''.format(i+1,seg[0],seg[1],seg[2]))

print("Done.")
