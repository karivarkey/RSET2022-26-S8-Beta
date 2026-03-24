import streamlit as st
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import pandas as pd
import h5py
import joblib
import time
from scipy import signal
from scipy.stats import skew, kurtosis
import plotly.graph_objects as go
import streamlit.components.v1 as components
import base64

# --- CONFIGURATION ---
MODEL_PATH = r"D:\seismic\seismic_vqvae_v2.pth"
STAGE1_PATH = r"D:\seismic\stage1_gatekeeper.pkl"
STAGE2_PATH = r"D:\seismic\stage2_hazard.pkl"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CHANNELS_TO_USE = [100, 256, 400]
FS = 20.0
WINDOW_SECONDS = 30
WINDOW_SIZE = int(WINDOW_SECONDS * FS)

# --- INJECT CUSTOM CSS FOR ANIMATIONS & STYLING ---
st.set_page_config(page_title="SEISMICO", page_icon="🌍", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* Pulsing Animation for Critical Alerts */
    @keyframes pulse-red {
        0% { box-shadow: 0 0 0 0 rgba(255, 50, 50, 0.7); transform: scale(1); }
        50% { box-shadow: 0 0 0 20px rgba(255, 50, 50, 0); transform: scale(1.02); }
        100% { box-shadow: 0 0 0 0 rgba(255, 50, 50, 0); transform: scale(1); }
    }
    
    .critical-banner {
        animation: pulse-red 1.5s infinite;
        background: linear-gradient(135deg, #ff0000, #990000);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-family: 'Courier New', Courier, monospace;
        font-size: 24px;
        font-weight: 900;
        letter-spacing: 2px;
        margin-bottom: 20px;
        text-transform: uppercase;
        box-shadow: 0 10px 20px rgba(255,0,0,0.3);
    }

    .safe-banner {
        background: linear-gradient(135deg, #00b09b, #96c93d);
        color: white;
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 20px;
        box-shadow: 0 5px 15px rgba(0,255,0,0.2);
    }
    
    /* Cool gradient text for headers */
    .gradient-text {
        background: -webkit-linear-gradient(45deg, #00C9FF, #92FE9D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900;
        font-size: 3em;
        margin-bottom: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- VQ-VAE ENCODER ARCHITECTURE ---
class SeismicEncoder(nn.Module):
    def __init__(self, num_hiddens=128, num_embeddings=128, embedding_dim=64):
        super(SeismicEncoder, self).__init__()
        self._encoder = nn.Sequential(
            nn.Conv2d(3, num_hiddens // 2, kernel_size=4, stride=2, padding=1),
            nn.ReLU(True),
            nn.Conv2d(num_hiddens // 2, num_hiddens, kernel_size=4, stride=2, padding=1),
            nn.ReLU(True),
            nn.Conv2d(num_hiddens, num_hiddens, kernel_size=4, stride=2, padding=1),
            nn.ReLU(True),
            nn.Conv2d(num_hiddens, embedding_dim, kernel_size=3, stride=1, padding=1)
        )
        self._pre_vq_conv = nn.Conv2d(embedding_dim, embedding_dim, kernel_size=1, stride=1)

    def forward(self, x):
        return self._pre_vq_conv(self._encoder(x))

# --- FEATURE EXTRACTION HELPERS ---
def compute_3ch_spectrogram(waveform_chunk, fs):
    specs = []
    # Note: waveform_chunk here is already isolated to the 3 chosen channels
    for ch_idx in range(3):
        f, t, Sxx = signal.spectrogram(waveform_chunk[:, ch_idx], fs, nperseg=64, noverlap=32)
        Sxx = np.log1p(Sxx)
        min_val, max_val = Sxx.min(), Sxx.max()
        if max_val - min_val > 0:
            Sxx = (Sxx - min_val) / (max_val - min_val)
        else:
            Sxx = np.zeros_like(Sxx)
        specs.append(Sxx)
    return np.array(specs)

def compute_classical_features(waveform_chunk, fs):
    """The 24-feature raw physics engine"""
    features = []
    for ch_idx in range(waveform_chunk.shape[1]):
        trace = waveform_chunk[:, ch_idx]
        
        max_amp = np.max(np.abs(trace))             
        variance = np.var(trace)                    
        energy = np.sum(trace ** 2)                 
        zcr = np.sum(np.diff(np.sign(trace)) != 0)  
        mav = np.mean(np.abs(trace))                
        skewness = skew(trace)
        kurt = kurtosis(trace)
        
        freqs = np.fft.fftfreq(len(trace), d=1/fs)
        fft_mags = np.abs(np.fft.fft(trace))
        peak_freq = np.abs(freqs[np.argmax(fft_mags[1:]) + 1]) 
        
        features.extend([max_amp, variance, energy, zcr, mav, skewness, kurt, peak_freq])
        
    return np.array(features)

# --- CACHE MODELS ---
@st.cache_resource(show_spinner=False)
def load_models():
    vqvae = SeismicEncoder().to(DEVICE)
    vqvae.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE), strict=False)
    vqvae.eval()
    return vqvae, joblib.load(STAGE1_PATH), joblib.load(STAGE2_PATH)

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>⚡ System Diagnostics</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.info("🧠 **Core Model:** VQ-VAE + Hybrid RF/XGB Ensembles")
    st.success("🟢 Spectrogram Engine: Online")
    st.success("🟢 Physics Engine: Online")
    st.success("🟢 Stage 1 Gatekeeper: Online")
    st.success("🟢 Stage 2 Hazard ID: Online")
    st.markdown("---")
    st.caption("Developed for Advanced Seismic Monitoring")

# ==========================================
# MAIN DASHBOARD
# ==========================================
st.markdown("<h1 class='gradient-text'>SEISMICO AI</h1>", unsafe_allow_html=True)
st.markdown("### Real-time Distributed Acoustic Sensing & Threat Detection")

vqvae, gatekeeper, hazard_id = load_models()

uploaded_file = st.file_uploader("DROP RAW .H5 STREAM HERE", type=['h5'])

if uploaded_file is not None:
    st.toast('Data link established. Initializing scan...', icon='📡')
    
    with h5py.File(uploaded_file, 'r') as f:
        full_trace = f['Traces'][:]
        num_samples = full_trace.shape[0]
        
    num_chunks = num_samples // WINDOW_SIZE
    
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    results = []
    landslide_count = rockfall_count = 0
    
    # Live Inference Loop
    for i in range(num_chunks):
        status_text.markdown(f"**Scanning Time Window {i+1}/{num_chunks}...**")
        start_idx = i * WINDOW_SIZE
        
        # Isolate exactly the 3 channels we trained on
        chunk = full_trace[start_idx : start_idx + WINDOW_SIZE, CHANNELS_TO_USE]
        
        # 1. Deep Learning Features
        spec = compute_3ch_spectrogram(chunk, FS)
        tensor_x = F.pad(torch.from_numpy(spec).float().unsqueeze(0).to(DEVICE), (0, 7, 0, 7), "constant", 0)
        
        with torch.no_grad():
            deep_features = vqvae(tensor_x).view(-1).cpu().numpy() # 960 features
            
        # 2. Classical Physics Features
        physics_features = compute_classical_features(chunk, FS) # 24 features
        
        # 3. Hybrid Fusion (984 features)
        hybrid_features = np.concatenate([deep_features, physics_features]).reshape(1, -1)
        
        # 4. Predictions & Confidence Scoring
        gate_probs = gatekeeper.predict_proba(hybrid_features)[0]
        gate_pred = np.argmax(gate_probs)
        
        time_label = f"{i*30}s - {(i+1)*30}s"
        
        if gate_pred == 0:
            confidence = round(gate_probs[0] * 100, 1)
            results.append({"Time": time_label, "Status": "Safe", "Event": "Ambient/Anthro", "Confidence (%)": confidence, "color": "green"})
        else:
            hazard_probs = hazard_id.predict_proba(hybrid_features)[0]
            hazard_pred = np.argmax(hazard_probs)
            confidence = round(np.max(hazard_probs) * 100, 1)
            
            if hazard_pred == 0:
                results.append({"Time": time_label, "Status": "Warning", "Event": "Rockfall", "Confidence (%)": confidence, "color": "orange"})
                rockfall_count += 1
            else:
                results.append({"Time": time_label, "Status": "CRITICAL", "Event": "Landslide", "Confidence (%)": confidence, "color": "red"})
                landslide_count += 1
                
        progress_bar.progress((i + 1) / num_chunks)
        time.sleep(0.05) # Cinematic delay

    status_text.empty()
    progress_bar.empty()

    # Dynamic Banners & Confetti/Sirens
    if landslide_count > 0:
        st.markdown("<div class='critical-banner'>🚨 CRITICAL ALERT: LANDSLIDE DETECTED 🚨</div>", unsafe_allow_html=True)
        st.toast('EVACUATION WARNING TRIGGERED', icon='🚨')
        
        # 🔊 INJECT HIDDEN AUTOPLAY ALARM 🔊
        try:
            alarm_path = r"D:\seismic\alarm.mp3"
            with open(alarm_path, "rb") as f:
                b64_audio = base64.b64encode(f.read()).decode()
            
            kill_switch_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                .kill-btn {{
                    background-color: #ff0000; color: white; padding: 15px 32px; text-align: center;
                    font-family: 'Courier New', Courier, monospace; font-size: 20px; font-weight: 900;
                    border-radius: 8px; border: 2px solid white; cursor: pointer; width: 100%;
                    box-shadow: 0 4px 15px 0 rgba(255,0,0,0.5); text-transform: uppercase; transition: 0.3s;
                }}
                .kill-btn.silenced {{
                    background-color: #4CAF50; border: 2px solid #4CAF50; box-shadow: none; cursor: default;
                }}
                body {{ margin: 0; padding: 0; background-color: transparent; }}
            </style>
            </head>
            <body>
                <audio id="siren" autoplay loop><source src="data:audio/mpeg;base64,{b64_audio}" type="audio/mpeg"></audio>
                <button id="stopBtn" class="kill-btn" onclick="silence()">🛑 Silence Alarm & Acknowledge Threat</button>
                <script>
                    function silence() {{
                        var audio = document.getElementById('siren'); audio.pause();
                        var btn = document.getElementById('stopBtn');
                        btn.innerHTML = '🔇 ALARM ACKNOWLEDGED'; btn.className = 'kill-btn silenced';
                    }}
                </script>
            </body>
            </html>
            """
            components.html(kill_switch_html, height=80)
        except Exception as e:
            st.error("Audio alarm missing. Ensure 'alarm.mp3' is in D:\seismic\\")
            
    elif rockfall_count > 0:
        st.warning(f"⚠️ **CAUTION:** {rockfall_count} Rockfall(s) detected in the area.")
    else:
        st.markdown("<div class='safe-banner'>✅ ALL CLEAR: NO HAZARDS DETECTED IN THIS STREAM</div>", unsafe_allow_html=True)
        st.balloons() 

    st.markdown("---")

    # ROW 1: METRICS
    col1, col2, col3 = st.columns(3)
    col1.metric(label="Total Windows Scanned", value=f"{num_chunks}")
    col2.metric(label="Rockfalls Detected", value=rockfall_count, delta="Caution", delta_color="off")
    col3.metric(label="Landslides Detected", value=landslide_count, delta="CRITICAL" if landslide_count > 0 else "Clear", delta_color="inverse")

    # ROW 2: INTERACTIVE SEISMIC GRAPH
    st.markdown("### 📈 Live Seismic Trace Overlay")
    time_axis = np.linspace(0, num_samples/FS, num_samples)
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(x=time_axis, y=full_trace[:, CHANNELS_TO_USE[0]], 
                             mode='lines', line=dict(color='#00FFFF', width=0.8), name='Channel 100'))
    
    for i, res in enumerate(results):
        if res['color'] == 'red':
            fig.add_vrect(x0=i*30, x1=(i+1)*30, fillcolor="red", opacity=0.3, line_width=2, line_color="red", annotation_text="💥 LANDSLIDE", annotation_font_color="white")
        elif res['color'] == 'orange':
            fig.add_vrect(x0=i*30, x1=(i+1)*30, fillcolor="orange", opacity=0.3, line_width=1, line_dash="dash", annotation_text="⚠️ Rockfall", annotation_font_color="white")

    fig.update_layout(
        height=400, margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor='rgba(10, 10, 10, 1)', paper_bgcolor='rgba(0, 0, 0, 0)',
        xaxis=dict(showgrid=False, title="Time (Seconds)", color="white"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title="Amplitude", color="white")
    )
    st.plotly_chart(fig, use_container_width=True)

    # ROW 3: STYLED LOG & CSV EXPORT
    st.markdown("### 📋 Event Signature Log")
    df_results = pd.DataFrame(results).drop(columns=['color'])
    
    def highlight_hazards(val):
        if val == 'CRITICAL': return 'background-color: #4a0000; color: #ff4d4d; font-weight: bold; border-left: 5px solid red;'
        if val == 'Warning': return 'background-color: #4a3300; color: #ffb84d; font-weight: bold;'
        if val == 'Safe': return 'color: #00ff00;'
        return ''

    st.dataframe(df_results.style.map(highlight_hazards, subset=['Status']), use_container_width=True)
    
    # --- CSV EXPORT BUTTON ---
    csv_export = df_results.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Threat Report (CSV)",
        data=csv_export,
        file_name='seismic_threat_report.csv',
        mime='text/csv',
    )
    