###############
#
# stressAnalysis_mfa_monosyllabic.py
#
# This new version of stressAnalysis.py is based on stressAnalysis_mfa version, but also analyses monosyllabic words in order to measure syllable prominence of every words!
#
# 1. Creation of the plurisyllabic word's prosodic shape dictionary from CMU Dictionary (ex. "effect":["oO","Oo"])
# 2. Parse TextGrid files, get corresponding WAVE files, do acoustic analysis and make a new TextGrid with new tiers : ExpectedShape, ObservedShape, DetailedShape. Store the values in stressTable
# 3. Make decile scale for F0, intensity, duration for each speaker
# 4. Loop on new TextGrids and inject prosodic shape (o/O) from decile values of each dimension (DetailedShape) + mean of the 3 dimensions (ObservedShape)
# 5. Export stressTable.csv (list of all target word occurrences with details about their prosodic realisation)
# 6. Export speakers.csv (just a list of all speakers)
#
# S. Coulange 2024

import re, os, praat_textgrids as textgrids, parselmouth, statistics, random, string, sys, numpy
from parselmouth.praat import call

input_folder = sys.argv[1] # textgrids with tiers POS (first position), WOR, Nuclei
audio_folder = sys.argv[2]
output_folder = sys.argv[3]
cmu_dictionary = sys.argv[4] # Raw CMU dictionary cmudict-0.7b

time_step = 0.01 # (seconds) time step to measure F0 and intensity within the vowel (get value for each, linear) ex. a vowel of duration 40ms will have 4 F0/intensity measures in time_step=0.01

# In case of monosyllabic functional words (POS not in plainCategories), consider it is stressed if decile value >= functionWordDecileThreshold, else consider it's unstressed
functionWordDecileThreshold = 50 # 50 is the median prosodic value of the speaker

# Do the job for this number of files only (0=all)
test_limit = 0

stressCode = {
    "0":"o",
    "2":"o",
    "1":"O"
}

# List of potential vowel from MFA output
arpavowels = [ "AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW" ]

##################################################
#
# 1. Creation of the all word's prosodic shape dictionary from CMU Dictionary (ex. "effect":["oO","Oo"])
#
print("Creation of prosodic shapes dictionary from CMU Dictionary...")
gabarits = {}
with open(cmu_dictionary, 'r', encoding="latin1") as inf:
    for line in inf:
        if line.startswith(";;;"):
            continue
        line = line.strip()
        l = line.split('  ')
        if len(l)==2:
            w, t = l 
            w = re.sub(r'\(\d\)','', w.lower())
            gab = re.sub(r'[^012]','',t)
            if len(gab)>=1:
                if w not in gabarits.keys():
                    gabarits[w] = []
                if gab not in gabarits[w]:
                    gabarits[w].append(gab)   
        
print("OK")



##################################################
#
# 2. Parse TextGrid files, get corresponding WAVE files and make a new TextGrid with new tiers : ExpectedShape, ObservedShape, DetailedShape
#
spk2nbWsyll = {} # Number of target words per speaker (all words with matching count of syllable)
spk2nbWpluri = {} # Number of words per speaker
stressTable = []

# For statistics only:
spk2nbPlainPluri = {} # number of plain words per speaker
spk2nbPlainTargetWord = {} # number of plain target words per speaker
plainCategories = ["NOUN", "VERB", "ADV", "ADJ"] # Word categories to consider "plain words"

def getStressPosition(shapeString):
    # This function return the number of the first syllable that bears a stress
    # Example: shapeString="oOo" returns 2
    # Example: shapeString="Oo" returns 1
    # Example: shapeString="OoOO" returns 1
    # Example: shapeString="oo" returns 0
    for i,syll in enumerate(shapeString):
        if syll == stressCode["1"]:
            return i+1
    return 0

