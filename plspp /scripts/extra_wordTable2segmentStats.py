###############
#
# extra_wordTable2segmentStats.py
#
# PARSE wordTable.csv and make a detailed table describing each segment
# 
#
# S. Coulange 2022-2023

import sys, re, json, statistics

input_folder = sys.argv[1] # textgrids with tiers POS (first position), WOR, Nuclei
if not input_folder.endswith('/'): input_folder+='/'
input_file = sys.argv[2] # wordTable.csv
output_file = sys.argv[3] # output file segmentTable.csv

# Do the job for this number of segments (0=all)
test_limit = 0

# Secondary stats for words up to X syllables
maxNbSylls = 3

# Analyze only following POS
posList = [ "NOUN", "VERB", "ADV", "ADJ" ]


segs2stats = {} # for each segment, list stats (nb of pauses, nb of intra-phrase pauses...)



##################################################
#
# 1. Parse stressTable.csv file and fill segs2stats line by line
#
print("Reading", input_folder + input_file ,"...")
cpt = 0
with open(input_folder + input_file,"r") as inf:
    inf.readline() # skip header

    # STRUCTURE OF wordTable.csv
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
        # 18 F0min	
        # 19 F0max	
        # 20 F0sd	
        # 21 syllmfa_equals_syllnuclei
    # 18 /22 ID

    for line in inf:
        line = line.strip()
        l = line.split(';')
        if len(l)==19:
            if test_limit != 0 and cpt >= test_limit:
                break

            fileName = l[0]
            if fileName not in segs2stats.keys():
                segs2stats[fileName] = {
                    "spk" : "",
                    "nbTokens": 0,
                    "duration": 0,
                    "nbTargetWords": 0,
                    "nbExpIsObs": 0,
                    "stressScores": [],
                    "meanStressScore": 0,

                    "nbTargetWords3syllmax": 0,
                    "nbExpIsObs3syllmax": 0,
                    "stressScores3syllmax": [],
                    "meanStressScore3syllmax": 0,
                }
                segs2stats[fileName]["spk"] = l[1]
                cpt+=1
                print("Processing", fileName, "...")

            segs2stats[fileName]["nbTokens"] += 1
            segs2stats[fileName]["duration"] = l[6]

            if l[7] != "" and l[4] in posList:
                # This is a target word
                segs2stats[fileName]["nbTargetWords"] += 1

                if len(l[10]) <= maxNbSylls:
                    segs2stats[fileName]["nbTargetWords3syllmax"] += 1

                if l[9] == l[10]:
                    segs2stats[fileName]["nbExpIsObs"] += 1
                    if len(l[10]) <= maxNbSylls:
                        segs2stats[fileName]["nbExpIsObs3syllmax"] += 1

                # Compute deciles info
                stressPos = 0
                cptsyll = 0
                for x in l[9]:
                    cptsyll+=1
                    if x=='O': stressPos = cptsyll

                deciles = json.loads(l[11])
                stressSyll = 0
                unstressSylls = []
                x = 0
                for dec in deciles:
                    x+=1
                    if x == stressPos: 
                        stressSyll = dec
                    else: 
                        unstressSylls.append(dec)
                
                score = (stressSyll - statistics.mean(unstressSylls)) / (stressSyll + statistics.mean(unstressSylls))
                score = round(score, 3)
                # print("DECILES:",deciles, "stressPos:", stressPos, stressSyll, l[3], l[10], l[11], score)

                segs2stats[fileName]["stressScores"].append(score)
                if len(l[10]) <= maxNbSylls:
                    segs2stats[fileName]["stressScores3syllmax"].append(score)
            
print(cpt,"segments parsed. (test_limit =",test_limit,")")


# Make some other stats on each segment
for seg, stats in segs2stats.items():
    if stats['nbTargetWords']>0:
        segs2stats[seg]["meanStressScore"] = round(statistics.mean(segs2stats[seg]["stressScores"]), 3)
        if stats['nbTargetWords3syllmax']>0:
            segs2stats[seg]["meanStressScore3syllmax"] = round(statistics.mean(segs2stats[seg]["stressScores3syllmax"]), 3)


# Export segst2stats in csv
with open(input_folder + output_file,'w') as outf:
    outf.write('file;'+';'.join([ format(x) for x in segs2stats[list(segs2stats.keys())[0]].keys() ])+'\n')
    # outf.write('{};{};{};{};{};{};{};{};{};{};{}\n'.format(
    #         "file",
    #         "spk" ,
    #         "nbTokens",
    #         "duration",
    #         "nbTargetWords",
    #         "nbExpIsObs",
    #         "meanStressScore",
    #         "nbTargetWords3syllmax",
    #         "nbExpIsObs3syllmax",
    #         "stressScores3syllmax",
    #         "meanStressScore3syllmax"
    #     ))

    for seg, stats in segs2stats.items():
        outf.write(str(seg)+';'+';'.join([ str(x) for x in stats.values() ])+'\n')
        # outf.write('{};{};{};{};{};{};{};{};{};{};{}\n'.format(
        #     seg,
        #     stats["spk" ],
        #     stats["nbTokens"],
        #     stats["duration"],
        #     stats["nbTargetWords"],
        #     stats["nbExpIsObs"],
        #     stats["meanStressScore"],
        #     stats["nbTargetWords3syllmax"],
        #     stats["nbExpIsObs3syllmax"],
        #     stats["stressScores3syllmax"],
        #     stats["meanStressScore3syllmax"]
        # ))
print("Table exported to:",input_folder + output_file)