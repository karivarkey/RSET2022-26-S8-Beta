import re

# --------------------------------------------------
# ✅ METRIC 1 — FACT RETENTION SCORE
# --------------------------------------------------
import re

def normalize(text):
    """Removes punctuation & spaces for robust matching"""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def fact_retention_score(entities: dict, generated: str):
    """
    Measures how many extracted entities appear in the final summary.
    More robust to formatting & punctuation differences.
    """

    total = 0
    found = 0

    gen_norm = normalize(generated)

    for key, values in entities.items():
        for v in values:
            total += 1

            if normalize(v) in gen_norm:
                found += 1

    if total == 0:
        return 1.0

    return found / total

# --------------------------------------------------
# ✅ METRIC 2 — COMPRESSION RATIO
# --------------------------------------------------
def compression_ratio(original: str, summary: str):
    orig_len = len(original.split())
    summ_len = len(summary.split())

    if orig_len == 0:
        return 0.0

    return summ_len / orig_len

# --------------------------------------------------
# ✅ METRIC 3 — COVERAGE SCORE (FINAL VERSION)
# --------------------------------------------------
def coverage_score(extractive: str, abstractive: str):
    ext_sents = [
        s.strip().lower()
        for s in re.split(r'[.!?]\s+', extractive)
        if s.strip()
    ]

    abs_words = set(abstractive.lower().split())

    matched = 0

    for sent in ext_sents:
        words = sent.split()

        # keep meaningful words only
        key_words = [w for w in words if len(w) > 4]

        if not key_words:
            continue

        overlap = sum(1 for w in key_words if w in abs_words)

        if overlap / len(key_words) >= 0.3:
            matched += 1

    if len(ext_sents) == 0:
        return 1.0

    return matched / len(ext_sents)

# --------------------------------------------------
# ✅ COMPARISON: BASELINE vs PIPELINE
# --------------------------------------------------
def print_comparison(original,
                     extractive_summary,
                     pipeline_summary,
                     entities):

    print("\n📊 BASELINE vs PIPELINE EVALUATION\n")

    # ----- Baseline (Extractive Only)
    base_fact = fact_retention_score(entities, extractive_summary)
    base_comp = compression_ratio(original, extractive_summary)
    base_cov = 1.0   # extractive covers itself

    # ----- Pipeline (Final Output)
    pipe_fact = fact_retention_score(entities, pipeline_summary)
    pipe_comp = compression_ratio(original, pipeline_summary)
    pipe_cov = coverage_score(extractive_summary, pipeline_summary)

    print("🔹 BASELINE (Extractive Only)")
    print(f"✔ Fact Retention Score : {base_fact:.2f}")
    print(f"✔ Compression Ratio    : {base_comp:.2f}")
    print(f"✔ Coverage Score       : {base_cov:.2f}")

    print("\n🔹 PIPELINE (Extractive → Abstractive → Grounded)")
    print(f"✔ Fact Retention Score : {pipe_fact:.2f}")
    print(f"✔ Compression Ratio    : {pipe_comp:.2f}")
    print(f"✔ Coverage Score       : {pipe_cov:.2f}")

    print("\n📈 Improvement Analysis:")

    print(f"- Fact Retention Change : {pipe_fact - base_fact:+.2f}")
    print(f"- Compression Change    : {pipe_comp - base_comp:+.2f}")
    print(f"- Coverage Consistency  : {pipe_cov:.2f}")

    print("\nInterpretation Guide:")
    print("✔ Higher Fact Retention → Better factual accuracy")
    print("✔ Compression ~0.3–0.6 → Ideal summary length")
    print("✔ Coverage >0.6 → Pipeline preserved extractive intent")