cpt = 0
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

    # READ CORRESPONDING WAVE FILE
    sound = parselmouth.Sound(audio_folder+file.replace(".TextGrid",".wav"))
    intensity = sound.to_intensity()
    pitch = sound.to_pitch()
    PitchTier = call(pitch, "Down to PitchTier")

    spk = re.sub(r"(_\d+)?\.TextGrid","",file)
    nbWplurisyll = 0
    nbWsyll = 0

    # For statistics only
    nbPlainPluri = 0
    nbPlainTargetWord = 0

    ########## Initialisation des tiers ExpectedShape, ObservedShape, DetailedShape
    d = textgrids.Interval()
    d.xmin, d.xmax, d.text = [grid.xmin, grid.xmax, ""]
    grid["ExpectedShape"] = textgrids.Tier()
    grid["ExpectedShape"].append(d)
    
    grid["ObservedShape"] = textgrids.Tier()
    grid["ObservedShape"].append(d)

    grid["DetailedShape"] = textgrids.Tier()
    grid["DetailedShape"].append(d)
    ###################################################

    # LOOP ON INTERVALLES → CHECK IF WORD IN DICTIONARY → ACOUSTIC MEASURES ON EACH SYLLABLE
    for i,intervalle in enumerate(grid['words']):
        lab = intervalle.text.transcode()
        deb = intervalle.xmin
        fin = intervalle.xmax
        if lab != "":

            # if the word is in the dictionnary
            if lab.lower() in gabarits.keys():
                if grid['POS'][i].text.transcode() in plainCategories: #### for statistics only
                    nbPlainPluri+=1 #### for statistics only
                nbWplurisyll+=1
                nbSyll=0
                syllnuclei = 0 # number of syllable nuclei detected within the word
                syllmfa_equals_syllnuclei = False # True if same number of syllable detected by MFA and syllable-nuclei_v3
                syllF0 = [] # list of each vowel F0 mean
                sylldB = [] # list of each vowel intensity peak
                sylldur = [] # list of each vowel interval duration
                phones = [] # list of phones within the current word
                vowelIntervals = [] # list of vowel intervals within the current word

                # on compte le nb de syllabes détectées par MFA
                for phone in grid['phones']:
                    if phone.xmin >= deb and phone.xmax <= fin:
                        phones.append(phone.text.transcode())
                        if phone.text.transcode()[:2] in arpavowels:
                            vowelIntervals.append(phone)
                            nbSyll+=1
                        
                ok = False
                # on compare le nb de syllabes avec le nombre de syllabes de chaque gabarits possibles
                for gab in gabarits[lab.lower()]:
                    if len(gab)==nbSyll:
                        ok=True
                        
                # THIS WORD = OK : ACOUSTIC MEASURES ON EACH SYLLABLE
                # si on trouve un gabarit avec le même nombre de syllabe => on pourra utiliser ce mot :D
                if ok:
                    if grid['POS'][i].text.transcode() in plainCategories: #### for statistics only
                        nbPlainTargetWord+=1 #### for statistics only
                    nbWsyll+=1

                    # on compte le nb de syllabes détectées par syllable-nuclei_v3 (juste pour info)
                    for syll in grid['Nuclei']:
                        if syll.xpos >= deb and syll.xpos <= fin:
                            syllnuclei+=1
                    if nbSyll == syllnuclei:
                        syllmfa_equals_syllnuclei = True

                    # GetPOS
                    posIntNb = call(tg, "Get interval at time...", 1, vowelIntervals[0].xmax-0.001)
                    pos = call(tg, "Get label of interval...", 1, posIntNb)


                    #################################################################
                    # Make ExpectedShape Interval
                    ## (add empty interval before if previous ends before this one starts)
                    n = textgrids.Interval()
                    n.xmin, n.xmax, n.text = [ grid['ExpectedShape'][-1].xmax, deb, "" ]
                    if grid['ExpectedShape'][-1].text != "" and grid['ExpectedShape'][-1].xmax < deb: grid['ExpectedShape'].append(n)

                    ## then add new ExpectedShape Interval
                    newInt = textgrids.Interval()
                    newInt.xmin = deb
                    newInt.xmax = fin
                    gabs = []
                    for gab in gabarits[lab.lower()]:
                        g = ""
                        for s in gab:
                            g+=stressCode[s]
                        gabs.append(g)

                    # SELECTION EXPECTEDSHAPE AMONG POSSIBLE SHAPES FOR THIS WORD
                    myGab = ""
                    if len(gabs)>1:
                        # Choix Nom/verb dans bisyllabiques
                        if gabs==["Oo","oO"] or gabs==["oO","Oo"]:
                            if pos in ["NOUN","ADJ"]: myGab = 'Oo'
                            elif pos == "VERB": myGab = 'oO'
                            else:
                                myGab = "/".join(gabs)

                        # Choix nb de syllabes si syllabe optionnelle
                        else:
                            for gab in gabs:
                                if len(gab)==nbSyll: myGab = gab
                    else:
                        myGab = "/".join(gabs)

                    expectedShapes = "/".join(gabs)
                    expectedShape = myGab

                    # EDIT HERE: in case of monosyllabic words: if plain: expect stressed syllable, else expect unstressed syllable
                    if len(expectedShape)==1:
                        if pos not in plainCategories:
                            expectedShape = "o"

                    newInt.text = expectedShape
                    grid['ExpectedShape'].append(newInt)
                    #################################################################


                    #################################################################
                    # Make DetailedShape Interval (F0 Intensity Duration)
                    ## (add empty interval before if previous ends before this one starts)
                    n = textgrids.Interval()
                    n.xmin, n.xmax, n.text = [ grid['DetailedShape'][-1].xmax, deb, "" ]
                    if grid['DetailedShape'][-1].text != "" and grid['DetailedShape'][-1].xmax < deb: grid['DetailedShape'].append(n)

                    ## then add new DetailedShape Interval : ex. oO oo Oo for rising pitch, flat intensity and long-short duration
                    newInt = textgrids.Interval()
                    newInt.xmin = deb
                    newInt.xmax = fin

                    ### F0, Intensity, duration
                    #### Get F0 & intensity measures from audio
                    for s in vowelIntervals:
                        F0list = [call(PitchTier, "Get value at time...", x) for x in numpy.arange(s.xmin, s.xmax, time_step)]
                        F0 = statistics.mean(F0list)
                        F0min, F0max = min(F0list), max(F0list)
                        if len(F0list)>1:
                            F0sd = statistics.stdev(F0list)
                        else:
                            F0sd = F0min
                        
                        dBlist = [call(intensity, "Get value at time...", x, "Linear") for x in numpy.arange(s.xmin, s.xmax, time_step)]
                        dB = max(dBlist) # let's keep only maximum intensity here
                        
                        syllF0.append(F0)
                        sylldB.append(dB)

                        ### Duration
                        sylldur.append(s.xmax-s.xmin)

                    
                    newInt.text = " "
                    
                    grid['DetailedShape'].append(newInt)
                    #################################################################


                    #################################################################
                    # Make ObservedShape Interval (MERGED F0 INT DUR)
                    ## (add empty interval before if previous ends before this one starts)
                    n = textgrids.Interval()
                    n.xmin, n.xmax, n.text = [ grid['ObservedShape'][-1].xmax, deb, "" ]
                    if grid['ObservedShape'][-1].text != "" and grid['ObservedShape'][-1].xmax < deb: grid['ObservedShape'].append(n)

                    ## then add new ObservedShape Interval : ex. oO oo Oo for rising pitch, flat intensity and long-short duration
                    newInt = textgrids.Interval()
                    newInt.xmin = deb
                    newInt.xmax = fin


                    # GENERATE A UNIQUE TOKEN TO RETRIEVE THE DATA IN STRESSTABLE
                    wid = ''.join(random.choices(string.ascii_lowercase + string.ascii_uppercase + string.digits, k=7))
                    newInt.text = wid
                    grid['ObservedShape'].append(newInt)
                    #################################################################

                    # SAVE INFO IN STRESSTABLE
                    stressTable.append({
                        "id":wid,
                        "spk":spk,
                        "lab":lab,
                        "pos":pos,
                        "lenSyllxpos":len(vowelIntervals),
                        "expectedShapes":expectedShapes,
                        "expectedShape":expectedShape,
                        "mergedShape":"", #mergedShape,
                        "deciles":[], #distMed,
                        "F0shape":"", #F0shape,
                        "dBshape":"", #dBshape,
                        "durshape":"", #durshape,
                        "syllF0":syllF0,
                        "F0deciles":[], #F0distMed,
                        "sylldB":sylldB,
                        "dBdeciles":[], #dBdistMed,
                        "sylldur":sylldur,
                        "durdeciles":[], #durdistMed,
                        "deb":deb,
                        "fin":fin,
                        "file":file,
                        "syllmfa_equals_syllnuclei": syllmfa_equals_syllnuclei,
                        "F0min":F0min,
                        "F0max":F0max,
                        "F0sd": F0sd,
                        "expectedStressPosition": getStressPosition(expectedShape),
                        "observedStressPosition": ""
                    })
                   

    # Finalisation des nouvelles tiers
    f = textgrids.Interval()
    f.xmin, f.xmax, f.text = [grid.xmin, grid.xmax, ""]
    if len(grid['ExpectedShape'])>1: grid['ExpectedShape'].append(f)
    if len(grid['ObservedShape'])>1: grid['ObservedShape'].append(f)
    if len(grid['DetailedShape'])>1: grid['DetailedShape'].append(f)

    if len(grid['ExpectedShape'])>1: grid['ExpectedShape'][0].xmax = grid['ExpectedShape'][1].xmin
    if len(grid['ExpectedShape'])>2: grid['ExpectedShape'][-1].xmin = grid['ExpectedShape'][-2].xmax
    if len(grid['DetailedShape'])>2: grid['DetailedShape'][-1].xmin = grid['DetailedShape'][-2].xmax

    if len(grid['ObservedShape'])>1: grid['ObservedShape'][0].xmax = grid['ObservedShape'][1].xmin
    if len(grid['ObservedShape'])>2: grid['ObservedShape'][-1].xmin = grid['ObservedShape'][-2].xmax
    if len(grid['DetailedShape'])>2: grid['DetailedShape'][-1].xmin = grid['DetailedShape'][-2].xmax

    # print(file, nbWplurisyll, nbWsyll)

    # Statistiques par locuteur
    if spk not in spk2nbWsyll.keys():
        spk2nbWsyll[spk] = 0
    spk2nbWsyll[spk]+=nbWsyll

    if spk not in spk2nbWpluri.keys():
        spk2nbWpluri[spk] = 0
    spk2nbWpluri[spk]+=nbWplurisyll

    if spk not in spk2nbPlainPluri.keys(): #### For statistics only
        spk2nbPlainPluri[spk] = 0
    spk2nbPlainPluri[spk]+=nbPlainPluri

    if spk not in spk2nbPlainTargetWord.keys(): #### For statistics only
        spk2nbPlainTargetWord[spk] = 0
    spk2nbPlainTargetWord[spk]+=nbPlainTargetWord

    outFile = file
    grid.write(output_folder+outFile)

    ### CHANGER LA CLASSE PointTier en TextTier (nouvelle syntaxe de Praat)
    with open(output_folder+ outFile, 'r') as outf:
        fifi = outf.read()
        fifi = fifi.replace('class = "PointTier"','class = "TextTier"')
    
    with open(output_folder+ outFile, 'w') as outf:
        outf.write(fifi)



