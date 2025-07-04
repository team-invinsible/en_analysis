###############
#
# extra_pauseTable2segmentStats.py
#
# PARSE pauseTable.csv and make a detailed table describing each segment
# 
#
# S. Coulange 2022-2023

import sys

input_folder = sys.argv[1] # textgrids with tiers POS (first position), WOR, Nuclei
if not input_folder.endswith('/'): input_folder+='/'
input_file = sys.argv[2] # pauseTable.csv
output_file = sys.argv[3] # output file segmentTable.csv

# Do the job for this number of segments (0=all)
test_limit = 0

# Pause threshold
pauseThreshold = { 'min': 0.400, 'max': 2 }


clauseTag = ["S","SBAR","SBARQ","SINV","SQ"]
phraseTag = ["ADJP","ADVP","CONJP","FRAG","INTJ","LST","NAC","NP","NX","PP","PRN","PRT","QP","RRC","UCP","VP","WHADJP","WHAVP","WHNP","WHPP","X"]
conjTag = ["CC","IN"]

segs2stats = {} # for each segment, list stats (nb of pauses, nb of intra-phrase pauses...)

##################################################
#
# 1. Parse stressTable.csv file and fill segs2stats line by line
#
print("Reading", input_folder + input_file ,"...")
cpt = 0
with open(input_folder + input_file,"r") as inf:
    inf.readline() # skip header

    # STRUCTURE OF pauseTable.csv
    # 0 spk
    # 1 file
    # 2 i
    # 3 POScontextLeft
    # 4 POScontextRight
    # 5 duration
    # 6 wordLeft
    # 7 wordLeftEndingLarger
    # 8 wordLeftEndingLargerNb
    # 9 wordLeftDepth
    # 10 wordLeftTagw
    # 11 wordRight
    # 12 wordRightStartingLarger
    # 13 wordRightStartingLargerNb
    # 14 wordRightDepth
    # 15 wordRightTagw
    # 16 deb
    # 17 fin

    for line in inf:
        line = line.strip()
        l = line.split(';')
        spk, fileName, ix, POScontextLeft, POScontextRight, duration, wordLeft, wordLeftEndingLarger, wordLeftEndingLargerNb, wordLeftDepth, wordLeftTagw, wordRight, wordRightStartingLarger, wordRightStartingLargerNb, wordRightDepth, wordRightTagw, deb, fin = l
        if len(l)==18:
            if test_limit != 0 and cpt >= test_limit:
                break
            
            if fileName not in segs2stats.keys():
                segs2stats[fileName] = {
                    "spk" : "",
                    "duration": 0,
                    "nbTokens": -1, # nb tokens = nb <p:>-1
                    "nbPauses": 0,
                    "nbpClause": 0,
                    "nbpPhrase": 0,
                    "nbpWord": 0,

                    "durPauses": 0,
                    "durpClause": 0,
                    "durpPhrase": 0,
                    "durpWord": 0,

                    "nb_clause": 0,
                    "nb_phrase": 0,

                    "maxDepth": 0
                }
                segs2stats[fileName]["spk"] = spk
                cpt+=1
                print("Processing", fileName, "...")

            duration = round(float(duration), 3)
            fin = float(fin)
            wordLeftDepth = int(wordLeftDepth)
            segs2stats[fileName]["nbTokens"] += 1
            segs2stats[fileName]["duration"] = fin
            
            if segs2stats[fileName]["maxDepth"] < wordLeftDepth:
                segs2stats[fileName]["maxDepth"] = wordLeftDepth

            if wordRightStartingLarger in clauseTag:
                segs2stats[fileName]["nb_clause"] += 1
            # Unable to compute nb of phrases since only "largest_constituent" appear on PauseTable.csv

            if duration>= pauseThreshold['min'] and duration<pauseThreshold['max']:
                # This is a pause
                segs2stats[fileName]["nbPauses"] += 1
                segs2stats[fileName]["durPauses"] += duration

                if wordLeftEndingLarger in clauseTag or wordRightStartingLarger in clauseTag:
                    # This is an inter-clause pause
                    segs2stats[fileName]['nbpClause'] += 1
                    segs2stats[fileName]['durpClause'] += duration
                elif wordLeftEndingLarger in phraseTag or wordRightStartingLarger in phraseTag:
                    # This is an inter-phrase pause
                    segs2stats[fileName]['nbpPhrase'] += 1
                    segs2stats[fileName]['durpPhrase'] += duration
                else:
                    # This is an intra-phrase pause
                    segs2stats[fileName]['nbpWord'] += 1
                    segs2stats[fileName]['durpWord'] += duration

print(cpt,"segments parsed. (test_limit =",test_limit,")")


# Export segst2stats in csv
with open(input_folder + output_file,'w') as outf:
    outf.write('file;'+';'.join([ format(x) for x in segs2stats[list(segs2stats.keys())[0]].keys() ])+'\n')

    for seg, stats in segs2stats.items():
        outf.write(str(seg)+';'+';'.join([ str(x) for x in stats.values() ])+'\n')
        
print("Table exported to:",input_folder + output_file)