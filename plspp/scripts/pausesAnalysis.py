###############
#
# pausesAnalysis.py
#
# 1. Parse POS-ASR TextGrid files, make dictionary key=speaker value=[ [file, i, POScontextLeft, POScontextRight, duration] ]
# 2. Compute total duration of pause and frequency per speaker
# 3. Export pauseTable.csv : one pause per line, with speaker, pauseId, POScontextLeft, POScontextRight, duration
#
# S. Coulange 2022-2023

import re, os, textgrids, copy, random, string, sys

posShape_folder = sys.argv[1] # textgrid with tiers POS
benepar_folder = sys.argv[2] # benepar files (constituency analysis with squared brackets "[]")

# Do the job for this number of files only (0=all)
test_limit = 0


bugList = []


##################################################
#
# 1. Parse POS-ASR TextGrid files
#
spk2pauses = {} # dictionary key=speaker value=[ [file, i, POScontextLeft, POScontextRight, duration] ]

cpt = 0
for file in os.listdir(posShape_folder):
    
    if test_limit!=0 and cpt>test_limit: break
    else: cpt+=1
    
    # READ INPUT TEXTGRID FILE
    print("Processing",file,"...")
    try:
        grid = textgrids.TextGrid(posShape_folder+file)
    except:
        print("Unable to open the file!!")
        continue

    #tg = call("Read from file...", input_folder+file)    # LIGNE A SUPPRIMER?
    lenWor = len(grid['POS'])
    fileNameNoExt = file.replace('.TextGrid', '')
    spk = fileNameNoExt  # 수정: 전체 파일명을 화자 ID로 사용 (예: 2_9)


    # READ INPUT BENEPAR FILE
    try:
        with open(benepar_folder+fileNameNoExt+'.txt.benepar', "r") as inf:
            ana = inf.read()
    except:
        print("Can't open benebar file!")
        continue
    

    # BENEPAR CONSTITUENCY TREE PARSING
    metamemory = {} # dictionary of all constituents with IDkey as key, name and nb of words they contain as values : IDkey=["S",24], IDkey=["NP",3]...
    keylist = [] # chronological list of all constituents
    memory = [] # list of constituent currently opened with their nb of words so far ["S", 3],["NP",1]...
    head = [] # list of openingTags right before a given word
    wordlist = []
    ana = re.sub(r"\[[.,!?] [., !?]\]", "", ana) # Remove all punctuation constituent if any.
    for c in re.findall(r"\[([A-Z.$:',-]+)\s+([^\]\[ ]+)\]|\[([A-Z$]+)|(\])",ana):
        # [S [ADVP [RB okay]] [NP [PRP i]] [VP [VBP agree]
        #
        # wordLevel, word, openingTag, closing
        # ('', '', 'S', '')
        # ('IN', 'so', '', '')
        # ('', '', 'S', '')
        # ('', '', 'NP', '')
        # ('PRP', 'i', '', '')
        # ('', '', '', ')')

        wTag, word, openingTag, closing = c

        # print(wTag, word, openingTag, closing)

        if len(openingTag)>0:
            newKey = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            keylist.append(newKey)
            memory.append([newKey,openingTag,0])
            head.append([newKey,openingTag,0])
        
        if len(wTag)>0:
            # ['i', ['S', 'NP'], ['NP'], 'PRP', 3]
            # [word, startingConsts, endingConsts, wordLevelTag, depth]
            for x in memory:
                x[2] += 1
            for x in head:
                x[2] += 1
            wordlist.append( [ word, copy.copy(head), [], wTag, len(memory) ] )
            head = []

        if len(closing)>0:
            wordlist[-1][2].append(memory[-1])
            metamemory[memory[-1][0]] = memory[-1][1:]
            memory.pop()

    # Update nb of words per opening consitituent
    for w in wordlist:
        for x in w[1]:
            x[2] = metamemory[x[0]][1]

    
    # LOOP ON INTERVALLES
    if 'words' in grid:
        tierWords = 'words' # MFA OUTPUT
    else: 
        tierWords = 'WOR' # WHISPER OUTPUT

    for i,intWor in enumerate(grid[tierWords]):
        labWor = intWor.text.transcode()
        if labWor == "<p:>" or labWor == "":
            # GET TIMING INFO
            deb = round(intWor.xmin,3)
            fin = round(intWor.xmax,3)

            # POS CONTEXT
            POScontextLeft = grid['POS'][i-1].text.transcode() if i>0 else "start"
            POScontextRight = grid['POS'][i+1].text.transcode() if i<lenWor-1 else "end"
            duration = (intWor.xmax - intWor.xmin)

            # CONSTITUENCY CONTEXT
            wordLeft = grid[tierWords][i-1].text.transcode() if i>0 else "start"
            wordRight = grid[tierWords][i+1].text.transcode() if i<lenWor-1 else "end"

            if(wordRight == "end"):
                wordlist.append(['end',[],[],'end',0])
            if(wordRight == ""):
                wordlist.append(['end',[],[],'end',0]) # cas de dec2022-206_147-136-150_SPEAKER_00_10
            

            # in case of "don't" etc. which is 2 words in wordlist, so pop the first one and keep only the ending element
            while wordLeft != "start" and len(wordlist)>0 and not wordLeft.endswith(wordlist[0][0]):
                wordlist.pop(0)

            # Check if difference still exists
            if len(wordlist)==0 or not wordLeft.endswith(wordlist[0][0]) and wordLeft!="start":
                print("ERROR!!!", wordLeft, wordlist[0][0] if len(wordlist)>0 else '')
                bugList.append(file)
                continue

            # print(wordLeft, wordlist[0][0])
            boundaryStrength = len(wordlist[0][2])+len(wordlist[1][1]) if len(wordlist)>1 else 0 # represents the number of closing and openning brackets at this position

            wordLeftEndingLarger = wordlist[0][2][-1][1] if len(wordlist[0][2])>0 else ""
            wordLeftEndingLargerNb = wordlist[0][2][-1][2] if len(wordlist[0][2])>0 else ""
            wordLeftDepth = wordlist[0][4]
            wordLeftTagw = wordlist[0][3]

            wordRightStartingLarger = wordlist[1][1][0][1] if len(wordlist)>1 and len(wordlist[1][1])>0 else ""
            wordRightStartingLargerNb = wordlist[1][1][0][2] if len(wordlist)>1 and len(wordlist[1][1])>0 else ""
            wordRightDepth = wordlist[1][4] if len(wordlist)>1 else 0
            wordRightTagw = wordlist[1][3] if len(wordlist)>1 else ""

            if spk not in spk2pauses.keys():
                spk2pauses[spk] = []

            spk2pauses[spk].append( [fileNameNoExt, i, POScontextLeft, POScontextRight, duration, wordLeft, wordLeftEndingLarger, wordLeftEndingLargerNb, wordLeftDepth, wordLeftTagw, wordRight, wordRightStartingLarger, wordRightStartingLargerNb, wordRightDepth, wordRightTagw, deb, fin, boundaryStrength] )

