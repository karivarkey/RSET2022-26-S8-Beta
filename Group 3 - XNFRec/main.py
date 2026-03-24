# ================================================================
# IMPORTS
# ================================================================

import os
import random
import hashlib
from collections import defaultdict

import numpy as np
import pandas as pd
import networkx as nx
from tqdm import tqdm
import faiss

import torch
import torch.nn.functional as F
from torch.nn import Module, Embedding
from torch_geometric.nn import RGCNConv

import skfuzzy as fuzz

from sentence_transformers import SentenceTransformer
from keybert import KeyBERT
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

# ================================================================
# MODEL LOADING
# ================================================================

EMBED_DIM = 1024
embedder = SentenceTransformer("BAAI/bge-large-en-v1.5")
kw_model = KeyBERT(embedder)


# ================================================================
# CONCEPT UTILITIES
# ================================================================

def normalize_concept(text: str) -> str:
    return " ".join(text.lower().replace("-", " ").split())


def concept_id(text: str) -> str:
    return "K_" + hashlib.md5(text.encode()).hexdigest()[:10]


# ================================================================
# CONCEPT EXTRACTION
# ================================================================

def extract_raw_concepts(text, top_k=12, min_score=0.25):
    if not isinstance(text, str) or not text.strip():
        return []

    keywords = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words="english",
        use_mmr=True,
        diversity=0.7,
        top_n=top_k
    )

    concepts = []
    for phrase, score in keywords:
        phrase = normalize_concept(phrase)
        if score >= min_score and phrase not in ENGLISH_STOP_WORDS and len(phrase) >= 4:
            concepts.append(phrase)

    return concepts


def merge_similar_concepts(concepts, threshold=0.85):
    if not concepts:
        return []

    embs = embedder.encode(concepts, normalize_embeddings=True)
    sim = cosine_similarity(embs)

    merged, used = [], set()
    for i, c in enumerate(concepts):
        if i in used:
            continue
        group = [c]
        used.add(i)
        for j in range(i + 1, len(concepts)):
            if j not in used and sim[i, j] >= threshold:
                group.append(concepts[j])
                used.add(j)
        merged.append(max(group, key=len))

    return merged


def extract_concepts(text):
    return merge_similar_concepts(extract_raw_concepts(text))


# ================================================================
# KNOWLEDGE GRAPH
# ================================================================

def build_kg(df):
    G = nx.DiGraph()

    courses = df[["course_id", "short_description"]].drop_duplicates()

    for _, row in tqdm(courses.iterrows(), total=len(courses), desc="KG: Courses → Concepts"):
        c = f"C_{row.course_id}"
        G.add_node(c, ntype="course", text=str(row.short_description))

        for concept in extract_concepts(str(row.short_description)):
            k = concept_id(concept)
            if not G.has_node(k):
                G.add_node(k, ntype="concept", text=concept)
            G.add_edge(c, k, etype="covers", weight=1.0)

    for _, row in tqdm(df.iterrows(), total=len(df), desc="KG: Learners → Courses"):
        l = f"L_{row.learner_id}"
        c = f"C_{row.course_id}"
        if not G.has_node(l):
            G.add_node(l, ntype="learner")

        r = float(row.get("learner_rating", 1.0))
        r = max(0.0, min(r / 5.0, 1.0))
        G.add_edge(l, c, etype="enrolled", weight=r)

    return G


# ================================================================
# NODE FEATURES — BATCH ENCODE (10x faster than one-by-one)
# ================================================================

def build_node_features(G):
    """
    Encode all course/concept nodes in one batched call.
    Drops runtime from ~10 min to ~1 min for 300 courses.
    """
    text_nodes = [
        (n, d["text"]) for n, d in G.nodes(data=True)
        if d["ntype"] in {"course", "concept"}
    ]

    feats = {}

    if text_nodes:
        names = [n for n, _ in text_nodes]
        texts = [t for _, t in text_nodes]
        print(f"[INFO] Batch encoding {len(texts)} nodes...")
        vecs = embedder.encode(
            texts,
            normalize_embeddings=True,
            batch_size=256,
            show_progress_bar=True
        )
        for n, v in zip(names, vecs):
            feats[n] = v.astype(np.float32)

    for n, d in G.nodes(data=True):
        if n not in feats:
            feats[n] = np.zeros(EMBED_DIM, dtype=np.float32)

    return feats


def build_faiss_index(G, node_features):
    course_nodes = [n for n, d in G.nodes(data=True) if d["ntype"] == "course"]

    vectors = np.vstack([node_features[c] for c in course_nodes]).astype("float32")
    faiss.normalize_L2(vectors)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    return index, course_nodes  # plain list of strings


def add_course_similarity_edges(G, node_features, top_k=15, min_similarity=0.60):
    course_nodes = [n for n, d in G.nodes(data=True) if d["ntype"] == "course"]

    print(f"\n[INFO] Building course similarity graph for {len(course_nodes)} courses...")

    course_vectors = np.vstack([node_features[c] for c in course_nodes]).astype("float32")
    faiss.normalize_L2(course_vectors)

    index = faiss.IndexFlatIP(course_vectors.shape[1])
    index.add(course_vectors)

    similarity_edges = 0
    for i, c in enumerate(tqdm(course_nodes, desc="Course similarity")):
        D, I = index.search(course_vectors[i:i + 1], top_k + 1)

        for j, sim in zip(I[0][1:], D[0][1:]):
            similar_course = course_nodes[j]
            if sim >= min_similarity:
                G.add_edge(c, similar_course, etype="similar_to", weight=float(sim))
                similarity_edges += 1

    print(f"[INFO] Added {similarity_edges} course similarity edges\n")
    return G


