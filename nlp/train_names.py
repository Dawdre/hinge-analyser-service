import csv
import os
import random

import spacy
from spacy.tokens import DocBin
from tqdm import tqdm

nlp = spacy.blank("en")
db = DocBin()
TRAIN_DATA = []


def load_or_create_ner():
    if True:
        nlp1 = spacy.load(r".\nlp-output\model-best")
        doc = nlp1(
            "sup Gemma what is happening? Sophie and i are going to see Olivia")
        for blah in doc.ents:
            print(blah.label_, blah.text)
    else:
        create_ner()


def fluff(person: str):
    random_fluff = [
        "Hi {}",
        "Hey {}, how are you?",
        "How are you {}?",
        "You are very pretty {}",
        "Hello {}, how are you?",
        "Yes {}",
        "No {}"
    ]
    choice: str = random.choice(random_fluff).format(person)
    choice.lower().strip(",.?!")
    start = choice.find(person)
    end = start + len(person)
    print(choice, start, end)

    return (
        choice,
        {"entities": [(start, end, 'person')]}
    )


def create_ner():
    with open('names.csv', mode='r') as file:
        csv_file = csv.reader(file)
        for lines in csv_file:
            TRAIN_DATA.append(fluff(lines[2]))

    for text, annot in tqdm(TRAIN_DATA):
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annot['entities']:
            span = doc.char_span(start, end, label=label, alignment_mode="contract")
            if span is None:
                print("Skipping entity")
            else:
                ents.append(span)
        doc.ents = ents
        db.add(doc)

    os.chdir(r'./')
    db.to_disk("./train.spacy")
