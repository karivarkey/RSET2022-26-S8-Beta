import React, { useState, useEffect, useRef, useCallback, memo } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, Zap, Brain, Clock, BarChart3, FileText,
  CheckCircle2, XCircle, Shield, Users,
  LayoutDashboard, Fingerprint, Waves, Cpu, Plus, Minus, RefreshCw, ArrowLeft,
  ChevronRight, Eye
} from 'lucide-react';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import { Chart as ChartJS, registerables } from 'chart.js';
import { EventSourcePolyfill } from 'event-source-polyfill';
import annotationPlugin from 'chartjs-plugin-annotation';
import zoomPlugin from 'chartjs-plugin-zoom';
import 'hammerjs';

import video1 from './assets/videos/1. Digital Brain Diagnostics.mp4';
import video2 from './assets/videos/Neural Interface Simulation.mp4';
import video3 from './assets/videos/Microscopic Neuronal Activity.mp4';
import video4 from './assets/videos/Brain & Neural Network Overview.mp4';
import researchPaper from './assets/Report/New_Paper___MIDAS___Final_Draft copy.pdf';

ChartJS.register(...registerables, annotationPlugin, zoomPlugin);

const API_BASE = import.meta.env.VITE_API_BASE || "https://5498-34-73-122-232.ngrok-free.app";
const api = axios.create({
  baseURL: API_BASE,
  headers: { "ngrok-skip-browser-warning": "true" }
});

// ── Design tokens ──────────────────────────────────────────────────────────────
const STATE_COLORS = {
  IDLE: { text: '#94A3B8', bg: 'rgba(148,163,184,0.07)', border: 'rgba(148,163,184,0.12)' },
  INITIALIZING: { text: '#60A5FA', bg: 'rgba(96,165,250,0.07)', border: 'rgba(96,165,250,0.18)' },
  NORMAL: { text: '#34D399', bg: 'rgba(52,211,153,0.07)', border: 'rgba(52,211,153,0.18)' },
  PREICTAL: { text: '#FBBF24', bg: 'rgba(251,191,36,0.07)', border: 'rgba(251,191,36,0.2)' },
  ICTAL: { text: '#F87171', bg: 'rgba(248,113,113,0.08)', border: 'rgba(248,113,113,0.22)' },
  INTERICTAL: { text: '#A78BFA', bg: 'rgba(167,139,250,0.07)', border: 'rgba(167,139,250,0.18)' },
};
const getStateColors = (state) => STATE_COLORS[state] || STATE_COLORS.IDLE;

const WAVE_COLOR = {
  IDLE: '#60A5FA', INITIALIZING: '#60A5FA',
  NORMAL: '#34D399', PREICTAL: '#FBBF24',
  ICTAL: '#F87171', INTERICTAL: '#A78BFA',
};

const MONO = "'Space Mono', monospace";

// ── EEG chart options — animation:false kills jitter ─────────────────────────
const EEG_CHART_OPTIONS = {
  maintainAspectRatio: false,
  animation: false,
  responsive: true,
  scales: {
    x: { display: false },
    y: {
      grid: { color: 'rgba(255,255,255,0.03)' },
      min: -150, max: 150,
      ticks: { color: 'rgba(255,255,255,0.18)', font: { size: 10 } },
    },
  },
  plugins: {
    legend: { display: false },
    zoom: { pan: { enabled: false }, zoom: { wheel: { enabled: false }, pinch: { enabled: false } } },
  },
};

function buildAnnotations(markers, large = false) {
  if (!markers) return {};
  const out = {};
  (markers.seizures || []).forEach((s, i) => {
    out[`ictal_${i}`] = {
      type: 'box', xMin: s.start, xMax: s.end,
      backgroundColor: 'rgba(248,113,113,0.12)', borderWidth: 1, borderColor: 'rgba(248,113,113,0.3)',
      label: {
        display: true, content: large ? 'ICTAL ZONE' : 'ICTAL', position: large ? 'center' : 'start',
        font: { size: large ? 11 : 8, weight: '900' }, color: '#fff', backgroundColor: '#F87171',
        padding: large ? 6 : 2, borderRadius: large ? 6 : 2
      },
    };
  });
  (markers.preictals || []).forEach((p, i) => {
    out[`pre_${i}`] = {
      type: 'box', xMin: p.start, xMax: p.end,
      backgroundColor: 'rgba(251,191,36,0.08)', borderWidth: 1, borderColor: 'rgba(251,191,36,0.2)',
      label: {
        display: true, content: large ? 'PRE-ICTAL' : 'PRE', position: large ? 'center' : 'start',
        font: { size: large ? 11 : 8, weight: '900' }, color: '#fff', backgroundColor: '#FBBF24',
        padding: large ? 6 : 2, borderRadius: large ? 6 : 2
      },
    };
  });
  return out;
}

const makeGridOptions = (markers) => ({
  maintainAspectRatio: false,
  animation: false,
  responsive: true,
  scales: {
    x: { type: 'linear', grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.15)', font: { size: 9 } } },
    y: {
      grid: { color: 'rgba(255,255,255,0.03)' },
      ticks: { color: 'rgba(255,255,255,0.15)', font: { size: 9 }, callback: v => `${(v * 100).toFixed(0)}%` },
    },
  },
  plugins: {
    legend: { display: true, position: 'top', labels: { color: 'rgba(255,255,255,0.28)', font: { size: 9, weight: 'bold' }, boxWidth: 10, padding: 6 } },
    zoom: { pan: { enabled: false }, zoom: { wheel: { enabled: false }, pinch: { enabled: false } } },
    annotation: { annotations: buildAnnotations(markers) },
  },
});

const makeModalOptions = (markers) => ({
  maintainAspectRatio: false,
  animation: false,
  responsive: true,
  scales: {
    x: { type: 'linear', grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.3)', font: { size: 11 } } },
    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: 'rgba(255,255,255,0.3)', font: { size: 11 }, callback: v => `${(v * 100).toFixed(0)}%` } },
  },
  plugins: {
    legend: { display: true, position: 'top', labels: { color: 'rgba(255,255,255,0.4)', font: { size: 11, weight: 'bold' }, boxWidth: 14 } },
    zoom: { pan: { enabled: true, mode: 'x', speed: 2 }, zoom: { wheel: { enabled: true, speed: 0.01 }, pinch: { enabled: true }, mode: 'x' } },
    annotation: { annotations: buildAnnotations(markers, true) },
  },
});

function normalise(data) {
  if (!data || data.length === 0) return [];
  const min = Math.min(...data), max = Math.max(...data);
  if (max === min) return data.map(() => 0.5);
  return data.map(v => (v - min) / (max - min));
}

function smooth(data, windowSize = 3) {
  if (!data || data.length === 0) return [];
  const smoothed = [];
  for (let i = 0; i < data.length; i++) {
    let start = Math.max(0, i - windowSize);
    let end = Math.min(data.length - 1, i + windowSize);
    let sum = 0;
    for (let j = start; j <= end; j++) {
      sum += data[j];
    }
    smoothed.push(sum / (end - start + 1));
  }
  return smoothed;
}

function computeMeans(data, time, markers) {
  const isPreIctal = t => markers?.preictals?.some(p => t >= p.start && t <= p.end);
  const isIctal = t => markers?.seizures?.some(s => t >= s.start && t <= s.end);

  let pSum = 0, pCnt = 0, iSum = 0, iCnt = 0, nSum = 0, nCnt = 0;
  for (let i = 0; i < time.length; i++) {
    if (isIctal(time[i])) { iSum += data[i]; iCnt++; }
    else if (isPreIctal(time[i])) { pSum += data[i]; pCnt++; }
    else { nSum += data[i]; nCnt++; }
  }
  return [nCnt ? nSum / nCnt : 0, pCnt ? pSum / pCnt : 0, iCnt ? iSum / iCnt : 0];
}

const makeBarOptions = () => ({
  maintainAspectRatio: false,
  animation: false,
  responsive: true,
  scales: {
    y: { beginAtZero: true, max: 1, grid: { color: 'rgba(255,255,255,0.03)' }, ticks: { color: 'rgba(255,255,255,0.15)', font: { size: 9 }, callback: v => `${(v * 100).toFixed(0)}%` } },
    x: { grid: { display: false }, ticks: { color: 'rgba(255,255,255,0.3)', font: { size: 10, weight: 'bold' } } }
  },
  plugins: { legend: { display: true, position: 'top', labels: { color: 'rgba(255,255,255,0.28)', font: { size: 9, weight: 'bold' }, boxWidth: 10, padding: 6 } }, zoom: { pan: { enabled: false }, zoom: { wheel: { enabled: false } } } }
});