##################################################
#
# 2. Compute total duration of pause and frequency per speaker
#
print("Statsss...") 
print("SPEAKER, NUMBER_OF_PAUSES, TOTAL_PAUSE_DURATION")
for spk,pauses in spk2pauses.items():
    sumDur = 0
    for pause in pauses:
        sumDur += pause[4]
    print(spk, len(pauses), sumDur)

    
##################################################
#
# 3. Export pauseTable.csv : one pause per line, with speaker, pauseId, POScontextLeft, POScontextRight, duration
#
print('Export pauseTable.csv...')
with open('pauseTable.csv','w') as st:
    st.write("spk;file;i;POScontextLeft;POScontextRight;duration;wordLeft;wordLeftEndingLarger;wordLeftEndingLargerNb;wordLeftDepth;wordLeftTagw;boundaryStrength;wordRight;wordRightStartingLarger;wordRightStartingLargerNb;wordRightDepth;wordRightTagw;start;end\n")
    for spk,pauses in spk2pauses.items():
        for pause in pauses:
            st.write("{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{}\n"\
                        .format(spk,
                                pause[0],   #file
                                pause[1],   #i
                                pause[2],   #POScontextLeft
                                pause[3],   #POScontextRight
                                pause[4],   #duration
                                pause[5],   #wordLeft
                                pause[6],   #wordLeftEndingLarger
                                pause[7],   #wordLeftEndingLargerNb
                                pause[8],   #wordLeftDepth
                                pause[9],   #wordLeftTagw
                                pause[17],  #boundaryStrength
                                pause[10],  #wordRight
                                pause[11],  #wordRightStartingLarger
                                pause[12],  #wordRightStartingLargerNb
                                pause[13],  #wordRightDepth
                                pause[14],   #wordRightTagw
                                pause[15],  #starting time
                                pause[16]   #ending time
                                ))

print("DONE.")

print("Buglist:")
for i in bugList:
    print(i)
