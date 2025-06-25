###############
#
# extra_statsPerSegment_stress.py
#
# This script parse all the TextGrid files (and stressTable.csv) and make a big table with all words 
# (including target and not target words) with stress info when available, and make another table with
# stats for each audio file (nb of tokens, nb of target words, nb of words correctly stressed, duration)
#
# This script isn't implemented yet in the pipeline (.sh file). You will have to run it separately for now.
# python extra_statsPerSegment_stress.py path/to/TextGridFolder path/to/stressTable.csv path/to/output/wordTable.csv path/to/output/segmentTable.csv
#
# 0. Parse stressTable.csv file to get full info about stress words (ID, number of syllable candidates...)
# 1. Parse TextGrid files, make a big csv table with one word per line and stress info if present & make statistics for each segment
# 3. Export statistic for each segment (audio file)
#
# S. Coulange 2022-2023

import sys
import os

# Add praat_textgrids module path
praat_textgrids_path = "/opt/anaconda3/envs/pipeline/lib/python3.10/site-packages"
if praat_textgrids_path not in sys.path:
    sys.path.append(praat_textgrids_path)

import re, os, textgrids, parselmouth, statistics, random, string
from parselmouth.praat import call

input_folder = sys.argv[1] # textgrids with tiers POS (first position), WOR, Nuclei
if not input_folder.endswith('/'): input_folder+='/'
stressTableFilePath = sys.argv[2] # path and file name pointing to stressTable.csv
output_file = sys.argv[3] # output file wordTable.csv
output_file2 = sys.argv[4] # output file segmentTable.csv

# Do the job for this number of files only (0=all)
test_limit = 0




##################################################
#
# 0. Parse stressTable.csv file to get full info about stress words (ID, number of syllable candidates...)
#
print("Putting in memory stressTable.csv...")
cpt = 0
segment2stressTable = {} # for each segment (file), list words with stress info
header = []

with open(stressTableFilePath,"r") as inf:
    header = inf.readline().strip().split(';') # get header
    fileColumn = header.index("file")
    # STRUCTURE OF stressTable.csv
    # 0 spk
    # 1 lab
    # 2 pos
    # 3 lenSyllxpos
    # 4 expectedShapes
    # 5 expectedShape
    # 6 observedShape
    # 7 expectedStressPosition
    # 8 observedStressPosition
    # 9 expectedIsObserved
    # 10 globalDeciles
    # 11 stressSyllableDecile
    # 12 meanUnstressSyllablesDeciles
    # 13 F0shape
    # 14 dBshape
    # 15 durshape
    # 16 syllF0
    # 17 F0Deciles
    # 18 stressSyllableDecileF0
    # 19 meanUnstressSyllablesDecilesF0
    # 20 sylldB
    # 21 dBDeciles
    # 22 stressSyllableDeciledB
    # 23 meanUnstressSyllablesDecilesdB
    # 24 sylldur
    # 25 durDeciles
    # 26 stressSyllableDeciledur
    # 27 meanUnstressSyllablesDecilesdur
    # 28 startTime
    # 29 endTime
    # 30 file
    # 31 ID

    for line in inf:
        line = line.strip()
        l = line.split(';')
        
        if re.sub(r"(.merged.pos)?.TextGrid","",l[fileColumn]) not in segment2stressTable.keys():
            segment2stressTable[re.sub(r"(.merged.pos)?.TextGrid","",l[fileColumn])] = []
        segment2stressTable[re.sub(r"(.merged.pos)?.TextGrid","",l[fileColumn])].append(l)
        cpt+=1
print("Done.",cpt,"entries in memory.")


