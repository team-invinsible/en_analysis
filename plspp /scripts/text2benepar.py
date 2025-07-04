import benepar, spacy, os, sys
import re
# https://github.com/nikitakit/self-attentive-parser
# https://spacy.io/universe/project/self-attentive-parser

input_folder = sys.argv[1] # text file of raw transcript
output_dir = sys.argv[2]
benepar_model = sys.argv[3] # 'benepar_en3'
spacy_model = sys.argv[4] # 'en_core_web_md'

# Do the job for this number of files only (0=all)
test_limit = 0


##################################################
#
# 1. Load Spacy & Benepar
#

# Download BENEPAR model if doesn't exist
benepar.download(benepar_model)

# Load SPACY + BENEPAR
nlp = spacy.load(spacy_model)
if spacy.__version__.startswith('2'):
    nlp.add_pipe(benepar.BeneparComponent(benepar_model))
else:
    nlp.add_pipe("benepar", config={"model": benepar_model})


##################################################
#
# Helper function to split text into chunks
#
def split_text_into_chunks(text, max_words=150):
    """
    Split text into smaller chunks to avoid token limit issues.
    Uses sentence boundaries when possible, otherwise splits by word count.
    """
    # First try to split by sentences
    sentences = re.split(r'[.!?]+\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Count approximate words in current chunk + new sentence
        current_words = len(current_chunk.split())
        sentence_words = len(sentence.split())
        
        # If this sentence alone is too long, split it by words
        if sentence_words > max_words:
            # Save current chunk if it exists
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # Split long sentence into word-based chunks
            words = sentence.split()
            for i in range(0, len(words), max_words):
                chunk_words = words[i:i + max_words]
                chunks.append(" ".join(chunk_words))
            continue
        
        # If adding this sentence would exceed limit, start new chunk
        if current_words + sentence_words > max_words and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += ". " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks


##################################################
#
# 2. Parse text files & run spacy+benepar
#

cpt = 0
for file in os.listdir(input_folder):
    
    if test_limit!=0 and cpt>test_limit: break
    else: cpt+=1
    
    text = ""
    print("Processing",file,"...")
    with open(input_folder+file, "r") as inf:
        text = inf.read()
        text = text.strip()

    # Split text into manageable chunks
    chunks = split_text_into_chunks(text, max_words=150)
    
    # Process each chunk separately
    all_parses = []
    for i, chunk in enumerate(chunks):
        try:
            print(f"  Processing chunk {i+1}/{len(chunks)} (words: {len(chunk.split())})")
            doc = nlp(chunk)
            
            # Collect parses from this chunk
            for sent in list(doc.sents):
                x = sent._.parse_string.replace("(","[").replace(")","]").replace("``","HYPH")
                all_parses.append(x)
                
        except Exception as e:
            print(f"  Warning: Error processing chunk {i+1}: {e}")
            # Continue with other chunks even if one fails
            continue

    # Export all parses to output file
    with open(output_dir + file + ".benepar", "w") as outf:
        for parse in all_parses:
            outf.write("{}\n".format(parse))
    
    print(f"  Completed: {len(all_parses)} sentences processed")
