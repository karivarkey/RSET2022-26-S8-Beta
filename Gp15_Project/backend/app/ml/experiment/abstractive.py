import re
from transformers import BartTokenizer, BartForConditionalGeneration
import torch

from src.grounding_filter import remove_ungrounded_lines
from src.evaluation import fact_retention_score
from src.preprocess import clean_injected_sentence

MODEL_NAME = "facebook/bart-large-cnn"

tokenizer = BartTokenizer.from_pretrained(MODEL_NAME)
model = BartForConditionalGeneration.from_pretrained(MODEL_NAME)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = model.to(device)

# --------------------------------------------------
# ✅ Normalize helper
# --------------------------------------------------
def normalize(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())

# --------------------------------------------------
# ✅ Sentence split helper
# --------------------------------------------------
def split_sentences(text: str):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]

# --------------------------------------------------
# ✅ Deduplicate
# --------------------------------------------------
def deduplicate_sentences(text: str) -> str:
    sentences = split_sentences(text)
    seen = set()
    cleaned = []

    for s in sentences:
        norm = normalize(s)
        if norm and norm not in seen:
            cleaned.append(s)
            seen.add(norm)

    return " ".join(cleaned)

# --------------------------------------------------
# ✅ Collect missing entity sentences FROM SOURCE
# --------------------------------------------------
def collect_missing_entity_sentences(extractive: str,
                                     original_email: str,
                                     entities: dict):

    extractive_norm = normalize(extractive)
    source_sentences = split_sentences(original_email)

    additions = []

    for label, values in entities.items():
        for v in values:

            # already present in extractive → skip
            if normalize(v) in extractive_norm:
                continue

            for sent in source_sentences:
                if normalize(v) in normalize(sent):

                    cleaned = clean_injected_sentence(sent)
                    if not cleaned:
                        continue

                    additions.append(cleaned)
                    break

    return list(dict.fromkeys(additions))

# --------------------------------------------------
# ✅ Build FULL TEXT TO REWRITE
# --------------------------------------------------
def build_full_rewrite_input(extractive_summary,
                             original_email,
                             entities):

    extractive_sentences = split_sentences(extractive_summary)

    extra_sentences = collect_missing_entity_sentences(
        extractive_summary,
        original_email,
        entities
    )

    full_text = extractive_sentences + extra_sentences

    return " ".join(full_text)

# --------------------------------------------------
# ✅ Abstractive rewrite (PURE PARAPHRASE MODE)
# --------------------------------------------------
def abstractive_rewrite(prompt: str,
                        original_email: str,
                        extractive_summary: str,
                        entities: dict) -> str:

    # 🔹 Build FULL text that must appear in output
    full_input = build_full_rewrite_input(
        extractive_summary,
        original_email,
        entities
    )

    # 🔹 Send THAT to the model (not just prompt)
    inputs = tokenizer(
        full_input,
        max_length=1024,
        truncation=True,
        return_tensors="pt"
    ).to(device)

    input_len = inputs["input_ids"].shape[1]

    min_len = int(input_len * 0.9)
    max_len = int(input_len * 1.2)

    summary_ids = model.generate(
        inputs["input_ids"],
        num_beams=2,
        max_length=max_len,
        min_length=min_len,
        length_penalty=1.0,
        repetition_penalty=1.05,
        early_stopping=False
    )

    rewritten = tokenizer.decode(
        summary_ids[0],
        skip_special_tokens=True
    )

    # 🔹 Remove hallucinated content
    grounded = remove_ungrounded_lines(
        rewritten,
        original_email
    )

    # 🔹 Remove duplicates
    grounded = deduplicate_sentences(grounded)

    # 🔹 Safety fallback
    if fact_retention_score(entities, grounded) < 0.6:
        return extractive_summary

    return grounded
