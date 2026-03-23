import re
import spacy
from nltk.tokenize import sent_tokenize

nlp = spacy.load("en_core_web_sm")

def remove_signature(text: str):
    """
    Remove common email signature endings
    """
    signature_patterns = [
        r"Best,\s*\n.*",
        r"Regards,\s*\n.*",
        r"Thanks,\s*\n.*",
        r"Sincerely,\s*\n.*"
    ]

    for pattern in signature_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)

    return text

def separate_subject(text: str):
    """
    Keep subject separate if present
    """
    subject = None

    match = re.search(r"Subject:(.*)", text, re.IGNORECASE)
    if match:
        subject = match.group(1).strip()

    return subject

def clean_email(text: str) -> str:
    text = re.sub(r'\r', '', text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def split_sentences(text: str):
    """
    Better segmentation:
    remove subject line first to avoid merging
    """
    text = re.sub(r"Subject:.*\n", "", text, flags=re.IGNORECASE)
    return sent_tokenize(text)

def extract_entities(text: str):
    doc = nlp(text)

    entities = {
        "DATE": [],
        "TIME": [],
        "MONEY": [],
        "GPE": [],
        "PERSON": [],
        "ORG": []
    }

    for ent in doc.ents:
        if ent.label_ in entities:
            entities[ent.label_].append(ent.text)

    return entities

def filter_noise_sentences(sentences):
    """
    Remove greeting words from beginning,
    but keep the sentence if it contains useful info.
    """

    greeting_patterns = [
        r"^(dear\s+\w+,?\s*)",
        r"^(hi\s+\w*,?\s*)",
        r"^(hello\s+\w*,?\s*)"
    ]

    cleaned_sentences = []

    for sent in sentences:
        new_sent = sent.strip()

        # Remove greeting only at start
        for pattern in greeting_patterns:
            new_sent = re.sub(pattern, "", new_sent, flags=re.IGNORECASE)

        # Keep sentence if still meaningful
        if len(new_sent.split()) > 2:
            cleaned_sentences.append(new_sent)

    return cleaned_sentences

def clean_injected_sentence(sentence: str) -> str:
    """
    Clean awkward fragments produced by entity injection.
    """
    sentence = sentence.strip()

    # Remove label-only fragments like "Organization:"
    sentence = re.sub(r"^(date|time|budget|organization|location)\s*:\s*$",
                      "",
                      sentence,
                      flags=re.IGNORECASE)

    # Remove salutation leakage
    sentence = re.sub(r"\b(dear\s+\w+[,!]?)\b",
                      "",
                      sentence,
                      flags=re.IGNORECASE)

    # Remove double spaces
    sentence = re.sub(r"\s{2,}", " ", sentence)

    return sentence.strip()


def preprocess_email(text: str):

    subject = separate_subject(text)

    text = remove_signature(text)
    cleaned = clean_email(text)
    sentences = split_sentences(cleaned)
    sentences = filter_noise_sentences(sentences)
    entities = extract_entities(cleaned)
    entities = clean_entities(entities)

    return {
        "subject": subject,
        "cleaned_text": cleaned,
        "sentences": sentences,
        "entities": entities
    }
def clean_entities(entities):
    filtered = {}

    for label, values in entities.items():
        cleaned = []

        for v in values:
            v = v.strip()

            if len(v) < 3:
                continue
            if v.lower() in {"annual", "dear team"}:
                continue

            cleaned.append(v)

        filtered[label] = cleaned

    return filtered