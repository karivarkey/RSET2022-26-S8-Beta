# ================================================================
# COCO DATASET — KG + NFH GRAPH GENERATION & PYVIS VISUALIZATION
# Matches main pipeline logic exactly.
# ================================================================

import os, re, hashlib, random, warnings
from collections import defaultdict
import numpy as np
import pandas as pd
import networkx as nx
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ── Optional heavy imports (graceful fallback) ─────────────────
try:
    from sentence_transformers import SentenceTransformer
    from keybert import KeyBERT
    HAS_KEYBERT = True
    print("[INFO] KeyBERT + SentenceTransformer found — using semantic concept extraction.")
except ImportError:
    HAS_KEYBERT = False
    print("[INFO] KeyBERT not found — using TF-IDF bigram concept extraction (fallback).")

try:
    from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False
    print("[WARN] sklearn not found — similarity edges will be skipped.")

try:
    import skfuzzy as fuzz
    HAS_FUZZY = True
except ImportError:
    HAS_FUZZY = False
    from sklearn.cluster import KMeans
    print("[INFO] skfuzzy not found — using KMeans as fuzzy-cluster proxy.")

from pyvis.network import Network


# ================================================================
# CONFIG
# ================================================================

CSV_PATH        = "data/COCO_minimal_dataset_LLM.csv"   # ← CSV inside data/ folder
FULL_OUTPUT     = "kg_full_graph.html"
NFH_OUTPUT      = "nfh_belief_graph.html"
EMBED_DIM       = 128       # TF-IDF dim (fallback); semantic dim set by model
N_CLUSTERS      = 4
SIM_THRESHOLD   = 0.45      # cosine threshold for course-similarity edges
TOP_K_SIM       = 5         # max similar courses per course
BELIEF_EPS      = 0.05      # min |belief| to add edge
CONCEPT_TOP_N   = 6         # concepts extracted per course  → ~152 concept nodes

# ── Dataset slice parameters  (tuned to ≈ 228 total nodes) ───
MAX_COURSES     = 30        # top-N courses by enrollment to consider
MIN_ENROLL      = 4         # min enrollments a course must have
MAX_LEARNERS    = 45        # number of learners to include
MIN_L_COURSES   = 2         # min number of selected courses a learner must have taken

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


# ================================================================
# EXTRA STOP WORDS (domain-specific)
# ================================================================

EXTRA_STOPS = {
    "course", "learn", "learning", "using", "this", "make", "just", "about",
    "your", "from", "that", "with", "have", "will", "what", "more", "help",
    "every", "need", "ways", "want", "able", "including", "introduction",
    "complete", "updated", "training", "understand", "discover", "explore",
    "begin", "basic", "start", "series", "video", "videos", "supplement",
    "materials", "topics", "section", "like", "take", "know", "well", "even",
    "without", "prior", "microcourse", "gain", "gives", "give", "become",
    "best", "selling", "number", "first", "second", "third", "udemy",
    "everything", "anybody", "beginner", "beginners", "quickly", "getting",
    "anywhere", "amazing", "today", "most", "used", "highly", "rated",
    "instructor", "student", "students", "lesson", "lessons",
}

if HAS_SKLEARN:
    ALL_STOPS = ENGLISH_STOP_WORDS | EXTRA_STOPS
else:
    ALL_STOPS = EXTRA_STOPS


# ================================================================
# STEP 1 — LOAD & SLICE DATASET
# ================================================================

def load_and_slice(csv_path: str) -> pd.DataFrame:
    print(f"\n[STEP 1] Loading dataset: {csv_path}")
    df = pd.read_csv(csv_path)
    df["course_id"]  = df["course_id"].astype(str).str.strip()
    df["learner_id"] = df["learner_id"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["learner_id","course_id"], keep="last").reset_index(drop=True)

    # Select courses
    course_counts   = df["course_id"].value_counts()
    selected        = course_counts[course_counts >= MIN_ENROLL].head(MAX_COURSES).index.tolist()
    subset          = df[df["course_id"].isin(selected)]

    # Select learners with enough cross-course connections
    lcnt            = subset.groupby("learner_id").size()
    good_learners   = lcnt[lcnt >= MIN_L_COURSES].index.tolist()
    random.shuffle(good_learners)
    chosen_learners = good_learners[:MAX_LEARNERS]

    final = subset[subset["learner_id"].isin(chosen_learners)].copy()
    final = final.reset_index(drop=True)

    print(f"         Learners : {final['learner_id'].nunique()}")
    print(f"         Courses  : {final['course_id'].nunique()}")
    print(f"         Rows     : {len(final)}")
    return final


# ================================================================
# STEP 2 — CONCEPT EXTRACTION
# ================================================================

# ── Path A: KeyBERT ────────────────────────────────────────────

if HAS_KEYBERT:
    _embedder  = SentenceTransformer("BAAI/bge-large-en-v1.5")
    _kw_model  = KeyBERT(_embedder)

    def _normalize(text: str) -> str:
        return " ".join(text.lower().replace("-", " ").split())

    def extract_concepts_keybert(text: str, top_n: int = CONCEPT_TOP_N) -> list:
        if not isinstance(text, str) or not text.strip():
            return []
        kws = _kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 3),
            stop_words="english",
            use_mmr=True,
            diversity=0.65,
            top_n=top_n
        )
        return [_normalize(k) for k, s in kws if s >= 0.22 and len(k) >= 4]

    extract_concepts = extract_concepts_keybert

# ── Path B: TF-IDF bigrams (fallback) ─────────────────────────

else:
    def extract_concepts_tfidf(text: str, top_n: int = CONCEPT_TOP_N) -> list:
        """Extract meaningful unigrams + bigrams via TF-IDF-style scoring."""
        clean = re.sub(r"[^a-zA-Z\s]", " ", text.lower())
        words = [w for w in clean.split() if len(w) >= 4 and w not in ALL_STOPS]

        candidates = []
        for i in range(len(words) - 1):
            candidates.append(words[i] + " " + words[i + 1])
        candidates += words

        seen, unique = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)
        return unique[:top_n]

    extract_concepts = extract_concepts_tfidf


# ================================================================
# STEP 3 — NODE / EDGE UTILITIES
# ================================================================

def concept_id(text: str) -> str:
    return "K_" + hashlib.md5(text.encode()).hexdigest()[:10]


def build_node_features_tfidf(G) -> dict:
    """Build 128-dim TF-IDF features for course & concept nodes."""
    text_nodes = [
        (n, d["text"]) for n, d in G.nodes(data=True)
        if d.get("ntype") in {"course", "concept"}
    ]
    if not text_nodes or not HAS_SKLEARN:
        return {n: np.zeros(EMBED_DIM, dtype=np.float32) for n in G.nodes()}

    names = [n for n, _ in text_nodes]
    texts = [t for _, t in text_nodes]

    vec  = TfidfVectorizer(max_features=EMBED_DIM, stop_words="english", ngram_range=(1, 2))
    mat  = vec.fit_transform(texts).toarray().astype(np.float32)

    # L2-normalise
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat  /= norms

    feats = dict(zip(names, mat))
    for n in G.nodes():
        if n not in feats:
            feats[n] = np.zeros(EMBED_DIM, dtype=np.float32)
    return feats