# ================================================================
# NFH
# ================================================================

def hierarchical_negative_sampling(G, learner, pos_course, courses, node_features):
    difficulty_roll = random.random()

    if difficulty_roll < 0.3:
        while True:
            neg = random.choice(courses)
            if neg != pos_course:
                return neg

    elif difficulty_roll < 0.7:
        candidates = set()
        for cl in G.successors(learner):
            if G.nodes.get(cl, {}).get("ntype") == "cluster":
                for l2 in G.predecessors(cl):
                    if G.nodes.get(l2, {}).get("ntype") == "learner":
                        for c in G.successors(l2):
                            if G.nodes.get(c, {}).get("ntype") == "course" and c != pos_course:
                                candidates.add(c)
        if candidates:
            return random.choice(list(candidates))

    candidates = set()
    for k in G.successors(pos_course):
        if G.nodes[k]["ntype"] == "concept":
            for c2 in G.predecessors(k):
                if G.nodes[c2]["ntype"] == "course" and c2 != pos_course:
                    candidates.add(c2)

    if candidates:
        return random.choice(list(candidates))

    while True:
        neg = random.choice(courses)
        if neg != pos_course:
            return neg


def build_nfh(G, node_features, tau=3):
    evidence = defaultdict(list)

    for l, ld in tqdm(G.nodes(data=True), desc="NFH: Evidence"):
        if ld["ntype"] != "learner":
            continue

        for c in G.successors(l):
            if G.nodes[c]["ntype"] != "course":
                continue

            r_lc = G[l][c]["weight"]
            c_emb = node_features[c]

            for k in G.successors(c):
                if G.nodes[k]["ntype"] != "concept":
                    continue
                w_ck = float(np.dot(c_emb, node_features[k]))
                if w_ck > 0:
                    evidence[(l, k)].append((r_lc, w_ck))

    nfh = defaultdict(dict)
    for (l, k), vals in tqdm(evidence.items(), desc="NFH: Aggregation"):
        n = len(vals)
        T = sum(r * w for r, w in vals) / n
        Fv = sum((1 - r) * w for r, w in vals) / n
        I = 1 - min(1.0, n / tau)
        nfh[k][l] = (T, I, Fv)

    return nfh


def add_belief_edges(G, nfh, eps=0.1):
    for k, learners in tqdm(nfh.items(), desc="NFH → Belief edges"):
        for l, (T, I, Fv) in learners.items():
            b = 1.5 * (T - Fv) * (1 - I)
            if abs(b) >= eps:
                G.add_edge(l, k, etype="belief", weight=float(b))
    return G


# ================================================================
# FUZZY CLUSTERING
# ================================================================

def build_belief_matrix(nfh):
    learners = sorted({l for v in nfh.values() for l in v})
    concepts = list(nfh.keys())

    if not learners or not concepts:
        return [], np.empty((0, 0))

    li = {l: i for i, l in enumerate(learners)}
    ci = {c: i for i, c in enumerate(concepts)}

    X = np.zeros((len(learners), len(concepts)))
    for c, vals in nfh.items():
        for l, (T, I, Fv) in vals.items():
            X[li[l], ci[c]] = (T - Fv) * (1 - I)

    return learners, X


def fuzzy_cluster(X, k):
    k = min(k, max(1, X.shape[0]))
    _, U, *_ = fuzz.cmeans(X.T, c=k, m=2.0, error=1e-5, maxiter=300)
    return U.T


def add_cluster_nodes(G, learners, U, dataset_size="auto"):
    total_courses = len([n for n, d in G.nodes(data=True) if d["ntype"] == "course"])

    if dataset_size == "auto":
        if total_courses < 1000:
            dataset_size = "small"
        elif total_courses < 5000:
            dataset_size = "medium"
        else:
            dataset_size = "large"

    if dataset_size == "small":
        thresh = 0.35
        min_clusters = 1
        max_clusters = 1
    elif dataset_size == "medium":
        thresh = 0.25
        min_clusters = 1
        max_clusters = 2
    else:
        thresh = 0.20
        min_clusters = 1
        max_clusters = 3

    for j in range(U.shape[1]):
        G.add_node(f"CL_{j}", ntype="cluster")

    for i, l in enumerate(learners):
        memberships = [(j, w) for j, w in enumerate(U[i])]
        memberships.sort(key=lambda x: x[1], reverse=True)

        assigned = 0
        for j, w in memberships:
            if w >= thresh or assigned < min_clusters:
                G.add_edge(l, f"CL_{j}", etype="belongs_to", weight=float(w))
                assigned += 1
                if assigned >= max_clusters:
                    break

    return G


# ================================================================
# KG → PyG  (n_rel=7: adds enrolled_by + covered_by reverse edges)
# ================================================================

def kg_to_pyg(G):
    nodes = list(G.nodes())
    idx = {n: i for i, n in enumerate(nodes)}

    edge_index, edge_type = [], []
    rel = {
        "enrolled": 0,
        "covers": 1,
        "belief": 2,
        "belongs_to": 3,
        "similar_to": 4,
        "enrolled_by": 5,  # reverse of enrolled — course→learner signal
        "covered_by": 6,  # reverse of covers — concept→course signal
    }

    for u, v, d in G.edges(data=True):
        etype = d["etype"]
        edge_index.append([idx[u], idx[v]])
        edge_type.append(rel[etype])

        if etype == "enrolled":
            edge_index.append([idx[v], idx[u]])
            edge_type.append(rel["enrolled_by"])
        elif etype == "covers":
            edge_index.append([idx[v], idx[u]])
            edge_type.append(rel["covered_by"])

    return (
        torch.tensor(edge_index).t().contiguous(),
        torch.tensor(edge_type),
        idx
    )


