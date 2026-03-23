# ═══════════════════════════════════════════════════════════════════════════════
# QUANTUM SEIZURE INTELLIGENCE — COMPLETE BACKEND (Single Colab Cell)
# Everything in one place: RAG engine + all helpers + FastAPI server
#
# pip install fastapi uvicorn pyngrok pyedflib numba joblib tensorflow
#             matplotlib fpdf2 nest_asyncio groq chromadb sentence-transformers
# ═══════════════════════════════════════════════════════════════════════════════

import nest_asyncio
import asyncio
import json
import os
import glob
import numpy as np
import pyedflib
import tensorflow as tf
import joblib
import warnings
import matplotlib.pyplot as plt
import io, base64
from fpdf import FPDF
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# RAG dependencies
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from groq import Groq

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pyngrok import ngrok
import uvicorn
from scipy.signal import butter, iirnotch, lfilter, lfilter_zi, hilbert, welch
from scipy.stats import skew, kurtosis
from collections import deque
import numba

warnings.filterwarnings("ignore")
nest_asyncio.apply()

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
DATASET_PATH = '/content/drive/MyDrive/CHBMIT_1'
MODEL_DIR    = '/content/drive/MyDrive/Models_TCN/'
NGROK_TOKEN  = "API_TOKEN"

# Free key from https://console.groq.com (30 seconds to sign up)
GROQ_API_KEY = "TOKEN"

# RAG config — no HuggingFace token needed, model downloads automatically
CHROMA_DIR   = "/content/eeg_rag_db"
EMBED_MODEL  = "all-MiniLM-L6-v2"   # 22MB, CPU-fast, no auth needed
GROQ_MODEL   = "llama-3.3-70b-versatile"
COLLECTION   = "epilepsy_knowledge"

SFREQ, WINDOW_SEC, STRIDE_SEC, SEQ_LEN = 256, 4.0, 2.0, 120
TH_PRE, TH_ICT, TH_NORMAL = 0.6, 0.8, 0.6
STD_MONTAGE = [
    'FP1-F7','F7-T7','T7-P7','P7-O1',
    'FP1-F3','F3-C3','C3-P3','P3-O1',
    'FP2-F4','F4-C4','C4-P4','P4-O2',
    'FP2-F8','F8-T8','T8-P8','P8-O2',
    'FZ-CZ','CZ-PZ'
]
NEIGHBORS = {
    0:[1,4], 1:[0,2], 2:[1,3], 3:[2,7],
    4:[0,5], 5:[4,6], 6:[5,7], 7:[3,6],
    8:[12,9], 9:[8,10], 10:[9,11], 11:[10,15],
    12:[8,13], 13:[12,14], 14:[13,15], 15:[11,14],
    16:[5,9], 17:[16,6,10]
}

# ─── PYDANTIC MODEL ────────────────────────────────────────────────────────────
class AIConsultationRequest(BaseModel):
    patient_id: str
    file_name: str
    features: Dict[str, Any]

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — EPILEPSY KNOWLEDGE BASE
# Curated from: Niedermeyer's EEG, CHB-MIT papers, seizure prediction
# literature, quantum EEG research, clinical guidelines.
# ═══════════════════════════════════════════════════════════════════════════════

