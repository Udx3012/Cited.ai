"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  FileText, MessageSquare, Compass, Shield, Zap, CheckCircle2,
  ChevronRight, ArrowRight, Upload, Search, Check, Database, Server,
  Cpu, Link2, FileCode, Layers, Play, Settings, RefreshCw, HelpCircle,
  FileCheck, AlertTriangle
} from "lucide-react";
import { useGSAPAnimations } from "@/hooks/useGSAPAnimations";

// Helper: split text into individual character spans for GSAP targeting
function SplitChars({ children, className = "" }: { children: string; className?: string }) {
  return (
    <>
      {children.split("").map((char, i) => (
        <span
          key={i}
          data-gsap-hero-char
          className={className}
          style={{ display: "inline-block", whiteSpace: char === " " ? "pre" : undefined }}
        >
          {char}
        </span>
      ))}
    </>
  );
}

// Animation presets
const fadeInUp = {
  initial: { opacity: 0, y: 25 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-100px" },
  transition: { duration: 0.6, ease: [0.16, 1, 0.3, 1] }
};

const staggerContainer = {
  initial: {},
  whileInView: {
    transition: {
      staggerChildren: 0.1
    }
  },
  viewport: { once: true, margin: "-100px" }
};

export default function Home() {
  // Navigation states
  const [scrolled, setScrolled] = useState(false);

  // Initialize all GSAP scroll-driven animations
  useGSAPAnimations();

  // Dashboard mock states
  const [activeTab, setActiveTab] = useState("chat");
  const [activeCitation, setActiveCitation] = useState<number | null>(null);

  // Sync state hooks
  const [mockDocs, setMockDocs] = useState<any[]>([
    { name: "Q4-Report.pdf", size: "124 KB", chunks: 145 },
    { name: "GDPR-Handbook.pdf", size: "842 KB", chunks: 212 },
    { name: "AI-Act-Brief.pdf", size: "98 KB", chunks: 55 }
  ]);
  const [totalChunks, setTotalChunks] = useState(412);
  const [mockCitations, setMockCitations] = useState<any[]>([
    { id: 1, name: "Q4-Report.pdf", page: "p. 34", score: 0.94, text: "The Q4-2025 report identifies three primary regulatory risk vectors affecting the fiscal outlook [1] including cross-border data-transfer restrictions..." },
    { id: 2, name: "GDPR-Handbook.pdf", page: "p. 118", score: 0.89, text: "Evolving AI governance mandates require strict isolation..." },
    { id: 3, name: "AI-Act-Brief.pdf", page: "p. 7", score: 0.81, text: "Attribution requirements for large language models..." }
  ]);
  const [chatConv, setChatConv] = useState({
    userText: "What does the Q4 report say about regulatory risk?",
    aiText: "The Q4-2025 report identifies three primary regulatory risk vectors affecting the fiscal outlook [1] including cross-border data-transfer restrictions [2] and evolving AI governance mandates.",
    cites: [1, 2],
    latency: "842 ms",
    score: "94.6%"
  });

  // Sync data on mount
  useEffect(() => {
    // 1. Get documents
    const savedDocs = localStorage.getItem("cited_documents");
    if (savedDocs) {
      try {
        const parsed = JSON.parse(savedDocs);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMockDocs(parsed.map((d: any) => ({
            name: d.name,
            size: d.size,
            chunks: d.chunks || 0
          })));
          const sum = parsed.reduce((acc: number, d: any) => acc + (d.chunks || 0), 0);
          setTotalChunks(sum);
        }
      } catch (e) {
        console.error("Mockup failed to parse saved documents:", e);
      }
    }

    // 2. Get chat messages and citations
    const savedMessages = localStorage.getItem("cited_chat_messages");
    const savedCitesMap = localStorage.getItem("cited_chat_citations");
    if (savedMessages) {
      try {
        const messages = JSON.parse(savedMessages);
        if (Array.isArray(messages)) {
          // Find the last user message and the next AI message
          let lastUserIdx = -1;
          for (let i = messages.length - 1; i >= 0; i--) {
            if (messages[i].sender === "user") {
              lastUserIdx = i;
              break;
            }
          }
          if (lastUserIdx !== -1 && lastUserIdx + 1 < messages.length) {
            const userMsg = messages[lastUserIdx];
            const aiMsg = messages[lastUserIdx + 1];
            if (aiMsg && aiMsg.sender === "ai") {
              let citesList: any[] = [];
              if (savedCitesMap) {
                const citesMap = JSON.parse(savedCitesMap);
                citesList = (aiMsg.citations || []).map((cId: any) => {
                  const c = citesMap[cId];
                  return c ? {
                    id: c.id,
                    name: c.source,
                    page: `p. ${c.page}`,
                    score: parseFloat(c.score || "0.9")
                  } : null;
                }).filter(Boolean);
              }
              
              setChatConv({
                userText: userMsg.text,
                aiText: aiMsg.text,
                cites: aiMsg.citations || [],
                latency: aiMsg.latency || "842 ms",
                score: aiMsg.score || "94.6%"
              });

              if (citesList.length > 0) {
                setMockCitations(citesList);
              }
            }
          }
        }
      } catch (e) {
        console.error("Mockup failed to parse saved chat messages:", e);
      }
    }
  }, []);

  const renderTextWithCitations = (text: string) => {
    const parts = text.split(/(\[\d+\])/g);
    return (
      <span className="text-xs text-zinc-300 leading-relaxed mb-1">
        {parts.map((part, index) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const citId = parseInt(match[1], 10);
            const isHighlighted = activeCitation === citId;
            return (
              <button
                key={index}
                onClick={() => setActiveCitation(isHighlighted ? null : citId)}
                className={`inline-flex items-center justify-center w-5 h-5 mx-1 text-[10px] font-bold rounded ${
                  isHighlighted ? "bg-[#45A29E] text-black" : "bg-zinc-800 text-[#45A29E] hover:bg-zinc-700"
                } transition-all`}
              >
                {citId}
              </button>
            );
          }
          return part;
        })}
      </span>
    );
  };

  // Architecture interactive step state
  const [expandedStep, setExpandedStep] = useState<number | null>(1);

  // Monitor scrolling to style header
  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Tech Stack status list
  const techStack = [
    { name: "FastAPI", category: "Backend" },
    { name: "Postgres + pgvector", category: "Vector store" },
    { name: "OpenSearch", category: "BM25" },
    { name: "AI Embeddings", category: "Embeddings" },
    { name: "AI Reranker", category: "Reranker" },
    { name: "AI Models", category: "LLM" },
    { name: "S3 / R2", category: "Object storage" },
    { name: "Kubernetes", category: "Runtime" },
    { name: "OpenTelemetry", category: "Observability" },
    { name: "React + Tailwind", category: "Frontend" }
  ];

  // Pipeline architecture steps
  const steps = [
    {
      num: "01",
      title: "Ingest",
      desc: "PDF • DOCX",
      detail: "Upload documents up to 50MB. The system automatically secures and indexes file structure and contents in persistent object storage, so they are ready to search."
    },
    {
      num: "02",
      title: "Parse & OCR",
      desc: "Layout-aware text extraction",
      detail: "Extracts document layout, hierarchy, and text naturally. Automatically applies OCR engines to read scanned pages, figures, and charts, ensuring no data is missed."
    },
    {
      num: "03",
      title: "Chunk",
      desc: "Semantic context grouping",
      detail: "Intelligently groups text based on paragraph boundaries, sections, and tables rather than arbitrary word counts, preserving context flow for the search engine."
    },
    {
      num: "04",
      title: "Embed",
      desc: "1024-dim search vectors",
      detail: "Converts document sections into high-density semantic search vectors using optimized embedding APIs. Features automatic failover configurations to guarantee service uptime."
    },
    {
      num: "05",
      title: "Hybrid Search",
      desc: "Dense Proximity + Exact Match",
      detail: "Combines semantic search vectors with keyword-based sparse matching. Merges results using rank reciprocity to find matching context with maximum relevance."
    },
    {
      num: "06",
      title: "Rerank",
      desc: "Neural Reranking Stage",
      detail: "Re-evaluates search candidates through a secondary neural reranker, sorting out irrelevant blocks and leaving only the most contextually relevant chunks."
    },
    {
      num: "07",
      title: "Ground & Cite",
      desc: "Verified Answer Generation",
      detail: "Synthesizes answers strictly using retrieved context. A secondary validation layer cross-audits every claim against source chunks to guarantee zero hallucinations and provide clickable page numbers."
    }
  ];

  return (
    <div className="relative min-h-screen bg-[#030303] text-zinc-200">

      {/* Noise Texture Overlay — premium grain */}
      <div className="noise-overlay" />

      {/* Cursor Glow Follower — ambient interactivity */}
      <div data-gsap-cursor-glow className="cursor-glow" />

      {/* Background Decorative Blur Gradients — GSAP parallax targets */}
      <div data-gsap-orb data-gsap-speed="-0.3" className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full bg-[#45A29E]/[0.03] blur-[120px] pointer-events-none animate-glow-slow" />
      <div data-gsap-orb data-gsap-speed="0.2" className="absolute top-[30%] right-[-10%] w-[60%] h-[60%] rounded-full bg-blue-500/[0.02] blur-[150px] pointer-events-none" />
      <div data-gsap-orb data-gsap-speed="-0.15" className="absolute bottom-[10%] left-[20%] w-[40%] h-[40%] rounded-full bg-amber-500/[0.015] blur-[130px] pointer-events-none" />
      <div data-gsap-orb data-gsap-speed="0.4" className="absolute top-[60%] right-[5%] w-[35%] h-[35%] rounded-full bg-[#45A29E]/[0.015] blur-[100px] pointer-events-none" />
      <div data-gsap-orb data-gsap-speed="-0.25" className="absolute top-[10%] left-[40%] w-[25%] h-[25%] rounded-full bg-purple-500/[0.01] blur-[100px] pointer-events-none" />

      {/* Sticky Navigation Header */}
      <header className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 border-b border-white/[0.04] bg-[#030303]/60 backdrop-blur-md ${scrolled ? "py-4 shadow-[0_10px_30px_rgba(0,0,0,0.8)]" : "py-5"}`}>
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between">
          <a href="#" className="flex items-center gap-2 group">
            <span className="text-white font-semibold text-lg tracking-tight">Cited.AI</span>
          </a>

          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-zinc-400 hover:text-white transition-colors text-sm font-medium">Features</a>
            <a href="#architecture" className="text-zinc-400 hover:text-white transition-colors text-sm font-medium">Architecture</a>
            <a href="#how-it-works" className="text-zinc-400 hover:text-white transition-colors text-sm font-medium">How it works</a>
            <a href="#stack" className="text-zinc-400 hover:text-white transition-colors text-sm font-medium">Stack</a>
          </nav>

          <div className="flex items-center gap-6">
            <a href="/login" className="text-zinc-400 hover:text-white transition-colors text-sm font-medium">Sign in</a>
            <a href="/login" className="bg-white hover:bg-zinc-200 text-black px-4 py-2 rounded-full text-sm font-semibold transition-all shadow-[0_0_15px_rgba(255,255,255,0.1)] hover:scale-[1.02] active:scale-[0.98]">
              Get started
            </a>
          </div>
        </div>
      </header>

      {/* Page 1: Hero Section */}
      <section className="relative pt-36 pb-12 flex flex-col items-center justify-center overflow-hidden">
        {/* Hero Grid Pattern — depth backdrop */}
        <div className="hero-grid absolute inset-0 pointer-events-none" />

        <div className="max-w-7xl mx-auto px-6 text-center flex flex-col items-center z-10">


          {/* Heading */}
          <h1
            className="text-5xl md:text-7xl font-serif text-white tracking-tight leading-[1.2] mb-6 max-w-4xl"
            style={{ perspective: "800px" }}
          >
            <SplitChars>Let your documents</SplitChars>
            <br />
            <span className="italic text-shimmer drop-shadow-[0_0_20px_rgba(69,162,158,0.3)]" data-gsap-hero-char>
              answer
            </span>
            <SplitChars> for you.</SplitChars>
          </h1>

          {/* Subtitle */}
          <p
            data-gsap-hero-sub
            className="text-zinc-400 text-base md:text-lg max-w-2xl leading-relaxed mb-10 font-sans font-normal"
            style={{ opacity: 0 }}
          >
            Cited.AI is a grounded retrieval platform for teams that can&apos;t afford hallucinations.
            Upload once, ask anything — every answer arrives with page-level citations and a verifiable trail.
          </p>

          {/* Action CTAs */}
          <div
            data-gsap-hero-ctas
            className="flex flex-col sm:flex-row items-center gap-4 mb-16"
            style={{ opacity: 0 }}
          >
            <a href="/login" className="flex items-center gap-2 bg-[#45A29E] hover:bg-[#3d9490] text-black px-6 py-3.5 rounded-full text-sm font-semibold transition-all hover:scale-[1.02] shadow-[0_4px_20px_rgba(69,162,158,0.25)] hover:shadow-[0_6px_30px_rgba(69,162,158,0.35)]">
              Start building <ArrowRight className="w-4 h-4" />
            </a>
            <a href="#how-it-works" className="flex items-center gap-2 bg-zinc-900/60 hover:bg-zinc-900 border border-white/[0.08] hover:border-[#45A29E]/30 text-white px-6 py-3.5 rounded-full text-sm font-semibold transition-all">
              See how it works
            </a>
          </div>

          {/* Quick specs / trust banner */}
          <div
            className="flex flex-wrap justify-center items-center gap-x-8 gap-y-3 text-[10px] md:text-xs font-semibold tracking-[0.2em] text-zinc-400 uppercase"
          >
            <span data-gsap-trust-item style={{ opacity: 0 }}>No credit card</span>
            <span data-gsap-trust-item style={{ opacity: 0 }} className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
            <span data-gsap-trust-item style={{ opacity: 0 }}>SOC 2 Type II</span>
            <span data-gsap-trust-item style={{ opacity: 0 }} className="w-1.5 h-1.5 rounded-full bg-zinc-800" />
            <span data-gsap-trust-item style={{ opacity: 0 }}>GDPR Ready</span>
          </div>
        </div>
      </section>

      {/* Page 2: Platform Screenshot/Mockup */}
      <section className="py-12 relative flex justify-center">
        <div className="max-w-7xl mx-auto px-6 w-full perspective-container">
          {/* Floating shadow underneath mockup */}
          <div data-gsap-mockup-shadow className="mockup-shadow w-[80%] h-16 mx-auto -mb-8 rounded-full" style={{ opacity: 0 }} />

          <div
            data-gsap-mockup
            className="w-full rounded-xl border border-white/[0.06] bg-[#08080a] shadow-[0_20px_60px_rgba(0,0,0,0.8),0_0_80px_rgba(69,162,158,0.03)] overflow-hidden"
            style={{ opacity: 0 }}
          >
            {/* Window Top Bar */}
            <div className="px-4 py-3 bg-[#0d0d11] border-b border-white/[0.05] flex items-center justify-between">
              {/* Window Controls */}
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-zinc-805" />
                <div className="w-3 h-3 rounded-full bg-zinc-805" />
                <div className="w-3 h-3 rounded-full bg-zinc-805" />
              </div>

              {/* Address bar */}
              <div className="text-zinc-400 text-xs font-mono bg-zinc-950 px-6 py-1 rounded-md border border-white/[0.03]">
                cited.ai / workspace / acme
              </div>

              <div className="w-12" /> {/* spacer */}
            </div>

            {/* Platform Application Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[500px] text-zinc-300 font-sans">

              {/* App Sidebar (3 cols) */}
              <div className="lg:col-span-3 bg-[#060608] border-r border-white/[0.04] p-4 flex flex-col justify-between">
                <div>
                  {/* Stats badge */}
                  <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-900/60 border border-white/[0.03] mb-6">
                    <FileText className="w-4 h-4 text-[#45A29E]" />
                    <span className="text-xs font-medium text-zinc-300">{totalChunks} chunks embedded</span>
                  </div>

                  {/* Navigation Links */}
                  <div className="space-y-1">
                    {[
                      { id: "dashboard", label: "Overview", icon: Layers },
                      { id: "documents", label: "Documents", icon: FileCode },
                      { id: "chat", label: "Chat Sandbox", icon: MessageSquare },
                      { id: "inspector", label: "AI Inspector", icon: Compass },
                      { id: "evaluation", label: "Evaluation", icon: Shield },
                      { id: "settings", label: "Settings", icon: Settings }
                    ].map((tab) => {
                      const Icon = tab.icon;
                      const isActive = activeTab === tab.id;
                      return (
                        <button
                          key={tab.id}
                          onClick={() => {
                            setActiveTab(tab.id);
                            setActiveCitation(null);
                          }}
                          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${isActive
                            ? "bg-zinc-900 text-white shadow-inner border border-white/[0.03]"
                            : "text-zinc-400 hover:text-zinc-300 hover:bg-zinc-900/20"
                            }`}
                        >
                          <Icon className={`w-4 h-4 ${isActive ? "text-[#45A29E]" : "text-zinc-400"}`} />
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Bottom score card */}
                <div className="mt-8 pt-4 border-t border-white/[0.03] flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500" />
                    <span className="text-[11px] text-zinc-300 font-semibold tracking-wider uppercase">Faithfulness</span>
                  </div>
                  <span className="text-xs font-bold text-green-400">{chatConv.score}</span>
                </div>
              </div>

              {/* App Content Panel (9 cols: handles tabs) */}
              <div className="lg:col-span-9 flex flex-col lg:flex-row bg-[#08080a]">
                <div className="flex-1 p-6 flex flex-col justify-between border-b lg:border-b-0 lg:border-r border-white/[0.04]">

                  {/* Dynamic Tab Content */}
                  <div className="h-full flex flex-col justify-center">
                    <AnimatePresence mode="wait">
                      {activeTab === "chat" && (
                        <motion.div
                          key="chat-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-6"
                        >
                          {/* User Message */}
                          <div className="flex gap-4 items-start">
                            <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center text-xs font-bold text-zinc-300 shrink-0 font-sans">
                              U
                            </div>
                            <div className="bg-zinc-900/40 border border-white/[0.03] px-4 py-3 rounded-2xl rounded-tl-none max-w-xl">
                              <p className="text-xs text-zinc-300 leading-relaxed font-sans font-normal">
                                {chatConv.userText}
                              </p>
                            </div>
                          </div>

                          {/* Assistant Message */}
                          <div className="flex gap-4 items-start">
                            <div className="w-8 h-8 rounded-full bg-blue-950 border border-blue-900/50 flex items-center justify-center text-xs font-bold text-blue-400 shrink-0 font-sans">
                              A
                            </div>
                            <div className="bg-[#0b0c10] border border-blue-950/30 px-4 py-3 rounded-2xl rounded-tl-none max-w-xl shadow-[0_4px_30px_rgba(59,130,246,0.02)] w-full">
                              {renderTextWithCitations(chatConv.aiText)}

                              {/* Skeleton line representing continuing streaming text */}
                              <div className="h-1.5 w-3/4 bg-zinc-800/40 rounded-full mt-4" />
                              <div className="h-1.5 w-1/2 bg-zinc-800/20 rounded-full mt-2" />
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {activeTab === "dashboard" && (
                        <motion.div
                          key="dashboard-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <h3 className="text-sm font-semibold text-white">System Metrics</h3>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="bg-zinc-950 p-4 rounded-xl border border-white/[0.03]">
                              <span className="text-[10px] text-zinc-300 block font-medium uppercase">Faithfulness</span>
                              <span className="text-xl font-bold text-green-400 mt-1 block">{chatConv.score}</span>
                            </div>
                            <div className="bg-zinc-950 p-4 rounded-xl border border-white/[0.03]">
                              <span className="text-[10px] text-zinc-300 block font-medium uppercase">latency p95</span>
                              <span className="text-xl font-bold text-white mt-1 block">{chatConv.latency}</span>
                            </div>
                            <div className="bg-zinc-950 p-4 rounded-xl border border-white/[0.03]">
                              <span className="text-[10px] text-zinc-300 block font-medium uppercase">Chunks Embedded</span>
                              <span className="text-xl font-bold text-[#45A29E] mt-1 block">{totalChunks}</span>
                            </div>
                            <div className="bg-zinc-950 p-4 rounded-xl border border-white/[0.03]">
                              <span className="text-[10px] text-zinc-300 block font-medium uppercase">Hallucinations</span>
                              <span className="text-xl font-bold text-zinc-300 mt-1 block">0.00%</span>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {activeTab === "documents" && (
                        <motion.div
                          key="documents-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-3"
                        >
                          <h3 className="text-sm font-semibold text-white">Active Corpora</h3>
                          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                            {mockDocs.map((doc, idx) => (
                              <div key={idx} className="bg-zinc-950/80 px-4 py-3 rounded-lg border border-white/[0.03] flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <FileText className="w-4 h-4 text-zinc-300" />
                                  <span className="text-xs font-medium text-zinc-300">{doc.name}</span>
                                </div>
                                <div className="flex items-center gap-4">
                                  <span className="text-[10px] text-zinc-300 font-mono">{doc.size}</span>
                                  <span className="text-[10px] text-zinc-300 bg-zinc-900 border border-white/[0.04] px-2 py-0.5 rounded">{doc.chunks} chunks</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </motion.div>
                      )}

                      {activeTab === "inspector" && (
                        <motion.div
                          key="inspector-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-3"
                        >
                          <h3 className="text-sm font-semibold text-white">Retrieval Stages</h3>
                          <div className="space-y-2 text-[11px] font-mono">
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03]">
                              <span className="text-[#45A29E]">1. Dense Match (Qdrant)</span>
                              <p className="text-zinc-300 mt-1">Returned 10 documents based on vector distance.</p>
                            </div>
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03]">
                              <span className="text-[#45A29E]">2. Sparse Match (BM25)</span>
                              <p className="text-zinc-300 mt-1">Found exact matches for query terms: &quot;{chatConv.userText.split(" ").slice(0, 3).join(" ")}&quot;.</p>
                            </div>
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03]">
                              <span className="text-[#45A29E]">3. Cross-Encoder Rerank</span>
                              <p className="text-zinc-300 mt-1">Sorted top 20 candidate chunks. Replaced ranking indexes 4 and 1.</p>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {activeTab === "evaluation" && (
                        <motion.div
                          key="evaluation-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-3"
                        >
                          <h3 className="text-sm font-semibold text-white">Golden Evaluation Set Results</h3>
                          <div className="p-4 bg-zinc-950 border border-white/[0.03] rounded-lg flex items-center justify-between">
                            <div>
                              <span className="text-2xl font-serif font-bold text-white">92.4%</span>
                              <span className="text-[10px] text-zinc-300 block mt-1">Overall correctness (n=50)</span>
                            </div>
                            <div className="text-right">
                              <span className="text-[10px] text-green-400 font-mono block">Faithfulness: 96%</span>
                              <span className="text-[10px] text-[#45A29E] font-mono block mt-1">Citation Accuracy: 90%</span>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      {activeTab === "settings" && (
                        <motion.div
                          key="settings-tab"
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0 }}
                          className="space-y-4"
                        >
                          <h3 className="text-sm font-semibold text-white">System Configurations</h3>
                          <div className="space-y-3">
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03] flex justify-between items-center text-xs">
                              <div>
                                <span className="text-white font-medium block">Default Temperature</span>
                                <span className="text-[10px] text-zinc-300">Strict deterministic mode</span>
                              </div>
                              <span className="font-mono text-zinc-300">0.0</span>
                            </div>
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03] flex justify-between items-center text-xs">
                              <div>
                                <span className="text-white font-medium block">Search Weights</span>
                                <span className="text-[10px] text-zinc-300">Hybrid balance (Dense / BM25)</span>
                              </div>
                              <span className="font-mono text-[#45A29E]">0.7 / 0.3</span>
                            </div>
                            <div className="bg-zinc-950 p-3 rounded border border-white/[0.03] flex justify-between items-center text-xs">
                              <div>
                                <span className="text-white font-medium block">API Engine Endpoint</span>
                                <span className="text-[10px] text-zinc-300">Secure FastAPI server</span>
                              </div>
                              <span className="font-mono text-zinc-300 truncate max-w-[120px]">cited.ai/api/v1</span>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Chat Input Placeholder */}
                  <div className="mt-8 pt-4 border-t border-white/[0.04] flex items-center justify-between gap-3">
                    <input
                      type="text"
                      placeholder="Ask Cited.ai a question..."
                      className="bg-zinc-950 text-xs px-4 py-3 rounded-full border border-white/[0.04] flex-1 text-zinc-400 focus:outline-none focus:border-[#45A29E]/30 transition-all font-normal"
                      disabled
                    />
                    <button className="bg-zinc-900 border border-white/[0.05] text-[#45A29E] w-9 h-9 rounded-full flex items-center justify-center">
                      <Search className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Citations Column (3 cols) */}
                <div className="w-full lg:w-72 bg-[#060608] p-4 flex flex-col justify-between">
                  <div>
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4 pb-2 border-b border-white/[0.03]">
                      <span className="text-[10px] text-zinc-300 font-bold uppercase tracking-wider font-sans">Citations</span>
                      <span className="text-[10px] text-[#45A29E] font-semibold bg-[#45A29E]/10 border border-[#45A29E]/20 px-2 py-0.5 rounded font-sans">{mockCitations.length} verified citations</span>
                    </div>

                    {/* Cards */}
                    <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                      {mockCitations.map((cit) => {
                        const isHighlighted = activeCitation === cit.id;
                        return (
                          <div
                            key={cit.id}
                            onClick={() => setActiveCitation(activeCitation === cit.id ? null : cit.id)}
                            className={`p-3 rounded-lg border text-left cursor-pointer transition-all ${isHighlighted
                              ? "bg-zinc-900/80 border-[#45A29E] shadow-[0_0_15px_rgba(197,168,128,0.05)]"
                              : "bg-zinc-950/40 border-white/[0.03] hover:border-white/[0.08]"
                              }`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-semibold text-zinc-300 truncate max-w-[130px] flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${isHighlighted ? "bg-[#45A29E]" : "bg-zinc-700"}`} />
                                [{cit.id}] {cit.name}
                              </span>
                              <span className="text-[10px] font-bold text-green-400 font-mono">{cit.score}</span>
                            </div>
                            <span className="text-[10px] text-zinc-400 font-mono block">{cit.page}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Latency statistics */}
                  <div className="mt-8 pt-4 border-t border-white/[0.03] flex items-center gap-2 text-zinc-400">
                    <Zap className="w-3.5 h-3.5 text-[#45A29E]" />
                    <span className="text-[10px] font-mono tracking-wider">842 ms P95</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Page 3: Capabilities Section */}
      <section id="features" className="py-24 relative overflow-hidden">
        {/* Section divider line */}
        <div className="section-divider-line w-full absolute top-0" />

        <div className="max-w-7xl mx-auto px-6">

          {/* Header */}
          <div className="mb-16">
            <div data-gsap-section-label className="flex items-center gap-3 mb-4">
              <div data-gsap-label-line className="section-divider-line w-8 h-[1px]" />
              <span data-gsap-label-text className="text-xs font-mono font-bold tracking-[0.2em] text-blue-500 uppercase">CAPABILITIES</span>
            </div>
            <h2 data-gsap-heading className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4">
              Retrieval that <br />
              actually retrieves.
            </h2>
            <p className="text-zinc-400 text-sm md:text-base max-w-xl font-normal leading-relaxed">
              Cited.AI ships the entire RAG stack — parsing, chunking, hybrid search, reranking, grounded synthesis and continuous evaluation — in one clean primitive.
            </p>
          </div>

          {/* Grid */}
          <div
            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          >
            {[
              {
                title: "Grounded, page-level citations",
                desc: "Every claim links back to the exact chunk, page and confidence score. No black boxes.",
                icon: FileText
              },
              {
                title: "Hybrid retrieval, out of the box",
                desc: "Dense + BM25 with Reciprocal Rank Fusion and a cross-encoder reranker — tuned per corpus.",
                icon: Database
              },
              {
                title: "Retrieval inspector",
                desc: "Visualize every stage: what got retrieved, why it ranked, and how the AI used it.",
                icon: Compass
              },
              {
                title: "Evaluation, not vibes",
                desc: "Track faithfulness, MRR, nDCG and hallucination rate over time. Ship with confidence.",
                icon: RefreshCw
              },
              {
                title: "Enterprise-grade privacy",
                desc: "SOC 2, GDPR, per-tenant encryption. Bring your own model or run fully on-prem.",
                icon: Shield
              },
              {
                title: "Ridiculously fast",
                desc: "Sub-second retrieval on millions of chunks. Streaming answers with typed markdown.",
                icon: Zap
              }
            ].map((card, idx) => {
              const Icon = card.icon;
              return (
                <div
                  key={idx}
                  data-gsap-cap-card
                  className="glass-card p-6 rounded-2xl flex flex-col justify-between group"
                >
                  <div>
                    {/* Icon container */}
                    <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.04] flex items-center justify-center mb-6 group-hover:border-[#45A29E]/30 transition-colors">
                      <Icon className="w-5 h-5 text-[#45A29E]" />
                    </div>

                    {/* Title */}
                    <h3 className="text-base font-semibold text-white mb-2 leading-snug">
                      {card.title}
                    </h3>

                    {/* Description */}
                    <p className="text-zinc-300 text-sm leading-relaxed font-normal font-sans">
                      {card.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Page 4: Architecture Section */}
      <section id="architecture" className="py-24 relative">
        {/* Section divider line */}
        <div className="section-divider-line w-full absolute top-0" />

        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">

            {/* Left Header Info (5 cols) */}
            <div className="lg:col-span-5 flex flex-col justify-start">
              <div data-gsap-section-label className="flex items-center gap-3 mb-4">
                <div data-gsap-label-line className="section-divider-line w-8 h-[1px]" />
                <span data-gsap-label-text className="text-xs font-mono font-bold tracking-[0.2em] text-blue-500 uppercase">ARCHITECTURE</span>
              </div>
              <h2 data-gsap-heading className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4 leading-tight">
                Every stage, <br />
                observable.
              </h2>
              <p className="text-zinc-400 text-sm md:text-base font-normal leading-relaxed mb-8">
                Cited.AI isn&apos;t a single AI call wrapped in a UI. It&apos;s an end-to-end pipeline where you can inspect what got retrieved, why it ranked, and how the model used it — down to the character span.
              </p>

              {/* Decorative mini status box */}
              <div className="hidden lg:block p-4 bg-zinc-950 border border-white/[0.03] rounded-2xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 rounded-full bg-blue-500/[0.02] blur-xl" />
                <span className="text-[10px] text-zinc-400 uppercase block mb-1 tracking-wider font-semibold">Local ML Engines</span>
                <p className="text-xs text-zinc-400 leading-relaxed font-normal">
                  Embeddings & reranking calculations operate locally inside our Render container on custom-compiled libraries for maximum performance.
                </p>
              </div>
            </div>

            {/* Right Accordion List (7 cols) */}
            <div className="lg:col-span-7 space-y-3">
              {steps.map((step, idx) => {
                const stepNum = idx + 1;
                const isExpanded = expandedStep === stepNum;
                return (
                  <div
                    key={stepNum}
                    data-gsap-arch-step
                    className={`rounded-2xl border transition-all duration-300 overflow-hidden ${isExpanded
                      ? "bg-[#09090c] border-[#45A29E]/30 shadow-[0_4px_30px_rgba(69,162,158,0.04)]"
                      : "bg-zinc-950/20 border-white/[0.03] hover:border-white/[0.08]"
                      }`}
                  >
                    <button
                      onClick={() => setExpandedStep(isExpanded ? null : stepNum)}
                      className="w-full flex items-center justify-between p-5 text-left transition-colors"
                    >
                      <div className="flex items-center gap-5">
                        <span className="text-xs font-mono font-bold text-zinc-400 w-6">
                          {step.num}
                        </span>
                        <div>
                          <span className={`text-sm font-semibold block transition-colors ${isExpanded ? "text-[#45A29E]" : "text-white"}`}>
                            {step.title}
                          </span>
                          <span className="text-xs text-zinc-400 font-normal block mt-0.5">
                            {step.desc}
                          </span>
                        </div>
                      </div>

                      {/* Chevron indicator */}
                      <ChevronRight className={`w-4 h-4 text-zinc-400 transition-transform duration-300 ${isExpanded ? "rotate-90 text-[#45A29E]" : ""}`} />
                    </button>

                    {/* Collapsible Details */}
                    <AnimatePresence initial={false}>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0 }}
                          animate={{ height: "auto" }}
                          exit={{ height: 0 }}
                          transition={{ duration: 0.3, ease: "easeInOut" }}
                        >
                          <div className="px-5 pb-5 pt-1 ml-11 border-t border-white/[0.02]">
                            <p className="text-sm text-zinc-300 font-normal leading-relaxed mb-4">
                              {step.detail}
                            </p>

                            {/* Tech spec snippet */}
                            <div className="bg-zinc-950 border border-white/[0.04] p-3 rounded-lg flex items-center justify-between text-[10px] font-mono text-zinc-400">
                              <span className="flex items-center gap-1.5">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#45A29E]" />
                                status: operational
                              </span>
                              <span>isolation: active</span>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* Page 5: Workflow Section */}
      <section id="how-it-works" className="py-24 relative">
        {/* Section divider line */}
        <div className="section-divider-line w-full absolute top-0" />

        <div className="max-w-7xl mx-auto px-6">

          {/* Header */}
          <div className="mb-16 text-center md:text-left">
            <div data-gsap-section-label className="flex items-center gap-3 mb-4 justify-center md:justify-start">
              <div data-gsap-label-line className="section-divider-line w-8 h-[1px]" />
              <span data-gsap-label-text className="text-xs font-mono font-bold tracking-[0.2em] text-blue-500 uppercase">WORKFLOW</span>
            </div>
            <h2 data-gsap-heading className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4">
              Three steps. <br />
              Zero hallucinations.
            </h2>
          </div>

          {/* Steps Horizontal Grid */}
          <div
            className="grid grid-cols-1 lg:grid-cols-3 gap-6"
          >
            {[
              {
                step: "01",
                title: "Upload once",
                desc: "Drag and drop PDFs, DOCX, or entire drives. We handle OCR, layout, tables, and versioning automatically.",
                icon: Upload
              },
              {
                step: "02",
                title: "Ask anything",
                desc: "Natural language search with hybrid retrieval. Sub-second answers streamed with markdown, code and math.",
                icon: Search
              },
              {
                step: "03",
                title: "Trust the answer",
                desc: "Every sentence carries a citation. Click through to the exact page, highlight, and retrieval score.",
                icon: FileText
              }
            ].map((wf, idx) => {
              const Icon = wf.icon;
              return (
                <div
                  key={idx}
                  data-gsap-wf-card
                  className="glass-card p-6 rounded-2xl flex flex-col justify-between text-left relative overflow-hidden group"
                >
                  <div className="absolute top-0 right-0 w-24 h-24 bg-[#45A29E]/[0.01] rounded-bl-full pointer-events-none group-hover:bg-[#45A29E]/[0.02] transition-colors" />

                  <div>
                    {/* Header line with step number */}
                    <div className="flex items-center justify-between mb-8">
                      <div className="w-10 h-10 rounded-xl bg-zinc-900 border border-white/[0.04] flex items-center justify-center group-hover:border-[#45A29E]/20 transition-colors">
                        <Icon className="w-5 h-5 text-[#45A29E]" />
                      </div>
                      <span className="text-xs font-mono font-bold text-zinc-400 tracking-wider">
                        {wf.step}
                      </span>
                    </div>

                    {/* Title */}
                    <h3 className="text-base font-semibold text-white mb-2 leading-snug">
                      {wf.title}
                    </h3>

                    {/* Description */}
                    <p className="text-zinc-300 text-sm leading-relaxed font-normal font-sans">
                      {wf.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Page 6: Stack Section */}
      <section id="stack" className="py-24 relative">
        {/* Section divider line */}
        <div className="section-divider-line w-full absolute top-0" />

        <div className="max-w-7xl mx-auto px-6 text-center flex flex-col items-center">

          {/* Header */}
          <div className="mb-12">
            <div data-gsap-section-label className="flex items-center gap-3 mb-4 justify-center">
              <div data-gsap-label-line className="section-divider-line w-8 h-[1px]" />
              <span data-gsap-label-text className="text-xs font-mono font-bold tracking-[0.2em] text-blue-500 uppercase">STACK</span>
            </div>
            <h2 data-gsap-heading className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4">
              Built on primitives <br />
              you already trust.
            </h2>
          </div>

          {/* Badges Grid (Responsive Pill Layout) */}
          <div
            className="flex flex-wrap justify-center gap-3 max-w-4xl"
          >
            {techStack.map((tech, idx) => (
              <div
                key={idx}
                data-gsap-stack-pill
                className="bg-zinc-950 hover:bg-zinc-900 border border-white/[0.04] hover:border-[#45A29E]/20 px-4 py-2.5 rounded-full flex items-center gap-2.5 transition-all duration-300"
              >
                {/* Indicator dot */}
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />

                {/* Tech Info */}
                <span className="text-xs font-semibold text-white">{tech.name}</span>
                <span className="text-[10px] text-zinc-400 font-medium font-sans">({tech.category})</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Page 7: CTA Section */}
      <section className="py-20 relative flex justify-center">
        <div className="max-w-5xl mx-auto px-6 w-full">
          <div
            data-gsap-cta
            className="w-full bg-[#08080c] border border-white/[0.06] rounded-3xl p-8 md:p-12 text-center relative overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)]"
          >
            {/* Glowing accents */}
            {/* CTA Glow Border */}
            <div data-gsap-cta-glow className="cta-glow-border" style={{ opacity: 0 }} />

            <div className="absolute inset-0 bg-gradient-to-t from-[#45A29E]/[0.02] to-transparent pointer-events-none" />
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[70%] h-[30%] bg-blue-500/[0.015] blur-2xl rounded-full pointer-events-none" />

            <span className="text-[10px] font-mono font-bold tracking-[0.3em] text-[#45A29E] uppercase block mb-4">DEPLOY INSTANTLY</span>
            <h2 className="text-4xl md:text-5xl font-serif text-white tracking-tight mb-4 max-w-2xl mx-auto leading-tight">
              Ship RAG that <br />
              you&apos;d trust yourself.
            </h2>
            <p className="text-zinc-300 text-sm md:text-base font-sans font-normal leading-relaxed max-w-xl mx-auto mb-8">
              Start with the free tier. Move to production when your evaluations say so — not because someone told you it&apos;s time.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a href="/login" className="flex items-center gap-2 bg-white hover:bg-zinc-200 text-black px-6 py-3 rounded-full text-xs font-semibold transition-all hover:scale-[1.02] shadow-[0_4px_15px_rgba(255,255,255,0.08)]">
                Get started free <ArrowRight className="w-4 h-4" />
              </a>
              <a href="/login" className="bg-zinc-900 border border-white/[0.06] hover:bg-zinc-800 text-white px-6 py-3 rounded-full text-xs font-semibold transition-all">
                Talk to sales
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Page 8: Footer Section */}
      <footer data-gsap-footer className="pt-20 pb-10 bg-[#020203] relative">
        {/* Section divider line */}
        <div className="section-divider-line w-full absolute top-0" />

        <div className="max-w-7xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 mb-16">

            {/* Logo and Tagline (5 cols) */}
            <div className="lg:col-span-5 flex flex-col justify-start items-start">
              <a href="#" className="flex items-center gap-2 mb-4 group">
                <span className="text-white font-semibold text-lg tracking-tight">Cited.AI</span>
              </a>
              <p className="text-zinc-400 text-xs leading-relaxed font-normal max-w-xs mb-4">
                The retrieval platform for teams that can&apos;t afford hallucinations.
              </p>
            </div>

            {/* Links Columns (7 cols) - Carded View */}
            <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-3 gap-6">
              {[
                {
                  title: "Product",
                  desc: "Fact-checked document grounded search utilizing hybrid dense/sparse pipelines to eliminate hallucinations.",
                  links: [
                    { name: "Features", href: "#features" },
                    { name: "Architecture", href: "#architecture" },
                    { name: "Evaluation", href: "#how-it-works" }
                  ]
                },
                {
                  title: "Developers",
                  desc: "API-first endpoints for custom applications. Streamlined chunking, indexing and fact-checking via REST.",
                  links: [
                    { name: "Docs & Reference", href: "/dashboard/settings" },
                    { name: "System Status", href: "/dashboard" }
                  ]
                },
                {
                  title: "Company",
                  desc: "Strict compliance frameworks, secure multi-tenant isolated vector indexes, and GDPR-ready data policies.",
                  links: [
                    { name: "Security Standards", href: "#" },
                    { name: "Privacy Policy", href: "#" }
                  ]
                }
              ].map((col, idx) => (
                <div key={idx} className="flex flex-col text-left p-5 bg-zinc-950/80 border border-white/[0.04] rounded-2xl relative overflow-hidden group hover:border-[#45A29E]/20 transition-all duration-300">
                  <div className="absolute inset-0 bg-gradient-to-b from-[#45A29E]/[0.01] to-transparent pointer-events-none" />
                  <span className="text-xs font-bold text-white uppercase tracking-wider block mb-2">
                    {col.title}
                  </span>
                  <p className="text-zinc-400 text-xs font-normal leading-relaxed mb-4 flex-1">
                    {col.desc}
                  </p>
                  <ul className="space-y-2 border-t border-white/[0.02] pt-3">
                    {col.links.map((link, lIdx) => (
                      <li key={lIdx}>
                        <a href={link.href} className="text-xs text-[#45A29E] hover:text-white transition-colors font-medium flex items-center gap-1 group/link">
                          <span>{link.name}</span>
                          <span className="inline-block transform group-hover/link:translate-x-0.5 transition-transform">&rarr;</span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom metadata row */}
          <div className="pt-8 border-t border-white/[0.02] flex flex-col sm:flex-row justify-between items-center gap-4">
            <span className="text-[10px] text-zinc-400 font-normal">
              © 2026 Cited.AI • A grounded retrieval platform
            </span>

            {/* Operational status */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-950 border border-white/[0.02]">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
              </span>
              <span className="text-[10px] text-zinc-400 font-semibold font-sans tracking-wide">All systems operational</span>
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}