def build_node_features_semantic(G) -> dict:
    """Build sentence-transformer embeddings for course & concept nodes."""
    text_nodes = [
        (n, d["text"]) for n, d in G.nodes(data=True)
        if d.get("ntype") in {"course", "concept"}
    ]
    feats = {}
    if text_nodes:
        names = [n for n, _ in text_nodes]
        texts = [t for _, t in text_nodes]
        vecs  = _embedder.encode(texts, normalize_embeddings=True,
                                 batch_size=64, show_progress_bar=False)
        feats = dict(zip(names, [v.astype(np.float32) for v in vecs]))
    for n in G.nodes():
        if n not in feats:
            feats[n] = np.zeros(
                _embedder.get_sentence_embedding_dimension(), dtype=np.float32
            )
    return feats


def build_node_features(G) -> dict:
    if HAS_KEYBERT:
        return build_node_features_semantic(G)
    return build_node_features_tfidf(G)


# ================================================================
# STEP 4 — BUILD KNOWLEDGE GRAPH
# ================================================================

def build_kg(df: pd.DataFrame) -> nx.DiGraph:
    print("\n[STEP 4] Building Knowledge Graph...")
    G = nx.DiGraph()

    courses_df = df[["course_id", "short_description"]].drop_duplicates()

    # Course → Concept edges
    for _, row in tqdm(courses_df.iterrows(), total=len(courses_df),
                       desc="  Courses → Concepts"):
        c_node = f"C_{row.course_id}"
        G.add_node(c_node, ntype="course", text=str(row.short_description))

        concepts = extract_concepts(str(row.short_description))
        for phrase in concepts:
            k_node = concept_id(phrase)
            if not G.has_node(k_node):
                G.add_node(k_node, ntype="concept", text=phrase)
            G.add_edge(c_node, k_node, etype="covers", weight=1.0)

    # Learner → Course edges
    for _, row in tqdm(df.iterrows(), total=len(df),
                       desc="  Learners → Courses"):
        l_node = f"L_{row.learner_id}"
        c_node = f"C_{row.course_id}"
        if not G.has_node(l_node):
            G.add_node(l_node, ntype="learner")
        r = float(row.get("learner_rating", 3.0))
        r = max(0.0, min(r / 5.0, 1.0))
        G.add_edge(l_node, c_node, etype="enrolled", weight=r)

    print(f"  KG nodes: {G.number_of_nodes()}  |  edges: {G.number_of_edges()}")
    return G


# ================================================================
# STEP 5 — COURSE SIMILARITY EDGES
# ================================================================

def add_course_similarity_edges(G: nx.DiGraph, node_features: dict) -> nx.DiGraph:
    if not HAS_SKLEARN:
        return G

    print("\n[STEP 5] Adding course-similarity edges...")
    courses = [n for n, d in G.nodes(data=True) if d.get("ntype") == "course"]
    if len(courses) < 2:
        return G

    mat   = np.vstack([node_features[c] for c in courses])
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat  /= norms

    sims  = sk_cosine(mat)                        # (n_courses, n_courses)

    added = 0
    for i, ci in enumerate(courses):
        row    = sims[i].copy()
        row[i] = -1                               # exclude self
        top_j  = np.argsort(row)[::-1][:TOP_K_SIM]
        for j in top_j:
            if row[j] >= SIM_THRESHOLD:
                G.add_edge(ci, courses[j],
                           etype="similar_to", weight=float(row[j]))
                added += 1

    print(f"  Added {added} similar_to edges")
    return G


# ================================================================
# STEP 6 — NFH (Neutrosophic Fuzzy Hypergraph) BELIEF COMPUTATION
# ================================================================

def build_nfh(G: nx.DiGraph, node_features: dict,
              tau: int = 3) -> dict:
    """Replicate the T / I / Fv evidence aggregation from main code."""
    print("\n[STEP 6] Building NFH evidence...")
    evidence = defaultdict(list)

    for l_node, ld in tqdm(G.nodes(data=True), desc="  NFH: Collecting evidence"):
        if ld.get("ntype") != "learner":
            continue
        for c_node in G.successors(l_node):
            if G.nodes[c_node].get("ntype") != "course":
                continue

            r_lc  = G[l_node][c_node]["weight"]   # normalised rating [0,1]
            c_emb = node_features.get(c_node,
                                      np.zeros(EMBED_DIM, dtype=np.float32))

            for k_node in G.successors(c_node):
                if G.nodes[k_node].get("ntype") != "concept":
                    continue
                k_emb = node_features.get(k_node,
                                          np.zeros(EMBED_DIM, dtype=np.float32))
                w_ck  = float(np.dot(c_emb, k_emb))
                if w_ck > 0:
                    evidence[(l_node, k_node)].append((r_lc, w_ck))

    print("  NFH: Aggregating T / I / Fv ...")
    nfh = defaultdict(dict)
    for (l_node, k_node), vals in evidence.items():
        n   = len(vals)
        T   = sum(r * w for r, w in vals) / n
        Fv  = sum((1 - r) * w for r, w in vals) / n
        I   = 1 - min(1.0, n / tau)
        nfh[k_node][l_node] = (T, I, Fv)

    print(f"  NFH entries: {sum(len(v) for v in nfh.values())}")
    return nfh


def add_belief_edges(G: nx.DiGraph, nfh: dict,
                     eps: float = BELIEF_EPS) -> nx.DiGraph:
    print("\n[STEP 7] Adding belief edges...")
    added = 0
    for k_node, learners in nfh.items():
        for l_node, (T, I, Fv) in learners.items():
            b = 1.5 * (T - Fv) * (1 - I)
            if abs(b) >= eps:
                G.add_edge(l_node, k_node, etype="belief", weight=float(b))
                added += 1
    print(f"  Added {added} belief edges")
    return G


# ================================================================
# STEP 8 — FUZZY CLUSTERING
# ================================================================

def build_belief_matrix(nfh: dict):
    learners = sorted({l for v in nfh.values() for l in v})
    concepts = list(nfh.keys())
    if not learners or not concepts:
        return [], np.empty((0, 0))

    li = {l: i for i, l in enumerate(learners)}
    X  = np.zeros((len(learners), len(concepts)), dtype=np.float32)
    for ci, (k_node, vals) in enumerate(nfh.items()):
        for l_node, (T, I, Fv) in vals.items():
            X[li[l_node], ci] = (T - Fv) * (1 - I)
    return learners, X


def fuzzy_cluster(X: np.ndarray, k: int) -> np.ndarray:
    k = min(k, max(1, X.shape[0]))
    if HAS_FUZZY:
        _, U, *_ = fuzz.cmeans(X.T, c=k, m=2.0, error=1e-5, maxiter=300)
        return U.T
    else:
        km  = KMeans(n_clusters=k, random_state=SEED, n_init="auto")
        lab = km.fit_predict(X)
        U   = np.zeros((X.shape[0], k), dtype=np.float32)
        for i, l in enumerate(lab):
            U[i, l] = 1.0
        return U