// ── Chart definitions ─────────────────────────────────────────────────────────
const CHART_DEFS = [
  {
    title: 'Quantum Density Descriptors', keys: [
      { label: 'vN Entropy', path: d => d.quantum.vn_entropy, color: '#60A5FA' },
      { label: 'Purity', path: d => d.quantum.purity, color: '#34D399' },
      { label: 'Coherence', path: d => d.quantum.coherence, color: '#FBBF24' },
      { label: 'Entanglement', path: d => d.quantum.entanglement, color: '#EC4899' },
    ]
  },
  {
    title: 'Spectral Power Dynamics', keys: [
      { label: 'Delta', path: d => d.freq_domain.rel_delta, color: '#6366F1' },
      { label: 'Theta', path: d => d.freq_domain.rel_theta, color: '#34D399' },
      { label: 'Alpha', path: d => d.freq_domain.rel_alpha, color: '#FBBF24' },
      { label: 'Beta', path: d => d.freq_domain.rel_beta, color: '#F87171' },
    ]
  },
  {
    title: 'Clinical Spectral Indices', keys: [
      { label: 'Theta/Alpha', path: d => d.freq_domain.theta_alpha, color: '#A78BFA' },
      { label: 'Delta/Alpha', path: d => d.freq_domain.delta_alpha, color: '#F87171' },
      { label: 'Spec Entropy', path: d => d.freq_domain.spec_entropy, color: '#60A5FA' },
    ]
  },
  {
    title: 'Time-Domain Micro-dynamics', keys: [
      { label: 'Energy', path: d => d.time_domain.energy, color: '#60A5FA' },
      { label: 'Hjorth Act.', path: d => d.time_domain.hjorth_act, color: '#34D399' },
      { label: 'Complexity', path: d => d.time_domain.hjorth_comp, color: '#A78BFA' },
    ]
  },
  {
    title: 'Wigner-Ville Phase-Space', keys: [
      { label: 'WV Energy', path: d => d.phase_space.wv_energy, color: '#60A5FA' },
      { label: 'WV Entropy', path: d => d.phase_space.wv_entropy, color: '#A78BFA' },
      { label: 'WV Kurtosis', path: d => d.phase_space.wv_kurtosis, color: '#FBBF24' },
    ]
  },
  {
    title: 'Synchronisation & Flux', keys: [
      { label: 'Zero-Crossing', path: d => d.time_domain.zcr, color: '#34D399' },
      { label: 'Peak-to-Peak', path: d => d.time_domain.peak_to_peak, color: '#F87171' },
      { label: 'Mean Sync', path: d => d.time_domain.inter_corr, color: '#60A5FA' },
    ]
  },
];

// ── Tiny shared components (defined outside any render fn) ────────────────────
const StatusDot = memo(({ color = '#34D399', size = 6 }) => (
  <div className="relative flex-shrink-0 flex items-center justify-center"
    style={{ width: size, height: size }}>
    <div className="absolute rounded-full animate-ping"
      style={{ width: size * 2.2, height: size * 2.2, backgroundColor: color, opacity: 0.12 }} />
    <div className="rounded-full" style={{ width: size, height: size, backgroundColor: color }} />
  </div>
));

const TopGlow = ({ color }) => (
  <div className="absolute top-0 left-6 right-6 h-px pointer-events-none"
    style={{ background: `linear-gradient(90deg,transparent,${color}45,transparent)` }} />
);

const SectionLabel = ({ children, color = '#60A5FA' }) => (
  <div className="text-[9px] font-bold tracking-[0.4em] uppercase mb-3"
    style={{ color, fontFamily: MONO }}>{children}</div>
);