##################################################
#
# 3. Make decile scale for F0, intensity, duration for each speaker
#
# CALCUL DES DÉCILES POUR CHAQUE PARAMÈTRE PROSODIQUE
# plutôt que d'afficher le pourcentage d'augmentation/diminution par rapport à la moyenne(min,max) des syllabes de chaque mot
# calculer les déciles de chaque dimension pour chaque locuteur.
# Il est plus facile de faire ce calcul maintenant, une fois que tous les mots cibles de chaque locuteur ont été analysés
spk2vals = {} # pour chaque locuteur → pour chaque dimension → liste de toutes les valeurs observées
spk2deciles = {} # pour chaque locuteur → pour chaque dimension → liste des valeurs de déciles

for stress in stressTable:
    spk = stress['spk']
    if spk not in spk2vals.keys(): spk2vals[spk] = { 'syllF0':[], 'sylldB':[], 'sylldur':[] }

    for dim in ["syllF0","sylldB","sylldur"]:
        for value in stress[dim]:
            spk2vals[spk][dim].append(value)

for spk in spk2vals.keys():
    spk2deciles[spk] = { 'decsF0':[], 'decsdB':[], 'decsdur':[] }

    for dim in ["syllF0","sylldB","sylldur"]:
        deciles = statistics.quantiles(spk2vals[spk][dim], n=100) # CENTILES au lieu de décile pour éviter ambiguïtés du type oOO
        spk2deciles[spk][dim.replace('syll','decs')] = [min(spk2vals[spk][dim])] + deciles + [max(spk2vals[spk][dim])]

