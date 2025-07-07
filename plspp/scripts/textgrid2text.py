import sys
import os

# Add praat_textgrids module path
praat_textgrids_path = "/opt/anaconda3/envs/pipeline/lib/python3.10/site-packages"
if praat_textgrids_path not in sys.path:
    sys.path.append(praat_textgrids_path)

import os, textgrids, sys
from parselmouth.praat import call

input_folder = sys.argv[1]
output_dir = sys.argv[2]

# Do the job for this number of files only (0=all)
test_limit = 0


##################################################
#
# 1. Parse TextGrid files & get raw text
#
cptPrevText = 0
cpt = 0
for file in os.listdir(input_folder):
    
    if test_limit!=0 and cpt>test_limit: break
    else: cpt+=1
    
    # READ INPUT TEXTGRID FILE
    print("Processing",file,"...")
    try:
        grid = textgrids.TextGrid(input_folder+file)
    except:
        print("Unable to read the file!!")
        continue

    tg = call("Read from file...", input_folder+file)

    # LOOP ON INTERVALLES
    ## Get words string
    text = ""
    previousIsText = False
    for i,intWor in enumerate(grid['WOR']):
        labWor = intWor.text.transcode()
        if labWor != "<p:>":
            if previousIsText:
                text += " "
                print("....................PREVIOUS IS TEXT",file)
                cptPrevText+=1
            text += labWor
            previousIsText = True
        else:
            text += " "
            previousIsText = False

    ##################################################
    #
    # 2. Export plain text
    #

    with open(output_dir + file.replace('.TextGrid','') + ".txt", "w") as outf:
        outf.write("{}".format(text.replace("  "," ")))

print("PREVIOUS IS TEXT NB OCC",cptPrevText)
