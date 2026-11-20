"""Reproducible comparison for the two sentences supplied by the user."""
import json,re,unicodedata
from pathlib import Path

def normalize(text):
    text=re.sub(r'\[[^\]]*\]','',text).split('所以')[0]
    return ''.join(c.lower() for c in text if unicodedata.category(c)[0] in ('L','N'))

def edits(reference,hypothesis):
    row=list(range(len(hypothesis)+1))
    for i,a in enumerate(reference,1):
        current=[i]
        for j,b in enumerate(hypothesis,1):current.append(min(current[-1]+1,row[j]+1,row[j-1]+(a!=b)))
        row=current
    return row[-1]