# print("Centiles per dimension for each speaker:")
# for spk,dim2decs in spk2deciles.items():
#     print(spk)
#     for dim,decs in dim2decs.items():
#         print('\t',dim,decs)

def getDecileNb(val,listDecs):
    # for a given val, return the nb of decile from a list of deciles [min, d1up, d2up, d3up, ... d9up, max]
    # #decile=0,1,2,3...99
    for d,upperBoundary in enumerate(listDecs):
        if val < upperBoundary:
            return d-1
        if d==100 and val == upperBoundary:
            return 99
###########


##################################################
#
# 4. Loop on new TextGrids and inject prosodic shape (o/O) from decile values of each dimension (DetailedShape) + mean of the 3 dimensions (ObservedShape)
#
print("Loop on generated TextGrid to inject prosodic shape computed from deciles...")
for file in os.listdir(output_folder):
    # READ INPUT TEXTGRID FILE
    print("Processing",file,"...")
    try:
        grid = textgrids.TextGrid(output_folder+file)
    except:
        print("Unable to open the file!!")
        continue

    tg = call("Read from file...", output_folder+file)

    for i,intervalle in enumerate(grid['ObservedShape']):

        if intervalle.text!="":
            # Get ID Token
            token = intervalle.text
            w = [row for row in stressTable if row['id']==token][0]

            decF0  = [ getDecileNb(x,spk2deciles[w['spk']]['decsF0']) for x in w['syllF0'] ]
            decdB = [ getDecileNb(x,spk2deciles[w['spk']]['decsdB']) for x in w['sylldB'] ]
            decdur = [ getDecileNb(x,spk2deciles[w['spk']]['decsdur']) for x in w['sylldur'] ]
            try:
                decAll = [ round(statistics.mean([x,y,z]),1) for x,y,z in zip(decF0,decdB,decdur) ] # ARRONDI À UNE DÉCIMALE
            except:
                decAll = []

            w["F0deciles"], w["dBdeciles"], w["durdeciles"], w["deciles"] = decF0, decdB, decdur, decAll

            Allshape, F0shape, dBshape, durshape = "", "", "", ""

            for sF0, sdB, sdur, sAll in zip(decF0, decdB, decdur, decAll):
                if len(decAll)>1:
                    if sF0 == max(decF0): F0shape+=stressCode["1"] 
                    else: F0shape+=stressCode["0"]
                    if sdB == max(decdB): dBshape+=stressCode["1"] 
                    else: dBshape+=stressCode["0"]
                    if sdur == max(decdur): durshape+=stressCode["1"] 
                    else: durshape+=stressCode["0"]
                    if sAll == max(decAll): Allshape+=stressCode["1"] 
                    else: Allshape+=stressCode["0"]
                # EDIT: in case of monosyllabic word, indicate stressed syllable if decile value >= functionWordDecileThreshold, else consider it's unstressed
                elif len(decAll)==1:
                    if sF0 >= functionWordDecileThreshold: F0shape+=stressCode["1"] 
                    else: F0shape+=stressCode["0"]
                    if sdB >= functionWordDecileThreshold: dBshape+=stressCode["1"]
                    else: dBshape+=stressCode["0"]
                    if sdur >= functionWordDecileThreshold: durshape+=stressCode["1"] 
                    else: durshape+=stressCode["0"]
                    if sAll >= functionWordDecileThreshold: Allshape+=stressCode["1"] 
                    else: Allshape+=stressCode["0"]

            w["mergedShape"], w["F0shape"], w["dBshape"], w["durshape"] = Allshape, F0shape, dBshape, durshape   
            w["observedStressPosition"] = getStressPosition(Allshape)      
            
            intervalle.text = Allshape
            grid['DetailedShape'][i].text = " ".join([F0shape, dBshape, durshape])
            

    outFile = file
    grid.write(output_folder+outFile)

    ### CHANGER LA CLASSE PointTier en TextTier (nouvelle syntaxe de Praat)
    with open(output_folder+ outFile, 'r') as outf:
        fifi = outf.read()
        fifi = fifi.replace('class = "PointTier"','class = "TextTier"')
    
    with open(output_folder+ outFile, 'w') as outf:
        outf.write(fifi)



