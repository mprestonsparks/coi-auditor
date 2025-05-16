from spellchecker import SpellChecker
import re

spell = SpellChecker()

# find those words that may be misspelled
words = ["certif1cate", "liabi1ity", "subrogation", "indemnify", "ACORD"]

misspelled = spell.unknown(words)

for word in misspelled:
    # Get the suggested correction
    correction = spell.correction(word)

    # Apply rule-based corrections
    if word == "certif1cate":
        correction = "certificate"
    elif word == "liabi1ity":
        correction = "liability"
    elif word == "ACORD":
        correction = "ACORD"  # Keep ACORD as is

    print(f"Misspelled word: {word}, Correction: {correction}")