def add_cluster_nodes(G: nx.DiGraph, learners: list,
                      U: np.ndarray, thresh: float = 0.30) -> nx.DiGraph:
    print("\n[STEP 8] Adding cluster nodes & belongs_to edges...")
    n_clusters = U.shape[1]
    for j in range(n_clusters):
        G.add_node(f"CL_{j}", ntype="cluster", label=f"Cluster {j}")

    added = 0
    for i, l in enumerate(learners):
        memberships = sorted(enumerate(U[i]), key=lambda x: x[1], reverse=True)
        assigned = 0
        for j, w in memberships:
            if w >= thresh or assigned == 0:
                G.add_edge(l, f"CL_{j}", etype="belongs_to", weight=float(w))
                added += 1
                assigned += 1
                if assigned >= 2:
                    break

    print(f"  Added {n_clusters} cluster nodes + {added} belongs_to edges")
    return G


# ================================================================
# STEP 9 — PYVIS: FULL KG VISUALIZATION
# ================================================================

# ── Color palette ──────────────────────────────────────────────
COLORS = {
    "learner"  : "#58BCFF",   # sky blue
    "course"   : "#FF9E3B",   # warm amber
    "concept"  : "#4ECBA4",   # teal green
    "cluster"  : "#C97BF5",   # violet
}
EDGE_COLORS = {
    "enrolled"  : "#A8D4FF",
    "covers"    : "#78E8C0",
    "similar_to": "#FFD580",
    "belief_pos": "#00FFB0",
    "belief_neg": "#FF4F6A",
    "belongs_to": "#D9A8FF",
}


def _shorten(text: str, n: int = 22) -> str:
    return text if len(text) <= n else text[:n - 1] + "…"


def visualize_full_kg(G: nx.DiGraph, output: str = FULL_OUTPUT) -> str:
    print(f"\n[VIZ] Rendering Full KG → {output}")

    net = Network(
        height  = "920px",
        width   = "100%",
        directed = True,
        bgcolor = "#0D1117",
        font_color = "white",
    )

    # Physics: Barnes-Hut for nice separation
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "barnesHut": {
          "gravitationalConstant": -28000,
          "centralGravity": 0.25,
          "springLength": 160,
          "springConstant": 0.04,
          "damping": 0.10,
          "avoidOverlap": 0.3
        },
        "minVelocity": 0.75,
        "maxVelocity": 50,
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 50
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 120,
        "navigationButtons": true,
        "keyboard": true
      },
      "edges": {
        "smooth": {
          "type": "curvedCW",
          "roundness": 0.15
        },
        "arrows": {
          "to": { "enabled": true, "scaleFactor": 0.55 }
        }
      },
      "nodes": {
        "font": {
          "size": 11,
          "face": "Inter, Arial, sans-serif"
        }
      }
    }
    """)

    # ── Node degree for sizing ─────────────────────────────────
    degrees = dict(G.degree())

    for n, d in G.nodes(data=True):
        ntype = d.get("ntype", "")
        color = COLORS.get(ntype, "#888888")
        text  = d.get("text", n)

        if ntype == "learner":
            label = f"L{n[2:6]}…"          # short learner id
            size  = 14 + min(degrees[n], 20)
            shape = "dot"
            title = (f"<b>Learner</b>: {n}<br>"
                     f"Enrollments: {degrees[n]}")
            border = "#FFFFFF"

        elif ntype == "course":
            label = _shorten(text, 28)
            size  = 22 + min(degrees[n], 25)
            shape = "box"
            title = (f"<b>Course</b>: {n}<br>"
                     f"{text}<br>"
                     f"Degree: {degrees[n]}")
            border = "#FFC864"

        elif ntype == "concept":
            label = _shorten(text, 20)
            size  = 10 + min(degrees[n] * 2, 15)
            shape = "ellipse"
            title = (f"<b>Concept</b><br>{text}")
            border = "#2DB88A"

        elif ntype == "cluster":
            label = d.get("label", n)
            size  = 28
            shape = "diamond"
            title = (f"<b>{label}</b><br>"
                     f"Learner cluster")
            border = "#A04EE8"

        else:
            label = _shorten(str(n), 18)
            size  = 10
            shape = "dot"
            title = str(n)
            border = color

        net.add_node(
            n,
            label = label,
            color = {
                "background" : color,
                "border"     : border,
                "highlight"  : {"background": "#FFFFFF", "border": border},
                "hover"      : {"background": "#FFFFFF", "border": border},
            },
            size  = size,
            shape = shape,
            title = title,
            font  = {"size": 11 if ntype != "cluster" else 13,
                     "color": "white",
                     "bold" : ntype == "cluster"},
        )

    # ── Edges ──────────────────────────────────────────────────
    for u, v, d in G.edges(data=True):
        etype  = d.get("etype", "")
        weight = float(d.get("weight", 1.0))

        if etype == "enrolled":
            color = EDGE_COLORS["enrolled"]
            width = 1.5 + weight * 3.5
            title = f"enrolled | rating={weight:.2f}"
            dash  = False

        elif etype == "covers":
            color = EDGE_COLORS["covers"]
            width = 1.2
            title = f"covers concept"
            dash  = False

        elif etype == "similar_to":
            color = EDGE_COLORS["similar_to"]
            width = 1.0 + weight * 3.0
            title = f"similar_to | sim={weight:.3f}"
            dash  = True            # dashed to distinguish from covers

        elif etype == "belief":
            color = EDGE_COLORS["belief_pos"] if weight > 0 else EDGE_COLORS["belief_neg"]
            width = 1.0 + abs(weight) * 5.0
            title = f"belief = {weight:.3f}"
            dash  = False

        elif etype == "belongs_to":
            color = EDGE_COLORS["belongs_to"]
            width = 1.0 + weight * 2.5
            title = f"belongs_to | w={weight:.2f}"
            dash  = False

        else:
            color = "#666666"
            width = 1.0
            title = etype
            dash  = False

        net.add_edge(
            u, v,
            color  = color,
            width  = width,
            title  = title,
            dashes = dash,
        )

    # ── HTML wrapper with legend ───────────────────────────────
    net.save_graph(output)
    _inject_legend_kg(output)

    path = os.path.abspath(output)
    print(f"  Saved → {path}")
    return path


def _inject_legend_kg(filepath: str):
    """Inject legend + full interactive control panel into KG HTML."""
    inject = """
<!-- ═══════════════════════════════════════════════════════════
     COCO KG  —  Legend + Control Panel
