import numpy as np
import networkx as nx
import spacy

nlp = spacy.load("en_core_web_sm")

# ---------- Sentence Similarity ----------
def sentence_similarity(sent1: str, sent2: str) -> float:
    doc1 = nlp(sent1)
    doc2 = nlp(sent2)

    vec1 = doc1.vector
    vec2 = doc2.vector

    if np.linalg.norm(vec1) == 0 or np.linalg.norm(vec2) == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

# ---------- Similarity Matrix ----------
def build_similarity_matrix(sentences: list) -> np.ndarray:
    size = len(sentences)
    sim_matrix = np.zeros((size, size))

    for i in range(size):
        for j in range(size):
            if i != j:
                sim_matrix[i][j] = sentence_similarity(sentences[i], sentences[j])

    return sim_matrix

# ---------- Information Boost ----------
def information_boost(sentence: str) -> float:
    doc = nlp(sentence)
    boost = 0.0

    # Named Entity Boost
    for ent in doc.ents:
        if ent.label_ in ["DATE", "TIME"]:
            boost += 0.3
        elif ent.label_ == "MONEY":
            boost += 0.3
        elif ent.label_ in ["GPE", "ORG"]:
            boost += 0.3

    # Keyword Boost
    keywords = [
        "deadline", "due", "meeting", "schedule",
        "submit", "payment", "budget", "action",
        "required", "please", "kindly", "confirm"
    ]
    deadline_words = ["by", "before", "due", "deadline"]

    for word in deadline_words:
        if word in sentence.lower():
           boost += 0.30

    location_patterns = [" at ", " in "]

    for pattern in location_patterns:
        if pattern in sentence.lower():
            boost += 0.30

    for word in keywords:
        if word in sentence.lower():
            boost += 0.1

    # Action Verb Boost
    action_verbs = ["review", "complete", "send", "prepare", "approve","submit"]

    for token in doc:
        if token.lemma_.lower() in action_verbs:
            boost += 0.15

    return boost

# ---------- Action Sentence Detector ----------
def is_action_sentence(sentence: str) -> bool:
    doc = nlp(sentence)

    action_verbs = [
        "review", "complete", "send", "prepare",
        "approve", "submit", "confirm", "provide",
        "ensure", "kindly", "please","must","required"
    ]

    for token in doc:
        if token.lemma_.lower() in action_verbs:
            return True

    return False


    # ---------- Mandatory Info Detector ----------
def is_mandatory_sentence(sentence: str) -> bool:
    doc = nlp(sentence)

    # 🔹 1. Factual Entities (Date / Time / Money)
    for ent in doc.ents:
        if ent.label_ in ["DATE", "TIME", "MONEY"]:
            return True

    # 🔹 2. Action Sentences
    if is_action_sentence(sentence):
        return True

    # 🔹 3. Critical Keywords
    critical_patterns = [
        "meeting details",
        "date:",
        "time:",
        "budget",
        "cost",
        "$",
        "am",
        "pm",
        "ist",
        "deadline",
        "submit",
        "presentation"
    ]

    s = sentence.lower()
    for p in critical_patterns:
        if p in s:
            return True

    return False



# ---------- TextRank Extractive Summariser ----------
def extractive_summarize(sentences: list, top_n: int = 3) -> str:

    if len(sentences) <= top_n:
        return " ".join(sentences)

    # ---------- STEP 1: Collect mandatory sentences ----------
    mandatory = []
    remaining = []

    for s in sentences:
        if is_mandatory_sentence(s):
            mandatory.append(s)
        else:
            remaining.append(s)

    # If mandatory sentences already fill the quota, return them
    if len(mandatory) >= top_n:
        return " ".join(mandatory[:top_n])

    # ---------- STEP 2: Rank remaining sentences ----------
    sim_matrix = build_similarity_matrix(remaining)

    for i, sentence in enumerate(remaining):
        base_score = scores[i]


    graph = nx.from_numpy_array(sim_matrix)
    scores = nx.pagerank(graph)

    ranked_sentences = []

    ranked_sentences = []

    for i, sentence in enumerate(remaining):
        base_score = scores[i]
        boost = information_boost(sentence)
        final_score = base_score + boost
        ranked_sentences.append((final_score, sentence))


    ranked_sentences.sort(reverse=True)

    # ---------- STEP 3: Fill remaining slots ----------
    needed = top_n - len(mandatory)
    selected = [s for (_, s) in ranked_sentences[:needed]]

    final_summary = []

    final_summary = []
    added = set()

    for s in sentences:
        if (s in mandatory or s in selected) and s not in added:
            final_summary.append(s)
            added.add(s)



    return " ".join(final_summary)