##################################################
#
# 5. Export stressTable.csv
#
print('Export stressTable.csv...')
with open('stressTable.csv','w') as st:
    st.write(";".join([
        "spk",
        "lab",
        "pos",
        "lenSyllxpos",
        "expectedShapes",
        "expectedShape",
        "observedShape",
        "expectedStressPosition",
        "observedStressPosition",
        "expectedIsObserved",
        "globalDeciles",
        "stressSyllableDecile",
        "meanUnstressSyllablesDeciles",
        "F0shape",
        "dBshape",
        "durshape",
        "syllF0",
        "F0Deciles",
        "stressSyllableDecileF0",
        "meanUnstressSyllablesDecilesF0",
        "sylldB",
        "dBDeciles",
        "stressSyllableDeciledB",
        "meanUnstressSyllablesDecilesdB",
        "sylldur",
        "durDeciles",
        "stressSyllableDeciledur",
        "meanUnstressSyllablesDecilesdur",
        "F0min",
        "F0max",
        "F0sd",
        "syllmfa_equals_syllnuclei",
        "startTime",
        "endTime",
        "file",
        "ID"
    ])+"\n")
    for stress in stressTable:

        # Get the decile value of the expected stressed syllable, and the mean of deciles of other syllables
        deciles = [x for x in stress['deciles']]
        stressSyllableDecile = ""
        meanUnstressSyllablesDeciles = ""
        if stress['lenSyllxpos']>1:
            stressSyllableDecile = deciles.pop(stress["expectedStressPosition"]-1)
            meanUnstressSyllablesDeciles = statistics.mean(deciles)
        else:
            if stress["observedStressPosition"]==1:
                stressSyllableDecile = deciles[0]
                meanUnstressSyllablesDeciles = ""
            else:
                stressSyllableDecile = ""
                meanUnstressSyllablesDeciles = deciles[0]

        # Do the same for F0
        F0deciles = [x for x in stress['F0deciles']]
        stressSyllableDecileF0 = ""
        meanUnstressSyllablesDecilesF0 = ""
        if stress['lenSyllxpos']>1:
            stressSyllableDecileF0 = F0deciles.pop(stress["expectedStressPosition"]-1)
            meanUnstressSyllablesDecilesF0 = statistics.mean(F0deciles)
        else:
            if stress["F0shape"]==stressCode['1']:
                stressSyllableDecileF0 = F0deciles[0]
                meanUnstressSyllablesDecilesF0 = ""
            else:
                stressSyllableDecileF0 = ""
                meanUnstressSyllablesDecilesF0 = F0deciles[0]

        # Do the same for intensity
        dBdeciles = [x for x in stress['dBdeciles']]
        stressSyllableDeciledB = ""
        meanUnstressSyllablesDecilesdB = ""
        if stress['lenSyllxpos']>1:
            stressSyllableDeciledB = dBdeciles.pop(stress["expectedStressPosition"]-1)
            meanUnstressSyllablesDecilesdB = statistics.mean(dBdeciles)
        else:
            if stress["dBshape"]==stressCode['1']:
                stressSyllableDeciledB = dBdeciles[0]
                meanUnstressSyllablesDecilesdB = ""
            else:
                stressSyllableDeciledB = ""
                meanUnstressSyllablesDecilesdB = dBdeciles[0]

        # Do the same for Duration
        durdeciles = [x for x in stress['durdeciles']]
        stressSyllableDeciledur = ""
        meanUnstressSyllablesDecilesdur = ""
        if stress['lenSyllxpos']>1:
            stressSyllableDeciledur = durdeciles.pop(stress["expectedStressPosition"]-1)
            meanUnstressSyllablesDecilesdur = statistics.mean(durdeciles)
        else:
            if stress["durshape"]==stressCode['1']:
                stressSyllableDeciledur = durdeciles[0]
                meanUnstressSyllablesDecilesdur = ""
            else:
                stressSyllableDeciledur = ""
                meanUnstressSyllablesDecilesdur = durdeciles[0]

        st.write("{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{};{}\n"\
                        .format(stress['spk'],
                                stress['lab'],
                                stress['pos'],
                                stress['lenSyllxpos'],
                                stress['expectedShapes'],
                                stress['expectedShape'],
                                stress['mergedShape'],
                                stress['expectedStressPosition'],
                                stress['observedStressPosition'],
                                "1" if stress['expectedShape']==stress['mergedShape'] else "0",
                                ", ".join([str(x) for x in stress['deciles']]),
                                stressSyllableDecile,
                                meanUnstressSyllablesDeciles,
                                stress['F0shape'],
                                stress['dBshape'],
                                stress['durshape'],
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['syllF0']]),
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['F0deciles']]),
                                stressSyllableDecileF0,
                                meanUnstressSyllablesDecilesF0,
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['sylldB']]),
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['dBdeciles']]),
                                stressSyllableDeciledB,
                                meanUnstressSyllablesDecilesdB,
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['sylldur']]),
                                ", ".join([str(round(x,3) if isinstance(x, float) else x) for x in stress['durdeciles']]),
                                stressSyllableDeciledur,
                                meanUnstressSyllablesDecilesdur,
                                str(round(stress['F0min'],3)),
                                str(round(stress['F0max'],3)),
                                str(round(stress['F0sd'],3)),
                                stress['syllmfa_equals_syllnuclei'],
                                stress['deb'],
                                stress['fin'],
                                stress['file'],
                                stress['id']))


print("DONE.")


##################################################
#
# 6. Export speakers.csv
#
print('Export speakers.csv...')
with open('speakers.csv','w') as st:
    st.write("speakerID\n")
    for spk in spk2nbWpluri.keys():
        st.write("{}\n".format(spk))
print("DONE.")


# PRINT SOME STATS
print("Number of target word per speaker (total of plurisyllabic words):")
with open('nbWords_perSpeaker.csv', "w") as outf:
    print("Speaker\tNumberTargetWords\tNumberPolysyllabicWords\tNumberPlainTargetWord\tNumberPlainPolysyllabicWords")
    outf.write(";".join(["Speaker","NumberTargetWords","NumberPolysyllabicWords","NumberPlainTargetWord","NumberPlainPolysyllabicWords"])+"\n")
    for s,n in spk2nbWsyll.items():
        print(s,n,spk2nbWpluri[s],spk2nbPlainTargetWord[s],spk2nbPlainPluri[s])
        outf.write(";".join([ str(x) for x in [s,n,spk2nbWpluri[s],spk2nbPlainTargetWord[s],spk2nbPlainPluri[s]] ])+"\n")