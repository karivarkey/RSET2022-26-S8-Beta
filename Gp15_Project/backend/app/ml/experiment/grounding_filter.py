from sentence_transformers import SentenceTransformer, util
import re

sim_model = SentenceTransformer('all-MiniLM-L6-v2')

import re
from sentence_transformers import SentenceTransformer, util

# Load once (IMPORTANT)
sim_model = SentenceTransformer('all-MiniLM-L6-v2')

def contains_critical_info(sent: str) -> bool:
    sent_lower = sent.lower()

    critical_patterns = [
        r"\$\s?\d+",                 # money
        r"\d{1,2}:\d{2}",            # time
        r"\b(am|pm)\b",
        r"\b\d{1,2}(st|nd|rd|th)\b", # dates
        r"\bbudget\b",
        r"\bdeadline\b",
        r"\bhall\b",
        r"\bcampus\b",
        r"\bconference\b"
    ]

    return any(re.search(p, sent_lower) for p in critical_patterns)

def remove_ungrounded_lines(generated: str,
                            source: str,
                            threshold: float = 0.55) -> str:

    gen_sentences = re.split(r'(?<=[.!?])\s+|\n+', generated)
    src_sentences = re.split(r'(?<=[.!?])\s+|\n+', source)

    gen_sentences = [s.strip() for s in gen_sentences if s.strip()]
    src_sentences = [s.strip() for s in src_sentences if s.strip()]

    if not gen_sentences or not src_sentences:
        return generated

    src_embeddings = sim_model.encode(src_sentences, convert_to_tensor=True)

    kept_sentences = []

    for sent in gen_sentences:
        emb = sim_model.encode(sent, convert_to_tensor=True)
        scores = util.cos_sim(emb, src_embeddings)

        if scores.max().item() >= threshold or contains_critical_info(sent):
            kept_sentences.append(sent)

    if not kept_sentences:
        return generated

    return " ".join(kept_sentences)