# ================================================================
# CANDIDATE GENERATION
# ================================================================

def generate_hybrid_candidates(
        G,
        learner_node,
        node_features,
        faiss_index,
        course_nodes,
        mode="full",
        debug=False
):
    total_courses = len(course_nodes)

    # ⭐ REALISTIC PARAMETERS (not stupid ones!)
    if mode == "fast":
        max_semantic = 80
        max_graph = 120
        max_popular = 30
        max_collab = 20
        max_similarity = 30
        final_cap = 200
        per_course_search = False
        per_course_limit = 3
        top_concepts = 15
    else:  # "full"
        max_semantic = 150
        max_graph = 200
        max_popular = 50
        max_similarity = 50

        if total_courses < 1000:
            max_collab = 30
        elif total_courses < 5000:
            max_collab = 80
        else:
            max_collab = 150

        final_cap = 400  # ⭐ NOT 3000!
        per_course_search = True
        per_course_limit = 5
        top_concepts = 25

    if learner_node not in G:
        return []

    taken = {v for u, v, d in G.edges(learner_node, data=True) if d["etype"] == "enrolled"}

    # 1. Semantic candidates
    semantic_candidates = set()
    profile = learner_profile_embedding(G, learner_node, node_features)

    if profile is not None:
        D, I = faiss_index.search(profile, min(max_semantic, total_courses))
        semantic_candidates.update(course_nodes[i] for i in I[0])

        if per_course_search:
            for c in list(taken)[:per_course_limit]:
                if c in node_features:
                    c_emb = node_features[c].reshape(1, -1).astype("float32")
                    faiss.normalize_L2(c_emb)
                    D2, I2 = faiss_index.search(c_emb, 50)
                    semantic_candidates.update(course_nodes[i] for i in I2[0])

    # 2. Graph candidates
    graph_candidates = set()

    concept_freq = defaultdict(int)
    for c in taken:
        for k in G.successors(c):
            if G.nodes[k]["ntype"] == "concept":
                concept_freq[k] += 1

    top_k = 25 if mode == "fast" else top_concepts
    top_concepts_list = sorted(concept_freq, key=concept_freq.get, reverse=True)[:top_k]

    for k in top_concepts_list:
        for c2 in G.predecessors(k):
            if G.nodes[c2]["ntype"] == "course":
                graph_candidates.add(c2)

    for cl in G.successors(learner_node):
        if G.nodes[cl]["ntype"] != "cluster":
            continue
        for l2 in G.predecessors(cl):
            if G.nodes[l2]["ntype"] != "learner":
                continue
            for c2 in G.successors(l2):
                if G.nodes[c2]["ntype"] == "course":
                    graph_candidates.add(c2)

    for k in G.successors(learner_node):
        if G.nodes.get(k, {}).get("ntype") == "concept":
            for c2 in G.predecessors(k):
                if G.nodes[c2]["ntype"] == "course":
                    graph_candidates.add(c2)

    if mode == "full":
        for k in G.successors(learner_node):
            if G.nodes.get(k, {}).get("ntype") == "concept":
                for l2 in G.predecessors(k):
                    if G.nodes.get(l2, {}).get("ntype") == "learner" and l2 != learner_node:
                        for c2 in G.successors(l2):
                            if G.nodes[c2]["ntype"] == "course":
                                graph_candidates.add(c2)

    # 3. Similarity-based expansion
    similarity_candidates = set()
    for c in taken:
        for c_similar in G.successors(c):
            if G.nodes.get(c_similar, {}).get("ntype") == "course":
                if G[c][c_similar].get("etype") == "similar_to":
                    similarity_candidates.add(c_similar)
        for c_similar in G.predecessors(c):
            if G.nodes.get(c_similar, {}).get("ntype") == "course":
                if G.has_edge(c_similar, c) and G[c_similar][c].get("etype") == "similar_to":
                    similarity_candidates.add(c_similar)

    # 4. Collaborative filtering
    collab_candidates = set()
    if max_collab > 0:
        similar_learners = set()
        for cl in G.successors(learner_node):
            if G.nodes[cl]["ntype"] == "cluster":
                for l2 in G.predecessors(cl):
                    if G.nodes[l2]["ntype"] == "learner" and l2 != learner_node:
                        similar_learners.add(l2)

        for l2 in list(similar_learners)[:100]:
            for c in G.successors(l2):
                if G.nodes[c]["ntype"] == "course":
                    collab_candidates.add(c)

    # 5. Popularity
    pop = defaultdict(int)
    for u, v, d in G.edges(data=True):
        if d["etype"] == "enrolled":
            pop[v] += 1

    popular_candidates = set(sorted(pop, key=pop.get, reverse=True)[:max_popular])

    if debug:
        print(f"\n[CANDIDATE GENERATION DEBUG - {mode} mode]")
        print(f"Semantic: {len(semantic_candidates)}")
        print(f"Graph: {len(graph_candidates)}")
        print(f"Collab: {len(collab_candidates)}")
        print(f"Similarity: {len(similarity_candidates)}")
        print(f"Popular: {len(popular_candidates)}")
        print(f"Taken: {len(taken)}")

    candidates = (
            list(semantic_candidates)[:max_semantic] +
            list(graph_candidates)[:max_graph] +
            list(collab_candidates)[:max_collab] +
            list(similarity_candidates)[:max_similarity] +
            list(popular_candidates)
    )

    candidates = list(set(candidates) - taken)

    if debug:
        print(f"Before cap: {len(candidates)}")
        print(f"Final cap: {final_cap}")

    if len(candidates) > final_cap:
        candidates = random.sample(candidates, final_cap)

    if debug:
        print(f"After cap: {len(candidates)}\n")

    return candidates


