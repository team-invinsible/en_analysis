###############
#
# extra_pauseTagTagger.py
#
# This script parses all the TextGrid files from the shape/ directory along with the pauseTable.csv file.
# in each TextGrid file, it adds 2 new tiers:
# 1) a pauseType tier indicating the pause type: BC (between clause), BP (between phrase), or WP (within phrase)
# 2) a wordDist tier indicating the syntactic distance between words (number of closing and opening constituents)
#
# You need to set a minimum and maximum pause duration threshold.
#
# S. Coulange 2025

import re, os, textgrids, sys, copy

input_folder = sys.argv[1] # shape/ directory
pauseTableFilePath = sys.argv[2] # path and file name pointing to pauseTable.csv
output_folder = sys.argv[3] # output directory

# Do the job for this number of files only (0=all)
test_limit = 0

threshold = {
    "min": 0.180,
    "max": 2
}

def getPauseTableOfThisSegment(filename):
    # returns a list of <p:> intervalles corresponding to those contained in the TextGrid file called "filename".TextGrid
    pauseTable = []
    header = []

    # spk
    # file
    # i
    # POScontextLeft
    # POScontextRight
    # duration
    # wordLeft
    # wordLeftEndingLarger
    # wordLeftEndingLargerNb
    # wordLeftDepth
    # wordLeftTagw
    # boundaryStrength
    # wordRight
    # wordRightStartingLarger
    # wordRightStartingLargerNb
    # wordRightDepth
    # wordRightTagw
    # start
    # end

    with open(pauseTableFilePath, "r") as inf:
        header = inf.readline().strip().split(";")
        for line in inf:
            l = line.strip().split(";")
            if l[header.index("file")] == filename:
                pauseTable.append(l)

    return pauseTable, header
    
clauseLevel = ["S","SBAR","SBARQ","SINV","SQ"]
phraseLevel = ["ADJP","ADVP","CONJP","FRAG","INTJ","LST","NAC","NP","NX","PP","PRN","PRT","QP","RRC","UCP","VP","WHADJP","WHAVP","WHNP","WHPP","X"]

def getPauseType(p,header):
    # From a <p:> line of pauseTable.csv, returns BC, BP or WP depending on larger ending or starting constituent
    if p[header.index("wordLeftEndingLarger")] in clauseLevel or p[header.index("wordRightStartingLarger")] in clauseLevel:
        return "BC"
    elif p[header.index("wordLeftEndingLarger")] in phraseLevel or p[header.index("wordRightStartingLarger")] in phraseLevel:
        return "BP"
    else:
        return "WP"

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

    file = re.sub(r"(.merged.pos_shape)?.TextGrid","",file)
    spk = re.sub(r"_\d+$","",file)

    pauseTable, header = getPauseTableOfThisSegment(file)

    grid["pauseType"] = textgrids.Tier()

    for i,intervalle in enumerate(grid['WOR']):
        lab = intervalle.text
        dur = float(intervalle.xmax) - float(intervalle.xmin)
        
        if lab in ["<p:>", ""] and dur>=threshold["min"] and dur<threshold["max"]:
            # This is a pause, get corresponding <p:> in pauseTable
            p = []
            for pline in pauseTable:
                if float(pline[header.index("start")]) == round(float(intervalle.xmin),3):
                    p = pline
                    break
            
            ## (add empty interval before if previous ends before this one starts)
            n = textgrids.Interval()
            n.xmin, n.xmax, n.text = [grid['pauseType'][-1].xmax if len(grid['pauseType']) > 0 else 0, intervalle.xmin, ""]
            if len(grid['pauseType']) == 0 and float(intervalle.xmin) > 0: grid['pauseType'].append(n)
            elif len(grid['pauseType']) > 0 and grid['pauseType'][-1].text != "" and grid['pauseType'][-1].xmax < intervalle.xmin: grid['pauseType'].append(n)

            # Inject new data into TextGrid
            d = textgrids.Interval()
            d.xmin, d.xmax = [float(intervalle.xmin), float(intervalle.xmax)]
            d.text = getPauseType(p,header)
            grid["pauseType"].append(d)


    grid["wordDist"] = textgrids.Tier()

    for i,intervalle in enumerate(grid['WOR']):
        lab = intervalle.text
        
        if lab in ["<p:>", ""]:
            # This is a pause, get corresponding <p:> in pauseTable
            p = []
            for pline in pauseTable:
                if float(pline[header.index("start")]) == round(float(intervalle.xmin),3):
                    p = pline
                    break
                    
            ## (add empty interval before if previous ends before this one starts)
            n = textgrids.Interval()
            n.xmin, n.xmax, n.text = [grid['wordDist'][-1].xmax if len(grid['wordDist']) > 0 else 0, intervalle.xmin, ""]
            if len(grid['wordDist']) == 0 and float(intervalle.xmin) > 0: grid['wordDist'].append(n)
            elif len(grid['wordDist']) > 0 and grid['wordDist'][-1].text != "" and grid['wordDist'][-1].xmax < intervalle.xmin: grid['wordDist'].append(n)

            d = textgrids.Interval()
            d.xmin, d.xmax = [float(intervalle.xmin), float(intervalle.xmax)]
            d.text = p[header.index("boundaryStrength")]
            grid["wordDist"].append(d)


    # Finalisation des nouvelles tiers
    f = textgrids.Interval()
    f.xmin, f.xmax, f.text = [grid.xmin, grid.xmax, ""]
    if len(grid['pauseType'])==0: grid['pauseType'].append(f)
    if len(grid['wordDist'])==0: grid['wordDist'].append(f)

    if len(grid['pauseType'])>0 and grid['pauseType'][-1].xmax < grid.xmax: 
        f.xmin, f.xmax, f.text = [grid['pauseType'][-1].xmax, grid.xmax, ""]
        grid['pauseType'].append(f)
        
    if len(grid['wordDist'])>0 and grid['wordDist'][-1].xmax < grid.xmax: 
        f.xmin, f.xmax, f.text = [grid['wordDist'][-1].xmax, grid.xmax, ""]
        grid['wordDist'].append(f)
       

    grid.write(os.path.join(output_folder,file+".TextGrid"))
    
    ### CHANGER LA CLASSE PointTier en TextTier (nouvelle syntaxe de Praat)
    with open(os.path.join(output_folder,file+".TextGrid"), 'r') as outf:
        fifi = outf.read()
        fifi = fifi.replace('class = "PointTier"','class = "TextTier"')
    
    with open(os.path.join(output_folder,file+".TextGrid"), 'w') as outf:
        outf.write(fifi)


print(cpt,'files processed.')