##################################################
#
# 1. Parse TextGrid files, make a big csv table with one word per line and stress info if present & make statistics for each segment
#
segment2stat = {}
cpt = 0
with open(output_file, 'w') as outf:
    outf.write("file;spk;i;word;POS;start;end;lenSyllxpos;expectedShapes;expectedShape;observedShape;globalDeciles;F0shape;dBshape;durshape;F0Deciles;dBDeciles;durDeciles;ID\n")

    # STRUCTURE OF OUTPUT FILE
    # 0 file
    # 1 spk
    # 2 i
    # 3 word
    # 4 POS
    # 5 start
    # 6 end
    # 7 lenSyllxpos
    # 8 expectedShapes
    # 9 expectedShape
    # 10 observedShape
    # 11 globalDeciles
    # 12 F0shape
    # 13 dBshape
    # 14 durshape
    # 15 F0Deciles
    # 16 dBDeciles
    # 17 durDeciles
    # 18 ID

    for file in os.listdir(input_folder):
        
        if test_limit!=0 and cpt>test_limit: break
        else: cpt+=1
        
        # READ INPUT TEXTGRID FILE
        print("Processing",file,"...")
        try:
            grid = textgrids.TextGrid(input_folder+file)
        except:
            print("Unable to open the file!!")
            continue

        tg = call("Read from file...", input_folder+file)

        file = re.sub(r"(.merged.pos_shape)?.TextGrid","",file)
        spk = re.sub(r"_\d+$","",file)

        wordTable = [] # List of all words of the current file

        # LOOP ON INTERVALLES
        nbToken = 0
        nbTargetWords = 0
        nbExpIsObs = 0
        for i,intervalle in enumerate(grid['words']):
            lab = intervalle.text.transcode()
            
            if lab != "<p:>" and lab != "":
                nbToken+=1
                deb = round(intervalle.xmin,3)
                fin = round(intervalle.xmax,3)
                pos = grid['POS'][i].text.transcode()

                thisStressWord = ["" for x in range(0,36)] # Init to empty vector
                if file in segment2stressTable.keys():
                    for w in segment2stressTable[file]:
                        if round(float(w[header.index("startTime")]),3) == deb:
                            thisStressWord = w # Get the stress info about this word if found in StressTable
                            nbTargetWords+=1

                            if w[header.index("expectedShape")]==w[header.index("observedShape")]:
                                # Expected shape is observed (correct stress position)
                                nbExpIsObs+=1

                outf.write(';'.join([
                    format(file), # file
                    format(spk), # spk
                    format(i), # i
                    format(lab), # word
                    format(pos), # POS
                    format(round(deb,3)), # start
                    format(round(fin,3)), # end
                    format(thisStressWord[header.index("lenSyllxpos")]), # lenSyllxpos
                    format(thisStressWord[header.index("expectedShapes")]), # expectedShapes
                    format(thisStressWord[header.index("expectedShape")]), # expectedShape
                    format(thisStressWord[header.index("observedShape")]), # observedShape
                    format(thisStressWord[header.index("globalDeciles")]), # globalDeciles
                    format(thisStressWord[header.index("F0shape")]), # F0shape
                    format(thisStressWord[header.index("dBshape")]), # dBshape
                    format(thisStressWord[header.index("durshape")]), # durshape
                    format(thisStressWord[header.index("F0Deciles")]), # F0Deciles
                    format(thisStressWord[header.index("dBDeciles")]), # dBDeciles
                    format(thisStressWord[header.index("durDeciles")]), # durDeciles
                    format(thisStressWord[header.index("ID")]), # ID
                    ])+"\n")

        ## Statistics on the current segment                    
        segment2stat[file] = {
            "spk":spk,
            "nbTokens":nbToken,
            "nbTargetWords":nbTargetWords,
            "nbExpIsObs":nbExpIsObs,
            "duration": round(grid['words'][-1].xmax,3)
        }
print(cpt,'files processed.')


##################################################
#
# 3. Export statistic for each segment (audio file)
#
print("GLOBAL STATISTICS PER SEGMENT:")
if len(segment2stat.keys())>0:
    print('file\t' + '\t'.join(list(segment2stat[list(segment2stat.keys())[0]].keys())))
else:
    print("No segment statistics.")

with open(output_file2, 'w') as outf:
    outf.write('file;' + ';'.join(list(segment2stat[list(segment2stat.keys())[0]].keys())) + '\n')
    for i,j in segment2stat.items():
        print(i, ";".join([str(y) for x,y in j.items()]))
        outf.write(format(i) + ";" + ";".join([format(y) for x,y in j.items()]) + "\n")