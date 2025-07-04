################
#
# tg2tgpos.py
# This script processes a TextGrid file to add a new tier for part of speech (POS) tagging.
# It uses the SpaCy library to analyze the words in the specified tier and outputs a new TextGrid file with the POS information.
#
# input: - input folder containing TextGrid with word alignments.
#        - output folder where the new TextGrid files will be saved.
#        - SpaCy model name (e.g., 'en_core_web_md').
#        - tier_words: the name of the tier containing word alignments.
#
# output: - TextGrid files with a new tier "POS" containing the part of speech tags for each word.
#
# S. Coulange 2025

import textgrids, os, spacy, copy, sys
# https://pypi.org/project/praat-textgrids/

input_folder = sys.argv[1]
output_folder = sys.argv[2]
spacy_model = sys.argv[3] # "en_core_web_md" "en_core_web_trf"
tier_words = sys.argv[4] # "WOR"


print("Loading SpaCy model",spacy_model,"...")
nlp = spacy.load(spacy_model)
print("Done.")

# Ensure output folder exists
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"Created output folder: {output_folder}")

# Process each TextGrid file in the input folder
if not os.path.exists(input_folder):
    print(f"Input folder does not exist: {input_folder}")
    sys.exit(1)
if not os.listdir(input_folder):
    print(f"Input folder is empty: {input_folder}")
    sys.exit(1)


for indx, file in enumerate(os.listdir(input_folder)):

    print("Processing",file,"...")
    try:
        grid = textgrids.TextGrid(input_folder+file)
    except:
        print("Unable to open the following TextGrid file:", file)
        continue

    words = [] # liste des mots de l'intervalle "WOR" (text de chaque intervalle)
    code = [] # index de l'intervalle
    toks = [] # liste des tokens de l'output de Spacy
    package = [] # list de ('word','code','pos'), pos peut être = pos+pos

    for i,intervalle in enumerate(grid[tier_words]):
        lab = intervalle.text.transcode()
        if lab not in ["<p:>",""]:
            words.append(lab)
            code.append(i)
    
    ### CREATION TIER POS (par duplication de la tier WOR)
    tierPOS = copy.deepcopy(grid[tier_words])
    grid['POS'] = tierPOS
    grid.move_to_end('POS', last=False)

    ### ANALYSE MORPHOSYNTAXIQUE
    nlpText = nlp(" ".join(words))
    for token in nlpText:
        toks.append(token)

    ### FUSION DES TOKENS FAISANT PARTIE D'UN SEUL INTERVALLE DANS TIER tier_words
    i = 0
    j = 0
    
    while i<len(toks):
        wordistok = False
        ctoks = ""
        cpos = []

        while not wordistok:
            if i>=len(toks):
                break

            ctoks += toks[i].text + toks[i].whitespace_
            cpos.append(toks[i].pos_)

            if ctoks.strip() == words[j]:
                package.append([words[j], code[j], "+".join(cpos)])
                wordistok = True
            
            else:
                i+=1
            
        j+=1
        i+=1


    ### RENSEIGNEMENT DE LA TIER POS
    for x in package:
        if grid['POS'][x[1]].text == x[0]:
            grid['POS'][x[1]].text = x[2]
        else:
            print('ERROR',x,grid['POS'][x[1]])
    

    ### ENREGISTREMENT DU NOUVEAU TEXTGRID
    outFile = file
    grid.write(output_folder+outFile)


    ### CHANGER LA CLASSE PointTier en TextTier (nouvelle syntaxe de Praat?)
    with open(output_folder+ outFile, 'r') as outf:
        temp = outf.read()
        temp = temp.replace('class = "PointTier"','class = "TextTier"')
    
    with open(output_folder+ outFile, 'w') as outf:
        outf.write(temp)

print('Done.')
