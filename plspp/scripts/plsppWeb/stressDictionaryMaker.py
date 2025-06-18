##################################################
# 
# stressDictionaryMaker.py
#
# Creation of the stress dictionary from the input phonetic dictionary (ex. "effect":["oO","Oo"])
#
# Input: 
#   - phonetic dictionary
#   - format of the phonetic dictionary ["CMU", "britfone", "custom"]
#
# S. Coulange 2025

import sys, re

def makeStressDictionaryCMU(dictionary):
    """
    Create a stress dictionary from a CMU phonetic dictionary.
    The CMU format is expected to have words followed by their phonetic representation.
    Expected format:
        ;;; Comment line
        CAMERA  K AE1 M ER0 AH0
        CAMERA(1)  K AE1 M R AH0
        CAMERA'S  K AE1 M R AH0 Z
        CAMERAMAN  K AE1 M ER0 AH0 M AH0 N
        CAMERAMEN  K AE1 M ER0 AH0 M EH0 N
        CAMERAS  K AE1 M ER0 AH0 Z
        CAMERAS(1)  K AE1 M R AH0 Z
    """
    stress_dict = {}
    with open(dictionary, 'r', encoding="latin1") as inf:
        for line in inf:
            if line.startswith(";;;"):
                continue
            line = line.strip()
            parts = line.split('  ')
            if len(parts) == 2:
                word, phonetic = parts
                # Remove any trailing digits or parentheses from the word
                word = re.sub(r'\(\d\)','', word.lower())
                # Keep only the stress pattern (digits)
                stress_pattern = re.sub(r'[^012]','',phonetic)
                
                # Add the stress pattern to the dictionary
                if word not in stress_dict:
                    stress_dict[word] = []
                if stress_pattern not in stress_dict[word]:
                    stress_dict[word].append(stress_pattern)
    return stress_dict

def makeStressDictionaryBritfone(dictionary):
    pass

def makeStressDictionaryCustom(dictionary):
    pass


def makeStressDictionary(dictionary, format):
    import re
    if format not in ["CMU", "britfone", "custom"]:
        raise ValueError("Format must be one of 'CMU', 'britfone', or 'custom'.")

    if format == "CMU":
        return makeStressDictionaryCMU(dictionary)
    elif format == "britfone":
        return makeStressDictionaryBritfone(dictionary)
    elif format == "custom":
        return makeStressDictionaryCustom(dictionary)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stressDictionaryMaker.py <dictionary_path> <format>")
        sys.exit(1)

    dictionary_path = sys.argv[1]
    format = sys.argv[2]

    stress_dict = makeStressDictionary(dictionary_path, format)

    # Export the stress dictionary to a file
    output_path = dictionary_path + "_stress_dict.txt"
    print(f"Exporting stress dictionary to {output_path}...")

    with open(output_path, 'w', encoding="utf-8") as outf:
        for word, patterns in stress_dict.items():
            outf.write(f"{word}: {', '.join(patterns)}\n")

    print("Stress dictionary created successfully.")