════════════════════════════════════════════════════════════ -->
<style>
  /* ── Global ───────────────────────────────────────────── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  body { background:#0D1117 !important; margin:0; }

  /* ── Title banner ─────────────────────────────────────── */
  #kg-title {
    position:fixed; top:14px; left:50%; transform:translateX(-50%);
    background:rgba(13,17,23,0.90); border:1px solid #30363d;
    border-radius:10px; padding:7px 28px;
    color:#e6edf3; font-family:Inter,Arial,sans-serif;
    font-size:17px; font-weight:700; z-index:9999;
    backdrop-filter:blur(10px);
    box-shadow:0 2px 16px rgba(0,0,0,0.55);
    letter-spacing:0.3px; white-space:nowrap;
  }

  /* ── Legend panel ─────────────────────────────────────── */
  #kg-legend {
    position:fixed; top:14px; right:14px;
    background:rgba(13,17,23,0.93); border:1px solid #30363d;
    border-radius:12px; padding:14px 16px;
    color:#e6edf3; font-family:Inter,Arial,sans-serif;
    font-size:12.5px; z-index:9999; min-width:200px;
    backdrop-filter:blur(10px);
    box-shadow:0 4px 24px rgba(0,0,0,0.55);
  }
  #kg-legend h3 {
    margin:0 0 9px 0; font-size:13px; font-weight:700;
    color:#58BCFF; letter-spacing:0.4px;
  }
  #kg-legend .lrow { display:flex; align-items:center; margin:5px 0; gap:9px; }
  .l-dot  { width:13px; height:13px; border-radius:50%; flex-shrink:0; }
  .l-box  { width:13px; height:9px;  border-radius:2px; flex-shrink:0; }
  .l-diam { width:11px; height:11px; transform:rotate(45deg); flex-shrink:0; }
  .l-line { width:22px; height:3px;  border-radius:2px; flex-shrink:0; }
  #kg-legend hr { border:none; border-top:1px solid #30363d; margin:8px 0; }

  /* ── Control panel ────────────────────────────────────── */
  #kg-controls {
    position:fixed; bottom:18px; left:50%; transform:translateX(-50%);
    display:flex; gap:8px; align-items:center;
    background:rgba(13,17,23,0.93); border:1px solid #30363d;
    border-radius:14px; padding:10px 18px;
    z-index:9999; backdrop-filter:blur(10px);
    box-shadow:0 4px 24px rgba(0,0,0,0.6);
    flex-wrap:wrap; justify-content:center;
  }
  .ctrl-sep {
    width:1px; height:28px; background:#30363d; margin:0 4px;
  }
  .ctrl-label {
    font-family:Inter,Arial,sans-serif; font-size:10px;
    color:#6e7681; letter-spacing:0.5px; text-transform:uppercase;
    margin-right:2px; align-self:center;
  }

  /* ── Button base ──────────────────────────────────────── */
  .kbtn {
    display:inline-flex; align-items:center; gap:5px;
    padding:6px 13px; border-radius:8px; border:1px solid #30363d;
    background:rgba(255,255,255,0.05);
    color:#c9d1d9; font-family:Inter,Arial,sans-serif;
    font-size:12px; font-weight:600; cursor:pointer;
    transition:all 0.18s ease; white-space:nowrap;
    user-select:none;
  }
  .kbtn:hover  { background:rgba(255,255,255,0.12); border-color:#58BCFF;
                  color:#fff; transform:translateY(-1px); }
  .kbtn:active { transform:translateY(0px); }

  /* ── Specific button colours ──────────────────────────── */
  .kbtn-green  { border-color:#238636; color:#3fb950; }
  .kbtn-green:hover  { background:rgba(35,134,54,0.25); border-color:#3fb950; color:#3fb950; }
  .kbtn-red    { border-color:#da3633; color:#f85149; }
  .kbtn-red:hover    { background:rgba(218,54,51,0.25);  border-color:#f85149; color:#f85149; }
  .kbtn-amber  { border-color:#d29922; color:#e3b341; }
  .kbtn-amber:hover  { background:rgba(210,153,34,0.25); border-color:#e3b341; color:#e3b341; }
  .kbtn-blue   { border-color:#1f6feb; color:#58a6ff; }
  .kbtn-blue:hover   { background:rgba(31,111,235,0.25); border-color:#58a6ff; color:#58a6ff; }
  .kbtn-purple { border-color:#6e40c9; color:#bc8cff; }
  .kbtn-purple:hover { background:rgba(110,64,201,0.25); border-color:#bc8cff; color:#bc8cff; }

  /* ── Active / toggled state ───────────────────────────── */
  .kbtn.active-on  { background:rgba(35,134,54,0.30) !important;
                      border-color:#3fb950 !important; color:#3fb950 !important; }
  .kbtn.active-off { background:rgba(218,54,51,0.30) !important;
                      border-color:#f85149 !important; color:#f85149 !important; }

  /* ── Stats bar ────────────────────────────────────────── */
  #kg-stats {
    position:fixed; bottom:18px; right:14px;
    background:rgba(13,17,23,0.88); border:1px solid #30363d;
    border-radius:10px; padding:7px 13px;
    color:#8b949e; font-family:monospace; font-size:11px;
    z-index:9999; line-height:1.7;
  }
  #kg-stats span { color:#c9d1d9; font-weight:600; }
</style>

<!-- Title -->
<div id="kg-title">📚Knowledge Graph</div>

<!-- Legend -->
<div id="kg-legend">
  <h3>⬡ Node Types</h3>
  <div class="lrow"><div class="l-dot"  style="background:#58BCFF"></div>Learner</div>
  <div class="lrow"><div class="l-box"  style="background:#FF9E3B"></div>Course</div>
  <div class="lrow"><div class="l-dot"  style="background:#4ECBA4;border-radius:30% 70% 70% 30%/30% 30% 70% 70%"></div>Concept</div>
  <div class="lrow"><div class="l-diam" style="background:#C97BF5"></div>&nbsp;Cluster</div>
  <hr>
  <h3>⟶ Edge Types</h3>
  <div class="lrow"><div class="l-line" style="background:#A8D4FF"></div>enrolled</div>
  <div class="lrow"><div class="l-line" style="background:#78E8C0"></div>covers</div>
  <div class="lrow"><div class="l-line" style="background:#FFD580"></div>similar_to</div>
  <div class="lrow"><div class="l-line" style="background:#00FFB0"></div>belief (+)</div>
  <div class="lrow"><div class="l-line" style="background:#FF4F6A"></div>belief (−)</div>
  <div class="lrow"><div class="l-line" style="background:#D9A8FF"></div>belongs_to</div>
</div>

<!-- Control Panel -->
<div id="kg-controls">

  <span class="ctrl-label">Physics</span>
  <button class="kbtn kbtn-red active-off" id="btn-physics"
          onclick="togglePhysics(this)">⏸ Physics OFF</button>
  <button class="kbtn kbtn-amber"
          onclick="stabiliseNow()">⚡ Stabilise</button>

  <div class="ctrl-sep"></div>
  <span class="ctrl-label">Nodes</span>
  <button class="kbtn kbtn-blue"
          onclick="freezeNodes()">🔒 Freeze All</button>
  <button class="kbtn kbtn-blue"
          onclick="unfreezeNodes()">🔓 Unfreeze All</button>

  <div class="ctrl-sep"></div>
  <span class="ctrl-label">View</span>
  <button class="kbtn kbtn-green"
          onclick="fitView()">⊡ Fit View</button>
  <button class="kbtn"
          onclick="zoomIn()">＋ Zoom In</button>
  <button class="kbtn"
          onclick="zoomOut()">－ Zoom Out</button>
  <button class="kbtn kbtn-purple"
          onclick="resetView()">↺ Reset</button>

  <div class="ctrl-sep"></div>
  <span class="ctrl-label">Layout</span>
  <button class="kbtn" id="btn-labels"
          onclick="toggleLabels(this)">🏷 Hide Labels</button>
  <button class="kbtn" id="btn-edges"
          onclick="toggleEdges(this)">👁 Hide Edges</button>

</div>

<!-- Stats -->
<div id="kg-stats">
  Nodes: <span id="stat-nodes">–</span> &nbsp;|&nbsp;
  Edges: <span id="stat-edges">–</span><br>
  Physics: <span id="stat-physics">ON</span> &nbsp;|&nbsp;
  Frozen: <span id="stat-frozen">0</span>
</div>

<script>
// ── Wait for pyvis network object to be ready ──────────────
var _physicsOn   = true;
var _labelsOn    = true;
var _edgesOn     = true;
var _frozenNodes = {};
var _initScale   = null;
var _initPos     = null;

function _getNet() {
  // pyvis stores the network in a variable called `network`
  if (typeof network !== "undefined") return network;
  // fallback: scan window for vis.Network instances
  for (var k in window) {
    try {
      if (window[k] && window[k].body && window[k].fit) return window[k];
    } catch(e) {}
  }
  return null;
}

// ── Physics toggle ─────────────────────────────────────────
function togglePhysics(btn) {
  var net = _getNet(); if (!net) return;
  _physicsOn = !_physicsOn;
  net.setOptions({ physics: { enabled: _physicsOn } });
  if (_physicsOn) {
    btn.textContent  = "⏸ Physics OFF";
    btn.className    = "kbtn kbtn-red active-off";
    document.getElementById("stat-physics").textContent = "ON";
    net.startSimulation();
  } else {
    btn.textContent  = "▶ Physics ON";
    btn.className    = "kbtn kbtn-green active-on";
    document.getElementById("stat-physics").textContent = "OFF";
    net.stopSimulation();
  }
}

// ── Force immediate stabilisation then stop ────────────────
function stabiliseNow() {
  var net = _getNet(); if (!net) return;
  net.setOptions({ physics: { enabled: true } });
  net.stabilize(200);
  setTimeout(function() {
    net.setOptions({ physics: { enabled: false } });
    _physicsOn = false;
    var btn = document.getElementById("btn-physics");
    btn.textContent = "▶ Physics ON";
    btn.className   = "kbtn kbtn-green active-on";
    document.getElementById("stat-physics").textContent = "OFF";
  }, 2500);
}

// ── Freeze / unfreeze all nodes in place ───────────────────
function freezeNodes() {
  var net = _getNet(); if (!net) return;
  var positions = net.getPositions();
  var updates   = [];
  Object.keys(positions).forEach(function(id) {
    updates.push({ id: id,
                   x: positions[id].x, y: positions[id].y,
                   fixed: { x: true, y: true } });
  });
  net.body.data.nodes.update(updates);
  _frozenNodes = positions;
  document.getElementById("stat-frozen").textContent =
    Object.keys(positions).length;
}

function unfreezeNodes() {
  var net = _getNet(); if (!net) return;
  var nodeIds = net.body.data.nodes.getIds();
  var updates = nodeIds.map(function(id) {
    return { id: id, fixed: { x: false, y: false } };
  });
  net.body.data.nodes.update(updates);
  _frozenNodes = {};
  document.getElementById("stat-frozen").textContent = "0";
}

// ── View controls ──────────────────────────────────────────
function fitView() {
  var net = _getNet(); if (!net) return;
  net.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } });
}

function zoomIn() {
  var net = _getNet(); if (!net) return;
  var s = net.getScale();
  net.moveTo({ scale: s * 1.3,
               animation: { duration: 300, easingFunction: "easeInOutQuad" } });
}

function zoomOut() {
  var net = _getNet(); if (!net) return;
  var s = net.getScale();
  net.moveTo({ scale: s * 0.77,
               animation: { duration: 300, easingFunction: "easeInOutQuad" } });
}

function resetView() {
  var net = _getNet(); if (!net) return;
  net.fit({ animation: { duration: 800, easingFunction: "easeInOutQuad" } });
}

// ── Toggle node labels ─────────────────────────────────────
function toggleLabels(btn) {
  var net = _getNet(); if (!net) return;
  _labelsOn = !_labelsOn;
  if (_labelsOn) {
    net.body.data.nodes.get().forEach(function(n) {
      net.body.data.nodes.update({ id: n.id, label: n._origLabel || n.label });
    });
    btn.textContent = "🏷 Hide Labels";
  } else {
    net.body.data.nodes.get().forEach(function(n) {
      if (!n._origLabel) {
        net.body.data.nodes.update({ id: n.id, _origLabel: n.label, label: " " });
      } else {
        net.body.data.nodes.update({ id: n.id, label: " " });
      }
    });
    btn.textContent = "🏷 Show Labels";
  }
}

// ── Toggle edge visibility ─────────────────────────────────
function toggleEdges(btn) {
  var net = _getNet(); if (!net) return;
  _edgesOn = !_edgesOn;
  var edges = net.body.data.edges.get();
  var updates = edges.map(function(e) {
    return { id: e.id, hidden: !_edgesOn };
  });
  net.body.data.edges.update(updates);
  btn.textContent = _edgesOn ? "👁 Hide Edges" : "👁 Show Edges";
}

// ── Populate stats once network is ready ──────────────────
window.addEventListener("load", function() {
  var poll = setInterval(function() {
    var net = _getNet();
    if (!net) return;
    clearInterval(poll);
    // Default: physics OFF after stabilisation
    net.once("stabilized", function() {
      net.setOptions({ physics: { enabled: false } });
      _physicsOn = false;
      var btn = document.getElementById("btn-physics");
      if (btn) {
        btn.textContent = "▶ Physics ON";
        btn.className   = "kbtn kbtn-green active-on";
      }
      document.getElementById("stat-physics").textContent = "OFF";
    });
    // Stats
    var nodeCount = net.body.data.nodes.length;
    var edgeCount = net.body.data.edges.length;
    document.getElementById("stat-nodes").textContent = nodeCount;
    document.getElementById("stat-edges").textContent = edgeCount;
    _initScale = net.getScale();
    _initPos   = net.getViewPosition();
  }, 300);
});
</script>
"""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", inject + "\n</body>")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


# ================================================================
# STEP 10 — PYVIS: NFH BELIEF GRAPH VISUALIZATION
# ================================================================

def build_nfh_subgraph(G: nx.DiGraph) -> nx.DiGraph:
    """Extract only learner + concept nodes connected by belief edges."""
    nfh_G = nx.DiGraph()
    for u, v, d in G.edges(data=True):
        if d.get("etype") == "belief":
            for node in (u, v):
                if not nfh_G.has_node(node):
                    ndata = G.nodes[node]
                    nfh_G.add_node(node, **ndata)
            nfh_G.add_edge(u, v, **d)
    return nfh_G


def visualize_nfh_graph(G: nx.DiGraph, nfh: dict,
                        output: str = NFH_OUTPUT) -> str:
    print(f"\n[VIZ] Rendering NFH Belief Graph → {output}")

    nfh_G = build_nfh_subgraph(G)
    print(f"  NFH nodes: {nfh_G.number_of_nodes()}  |  "
          f"edges: {nfh_G.number_of_edges()}")

    net = Network(
        height   = "920px",
        width    = "100%",
        directed = True,
        bgcolor  = "#060B14",
        font_color = "white",
    )

    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "forceAtlas2Based": {
          "gravitationalConstant": -75,
          "centralGravity": 0.012,
          "springLength": 180,
          "springConstant": 0.08,
          "damping": 0.4,
          "avoidOverlap": 0.5
        },
        "solver": "forceAtlas2Based",
        "minVelocity": 0.5,
        "maxVelocity": 60,
        "stabilization": {
          "enabled": true,
          "iterations": 400,
          "updateInterval": 50
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true
      },
      "edges": {
        "smooth": {
          "type": "dynamic"
        },
        "arrows": {
          "to": { "enabled": true, "scaleFactor": 0.6 }
        }
      }
    }
    """)

    degrees = dict(nfh_G.degree())

    # ── Pre-compute per-learner belief stats for sizing ────────
    learner_strength = defaultdict(float)
    concept_strength = defaultdict(float)
    for u, v, d in nfh_G.edges(data=True):
        w = abs(float(d.get("weight", 0)))
        learner_strength[u] += w
        concept_strength[v] += w

    max_ls = max(learner_strength.values()) if learner_strength else 1.0
    max_cs = max(concept_strength.values()) if concept_strength else 1.0

    for n, d in nfh_G.nodes(data=True):
        ntype = d.get("ntype", "")
        text  = d.get("text", n)

        if ntype == "learner":
            norm_s = learner_strength[n] / max_ls
            # Gradient: weak → muted blue, strong → bright cyan
            r = int(30  + norm_s * 28)
            g = int(140 + norm_s * 100)
            b = int(220 + norm_s * 35)
            color  = f"rgb({r},{g},{b})"
            border = "#FFFFFF"
            label  = f"L{n[2:6]}…"
            size   = 12 + norm_s * 16
            shape  = "dot"
            # Count positive vs negative beliefs
            pos_k = sum(1 for _, _, ed in nfh_G.out_edges(n, data=True)
                        if ed["weight"] > 0)
            neg_k = sum(1 for _, _, ed in nfh_G.out_edges(n, data=True)
                        if ed["weight"] < 0)
            title = (f"<b>Learner</b>: {n}<br>"
                     f"Belief edges: {degrees[n]}<br>"
                     f"Positive beliefs: {pos_k}<br>"
                     f"Negative beliefs: {neg_k}")

        elif ntype == "concept":
            norm_s = concept_strength[n] / max_cs
            # Gradient: low belief → dim teal, high belief → bright lime
            r = int(20  + norm_s * 80)
            g = int(190 + norm_s * 65)
            b = int(140 - norm_s * 80)
            color  = f"rgb({r},{g},{b})"
            border = "#1EE8A8"
            label  = _shorten(text, 22)
            size   = 10 + norm_s * 18
            shape  = "ellipse"
            title  = (f"<b>Concept</b><br>{text}<br>"
                      f"Belief strength: {concept_strength[n]:.3f}")

        else:
            color  = "#888888"
            border = "#AAAAAA"
            label  = _shorten(str(n), 18)
            size   = 10
            shape  = "dot"
            title  = str(n)

        net.add_node(
            n,
            label = label,
            color = {
                "background" : color,
                "border"     : border,
                "highlight"  : {"background": "#FFFFFF", "border": border},
                "hover"      : {"background": "#FFFFFF", "border": border},
            },
            size  = int(size),
            shape = shape,
            title = title,
            font  = {"size": 10, "color": "white"},
        )

    # ── Belief edges with colour gradient ─────────────────────
    all_weights = [abs(float(d["weight"]))
                   for _, _, d in nfh_G.edges(data=True)]
    max_w = max(all_weights) if all_weights else 1.0

    for u, v, d in nfh_G.edges(data=True):
        w    = float(d.get("weight", 0))
        norm = abs(w) / max_w

        if w > 0:
            # Positive belief: dark green → bright neon green
            r = int(0   + norm * 30)
            g = int(180 + norm * 75)
            b = int(80  + norm * 30)
            color = f"rgb({r},{g},{b})"
            title = f"✅ Belief = +{w:.3f}"
        else:
            # Negative belief: dark red → bright coral
            r = int(180 + norm * 75)
            g = int(20  + norm * 40)
            b = int(30  + norm * 20)
            color = f"rgb({r},{g},{b})"
            title = f"❌ Belief = {w:.3f}"

        width = 1.0 + norm * 6.0

        net.add_edge(
            u, v,
            color = color,
            width = width,
            title = title,
        )

    net.save_graph(output)
    _inject_legend_nfh(output)

    path = os.path.abspath(output)
    print(f"  Saved → {path}")
    return path


def _inject_legend_nfh(filepath: str):
    """Inject legend + full interactive control panel into NFH HTML."""
    inject = """
<!-- ═══════════════════════════════════════════════════════════
     COCO NFH  —  Legend + Control Panel
════════════════════════════════════════════════════════════ -->
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  body { background:#060B14 !important; margin:0; }

  #nfh-title {
    position:fixed; top:14px; left:50%; transform:translateX(-50%);
    background:rgba(6,11,20,0.92); border:1px solid #1a2637;
    border-radius:10px; padding:7px 28px;
    color:#c9d9eb; font-family:Inter,Arial,sans-serif;
    font-size:17px; font-weight:700; z-index:9999;
    backdrop-filter:blur(10px);
    box-shadow:0 2px 16px rgba(0,0,0,0.7);
    letter-spacing:0.3px; white-space:nowrap;
  }

  #nfh-legend {
    position:fixed; top:14px; right:14px;
    background:rgba(6,11,20,0.93); border:1px solid #1a2637;
    border-radius:12px; padding:14px 16px;
    color:#c9d9eb; font-family:Inter,Arial,sans-serif;
    font-size:12.5px; z-index:9999; min-width:200px;
    backdrop-filter:blur(10px);
    box-shadow:0 4px 24px rgba(0,0,0,0.7);
  }
  #nfh-legend h3 {
    margin:0 0 9px 0; font-size:13px; font-weight:700;
    color:#1EE8A8; letter-spacing:0.4px;
  }
  #nfh-legend .lrow { display:flex; align-items:center; margin:5px 0; gap:9px; }
  .n-dot  { width:13px; height:13px; border-radius:50%; flex-shrink:0; }
  .n-ell  { width:18px; height:10px; border-radius:50%; flex-shrink:0; }
  .n-line { width:22px; height:3px;  border-radius:2px; flex-shrink:0; }
  #nfh-legend hr { border:none; border-top:1px solid #1a2637; margin:8px 0; }

  #nfh-formula {
    position:fixed; bottom:18px; left:14px;
    background:rgba(6,11,20,0.88); border:1px solid #1a2637;
    border-radius:10px; padding:8px 14px;
    color:#6a8baf; font-family:monospace; font-size:11px;
    z-index:9999; max-width:290px; line-height:1.7;
  }

  /* ── Control panel — same design, dark navy theme ──────── */
  #nfh-controls {
    position:fixed; bottom:18px; left:50%; transform:translateX(-50%);
    display:flex; gap:8px; align-items:center;
    background:rgba(6,11,20,0.93); border:1px solid #1a2637;
    border-radius:14px; padding:10px 18px;
    z-index:9999; backdrop-filter:blur(10px);
    box-shadow:0 4px 24px rgba(0,0,0,0.7);
    flex-wrap:wrap; justify-content:center;
  }
  .nctrl-sep   { width:1px; height:28px; background:#1a2637; margin:0 4px; }
  .nctrl-label {
    font-family:Inter,Arial,sans-serif; font-size:10px;
    color:#4a6280; letter-spacing:0.5px; text-transform:uppercase;
    margin-right:2px; align-self:center;
  }
  .nbtn {
    display:inline-flex; align-items:center; gap:5px;
    padding:6px 13px; border-radius:8px; border:1px solid #1a2637;
    background:rgba(255,255,255,0.04);
    color:#8baacc; font-family:Inter,Arial,sans-serif;
    font-size:12px; font-weight:600; cursor:pointer;
    transition:all 0.18s ease; white-space:nowrap; user-select:none;
  }
  .nbtn:hover  { background:rgba(255,255,255,0.10); border-color:#1EE8A8;
                  color:#fff; transform:translateY(-1px); }
  .nbtn:active { transform:translateY(0); }
  .nbtn-green  { border-color:#1a4a30; color:#1EE8A8; }
  .nbtn-green:hover  { background:rgba(30,232,168,0.15); border-color:#1EE8A8; color:#1EE8A8; }
  .nbtn-red    { border-color:#4a1a1a; color:#FF4F6A; }
  .nbtn-red:hover    { background:rgba(255,79,106,0.18);  border-color:#FF4F6A; color:#FF4F6A; }
  .nbtn-amber  { border-color:#4a3a10; color:#FFD580; }
  .nbtn-amber:hover  { background:rgba(255,213,128,0.15); border-color:#FFD580; color:#FFD580; }
  .nbtn-blue   { border-color:#1a2a4a; color:#58BCFF; }
  .nbtn-blue:hover   { background:rgba(88,188,255,0.15);  border-color:#58BCFF; color:#58BCFF; }
  .nbtn-purple { border-color:#2a1a4a; color:#BC8CFF; }
  .nbtn-purple:hover { background:rgba(188,140,255,0.15); border-color:#BC8CFF; color:#BC8CFF; }
  .nbtn.active-on  { background:rgba(30,232,168,0.20) !important;
                      border-color:#1EE8A8 !important; color:#1EE8A8 !important; }
  .nbtn.active-off { background:rgba(255,79,106,0.20) !important;
                      border-color:#FF4F6A !important; color:#FF4F6A !important; }

  #nfh-stats {
    position:fixed; bottom:18px; right:14px;
    background:rgba(6,11,20,0.88); border:1px solid #1a2637;
    border-radius:10px; padding:7px 13px;
    color:#4a6280; font-family:monospace; font-size:11px;
    z-index:9999; line-height:1.7;
  }
  #nfh-stats span { color:#8baacc; font-weight:600; }
</style>

<!-- Title -->
<div id="nfh-title">Neutrosophic Fuzzy Hypergraph</div>

<!-- Legend -->
<div id="nfh-legend">
  <h3>⬡ Node Types</h3>
  <div class="lrow">
    <div class="n-dot" style="background:linear-gradient(135deg,#1E8CDC,#3EE4FF)"></div>
    Learner (size = Σ|belief|)
  </div>
  <div class="lrow">
    <div class="n-ell" style="background:linear-gradient(135deg,#14BE8C,#AAFF80)"></div>
    Concept (size = belief strength)
  </div>
  <hr>
  <h3>⟶ Edge Types</h3>
  <div class="lrow">
    <div class="n-line" style="background:linear-gradient(90deg,#00B460,#00FF80)"></div>
    Positive belief &nbsp;<small style="color:#4a6280">(b &gt; 0)</small>
  </div>
  <div class="lrow">
    <div class="n-line" style="background:linear-gradient(90deg,#B41430,#FF4464)"></div>
    Negative belief &nbsp;<small style="color:#4a6280">(b &lt; 0)</small>
  </div>
  <hr>
  <small style="color:#4a6280">Thickness ∝ |belief score|</small>
</div>

<!-- Control Panel -->
<div id="nfh-controls">

  <span class="nctrl-label">Physics</span>
  <button class="nbtn nbtn-red active-off" id="nbtn-physics"
          onclick="nTogglePhysics(this)">⏸ Physics OFF</button>
  <button class="nbtn nbtn-amber"
          onclick="nStabilise()">⚡ Stabilise</button>

  <div class="nctrl-sep"></div>
  <span class="nctrl-label">Nodes</span>
  <button class="nbtn nbtn-blue"  onclick="nFreeze()">🔒 Freeze All</button>
  <button class="nbtn nbtn-blue"  onclick="nUnfreeze()">🔓 Unfreeze All</button>

  <div class="nctrl-sep"></div>
  <span class="nctrl-label">View</span>
  <button class="nbtn nbtn-green" onclick="nFitView()">⊡ Fit View</button>
  <button class="nbtn"            onclick="nZoomIn()">＋ Zoom In</button>
  <button class="nbtn"            onclick="nZoomOut()">－ Zoom Out</button>
  <button class="nbtn nbtn-purple" onclick="nReset()">↺ Reset</button>

  <div class="nctrl-sep"></div>
  <span class="nctrl-label">Display</span>
  <button class="nbtn" id="nbtn-labels" onclick="nToggleLabels(this)">🏷 Hide Labels</button>
  <button class="nbtn" id="nbtn-edges"  onclick="nToggleEdges(this)">👁 Hide Edges</button>

</div>

<!-- Formula box -->
<div id="nfh-formula">
  <b style="color:#8baacc">Belief score:</b> b = 1.5 × (T − Fv) × (1 − I)<br>
  <b style="color:#8baacc">T</b> = truth mass &nbsp;|&nbsp;
  <b style="color:#8baacc">Fv</b> = falsity mass<br>
  <b style="color:#8baacc">I</b> = indeterminacy (↑ with fewer evidence items)
</div>

<!-- Stats -->
<div id="nfh-stats">
  Nodes: <span id="nstat-nodes">–</span> &nbsp;|&nbsp;
  Edges: <span id="nstat-edges">–</span><br>
  Physics: <span id="nstat-physics">ON</span> &nbsp;|&nbsp;
  Frozen: <span id="nstat-frozen">0</span>
</div>

<script>
var _nPhysicsOn = true;
var _nLabelsOn  = true;
var _nEdgesOn   = true;

function _nGetNet() {
  if (typeof network !== "undefined") return network;
  for (var k in window) {
    try { if (window[k] && window[k].body && window[k].fit) return window[k]; }
    catch(e) {}
  }
  return null;
}

function nTogglePhysics(btn) {
  var net = _nGetNet(); if (!net) return;
  _nPhysicsOn = !_nPhysicsOn;
  net.setOptions({ physics: { enabled: _nPhysicsOn } });
  if (_nPhysicsOn) {
    btn.textContent = "⏸ Physics OFF";
    btn.className   = "nbtn nbtn-red active-off";
    document.getElementById("nstat-physics").textContent = "ON";
    net.startSimulation();
  } else {
    btn.textContent = "▶ Physics ON";
    btn.className   = "nbtn nbtn-green active-on";
    document.getElementById("nstat-physics").textContent = "OFF";
    net.stopSimulation();
  }
}

function nStabilise() {
  var net = _nGetNet(); if (!net) return;
  net.setOptions({ physics: { enabled: true } });
  net.stabilize(200);
  setTimeout(function() {
    net.setOptions({ physics: { enabled: false } });
    _nPhysicsOn = false;
    var btn = document.getElementById("nbtn-physics");
    btn.textContent = "▶ Physics ON";
    btn.className   = "nbtn nbtn-green active-on";
    document.getElementById("nstat-physics").textContent = "OFF";
  }, 2500);
}

function nFreeze() {
  var net = _nGetNet(); if (!net) return;
  var pos  = net.getPositions();
  var upd  = Object.keys(pos).map(function(id) {
    return { id:id, x:pos[id].x, y:pos[id].y, fixed:{x:true,y:true} };
  });
  net.body.data.nodes.update(upd);
  document.getElementById("nstat-frozen").textContent = upd.length;
}

function nUnfreeze() {
  var net = _nGetNet(); if (!net) return;
  var upd = net.body.data.nodes.getIds().map(function(id) {
    return { id:id, fixed:{x:false,y:false} };
  });
  net.body.data.nodes.update(upd);
  document.getElementById("nstat-frozen").textContent = "0";
}

function nFitView() {
  var net = _nGetNet(); if (!net) return;
  net.fit({ animation: { duration:600, easingFunction:"easeInOutQuad" } });
}

function nZoomIn() {
  var net = _nGetNet(); if (!net) return;
  net.moveTo({ scale: net.getScale()*1.3,
               animation:{duration:300,easingFunction:"easeInOutQuad"} });
}

function nZoomOut() {
  var net = _nGetNet(); if (!net) return;
  net.moveTo({ scale: net.getScale()*0.77,
               animation:{duration:300,easingFunction:"easeInOutQuad"} });
}

function nReset() {
  var net = _nGetNet(); if (!net) return;
  net.fit({ animation:{duration:800,easingFunction:"easeInOutQuad"} });
}

function nToggleLabels(btn) {
  var net = _nGetNet(); if (!net) return;
  _nLabelsOn = !_nLabelsOn;
  net.body.data.nodes.get().forEach(function(n) {
    if (_nLabelsOn) {
      net.body.data.nodes.update({id:n.id, label: n._orig || n.label});
    } else {
      if (!n._orig) net.body.data.nodes.update({id:n.id, _orig:n.label, label:" "});
      else          net.body.data.nodes.update({id:n.id, label:" "});
    }
  });
  btn.textContent = _nLabelsOn ? "🏷 Hide Labels" : "🏷 Show Labels";
}

function nToggleEdges(btn) {
  var net = _nGetNet(); if (!net) return;
  _nEdgesOn = !_nEdgesOn;
  net.body.data.edges.update(
    net.body.data.edges.get().map(function(e) {
      return {id:e.id, hidden:!_nEdgesOn};
    })
  );
  btn.textContent = _nEdgesOn ? "👁 Hide Edges" : "👁 Show Edges";
}

window.addEventListener("load", function() {
  var poll = setInterval(function() {
    var net = _nGetNet(); if (!net) return;
    clearInterval(poll);
    net.once("stabilized", function() {
      net.setOptions({ physics:{enabled:false} });
      _nPhysicsOn = false;
      var btn = document.getElementById("nbtn-physics");
      if (btn) { btn.textContent="▶ Physics ON"; btn.className="nbtn nbtn-green active-on"; }
      document.getElementById("nstat-physics").textContent = "OFF";
    });
    document.getElementById("nstat-nodes").textContent = net.body.data.nodes.length;
    document.getElementById("nstat-edges").textContent = net.body.data.edges.length;
  }, 300);
});
</script>
"""
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</body>", inject + "\n</body>")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)


# ================================================================
# MAIN PIPELINE
# ================================================================

def print_graph_summary(G: nx.DiGraph, label: str = "Graph"):
    print(f"\n{'─'*50}")
    print(f" {label} Summary")
    print(f"{'─'*50}")
    ntypes = defaultdict(int)
    etypes = defaultdict(int)
    for _, d in G.nodes(data=True):
        ntypes[d.get("ntype","?")] += 1
    for _, _, d in G.edges(data=True):
        etypes[d.get("etype","?")] += 1
    print(f" Nodes: {G.number_of_nodes()}")
    for k, v in sorted(ntypes.items()):
        print(f"   {k:<14}: {v}")
    print(f" Edges: {G.number_of_edges()}")
    for k, v in sorted(etypes.items()):
        print(f"   {k:<14}: {v}")
    print(f"{'─'*50}")


def main():
    # ── 1. Load data ───────────────────────────────────────────
    df = load_and_slice(CSV_PATH)

    # ── 2. Build KG ────────────────────────────────────────────
    G = build_kg(df)

    # ── 3. Node features ───────────────────────────────────────
    print("\n[STEP 3] Building node features...")
    node_features = build_node_features(G)
    print(f"  Feature vectors built for {len(node_features)} nodes  "
          f"(dim={next(iter(node_features.values())).shape[0]})")

    # ── 4. Course similarity edges ─────────────────────────────
    G = add_course_similarity_edges(G, node_features)

    # ── 5. NFH ─────────────────────────────────────────────────
    nfh = build_nfh(G, node_features, tau=3)

    # ── 6. Belief edges ────────────────────────────────────────
    G = add_belief_edges(G, nfh, eps=BELIEF_EPS)

    # ── 7. Fuzzy clusters ──────────────────────────────────────
    learners, X = build_belief_matrix(nfh)
    if len(learners) > 0:
        U = fuzzy_cluster(X, N_CLUSTERS)
        G = add_cluster_nodes(G, learners, U)

    print_graph_summary(G, "Full KG (with NFH + Clusters)")

    # ── 8. Save GEXF (optional — matches main code) ────────────
    try:
        nx.write_gexf(G, "full_pipeline_graph_250_nodes.gexf")
        nfh_G = build_nfh_subgraph(G)
        nx.write_gexf(nfh_G, "nfh_only_graph_250_nodes.gexf")
        print("\n[INFO] GEXF files saved — compatible with your existing visualize_*.py script.")
    except Exception as e:
        print(f"[WARN] GEXF save failed: {e}")

    # ── 9. Visualise ───────────────────────────────────────────
    full_path = visualize_full_kg(G, FULL_OUTPUT)
    nfh_path  = visualize_nfh_graph(G, nfh, NFH_OUTPUT)

    # ── 10. Open in browser ────────────────────────────────────
    import webbrowser
    print("\n[DONE] Opening graphs in browser...")
    webbrowser.open("file://" + full_path)
    webbrowser.open("file://" + nfh_path)

    print(f"\n  Full KG  → {full_path}")
    print(f"  NFH Graph→ {nfh_path}")


if __name__ == "__main__":
    main()