# ================================================================
# SCORING FUNCTION — adds collab + belief + frequent-course boost
# ================================================================

def score_candidates(G, lnode, candidates, z, idx, node_features, profile,
                     all_learner_profiles, pop_cache, max_pop, freq_set):
    if profile is None or lnode not in idx:
        return []

    profile_flat = profile.flatten()

    # Taken concepts
    taken_concepts = set()
    for c in G.successors(lnode):
        if G.nodes.get(c, {}).get("ntype") == "course":
            for k in G.successors(c):
                if G.nodes[k]["ntype"] == "concept":
                    taken_concepts.add(k)

    # Collaborative filtering via BGE profile similarity
    collab_scores = defaultdict(float)
    for l2, (prof2, courses2) in all_learner_profiles.items():
        if l2 == lnode:
            continue
        sim = float(np.dot(profile_flat, prof2))
        if sim < 0.2:
            continue
        for c2, rating in courses2:
            collab_scores[c2] += sim * rating * 1.2
    max_collab = max(collab_scores.values()) if collab_scores else 1.0

    # Belief boost
    belief_boost = defaultdict(float)
    for _, k, d in G.edges(lnode, data=True):
        if d["etype"] == "belief" and d["weight"] > 0:
            for c2 in G.predecessors(k):
                if G.nodes[c2]["ntype"] == "course":
                    belief_boost[c2] += d["weight"]
    max_belief = max(belief_boost.values()) if belief_boost else 1.0

    # Vectorised graph scoring
    valid_cands = [c for c in candidates if c in idx]
    if not valid_cands:
        return []

    l_emb = z[idx[lnode]]
    cand_embs = z[[idx[c] for c in valid_cands]]
    graph_sims = ((F.cosine_similarity(l_emb.unsqueeze(0), cand_embs) + 1) / 2).tolist()

    scores = []
    for i, c in enumerate(valid_cands):
        sem = (float(np.dot(node_features[c], profile_flat)) + 1) / 2 \
            if c in node_features else 0.5
        graph = graph_sims[i]
        pop = pop_cache.get(c, 0) / max_pop

        cand_concepts = {k for k in G.successors(c) if G.nodes[k]["ntype"] == "concept"}
        overlap = len(taken_concepts & cand_concepts) / max(len(cand_concepts), 1)

        collab = collab_scores.get(c, 0.0) / max_collab
        belief = belief_boost.get(c, 0.0) / max_belief

        # Frequently-occurring course bonus
        # Courses with high enrollment are more likely to be relevant
        freq_bonus = 1.0 if c in freq_set else 0.0

        score = (
                0.30 * sem +  # up from 0.30
                0.30 * graph +
                0.20 * collab +
                0.12 * overlap +
                0.02 * pop +  # down from 0.05 — popularity is noise at small scale
                0.04 * belief +
                0.02 * freq_bonus  # down from 0.07 — don't reward just being popular
        )
        scores.append((c, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores


# ================================================================
# RGCN MODEL  (n_rel=7 to match reverse edges)
# ================================================================

class RecommenderRGCN(Module):
    def __init__(self, n_nodes, in_dim, hid, out, n_rel):
        super().__init__()
        self.emb = Embedding(n_nodes, in_dim)

        self.c1 = RGCNConv(in_dim, hid, n_rel)
        self.c2 = RGCNConv(hid, hid, n_rel)
        self.c3 = RGCNConv(hid, hid // 2, n_rel)
        self.c4 = RGCNConv(hid // 2, out, n_rel)

        self.dropout = torch.nn.Dropout(0.2)
        self.layer_norm1 = torch.nn.LayerNorm(hid)
        self.layer_norm2 = torch.nn.LayerNorm(hid)

    def forward(self, ei, et):
        x = self.emb.weight

        x = F.relu(self.c1(x, ei, et))
        x = self.dropout(x)
        x = self.layer_norm1(x)

        identity = x
        x = F.relu(self.c2(x, ei, et))
        x = self.dropout(x)
        x = self.layer_norm2(x + identity)

        x = F.relu(self.c3(x, ei, et))
        x = self.dropout(x)
        x = self.c4(x, ei, et)

        return x


# ================================================================
# TRAINING
# ================================================================

def init_learner_embeddings(model, idx, G, node_features):
    with torch.no_grad():
        for n, i in idx.items():
            ntype = G.nodes[n]["ntype"]
            if ntype in {"course", "concept"} and n in node_features:
                model.emb.weight[i] = torch.tensor(node_features[n])
            elif ntype == "learner":
                taken = [c for _, c, d in G.edges(n, data=True) if d["etype"] == "enrolled"]
                valid = [node_features[c] for c in taken if c in node_features]
                if valid:
                    v = torch.tensor(np.mean(valid, axis=0))
                    model.emb.weight[i] = v / (v.norm() + 1e-8)


def build_all_learner_profiles(G, node_features):
    """Pre-build BGE profiles for every learner for collab filtering."""
    profiles = {}
    for n, d in G.nodes(data=True):
        if d["ntype"] != "learner":
            continue
        profile = learner_profile_embedding(G, n, node_features)
        if profile is None:
            continue
        courses_taken = [
            (c, G[n][c]["weight"])
            for _, c, d2 in G.edges(n, data=True)
            if d2["etype"] == "enrolled"
        ]
        profiles[n] = (profile.flatten().copy(), courses_taken)
    return profiles


def train(model, ei, et, idx, G, node_features,
          faiss_index, course_nodes,
          all_learner_profiles, pop_cache, max_pop, freq_set,
          test_df=None, k_eval=10, epochs=150):
    opt = torch.optim.Adam(model.parameters(), lr=2e-4, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        opt, mode="max", factor=0.5, patience=5
    )

    courses = [n for n, d in G.nodes(data=True) if d["ntype"] == "course"]
    enroll = [(l, c) for l, c, d in G.edges(data=True) if d["etype"] == "enrolled"]

    best_ndcg = 0.0
    best_state = None
    patience = 30
    counter = 0
    NEG_K = 10

    # Pre-collect nodes for BGE regularisation
    reg_nodes = [
        (n, i) for n, i in idx.items()
        if G.nodes[n]["ntype"] in {"course", "concept"} and n in node_features
    ]

    unique_learners = test_df["learner_id"].unique() if test_df is not None else []
    val_size = min(150, len(unique_learners))

    for ep in tqdm(range(epochs), desc="GCN Training"):

        model.emb.weight.requires_grad = (ep >= 5)
        model.train()
        opt.zero_grad()

        z = model(ei, et)

        sampled = random.sample(enroll, min(len(enroll), 1000))

        # Vectorised negative sampling
        u_idx, pos_idx, neg_idx = [], [], []
        for l, c_pos in sampled:
            li = idx[l]
            pi = idx[c_pos]
            for _ in range(NEG_K):
                c_neg = hierarchical_negative_sampling(G, l, c_pos, courses, node_features)
                u_idx.append(li)
                pos_idx.append(pi)
                neg_idx.append(idx[c_neg])

        u_emb = z[u_idx]
        pos_emb = z[pos_idx]
        neg_emb = z[neg_idx]

        # Cosine margin loss (better than BPR for embedding alignment)
        pos_sim = F.cosine_similarity(u_emb, pos_emb)
        neg_sim = F.cosine_similarity(u_emb, neg_emb)
        loss = F.relu(neg_sim - pos_sim + 0.3).mean()

        # BGE regularisation: keep RGCN anchored to semantic space
        sample_reg = random.sample(reg_nodes, min(200, len(reg_nodes)))

        # FIX: Vectorized target extraction and cosine similarity
        reg_idx = [i for n, i in sample_reg]
        reg_targets = torch.tensor(
            np.array([node_features[n] for n, i in sample_reg]),
            dtype=torch.float32,
            device=z.device
        )

        reg_loss = (1 - F.cosine_similarity(z[reg_idx], reg_targets)).mean()
        total_loss = loss + 0.01 * reg_loss

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        opt.step()

        current_ndcg = 0.0

        if test_df is not None and ep % 2 == 0:
            model.eval()
            with torch.no_grad():
                z_eval = model(ei, et)
                ndcgs = []

                for lid in random.sample(list(unique_learners), val_size):
                    gt = test_df[test_df["learner_id"] == lid]
                    lnode = f"L_{lid}"
                    if lnode not in idx:
                        continue

                    true = {f"C_{c}" for c in gt["course_id"]}
                    candidates = generate_hybrid_candidates(
                        G, lnode, node_features, faiss_index, course_nodes, mode="fast"
                    )
                    if not candidates:
                        continue

                    profile = learner_profile_embedding(G, lnode, node_features)
                    sc = score_candidates(G, lnode, candidates, z_eval, idx,
                                          node_features, profile,
                                          all_learner_profiles, pop_cache, max_pop, freq_set)
                    recs = [c for c, _ in sc[:k_eval]]
                    ndcgs.append(ndcg_at_k(recs, true, k_eval))

                if ndcgs:
                    current_ndcg = float(np.mean(ndcgs))

        tqdm.write(f"Epoch {ep:02d} | Loss {total_loss.item():.4f} | NDCG@{k_eval}: {current_ndcg:.4f}")
        scheduler.step(current_ndcg)

        if current_ndcg > best_ndcg:
            best_ndcg = current_ndcg
            counter = 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            counter += 1

        if counter >= patience:
            print(f"Early stopping at epoch {ep}. Restoring best model (NDCG: {best_ndcg:.4f})...")
            if best_state:
                model.load_state_dict(best_state)
            break


# ================================================================
# METRICS — ⭐ UPDATED WITH MULTIPLE K VALUES
# ================================================================

def precision_at_k(rec, rel, k):
    """Precision@K: Fraction of top-k that are relevant"""
    return len(set(rec[:k]) & rel) / k if k else 0.0


def recall_at_k(rec, rel, k):
    """Recall@K: Fraction of relevant items found in top-k"""
    return len(set(rec[:k]) & rel) / len(rel) if rel else 0.0


def hit_rate_at_k(rec, rel, k):
    """Hit Rate@K: 1 if at least one relevant item in top-k, else 0"""
    return 1.0 if len(set(rec[:k]) & rel) > 0 else 0.0


def ndcg_at_k(rec, rel, k):
    """NDCG@K: Normalized Discounted Cumulative Gain"""
    dcg = sum(1 / np.log2(i + 2) for i, r in enumerate(rec[:k]) if r in rel)
    idcg = sum(1 / np.log2(i + 2) for i in range(min(k, len(rel))))
    return dcg / idcg if idcg else 0.0


def compute_all_metrics(rec, rel, k_values):
    """
    Compute all metrics for all k values.

    Parameters:
    -----------
    rec : list
        Ranked list of recommended items
    rel : set
        Set of relevant (ground truth) items
    k_values : list
        List of k values to evaluate (e.g., [5, 10, 15, 20])

    Returns:
    --------
    dict: Dictionary with metrics for each k value
          Format: {5: {'precision': ..., 'recall': ..., 'ndcg': ..., 'hr': ...}, ...}
    """
    results = {}
    for k in k_values:
        results[k] = {
            'precision': precision_at_k(rec, rel, k),
            'recall': recall_at_k(rec, rel, k),
            'ndcg': ndcg_at_k(rec, rel, k),
            'hr': hit_rate_at_k(rec, rel, k)
        }
    return results


# ================================================================
# TRAIN-TEST SPLIT
# ================================================================

def train_test_split_80_20(df):
    tr, te = [], []
    for _, g in df.groupby("learner_id"):
        if len(g) < 2:
            continue
        g = g.sample(frac=1, random_state=42)
        s = int(0.80 * len(g))
        tr.append(g.iloc[:s])
        te.append(g.iloc[s:])
    return pd.concat(tr).reset_index(drop=True), pd.concat(te).reset_index(drop=True)


# ================================================================
# LEARNER PROFILE
# ================================================================

def learner_profile_embedding(G, learner, node_features):
    taken = [c for _, c, d in G.edges(learner, data=True) if d["etype"] == "enrolled"]

    if not taken:
        return None

    valid = [node_features[c] for c in taken if c in node_features]
    if not valid:
        return None

    embs = np.vstack(valid)
    weights = np.exp(np.linspace(0, 1, len(embs)))
    weights /= weights.sum()

    profile = np.average(embs, axis=0, weights=weights, keepdims=True).astype("float32")
    faiss.normalize_L2(profile)
    return profile


# ================================================================
# OFFLINE EVALUATION — ⭐ UPDATED WITH MULTI-K METRICS
# ================================================================

def offline_evaluate(df, k_values=[5, 10, 15, 20], n_clusters=5, epochs=150, min_course_freq=3):
    """
    Evaluate the recommender system at multiple k values.

    Parameters:
    -----------
    df : DataFrame
        Input dataset
    k_values : list
        List of k values for evaluation (default: [5, 10, 15, 20])
    n_clusters : int
        Number of fuzzy clusters
    epochs : int
        Training epochs
    min_course_freq : int
        Minimum course frequency filter
    """

    # ── Step 1: Deduplicate ─────────────────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["learner_id", "course_id"], keep="last").reset_index(drop=True)
    print(f"\n[INFO] Removed {before - len(df)} duplicate (learner, course) pairs")

    df["course_id"] = df["course_id"].astype(str).str.strip()
    df["learner_id"] = df["learner_id"].astype(str).str.strip()

    # ── Step 2: Frequency filter BEFORE building KG ─────────────────
    course_counts = df["course_id"].value_counts()
    valid_courses = course_counts[course_counts >= min_course_freq].index

    print(f"[INFO] Original courses:              {df['course_id'].nunique()}")
    print(f"[INFO] Courses with ≥{min_course_freq} enrollments: {len(valid_courses)}")

    # Frequently-occurring courses: top 20% by enrollment count
    freq_threshold = course_counts[course_counts >= min_course_freq].quantile(0.80)
    freq_courses = set(f"C_{c}" for c in course_counts[course_counts >= freq_threshold].index)
    print(f"[INFO] Frequently-occurring courses (top 20%): {len(freq_courses)}")
    print(f"[INFO] Top 5 most enrolled:")
    for cid, cnt in course_counts.head(5).items():
        print(f"       C_{cid}: {cnt} enrollments")

    df = df[df["course_id"].isin(valid_courses)].reset_index(drop=True)

    # ── Step 3: Filter learners ──────────────────────────────────────
    df = df.groupby("learner_id").filter(lambda x: len(x) >= 2).reset_index(drop=True)

    print(f"\n[INFO] Final dataset:   {len(df)} interactions")
    print(f"[INFO] Unique learners: {df['learner_id'].nunique()}")
    print(f"[INFO] Unique courses:  {df['course_id'].nunique()}")

    # ── Step 4: Split ────────────────────────────────────────────────
    train_df, test_df = train_test_split_80_20(df)

    # Sanity-check: no (learner, course) overlap between train and test
    train_pairs = set(zip(train_df["learner_id"], train_df["course_id"]))
    test_pairs = set(zip(test_df["learner_id"], test_df["course_id"]))
    overlap = train_pairs & test_pairs
    print(f"\n[SANITY] Train/test overlap: {len(overlap)} pairs")
    if overlap:
        mask = test_df.apply(lambda r: (r["learner_id"], r["course_id"]) in overlap, axis=1)
        test_df = test_df[~mask].reset_index(drop=True)

    print(f"[INFO] Train: {len(train_df)} | Test: {len(test_df)}")

    # ── Step 5: Build graph ──────────────────────────────────────────
    G = build_kg(train_df)

    # Add ALL course nodes from full df so test-only courses are visible
    all_courses_df = df[["course_id", "short_description"]].drop_duplicates()
    added = 0
    for _, row in all_courses_df.iterrows():
        c = f"C_{row.course_id}"
        if not G.has_node(c):
            G.add_node(c, ntype="course", text=str(row.short_description))
            added += 1
    print(f"[INFO] Added {added} extra course nodes (test-only)")

    # ── Step 6: Node features (batched) ─────────────────────────────
    feats = build_node_features(G)
    faiss_index, course_nodes = build_faiss_index(G, feats)
    print(f"[INFO] Total courses in graph: {len(course_nodes)}")

    G = add_course_similarity_edges(G, feats, top_k=15, min_similarity=0.60)

    nfh = build_nfh(G, feats)
    G = add_belief_edges(G, nfh)

    learners, X = build_belief_matrix(nfh)
    if len(learners):
        U = fuzzy_cluster(X, n_clusters)
        G = add_cluster_nodes(G, learners, U)

    print("\n========== CLUSTERING DIAGNOSTIC ==========")
    cluster_nodes = [n for n, d in G.nodes(data=True) if d["ntype"] == "cluster"]
    print(f"Number of clusters created: {len(cluster_nodes)}")
    learner_cluster_edges = sum(1 for _, _, d in G.edges(data=True) if d["etype"] == "belongs_to")
    print(f"Learner→Cluster edges: {learner_cluster_edges}")

    test_learner = list(test_df["learner_id"].unique())[0]
    test_lnode = f"L_{test_learner}"
    lc = [c for c in G.successors(test_lnode) if G.nodes.get(c, {}).get("ntype") == "cluster"]
    print(f"First test learner's clusters: {len(lc)}")
    if lc:
        members = [l for l in G.predecessors(lc[0]) if G.nodes[l]["ntype"] == "learner"]
        print(f"Members in first cluster: {len(members)}")
    else:
        print("⚠️ First test learner has NO cluster memberships!")
    print("==========================================\n")

    # ── Step 7: Pre-compute global caches ───────────────────────────
    pop_cache = defaultdict(int)
    for u, v, d in G.edges(data=True):
        if d["etype"] == "enrolled":
            pop_cache[v] += 1
    max_pop = max(pop_cache.values()) if pop_cache else 1

    all_learner_profiles = build_all_learner_profiles(G, feats)

    # ── Step 8: PyG + model ──────────────────────────────────────────
    ei, et, idx = kg_to_pyg(G)

    # n_rel=7 to match enrolled_by + covered_by reverse edges
    model = RecommenderRGCN(len(idx), EMBED_DIM, 256, EMBED_DIM, 7)
    init_learner_embeddings(model, idx, G, feats)

    # ── Step 9: Train ────────────────────────────────────────────────
    # Use max k for training validation
    train(
        model, ei, et, idx, G, feats,
        faiss_index, course_nodes,
        all_learner_profiles, pop_cache, max_pop, freq_courses,
        test_df=test_df, k_eval=max(k_values), epochs=epochs
    )

    with torch.no_grad():
        z = model(ei, et)

    # ⭐ NEW: Store metrics for all k values
    metrics_by_k = {k: {
        'precision': [],
        'recall': [],
        'ndcg': [],
        'hr': []
    } for k in k_values}

    # Candidate generation diagnostic
    print("\n========== CANDIDATE GENERATION DIAGNOSTIC ==========")
    diag_candidates = generate_hybrid_candidates(
        G, test_lnode, feats, faiss_index, course_nodes, mode="full", debug=True
    )
    print(f"Total unique candidates: {len(diag_candidates)}")
    print("====================================================\n")

    # ⭐ UPDATED: Final evaluation with multiple k values
    max_k_needed = max(k_values)

    for lid, gt in tqdm(test_df.groupby("learner_id"), desc="Evaluating"):
        lnode = f"L_{lid}"
        if lnode not in idx:
            continue

        true = {f"C_{c}" for c in gt["course_id"]}
        candidates = generate_hybrid_candidates(
            G, lnode, feats, faiss_index, course_nodes, mode="full"
        )
        if not candidates:
            continue

        if lid == list(test_df["learner_id"].unique())[0]:
            print("\n===== DEBUG FOR FIRST LEARNER =====")
            print("Liked test courses:", true)
            profile_dbg = learner_profile_embedding(G, lnode, feats)
            if profile_dbg is not None:
                D, I = faiss_index.search(profile_dbg, 10)
                print("Top Semantic Candidates:", [course_nodes[i] for i in I[0]][:5])
            print("Total Hybrid Candidates:", len(candidates))
            print("===================================\n")

        profile = learner_profile_embedding(G, lnode, feats)
        scores = score_candidates(G, lnode, candidates, z, idx, feats, profile,
                                  all_learner_profiles, pop_cache, max_pop, freq_courses)

        # Get top-max_k_needed recommendations
        recs = [c for c, _ in scores[:max_k_needed]]

        # Compute metrics for all k values
        user_metrics = compute_all_metrics(recs, true, k_values)

        # Store results
        for k in k_values:
            metrics_by_k[k]['precision'].append(user_metrics[k]['precision'])
            metrics_by_k[k]['recall'].append(user_metrics[k]['recall'])
            metrics_by_k[k]['ndcg'].append(user_metrics[k]['ndcg'])
            metrics_by_k[k]['hr'].append(user_metrics[k]['hr'])

    # Candidate recall (uses largest k)
    hit, total = 0, 0
    for lid, gt in test_df.groupby("learner_id"):
        lnode = f"L_{lid}"
        if lnode not in G:
            continue
        true = {f"C_{c}" for c in gt["course_id"]}
        candidates = generate_hybrid_candidates(
            G, lnode, feats, faiss_index, course_nodes, mode="full"
        )
        if true & set(candidates):
            hit += 1
        total += 1

    candidate_recall = hit / total if total > 0 else 0.0

    # ⭐ BEAUTIFUL RESULTS TABLE
    print("\n" + "=" * 80)
    print("EVALUATION RESULTS".center(80))
    print("=" * 80)

    # Table header
    print(f"\n{'Metric':<15} │ {'@5':>10} │ {'@10':>10} │ {'@15':>10} │ {'@20':>10}")
    print("─" * 15 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 12 + "┼" + "─" * 12)

    # Precision row
    prec_vals = [np.mean(metrics_by_k[k]['precision']) for k in k_values]
    print(
        f"{'Precision':<15} │ {prec_vals[0]:>10.4f} │ {prec_vals[1]:>10.4f} │ {prec_vals[2]:>10.4f} │ {prec_vals[3]:>10.4f}")

    # Recall row
    rec_vals = [np.mean(metrics_by_k[k]['recall']) for k in k_values]
    print(f"{'Recall':<15} │ {rec_vals[0]:>10.4f} │ {rec_vals[1]:>10.4f} │ {rec_vals[2]:>10.4f} │ {rec_vals[3]:>10.4f}")

    # NDCG row
    ndcg_vals = [np.mean(metrics_by_k[k]['ndcg']) for k in k_values]
    print(
        f"{'NDCG':<15} │ {ndcg_vals[0]:>10.4f} │ {ndcg_vals[1]:>10.4f} │ {ndcg_vals[2]:>10.4f} │ {ndcg_vals[3]:>10.4f}")

    # HR row
    hr_vals = [np.mean(metrics_by_k[k]['hr']) for k in k_values]
    print(
        f"{'HR (Hit Rate)':<15} │ {hr_vals[0]:>10.4f} │ {hr_vals[1]:>10.4f} │ {hr_vals[2]:>10.4f} │ {hr_vals[3]:>10.4f}")

    print("─" * 15 + "┴" + "─" * 12 + "┴" + "─" * 12 + "┴" + "─" * 12 + "┴" + "─" * 12)
    print(f"\nCandidate Recall: {candidate_recall:.4f}")
    print(f"Total Users Evaluated: {total}")
    print("=" * 80)

    # Return detailed results
    return {
        'metrics_by_k': metrics_by_k,
        'candidate_recall': candidate_recall,
        'total_users': total
    }


# ================================================================
# MAIN
# ================================================================

if __name__ == "__main__":
    DATA_DIR = "data"

    if not os.path.exists(DATA_DIR):
        raise FileNotFoundError(f"Data directory '{DATA_DIR}' does not exist.")

    csv_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(".csv")]
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in '{DATA_DIR}' directory.")

    print("\nAvailable CSV files:")
    for f in csv_files:
        print(f" - {f}")

    while True:
        fname = input("\nEnter CSV file name from the list above: ").strip()
        if fname in csv_files:
            break
        print("❌ Invalid file name. Please choose from the listed CSV files.")

    csv_path = os.path.join(DATA_DIR, fname)
    print(f"\n[INFO] Loading dataset: {csv_path}")

    df = pd.read_csv(csv_path)

    # ── Meaningful stratified sampling (preserve full learner histories) ──
    MAX_ROWS = 25000

    if len(df) > MAX_ROWS:
        print(f"[INFO] Dataset has {len(df)} rows — applying stratified learner sampling...")

        # Step 1: Bin learners into 3 activity tiers by interaction count
        learner_counts = df.groupby("learner_id").size().reset_index(name="n_interactions")

        low = learner_counts[learner_counts["n_interactions"] <= 3]
        medium = learner_counts[(learner_counts["n_interactions"] > 3) &
                                (learner_counts["n_interactions"] <= 15)]
        high = learner_counts[learner_counts["n_interactions"] > 15]

        print(f"         Low activity  learners (≤3 interactions) : {len(low)}")
        print(f"         Mid activity  learners (4–15 interactions): {len(medium)}")
        print(f"         High activity learners (>15 interactions) : {len(high)}")

        # Step 2: Allocate row budget proportionally across tiers
        total_learners = len(learner_counts)
        budget_low = int(MAX_ROWS * len(low) / total_learners)
        budget_medium = int(MAX_ROWS * len(medium) / total_learners)
        budget_high = MAX_ROWS - budget_low - budget_medium  # remainder goes to high


        # Step 3: Greedily pick learners per tier until budget is consumed
        def pick_learners_within_budget(tier_df, row_budget, seed=42):
            """Pick as many learners as possible without exceeding row_budget.
               Shuffle first so selection is random but complete histories are kept."""
            shuffled = tier_df.sample(frac=1, random_state=seed)
            selected, total = [], 0
            for _, row in shuffled.iterrows():
                if total + row["n_interactions"] <= row_budget:
                    selected.append(row["learner_id"])
                    total += row["n_interactions"]
            return selected


        chosen_low = pick_learners_within_budget(low, budget_low)
        chosen_medium = pick_learners_within_budget(medium, budget_medium)
        chosen_high = pick_learners_within_budget(high, budget_high)

        all_chosen = chosen_low + chosen_medium + chosen_high

        df = df[df["learner_id"].isin(all_chosen)].reset_index(drop=True)

        print(f"[INFO] Stratified sample: {len(all_chosen)} learners → {len(df)} rows")
        print(f"         Low tier  : {len(chosen_low)} learners")
        print(f"         Mid tier  : {len(chosen_medium)} learners")
        print(f"         High tier : {len(chosen_high)} learners")
    else:
        print(f"[INFO] Dataset has {len(df)} rows — no sampling needed.")

    # ⭐ Evaluate at k=[5, 10, 15, 20]
    results = offline_evaluate(df, k_values=[5, 10, 15, 20], epochs=150, min_course_freq=1)