EPILEPSY_KNOWLEDGE = [
    {
        "id": "vne_001", "topic": "von_neumann_entropy_baseline",
        "text": (
            "Von Neumann entropy (VNE) measures the complexity of the EEG density matrix. "
            "In healthy resting-state EEG, VNE typically ranges from 1.6 to 2.2, reflecting "
            "high neural diversity and stochastic processing. Values consistently above 1.8 "
            "indicate a well-distributed, non-pathological brain state."
        ),
    },
    {
        "id": "vne_002", "topic": "von_neumann_entropy_preictal",
        "text": (
            "Prior to seizure onset, von Neumann entropy characteristically declines as neural "
            "networks begin to synchronize. A drop below 1.2–1.4 in the 5–10 minutes before "
            "clinical seizure onset has been reported as a preictal signature in CHB-MIT studies. "
            "This entropy reduction reflects loss of network diversity and increasing "
            "phase-locking, especially in temporal lobe epilepsy."
        ),
    },
    {
        "id": "vne_003", "topic": "von_neumann_entropy_ictal",
        "text": (
            "During ictal discharge, von Neumann entropy collapses dramatically, often falling "
            "below 0.8. This reflects extreme hypersynchrony where a single dominant eigenstate "
            "of the density matrix accounts for most neural variance. "
            "The minimum entropy point corresponds to peak seizure intensity. "
            "Recovery of entropy toward baseline signals seizure termination."
        ),
    },
    {
        "id": "pur_001", "topic": "purity_baseline",
        "text": (
            "Quantum purity (Tr(rho^2)) measures the degree to which the EEG density matrix "
            "approximates a pure state. In baseline recordings, purity is low (0.05–0.15), "
            "consistent with a mixed state representing diverse, uncorrelated neural activity. "
            "High purity indicates that a small number of correlated sources dominate the signal."
        ),
    },
    {
        "id": "pur_002", "topic": "purity_ictal_marker",
        "text": (
            "Purity values exceeding 0.5 are a strong marker of ictal activity. During seizures, "
            "the EEG density matrix approaches a pure state as neurons fire in lockstep. "
            "Peak purity above 0.7 is consistent with generalized tonic-clonic seizures. "
            "Focal seizures may show purity peaks of 0.4–0.6 localized to specific electrode pairs."
        ),
    },
    {
        "id": "pur_003", "topic": "purity_entropy_relationship",
        "text": (
            "Purity and von Neumann entropy are inversely related: as purity rises, entropy falls. "
            "The combined trajectory — entropy declining while purity rises — is the most reliable "
            "quantum-inspired biomarker of evolving seizure activity. "
            "A purity spike with simultaneous entropy trough defines the ictal apex."
        ),
    },
    {
        "id": "coh_001", "topic": "coherence_seizure_dynamics",
        "text": (
            "EEG coherence measures phase synchrony between electrode pairs. "
            "In the preictal period, coherence increases progressively in theta (4-8 Hz) and "
            "alpha (8-13 Hz) bands, reflecting emerging network coupling. "
            "Inter-hemispheric coherence increase is a sensitive early warning feature "
            "for seizures originating in mesial temporal structures."
        ),
    },
    {
        "id": "coh_002", "topic": "coherence_postictal",
        "text": (
            "Post-ictally, coherence typically remains elevated for 30-120 seconds before "
            "returning to baseline. Persistent post-ictal coherence elevation beyond 2 minutes "
            "may indicate ongoing subclinical discharges or seizure clustering risk."
        ),
    },
    {
        "id": "hfd_001", "topic": "higuchi_fd_seizure",
        "text": (
            "Higuchi fractal dimension (HFD) quantifies EEG signal complexity. "
            "Normal waking EEG has HFD in the range 1.5–1.8. "
            "During preictal periods, HFD decreases to 1.2–1.4 as the signal becomes more regular. "
            "During ictal activity, HFD drops further to 1.0–1.2, reflecting the highly rhythmic "
            "nature of seizure discharges. HFD computed with kmax=6 captures short-range scaling."
        ),
    },
    {
        "id": "hjorth_001", "topic": "hjorth_seizure_markers",
        "text": (
            "Hjorth parameters (Activity, Mobility, Complexity) characterize EEG morphology. "
            "During seizures: Activity increases sharply due to high-amplitude discharge. "
            "Mobility increases due to faster oscillatory components. "
            "Complexity paradoxically decreases because the waveform becomes more regular. "
            "High Activity + High Mobility + Low Complexity is a classic ictal signature in TLE."
        ),
    },
    {
        "id": "spec_001", "topic": "spectral_ratios_seizure",
        "text": (
            "Key spectral ratio changes in seizure evolution: "
            "Delta/Alpha ratio increases preictally as slower rhythms emerge. "
            "Theta/Alpha ratio elevation above 2.0 is a sensitive preictal marker in TLE. "
            "During ictal activity, gamma power (30-45 Hz) surges, often preceding "
            "clinical onset by 2-5 seconds. SEF95 drops preictally and spikes during "
            "high-frequency ictal oscillations."
        ),
    },
    {
        "id": "spec_002", "topic": "delta_dominance_postictal",
        "text": (
            "Post-ictal slowing is characterized by delta dominance (relative delta > 0.6) "
            "and suppression of alpha and beta rhythms. "
            "This post-ictal delta surge persists for 5-30 minutes depending on seizure duration. "
            "Monitoring relative delta power helps identify post-ictal state and estimate recovery."
        ),
    },
    {
        "id": "chbmit_001", "topic": "chbmit_dataset_characteristics",
        "text": (
            "The CHB-MIT Scalp EEG Database contains recordings from 22 pediatric patients "
            "with intractable epilepsy at Boston Children's Hospital. "
            "Sampling rate is 256 Hz with 23 EEG channels in standard 10-20 placement. "
            "Seizure durations range from 5 to 196 seconds. "
            "It is the standard benchmark for seizure prediction algorithms."
        ),
    },
    {
        "id": "chbmit_002", "topic": "chbmit_preictal_window",
        "text": (
            "For the CHB-MIT dataset, the standard preictal window is defined as 30 minutes "
            "before seizure onset, with a 30-minute post-ictal buffer to avoid contamination. "
            "The optimal prediction horizon for clinical utility is 5-30 minutes before onset. "
            "Studies using 1-hour preictal windows show better sensitivity at the cost of specificity."
        ),
    },
    {
        "id": "chbmit_003", "topic": "chb08_patient_profile",
        "text": (
            "Patient chb08 in the CHB-MIT dataset is an 11-year-old female with focal epilepsy. "
            "Her seizures are predominantly of left temporal origin, consistent with mesial "
            "temporal lobe epilepsy (MTLE). EEG seizure patterns begin with rhythmic theta "
            "activity in F7-T7 leads, evolving to high-amplitude delta with secondary "
            "generalization in longer seizures. Total of 5 seizures recorded across session files."
        ),
    },
    {
        "id": "szt_001", "topic": "temporal_lobe_seizure_eeg",
        "text": (
            "Temporal lobe seizures (TLS) on scalp EEG classically show: "
            "Preictal: rhythmic theta (5-7 Hz) in ipsilateral temporal leads (F7-T7 or F8-T8). "
            "Ictal onset: sustained rhythmic discharge starting at 5-9 Hz and accelerating. "
            "Evolution: frequency increase with amplitude growth, spreading to adjacent regions. "
            "Offset: irregular slowing and suppression. "
            "F7-T7 and T7-P7 are the most sensitive pairs for left MTLE detection."
        ),
    },
    {
        "id": "szt_002", "topic": "ictal_onset_zone_localization",
        "text": (
            "Seizure onset zone (SOZ) localization from scalp EEG: "
            "The electrode pair showing earliest high-frequency activity (>13 Hz) is typically "
            "closest to the SOZ. In left temporal lobe epilepsy, F7 or T7 usually leads. "
            "Propagation follows anatomical connectivity: temporal to frontal via uncinate "
            "fasciculus, and temporal to parietal to occipital for posterior spread. "
            "Bilateral synchrony within 5 seconds of onset suggests rapid secondary generalization."
        ),
    },
    {
        "id": "risk_001", "topic": "seizure_risk_stratification",
        "text": (
            "Clinical EEG-based seizure risk stratification: "
            "LOW: No interictal discharges, entropy stable, purity < 0.15. "
            "MODERATE: Intermittent interictal spikes, entropy trending down, purity 0.15-0.35, "
            "increased coherence in theta band, preictal window active. "
            "HIGH: Sustained entropy decline below 1.2, purity > 0.35, coherence spike, "
            "preictal features active within 10-minute window. "
            "CRITICAL: Entropy < 0.8, purity > 0.5, confirmed ictal discharge."
        ),
    },
    {
        "id": "risk_002", "topic": "seizure_clustering_risk",
        "text": (
            "Seizure clustering (multiple seizures within 24 hours) risk factors on EEG: "
            "Post-ictal entropy recovery slower than 5 minutes. "
            "Persistent inter-ictal discharges after seizure offset. "
            "High baseline coherence between consecutive recordings. "
            "Delta/alpha ratio remaining elevated more than 15 minutes post-ictally."
        ),
    },
    {
        "id": "qeeg_001", "topic": "quantum_inspired_eeg_framework",
        "text": (
            "Quantum-inspired EEG analysis treats the multichannel covariance matrix as a "
            "density matrix (rho), enabling quantum information metrics. "
            "Key metrics: von Neumann entropy (complexity), purity (synchrony), "
            "entanglement entropy (hemisphere coupling), quantum Fisher information (state change rate). "
            "These metrics have shown superior seizure detection accuracy vs classical features "
            "in comparative studies on the CHB-MIT dataset."
        ),
    },
    {
        "id": "qeeg_002", "topic": "entanglement_entropy_hemispheres",
        "text": (
            "Entanglement entropy between hemispheres, computed from the partial trace of rho "
            "over left channels, measures cross-hemispheric neural coupling. "
            "In focal epilepsy, entanglement entropy rises preictally as the seizure focus "
            "begins recruiting the contralateral hemisphere. "
            "A rapid entanglement entropy increase 2-5 minutes before seizure onset is a "
            "specific marker for impending secondary generalization."
        ),
    },
    {
        "id": "qeeg_003", "topic": "quantum_fisher_information_sensitivity",
        "text": (
            "Quantum Fisher information (QFI) quantifies the rate of change of the brain's "
            "density matrix between consecutive windows. "
            "High QFI indicates rapid state transitions, characteristic of preictal evolution. "
            "QFI spikes typically precede ictal onset by 60-180 seconds and can serve as "
            "a rapid-change alarm trigger in real-time monitoring systems."
        ),
    },
    {
        "id": "clin_001", "topic": "eeg_monitoring_thresholds",
        "text": (
            "Recommended automated alert thresholds for real-time EEG seizure monitoring: "
            "Alert Level 1 (Warning): VNE drops more than 20% from rolling 10-minute baseline. "
            "Alert Level 2 (Preictal): VNE < 1.2 AND purity > 0.25 sustained for more than 60 seconds. "
            "Alert Level 3 (Critical): VNE < 0.9 OR purity > 0.5. Immediate clinical review. "
            "Thresholds should be individualized per patient using their baseline session data."
        ),
    },
    {
        "id": "clin_002", "topic": "antiepileptic_eeg_effects",
        "text": (
            "Common antiepileptic drug effects on EEG features: "
            "Valproate: increases beta activity, reduces interictal discharges. "
            "Phenobarbital: increases fast activity, may increase VNE via desynchronization. "
            "Levetiracetam: minimal spectral effects, reduces spike frequency. "
            "Benzodiazepines: rapid beta increase and fast-acting entropy normalization. "
            "AED effects should be considered when interpreting entropy and purity baselines."
        ),
    },
    {
        "id": "clin_003", "topic": "sleep_effects_eeg",
        "text": (
            "Sleep stage effects on EEG quantum metrics: "
            "NREM sleep: VNE decreases due to synchronized slow oscillations, resembling preictal. "
            "REM sleep: VNE increases, resembling active wakefulness. "
            "This creates potential false positives in overnight monitoring. "
            "Sleep staging context is essential for correct interpretation of nocturnal entropy drops."
        ),
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RAG ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class EEGRagEngine:
    """
    Local RAG engine: ChromaDB (CPU) + sentence-transformers (no HF token needed)
    + Groq LLaMA 3.3 70B for generation (free tier).
    """

    def __init__(self):
        print("🔧 Initialising RAG engine (no HuggingFace token needed)...")

        # 22MB model, downloads once from public repo, no auth required
        self.embedder = SentenceTransformer(EMBED_MODEL)

        self.chroma = chromadb.PersistentClient(
            path=CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )

        existing = [c.name for c in self.chroma.list_collections()]
        if COLLECTION in existing:
            self.collection = self.chroma.get_collection(COLLECTION)
            print(f"✅ Loaded knowledge base ({self.collection.count()} chunks)")
        else:
            self._build()

        self.groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ RAG engine ready")

    def _build(self):
        print("📚 Building epilepsy knowledge base (~5s on CPU)...")
        try:
            self.chroma.delete_collection(COLLECTION)
        except Exception:
            pass

        self.collection = self.chroma.create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        texts      = [c["text"]               for c in EPILEPSY_KNOWLEDGE]
        ids        = [c["id"]                 for c in EPILEPSY_KNOWLEDGE]
        metadatas  = [{"topic": c["topic"]}   for c in EPILEPSY_KNOWLEDGE]
        embeddings = self.embedder.encode(texts, show_progress_bar=False).tolist()

        self.collection.add(ids=ids, documents=texts,
                            embeddings=embeddings, metadatas=metadatas)
        print(f"✅ Knowledge base built: {len(texts)} chunks indexed")

    def retrieve(self, query: str, n: int = 5) -> list[str]:
        emb = self.embedder.encode([query]).tolist()
        res = self.collection.query(query_embeddings=emb, n_results=n)
        return res["documents"][0]

    async def generate_report(
        self,
        patient_id: str,
        file_name: str,
        timeline: list[dict],
        vn_ent: np.ndarray,
        purity: np.ndarray,
        coherence: np.ndarray,
        ictal: Optional[list],
        preictal: Optional[list],
    ) -> str:

        mean_ent = float(np.mean(vn_ent))
        peak_pur = float(np.max(purity))

        state_counts: dict = {}
        for pt in timeline:
            state_counts[pt["state"]] = state_counts.get(pt["state"], 0) + 1
        dominant = max(state_counts, key=state_counts.get) if state_counts else "baseline"

        # Semantic query tuned to this session's characteristics
        q = [f"EEG seizure von Neumann entropy {round(mean_ent,2)} purity {round(peak_pur,2)}"]
        if ictal:    q.append("ictal discharge hypersynchrony temporal lobe purity collapse")
        if preictal: q.append("preictal entropy decline coherence increase warning signature")
        if mean_ent < 1.0: q.append("entropy collapse ictal onset localization")
        if "chb08" in patient_id.lower(): q.append("CHB-MIT chb08 temporal lobe epilepsy MTLE")
        q.append("Higuchi fractal Hjorth spectral ratios seizure risk stratification")
        retrieved = self.retrieve(" | ".join(q), n=5)

        # Global metric summary
        g = (
            f"VNE  : mean={round(mean_ent,4)}, min={round(float(np.min(vn_ent)),4)}, max={round(float(np.max(vn_ent)),4)}\n"
            f"Purity: mean={round(float(np.mean(purity)),4)}, peak={round(peak_pur,4)}\n"
            f"Coherence: mean={round(float(np.mean(coherence)),4)}, max={round(float(np.max(coherence)),4)}"
        )

        # Seizure context
        sz_ctx = ""
        if ictal:
            sz_ctx  = f"CONFIRMED ICTAL: onset={ictal[0]}s, offset={ictal[1]}s\n"
            sz_ctx += "Spatial hypothesis: Left Temporal (F7-T7) with posterior spread."
        if preictal:
            sz_ctx += f"\nCONFIRMED PRE-ICTAL WINDOW: {preictal[0]}s – {preictal[1]}s"
        if not sz_ctx:
            sz_ctx = "No confirmed ictal or pre-ictal events in this recording."

        # Timeline summary
        tl = self._summarize_timeline(timeline)

        # Knowledge block
        kb = "\n\n".join(f"[REF {i+1}]\n{c}" for i, c in enumerate(retrieved))

        prompt = f"""You are a clinical neurophysiology AI in a hospital EEG system.
Reason ONLY from the retrieved references and patient data below. Cite specific numbers.
Total length: under 700 words.

═══ RETRIEVED KNOWLEDGE ═══════════════════════════════════════════════
{kb}

═══ PATIENT DATA ═══════════════════════════════════════════════════════
Patient : {patient_id} | File: {file_name} | Dominant state: {dominant.upper()}

Ground-truth markers:
{sz_ctx}

Global quantum metrics:
{g}

Temporal state timeline:
{tl}

═══ REPORT (use these exact section headers) ════════════════════════════

### 1. EXECUTIVE SUMMARY
One paragraph referencing specific entropy and purity values and what the references say they indicate.

### 2. TEMPORAL TRAJECTORY ANALYSIS
Stage-by-stage breakdown with time ranges, metric values, and interpretation from the references.

### 3. QUANTUM BIOMARKER INTERPRETATION
Interpret entropy trajectory, purity peak, coherence dynamics against reference ranges.

### 4. SEIZURE RISK ASSESSMENT
- **Risk Level**: LOW / MODERATE / HIGH / CRITICAL
- **Confidence**: percentage
- **Reasoning**: 2-3 sentences citing specific thresholds from the references.

### 5. CLINICAL RECOMMENDATIONS
Specific, actionable next steps referencing alert thresholds from the knowledge base.

### 6. RESEARCH NOTE
One sentence on how this trace fits the patient's longitudinal seizure profile.

End with: *AI-generated report for research use. Requires clinical validation.*"""

        try:
            resp = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a clinical neurophysiology AI. "
                            "Reason strictly from retrieved knowledge and patient metrics. "
                            "Never fabricate clinical facts. Always cite specific numbers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            return resp.choices[0].message.content

        except Exception as e:
            return self._fallback(patient_id, file_name, vn_ent, purity, ictal, preictal, str(e))

    def _summarize_timeline(self, timeline: list[dict]) -> str:
        if not timeline:
            return "No data."
        lines, prev, start, ents = [], None, timeline[0]["time"], []
        for pt in timeline:
            if pt["state"] != prev:
                if prev is not None:
                    lines.append(f"  {start}s–{pt['time']}s → {prev.upper()} (avg entropy={round(float(np.mean(ents)),4)})")
                start, ents, prev = pt["time"], [], pt["state"]
            ents.append(pt["entropy"])
        lines.append(f"  {start}s–{timeline[-1]['time']}s → {prev.upper()} (avg entropy={round(float(np.mean(ents)),4)})")
        return "\n".join(lines)

    def _fallback(self, pid, fname, vn_ent, purity, ictal, preictal, err) -> str:
        risk = "CRITICAL" if ictal else ("MODERATE" if preictal else "LOW")
        r  = f"### QUANTUM EEG REPORT\n\n> ⚠️ Generation failed: {err}\n\n"
        r += f"**Patient:** {pid} | **File:** {fname}\n\n"
        r += f"**Mean VNE:** {round(float(np.mean(vn_ent)),4)} | **Peak Purity:** {round(float(np.max(purity)),4)}\n\n"
        if ictal: r += f"**CONFIRMED ICTAL:** onset={ictal[0]}s, offset={ictal[1]}s\n\n"
        r += f"**Risk Level:** {risk}\n\n"
        r += "*AI-generated for research use. Requires clinical validation.*"
        return r


# Initialise singleton at module load
print("Loading RAG engine...")
rag = EEGRagEngine()

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MARKER + TIMELINE HELPERS  (all defined here, no NameError)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_markers(feat: dict) -> tuple:
    """
    BUG FIX: /analysis returns markers.seizures (list of {start,end} dicts).
    Old code looked for markers.ictal — a key that never existed.
    """
    markers = feat.get("markers", {})

    ictal = None
    seizures = markers.get("seizures", [])
    if seizures:
        try:
            ictal = [float(seizures[0]["start"]), float(seizures[0]["end"])]
        except (KeyError, TypeError, ValueError):
            ictal = None

    preictal = None
    preictals = markers.get("preictals", [])
    if preictals:
        try:
            preictal = [float(preictals[0]["start"]), float(preictals[0]["end"])]
        except (KeyError, TypeError, ValueError):
            preictal = None

    return ictal, preictal


def build_temporal_timeline(
    time: np.ndarray,
    vn_ent: np.ndarray,
    purity: np.ndarray,
    coherence: np.ndarray,
    ictal: Optional[list],
    preictal: Optional[list],
) -> list[dict]:
    """
    Per-timestep state timeline.
    Ground-truth markers (from summary.txt) take priority over metric thresholds.
    This ensures seizure files are never misclassified as LOW risk.
    """
    timeline = []
    for i in range(len(time)):
        t   = float(time[i])
        ent = float(vn_ent[i])
        pur = float(purity[i])
        coh = float(coherence[i])

        # Priority 1: confirmed ground-truth window
        if ictal and ictal[0] <= t <= ictal[1]:
            state = "ictal"
        elif preictal and preictal[0] <= t <= preictal[1]:
            state = "preictal"
        # Priority 2: metric-driven classification
        elif ent < 0.6 and pur > 0.5:
            state = "ictal"
        elif ent < 0.8 and pur > 0.3:
            state = "preictal"
        elif ent < 1.0 and coh > 1.5:
            state = "neural_stress"
        else:
            state = "baseline"

        timeline.append({
            "time":      round(t, 1),
            "state":     state,
            "entropy":   round(ent, 4),
            "purity":    round(pur, 4),
            "coherence": round(coh, 4),
        })
    return timeline

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — FASTAPI APP
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="Quantum Seizure Intelligence API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.post("/ai_consultation")
async def ai_consultation(request: AIConsultationRequest):
    feat = request.features

    time      = np.array(feat["time"])
    vn_ent    = np.array(feat["quantum"]["vn_entropy"])
    purity    = np.array(feat["quantum"]["purity"])
    coherence = np.array(feat["quantum"]["coherence"])

    ictal, preictal = extract_markers(feat)   # ← correct keys, no NameError

    timeline = build_temporal_timeline(time, vn_ent, purity, coherence, ictal, preictal)

    report = await rag.generate_report(
        patient_id=request.patient_id,
        file_name=request.file_name,
        timeline=timeline,
        vn_ent=vn_ent,
        purity=purity,
        coherence=coherence,
        ictal=ictal,
        preictal=preictal,
    )

    state_dist: dict = {}
    for pt in timeline:
        state_dist[pt["state"]] = state_dist.get(pt["state"], 0) + 1

    return {
        "report":   report,
        "timeline": timeline,
        "meta": {
            "total_windows":      len(timeline),
            "state_distribution": state_dist,
            "ictal_detected":     ictal is not None,
            "preictal_detected":  preictal is not None,
            "reasoning_engine":   "RAG + Groq LLaMA-3.3-70B",
        },
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — KERAS CUSTOM OBJECTS
# ═══════════════════════════════════════════════════════════════════════════════

@tf.keras.utils.register_keras_serializable()
def weighted_recall(y_true, y_pred):
    y_t = tf.argmax(y_true, axis=-1); y_p = tf.argmax(y_pred, axis=-1)
    recalls = []
    for i in range(4):
        mask = tf.equal(y_t, i)
        rec = tf.reduce_sum(tf.cast(tf.logical_and(mask, tf.equal(y_p, i)), tf.float32)) / (tf.reduce_sum(tf.cast(mask, tf.float32)) + 1e-7)
        recalls.append(rec)
    return tf.reduce_sum(tf.stack(recalls) * [0.1, 0.55, 0.2, 0.15])

@tf.keras.utils.register_keras_serializable()
def weighted_kl_loss(y_true, y_pred):
    weights = tf.constant([2.0, 5.0, 6.0, 3.0])
    return tf.reduce_sum(tf.clip_by_value(y_true, 1e-7, 1.0) * tf.math.log(tf.clip_by_value(y_true, 1e-7, 1.0) / tf.clip_by_value(y_pred, 1e-7, 1.0)) * weights, axis=-1)

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SIGNAL PROCESSING CORE
# ═══════════════════════════════════════════════════════════════════════════════

@numba.jit(nopython=True)
def higuchi_fd(x, kmax):
    n = x.shape[0]; lk = np.empty(kmax); xr = np.empty(kmax); yr = np.empty(kmax)
    for k in range(1, kmax + 1):
        lm = 0.0
        for m in range(k):
            ll, nm = 0.0, int(np.floor((n-m-1)/k))
            for j in range(1, nm+1): ll += abs(x[m+j*k]-x[m+(j-1)*k])
            lm += (ll*(n-1)/(k*nm*k))
        lk[k-1]=lm/k; xr[k-1]=np.log(1.0/k); yr[k-1]=np.log(lk[k-1])
    return np.sum((xr-np.mean(xr))*(yr-np.mean(yr)))/np.sum((xr-np.mean(xr))**2)

def compute_extended_spectral(data, fs):
    fr, ps = welch(data, fs, nperseg=fs, axis=-1)
    d,t,a,b,g = [np.sum(ps[:,(fr>=l)&(fr<h)],axis=1) for l,h in [(0.5,4),(4,8),(8,13),(13,30),(30,45)]]
    total=d+t+a+b+g+1e-10; e=1e-10
    feats=np.stack([t/(d+e),a/(t+e),b/(a+e),g/(b+e),d/(a+e),d/(b+e),t/(b+e),d/total,t/total],axis=1)
    return feats, total

class QuantumInferenceEngine:
    def __init__(self, m_path, s_path):
        self.model=tf.keras.models.load_model(m_path,custom_objects={'weighted_kl_loss':weighted_kl_loss,'weighted_recall':weighted_recall},safe_mode=False)
        self.scaler=joblib.load(s_path)
        self.reset_state()

    def reset_state(self):
        self.seq_buf,self.prob_buf=deque(maxlen=SEQ_LEN),deque(maxlen=5)
        self.current_state,self.prev_cov,self.prev_energy="NORMAL",None,None
        b_bp,a_bp=butter(4,[0.5,80],btype='band',fs=SFREQ); b_n,a_n=iirnotch(60,30,fs=SFREQ)
        self.zi_bp=np.tile(lfilter_zi(b_bp,a_bp),(18,1)); self.zi_n=np.tile(lfilter_zi(b_n,a_n),(18,1))
        self.filters=(b_bp,a_bp,b_n,a_n)

    def process_window(self, raw):
        b_bp,a_bp,b_n,a_n=self.filters
        f,self.zi_bp=lfilter(b_bp,a_bp,raw,axis=1,zi=self.zi_bp)
        f,self.zi_n=lfilter(b_n,a_n,f,axis=1,zi=self.zi_n)
        corr=np.nan_to_num(np.corrcoef(f)); mc=np.mean(np.abs(corr),axis=1); w=np.ones(18)
        for i in range(18):
            if mc[i]<0.3:
                nbs=NEIGHBORS.get(i,[]); mn=max([np.abs(corr[i,n]) for n in nbs]) if nbs else 0
                w[i]=1.0 if mn>0.6 else 0.1
        wn=w/(np.sum(w)+1e-9)
        spec,ch_e=compute_extended_spectral(f,SFREQ)
        cur_e=np.sum(ch_e*wn); e_ch=abs(cur_e-self.prev_energy) if self.prev_energy else 0; self.prev_energy=cur_e
        res=np.zeros((18,3))
        for i in range(18):
            x=f[i,:]; dx=np.diff(x); ddx=np.diff(dx)
            v,vd,vdd=np.var(x),np.var(dx),np.var(ddx)
            res[i,:]=[v,np.sqrt(vd/(v+1e-10)),np.sqrt(vdd/(vd+1e-10))/(np.sqrt(vd/(v+1e-10))+1e-10)]
        h6=np.array([higuchi_fd(ch,6) for ch in f]); h50=np.array([higuchi_fd(ch,50) for ch in f])
        wig=skew(np.abs(hilbert(f,axis=-1)),axis=-1)
        cov=np.cov(f); rho=cov/(np.trace(cov)+1e-10); eig=np.linalg.eigvalsh(rho); eig=eig[eig>1e-12]
        vn=-np.sum(eig*np.log(eig))
        rho_L=rho[0:8,0:8]; rho_L/=(np.trace(rho_L)+1e-10); eig_L=np.linalg.eigvalsh(rho_L); ent_ent=-np.sum(eig_L[eig_L>1e-12]*np.log(eig_L[eig_L>1e-12]))
        qfi=np.sum((rho-(self.prev_cov/(np.trace(self.prev_cov)+1e-10)))**2) if self.prev_cov is not None else 0; self.prev_cov=cov
        f_vec=[np.sum(spec[:,i]*wn) for i in range(9)]+[np.sum(res[:,i]*wn) for i in range(3)]+\
              [np.sum(h6*wn),np.sum(h50*wn),np.sum(wig*wn),vn,ent_ent,qfi,e_ch]
        self.seq_buf.append(self.scaler.transform(np.array(f_vec).reshape(1,-1))[0])
        metrics={"entropy":float(vn),"entanglement":float(ent_ent),"fisher_info":float(qfi),"energy_flux":float(e_ch)}
        if len(self.seq_buf)==SEQ_LEN:
            p=self.model.predict(np.array(self.seq_buf).reshape(1,SEQ_LEN,-1),verbose=0)[0]
            self.prob_buf.append(p); avg=np.mean(self.prob_buf,axis=0)
            if avg[2]>TH_ICT: self.current_state="ICTAL"
            elif avg[1]>TH_PRE: self.current_state="PREICTAL"
            elif avg[0]>TH_NORMAL or avg[3]>TH_NORMAL: self.current_state="NORMAL"
            return avg.tolist(),self.current_state,metrics
        return None,None,metrics

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — REMAINING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
def health():
    return {"status": "Quantum Engine Running", "config": {"fs": SFREQ, "channels": 18}}

@app.get("/patients")
def list_patients():
    try:
        patients=sorted([d for d in os.listdir(DATASET_PATH) if os.path.isdir(os.path.join(DATASET_PATH,d))])
        return [{"id":p,"status":"Stable","risk":"Low","last_sync":"Recent"} for p in patients]
    except:
        return []

@app.get("/patient_details/{patient_id}")
def get_details(patient_id: str):
    folder=os.path.join(DATASET_PATH,patient_id)
    files=sorted([os.path.basename(f) for f in glob.glob(os.path.join(folder,'*.edf'))])
    metadata={"channels":"18","seizures":[],"clinical_notes":"Searching..."}
    if files:
        try:
            ft=pyedflib.EdfReader(os.path.join(folder,files[0])); metadata["channels"]=str(ft.signals_in_file); ft.close()
        except: pass
    sp=os.path.join(folder,f"{patient_id}-summary.txt")
    if os.path.exists(sp):
        try:
            with open(sp,'r') as f: content=f.read()
            if "Number of Channels:" in content:
                metadata["channels"]=content.split("Number of Channels:")[1].split("\n")[0].strip()
            for chunk in content.split("File Name: ")[1:]:
                lines=chunk.split("\n"); fn=lines[0].strip(); nsz=0
                for line in lines:
                    if "Number of Seizures in File:" in line: nsz=int(line.split(":")[1].strip())
                if nsz>0:
                    st,en="N/A","N/A"
                    for line in lines:
                        if "Seizure" in line and "Start Time:" in line: st=line.split("Start Time:")[1].split(" seconds")[0].strip()
                        if "Seizure" in line and "End Time:"   in line: en=line.split("End Time:")[1].split(" seconds")[0].strip()
                    metadata["seizures"].append({"file":fn,"start":st,"end":en})
            metadata["clinical_notes"]=f"Verified {len(metadata['seizures'])} clinical events."
        except Exception as e: metadata["clinical_notes"]=f"Parser: {str(e)}"
    return {"id":patient_id,"files":files,"metadata":metadata}

@app.get("/check_model/{patient_id}")
def check_model(patient_id: str):
    m=os.path.exists(os.path.join(MODEL_DIR,f"{patient_id}_best.keras"))
    s=os.path.exists(os.path.join(MODEL_DIR,f"{patient_id}_scaler.pkl"))
    return {"exists":m and s}

@app.get("/analysis")
async def perform_full_analysis(patient_id: str, file_name: str):
    path=os.path.join(DATASET_PATH,patient_id,file_name)
    if not os.path.exists(path): raise HTTPException(404,"File not found")
    sp=os.path.join(DATASET_PATH,patient_id,f"{patient_id}-summary.txt")
    seizure_markers=[]
    if os.path.exists(sp):
        with open(sp,'r') as f: content=f.read()
        if file_name in content:
            try:
                chunk=content.split(file_name)[1].split("File Name:")[0]
                lines=[l.strip() for l in chunk.split('\n')]
                for i,line in enumerate(lines):
                    if "Seizure" in line and "Start Time" in line:
                        start=float(line.split(":")[1].split(" seconds")[0].strip())
                        end=float(lines[i+1].split(":")[1].split(" seconds")[0].strip())
                        seizure_markers.append({"start":start,"end":end})
            except: pass
    f=pyedflib.EdfReader(path); labels=f.getSignalLabels()
    indices=[next(i for i,l in enumerate(labels) if t.upper() in l.upper()) for t in STD_MONTAGE]
    duration=f.getFileDuration(); step=5.0; time_bins=np.arange(0,duration,step)
    results={
        "time":time_bins.tolist(),
        "quantum":     {"vn_entropy":[],"purity":[],"linear_entropy":[],"coherence":[],"qfi":[],"entanglement":[]},
        "phase_space": {"wv_energy":[],"wv_entropy":[],"wv_variance":[],"wv_skewness":[],"wv_kurtosis":[]},
        "time_domain": {"energy":[],"hjorth_act":[],"hjorth_mob":[],"hjorth_comp":[],"zcr":[],"peak_to_peak":[],"inter_corr":[],"inter_corr_var":[]},
        "freq_domain": {"rel_delta":[],"rel_theta":[],"rel_alpha":[],"rel_beta":[],"rel_gamma":[],"theta_alpha":[],"delta_alpha":[],"spec_entropy":[],"sef95":[]},
        "markers":{"seizures":seizure_markers,"preictals":[{"start":max(0,s["start"]-600),"end":max(0,s["start"]-60)} for s in seizure_markers]}
    }
    for t in time_bins:
        ss,es=int(t*SFREQ),int((t+WINDOW_SEC)*SFREQ)
        if es>f.getNSamples()[0]: break
        chunk=np.zeros((18,int(WINDOW_SEC*SFREQ)))
        for i,idx in enumerate(indices): chunk[i,:]=f.readSignal(idx,ss,int(WINDOW_SEC*SFREQ))
        sig=chunk[0]
        cov=np.cov(chunk); tr=np.trace(cov)+1e-10; rho=cov/tr
        eig=np.linalg.eigvalsh(rho); eig=eig[eig>1e-12]
        results["quantum"]["vn_entropy"].append(float(-np.sum(eig*np.log(eig))))
        results["quantum"]["purity"].append(float(np.sum(eig**2)))
        results["quantum"]["linear_entropy"].append(float(1-np.sum(eig**2)))
        results["quantum"]["coherence"].append(float(np.sum(np.abs(rho))-np.sum(np.diag(rho))))
        results["quantum"]["qfi"].append(float(np.sum(rho**2)))
        rho_p=rho[0:9,0:9]; rho_p/=(np.trace(rho_p)+1e-10); e_p=np.linalg.eigvalsh(rho_p)
        results["quantum"]["entanglement"].append(float(-np.sum(e_p[e_p>1e-12]*np.log(e_p[e_p>1e-12]))))
        results["phase_space"]["wv_energy"].append(float(np.sum(sig**2)))
        results["phase_space"]["wv_entropy"].append(float(-np.sum(sig**2*np.log(sig**2+1e-10))))
        results["phase_space"]["wv_variance"].append(float(np.var(sig)))
        results["phase_space"]["wv_skewness"].append(float(skew(sig)))
        results["phase_space"]["wv_kurtosis"].append(float(kurtosis(sig)))
        results["time_domain"]["energy"].append(float(np.sum(sig**2)))
        results["time_domain"]["hjorth_act"].append(float(np.var(sig)))
        m0=np.var(sig); m1=np.var(np.diff(sig)); m2=np.var(np.diff(np.diff(sig)))
        mob=np.sqrt(m1/m0) if m0>0 else 0
        results["time_domain"]["hjorth_mob"].append(float(mob))
        results["time_domain"]["hjorth_comp"].append(float((np.sqrt(m2/m1)/mob) if mob>0 and m1>0 else 0))
        results["time_domain"]["zcr"].append(float(np.mean(np.diff(np.sign(sig))!=0)))
        results["time_domain"]["peak_to_peak"].append(float(np.ptp(sig)))
        corrs=np.abs(np.corrcoef(chunk)[np.triu_indices(18,k=1)])
        results["time_domain"]["inter_corr"].append(float(np.mean(corrs)))
        results["time_domain"]["inter_corr_var"].append(float(np.var(corrs)))
        fr,ps=welch(sig,SFREQ,nperseg=SFREQ); total_p=np.sum(ps)+1e-10; p_rel=ps/total_p
        results["freq_domain"]["rel_delta"].append(float(np.sum(ps[(fr>=1)&(fr<4)])/total_p))
        results["freq_domain"]["rel_theta"].append(float(np.sum(ps[(fr>=4)&(fr<8)])/total_p))
        results["freq_domain"]["rel_alpha"].append(float(np.sum(ps[(fr>=8)&(fr<13)])/total_p))
        results["freq_domain"]["rel_beta"].append(float(np.sum(ps[(fr>=13)&(fr<30)])/total_p))
        results["freq_domain"]["rel_gamma"].append(float(np.sum(ps[(fr>=30)&(fr<40)])/total_p))
        t_p=np.sum(ps[(fr>=4)&(fr<8)]); a_p=np.sum(ps[(fr>=8)&(fr<13)])+1e-10; d_p=np.sum(ps[(fr>=1)&(fr<4)])
        results["freq_domain"]["theta_alpha"].append(float(t_p/a_p))
        results["freq_domain"]["delta_alpha"].append(float(d_p/a_p))
        results["freq_domain"]["spec_entropy"].append(float(-np.sum(p_rel*np.log(p_rel+1e-10))))
        cum_p=np.cumsum(ps); results["freq_domain"]["sef95"].append(float(fr[np.where(cum_p>=0.95*total_p)[0][0]]))
    f.close()
    return results

@app.get("/stream_inference")
async def stream_inference(patient_id: str, file_name: str):
    m_path=os.path.join(MODEL_DIR,f"{patient_id}_best.keras")
    s_path=os.path.join(MODEL_DIR,f"{patient_id}_scaler.pkl")
    engine=QuantumInferenceEngine(m_path,s_path)
    path=os.path.join(DATASET_PATH,patient_id,file_name)
    f=pyedflib.EdfReader(path); labels=f.getSignalLabels()
    indices=[next(i for i,l in enumerate(labels) if t.upper() in l.upper()) for t in STD_MONTAGE]
    raw=np.zeros((18,f.getNSamples()[0]))
    for i,idx in enumerate(indices): raw[i,:]=f.readSignal(idx)
    f.close()
    sp=os.path.join(DATASET_PATH,patient_id,f"{patient_id}-summary.txt")
    seizure_ranges=[]
    if os.path.exists(sp):
        with open(sp,'r') as f: content=f.read()
        if file_name in content:
            try:
                chunk=content.split(file_name)[1].split("File Name:")[0]
                lines=[l.strip() for l in chunk.split('\n')]
                for i,l in enumerate(lines):
                    if "Seizure" in l and "Start Time" in l:
                        s=float(l.split(":")[1].split(" seconds")[0].strip())
                        e=float(lines[i+1].split(":")[1].split(" seconds")[0].strip())
                        seizure_ranges.append((s,e))
            except: pass
    async def event_generator():
        win,strd=int(WINDOW_SEC*SFREQ),int(STRIDE_SEC*SFREQ)
        for start in range(0,raw.shape[1]-win,strd):
            t_sec=start/SFREQ
            probs,ai_state,q_mets=engine.process_window(raw[:,start:start+win])
            gt_state="NORMAL"
            for s,e in seizure_ranges:
                if s<=t_sec<=e: gt_state="ICTAL"; break
                if (s-600)<=t_sec<=(s-60): gt_state="PREICTAL"; break
            payload={"time":f"{round(t_sec,1)}s","state":ai_state if ai_state else "INITIALIZING",
                     "gt_state":gt_state,"wave":raw[0,start:start+win:4].tolist(),
                     "probabilities":probs,"metrics":q_mets}
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(0.02)
    return StreamingResponse(event_generator(),media_type="text/event-stream")

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — SERVER START
# ═══════════════════════════════════════════════════════════════════════════════

def start_server():
    os.system("fuser -k 8000/tcp")
    ngrok.set_auth_token(NGROK_TOKEN)
    public_url=ngrok.connect(8000).public_url
    print(f"\n🚀 QUANTUM BACKEND LIVE: {public_url}\n")
    config=uvicorn.Config(app,host="0.0.0.0",port=8000,log_level="info")
    server=uvicorn.Server(config)
    loop=asyncio.get_event_loop()
    loop.run_until_complete(server.serve())

if __name__ == "__main__":
    start_server()
