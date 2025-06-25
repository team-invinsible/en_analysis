###############
#
# pausestress2TextGrids.py
#
# Generate a TextGrid file for each audio file, with a word tier, a stress tier (with stress score from -1 to +1), and a pause tier (BC, between-clauses / BP, between-phrases / WP, within-phrase)
# 
# Arguments :
    # 1. stressTable csv file (list of target words with stress information)
    # 2. pauseTable csv file (list of inter-words intervalles with syntactic context information)
    # 3. original TextGrid folder (containing at least tiers WOR, SYLL)
    # 4. path to folder with the audio files 
    # 5. path to folder for the generated TextGrid files
    # 6. pause duration lower and upper cutoff point (in seconds, default= 0.18 2)
#
# S. Coulange 2024

import re, sys, os, statistics, json
from parselmouth.praat import call

test_limit = 0

stressTable = sys.argv[1]
pauseTable = sys.argv[2]
input_textgrid_folder = sys.argv[3]
if not input_textgrid_folder.endswith('/'): input_textgrid_folder += '/'
audio_folder = sys.argv[4]
if not audio_folder.endswith('/'): audio_folder += '/'
output_folder = sys.argv[5]
if not output_folder.endswith('/'): output_folder += '/'

pauseThreshold = { "min": 0.18, "max": 2 }
if len(sys.argv)==7:
    pauseThreshold["min"] = float(sys.argv[6])
    pauseThreshold["max"] = float(sys.argv[7])
print("Pause threshold set to", pauseThreshold)


clauseTag = ["S","SBAR","SBARQ","SINV","SQ"]
phraseTag = ["ADJP","ADVP","CONJP","FRAG","INTJ","LST","NAC","NP","NX","PP","PRN","PRT","QP","RRC","UCP","VP","WHADJP","WHAVP","WHNP","WHPP","X"]
conjTag = ["CC","IN"]



##################################################
#
# 1. Copy original textgrids and generate new TextGrid files with tiers: WOR, SYLL
#
print("Reading original TextGrid files...")

