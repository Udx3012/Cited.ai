"use client";

import React, { useState, useEffect } from "react";
import { 
  Settings, Key, Layers, Sliders, CheckCircle2, 
  HelpCircle, Eye, EyeOff, Save, RefreshCw
} from "lucide-react";

export default function WorkspaceSettings() {
  const [showApiKey, setShowApiKey] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Form states
  const [modelType, setModelType] = useState("high");
  const [denseWeight, setDenseWeight] = useState(0.7);
  const [sparseWeight, setSparseWeight] = useState(0.3);
  const [chunkSize, setChunkSize] = useState(500);
  const [chunkOverlap, setChunkOverlap] = useState(50);
  const [temperature, setTemperature] = useState(0.0);
  const [backendUrl, setBackendUrl] = useState(process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1");
  const [apiKey, setApiKey] = useState("my_super_secret_cited_ai_key_2026");

  // Load values on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      setBackendUrl(localStorage.getItem("cited_backend_url") || process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000/api/v1");
      setApiKey(localStorage.getItem("cited_api_key") || "my_super_secret_cited_ai_key_2026");
      setModelType(localStorage.getItem("cited_model_type") || "high");
      setDenseWeight(parseFloat(localStorage.getItem("cited_dense_weight") || "0.7"));
      setSparseWeight(parseFloat(localStorage.getItem("cited_sparse_weight") || "0.3"));
      setChunkSize(parseInt(localStorage.getItem("cited_chunk_size") || "500"));
      setChunkOverlap(parseInt(localStorage.getItem("cited_chunk_overlap") || "50"));
      setTemperature(parseFloat(localStorage.getItem("cited_temperature") || "0.0"));
    }
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    
    if (typeof window !== "undefined") {
      localStorage.setItem("cited_backend_url", backendUrl);
      localStorage.setItem("cited_api_key", apiKey);
      localStorage.setItem("cited_model_type", modelType);
      localStorage.setItem("cited_dense_weight", String(denseWeight));
      localStorage.setItem("cited_sparse_weight", String(sparseWeight));
      localStorage.setItem("cited_chunk_size", String(chunkSize));
      localStorage.setItem("cited_chunk_overlap", String(chunkOverlap));
      localStorage.setItem("cited_temperature", String(temperature));
    }
    
    setTimeout(() => {
      setIsSaving(false);
    }, 500);
  };

  return (
    <div className="space-y-6 max-w-4xl text-left">
      
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-serif text-white tracking-tight">Settings</h1>
        <p className="text-zinc-400 text-xs font-normal mt-1">
          Adjust pipeline ingestion parameters, weight allocations, and service integrations.
        </p>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        
        {/* Section 1: API Configuration */}
        <div className="glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/[0.03] pb-3 mb-1">
            <Key className="w-4 h-4 text-[#45A29E]" />
            <h3 className="text-sm font-semibold text-white">API Keys & Integrations</h3>
          </div>

          <div className="space-y-4">
            {/* API Key field */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300 flex items-center justify-between">
                <span>RAG Service Key</span>
                <span className="text-xs text-zinc-400 font-mono">Used for backend endpoint X-API-Key auth</span>
              </label>
              <div className="flex items-center gap-3 relative">
                <input 
                  type={showApiKey ? "text" : "password"}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter backend api key"
                  className="bg-zinc-950 text-xs font-mono px-4 py-3 rounded-xl border border-white/[0.04] w-full text-zinc-200 focus:outline-none focus:border-[#45A29E]/30 transition-colors"
                />
                <button 
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-4 text-zinc-400 hover:text-white"
                >
                  {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Ingestion API Endpoint */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300 block">FastAPI Backend URL</label>
              <input 
                type="text"
                value={backendUrl}
                onChange={(e) => setBackendUrl(e.target.value)}
                placeholder="http://localhost:8000/api/v1"
                className="bg-zinc-950 text-xs font-mono px-4 py-3 rounded-xl border border-white/[0.04] w-full text-zinc-200 focus:outline-none focus:border-[#45A29E]/30 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* Section 2: Retrieval Parameters */}
        <div className="glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/[0.03] pb-3 mb-1">
            <Sliders className="w-4 h-4 text-[#45A29E]" />
            <h3 className="text-sm font-semibold text-white">Hybrid Retrieval Weights (RRF)</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Dense search slider */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium text-zinc-300">
                <span>Dense Search Weight (Qdrant)</span>
                <span className="font-mono text-[#45A29E] font-bold">{denseWeight}</span>
              </div>
              <input 
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={denseWeight}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setDenseWeight(val);
                  setSparseWeight(parseFloat((1 - val).toFixed(2)));
                }}
                className="w-full h-1.5 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#45A29E]"
              />
              <span className="text-xs text-zinc-400 font-normal block leading-relaxed">
                Prioritizes conceptual/semantic matches over raw wording.
              </span>
            </div>

            {/* Sparse search slider */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium text-zinc-300">
                <span>Sparse Search Weight (BM25)</span>
                <span className="font-mono text-[#45A29E] font-bold">{sparseWeight}</span>
              </div>
              <input 
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={sparseWeight}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setSparseWeight(val);
                  setDenseWeight(parseFloat((1 - val).toFixed(2)));
                }}
                className="w-full h-1.5 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#45A29E]"
              />
              <span className="text-xs text-zinc-400 font-normal block leading-relaxed">
                Prioritizes exact keyword matches, code symbols, and numbers.
              </span>
            </div>
          </div>
        </div>

        {/* Section 3: Ingestion & Chunking parameters */}
        <div className="glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/[0.03] pb-3 mb-1">
            <Layers className="w-4 h-4 text-[#45A29E]" />
            <h3 className="text-sm font-semibold text-white">Ingestion Chunking Strategy</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Chunk size input */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300 block">Chunk Token Size (Characters)</label>
              <input 
                type="number"
                value={chunkSize}
                onChange={(e) => setChunkSize(parseInt(e.target.value) || 0)}
                className="bg-zinc-950 text-xs px-4 py-3 rounded-xl border border-white/[0.04] w-full text-zinc-200 focus:outline-none focus:border-[#45A29E]/30 font-semibold font-mono"
              />
              <span className="text-xs text-zinc-400 font-normal block">
                Target length for dividing document paragraphs. Recommended: 500 characters.
              </span>
            </div>

            {/* Chunk overlap input */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-zinc-300 block">Chunk Overlap (Characters)</label>
              <input 
                type="number"
                value={chunkOverlap}
                onChange={(e) => setChunkOverlap(parseInt(e.target.value) || 0)}
                className="bg-zinc-950 text-xs px-4 py-3 rounded-xl border border-white/[0.04] w-full text-zinc-200 focus:outline-none focus:border-[#45A29E]/30 font-semibold font-mono"
              />
              <span className="text-xs text-zinc-400 font-normal block">
                Preserves textual boundary context between adjacent chunks. Recommended: 10%.
              </span>
            </div>
          </div>
        </div>

        {/* Section 4: AI Model Selection */}
        <div className="glass-card rounded-2xl p-5 space-y-4">
          <div className="flex items-center gap-2 border-b border-white/[0.03] pb-3 mb-1">
            <Settings className="w-4 h-4 text-[#45A29E]" />
            <h3 className="text-sm font-semibold text-white">AI Generation Parameters</h3>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Model classification */}
            <div className="space-y-2 text-left">
              <label className="text-xs font-medium text-zinc-300 block">Primary Synthesis Model</label>
              <select 
                value={modelType}
                onChange={(e) => setModelType(e.target.value)}
                className="bg-zinc-950 text-xs px-4 py-3 rounded-xl border border-white/[0.04] w-full text-zinc-200 focus:outline-none cursor-pointer"
              >
                <option value="high" className="bg-zinc-950">High Quality (70B parameters)</option>
                <option value="standard" className="bg-zinc-950">Standard (8B parameters)</option>
                <option value="custom" className="bg-zinc-950">Custom Endpoint</option>
              </select>
            </div>

            {/* Model temperature */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs font-medium text-zinc-300">
                <span>Model Temperature (Factual vs Creative)</span>
                <span className="font-mono text-[#45A29E] font-bold">{temperature}</span>
              </div>
              <input 
                type="range"
                min="0.0"
                max="1.0"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full h-1.5 bg-zinc-950 rounded-lg appearance-none cursor-pointer accent-[#45A29E]"
              />
              <span className="text-xs text-zinc-400 font-normal block leading-relaxed">
                Set to 0.0 for strict, hallucination-free factual citation summaries.
              </span>
            </div>
          </div>
        </div>

        {/* Action submit button */}
        <div className="flex justify-end gap-3">
          <button 
            type="submit"
            disabled={isSaving}
            className="flex items-center gap-2 bg-[#45A29E] hover:bg-[#398a87] text-black px-6 py-3 rounded-full text-xs font-semibold transition-all hover:scale-[1.02] shadow-[0_4px_15px_rgba(69,162,158,0.12)] cursor-pointer disabled:opacity-50"
          >
            {isSaving ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            Save Configuration
          </button>
        </div>

      </form>

    </div>
  );
}