const MetricCard = memo(({ label, value, icon: Icon, color, sub, bar, barColor }) => (
  <div className="relative overflow-hidden rounded-3xl p-5 flex flex-col gap-2.5"
    style={{ background: 'rgba(10,12,20,0.96)', border: '1px solid rgba(255,255,255,0.06)' }}>
    <TopGlow color={color} />
    <div className="flex items-center justify-between">
      <span className="text-[9px] font-bold tracking-[0.2em] uppercase"
        style={{ color: 'rgba(148,163,184,0.5)', fontFamily: MONO }}>{label}</span>
      <div className="p-1.5 rounded-lg" style={{ background: `${color}18` }}>
        <Icon size={12} style={{ color }} />
      </div>
    </div>
    <div className="text-2xl font-black tracking-tight leading-none"
      style={{ color, fontFamily: MONO }}>{value}</div>
    {sub && (
      <div className="text-[9px] tracking-widest uppercase"
        style={{ color: 'rgba(148,163,184,0.3)', fontFamily: MONO }}>{sub}</div>
    )}
    {bar !== undefined && (
      <div className="w-full h-0.5 rounded-full overflow-hidden mt-1"
        style={{ background: 'rgba(255,255,255,0.05)' }}>
        <div className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.min(100, bar)}%`, background: barColor || color }} />
      </div>
    )}
  </div>
));

// ═══════════════════════════════════════════════════════════════════════════════
//  LANDING  — memo so it never re-renders from App state changes
// ═══════════════════════════════════════════════════════════════════════════════
const Landing = memo(({ onEnter }) => {
  const [tab, setTab] = useState('home');
  const NAV = [
    { id: 'home', label: 'Overview' },
    { id: 'tech', label: 'Architecture' },
    { id: 'results', label: 'Performance' },
    { id: 'impact', label: 'Impact' },
  ];

  return (
    <div className="min-h-screen text-white flex flex-col relative overflow-x-hidden"
      style={{ background: '#030508' }}>

      {/* Ambient BG */}
      <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden">
        <video autoPlay loop muted playsInline className="absolute w-full h-full object-cover"
          style={{ opacity: 0.4 }}>
          <source src={video4} type="video/mp4" />
        </video>
        <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse 80% 50% at 50% 0%, rgba(99, 102, 241, 0.2) 0%, transparent 80%)' }} />
        <div className="absolute bottom-0 left-0 right-0 h-40" style={{ background: 'linear-gradient(to top, #030508, transparent)' }} />
      </div>

      {/* Nav */}
      <nav className="z-50 sticky top-0 flex items-center justify-between px-8 md:px-14"
        style={{ height: 66, background: 'rgba(3,5,8,0.8)', backdropFilter: 'blur(16px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'linear-gradient(135deg,#1D4ED8,#7C3AED)', boxShadow: '0 0 16px rgba(99,102,241,0.32)' }}>
            <Brain size={18} className="text-white" />
          </div>
          <div>
            <div className="text-[8px] font-bold tracking-[0.35em] uppercase"
              style={{ color: 'rgba(148,163,184,0.38)', fontFamily: MONO }}></div>
            <div className="text-sm font-black text-white leading-none">Epileptic Seizure Detection</div>
          </div>
        </div>

        <div className="hidden md:flex items-center gap-1 p-1 rounded-2xl"
          style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
          {NAV.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className="relative px-5 py-2 rounded-xl text-[11px] font-bold transition-colors"
              style={{ color: tab === t.id ? '#fff' : 'rgba(148,163,184,0.42)', fontFamily: MONO, letterSpacing: '0.06em' }}>
              {tab === t.id && (
                <motion.div layoutId="navPill" className="absolute inset-0 rounded-xl"
                  style={{ background: 'rgba(37,99,235,0.32)', border: '1px solid rgba(99,102,241,0.22)' }} />
              )}
              <span className="relative z-10">{t.label}</span>
            </button>
          ))}
        </div>

        <button onClick={onEnter}
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-[11px] font-bold hover:opacity-90 transition-opacity"
          style={{ background: 'linear-gradient(135deg,#1D4ED8,#7C3AED)', fontFamily: MONO, letterSpacing: '0.1em', color: '#fff', boxShadow: '0 0 16px rgba(99,102,241,0.25)' }}>
          <LayoutDashboard size={13} /> PORTAL
        </button>
      </nav>

      <main className="flex-1 z-10 overflow-y-auto">
        <AnimatePresence mode="wait">

          {/* HOME */}
          {tab === 'home' && (
            <motion.div key="home"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="max-w-6xl mx-auto px-8 md:px-14 pt-28 pb-40">

              <div className="text-center space-y-6 mb-36">
            
                <h1 className="text-6xl md:text-[7.5rem] font-black leading-[0.86] tracking-[-0.04em]">
                  <span className="text-white">Seizure</span><br />
                  <span style={{
                    background: 'linear-gradient(135deg,#60A5FA 0%,#A78BFA 55%,#F472B6 100%)',
                    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                  }}>Localization</span>
                </h1>

                <p className="text-lg md:text-xl max-w-2xl mx-auto leading-relaxed"
                  style={{ color: 'rgba(148,163,184,0.6)' }}>
                  Quantum-inspired feature engineering for enhanced preictal and ictal state classification via scalp EEG.
                </p>

                <div className="flex flex-col sm:flex-row gap-4 justify-center pt-3">
                  <button onClick={onEnter}
                    className="px-10 py-4 rounded-2xl font-bold text-[13px] hover:opacity-90 transition-opacity"
                    style={{ background: 'linear-gradient(135deg,#1D4ED8,#7C3AED)', fontFamily: MONO, letterSpacing: '0.1em', color: '#fff', boxShadow: '0 0 28px rgba(99,102,241,0.28)' }}>
                    OPEN DASHBOARD
                  </button>
                  <a href={researchPaper} target="_blank" rel="noopener noreferrer"
                    className="px-10 py-4 rounded-2xl font-bold text-[13px] flex items-center justify-center gap-2 hover:opacity-80 transition-opacity"
                    style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.6)', fontFamily: MONO, letterSpacing: '0.08em' }}>
                    <FileText size={14} /> VIEW PAPER
                  </a>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-36">
                {[
                  { value: '0.9376', label: 'ROC-AUC Score Of Quantum Classical Approach', color: '#60A5FA' },
                  { value: '50M+', label: 'Global Patients', color: '#34D399' },
                  { value: '11', label: 'Quantum Features', color: '#A78BFA' },
                  { value: '256Hz', label: 'EEG Resolution Of ChbMIT Dataset', color: '#F472B6' },
                ].map((s, i) => (
                  <div key={i} className="relative p-6 rounded-2xl overflow-hidden"
                    style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <TopGlow color={s.color} />
                    <div className="text-3xl font-black mb-1" style={{ color: s.color, fontFamily: MONO }}>{s.value}</div>
                    <div className="text-[9px] tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Challenge */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
                <div className="space-y-6">
                  <SectionLabel>The Challenge</SectionLabel>
                  <h2 className="text-5xl font-black leading-tight tracking-tight">
                    Beyond Classical<br /><span style={{ color: 'rgba(148,163,184,0.25)' }}>Signal Analysis</span>
                  </h2>
                  <p className="text-lg leading-relaxed" style={{ color: 'rgba(148,163,184,0.52)' }}>
                    Traditional EEG analysis misses global phase-space interactions. The core problem: reliably separating Pre-ictal from Ictal brain states in real-time.
                  </p>
                  <div className="grid grid-cols-2 gap-4">
                    {[
                      { icon: XCircle, color: '#F87171', title: 'Patient Locking', desc: 'Models fail on unseen patients chb21–24' },
                      { icon: Waves, color: '#FBBF24', title: 'Local Blindness', desc: 'Missing global phase-space interactions' },
                    ].map(({ icon: Icon, color, title, desc }) => (
                      <div key={title} className="p-5 rounded-2xl"
                        style={{ background: `${color}07`, border: `1px solid ${color}16` }}>
                        <Icon size={16} style={{ color }} className="mb-3" />
                        <div className="font-bold text-sm text-white mb-1">{title}</div>
                        <div className="text-xs leading-relaxed" style={{ color: 'rgba(148,163,184,0.42)' }}>{desc}</div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="relative rounded-[2.5rem] overflow-hidden"
                  style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(99,102,241,0.16)' }}>
                  <video autoPlay loop muted playsInline
                    className="absolute inset-0 w-full h-full object-cover opacity-10 mix-blend-screen">
                    <source src={video3} type="video/mp4" />
                  </video>
                  <div className="relative z-10 p-10 space-y-6">
                    <SectionLabel>The Mission</SectionLabel>
                    <h3 className="text-4xl font-black leading-tight">
                      Closing the<br /><span style={{ color: '#60A5FA' }}>Golden Window</span>
                    </h3>
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { val: '50M+', label: 'Global Lives', color: '#F87171' },
                        { val: '80%', label: 'Low-Resource', color: '#FBBF24' },
                      ].map(s => (
                        <div key={s.val} className="p-4 rounded-2xl"
                          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
                          <div className="text-2xl font-black" style={{ color: s.color, fontFamily: MONO }}>{s.val}</div>
                          <div className="text-[9px] tracking-widest uppercase mt-1" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>{s.label}</div>
                        </div>
                      ))}
                    </div>
                    <div className="space-y-2 pt-2">
                      <div className="flex justify-between text-[9px] font-bold"
                        style={{ fontFamily: MONO }}>
                        <span style={{ color: '#34D399' }}>Normal</span>
                        <span style={{ color: '#60A5FA' }}>QI Detection</span>
                        <span style={{ color: '#F87171' }}>Ictal</span>
                      </div>
                      <div className="relative h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
                        <motion.div
                          animate={{ x: ['0%', '200%'] }}
                          transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
                          className="absolute top-0 left-0 h-full w-1/3 rounded-full"
                          style={{ background: 'linear-gradient(90deg,transparent,#60A5FA,transparent)' }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* TECH */}
          {tab === 'tech' && (
            <motion.div key="tech"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="max-w-6xl mx-auto px-8 md:px-14 pt-24 pb-40">

              <div className="mb-14">
                <SectionLabel>// Methodology</SectionLabel>
                <h2 className="text-6xl md:text-8xl font-black tracking-tight leading-none">
                  Technical<br /><span style={{ color: 'rgba(148,163,184,0.22)' }}>Foundation</span>
                </h2>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-10">
                <div className="lg:col-span-4 space-y-6">
                  {[
                    { num: '3.1', title: 'Dataset', body: 'CHB–MIT Scalp EEG database at 256 Hz with clinically annotated transitions from 22 pediatric subjects.', items: ['Training: chb01–chb20', 'Test: chb21–chb23'] },
                    { num: '3.2', title: 'Preprocessing', body: null, items: ['Band-pass: 1–40 Hz', 'Notch: 50 Hz', 'ICA artifact removal', '1s windows / 2s stride'] },
                  ].map(s => (
                    <div key={s.num} className="p-7 rounded-3xl"
                      style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <div className="text-[8px] font-bold tracking-widest mb-1" style={{ color: 'rgba(148,163,184,0.22)', fontFamily: MONO }}>§ {s.num}</div>
                      <h3 className="text-base font-black text-white mb-3">{s.title}</h3>
                      {s.body && <p className="text-sm leading-relaxed mb-4" style={{ color: 'rgba(148,163,184,0.42)' }}>{s.body}</p>}
                      <div className="space-y-2">
                        {s.items.map(item => (
                          <div key={item} className="flex items-center gap-2.5 text-xs"
                            style={{ color: 'rgba(148,163,184,0.52)', fontFamily: MONO }}>
                            <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: '#60A5FA' }} />
                            {item}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="lg:col-span-8 space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    {[
                      { icon: Activity, color: '#60A5FA', title: 'Time-Domain (29)', desc: 'Hjorth descriptors, zero-crossing, dispersion, cross-channel statistics.', tags: ['Hjorth Complexity', 'Pearson Corr', 'Peak-to-Peak'] },
                      { icon: Zap, color: '#A78BFA', title: 'Freq-Domain (17)', desc: 'Welch PSD estimation summarising rhythmic energy redistribution across bands.', tags: ['Spectral Entropy', 'Band Ratios', 'Rel Power'] },
                    ].map(({ icon: Icon, color, title, desc, tags }) => (
                      <div key={title} className="p-8 rounded-3xl"
                        style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div className="p-2.5 rounded-xl inline-flex mb-5" style={{ background: `${color}12` }}>
                          <Icon size={22} style={{ color }} />
                        </div>
                        <h3 className="text-base font-black text-white mb-2">{title}</h3>
                        <p className="text-sm leading-relaxed mb-4" style={{ color: 'rgba(148,163,184,0.42)' }}>{desc}</p>
                        <div className="flex flex-wrap gap-2">
                          {tags.map(t => (
                            <span key={t} className="text-[9px] font-bold px-2.5 py-1 rounded-lg tracking-widest uppercase"
                              style={{ background: `${color}0E`, border: `1px solid ${color}18`, color: `${color}CC`, fontFamily: MONO }}>{t}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* QI table */}
                  <div className="p-8 rounded-3xl" style={{ background: 'rgba(99,102,241,0.04)', border: '1px solid rgba(99,102,241,0.12)' }}>
                    <div className="flex items-center gap-4 mb-6">
                      <div className="p-2.5 rounded-xl" style={{ background: 'rgba(99,102,241,0.16)' }}>
                        <Waves size={22} style={{ color: '#818CF8' }} />
                      </div>
                      <div>
                        <h3 className="text-base font-black text-white">Quantum-Inspired Features (11)</h3>
                        <p className="text-[9px] tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>Density Matrix-Based Global Dynamics</p>
                      </div>
                    </div>
                    <table className="w-full">
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <th className="text-left pb-3 pr-8 text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Feature</th>
                          <th className="text-left pb-3 text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>EEG Interpretation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ['Von Neumann Entropy', 'Global disorder and complexity of multichannel dynamics'],
                          ['Purity', 'Degree of global synchronisation and source dominance'],
                          ['Linear Entropy', 'Approximate mixedness of multichannel EEG activity'],
                          ['Quantum Coherence', 'Strength of inter-channel coupling'],
                          ['Quantum Fisher Info', 'Sensitivity of global EEG structure to perturbations'],
                          ['Entanglement Entropy', 'Information coupling between EEG channel subsets'],
                          ['Wigner Energy', 'Overall energy concentration in time-frequency plane'],
                          ['Wigner Entropy', 'Time-frequency complexity and spectral dispersion'],
                          ['Wigner Variance', 'Spread of energy in phase-space representation'],
                          ['Wigner Skewness', 'Asymmetry of transient oscillatory patterns'],
                          ['Wigner Kurtosis', 'Peakedness and intermittency of phase-space structure'],
                        ].map(([name, ctx]) => (
                          <tr key={name} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                            <td className="py-3 pr-8 font-bold text-sm whitespace-nowrap" style={{ color: '#818CF8', fontFamily: MONO }}>{name}</td>
                            <td className="py-3 text-sm" style={{ color: 'rgba(148,163,184,0.42)' }}>{ctx}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* RESULTS */}
          {tab === 'results' && (
            <motion.div key="results"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="max-w-5xl mx-auto px-8 md:px-14 pt-24 pb-40">

              <div className="mb-12">
                <SectionLabel color="#34D399">// Validation Results</SectionLabel>
                <h2 className="text-6xl font-black tracking-tight">
                  Performance<br /><span style={{ color: 'rgba(148,163,184,0.22)' }}>Benchmarks</span>
                </h2>
              </div>

              <div className="grid grid-cols-12 gap-5">
                <div className="col-span-12 lg:col-span-8 rounded-3xl overflow-hidden"
                  style={{ background: 'rgba(10,12,20,0.96)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="p-8">
                    <div className="text-[9px] font-bold tracking-widest uppercase mb-6" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>
                      Cross-Patient Validation — chb21, chb22, chb23
                    </div>
                    <table className="w-full">
                      <thead>
                        <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                          <th className="text-left pb-4 text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Feature Configuration</th>
                          <th className="text-right pb-4 text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>ROC-AUC</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          { label: 'Time-domain only', score: '0.8890', color: '#F87171', w: '72%' },
                          { label: 'Frequency-domain only', score: '0.9078', color: '#FBBF24', w: '80%' },
                          { label: 'Classical Hybrid (T+F)', score: '0.9151', color: '#60A5FA', w: '84%' },
                          { label: 'Quantum-Inspired only', score: '0.9239', color: '#34D399', w: '88%' },
                          { label: 'UNIFIED HYBRID (T+F+QI)', score: '0.9376', color: '#818CF8', w: '95%', hi: true },
                        ].map((row, i) => (
                          <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                            <td className="py-4 pr-6">
                              <div className="text-sm font-bold" style={{ color: row.hi ? '#fff' : 'rgba(148,163,184,0.52)' }}>{row.label}</div>
                              <div className="mt-2 h-0.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.04)' }}>
                                <motion.div initial={{ width: 0 }} animate={{ width: row.w }}
                                  transition={{ delay: i * 0.1 + 0.2, duration: 0.7 }}
                                  className="h-full rounded-full" style={{ background: row.color }} />
                              </div>
                            </td>
                            <td className="py-4 text-right font-black"
                              style={{ color: row.color, fontFamily: MONO, fontSize: row.hi ? 22 : 15 }}>{row.score}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="col-span-12 lg:col-span-4 space-y-4">
                  {[
                    { val: '0.90', label: 'Ictal Sensitivity', sub: 'Recall w/ QI', color: '#60A5FA' },
                    { val: '0.9376', label: 'Best ROC-AUC', sub: 'Unified Hybrid', color: '#818CF8' },
                    { val: '3', label: 'Unseen Patients', sub: 'Strict test set', color: '#34D399' },
                  ].map(s => (
                    <div key={s.val} className="relative p-6 rounded-2xl overflow-hidden"
                      style={{ background: `${s.color}07`, border: `1px solid ${s.color}16` }}>
                      <TopGlow color={s.color} />
                      <div className="text-3xl font-black mb-1" style={{ color: s.color, fontFamily: MONO }}>{s.val}</div>
                      <div className="text-sm font-bold text-white">{s.label}</div>
                      <div className="text-[9px] mt-0.5" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>{s.sub}</div>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          {/* IMPACT */}
          {tab === 'impact' && (
            <motion.div key="impact"
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              className="max-w-5xl mx-auto px-8 md:px-14 pt-24 pb-40 space-y-14">

              <div>
                <SectionLabel color="#A78BFA">// Global Impact</SectionLabel>
                <h2 className="text-6xl font-black tracking-tight">
                  Epilepsy<br /><span style={{ color: 'rgba(148,163,184,0.22)' }}>Worldwide</span>
                </h2>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="p-6 rounded-3xl" style={{ background: 'rgba(10,12,20,0.96)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="text-[9px] font-bold tracking-widest uppercase mb-5" style={{ color: '#60A5FA', fontFamily: MONO }}>Treatment Gap Index</div>
                  <div className="h-52">
                    <Bar
                      data={{ labels: ['Low Income', 'Lower-Mid', 'Upper-Mid', 'High Income'], datasets: [{ data: [75, 46, 28, 10], backgroundColor: ['rgba(96,165,250,0.7)', 'rgba(96,165,250,0.5)', 'rgba(96,165,250,0.3)', 'rgba(96,165,250,0.14)'], borderRadius: 6 }] }}
                      options={{ maintainAspectRatio: false, animation: false, plugins: { legend: { display: false } }, scales: { y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: 'rgba(148,163,184,0.32)', font: { size: 9 } } }, x: { grid: { display: false }, ticks: { color: 'rgba(148,163,184,0.32)', font: { size: 9 } } } } }}
                    />
                  </div>
                </div>
                <div className="p-6 rounded-3xl" style={{ background: 'rgba(10,12,20,0.96)', border: '1px solid rgba(255,255,255,0.06)' }}>
                  <div className="text-[9px] font-bold tracking-widest uppercase mb-5" style={{ color: '#34D399', fontFamily: MONO }}>Annual Incidence</div>
                  <div className="h-52">
                    <Doughnut
                      data={{ labels: ['Low-Mid Income', 'High Income'], datasets: [{ data: [139, 49], backgroundColor: ['rgba(52,211,153,0.65)', 'rgba(255,255,255,0.05)'], borderWidth: 0 }] }}
                      options={{ maintainAspectRatio: false, animation: false, plugins: { legend: { position: 'bottom', labels: { color: 'rgba(148,163,184,0.32)', font: { size: 10, weight: 'bold' } } } } }}
                    />
                  </div>
                  <div className="text-center mt-2">
                    <div className="text-xl font-black" style={{ color: '#34D399', fontFamily: MONO }}>139 vs 49</div>
                    <div className="text-[9px]" style={{ color: 'rgba(148,163,184,0.28)', fontFamily: MONO }}>per 100,000 population</div>
                  </div>
                </div>
              </div>

              {[
                { title: 'Overview', color: '#60A5FA', body: 'Epilepsy is a chronic noncommunicable disease of the brain affecting around 50 million people worldwide, characterised by recurrent seizures from excessive electrical discharges in brain cells.' },
                { title: 'Epidemiology', color: '#34D399', body: 'Globally, 5 million new diagnoses occur each year. In low- and middle-income countries, incidence reaches up to 139 per 100,000—close to 80% of all patients live in these settings.' },
                { title: 'Treatment Gap', color: '#A78BFA', body: 'Up to 70% of people could become seizure-free with appropriate medication. Yet in low-income countries, three-quarters do not receive adequate treatment—the Treatment Gap.' },
              ].map(s => (
                <section key={s.title} className="space-y-3">
                  <SectionLabel color={s.color}>// {s.title.toUpperCase()}</SectionLabel>
                  <h3 className="text-3xl font-black text-white">{s.title}</h3>
                  <p className="text-lg leading-relaxed" style={{ color: 'rgba(148,163,184,0.52)' }}>{s.body}</p>
                </section>
              ))}
            </motion.div>
          )}

        </AnimatePresence>
      </main>

      <footer className="z-50 sticky bottom-0 flex items-center justify-between px-14"
        style={{ height: 52, background: 'rgba(3,5,8,0.85)', backdropFilter: 'blur(14px)', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
        <span className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.18)', fontFamily: MONO }}>Epileptic Seizure </span>
        <div className="flex items-center gap-2">
          <StatusDot color="#34D399" size={5} />
          <span className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.18)', fontFamily: MONO }}>All systems operational</span>
        </div>
      </footer>
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════════════════════
//  DASHBOARD  — memo, receives all state via props
// ═══════════════════════════════════════════════════════════════════════════════
const Dashboard = memo(({
  patients, selectedPatient, patientDetails, modelStatus, selectedFile,
  isRunning, isAnalyzing, analysisData, intelligence, history,
  syncStarting, zoomedChart, aiReport, isConsulting,
  onGoHome, onSelectPatient, onSelectFile, onStartAnalysis,
  onQuantumSync, onConsultAI, onSetZoomed, onCloseAI,
  gridRefs, modalChartRef,
}) => {
  const [chartMode, setChartMode] = useState('timeline');
  const sc = getStateColors(intelligence.state);
  const waveColor = WAVE_COLOR[intelligence.state] || '#60A5FA';
  const showOverlay = isAnalyzing || (isRunning && (intelligence.state === 'INITIALIZING' || syncStarting));

  const eegData = {
    labels: intelligence.wave.map((_, i) => i),
    datasets: [{
      data: intelligence.wave,
      borderColor: waveColor,
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
      fill: false,
    }],
  };

  return (
    <div className="min-h-screen flex flex-col md:flex-row overflow-hidden relative"
      style={{ background: '#0A0B14', color: '#E2E8F0' }}>
      <div className="absolute inset-0 z-0 pointer-events-none"
        style={{ background: 'radial-gradient(circle at 50% -20%, rgba(99, 102, 241, 0.12) 0%, transparent 60%)' }} />

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside className="hidden md:flex w-72 flex-col flex-shrink-0"
        style={{ background: 'rgba(7,9,15,0.99)', borderRight: '1px solid rgba(255,255,255,0.05)' }}>

        <div className="p-5 flex items-center justify-between flex-shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: 'linear-gradient(135deg,#1D4ED8,#7C3AED)', boxShadow: '0 0 12px rgba(99,102,241,0.3)' }}>
              <Brain size={16} className="text-white" />
            </div>
            <div>
              <div className="text-[8px] font-bold tracking-[0.3em] uppercase" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>CHBMIT_DATASET</div>
              <div className="text-sm font-black text-white leading-none">Patient Portal</div>
            </div>
          </div>
          <button onClick={onGoHome} className="p-1.5 rounded-xl hover:bg-white/5 transition-colors"
            style={{ color: 'rgba(148,163,184,0.32)' }}>
            <ArrowLeft size={15} />
          </button>
        </div>

        <div className="p-3 flex-1 overflow-y-auto"
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.05) transparent' }}>
          <div className="flex items-center justify-between mb-3 px-2">
            <span className="text-[8px] font-bold tracking-[0.3em] uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Active Patients</span>
            <Users size={11} style={{ color: 'rgba(148,163,184,0.25)' }} />
          </div>
          <div className="space-y-1">
            {patients.map(p => {
              const active = selectedPatient?.id === p.id;
              return (
                <button key={p.id} onClick={() => onSelectPatient(p)}
                  className="w-full text-left p-3.5 rounded-2xl transition-all relative overflow-hidden"
                  style={{
                    background: active ? 'rgba(99,102,241,0.13)' : 'transparent',
                    border: `1px solid ${active ? 'rgba(99,102,241,0.26)' : 'transparent'}`,
                  }}>
                  {active && (
                    <div className="absolute top-0 left-0 right-0 h-px"
                      style={{ background: 'linear-gradient(90deg,transparent,rgba(99,102,241,0.45),transparent)' }} />
                  )}
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: active ? 'rgba(99,102,241,0.22)' : 'rgba(255,255,255,0.04)', border: `1px solid ${active ? 'rgba(99,102,241,0.32)' : 'rgba(255,255,255,0.06)'}` }}>
                      <Fingerprint size={14} style={{ color: active ? '#818CF8' : 'rgba(148,163,184,0.32)' }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-bold" style={{ color: active ? '#fff' : 'rgba(148,163,184,0.55)' }}>{p.id}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <StatusDot color="#34D399" size={5} />
                        <span className="text-[8px] font-bold tracking-widest uppercase" style={{ color: '#34D399', fontFamily: MONO }}>Live</span>
                      </div>
                    </div>
                    {active && <ChevronRight size={13} style={{ color: '#818CF8' }} />}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="p-3 flex-shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-2.5 p-3 rounded-xl"
            style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
            <StatusDot color="#34D399" size={5} />
            <span className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Node v2.4a — Online</span>
          </div>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">

        {/* Header */}
        <header className="h-14 flex items-center justify-between px-7 flex-shrink-0"
          style={{ background: 'rgba(7,9,15,0.95)', backdropFilter: 'blur(10px)', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3">
            {selectedPatient && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[9px] font-bold tracking-widest uppercase"
                style={{
                  background: modelStatus === 'exists' ? 'rgba(52,211,153,0.07)' : modelStatus === 'checking' ? 'rgba(251,191,36,0.07)' : 'rgba(248,113,113,0.07)',
                  border: `1px solid ${modelStatus === 'exists' ? 'rgba(52,211,153,0.18)' : modelStatus === 'checking' ? 'rgba(251,191,36,0.18)' : 'rgba(248,113,113,0.18)'}`,
                  color: modelStatus === 'exists' ? '#34D399' : modelStatus === 'checking' ? '#FBBF24' : '#F87171',
                  fontFamily: MONO,
                }}>
                {modelStatus === 'exists'
                  ? <><CheckCircle2 size={10} className="mr-1" /> Model Ready</>
                  : modelStatus === 'checking'
                    ? <><RefreshCw size={10} className="animate-spin mr-1" /> Syncing...</>
                    : <><XCircle size={10} className="mr-1" /> Offline</>
                }
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {patientDetails?.files && (
              <select onChange={e => onSelectFile(e.target.value)}
                className="text-[10px] font-bold px-3 py-2 rounded-xl outline-none cursor-pointer"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(148,163,184,0.65)', fontFamily: MONO }}>
                <option value="" style={{ background: '#06070D' }}>Select EEG Capture</option>
                {patientDetails.files.map(f => <option key={f} value={f} style={{ background: '#06070D' }}>{f}</option>)}
              </select>
            )}
            {selectedFile && (
              <>
                <button onClick={onStartAnalysis} disabled={isAnalyzing}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-bold disabled:opacity-40 transition-opacity"
                  style={{ background: 'rgba(167,139,250,0.11)', border: '1px solid rgba(167,139,250,0.22)', color: '#A78BFA', fontFamily: MONO, letterSpacing: '0.08em' }}>
                  <BarChart3 size={12} /> {isAnalyzing ? 'ANALYZING...' : 'FULL ANALYSIS'}
                </button>
                <button onClick={onQuantumSync} disabled={modelStatus !== 'exists'}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-bold disabled:opacity-30 disabled:cursor-not-allowed transition-opacity"
                  style={{ background: 'rgba(96,165,250,0.11)', border: '1px solid rgba(96,165,250,0.22)', color: '#60A5FA', fontFamily: MONO, letterSpacing: '0.08em' }}>
                  <Zap size={12} fill="currentColor" /> {isRunning ? 'RESTART' : 'RUN TCN'}
                </button>
              </>
            )}
          </div>
        </header>

        {/* Overlay */}
        <AnimatePresence>
          {showOverlay && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center"
              style={{ background: 'rgba(3,5,8,0.9)', backdropFilter: 'blur(18px)' }}>
              <div className="absolute inset-0 pointer-events-none">
                <video autoPlay loop muted playsInline className="w-full h-full object-cover mix-blend-screen opacity-25">
                  <source src={video1} type="video/mp4" />
                </video>
              </div>
              <div className="relative z-10 text-center space-y-7">
                <div className="relative w-20 h-20 mx-auto">
                  <div className="absolute inset-0 rounded-full animate-spin" style={{ border: '2px solid rgba(96,165,250,0.08)', borderTop: '2px solid #60A5FA' }} />
                  <div className="absolute inset-3 rounded-full animate-spin" style={{ border: '1px solid rgba(167,139,250,0.08)', borderBottom: '1px solid #A78BFA', animationDirection: 'reverse', animationDuration: '1.2s' }} />
                  <div className="absolute inset-0 flex items-center justify-center"><Brain size={22} style={{ color: '#60A5FA' }} /></div>
                </div>
                <div>
                  <h2 className="text-3xl font-black text-white tracking-tight mb-2">{isAnalyzing ? 'Deep Analysis' : 'Running Temporal Convolutional Network '}</h2>
                  <p className="text-[10px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>Mapping Neural Trajectories...</p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Workspace */}
        <div className="flex-1 p-6 overflow-y-auto space-y-5 min-h-0"
          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.04) transparent' }}>

          {!selectedPatient ? (
            <div className="flex items-center justify-center rounded-3xl overflow-hidden relative"
              style={{ minHeight: 480, background: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.04)' }}>
              <video autoPlay loop muted playsInline className="absolute inset-0 w-full h-full object-cover opacity-[0.16] pointer-events-none"
                style={{ filter: 'brightness(1.2)' }}>
                <source src={video2} type="video/mp4" />
              </video>
              <div className="relative z-10 text-center space-y-4">
                <div className="w-16 h-16 rounded-3xl flex items-center justify-center mx-auto"
                  style={{ background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)' }}>
                  <Users size={28} style={{ color: '#818CF8' }} />
                </div>
                <div>
                  <h2 className="text-3xl font-black text-white mb-2">Select a Patient</h2>
                  <p className="text-sm" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>Choose a subject from the sidebar</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-5">

              {/* Metric cards */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <MetricCard label="Neural State" icon={Activity} value={intelligence.state} color={sc.text}
                  sub={`Confidence: ${(intelligence.probs[2] * 100).toFixed(1)}%`} />
                <MetricCard label="vN Entropy" icon={Waves} value={intelligence.metrics.entropy.toFixed(3)} color="#60A5FA"
                  bar={Math.min(100, intelligence.metrics.entropy * 20)} barColor="#60A5FA" sub="Von Neumann" />
                <MetricCard label="Entanglement" icon={Cpu} value={intelligence.metrics.entanglement.toFixed(3)} color="#A78BFA"
                  bar={Math.min(100, intelligence.metrics.entanglement * 30)} barColor="#A78BFA" sub="Channel Coupling" />
                <MetricCard label="Risk Factor" icon={Shield}
                  value={intelligence.probs[1] > 0.4 ? 'ELEVATED' : 'NOMINAL'}
                  color={intelligence.probs[1] > 0.4 ? '#FBBF24' : '#34D399'}
                  sub={`Preictal: ${(intelligence.probs[1] * 100).toFixed(1)}%`} />
              </div>

              {/* Centre layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">

                {/* EEG chart */}
                <div className="col-span-1 lg:col-span-8 rounded-3xl flex flex-col relative overflow-hidden"
                  style={{ background: 'rgba(8,10,18,0.98)', border: `1px solid ${sc.border}`, minHeight: 400 }}>

                  <div className="absolute top-0 left-0 right-0 h-px pointer-events-none"
                    style={{ background: `linear-gradient(90deg,transparent,${sc.text}30,transparent)` }} />

                  <video autoPlay loop muted playsInline
                    className="absolute inset-0 w-full h-full object-cover pointer-events-none"
                    style={{ opacity: isRunning ? 0.08 : 0, transition: 'opacity 1s', filter: 'brightness(1.1)' }}>
                    <source src={video2} type="video/mp4" />
                  </video>

                  {/* EEG header */}
                  <div className="relative z-10 flex items-center justify-between px-5 pt-5">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl"
                        style={{ background: 'rgba(248,113,113,0.07)', border: '1px solid rgba(248,113,113,0.16)' }}>
                        <StatusDot color="#F87171" size={5} />
                        <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: '#F87171', fontFamily: MONO }}>Live EEG</span>
                      </div>
                      <span className="text-[9px] font-bold" style={{ color: 'rgba(148,163,184,0.22)', fontFamily: MONO }}>t={intelligence.time}</span>
                    </div>
                    {intelligence.gt_state && intelligence.gt_state !== 'NORMAL' && (
                      <div className="px-3 py-1.5 rounded-xl text-[9px] font-bold tracking-widest uppercase"
                        style={{ background: intelligence.gt_state === 'ICTAL' ? 'rgba(248,113,113,0.1)' : 'rgba(251,191,36,0.1)', border: `1px solid ${intelligence.gt_state === 'ICTAL' ? 'rgba(248,113,113,0.22)' : 'rgba(251,191,36,0.22)'}`, color: intelligence.gt_state === 'ICTAL' ? '#F87171' : '#FBBF24', fontFamily: MONO }}>
                        Clinical: {intelligence.gt_state}
                      </div>
                    )}
                  </div>

                  {/* Chart */}
                  <div className="relative z-10 flex-1 px-5 pt-4" style={{ minHeight: 240 }}>
                    <Line data={eegData} options={EEG_CHART_OPTIONS} />
                  </div>

                  {/* Footer */}
                  <div className="relative z-10 flex items-center justify-between px-5 py-4"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                    <div className="flex items-end gap-2">
                      {intelligence.probs.map((prob, i) => {
                        const colors = ['#34D399', '#FBBF24', '#F87171', '#A78BFA'];
                        const labels = ['NRM', 'PRE', 'ICT', 'INT'];
                        return (
                          <div key={i} className="flex flex-col items-center gap-1">
                            <div className="w-5 h-7 rounded flex items-end overflow-hidden p-0.5"
                              style={{ background: 'rgba(255,255,255,0.03)' }}>
                              <div className="w-full rounded-sm transition-all duration-500"
                                style={{ height: `${Math.max(4, prob * 100)}%`, background: colors[i], opacity: 0.7 }} />
                            </div>
                            <span className="text-[7px] font-bold" style={{ color: colors[i], fontFamily: MONO }}>{labels[i]}</span>
                          </div>
                        );
                      })}
                    </div>
                    <button onClick={onConsultAI} disabled={isConsulting}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-[10px] font-bold disabled:opacity-50 transition-opacity"
                      style={{ background: 'rgba(96,165,250,0.09)', border: '1px solid rgba(96,165,250,0.2)', color: '#60A5FA', fontFamily: MONO, letterSpacing: '0.08em' }}>
                      <Brain size={12} /> {isConsulting ? 'CONSULTING...' : 'AI CONSULTANT'}
                    </button>
                  </div>
                </div>

                {/* Right panel */}
                <div className="col-span-1 lg:col-span-4 space-y-4">

                  {/* Patient metadata */}
                  <div className="p-5 rounded-3xl" style={{ background: 'rgba(8,10,18,0.98)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    <div className="text-[8px] font-bold tracking-widest uppercase mb-4" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Patient Metadata</div>
                    {patientDetails?.metadata ? (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between p-3 rounded-2xl"
                          style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}>
                          <span className="text-[9px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Channels</span>
                          <span className="text-2xl font-black" style={{ color: '#60A5FA', fontFamily: MONO }}>{patientDetails.metadata.channels || 18}</span>
                        </div>
                        <div className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.18)', fontFamily: MONO }}>Seizure Events</div>
                        <div className="space-y-1.5 max-h-36 overflow-y-auto"
                          style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.04) transparent' }}>
                          {patientDetails.metadata.seizures?.length > 0
                            ? patientDetails.metadata.seizures.map((s, idx) => (
                              <div key={idx} className="p-3 rounded-xl"
                                style={{ background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.09)' }}>
                                <div className="text-[9px] font-bold text-white truncate" style={{ fontFamily: MONO }}>{s.file}</div>
                                <div className="flex justify-between text-[8px] mt-1" style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>
                                  <span>↦ {s.start}s</span><span>↤ {s.end}s</span>
                                </div>
                              </div>
                            ))
                            : <div className="text-center py-4 text-[9px] font-bold" style={{ color: 'rgba(148,163,184,0.18)', fontFamily: MONO }}>No annotations found</div>
                          }
                        </div>
                        {patientDetails.metadata.clinical_notes && (
                          <div className="p-3 rounded-2xl" style={{ background: 'rgba(96,165,250,0.04)', border: '1px solid rgba(96,165,250,0.09)' }}>
                            <div className="text-[8px] font-bold tracking-widest uppercase mb-1.5" style={{ color: '#60A5FA', fontFamily: MONO }}>Clinical Notes</div>
                            <p className="text-[10px] leading-relaxed" style={{ color: 'rgba(148,163,184,0.38)' }}>{patientDetails.metadata.clinical_notes}</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="h-36 flex items-center justify-center text-[9px] font-bold tracking-widest uppercase animate-pulse"
                        style={{ color: 'rgba(148,163,184,0.16)', fontFamily: MONO }}>Awaiting Handshake...</div>
                    )}
                  </div>

                  {/* Inference history */}
                  <div className="p-5 rounded-3xl" style={{ background: 'rgba(8,10,18,0.98)', border: '1px solid rgba(255,255,255,0.05)', minHeight: 160 }}>
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Inference History</div>
                      {isRunning && <StatusDot color="#60A5FA" size={5} />}
                    </div>
                    <div className="space-y-1.5">
                      {history.length === 0
                        ? <div className="text-center py-6 text-[9px] font-bold tracking-widest uppercase"
                          style={{ color: 'rgba(148,163,184,0.14)', fontFamily: MONO }}>Listening...</div>
                        : history.map((item, idx) => {
                          const hc = getStateColors(item.state);
                          return (
                            <div key={`${item.time}-${idx}`}
                              className="flex items-center justify-between p-3 rounded-xl"
                              style={{ background: hc.bg, border: `1px solid ${hc.border}` }}>
                              <div className="flex items-center gap-2">
                                <div className="w-1.5 h-1.5 rounded-full" style={{ background: hc.text }} />
                                <span className="text-[10px] font-bold" style={{ color: hc.text, fontFamily: MONO }}>{item.state}</span>
                              </div>
                              <span className="text-[9px]" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>{item.time}</span>
                            </div>
                          );
                        })
                      }
                    </div>
                  </div>
                </div>
              </div>

              {/* Analysis Charts */}
              {analysisData && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between pt-3"
                    style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                    <div>
                      <h2 className="text-base font-black text-white">Deep Neural Analysis</h2>
                      <p className="text-[9px] font-bold tracking-widest uppercase mt-0.5"
                        style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>{selectedFile}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-lg p-0.5 mr-2">
                        <button onClick={() => setChartMode('timeline')} className="px-3 py-1 text-[9px] font-bold tracking-widest uppercase rounded-md transition-colors"
                          style={{ background: chartMode === 'timeline' ? 'rgba(96,165,250,0.1)' : 'transparent', color: chartMode === 'timeline' ? '#60A5FA' : 'rgba(148,163,184,0.4)' }}>Timeline</button>
                        <button onClick={() => setChartMode('comparison')} className="px-3 py-1 text-[9px] font-bold tracking-widest uppercase rounded-md transition-colors"
                          style={{ background: chartMode === 'comparison' ? 'rgba(96,165,250,0.1)' : 'transparent', color: chartMode === 'comparison' ? '#60A5FA' : 'rgba(148,163,184,0.4)' }}>State Comparison</button>
                      </div>
                      {chartMode === 'timeline' && [['Full Trace', '#A78BFA'], ['Ictal Zone', '#F87171'], ['Pre-Ictal', '#FBBF24']].map(([label, color]) => (
                        <div key={label} className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[8px] font-bold tracking-widest uppercase"
                          style={{ background: `${color}07`, border: `1px solid ${color}16`, color, fontFamily: MONO }}>
                          <div className="w-1.5 h-1.5 rounded-full" style={{ background: color }} />{label}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    {CHART_DEFS.map((def, idx) => {
                      let chartData, chartOpts;

                      if (chartMode === 'timeline') {
                        chartData = {
                          labels: analysisData.time,
                          datasets: def.keys.map(k => ({
                            label: k.label,
                            data: smooth(normalise(k.path(analysisData))),
                            borderColor: k.color,
                            borderWidth: 1.2,
                            pointRadius: 0,
                            tension: 0.1,
                          }))
                        };
                        chartOpts = makeGridOptions(analysisData.markers);
                      } else {
                        chartData = {
                          labels: ['Baseline (Norm)', 'Pre-Ictal Phase', 'Ictal Peak'],
                          datasets: def.keys.map(k => ({
                            label: k.label,
                            data: computeMeans(normalise(k.path(analysisData)), analysisData.time, analysisData.markers),
                            backgroundColor: `${k.color}99`,
                            borderColor: k.color,
                            borderWidth: 1.5,
                            borderRadius: 6,
                            barPercentage: 0.7,
                            categoryPercentage: 0.8,
                          }))
                        };
                        chartOpts = makeBarOptions();
                      }

                      return (
                        <div key={idx} className="group rounded-3xl overflow-hidden"
                          style={{ background: 'rgba(8,10,18,0.98)', border: '1px solid rgba(255,255,255,0.05)' }}>
                          <div className="flex items-center justify-between px-4 pt-4 pb-2">
                            <span className="text-[9px] font-bold tracking-widest uppercase"
                              style={{ color: 'rgba(148,163,184,0.32)', fontFamily: MONO }}>{def.title}</span>
                            {chartMode === 'timeline' && (
                              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button onClick={e => { e.stopPropagation(); gridRefs[idx].current?.zoom(1.15); }}
                                  className="p-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(148,163,184,0.4)' }}><Plus size={11} /></button>
                                <button onClick={e => { e.stopPropagation(); gridRefs[idx].current?.zoom(0.85); }}
                                  className="p-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(148,163,184,0.4)' }}><Minus size={11} /></button>
                                <button onClick={e => { e.stopPropagation(); gridRefs[idx].current?.resetZoom(); }}
                                  className="p-1.5 rounded-lg" style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(148,163,184,0.4)' }}><RefreshCw size={11} /></button>
                                <button onClick={() => onSetZoomed({ title: def.title, datasets: chartData.datasets, markers: analysisData.markers, time: analysisData.time })}
                                  className="p-1.5 rounded-lg"
                                  style={{ background: 'rgba(96,165,250,0.1)', border: '1px solid rgba(96,165,250,0.18)', color: '#60A5FA' }}><Eye size={11} /></button>
                              </div>
                            )}
                          </div>
                          <div className="px-4 pb-4 h-52">
                            {chartMode === 'timeline'
                              ? <Line ref={gridRefs[idx]} data={chartData} options={chartOpts} />
                              : <Bar data={chartData} options={chartOpts} />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

            </div>
          )}
        </div>
      </main>

      {/* Zoom Modal */}
      <AnimatePresence>
        {zoomedChart && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] flex items-center justify-center p-8"
            style={{ background: 'rgba(2,3,7,0.93)', backdropFilter: 'blur(18px)' }}
            onClick={() => onSetZoomed(null)}>
            <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} exit={{ scale: 0.95 }}
              className="w-full h-full max-w-6xl rounded-3xl flex flex-col overflow-hidden relative"
              style={{ background: 'rgba(8,10,18,0.99)', border: '1px solid rgba(255,255,255,0.07)' }}
              onClick={e => e.stopPropagation()}>
              <div className="absolute top-0 left-0 right-0 h-px"
                style={{ background: 'linear-gradient(90deg,transparent,rgba(96,165,250,0.38),transparent)' }} />
              <div className="flex items-center justify-between p-5 flex-shrink-0"
                style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <div>
                  <div className="text-[8px] font-bold tracking-widest uppercase mb-1" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>{zoomedChart.title}</div>
                  <h3 className="text-lg font-black text-white">Detailed Trace — scroll to zoom · drag to pan</h3>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1 p-1 rounded-xl" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                    {[
                      [Plus, () => modalChartRef.current?.zoom(1.2)],
                      [Minus, () => modalChartRef.current?.zoom(0.8)],
                      [RefreshCw, () => modalChartRef.current?.resetZoom()],
                    ].map(([Icon, action], i) => (
                      <button key={i} onClick={action} className="p-2 rounded-lg"
                        style={{ background: 'rgba(255,255,255,0.04)', color: 'rgba(148,163,184,0.4)' }}>
                        <Icon size={14} />
                      </button>
                    ))}
                  </div>
                  <button onClick={() => onSetZoomed(null)} className="p-2 rounded-xl"
                    style={{ background: 'rgba(248,113,113,0.09)', border: '1px solid rgba(248,113,113,0.18)', color: '#F87171' }}>
                    <XCircle size={16} />
                  </button>
                </div>
              </div>
              <div className="flex-1 p-5 min-h-0">
                <Line ref={modalChartRef}
                  data={{ labels: zoomedChart.time, datasets: zoomedChart.datasets.map(d => ({ ...d, borderWidth: 2.5 })) }}
                  options={makeModalOptions(zoomedChart.markers)} />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* AI Panel */}
      <AnimatePresence>
        {aiReport && (
          <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 280, damping: 30 }}
            className="fixed top-14 right-0 bottom-0 flex flex-col z-50"
            style={{ width: 352, background: 'rgba(6,7,13,0.99)', borderLeft: '1px solid rgba(96,165,250,0.12)', backdropFilter: 'blur(14px)' }}>
            <div className="absolute top-0 left-0 right-0 h-px"
              style={{ background: 'linear-gradient(90deg,transparent,rgba(96,165,250,0.4),transparent)' }} />
            <div className="p-5 flex items-center justify-between flex-shrink-0"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-xl" style={{ background: 'rgba(96,165,250,0.09)', border: '1px solid rgba(96,165,250,0.18)' }}>
                  <Brain size={15} style={{ color: '#60A5FA' }} />
                </div>
                <div>
                  <div className="font-black text-white text-sm">AI Consultant</div>
                  <div className="text-[8px] font-bold tracking-widest uppercase" style={{ color: 'rgba(148,163,184,0.25)', fontFamily: MONO }}>Neural Analysis</div>
                </div>
              </div>
              <button onClick={onCloseAI} className="p-2 rounded-xl"
                style={{ background: 'rgba(248,113,113,0.07)', color: '#F87171' }}>
                <XCircle size={15} />
              </button>
            </div>
            <div className="flex-1 p-5 overflow-y-auto space-y-4 min-h-0"
              style={{ scrollbarWidth: 'thin', scrollbarColor: 'rgba(255,255,255,0.04) transparent' }}>
              <div className="p-3 rounded-xl text-xs italic"
                style={{ background: 'rgba(96,165,250,0.04)', border: '1px solid rgba(96,165,250,0.09)', color: 'rgba(96,165,250,0.5)' }}>
                Analysing {selectedPatient?.id}...
              </div>
              <div className="text-sm leading-relaxed whitespace-pre-wrap" style={{ color: 'rgba(148,163,184,0.62)' }}>
                {aiReport}
              </div>
              {isConsulting && (
                <div className="flex items-center gap-2 text-[9px] font-bold tracking-widest uppercase animate-pulse"
                  style={{ color: '#60A5FA', fontFamily: MONO }}>
                  <RefreshCw size={10} className="animate-spin" /> Updating...
                </div>
              )}
            </div>
            <div className="p-5 flex-shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
              <button onClick={onConsultAI}
                className="w-full py-3 rounded-xl font-bold text-[10px] tracking-widest uppercase hover:opacity-80 transition-opacity"
                style={{ background: 'rgba(96,165,250,0.07)', border: '1px solid rgba(96,165,250,0.16)', color: '#60A5FA', fontFamily: MONO }}>
                Refresh Report
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
});

// ═══════════════════════════════════════════════════════════════════════════════
//  ROOT  — only holds state + refs
// ═══════════════════════════════════════════════════════════════════════════════
const App = () => {
  const [view, setView] = useState('landing');
  const [patients, setPatients] = useState([]);
  const [selectedPatient, setSelected] = useState(null);
  const [patientDetails, setDetails] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [selectedFile, setFile] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisData, setAnalysis] = useState(null);
  const [intelligence, setIntelligence] = useState({
    state: 'IDLE', time: '0.0s',
    wave: new Array(150).fill(0),
    metrics: { entropy: 0, entanglement: 0, fisher_info: 0, energy_flux: 0 },
    probs: [1, 0, 0, 0],
  });
  const [history, setHistory] = useState([]);
  const [syncStarting, setSyncStarting] = useState(false);
  const [zoomedChart, setZoomed] = useState(null);
  const [aiReport, setAiReport] = useState(null);
  const [isConsulting, setConsulting] = useState(false);

  const sseRef = useRef(null);
  const modalChartRef = useRef(null);

  const gRef0 = useRef(null); const gRef1 = useRef(null); const gRef2 = useRef(null);
  const gRef3 = useRef(null); const gRef4 = useRef(null); const gRef5 = useRef(null);
  const gRef6 = useRef(null); const gRef7 = useRef(null); const gRef8 = useRef(null);
  const gRef9 = useRef(null); const gRef10 = useRef(null); const gRef11 = useRef(null);
  const gRef12 = useRef(null); const gRef13 = useRef(null); const gRef14 = useRef(null);
  const gRef15 = useRef(null); const gRef16 = useRef(null); const gRef17 = useRef(null);
  const gRef18 = useRef(null); const gRef19 = useRef(null); const gRef20 = useRef(null);
  const gRef21 = useRef(null); const gRef22 = useRef(null); const gRef23 = useRef(null);
  const gridRefs = [gRef0, gRef1, gRef2, gRef3, gRef4, gRef5, gRef6, gRef7, gRef8, gRef9, gRef10, gRef11,
    gRef12, gRef13, gRef14, gRef15, gRef16, gRef17, gRef18, gRef19, gRef20, gRef21, gRef22, gRef23];

  useEffect(() => {
    api.get('/patients').then(r => setPatients(r.data)).catch(() => { });
  }, []);

  const handleSelectPatient = useCallback(async (patient) => {
    setSelected(patient);
    setModelStatus('checking');
    setDetails(null);
    setFile('');
    setIsRunning(false);
    setAnalysis(null);
    setAiReport(null);
    if (sseRef.current) sseRef.current.close();
    try {
      const [mRes, dRes] = await Promise.all([
        api.get(`/check_model/${patient.id}`),
        api.get(`/patient_details/${patient.id}`),
      ]);
      setModelStatus(mRes.data.exists ? 'exists' : 'missing');
      setDetails(dRes.data);
    } catch { setModelStatus('missing'); }
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    setIsAnalyzing(true);
    setAnalysis(null);
    setAiReport(null);
    try {
      const res = await api.get(`/analysis?patient_id=${selectedPatient.id}&file_name=${selectedFile}`);
      setAnalysis(res.data);
    } catch { alert('Analysis failed. Check backend.'); }
    finally { setIsAnalyzing(false); }
  }, [selectedPatient, selectedFile]);

  const handleConsultAI = useCallback(async () => {
    if (!analysisData) return;
    setConsulting(true);
    try {
      const res = await api.post('/ai_consultation', {
        patient_id: selectedPatient.id, file_name: selectedFile, features: analysisData,
      });
      setAiReport(res.data.report);
    } catch { setAiReport('Consultation channel disrupted.'); }
    finally { setConsulting(false); }
  }, [analysisData, selectedPatient, selectedFile]);

  const handleQuantumSync = useCallback(() => {
    if (sseRef.current) sseRef.current.close();
    setHistory([]);
    setIntelligence(prev => ({ ...prev, state: 'INITIALIZING' }));
    setIsRunning(true);
    setSyncStarting(true);
    setTimeout(() => setSyncStarting(false), 4000);

    const url = `${API_BASE}/stream_inference?patient_id=${selectedPatient.id}&file_name=${selectedFile}`;
    sseRef.current = new EventSourcePolyfill(url, { headers: { 'ngrok-skip-browser-warning': 'true' } });

    let lastUpdate = 0;
    sseRef.current.onmessage = (e) => {
      const now = Date.now();
      if (now - lastUpdate < 60) return; // Throttle UI updates to ~16fps for performance
      lastUpdate = now;

      const data = JSON.parse(e.data);
      setIntelligence(prev => ({
        ...prev,
        state: data.state,
        time: data.time,
        wave: [...prev.wave, ...data.wave].slice(-150),
        metrics: data.metrics || prev.metrics,
        probs: data.probabilities || prev.probs,
      }));
      setHistory(prev => {
        if (data.state === 'INITIALIZING' || data.state === prev[0]?.state) return prev;
        return [{ time: data.time, state: data.state }, ...prev].slice(0, 8);
      });
    };
    sseRef.current.onerror = () => { setIsRunning(false); sseRef.current.close(); };
  }, [selectedPatient, selectedFile]);

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700;800;900&display=swap');
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.07); border-radius: 2px; }
      `}</style>

      {view === 'landing'
        ? <Landing key="landing" onEnter={() => setView('dashboard')} />
        : <Dashboard key="dashboard"
          patients={patients}
          selectedPatient={selectedPatient}
          patientDetails={patientDetails}
          modelStatus={modelStatus}
          selectedFile={selectedFile}
          isRunning={isRunning}
          isAnalyzing={isAnalyzing}
          analysisData={analysisData}
          intelligence={intelligence}
          history={history}
          syncStarting={syncStarting}
          zoomedChart={zoomedChart}
          aiReport={aiReport}
          isConsulting={isConsulting}
          onGoHome={() => setView('landing')}
          onSelectPatient={handleSelectPatient}
          onSelectFile={setFile}
          onStartAnalysis={handleStartAnalysis}
          onQuantumSync={handleQuantumSync}
          onConsultAI={handleConsultAI}
          onSetZoomed={setZoomed}
          onCloseAI={() => setAiReport(null)}
          gridRefs={gridRefs}
          modalChartRef={modalChartRef}
        />
      }
    </>
  );
};

export default App;