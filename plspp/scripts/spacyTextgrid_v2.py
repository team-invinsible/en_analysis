################
#
# SpacyTextgrid.py
# Ajoute un intervalle de fin sur tier_words, puisque le .srt s'arrête au dernier mot et pas à tmax du fichier.
#
# input : TextGrid avec Tier tier_words, alignement de mots
#
# output : TextGrid avec nouvelle Tier (au début) "POS", part of speech du ou des mots correspondants (analysé par Spacy)
#
# S. Coulange 2022

import textgrids, os, spacy, copy, sys
# https://pypi.org/project/praat-textgrids/

input_folder = sys.argv[1]
output_folder = sys.argv[2]
spacy_model = sys.argv[3] # 'en_core_web_md'
tier_words = sys.argv[4] # "WOR"


print("Loading SpaCy model",spacy_model,"...")
nlpEn = spacy.load(spacy_model)
print("Done.")


for indx, file in enumerate(os.listdir(input_folder)):

    print("Processing",file,"...")
    try:
        grid = textgrids.TextGrid(input_folder+file)
    except:
        print("Unable to open the file!!")
        continue

    words = [] # liste des mots de l'intervalle "WOR" (text de chaque intervalle)
    code = [] # index de l'intervalle
    toks = [] # liste des tokens de l'output de Spacy
    package = [] # list de ('word','code','pos'), pos peut être = pos+pos

    for i,intervalle in enumerate(grid[tier_words]):
        lab = intervalle.text.transcode()
        if lab != "<p:>" and lab != "":
            words.append(lab)
            code.append(i)

    # print(" ".join(words))
    # print(" ".join([str(x) for x in code]))
    # print(" ".join(["{}{}".format(x,y) for x,y in zip(code,words)]))

    
    ### CREATION TIER POS (par duplication de la tier WOR)
    tierPOS = copy.deepcopy(grid[tier_words])
    grid['POS'] = tierPOS
    grid.move_to_end('POS', last=False)
    

    ### ANALYSE MORPHOSYNTAXIQUE
    nlpText = nlpEn(" ".join(words))
    for token in nlpText:
        toks.append(token)

    # print("WORDS:",words)
    # print("TOKS:",toks)

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
        fifi = outf.read()
        fifi = fifi.replace('class = "PointTier"','class = "TextTier"')
    
    with open(output_folder+ outFile, 'w') as outf:
        outf.write(fifi)

print('Done.')