cpt=0
# for file in os.listdir(input_textgrid_folder):
for file in os.listdir("/home/sylvain/these/CLES_analyses/dynamicRater/serverResults/ratings/"):
        
    if test_limit!=0 and cpt>test_limit: break
    else: cpt+=1
    
    # READ INPUT TEXTGRID FILE
    print("Processing",file,"...")
    try:
        tg = call("Read from file...", input_textgrid_folder+file.replace(".TextGrid",".merged.pos_shape.TextGrid"))
    except:
        print("Unable to open the file!!")
        continue

    call(tg,"Remove tier...", 7)
    # call(tg,"Remove tier...", 6) # Observed
    # call(tg,"Remove tier...", 5) # Expected
    call(tg,"Remove tier...", 4)
    #call(tg,"Remove tier...", 3) # Nuclei
    call(tg,"Remove tier...", 1)

    call(tg, "Replace interval texts...", 1, 0, 0, "<p:>", "", "Literals")

    # create a new tier "PAUSES"
    pauseTierId = 1 # position of PAUSES tier
    call(tg, "Insert interval tier...", pauseTierId, "PAUSES")

    # create a new tier "STRESS"
    stressTierId = 6 # position of STRESS tier
    call(tg, "Insert interval tier...", stressTierId, "STRESS")

    
    ### LOOK FOR STRESS INFO IN stressTable.csv, COMPUTE STRESS SCORE AND PUT IT IN STRESS TIER
    with open(stressTable, "r") as inf:
        header = inf.readline().strip().split(';')
        # spk, lab, pos, lenSyllxpos, expectedShapes, expectedShape, observedShape, globalDeciles, F0shape, dBshape, durshape, syllF0, F0Deciles, sylldB, dBDeciles, sylldur, durDeciles, deb, fin, file, ID
        
        for line in inf:
            line = line.strip()
            l = line.split(';')
            
            if re.sub(r'\..*', '', l[-2]) == re.sub(r'\..*', '', file):
                thisLine = {}
                for x, col in enumerate(header):
                    thisLine[col] = l[x]

                # Add intervalle at current word position
                call(tg, "Insert boundary...", stressTierId, float(thisLine["deb"]))
                call(tg, "Insert boundary...", stressTierId, float(thisLine["fin"]))
                
                # Compute stress score
                # stressedSyllDecile - mean(unstressedSyllDeciles) / stressedSyllDecile + mean(unstressedSyllDeciles)
                globalDeciles = json.loads(thisLine['globalDeciles'])
                expStressPos = thisLine['expectedShape'].find("O") # -1 if no expected stress
                
                stressSyll = globalDeciles[expStressPos]
                globalDeciles.remove(globalDeciles[expStressPos])
                if len(globalDeciles)>1:
                    unstressSylls = statistics.mean(globalDeciles)
                else:
                    unstressSylls = globalDeciles[0]

                stressScore = (stressSyll - unstressSylls) / ((stressSyll + unstressSylls))
                stressScore = round(stressScore,2)
                
                if expStressPos == -1:
                    # No stress expected → stressScore = 0
                    stressScore = 0

                print("Found Target Word!",thisLine["lab"], stressScore, thisLine["globalDeciles"], stressSyll, unstressSylls)

                # Write stressScore in the intervalle
                intervalleId = call(tg, "Get interval at time...", stressTierId, float(thisLine["deb"])+0.000001) # we need to get the intervalle id from time info...
                call(tg, "Set interval text...", stressTierId, intervalleId, str(stressScore))



    ### LOOK FOR PAUSE INFO IN pauseTable.csv, COMPUTE PAUSE TYPE AND PUT IT IN PAUSE TIER
    with open(pauseTable, "r") as inf:
        header = inf.readline().strip().split(';')
        # spk, file, i, POScontextLeft, POScontextRight, duration, wordLeft, wordLeftEndingLarger, wordLeftEndingLargerNb, wordLeftDepth, wordLeftTagw, wordRight, wordRightStartingLarger, wordRightStartingLargerNb, wordRightDepth, wordRightTagw, start, end
        
        for line in inf:
            line = line.strip()
            l = line.split(';')
            
            if re.sub(r'\..*', '', l[1]) == re.sub(r'\..*', '', file):
                thisLine = {}
                for x, col in enumerate(header):
                    thisLine[col] = l[x]


                if float(thisLine['duration'])>= pauseThreshold['min'] and float(thisLine['duration'])<pauseThreshold['max']:
                    # This is a pause
                    if thisLine['wordLeftEndingLarger'] in clauseTag or thisLine['wordRightStartingLarger'] in clauseTag:
                        # This is an inter-clause pause
                        pauseType = "BC"
                    elif thisLine['wordLeftEndingLarger'] in phraseTag or thisLine['wordRightStartingLarger'] in phraseTag:
                        # This is an inter-phrase pause
                        pauseType = "BP"
                    else:
                        # This is an intra-phrase pause
                        pauseType = "WP"

                    # Add intervalle at current inter-word intervalle position
                    if thisLine["wordLeft"]!="start":
                        call(tg, "Insert boundary...", pauseTierId, float(thisLine["start"]))
                    if thisLine["wordRight"]!="end":
                        call(tg, "Insert boundary...", pauseTierId, float(thisLine["end"]))

                    # Write PauseType in the intervalle
                    intervalleId = call(tg, "Get interval at time...", pauseTierId, float(thisLine["start"])+0.000001) # we need to get the intervalle id from time info...
                    call(tg, "Set interval text...", pauseTierId, intervalleId, str(pauseType))


    ########## TEMPORARY: GET DYNAMIC RATING TIER AND ADD IT TO THE FILE
    # create a new tier "CLICKS"
    clickTierId = 1 # position of PAUSES tier
    call(tg, "Insert point tier...", clickTierId, "CLICKS")
    
    tgRatings = call("Read from file...", "/home/sylvain/these/CLES_analyses/dynamicRater/serverResults/ratings/"+file)
    nbPoints = call(tgRatings, "Get number of points...", 1) # Get number of clicks in "all" tier
    print(nbPoints)
    for p in range(0,nbPoints):
        ptime = call(tgRatings, "Get time of point...", 1, p+1)
        call(tg, "Insert point...", clickTierId, ptime, str(p))
    ##########

    # SAVE NEW TEXTGRID
    call(tg, "Save as text file...", output_folder+file)

print("Done.")